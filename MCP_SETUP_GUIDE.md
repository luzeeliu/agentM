# MCP Setup Guide for AgentM

This guide explains how your custom MCP (Model Context Protocol) server is integrated with LangGraph to replace the traditional tool node.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     LangGraph Agent                         │
│  ┌───────────┐         ┌──────────────┐                    │
│  │   Agent   │────────▶│  Tool Node   │                    │
│  │   (LLM)   │◀────────│ (MCP Tools)  │                    │
│  └───────────┘         └──────┬───────┘                    │
│                               │                             │
└───────────────────────────────┼─────────────────────────────┘
                                │ stdio transport
                                ▼
                    ┌───────────────────────┐
                    │   MCP Server          │
                    │  (FastMCP)            │
                    │                       │
                    │  ┌─────────────────┐  │
                    │  │ yahoo_search    │  │
                    │  │ duckduckgo_search│ │
                    │  │ google_search   │  │
                    │  │ bing_search     │  │
                    │  └─────────────────┘  │
                    └───────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │  LangChain Tools      │
                    │  (Search APIs)        │
                    └───────────────────────┘
```

## File Structure

```
AgentM/
├── agent/
│   ├── agent_runner.py          # LangGraph orchestration
│   ├── graph_state.py           # State definition
│   ├── llm_core.py              # LLM configuration
│   ├── MCP/
│   │   ├── server.py            # MCP server with tool definitions
│   │   ├── run_server.py        # Server entry point
│   │   └── mcp_adaptor.py       # MCP → LangChain adapter
│   └── tool/
│       ├── tool_box.py          # Legacy tool registry
│       └── search_tool/         # LangChain search tools
├── test_mcp_local.py            # Test suite
└── .env                         # Configuration
```

## Key Components

### 1. MCP Server ([agent/MCP/server.py](agent/MCP/server.py))

Exposes 4 search tools via FastMCP:
- `yahoo_search(query, page=5)`
- `duckduckgo_search(query, max_results=5)`
- `google_search(query, max_results=5)`
- `bing_search(query, max_results=5)`

Each tool wraps the corresponding LangChain tool from `agent/tool/search_tool/`.

### 2. MCP Adapter ([agent/MCP/mcp_adaptor.py](agent/MCP/mcp_adaptor.py))

**Key Features:**
- Connects to MCP server via stdio transport
- Discovers tools dynamically using `list_tools()`
- Converts JSON schema to Pydantic models
- Creates `StructuredTool` instances for LangChain
- Tools are prefixed with `mcp_` (e.g., `mcp_duckduckgo_search`)

**How it works:**
```python
# In agent_runner.py
from .MCP.mcp_adaptor import build_langchain_tools_from_mcp

mcp_tools = build_langchain_tools_from_mcp(os.getenv("MCP_COMMAND"))
tool_node = ToolNode(mcp_tools)
```

### 3. LangGraph Integration ([agent/agent_runner.py](agent/agent_runner.py))

The agent graph has 2 nodes:
1. **agent**: LLM node that decides which tools to call
2. **tool**: ToolNode that executes MCP tools

**Flow:**
```
Start → Agent → [has tool_calls?]
                     ↓ Yes        ↓ No
                   Tool          END
                     ↓
                   Agent (loop)
```

## Configuration

### Environment Variables ([.env](.env))

```bash
# MCP Server Command
MCP_COMMAND = python -m agent.MCP.run_server

# API Keys
GEMINI_API_KEY = your_gemini_key
GOOGLE_API_KEY = your_serpapi_key
```

## How to Test

### Test 1: MCP Tools Discovery

```bash
python test_mcp_local.py
```

This will:
1. Connect to the MCP server
2. List all available tools
3. Show tool names and descriptions

### Test 2: Tool Execution

The test script will execute a DuckDuckGo search to verify tools work correctly.

### Test 3: Full LangGraph Integration

Tests the complete agent with a sample query to ensure:
- LangGraph compiles correctly
- Agent can call MCP tools
- Results are returned properly

## Adding New Tools to MCP

### Step 1: Create LangChain Tool

Create a new tool in `agent/tool/`:

```python
# agent/tool/calculator_tool.py
from langchain.tools import BaseTool

