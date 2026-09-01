from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


SOURCE_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".cs"}


@dataclass(frozen=True)
class VerificationCheck:
    name: str
    command: str


def is_source_file(path: str | None) -> bool:
    return bool(path and Path(path).suffix.lower() in SOURCE_EXTENSIONS)


def discover_verification_checks(cwd: Path) -> list[VerificationCheck]:
    """Choose only checks already declared by the repository."""
    checks: list[VerificationCheck] = []
    pyproject = cwd / "pyproject.toml"
    if pyproject.is_file():
        try:
            content = pyproject.read_text(encoding="utf-8").lower()
        except OSError:
            content = ""
        if "ruff" in content:
            checks.extend(
                [
                    VerificationCheck("format check", "uv run ruff format --check ."),
                    VerificationCheck("lint", "uv run ruff check ."),
                ]
            )
        if "mypy" in content:
            checks.append(VerificationCheck("type check", "uv run mypy ."))
        if (cwd / "tests").is_dir():
            checks.append(
                VerificationCheck("unit tests", "uv run python -m unittest discover -s tests")
            )

    package_json = cwd / "package.json"
    if package_json.is_file():
        try:
            scripts = json.loads(package_json.read_text(encoding="utf-8")).get("scripts", {})
        except (OSError, json.JSONDecodeError):
            scripts = {}
        for script, label in (("format:check", "format check"), ("lint", "lint"), ("typecheck", "type check"), ("test", "unit tests"), ("build", "build")):
            if script in scripts:
                checks.append(VerificationCheck(label, f"npm run {script}"))

    return checks
