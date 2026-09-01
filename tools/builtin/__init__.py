from tools.builtin.edit_file import EditTool
from tools.builtin.glob import GlobTool
from tools.builtin.grep import GrepTool
from tools.builtin.list_dir import ListDirTool
from tools.builtin.inspect_codebase import InspectCodebaseTool
from tools.builtin.memory import MemoryTool
from tools.builtin.read_file import ReadFileTool
from tools.builtin.shell import ShellTool
from tools.builtin.tasks import (
    ClaimTaskTool,
    CompleteTaskTool,
    CreateTaskTool,
    CreatePlanTool,
    FailTaskTool,
    GetTaskTool,
    ListTasksTool,
    ResumeTaskTool,
    UpdateTaskTool,
    AddTodoTool,
    CompleteTodoTool,
)
from tools.builtin.web_fetch import WebFetchTool
from tools.builtin.web_search import WebSearchTool
from tools.builtin.write_file import WriteFileTool

__all__ = [
    "ReadFileTool",
    "WriteFileTool",
    "EditTool",
    "ShellTool",
    "ListDirTool",
    "InspectCodebaseTool",
    "GrepTool",
    "GlobTool",
    "WebSearchTool",
    "WebFetchTool",
    "CreateTaskTool",
    "CreatePlanTool",
    "UpdateTaskTool",
    "ClaimTaskTool",
    "CompleteTaskTool",
    "ResumeTaskTool",
    "FailTaskTool",
    "GetTaskTool",
    "ListTasksTool",
    "AddTodoTool",
    "CompleteTodoTool",
    "MemoryTool",
]


def get_all_builtin_tools() -> list[type]:
    return [
        ReadFileTool,
        WriteFileTool,
        EditTool,
        ShellTool,
        ListDirTool,
        InspectCodebaseTool,
        GrepTool,
        GlobTool,
        WebSearchTool,
        WebFetchTool,
        CreateTaskTool,
        CreatePlanTool,
        UpdateTaskTool,
        ClaimTaskTool,
        CompleteTaskTool,
        ResumeTaskTool,
        FailTaskTool,
        GetTaskTool,
        ListTasksTool,
        AddTodoTool,
        CompleteTodoTool,
        MemoryTool,
    ]
