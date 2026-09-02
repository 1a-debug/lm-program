from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from config.config import Config
from main import CLI


class CLIDemoCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_demo_reset_restores_bug_without_changing_tests(self) -> None:
        with TemporaryDirectory() as temp_dir:
            cwd = Path(temp_dir)
            source = cwd / "calculator.py"
            tests = cwd / "test_calculator.py"
            source.write_text("already fixed", encoding="utf-8")
            original_tests = "def test_divide_by_zero():\n    pass\n"
            tests.write_text(original_tests, encoding="utf-8")
            cli = CLI(Config(cwd=cwd))

            should_continue = await cli._handle_command("/demo-reset")

            self.assertTrue(should_continue)
            self.assertIn("return a / b", source.read_text(encoding="utf-8"))
            self.assertNotIn("if b == 0", source.read_text(encoding="utf-8"))
            self.assertEqual(tests.read_text(encoding="utf-8"), original_tests)


if __name__ == "__main__":
    unittest.main()
