import runpy
import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch


class MainEntrypointTests(unittest.TestCase):
    def test_running_main_py_starts_bot_and_preserves_compatibility_imports(self):
        start_module = ModuleType("start")
        start_module.main = Mock()

        main_path = Path(__file__).resolve().parents[1] / "main.py"
        with patch.dict(sys.modules, {"start": start_module}):
            runpy.run_path(str(main_path), run_name="__main__")

        start_module.main.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