class CalculatorTool(BaseTool):
    name: str = "calculator"
    description: str = "Performs basic math calculations"

    def _run(self, expression: str) -> str:
        try:
            result = eval(expression)  # Use safe eval in production!
            return f"Result: {result}"
        except Exception as e:
            return f"Error: {e}"
```

### Step 2: Add to MCP Server

Edit `agent/MCP/server.py`:

```python
@server.tool()
def calculator(expression: str):
    """Performs basic math calculations"""
    from ..tool.calculator_tool import CalculatorTool
    tool = CalculatorTool()
    return tool.invoke({"expression": expression})
```

### Step 3: Test

No changes needed in `agent_runner.py`! The adapter will automatically discover the new tool.

Run the test suite to verify:
```bash
python test_mcp_local.py
```

## Advantages of MCP Architecture

### ✅ **Dynamic Tool Discovery**
Tools are discovered at runtime - no need to manually register them in LangGraph.

### ✅ **Standardized Interface**
MCP provides a consistent protocol for tool communication across different LLM frameworks.

### ✅ **Process Isolation**
MCP server runs in a separate process, improving stability and security.

### ✅ **Easy Testing**
Tools can be tested independently via MCP before integrating with LangGraph.

### ✅ **Reusability**
The same MCP server can be used by multiple agents or frameworks.

### ✅ **Type Safety**
JSON schemas are automatically converted to Pydantic models for validation.

## Troubleshooting

### Issue: "MCP server not starting"

**Solution:** Check that `MCP_COMMAND` in `.env` is correct:
```bash
MCP_COMMAND = python -m agent.MCP.run_server
```

### Issue: "No tools discovered"

**Solution:** Verify the MCP server is exposing tools:
```python
# In agent/MCP/server.py
# Ensure @server.tool() decorator is used
@server.tool()
def your_tool_name(arg: str):
    pass
```

### Issue: "Tool execution fails"

**Solution:** Check that:
1. The underlying LangChain tool works independently
2. API keys are set in `.env`
3. Required dependencies are installed

### Issue: "Import errors"

**Solution:** Install required packages:
```bash
pip install -r requirements.txt
```

## Production Considerations

### 1. Error Handling

Add robust error handling in MCP server:

```python
@server.tool()
def robust_search(query: str):
    try:
        from ..tool.search_tool.duckduckgo_search_tool import DuckDuckGoSearchTool
        tool = DuckDuckGoSearchTool()
        return tool.invoke({"query": query})
    except Exception as e:
        return f"Error: {str(e)}"
```

### 2. Logging

Add logging to track tool usage:

```python
import logging

logger = logging.getLogger(__name__)

@server.tool()
def logged_search(query: str):
    logger.info(f"Search query: {query}")
    # ... tool execution
    logger.info(f"Search completed")
```

### 3. Rate Limiting

Implement rate limiting for API calls to avoid hitting limits.

### 4. Caching

Cache search results to reduce API calls:

```python
from functools import lru_cache

@lru_cache(maxsize=100)
def cached_search(query: str, max_results: int):
    # ... search implementation
```

## Next Steps

1. ✅ Run the test suite: `python test_mcp_local.py`
2. ✅ Add custom tools to the MCP server
3. ✅ Test with your backend: Start FastAPI server
4. ✅ Monitor tool usage and performance
5. ✅ Implement production improvements (logging, caching, etc.)

## Resources

- [MCP Documentation](https://modelcontextprotocol.io/)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [LangChain Tools](https://python.langchain.com/docs/modules/tools/)
- [FastMCP](https://github.com/jlowin/fastmcp)
