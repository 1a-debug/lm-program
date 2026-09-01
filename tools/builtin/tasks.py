import json
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from config.config import Config
from tools.base import Tool, ToolInvocation, ToolKind, ToolResult


@dataclass
class Task:
    id: str
    subject: str
    description: str
    status: Literal["pending", "in_progress", "paused", "failed", "completed"]
    owner: str | None
    blockedBy: list[str]
    todos: list[dict]
    attempts: int = 0
    max_retries: int = 2
    last_error: str | None = None


class TaskStore:
    def __init__(self, cwd: Path):
        self.tasks_dir = cwd / ".tasks"
        self.tasks_dir.mkdir(exist_ok=True)

    def _get_path(self, task_id: str) -> Path:
        return self.tasks_dir / f"{task_id}.json"

    def save(self, task: Task) -> None:
        path = self._get_path(task.id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(task), f, indent=2)

    def load(self, task_id: str) -> Task:
        path = self._get_path(task_id)
        if not path.exists():
            raise FileNotFoundError(f"Task {task_id} not found")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "todos" not in data:
            data["todos"] = []
        data.setdefault("attempts", 0)
        data.setdefault("max_retries", 2)
        data.setdefault("last_error", None)
        return Task(**data)

    def create(
        self, subject: str, description: str = "", max_retries: int = 2
    ) -> Task:
        task_id = "task_" + str(uuid.uuid4().hex)[:8]
        task = Task(
            id=task_id,
            subject=subject,
            description=description,
            status="pending",
            owner=None,
            blockedBy=[],
            todos=[],
            max_retries=max_retries,
        )
        self.save(task)
        return task

    def create_plan(
        self,
        subject: str,
        description: str,
        steps: list[str],
        max_retries: int,
    ) -> Task:
        if not steps:
            raise ValueError("A plan must contain at least one step")
        task = self.create(subject, description, max_retries)
        task.status = "in_progress"
        task.owner = "agent"
        task.attempts = 1
        task.todos = [
            {"id": str(uuid.uuid4().hex)[:6], "content": step, "completed": False}
            for step in steps
        ]
        self.save(task)
        return task

    def pause_active_tasks(self, reason: str = "Interrupted by user") -> list[Task]:
        paused = []
        for task in self.list_all():
            if task.status == "in_progress":
                task.status = "paused"
                task.last_error = reason
                self.save(task)
                paused.append(task)
        return paused

    def resume(self, task_id: str, owner: str = "agent") -> Task:
        task = self.load(task_id)
        if task.status not in {"paused", "failed"}:
            raise ValueError(f"Task {task_id} is {task.status}, cannot resume")
        if task.status == "failed" and task.attempts > task.max_retries:
            raise ValueError(f"Task {task_id} exhausted its retry limit")
        if self.incomplete_dependencies(task):
            raise ValueError(f"Task {task_id} still has incomplete dependencies")
        task.status = "in_progress"
        task.owner = owner
        task.last_error = None
        task.attempts += 1
        self.save(task)
        return task

    def fail(self, task_id: str, error: str) -> Task:
        task = self.load(task_id)
        if task.status != "in_progress":
            raise ValueError(f"Task {task_id} is {task.status}, cannot fail")
        task.last_error = error
        if task.attempts <= task.max_retries:
            task.status = "paused"
        else:
            task.status = "failed"
        self.save(task)
        return task

    def list_all(self) -> list[Task]:
        tasks = []
        for file in self.tasks_dir.glob("*.json"):
            try:
                tasks.append(self.load(file.stem))
            except Exception:
                pass
        return tasks

    def update_dependencies(self, task_id: str, add_blocked_by: list[str]) -> Task:
        task = self.load(task_id)
        if task.status != "pending":
            raise ValueError(f"Task {task_id} is {task.status}, cannot update dependencies")
        if task.owner is not None:
            raise ValueError(f"Task {task_id} is already owned")
        
        for dep in add_blocked_by:
            if dep == task_id:
                raise ValueError(f"Task {task_id} cannot depend on itself")
            self.load(dep)
            if dep not in task.blockedBy:
                task.blockedBy.append(dep)
        self.save(task)
        return task

    def incomplete_dependencies(self, task: Task) -> list[str]:
        incomplete = []
        for dep_id in task.blockedBy:
            try:
                dep_task = self.load(dep_id)
                if dep_task.status != "completed":
                    incomplete.append(dep_id)
            except FileNotFoundError:
                incomplete.append(dep_id)
        return incomplete

    def can_start(self, task_id: str) -> bool:
        task = self.load(task_id)
        return len(self.incomplete_dependencies(task)) == 0


