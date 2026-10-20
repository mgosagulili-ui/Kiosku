"""End-to-end model/controller/SQLite checks for POS and operator features."""
import sqlite3
from contextlib import closing
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from controllers import KioskController
from storage import SQLiteOrderStore, OrderStoreError, LOCAL_TZ


class BusinessFeatureTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / 'orders.sqlite3'
        self.store = SQLiteOrderStore(self.path)
        self.ctl = KioskController(store=self.store)
        self.coffee = self.ctl.items_in('Coffee')[0]

    def today(self):
        return str(datetime.now(LOCAL_TZ).date())

    def test_categories_product_creation_and_restart(self):
        self.ctl.create_category('Pastries')
        iid = self.ctl.create_product('Brownie', 'Pastries', 65, 12)
        product = next(p for p in self.ctl.inventory() if p.id == iid)
        self.assertEqual((product.stock, product.price), (12, 65))
        reopened = KioskController(store=SQLiteOrderStore(self.path))
        self.assertEqual(reopened.items_in('Pastries')[0].name, 'Brownie')
        self.assertEqual(reopened.items_in('Pastries')[0].stock, 12)
        self.assertEqual(len([p for p in reopened.inventory() if p.id == iid]), 1)

    def test_edit_logs_stock_changes_and_archive_retains_history(self):
        self.ctl.create_category('Treats')
        iid = self.ctl.create_product('Brownie', 'Treats', 65, 12)
        self.ctl.update_product(iid, 'Fudge Brownie', 'Treats', 70, 20, 'DELIVERY')
        item = next(p for p in self.ctl.inventory() if p.id == iid)
        self.assertEqual((item.name, item.price, item.stock), ('Fudge Brownie',70,20))
        movements = [m for m in self.store.movements() if m.item_id == iid]
        self.assertEqual([(m.before, m.after) for m in movements], [(12, 20), (None, 12)])
        self.ctl.archive_product(iid)
        self.assertFalse(any(p.id == iid for p in self.ctl.inventory()))
        self.assertTrue(any(p.id == iid for p in self.ctl.inventory(True)))
        self.assertEqual(len([m for m in SQLiteOrderStore(self.path).movements() if m.item_id == iid]),2)
        self.ctl.restore_product(iid)
        self.assertTrue(any(p.id == iid for p in self.ctl.inventory()))

    def test_bulk_restock_adds_different_quantities_and_persists(self):
        first = self.coffee
        second = self.ctl.items_in('Coffee')[1]
        self.ctl.bulk_restock({first.id: 8, second.id: 12}, mode='SET', reason='OPENING COUNT')
        self.ctl.bulk_restock({first.id: 5, second.id: 2}, mode='ADD', reason='DELIVERY')
        current = {p.id: p.stock for p in SQLiteOrderStore(self.path).products()}
        self.assertEqual((current[first.id], current[second.id]), (13, 14))
        movements = [m for m in self.store.movements() if m.reason == 'DELIVERY']
        self.assertEqual(len(movements), 2)
        self.assertEqual({m.item_id: (m.before, m.after) for m in movements},
                         {first.id: (8, 13), second.id: (12, 14)})

    def test_bulk_restock_is_atomic_when_any_product_untracked(self):
        first = self.coffee
        second = self.ctl.items_in('Coffee')[1]
        self.ctl.bulk_restock({first.id: 10}, mode='SET')
        old = len(self.store.movements())
        with self.assertRaisesRegex(ValueError, 'Set exact stock first'):
            self.ctl.bulk_restock({first.id: 3, second.id: 5}, mode='ADD')
        self.assertEqual(next(i.stock for i in self.store.products() if i.id == first.id), 10)
        self.assertIsNone(next(i.stock for i in self.store.products() if i.id == second.id))
        self.assertEqual(len(self.store.movements()), old)

    def test_bulk_restock_validates_all_inputs_before_writing(self):
        ids = [p.id for p in self.ctl.items_in('Coffee')[:2]]
        for entries, mode in [({ids[0]: 3, ids[1]: -1}, 'SET'),
                              ({ids[0]: 1, 'nonexistent': 3}, 'SET'),
                              ({ids[0]: 0}, 'ADD'),
                              ({ids[0]: True}, 'SET'),
                              ({}, 'SET')]:
            with self.subTest(entries=entries, mode=mode), self.assertRaises((ValueError, TypeError)):
                self.ctl.bulk_restock(entries, mode=mode)
        self.assertEqual(len(self.store.movements()), 0)
        self.assertTrue(all(p.stock is None for p in self.store.products()[:2]))

    def test_bulk_restock_exact_zero_and_noop_tracking(self):
        product = self.coffee
        self.ctl.bulk_restock({product.id: 0}, mode='SET', reason='FIRST COUNT')
        self.assertEqual(next(p.stock for p in self.store.products() if p.id == product.id), 0)
        count = len(self.store.movements())
        self.ctl.bulk_restock({product.id: 0}, mode='SET')
        self.assertEqual(len(self.store.movements()), count)

    def test_cash_change_stock_and_report_persist(self):
        self.ctl.update_product(self.coffee.id, self.coffee.name, self.coffee.category,
                                self.coffee.price, 4, 'OPENING COUNT')
        self.ctl.add_item(self.coffee.id)
        self.ctl.add_item(self.coffee.id)
        receipt = self.ctl.checkout(payment_method='CASH', cash_received=200)
        self.assertEqual((receipt.total, receipt.cash_received, receipt.change_due), (158,200,42))
        store = SQLiteOrderStore(self.path)
        self.assertEqual(store.get(receipt.number), receipt)
        self.assertEqual(next(p for p in store.products() if p.id == self.coffee.id).stock,2)
        report = store.sales_report(self.today(), self.today())
        self.assertEqual((report.gross_sales, report.order_count, report.units_sold), (158,1,2))
        self.assertEqual((report.cash_sales, report.qr_sales, report.cash_orders), (158,0,1))
        self.assertEqual(report.by_product[0], ('Cafe Latte',2,158))

    def test_qr_is_saved_without_fake_cash_details(self):
        self.ctl.add_item(self.coffee.id)
        receipt = self.ctl.checkout(payment_method='QR')
        self.assertEqual(receipt.payment_status, 'PAID')
        self.assertIsNone(receipt.cash_received)
        report = self.store.sales_report(self.today(), self.today())
        self.assertEqual(report.qr_sales,79)
        self.assertEqual(report.qr_orders,1)

    def test_validation_blocks_underpayment_and_keeps_cart(self):
        self.ctl.add_item(self.coffee.id)
        for payment, cash in [('CASH',20), ('CASH',None), ('QR',50), ('invalid',None)]:
            with self.subTest(payment=payment, cash=cash), self.assertRaises((ValueError, TypeError)):
                self.ctl.checkout(payment_method=payment, cash_received=cash)
        self.assertEqual(self.store.all(), ())
        self.assertEqual(self.ctl.cart_count(),1)

    def test_out_of_stock_is_rejected_and_no_partial_order(self):
        self.ctl.update_product(self.coffee.id, self.coffee.name, self.coffee.category,
                                self.coffee.price, 1)
        self.ctl.add_item(self.coffee.id)
        other = KioskController(store=self.store)
        other.add_item(self.coffee.id)
        other.checkout(payment_method='QR')
        with self.assertRaises(ValueError):
            self.ctl.checkout(payment_method='QR')
        self.assertEqual(self.ctl.cart_count(),1)
        self.assertEqual(len(self.store.all()),1)
        self.assertEqual(next(i.stock for i in self.store.products() if i.id == self.coffee.id),0)

    def test_replay_does_not_deduct_stock_twice(self):
        self.ctl.update_product(self.coffee.id, self.coffee.name, self.coffee.category,
                                self.coffee.price, 2)
        kwargs = dict(payment_method='QR', item_ids=(self.coffee.id,), request_id='repeat')
        lines = ((self.coffee.name, 1, self.coffee.price),)
        receipts = [self.store.save(lines, self.coffee.price, **kwargs) for _ in range(2)]
        self.assertEqual(receipts[0],receipts[1])
        self.assertEqual(next(i.stock for i in self.store.products() if i.id == self.coffee.id),1)
        self.assertEqual(len([m for m in self.store.movements() if m.reason=='SALE']),1)

    def test_repository_aggregates_duplicate_product_rows(self):
        self.ctl.update_product(self.coffee.id, self.coffee.name, self.coffee.category,
                                self.coffee.price, 1)
        rows = ((self.coffee.name,1,self.coffee.price),) * 2
        with self.assertRaises(ValueError):
            self.store.save(rows, self.coffee.price*2,
                            request_id='duplicated',payment_method='QR',
                            item_ids=(self.coffee.id,self.coffee.id))
        self.assertEqual(len(self.store.all()), 0)
        self.assertEqual(next(p.stock for p in self.store.products() if p.id == self.coffee.id),1)

    def test_concurrent_checkout_cannot_oversell(self):
        self.ctl.update_product(self.coffee.id, self.coffee.name, self.coffee.category,
                                self.coffee.price, 1)
        def order(i):
            try:
                return bool(self.store.save(((self.coffee.name,1,self.coffee.price),),
                       self.coffee.price, request_id=f'concurrent-{i}', payment_method='QR',
                       item_ids=(self.coffee.id,)))
            except ValueError:
                return False
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(order, (1,2)))
        self.assertEqual(outcomes.count(True),1)
        self.assertEqual(len(self.store.all()),1)

    def test_unpaid_legacy_ticket_excluded_from_paid_sales(self):
        self.store.save(((self.coffee.name,1,79),),79,request_id='legacy')
        self.ctl.add_item(self.coffee.id)
        self.ctl.checkout(payment_method='CASH',cash_received=80)
        report = self.store.sales_report(self.today(),self.today())
        self.assertEqual(report.gross_sales,79)
        self.assertEqual(len(self.store.orders_between(self.today(),self.today())),2)

    def test_legacy_v1_migrates_without_losing_orders(self):
        # Build a genuine v1 database from the original layout.
        old = self.path.parent/'legacy.sqlite3'
        # sqlite3.Connection.__exit__ commits but does not close the file.
        # Windows will lock legacy.sqlite3 until closing() releases it.
        with closing(sqlite3.connect(old)) as db, db:
            db.execute('CREATE TABLE orders(number INTEGER PRIMARY KEY AUTOINCREMENT, '
                       'request_id TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL, total INTEGER NOT NULL)')
            db.execute('CREATE TABLE order_lines(order_number INTEGER NOT NULL, position INTEGER NOT NULL, '
                       'name TEXT NOT NULL, quantity INTEGER NOT NULL, subtotal INTEGER NOT NULL, '
                       'PRIMARY KEY(order_number,position))')
            db.execute('INSERT INTO orders VALUES(1,?,?,?)',('previous','2026-10-01T00:00:00+00:00',79))
            db.execute('INSERT INTO order_lines VALUES(1,0,?,1,79)',('Cafe Latte',))
            db.execute('PRAGMA user_version=1')
            db.execute('PRAGMA application_id=0x4B494F53')
        migrated = SQLiteOrderStore(old)
        self.assertEqual(migrated.get(1).payment_status,'PAYMENT PENDING')
        self.assertEqual(migrated.get(1).lines, (('Cafe Latte',1,79),))
        self.assertEqual(len(migrated.products()),17)
        self.assertEqual(migrated.save((('X',1,10),),10,request_id='next').number,2)

    def test_day_range_and_historical_stock_counts(self):
        iid = self.ctl.create_product('Cookie', 'Coffee', 20, 10)
        self.assertEqual(self.store.stock_at(self.today())[iid],10)
        self.ctl.update_product(iid,'Cookie','Coffee',20,7,'DAMAGE')
        self.assertEqual(self.store.stock_at(self.today())[iid],7)
        yesterday = str(datetime.now(LOCAL_TZ).date()-timedelta(days=1))
        self.assertNotIn(iid,self.store.stock_at(yesterday))
        self.assertFalse(any(m.item_id == iid for m in self.store.movements(yesterday,yesterday)))
        with self.assertRaises(ValueError):
            self.store.sales_report(self.today(),yesterday)

if __name__ == '__main__':
    unittest.main()
