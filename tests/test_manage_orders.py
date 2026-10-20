import contextlib
import csv
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from storage import SQLiteOrderStore

HAS_CLI = importlib.util.find_spec('manage_orders') is not None
if HAS_CLI:
    from manage_orders import run


class OperatorAvailabilityTests(unittest.TestCase):
    def test_operator_tool_exists(self):
        self.assertTrue(HAS_CLI, 'Local order retrieval and backup tools are missing')


@unittest.skipUnless(HAS_CLI, 'Operator tool not present')
class OperatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = SQLiteOrderStore(self.root / 'orders.sqlite3')
        self.store.save((('Cafe Latte',2,158),), 158, request_id='a')
        self.store.save((('Matcha Latte',1,109),), 109, request_id='b')

    def call(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = run(['--data-dir', str(self.root), *map(str,args)])
        return code, out.getvalue(), err.getvalue()

    def test_list_orders(self):
        code, out, _ = self.call('list')
        self.assertEqual(code, 0)
        self.assertIn('#001', out)
        self.assertIn('#002', out)
        self.assertIn('PAYMENT PENDING', out)

    def test_ticket_to_stdout(self):
        code, out, _ = self.call('ticket', '1')
        self.assertEqual(code, 0)
        self.assertIn('2 x Cafe Latte', out)
        self.assertIn('not proof of payment', out.lower())

    def test_ticket_to_file(self):
        output = self.root / 'ticket.txt'
        code, _, _ = self.call('ticket', 1, '--output', output)
        self.assertEqual(code, 0)
        self.assertIn('Cafe Latte', output.read_text(encoding='utf-8'))

    def test_missing_ticket_returns_error(self):
        code, _, err = self.call('ticket', '999')
        self.assertEqual(code, 1)
        self.assertIn('not found', err.lower())

    def test_export_one_row_per_order(self):
        output = self.root / 'orders.csv'
        code, _, _ = self.call('export', '--output', output)
        self.assertEqual(code, 0)
        with output.open(encoding='utf-8-sig', newline='') as file:
            rows = list(csv.DictReader(file))
        self.assertEqual(len(rows), 2)
        self.assertEqual(sum(int(row['total_php']) for row in rows), 267)
        self.assertEqual(rows[0]['payment_status'], 'PAYMENT PENDING')

    def test_export_does_not_overwrite(self):
        output = self.root / 'keep.csv'
        output.write_text('original')
        code, _, _ = self.call('export', '--output', output)
        self.assertEqual(code, 1)
        self.assertEqual(output.read_text(), 'original')

    def test_backup_is_readable(self):
        output = self.root / 'backup.sqlite3'
        code, _, _ = self.call('backup', '--output', output)
        self.assertEqual(code, 0)
        self.assertEqual(len(SQLiteOrderStore(output).all()), 2)

    def test_wrong_data_directory_is_not_silently_created(self):
        output = io.StringIO()
        missing = self.root / 'missing'
        with contextlib.redirect_stderr(output):
            code = run(['--data-dir', str(missing), 'list'])
        self.assertEqual(code, 1)
        self.assertFalse(missing.exists())

    def test_csv_formula_like_names_are_text(self):
        self.store.save((('=DANGEROUS()',1,1),),1, request_id='c')
        output = self.root / 'safe.csv'
        self.call('export', '--output', output)
        with output.open(encoding='utf-8-sig', newline='') as file:
            rows = list(csv.DictReader(file))
        self.assertFalse(rows[-1]['items'].startswith(('=', '+', '-', '@')))


if __name__ == '__main__':
    unittest.main()
