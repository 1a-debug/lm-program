from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from tools.builtin.tasks import TaskStore


class TaskStoreTests(unittest.TestCase):
    def test_plan_can_be_paused_and_resumed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = TaskStore(Path(directory))
            task = store.create_plan("Refactor", "Move database code", ["Inspect", "Edit"], 2)

            self.assertEqual(task.status, "in_progress")
            self.assertEqual(task.attempts, 1)
            self.assertEqual(len(task.todos), 2)

            paused = store.pause_active_tasks("Interrupted by user")
            self.assertEqual([item.id for item in paused], [task.id])
            self.assertEqual(store.load(task.id).status, "paused")

            resumed = store.resume(task.id)
            self.assertEqual(resumed.status, "in_progress")
            self.assertEqual(resumed.attempts, 2)

    def test_failure_becomes_terminal_after_retry_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = TaskStore(Path(directory))
            task = store.create_plan("Refactor", "Move database code", ["Edit"], 1)

            self.assertEqual(store.fail(task.id, "first error").status, "paused")
            store.resume(task.id)
            failed = store.fail(task.id, "second error")

            self.assertEqual(failed.status, "failed")
            self.assertEqual(failed.last_error, "second error")


if __name__ == "__main__":
    unittest.main()
