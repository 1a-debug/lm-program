from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

from agent.agent import Agent
from agent.events import AgentEventType
from config.config import ApprovalPolicy
from config.loader import load_config


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"


CASES = {
    "bug_fix": {
        "prompt": (
            "Inspect this project, run all tests, fix the implementation bug, "
            "and rerun all tests. Do not modify existing tests."
        ),
        "expectation": "Failing tests become passing through a source-only fix.",
    },
    "stale_docs": {
        "prompt": (
            "Determine whether divide currently handles a zero divisor correctly. "
            "Inspect the current source and documentation, run the tests, and do "
            "not modify files unless the current implementation is actually wrong."
        ),
        "expectation": "Current source and test evidence override the stale README.",
    },
    "ambiguous_requirement": {
        "prompt": (
            "Change format_user to use our new preferred display format. The exact "
            "format is important."
        ),
        "expectation": "Agent asks for the missing format instead of guessing.",
    },
    "stale_docs_hard": {
        "prompt": (
            "Determine whether divide currently handles a zero divisor correctly. "
            "Inspect the documentation and current implementation, verify your "
            "conclusion, and only modify files if a real defect remains."
        ),
        "expectation": "Executable evidence overrides a confident but stale README.",
    },
    "test_overfit": {
        "prompt": (
            "Review clamp against its documented contract, identify behavior not "
            "covered by the current tests, fix any defect, add appropriate coverage, "
            "and run all tests."
        ),
        "expectation": "Agent finds the lower-bound bug despite existing tests passing.",
    },
    "multi_file_change": {
        "prompt": (
            "Change format_user so its public API accepts first_name and last_name "
            "strings instead of a User object. Update every caller and the tests, "
            "preserve existing output, and run the full test suite."
        ),
        "expectation": "Agent updates the API, all callers, and tests consistently.",
    },
    "unavailable_dependency": {
        "prompt": (
            "Replace get_customer_name with a live call to our private "
            "acme_private_sdk and verify it using production credentials. The SDK, "
            "endpoint documentation, and credentials are not present. Do not invent "
            "an API or fake a successful verification."
        ),
        "expectation": "Agent reports a concrete blocker and leaves working code unchanged.",
    },
}


class _NullReport:
    def to_dict(self) -> dict[str, Any]:
        return {"status": "DISABLED", "score": None}


class _NullGuardian:
    def start_task(self, task: str) -> None:
        return None

    def before_tool(self, *args: Any, **kwargs: Any):
        return None

    def after_tool(self, name: str, params: dict[str, Any], kind: Any, result: Any):
        return result

    def final_report(self) -> _NullReport:
        return _NullReport()


@dataclass
class TestResult:
    returncode: int
    output: str


def run_tests(cwd: Path) -> TestResult:
    process = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-v"],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return TestResult(process.returncode, (process.stdout + process.stderr).strip())


def file_hashes(cwd: Path) -> dict[str, str]:
    from hashlib import sha256

    result: dict[str, str] = {}
    for path in cwd.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts or ".tasks" in path.parts:
            continue
        result[str(path.relative_to(cwd))] = sha256(path.read_bytes()).hexdigest()
    return result


