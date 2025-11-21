import threading
from typing import List

from langchain_core.tools import BaseTool

from .mcp.mcp_client import get_mcp_tools


_mcp_tools: List[BaseTool] | None = None
_mcp_lock = threading.Lock()

# Tools with schema incompatibilities for Gemini
# These tools have array fields without 'items' definitions
GEMINI_INCOMPATIBLE_TOOLS = [
    'parse_paper_content',  # Has authors array without items definition
]


def _is_tool_schema_valid(tool: BaseTool) -> bool:
    """
    Check if a tool's schema is compatible with Gemini.

    Gemini requires that all array fields have an 'items' definition.
    """
    if tool.name in GEMINI_INCOMPATIBLE_TOOLS:
        return False

    # Could add more sophisticated schema validation here
    return True


def _ensure_mcp_tools() -> List[BaseTool]:
    """
    Load MCP tools using langchain_mcp_adapters.
    Tools are cached after first load.
    """
    global _mcp_tools
    if _mcp_tools is not None:
        return _mcp_tools

    with _mcp_lock:
        if _mcp_tools is None:
            try:
                print("[tool_box] Loading MCP tools...")
                all_tools = get_mcp_tools()

                # Filter out tools with incompatible schemas
                _mcp_tools = []
                excluded_tools = []

                for tool in all_tools:
                    if _is_tool_schema_valid(tool):
                        _mcp_tools.append(tool)
                    else:
                        excluded_tools.append(tool.name)

                print(f"[tool_box] Successfully loaded {len(_mcp_tools)} MCP tools")
                if excluded_tools:
                    print(f"[tool_box] Excluded {len(excluded_tools)} incompatible tools: {excluded_tools}")
            except Exception as exc:  # pragma: no cover - defensive
                print(f"[tool_box] Failed to load MCP tools: {exc}")
                _mcp_tools = []

    return _mcp_tools


def tool_box() -> List[BaseTool]:
    tools: List[BaseTool] = []

    # Add direct search tools (not via MCP to avoid async complexity)
    """
    try:
        from .search_tool.google_search_tool import GoogleSearchTool
        from .search_tool.duckduckgo_search_tool import DuckDuckGoSearchTool
        from .search_tool.yahoo_search_tool import YahooSearchTool
        from .search_tool.bing_search_tool import BingSearchTool

        tools.append(GoogleSearchTool())
        tools.append(DuckDuckGoSearchTool())
        tools.append(YahooSearchTool())
        tools.append(BingSearchTool())
        print(f"[tool_box] Added 4 search tools directly")
    except Exception as e:
        print(f"[tool_box] Failed to load search tools: {e}")
"""
    try:
        from .local_search.rag_tool import VanillaRAGSearchTool

        tools.append(VanillaRAGSearchTool())
        print(f"[tool_box] Added vanilla RAG search tool")
    except Exception as e:
        print(f"[tool_box] Failed to load vanilla RAG tool: {e}")

    # Add MCP tools (e.g., arxiv)
    #tools.extend(_ensure_mcp_tools())
    return tools
