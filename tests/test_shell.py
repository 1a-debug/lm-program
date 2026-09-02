import unittest

from config.config import Config
from tools.base import ToolInvocation
from tools.builtin.shell import ShellTool


class ShellToolOutputTests(unittest.IsolatedAsyncioTestCase):
    async def test_failed_command_does_not_duplicate_stderr_in_error(self) -> None:
        tool = ShellTool(Config())
        result = await tool.execute(
            ToolInvocation(
                params={
                    "command": "python -c \"import sys; print('unique-error', file=sys.stderr); sys.exit(3)\""
                },
                cwd=Config().cwd,
            )
        )

        self.assertFalse(result.success)
        self.assertRegex(result.error or "", r"^Command exited with code \d+$")
        self.assertNotIn("unique-error", result.error or "")
        self.assertLessEqual(result.output.count("unique-error"), 1)


if __name__ == "__main__":
    unittest.main()
