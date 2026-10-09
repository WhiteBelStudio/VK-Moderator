import runpy
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch


class MaintenanceScriptTests(unittest.TestCase):
    def _assert_help_works(self, module_name):
        output = StringIO()
        with patch.object(sys, "argv", [module_name, "--help"]):
            with redirect_stdout(output):
                with self.assertRaises(SystemExit) as raised:
                    runpy.run_module(module_name, run_name="__main__")

        self.assertEqual(raised.exception.code, 0)
        self.assertIn("usage:", output.getvalue().lower())

    def test_backup_cli_help(self):
        self._assert_help_works("scripts.backup_database")

    def test_restore_cli_help(self):
        self._assert_help_works("scripts.restore_database")


if __name__ == "__main__":
    unittest.main()
