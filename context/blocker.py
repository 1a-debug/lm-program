from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import re
from typing import Any

from tools.base import ToolResult


ABSENCE_TERMS = (
    r"(?:not\s+(?:present|available|installed|provided)|missing|unavailable|absent|"
    r"不存在|缺少|没有|未提供|不可用)"
)


@dataclass
class BlockerState:
    blocked: bool = False
    reason: str | None = None
    facts: list[str] = field(default_factory=list)
    semantic_attempts: Counter[str] = field(default_factory=Counter)
    failed_attempts: Counter[str] = field(default_factory=Counter)
    shell_syntax_failures: int = 0


class BlockerGate:
    """Stop tool use when required external inputs are demonstrably unavailable."""

    def __init__(self, repeat_limit: int = 2, syntax_failure_limit: int = 2) -> None:
        self.repeat_limit = repeat_limit
        self.syntax_failure_limit = syntax_failure_limit
        self.state = BlockerState()
        self._notice_emitted = False

    @property
    def blocked(self) -> bool:
        return self.state.blocked

    @property
    def reason(self) -> str | None:
        return self.state.reason

    def start_task(self, task: str) -> str | None:
        self.state = BlockerState()
        self._notice_emitted = False
        facts = self._declared_missing_prerequisites(task)
        requires_external = bool(
            re.search(
                r"(?:\b(?:live|production|private|external)\b|线上|生产|私有|外部|真实)",
                task,
                re.IGNORECASE,
            )
        )
        if requires_external and len(facts) >= 2:
            self._block(
                "Required external prerequisites are explicitly unavailable: "
                + ", ".join(facts),
                facts,
            )
        return self.state.reason

    def _declared_missing_prerequisites(self, task: str) -> list[str]:
        categories = {
            "SDK or dependency": r"(?:sdk|package|dependency|library|软件包|依赖|库)",
            "credentials": r"(?:credentials?|api[_ -]?key|token|password|凭据|密钥|令牌)",
            "API documentation": r"(?:documentation|docs?|api\s+contract|endpoint|文档|接口说明)",
        }
        facts: list[str] = []
        for label, subject in categories.items():
            subject_then_absent = rf"{subject}.{{0,140}}{ABSENCE_TERMS}"
            absent_then_subject = rf"{ABSENCE_TERMS}.{{0,80}}{subject}"
            if re.search(subject_then_absent, task, re.IGNORECASE | re.DOTALL) or re.search(
                absent_then_subject, task, re.IGNORECASE | re.DOTALL
            ):
                facts.append(label)
        return facts

    def before_tool(self, name: str) -> ToolResult | None:
        if not self.blocked:
            return None
        return ToolResult.error_result(
            "Blocker Gate stopped further tool use: " + (self.reason or "task blocked"),
            metadata={"blocker_gate": True, "tool_name": name},
        )

    def observe(self, name: str, params: dict[str, Any], result: ToolResult) -> str | None:
        if self.blocked or name != "shell":
            return None
        command = str(params.get("command", ""))
        objective = self._semantic_objective(command)
        self.state.semantic_attempts[objective] += 1
        combined = f"{result.error or ''}\n{result.output or ''}"
        effective_failure = not result.success or self._is_negative_evidence(combined)

        if self._is_shell_syntax_failure(combined):
            self.state.shell_syntax_failures += 1
        if effective_failure:
            self.state.failed_attempts[objective] += 1

        if self.state.shell_syntax_failures >= self.syntax_failure_limit:
            self._block(
                f"Shell syntax failed {self.state.shell_syntax_failures} times; "
                "the agent is not adapting to the active shell.",
                ["repeated shell syntax incompatibility"],
            )
        elif self.state.failed_attempts[objective] >= self.repeat_limit:
            self._block(
                f"The same semantic objective failed {self.state.failed_attempts[objective]} "
                f"times: {objective}.",
                [f"repeated failed objective: {objective}"],
            )
        return self.state.reason if self.blocked else None

    def consume_notice(self) -> str | None:
        if not self.blocked or self._notice_emitted:
            return None
        self._notice_emitted = True
        facts = "\n".join(f"- {fact}" for fact in self.state.facts)
        return f"""
[SYSTEM NOTICE: BLOCKER GATE ACTIVATED]

Further tool use has been disabled for this task.

Reason: {self.reason}

Verified or user-declared blocking facts:
{facts or '- An unrecoverable blocker was detected.'}

Stop exploring. Do not create diagnostic files, enumerate unrelated environment
details, invent missing APIs, or claim successful verification. Briefly explain
what is blocked, preserve the current project state, and state the minimum
specific information or access the user must provide to continue.
""".strip()

    def stats(self) -> dict[str, Any]:
        return {
            "blocked": self.blocked,
            "reason": self.reason,
            "facts": list(self.state.facts),
            "semantic_attempts": dict(self.state.semantic_attempts),
            "failed_attempts": dict(self.state.failed_attempts),
            "shell_syntax_failures": self.state.shell_syntax_failures,
        }

    def _block(self, reason: str, facts: list[str]) -> None:
        self.state.blocked = True
        self.state.reason = reason
        self.state.facts.extend(fact for fact in facts if fact not in self.state.facts)

    @staticmethod
    def _semantic_objective(command: str) -> str:
        lowered = command.lower()
        package_match = re.search(
            r"(?:\bimport\s+|pip\s+show\s+|find_spec\(\s*['\"])([a-z_][\w.-]*)",
            lowered,
        )
        if package_match:
            return f"check-package:{package_match.group(1)}"
        if re.search(r"api[_ -]?key|token|credential|os\.environ|\benv:|\bset\b", lowered):
            return "check-credentials"
        if re.search(r"python\s+--version|where\s+python|py\s+-0|sys\.version", lowered):
            return "inspect-python-environment"
        normalized = re.sub(r"\s+", " ", lowered).strip()
        return "shell:" + normalized[:120]

    @staticmethod
    def _is_shell_syntax_failure(output: str) -> bool:
        return bool(
            re.search(
                r"syntaxerror|unterminated|string literal|eol while scanning|"
                r"unexpected at this time|was unexpected|cannot open .*['\"]",
                output,
                re.IGNORECASE,
            )
        )

    @staticmethod
    def _is_negative_evidence(output: str) -> bool:
        return bool(
            re.search(
                r"no module named|not installed|installed:\s*false|not set|"
                r"matching env vars:\s*(?:none|\[\])|package not found",
                output,
                re.IGNORECASE,
            )
        )
