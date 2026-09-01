from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import re
from typing import Any, Awaitable, Callable
from config.config import ApprovalPolicy
from tools.base import ToolConfirmation


class ApprovalDecision(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_CONFIRMATION = "needs_confirmation"


@dataclass
class ApprovalContext:

    tool_name: str
    params: dict[str, Any]
    is_mutating: bool
    affected_paths: list[Path]
    command: str | None = None
    is_dangerous: bool = False


DANGEROUS_PATTERNS = [
    # File system destruction
    r"rm\s+(-rf?|--recursive)\s+[/~]",
    r"rm\s+-rf?\s+\*",
    r"rmdir\s+[/~]",
    # Disk operations
    r"dd\s+if=",
    r"mkfs",
    r"fdisk",
    r"parted",
    # System control
    r"shutdown",
    r"reboot",
    r"halt",
    r"poweroff",
    r"init\s+[06]",
    # Permission changes on root
    r"chmod\s+(-R\s+)?777\s+[/~]",
    r"chown\s+-R\s+.*\s+[/~]",
    # Network exposure
    r"nc\s+-l",
    r"netcat\s+-l",
    # Code execution from network
    r"curl\s+.*\|\s*(bash|sh)",
    r"wget\s+.*\|\s*(bash|sh)",
    # Fork bomb
    r":\(\)\s*\{\s*:\|:&\s*\}\s*;",
]

# Patterns for safe commands (can be auto-approved)
SAFE_PATTERNS = [
    # Information commands
    r"^(ls|dir|pwd|cd|echo|cat|head|tail|less|more|wc)(\s|$)",
    r"^(find|locate|which|whereis|file|stat)(\s|$)",
    # Development tools (read-only)
    r"^git\s+(status|log|diff|show|branch|remote|tag)(\s|$)",
    r"^(npm|yarn|pnpm)\s+(list|ls|outdated)(\s|$)",
    r"^pip\s+(list|show|freeze)(\s|$)",
    r"^cargo\s+(tree|search)(\s|$)",
    # Text processing (usually safe)
    r"^(grep|awk|sed|cut|sort|uniq|tr|diff|comm)(\s|$)",
    # System info
    r"^(date|cal|uptime|whoami|id|groups|hostname|uname)(\s|$)",
    r"^(env|printenv|set)$",
    # Process info
    r"^(ps|top|htop|pgrep)(\s|$)",
    # Test and static-analysis commands. These are allowed to create their
    # normal local caches, but do not change source files or remote state.
    r"^(python(?:\d+(?:\.\d+)?)?|py)\s+-m\s+(unittest|pytest)(\s|$)",
    r"^uv\s+run\s+(python(?:\d+(?:\.\d+)?)?\s+-m\s+(unittest|pytest)|pytest|ruff|mypy|pyright)(\s|$)",
    r"^pytest(\s|$)",
    r"^(npm|yarn|pnpm)\s+(test|run\s+(test|lint|typecheck))(\s|$)",
    r"^(cargo|go|dotnet)\s+test(\s|$)",
    r"^(ruff|mypy|pyright)\s+(check|\.)(\s|$)",
]

HIGH_RISK_COMMAND_PATTERNS = [
    # Deleting files or directories (POSIX, cmd.exe, and PowerShell)
    r"\b(rm|rmdir|del|erase|remove-item|unlink)\b",
    # Remote state changes and repository configuration
    r"\bgit\s+(commit|push|config)\b",
    # Explicit network access and dependency downloads
    r"\b(curl|wget|invoke-webrequest|invoke-restmethod)\b",
    r"\b(pip|npm|yarn|pnpm)\s+(install|add|publish)\b",
]

CONFIG_FILENAMES = {
    ".env",
    ".env.local",
    ".env.production",
    "config.toml",
    "config.json",
    "settings.json",
}


def is_dangerous_command(command: str) -> bool:
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return True

    return False


def is_safe_command(command: str) -> bool:
    for pattern in SAFE_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return True

    return False


def is_high_risk_command(command: str) -> bool:
    return any(
        re.search(pattern, command, re.IGNORECASE)
        for pattern in HIGH_RISK_COMMAND_PATTERNS
    )


def is_configuration_path(path: Path) -> bool:
    return path.name.lower() in CONFIG_FILENAMES


class ApprovalManager:
    def __init__(
        self,
        approval_policy: ApprovalPolicy,
        cwd: Path,
        confirmation_callback: Callable[[ToolConfirmation], bool] | None = None,
    ) -> None:
        self.approval_policy = approval_policy
        self.cwd = cwd
        self.confirmation_callback = confirmation_callback

    def _assess_command_safety(self, command: str) -> ApprovalDecision:
        if self.approval_policy == ApprovalPolicy.YOLO:
            return ApprovalDecision.APPROVED

        if is_dangerous_command(command):
            return ApprovalDecision.REJECTED

        if self.approval_policy == ApprovalPolicy.NEVER:
            if is_safe_command(command):
                return ApprovalDecision.APPROVED
            return ApprovalDecision.REJECTED

        if self.approval_policy in {ApprovalPolicy.AUTO, ApprovalPolicy.ON_FAILURE}:
            return ApprovalDecision.APPROVED

        if self.approval_policy == ApprovalPolicy.AUTO_EDIT:
            if is_safe_command(command):
                return ApprovalDecision.APPROVED

            return ApprovalDecision.NEEDS_CONFIRMATION

        if is_safe_command(command):
            return ApprovalDecision.APPROVED

        return ApprovalDecision.NEEDS_CONFIRMATION

    async def check_approval(self, context: ApprovalContext) -> ApprovalDecision:
        if not context.is_mutating:
            return ApprovalDecision.APPROVED

        # These operations always need an explicit decision unless the user
        # selected YOLO. They can delete data, overwrite credentials/config,
        # contact external systems, or change a remote Git repository.
        requires_confirmation = (
            context.tool_name in {"web_fetch", "web_search"}
            or bool(context.command and is_high_risk_command(context.command))
            or any(is_configuration_path(path) for path in context.affected_paths)
            or context.is_dangerous
        )
        if requires_confirmation:
            if self.approval_policy == ApprovalPolicy.YOLO:
                return ApprovalDecision.APPROVED
            if self.approval_policy == ApprovalPolicy.NEVER:
                return ApprovalDecision.REJECTED
            return ApprovalDecision.NEEDS_CONFIRMATION

        if context.command:
            decision = self._assess_command_safety(context.command)
            if decision != ApprovalDecision.NEEDS_CONFIRMATION:
                return decision

        for path in context.affected_paths:
            path_decision = ApprovalDecision.NEEDS_CONFIRMATION
            if path.is_relative_to(self.cwd):
                path_decision = ApprovalDecision.APPROVED
            else:
                return path_decision

        if context.is_dangerous:
            if self.approval_policy == ApprovalPolicy.YOLO:
                return ApprovalDecision.APPROVED
            return ApprovalDecision.NEEDS_CONFIRMATION

        return ApprovalDecision.APPROVED

    def request_confirmation(self, confirmation: ToolConfirmation) -> bool:
        if self.confirmation_callback:
            result = self.confirmation_callback(confirmation)
            return result

        # A non-interactive invocation cannot obtain the user's explicit
        # approval, so a confirmation-required operation must not proceed.
        return False
