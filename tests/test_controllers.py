from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import inspect
import logging
import tempfile
import unittest
from controllers import KioskController
from models import Cart, Coffee, Menu

HAS_STORE = 'store' in inspect.signature(KioskController).parameters
if HAS_STORE:
    from storage import SQLiteOrderStore, OrderStoreError


class ControllerContractTests(unittest.TestCase):
    def test_controller_accepts_durable_store(self):
        self.assertTrue(HAS_STORE, 'Controller cannot persist orders')


@unittest.skipUnless(HAS_STORE, 'Durable controller not present')
class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = SQLiteOrderStore(Path(self.temp.name) / 'orders.sqlite3')
        self.ctl = KioskController(store=self.store)
        self.iid = self.ctl.items_in('Coffee')[0].id

    def test_empty_checkout_does_not_allocate_number(self):
        self.assertIsNone(self.ctl.checkout())
        self.ctl.add_item(self.iid)
        self.assertEqual(self.ctl.checkout().number, 1)

    def test_checkout_saves_before_clearing(self):
        self.ctl.add_item(self.iid)
        receipt = self.ctl.checkout()
        self.assertEqual(self.store.get(receipt.number), receipt)
        self.assertEqual(self.ctl.cart_count(), 0)
        self.assertEqual(self.ctl.last_receipt, receipt)

    def test_sessions_have_separate_carts_and_shared_sequence(self):
        other = KioskController(store=self.store)
        self.ctl.add_item(self.iid)
        self.assertEqual(other.cart_count(), 0)
        other.add_item(self.iid)
        self.assertEqual((self.ctl.checkout().number, other.checkout().number), (1,2))

    def test_repeat_checkout_does_not_duplicate(self):
        self.ctl.add_item(self.iid)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.ctl.checkout(), range(12)))
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertEqual(len(self.store.all()), 1)

    def test_concurrent_adds_do_not_lose_updates(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda _: self.ctl.add_item(self.iid), range(60)))
        self.assertEqual(self.ctl.cart_count(), 60)
        self.assertEqual(self.ctl.cart_total(), 60 * 79)

    def test_failed_save_keeps_cart(self):
        class BrokenStore:
            def save(self, *args, **kwargs):
                raise OrderStoreError('forced failure')
        ctl = KioskController(store=BrokenStore())
        ctl.add_item(self.iid)
        with self.assertRaises(OrderStoreError):
            ctl.checkout()
        self.assertEqual((ctl.cart_count(), ctl.cart_total()), (1,79))
        self.assertIsNone(ctl.last_receipt)

    def test_retry_after_ambiguous_success_reuses_request_id(self):
        store = self.store
        class UncertainStore:
            failed = False
            def save(self, *args, **kwargs):
                saved = store.save(*args, **kwargs)
                if not self.failed:
                    self.failed = True
                    raise OrderStoreError('connection lost after commit')
                return saved
        ctl = KioskController(store=UncertainStore())
        ctl.add_item(self.iid)
        with self.assertRaises(OrderStoreError):
            ctl.checkout()
        self.assertEqual(ctl.checkout().number, 1)
        self.assertEqual(len(self.store.all()), 1)

    def test_preview_does_not_place_order(self):
        self.assertIsNone(self.ctl.preview())
        self.ctl.add_item(self.iid)
        self.assertEqual(self.ctl.preview().total, 79)
        self.assertEqual(self.store.all(), ())
        self.assertEqual(self.ctl.cart_count(), 1)

    def test_changed_order_requires_new_review(self):
        self.ctl.add_item(self.iid)
        preview = self.ctl.preview()
        self.ctl.add_item(self.iid)
        with self.assertRaises(ValueError):
            self.ctl.checkout(expected_lines=preview.lines)
        self.assertEqual(self.store.all(), ())
        self.assertEqual(self.ctl.cart_count(), 2)

    def test_matching_review_can_be_saved(self):
        self.ctl.add_item(self.iid)
        self.assertEqual(self.ctl.checkout(expected_lines=self.ctl.preview().lines).total,79)

    def test_listener_bind_is_deduplicated_and_unbind_works(self):
        calls = []
        def refresh(): calls.append(1)
        self.ctl.bind(refresh)
        self.ctl.bind(refresh)
        self.ctl.add_item(self.iid)
        self.assertEqual(calls, [1])
        self.ctl.unbind(refresh)
        self.ctl.add_item(self.iid)
        self.assertEqual(calls, [1])

    def test_listener_failure_does_not_hide_committed_order(self):
        self.ctl.add_item(self.iid)
        def fail(): raise RuntimeError('view failed')
        self.ctl.bind(fail)
        with self.assertLogs('controllers', logging.ERROR):
            ticket = self.ctl.checkout()
        self.assertEqual(self.store.get(ticket.number), ticket)
        self.assertEqual(self.ctl.cart_count(), 0)

    def test_invalid_item_does_not_change_cart(self):
        with self.assertRaises(ValueError):
            self.ctl.add_item('missing')
        self.assertEqual(self.ctl.cart_count(), 0)

    def test_injected_menu_and_cart_are_used(self):
        item = Coffee('custom', 'Custom', 10)
        cart = Cart()
        cart.add(item, 2)
        ctl = KioskController(Menu([item]), cart, store=self.store)
        self.assertEqual(ctl.cart_total(), 20)

    def test_remove_and_clear(self):
        self.ctl.add_item(self.iid)
        self.ctl.change_quantity(self.iid, 1)
        self.assertEqual(self.ctl.quantity_of(self.iid), 2)
        self.ctl.remove_item(self.iid)
        self.assertEqual(self.ctl.cart_lines(), ())
        self.ctl.add_item(self.iid)
        self.ctl.clear_cart()
        self.assertEqual(self.ctl.cart_total(), 0)


if __name__ == '__main__':
    unittest.main()
