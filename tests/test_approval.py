from __future__ import annotations

from pathlib import Path
import unittest

from config.config import ApprovalPolicy
from safety.approval import ApprovalContext, ApprovalDecision, ApprovalManager


class ApprovalManagerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.cwd = Path("C:/workspace")
        self.manager = ApprovalManager(ApprovalPolicy.ON_REQUEST, self.cwd)

    async def test_network_access_requires_confirmation(self) -> None:
        decision = await self.manager.check_approval(
            ApprovalContext("web_fetch", {}, True, [])
        )
        self.assertEqual(decision, ApprovalDecision.NEEDS_CONFIRMATION)

    async def test_test_command_is_approved(self) -> None:
        decision = await self.manager.check_approval(
            ApprovalContext("shell", {}, True, [], command="python -m unittest")
        )
        self.assertEqual(decision, ApprovalDecision.APPROVED)

    async def test_uv_test_command_is_approved(self) -> None:
        decision = await self.manager.check_approval(
            ApprovalContext("shell", {}, True, [], command="uv run python -m unittest")
        )
        self.assertEqual(decision, ApprovalDecision.APPROVED)

    async def test_git_commit_requires_confirmation(self) -> None:
        decision = await self.manager.check_approval(
            ApprovalContext("shell", {}, True, [], command="git commit -m test")
        )
        self.assertEqual(decision, ApprovalDecision.NEEDS_CONFIRMATION)

    async def test_config_overwrite_requires_confirmation(self) -> None:
        decision = await self.manager.check_approval(
            ApprovalContext("write_file", {}, True, [self.cwd / "config.toml"])
        )
        self.assertEqual(decision, ApprovalDecision.NEEDS_CONFIRMATION)

    def test_missing_confirmation_callback_rejects_operation(self) -> None:
        from tools.base import ToolConfirmation

        self.assertFalse(
            self.manager.request_confirmation(
                ToolConfirmation("shell", {}, "Execute: git commit -m test")
            )
        )


if __name__ == "__main__":
    unittest.main()
