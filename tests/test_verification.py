from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from context.verification import discover_verification_checks, is_source_file


class VerificationTests(unittest.TestCase):
    def test_python_checks_require_declared_tools(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pyproject.toml").write_text('[project]\ndependencies = ["ruff", "mypy"]', encoding="utf-8")
            (root / "tests").mkdir()

            commands = [check.command for check in discover_verification_checks(root)]

            self.assertIn("uv run ruff format --check .", commands)
            self.assertIn("uv run ruff check .", commands)
            self.assertIn("uv run mypy .", commands)
            self.assertIn("uv run python -m unittest discover -s tests", commands)

    def test_node_scripts_are_used_when_declared(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "package.json").write_text('{"scripts": {"lint": "eslint .", "test": "vitest"}}', encoding="utf-8")

            commands = [check.command for check in discover_verification_checks(root)]

            self.assertEqual(commands, ["npm run lint", "npm run test"])

    def test_source_file_detection(self) -> None:
        self.assertTrue(is_source_file("src/app.py"))
        self.assertFalse(is_source_file("README.md"))
