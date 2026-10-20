import importlib.util
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import tempfile
import unittest

HAS_STORAGE = importlib.util.find_spec('storage') is not None
if HAS_STORAGE:
    from storage import SQLiteOrderStore, OrderStoreError, default_database_path

ROWS = (('Cafe Latte', 2, 158), ('Matcha Latte', 1, 109))


class StorageAvailabilityTests(unittest.TestCase):
    def test_repository_exists(self):
        self.assertTrue(HAS_STORAGE, 'The transactional order repository is missing')


@unittest.skipUnless(HAS_STORAGE, 'Storage implementation not present')
class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'nested' / 'orders.sqlite3'
        self.store = SQLiteOrderStore(self.path)

    def save(self, key='first'):
        return self.store.save(ROWS, 267, request_id=key)

    def test_save_and_reload(self):
        receipt = self.save()
        reopened = SQLiteOrderStore(self.path)
        self.assertEqual(reopened.get(receipt.number), receipt)
        self.assertEqual(receipt.lines, ROWS)
        self.assertIn('+00:00', receipt.created_at)
        self.assertEqual(receipt.payment_status, 'PAYMENT PENDING')

    def test_numbers_survive_new_repository(self):
        self.assertEqual(self.save().number, 1)
        self.assertEqual(SQLiteOrderStore(self.path).save(ROWS, 267, request_id='next').number, 2)

    def test_idempotency(self):
        a, b = self.save(), self.save()
        self.assertEqual(a, b)
        self.assertEqual(len(self.store.all()), 1)

    def test_key_cannot_be_reused_for_different_order(self):
        self.save()
        with self.assertRaises(OrderStoreError):
            self.store.save((('Other',1,5),), 5, request_id='first')
        self.assertEqual(len(self.store.all()), 1)

    def test_multiple_connections_concurrent_order_numbers(self):
        def create(i):
            return SQLiteOrderStore(self.path).save(ROWS, 267, request_id=f'key-{i}').number
        with ThreadPoolExecutor(max_workers=8) as pool:
            numbers = list(pool.map(create, range(32)))
        self.assertEqual(sorted(numbers), list(range(1, 33)))

    def test_concurrent_retry_is_one_order(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            numbers = list(pool.map(lambda _: self.save().number, range(16)))
        self.assertEqual(set(numbers), {1})
        self.assertEqual(len(self.store.all()), 1)

    def test_insert_failure_rolls_back_order_and_lines(self):
        # db commits/rolls back first; closing then releases the database file.
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TRIGGER force_failure BEFORE INSERT ON order_lines "
                       "WHEN NEW.name = 'Matcha Latte' BEGIN SELECT RAISE(ABORT, 'forced'); END")
        with self.assertRaises(OrderStoreError):
            self.save()
        with closing(sqlite3.connect(self.path)) as db, db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM orders').fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM order_lines').fetchone()[0], 0)

    def test_corrupt_database_reports_storage_error(self):
        path = Path(self.temp.name) / 'corrupt.sqlite3'
        path.write_bytes(b'not a database')
        with self.assertRaises(OrderStoreError):
            SQLiteOrderStore(path)

    def test_future_schema_rejected(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('PRAGMA user_version=99')
        with self.assertRaises(OrderStoreError):
            SQLiteOrderStore(self.path)

    def test_unrelated_database_not_modified(self):
        other = Path(self.temp.name) / 'unrelated.sqlite3'
        with closing(sqlite3.connect(other)) as db, db:
            db.execute('CREATE TABLE unrelated(value TEXT)')
        with self.assertRaises(OrderStoreError):
            SQLiteOrderStore(other)
        with closing(sqlite3.connect(other)) as db, db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 0)

    def test_invalid_total_rejected_without_saving(self):
        with self.assertRaises(ValueError):
            self.store.save(ROWS, 1, request_id='bad')
        self.assertEqual(self.store.all(), ())

    def test_empty_request_id_rejected(self):
        with self.assertRaises(ValueError):
            self.store.save(ROWS, 267, request_id='')

    def test_recent_descending_and_limited(self):
        for i in range(4):
            self.save(str(i))
        self.assertEqual([r.number for r in self.store.recent(2)], [4, 3])
        self.assertEqual([r.number for r in self.store.all()], [1, 2, 3, 4])

    def test_missing_order_returns_none(self):
        self.assertIsNone(self.store.get(99))

    def test_invalid_query_arguments(self):
        for value in (0, -1, True, 1.5):
            with self.subTest(value=value), self.assertRaises((ValueError, TypeError)):
                self.store.get(value)
            with self.subTest(limit=value), self.assertRaises((ValueError, TypeError)):
                self.store.recent(value)

    def test_backup_restores_orders_and_sequence(self):
        original = self.save()
        path = Path(self.temp.name) / 'backup.sqlite3'
        self.store.backup(path)
        backup = SQLiteOrderStore(path)
        self.assertEqual(backup.get(1), original)
        self.assertEqual(backup.save(ROWS, 267, request_id='after-backup').number, 2)

    def test_backup_refuses_existing_file(self):
        path = Path(self.temp.name) / 'existing.txt'
        path.write_text('keep this')
        with self.assertRaises((OrderStoreError, FileExistsError)):
            self.store.backup(path)
        self.assertEqual(path.read_text(), 'keep this')

    def test_default_path_independent_of_cwd(self):
        from unittest.mock import patch
        with patch.dict('os.environ', {}, clear=True):
            self.assertEqual(default_database_path().parent.name, 'data')
            self.assertTrue(default_database_path().is_absolute())

    def test_env_data_directory(self):
        from unittest.mock import patch
        with patch.dict('os.environ', {'KIOSKU_DATA_DIR': self.temp.name}):
            self.assertEqual(default_database_path(), Path(self.temp.name) / 'orders.sqlite3')


if __name__ == '__main__':
    unittest.main()