class CreateTaskParams(BaseModel):
    subject: str = Field(..., description="Short title for the task")
    description: str = Field("", description="Detailed description of the task")
    max_retries: int = Field(2, ge=0, le=10, description="Maximum retry attempts")

class CreateTaskTool(Tool):
    name = "create_task"
    description = "Create a new pending task. Returns the task ID."
    kind = ToolKind.MEMORY
    schema = CreateTaskParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        store = TaskStore(invocation.cwd)
        params = CreateTaskParams(**invocation.params)
        task = store.create(params.subject, params.description, params.max_retries)
        return ToolResult.success_result(f"Created task: {task.id}")


class CreatePlanParams(BaseModel):
    subject: str = Field(..., description="Short title for the overall task")
    description: str = Field("", description="Detailed task goal")
    steps: list[str] = Field(..., min_length=1, description="Ordered, concrete plan steps")
    max_retries: int = Field(2, ge=0, le=10, description="Maximum retry attempts")


class CreatePlanTool(Tool):
    name = "create_plan"
    description = "Create and start one task with an ordered todo plan. Use this first for multi-step coding work."
    kind = ToolKind.MEMORY
    schema = CreatePlanParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        store = TaskStore(invocation.cwd)
        params = CreatePlanParams(**invocation.params)
        try:
            task = store.create_plan(
                params.subject, params.description, params.steps, params.max_retries
            )
            return ToolResult.success_result(f"Created active plan: {task.id}")
        except Exception as error:
            return ToolResult.error_result(str(error))


class UpdateTaskParams(BaseModel):
    task_id: str = Field(..., description="ID of the task to update")
    addBlockedBy: list[str] = Field(..., description="List of task IDs that must be completed before this task can start")

class UpdateTaskTool(Tool):
    name = "update_task"
    description = "Add dependencies to a task. Use this to construct a task graph."
    kind = ToolKind.MEMORY
    schema = UpdateTaskParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        store = TaskStore(invocation.cwd)
        params = UpdateTaskParams(**invocation.params)
        try:
            task = store.update_dependencies(params.task_id, params.addBlockedBy)
            return ToolResult.success_result(f"Updated {task.id}, blockedBy: {task.blockedBy}")
        except Exception as e:
            return ToolResult.error_result(str(e))


class ClaimTaskParams(BaseModel):
    task_id: str = Field(..., description="ID of the task to claim")
    owner: str = Field("agent", description="The agent claiming the task")

class ClaimTaskTool(Tool):
    name = "claim_task"
    description = "Claim a pending, unblocked task and set its status to in_progress."
    kind = ToolKind.MEMORY
    schema = ClaimTaskParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        store = TaskStore(invocation.cwd)
        params = ClaimTaskParams(**invocation.params)
        try:
            task = store.load(params.task_id)
            if task.status != "pending":
                return ToolResult.error_result(f"Task {params.task_id} is {task.status}, cannot claim")
            
            incomplete = store.incomplete_dependencies(task)
            if incomplete:
                return ToolResult.error_result(f"Blocked by incomplete tasks: {incomplete}")

            task.owner = params.owner
            task.status = "in_progress"
            task.attempts += 1
            store.save(task)
            return ToolResult.success_result(f"Claimed {task.id} ({task.subject})")
        except Exception as e:
            return ToolResult.error_result(str(e))


class CompleteTaskParams(BaseModel):
    task_id: str = Field(..., description="ID of the task to complete")
    owner: str = Field("agent", description="The agent completing the task")

class CompleteTaskTool(Tool):
    name = "complete_task"
    description = "Mark an in_progress task as completed. Checks for any newly unblocked tasks."
    kind = ToolKind.MEMORY
    schema = CompleteTaskParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        store = TaskStore(invocation.cwd)
        params = CompleteTaskParams(**invocation.params)
        try:
            task = store.load(params.task_id)
            if task.status != "in_progress":
                return ToolResult.error_result(f"Task {params.task_id} is {task.status}, cannot complete")
            if task.owner != params.owner:
                return ToolResult.error_result(f"Task {params.task_id} is owned by {task.owner}, not {params.owner}")
            
            all_tasks = store.list_all()
            ready_before = {t.id for t in all_tasks if t.status == "pending" and t.blockedBy and store.can_start(t.id)}
            
            task.status = "completed"
            store.save(task)
            
            unblocked = [t.subject for t in store.list_all() if t.status == "pending" and t.blockedBy and t.id not in ready_before and store.can_start(t.id)]
            msg = f"Completed {task.id} ({task.subject})"
            if unblocked:
                msg += f"\nUnblocked: {', '.join(unblocked)}"
            return ToolResult.success_result(msg)
        except Exception as e:
            return ToolResult.error_result(str(e))


