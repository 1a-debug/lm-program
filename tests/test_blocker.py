import unittest

from context.blocker import BlockerGate
from tools.base import ToolResult


class BlockerGateTests(unittest.TestCase):
    def test_preflight_blocks_explicitly_missing_external_prerequisites(self) -> None:
        gate = BlockerGate()

        reason = gate.start_task(
            "Replace this with a live private SDK call. The SDK, endpoint "
            "documentation, and production credentials are not present."
        )

        self.assertTrue(gate.blocked)
        self.assertIn("SDK or dependency", reason)
        self.assertIn("credentials", reason)
        self.assertIn("API documentation", reason)

    def test_preflight_does_not_block_normal_bug_fix(self) -> None:
        gate = BlockerGate()

        reason = gate.start_task("Run the tests and fix the divide function.")

        self.assertIsNone(reason)
        self.assertFalse(gate.blocked)

    def test_preflight_recognizes_chinese_missing_prerequisites(self) -> None:
        gate = BlockerGate()

        reason = gate.start_task(
            "请接入私有SDK进行线上验证，但SDK、接口文档和生产凭据都不存在。"
        )

        self.assertTrue(gate.blocked)
        self.assertIn("credentials", reason)

    def test_semantically_equivalent_package_checks_share_attempt_budget(self) -> None:
        gate = BlockerGate(repeat_limit=2)
        gate.start_task("Check whether the integration can run")

        first = gate.observe(
            "shell",
            {"command": "python -c \"import acme_private_sdk\""},
            ToolResult.error_result("No module named acme_private_sdk", exit_code=1),
        )
        second = gate.observe(
            "shell",
            {"command": "pip show acme_private_sdk"},
            ToolResult.error_result("Package not found", exit_code=1),
        )

        self.assertIsNone(first)
        self.assertIsNotNone(second)
        self.assertTrue(gate.blocked)
        self.assertIn("check-package:acme_private_sdk", second)

    def test_repeated_shell_syntax_failures_activate_gate(self) -> None:
        gate = BlockerGate(syntax_failure_limit=2)
        gate.start_task("Inspect the environment")

        gate.observe(
            "shell",
            {"command": "if ($env:KEY) { echo yes }"},
            ToolResult.error_result("{ was unexpected at this time.", exit_code=1),
        )
        reason = gate.observe(
            "shell",
            {"command": "python -c bad"},
            ToolResult.error_result("SyntaxError: unterminated string literal", exit_code=1),
        )

        self.assertTrue(gate.blocked)
        self.assertIn("Shell syntax failed 2 times", reason)

    def test_notice_is_emitted_once_and_subsequent_tools_are_blocked(self) -> None:
        gate = BlockerGate()
        gate.start_task(
            "Use a live private API, but its SDK and credentials are missing."
        )

        first_notice = gate.consume_notice()
        second_notice = gate.consume_notice()
        blocked = gate.before_tool("shell")

        self.assertIn("BLOCKER GATE ACTIVATED", first_notice)
        self.assertIsNone(second_notice)
        self.assertFalse(blocked.success)
        self.assertTrue(blocked.metadata["blocker_gate"])


if __name__ == "__main__":
    unittest.main()
