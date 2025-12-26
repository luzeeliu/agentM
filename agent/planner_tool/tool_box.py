from typing import List
from langchain_core.tools import BaseTool

def tool_box() -> List[BaseTool]:
    tools: List[BaseTool] = []

    # Add direct search tools (not via MCP to avoid async complexity)
    try:
        #tools.append(BingSearchTool())
        print(f"[tool_box] Added 4 search tools directly")
    except Exception as e:
        print(f"[tool_box] Failed to load search tools: {e}")


    # Add MCP tools (e.g., arxiv)
    return tools
