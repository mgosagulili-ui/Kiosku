from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LaunchTests(unittest.TestCase):
    def call(self, *args, cwd=None):
        return subprocess.run([sys.executable, str(ROOT / 'main.py'), *args],
                              cwd=cwd, capture_output=True, text=True, timeout=10)

    def test_help_does_not_require_flet(self):
        result = self.call('--help')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--data-dir', result.stdout)
        self.assertIn('--kiosk', result.stdout)

    def test_invalid_port_rejected(self):
        for port in ('0', '-1', '65536', 'abc'):
            with self.subTest(port=port):
                result = self.call('--port', port)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertNotIn('Traceback', result.stderr)

    def test_conflicting_mode_rejected(self):
        result = self.call('--kiosk', '--no-browser')
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('--no-browser', result.stderr)

    def test_help_from_another_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            result = self.call('--help', cwd=temp)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_environment_check_is_actionable(self):
        result = self.call('--check')
        self.assertIn(result.returncode, (0,1))
        self.assertIn('Python', result.stdout)
        self.assertIn('Flet', result.stdout)
        self.assertNotIn('Traceback', result.stderr)

    def test_kiosk_implies_desktop_in_settings(self):
        try:
            from main import parse_args, launch_settings
        except (ImportError, AttributeError):
            self.fail('Testable launch settings are missing')
        options = launch_settings(parse_args(['--kiosk']))
        self.assertTrue(options['desktop'])
        self.assertTrue(options['kiosk'])
        self.assertEqual(options['host'], '127.0.0.1')

    def test_default_is_local_browser(self):
        try:
            from main import parse_args, launch_settings
        except (ImportError, AttributeError):
            self.fail('Testable launch settings are missing')
        options = launch_settings(parse_args([]))
        self.assertFalse(options['desktop'])
        self.assertTrue(options['open_browser'])
        self.assertEqual(options['port'], 8550)


if __name__ == '__main__':
    unittest.main()
