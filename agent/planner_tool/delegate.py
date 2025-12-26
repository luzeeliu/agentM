from typing import Type
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

class DelegateInput(BaseModel):
    task: str = Field(description="The specific task or instruction to delegate to the specialist tool agent.")
    context: str = Field(description="Any necessary context or background information needed to perform the task.", default="")

class DelegateTool(BaseTool):
    name: str = "delegate_to_tool_agent"
    description: str = (
        "Use this tool to delegate complex tasks, browsing, deep research, or specific tool usages "
        "to the specialist Tool Agent. Use this when you don't have the specific tool required (like browser_navigate, etc.) "
        "or when the task requires a multi-step execution."
    )
    args_schema: Type[BaseModel] = DelegateInput

    def _run(self, task: str, context: str = "") -> str:
        # This function acts as a placeholder. The actual execution happens in the graph routing.
        return f"Delegating task: {task} with context: {context}"
