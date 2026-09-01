from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from context.project import build_project_context, inspect_symbol


class ProjectContextTests(unittest.TestCase):
    def test_context_identifies_python_readme_and_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("# Demo\nA FastAPI service.", encoding="utf-8")
            (root / "pyproject.toml").write_text('[project]\ndependencies = ["fastapi"]', encoding="utf-8")

            context = build_project_context(root)

            self.assertIn("Python", context)
            self.assertIn("FastAPI", context)
            self.assertIn("README.md excerpt", context)

    def test_inspection_reports_definition_and_call_site(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "service.py").write_text("def save_item():\n    pass\n", encoding="utf-8")
            (root / "app.py").write_text("from service import save_item\nsave_item()\n", encoding="utf-8")

            result = inspect_symbol(root, "save_item")

            self.assertIn("Definitions:", result)
            self.assertIn("service.py:1", result)
            self.assertIn("app.py:2", result)