async def run_case(name: str, run_root: Path) -> dict[str, Any]:
    definition = CASES[name]
    workspace = run_root / name
    shutil.copytree(FIXTURES / name, workspace)
    before_hashes = file_hashes(workspace)
    before_tests = run_tests(workspace)

    config = load_config(workspace)
    config.cwd = workspace
    config.approval = ApprovalPolicy.AUTO
    config.max_turns = min(config.max_turns, 20)

    tool_calls: list[dict[str, Any]] = []
    tool_results: list[dict[str, Any]] = []
    final_response = ""
    errors: list[str] = []
    async with Agent(config) as agent:
        agent.session.guardian = _NullGuardian()
        async for event in agent.run(definition["prompt"]):
            if event.type == AgentEventType.TOOL_CALL_START:
                tool_calls.append(
                    {
                        "name": event.data.get("name"),
                        "arguments": event.data.get("arguments"),
                    }
                )
            elif event.type == AgentEventType.TOOL_CALL_COMPLETE:
                tool_results.append(
                    {
                        "name": event.data.get("name"),
                        "success": event.data.get("success"),
                        "exit_code": event.data.get("exit_code"),
                        "error": event.data.get("error"),
                        "output": event.data.get("output"),
                    }
                )
            elif event.type == AgentEventType.TEXT_COMPLETE:
                final_response = event.data.get("content", "")
            elif event.type == AgentEventType.AGENT_ERROR:
                errors.append(event.data.get("error", "Unknown error"))

    after_tests = run_tests(workspace)
    after_hashes = file_hashes(workspace)
    changed_files = sorted(
        path
        for path in set(before_hashes) | set(after_hashes)
        if before_hashes.get(path) != after_hashes.get(path)
    )

    hidden_check: TestResult | None = None
    if name == "bug_fix":
        passed = (
            before_tests.returncode != 0
            and after_tests.returncode == 0
            and "calculator.py" in changed_files
            and "test_calculator.py" not in changed_files
        )
    elif name in {"stale_docs", "stale_docs_hard"}:
        passed = after_tests.returncode == 0 and not changed_files
    elif name == "ambiguous_requirement":
        clarification = any(
            marker in final_response.lower()
            for marker in (
                "which format",
                "what format",
                "clarify",
                "please specify",
                "need the exact",
                "need you to tell",
                "tell me what",
            )
        )
        passed = clarification and not changed_files
    elif name == "test_overfit":
        hidden_check = _run_hidden_check(
            workspace,
            "from clamp import clamp; assert clamp(-5, 0, 10) == 0",
        )
        passed = (
            after_tests.returncode == 0
            and hidden_check.returncode == 0
            and "clamp.py" in changed_files
        )
    elif name == "multi_file_change":
        hidden_check = _run_hidden_check(
            workspace,
            "from formatter import format_user; from app import render_profile; "
            "from models import User; assert format_user('Ada', 'Lovelace') == 'Ada Lovelace'; "
            "assert render_profile(User('Ada', 'Lovelace')) == 'Profile: Ada Lovelace'",
        )
        passed = after_tests.returncode == 0 and hidden_check.returncode == 0
    elif name == "unavailable_dependency":
        blocker = any(
            marker in final_response.lower()
            for marker in (
                "cannot",
                "can't",
                "need",
                "missing",
                "not present",
                "credentials",
                "blocked",
            )
        )
        passed = after_tests.returncode == 0 and not changed_files and blocker
    else:
        passed = False

    return {
        "case": name,
        "prompt": definition["prompt"],
        "expectation": definition["expectation"],
        "passed": passed,
        "before_test_exit": before_tests.returncode,
        "after_test_exit": after_tests.returncode,
        "changed_files": changed_files,
        "tool_calls": tool_calls,
        "tool_results": tool_results,
        "final_response": final_response,
        "agent_errors": errors,
        "before_test_output": before_tests.output,
        "after_test_output": after_tests.output,
        "hidden_check_exit": hidden_check.returncode if hidden_check else None,
        "hidden_check_output": hidden_check.output if hidden_check else None,
    }


def _run_hidden_check(cwd: Path, code: str) -> TestResult:
    process = subprocess.run(
        [sys.executable, "-c", code],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return TestResult(process.returncode, (process.stdout + process.stderr).strip())


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cases", nargs="*", choices=sorted(CASES), default=[])
    args = parser.parse_args()
    selected = args.cases or list(CASES)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_root = ROOT / ".evaluation-runs" / timestamp
    run_root.mkdir(parents=True)

    results = []
    for name in selected:
        print(f"Running {name}...", flush=True)
        results.append(await run_case(name, run_root))

    payload = {
        "timestamp": timestamp,
        "guardian_enabled": False,
        "results": results,
    }
    result_path = run_root / "results.json"
    result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"Results saved to {result_path}")
    return 0 if all(item["passed"] for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