class ResumeTaskParams(BaseModel):
    task_id: str = Field(..., description="ID of a paused or retryable failed task")
    owner: str = Field("agent", description="The agent resuming the task")


class ResumeTaskTool(Tool):
    name = "resume_task"
    description = "Resume a paused task. Failed tasks can resume while they still have retries available."
    kind = ToolKind.MEMORY
    schema = ResumeTaskParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        store = TaskStore(invocation.cwd)
        params = ResumeTaskParams(**invocation.params)
        try:
            task = store.resume(params.task_id, params.owner)
            return ToolResult.success_result(
                f"Resumed {task.id}; attempt {task.attempts}/{task.max_retries + 1}"
            )
        except Exception as error:
            return ToolResult.error_result(str(error))


class FailTaskParams(BaseModel):
    task_id: str = Field(..., description="ID of the task that could not be completed")
    error: str = Field(..., description="Concise failure reason")


class FailTaskTool(Tool):
    name = "fail_task"
    description = "Record a task failure. It pauses for retry until its retry limit is exhausted."
    kind = ToolKind.MEMORY
    schema = FailTaskParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        store = TaskStore(invocation.cwd)
        params = FailTaskParams(**invocation.params)
        try:
            task = store.fail(params.task_id, params.error)
            if task.status == "paused":
                return ToolResult.success_result(
                    f"Task paused for retry ({task.attempts}/{task.max_retries + 1} attempts used)"
                )
            return ToolResult.success_result(f"Task failed after {task.attempts} attempts")
        except Exception as error:
            return ToolResult.error_result(str(error))


class ListTasksParams(BaseModel):
    pass

class ListTasksTool(Tool):
    name = "list_tasks"
    description = "List all tasks and their current statuses."
    kind = ToolKind.MEMORY
    schema = ListTasksParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        store = TaskStore(invocation.cwd)
        tasks = store.list_all()
        if not tasks:
            return ToolResult.success_result("No tasks found.")
        
        lines = ["Tasks:"]
        for t in tasks:
            blocked_info = f" (blocked by: {', '.join(t.blockedBy)})" if t.blockedBy else ""
            lines.append(f"  [{t.id}] {t.status.upper()} - {t.subject}{blocked_info}")
        return ToolResult.success_result("\n".join(lines))


class GetTaskParams(BaseModel):
    task_id: str = Field(..., description="ID of the task to view")

class GetTaskTool(Tool):
    name = "get_task"
    description = "View the full JSON details of a specific task."
    kind = ToolKind.MEMORY
    schema = GetTaskParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        store = TaskStore(invocation.cwd)
        params = GetTaskParams(**invocation.params)
        try:
            task = store.load(params.task_id)
            return ToolResult.success_result(json.dumps(asdict(task), indent=2))
        except Exception as e:
            return ToolResult.error_result(str(e))


class AddTodoParams(BaseModel):
    task_id: str = Field(..., description="ID of the in_progress task")
    content: str = Field(..., description="Description of the todo step")

class AddTodoTool(Tool):
    name = "add_todo"
    description = "Add a sub-step (todo) to an in_progress task's checklist."
    kind = ToolKind.MEMORY
    schema = AddTodoParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        store = TaskStore(invocation.cwd)
        params = AddTodoParams(**invocation.params)
        try:
            task = store.load(params.task_id)
            if task.status != "in_progress":
                return ToolResult.error_result(f"Task {params.task_id} is not in_progress")
            
            todo_id = str(uuid.uuid4().hex)[:6]
            task.todos.append({"id": todo_id, "content": params.content, "completed": False})
            store.save(task)
            return ToolResult.success_result(f"Added todo [{todo_id}]: {params.content}")
        except Exception as e:
            return ToolResult.error_result(str(e))


class CompleteTodoParams(BaseModel):
    task_id: str = Field(..., description="ID of the task")
    todo_id: str = Field(..., description="ID of the todo to mark as completed")

class CompleteTodoTool(Tool):
    name = "complete_todo"
    description = "Mark a sub-step (todo) as completed in the active task."
    kind = ToolKind.MEMORY
    schema = CompleteTodoParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        store = TaskStore(invocation.cwd)
        params = CompleteTodoParams(**invocation.params)
        try:
            task = store.load(params.task_id)
            for todo in task.todos:
                if todo["id"] == params.todo_id:
                    if todo["completed"]:
                        return ToolResult.success_result(f"Todo {params.todo_id} is already completed")
                    todo["completed"] = True
                    store.save(task)
                    return ToolResult.success_result(f"Completed todo [{params.todo_id}]: {todo['content']}")
            return ToolResult.error_result(f"Todo {params.todo_id} not found in task {params.task_id}")
        except Exception as e:
            return ToolResult.error_result(str(e))
