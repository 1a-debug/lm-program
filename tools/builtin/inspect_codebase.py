from pydantic import BaseModel, Field

from context.project import inspect_symbol
from tools.base import Tool, ToolInvocation, ToolKind, ToolResult


class InspectCodebaseParams(BaseModel):
    symbol: str = Field(..., min_length=1, description="Function, class, module, or identifier to locate")
    max_results: int = Field(50, ge=1, le=200, description="Maximum matching lines to return")


class InspectCodebaseTool(Tool):
    name = "inspect_codebase"
    description = "Locate a symbol's definitions, imports, references, and likely callers before changing code."
    kind = ToolKind.READ
    schema = InspectCodebaseParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        params = InspectCodebaseParams(**invocation.params)
        return ToolResult.success_result(
            inspect_symbol(invocation.cwd, params.symbol, params.max_results)
        )
