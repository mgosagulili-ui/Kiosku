"""Catch the SQLite test-fixture leaks even on systems that allow open-file deletion.

These checks run the three reported scenarios with real SQLite connections.
Only connection creation is wrapped, to retain references for inspection.
"""
from contextlib import closing
import sqlite3
import unittest
from unittest.mock import patch

from tests import test_storage, test_business_features


@unittest.skipUnless(test_storage.HAS_STORAGE, 'Storage implementation not present')
class StorageConnectionCleanupTests(unittest.TestCase):
    def _assert_connections_closed(self, method_name, case_type=test_storage.StorageTests):
        connections = []
        real_connect = sqlite3.connect

        def tracked_connect(*args, **kwargs):
            connection = real_connect(*args, **kwargs)
            connections.append(connection)
            return connection

        case = case_type(method_name)
        try:
            with patch.object(sqlite3, 'connect', new=tracked_connect):
                case.setUp()
                getattr(case, method_name)()

            self.assertTrue(connections, 'The scenario must open a real database.')
            for index, connection in enumerate(connections):
                with self.subTest(scenario=method_name, connection=index):
                    with self.assertRaisesRegex(sqlite3.ProgrammingError, 'closed database'):
                        # If the database is still open, close our probe cursor,
                        # but do not close the connection before checking it.
                        with closing(connection.execute('SELECT 1')) as cursor:
                            cursor.fetchone()
        finally:
            # Keep a failing regression check from leaving files locked itself.
            # This happens AFTER the connection-closed assertions, not before.
            for connection in connections:
                connection.close()
            self.assertTrue(case.doCleanups(), 'Temporary-database cleanup failed.')

    def test_future_schema_releases_connections(self):
        self._assert_connections_closed('test_future_schema_rejected')

    def test_failed_insert_releases_connections(self):
        self._assert_connections_closed('test_insert_failure_rolls_back_order_and_lines')

    def test_unrelated_database_releases_connections(self):
        self._assert_connections_closed('test_unrelated_database_not_modified')

    def test_legacy_migration_releases_connections(self):
        # Recreate the Windows-only lock: verify ALL connections are closed
        # before TemporaryDirectory.cleanup(), even on Linux.
        self._assert_connections_closed('test_legacy_v1_migrates_without_losing_orders',
                                        test_business_features.BusinessFeatureTests)


if __name__ == '__main__':
    unittest.main()
