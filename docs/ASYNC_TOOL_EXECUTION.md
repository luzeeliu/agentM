# Async Tool Execution for MCP Tools

## Issue

When the agent tried to execute MCP tools, it crashed with:

```python
NotImplementedError: StructuredTool does not support sync invocation.
```

## Root Cause

**MCP tools are async-only** by design:
- `langchain-mcp-adapters` creates tools that only support `_arun()` (async execution)
- The original `tool_wrapper` in [agent_runner.py](../agent/agent_runner.py) used sync `invoke()`
- LangGraph's `ToolNode` tried to execute tools synchronously by default

### Why MCP Tools Must Be Async

MCP (Model Context Protocol) tools communicate with external server processes via stdio:
1. Send request to MCP server subprocess
2. Wait for response from subprocess
3. Parse and return result

This I/O-bound operation **must** be async to avoid blocking.

## Solution

Changed [agent_runner.py](../agent/agent_runner.py) to use **async tool execution**:

### Before (Sync - Broken)

```python
# Sync invocation (doesn't work with MCP tools)
def tool_wrapper(state: GraphState):
    message = state.get("message", [])
    tool_node = ToolNode(tool_box())
    result = tool_node.invoke({"messages": message})  # ❌ Sync
    ...
```

### After (Async - Works)

```python
# Async invocation (works with MCP tools)
async def tool_wrapper(state: GraphState):
    message = state.get("message", [])
    tool_node = _get_tool_node()
    result = await tool_node.ainvoke({"messages": message})  # ✅ Async
    ...
```

## Key Changes

1. **Made `tool_wrapper` async** (line 32)
   ```python
   async def tool_wrapper(state: GraphState):
   ```

2. **Used `ainvoke` instead of `invoke`** (line 38)
   ```python
   result = await tool_node.ainvoke({"messages": message})
   ```

3. **Lazy tool node initialization** (lines 22-29)
   - Tool node is created on first use
   - Ensures tools are loaded when needed

## How It Works

```
User Request
    │
    ├──> agent() - LLM decides to use a tool
    │
    ├──> check_tool_call() - Detects tool call
    │
    ├──> tool_wrapper() - ASYNC execution
    │         │
    │         ├──> ToolNode.ainvoke()
    │         │         │
    │         │         ├──> MCP tool._arun()
    │         │         │         │
    │         │         │         ├──> Send request to MCP server subprocess
    │         │         │         ├──> Await response (ASYNC I/O)
    │         │         │         └──> Return result
    │         │         │
    │         │         └──> Collect tool results
    │         │
    │         └──> Return updated messages
    │
    └──> agent() - Process tool results and generate response
```

## LangGraph Async Support

LangGraph fully supports async nodes:
- If a node function is `async def`, LangGraph uses `ainvoke()`
- If a node function is regular `def`, LangGraph uses `invoke()`
- MCP tools **require** async execution

## Testing

After applying this fix, MCP tools work correctly:

```bash
# Restart container
docker-compose restart

# Test the agent
# Should see successful tool execution:
[agent] Tool calls: ['google_search']
[tool] Executing google_search...
[tool] Result: {...}
```

## Performance Benefits

Async execution also provides:

1. **Better concurrency**: Multiple tool calls can run in parallel
2. **Non-blocking I/O**: Server doesn't freeze waiting for MCP responses
3. **Scalability**: Can handle more concurrent requests

## Related Files

- [agent/agent_runner.py](../agent/agent_runner.py) - Tool wrapper implementation
- [agent/tool/tool_box.py](../agent/tool/tool_box.py) - Tool loading and filtering
- [agent/tool/mcp/mcp_client.py](../agent/tool/mcp/mcp_client.py) - MCP tool loading

## Alternative Solutions

If you needed sync-only execution, you could:

1. **Wrap async in sync** (not recommended):
   ```python
   import asyncio
   result = asyncio.run(tool_node.ainvoke(...))
   ```
   But this defeats the purpose of async.

2. **Use different tools**: Non-MCP tools might support sync
3. **Modify MCP tools**: Add sync wrappers (complex)

The async approach is the **correct solution** for MCP tools.

## References

- [LangGraph Async Support](https://langchain-ai.github.io/langgraph/concepts/#asynchronous)
- [Python Async/Await](https://docs.python.org/3/library/asyncio-task.html)
- [MCP Protocol Specification](https://spec.modelcontextprotocol.io/)
