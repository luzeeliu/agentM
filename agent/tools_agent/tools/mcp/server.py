from pathlib import Path
from mcp.server.fastmcp import FastMCP
from pathlib import Path

server = FastMCP("agent-web-search-tools")
DEFAULT_WORKSPACE = Path(__file__).parent.parent / "MCP_workspace"

@server.tool()
async def yahoo_search(query: str, page: int = 5):
    from ..search_tool.yahoo_search_tool import YahooSearchTool
    tool = YahooSearchTool()
    return tool.invoke({"query": query, "page": page})

@server.tool()
async def duckduckgo_search(query: str, max_results: int = 5):
    from ..search_tool.duckduckgo_search_tool import DuckDuckGoSearchTool
    tool = DuckDuckGoSearchTool()
    return tool.invoke({"query": query, "max_results": max_results})

@server.tool()
async def google_search(query: str, max_results: int = 5):
    from ..search_tool.google_search_tool import GoogleSearchTool
    tool = GoogleSearchTool()
    return tool.invoke({"query": query, "max_results": max_results})

@server.tool()
async def bing_search(query: str, max_results: int = 5):
    from ..search_tool.bing_search_tool import BingSearchTool
    tool = BingSearchTool()
    return tool.invoke({"query": query, "max_results": max_results})

if __name__ == "__main__":
    server.run()