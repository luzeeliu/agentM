# Pydantic Version Fix for MCP

## Issue

The agent-web-search MCP server crashed with:
```python
KeyError: 'fields'
```

This error occurred in Pydantic's internal schema processing, indicating a version incompatibility.

## Root Cause

The `mcp` package (version 1.20.0+) requires **Pydantic >= 2.10.0**, but `backend/requirements.txt` had:
```txt
pydantic==2.8.2  # Too old!
```

When the MCP server tried to import `from mcp.server.fastmcp import FastMCP`, it failed because Pydantic 2.8.2 has internal API differences that break MCP's model definitions.

## Solution

Updated [backend/requirements.txt](../backend/requirements.txt):

```diff
- pydantic==2.8.2
+ pydantic>=2.10.0
```

Also loosened other version constraints for better compatibility:

```diff
- fastapi==0.115.0
- uvicorn==0.30.6
+ fastapi>=0.115.0
+ uvicorn>=0.30.6
```

## Why This Fixes It

1. **MCP Compatibility**: `mcp>=1.0.0` uses Pydantic 2.10+ internal APIs
2. **FastAPI Compatibility**: FastAPI 0.115+ also works with Pydantic 2.10+
3. **No Breaking Changes**: Pydantic 2.10 is backward compatible with 2.8 for most use cases

## Files Updated

- ✅ [backend/requirements.txt](../backend/requirements.txt) - Updated Pydantic to >= 2.10.0
- ✅ [scripts/test_mcp_in_docker.py](../scripts/test_mcp_in_docker.py) - Added version check
- ✅ [scripts/check_pydantic_version.py](../scripts/check_pydantic_version.py) - New diagnostic script

## Testing

### Check Version Compatibility

```bash
# Inside Docker container
docker exec -it agentm python scripts/check_pydantic_version.py
```

Should show:
```
[OK] pydantic                    2.10.x (or higher)
```

### Test MCP Integration

```bash
# Full integration test
docker exec -it agentm python scripts/test_mcp_in_docker.py
```

Should show:
```
[OK] Pydantic version is compatible
[OK] PASSED - MCP Client Test
[OK] PASSED - Tool Box Test
```

## Rebuild Instructions

Since you already have a running container with the old Pydantic version, you need to rebuild:

```bash
# Stop the current container
docker-compose down

# Rebuild with updated requirements
docker-compose build --no-cache

# Start the new container
docker-compose up -d

# Test MCP integration
docker exec -it agentm python scripts/test_mcp_in_docker.py
```

## Expected Outcome

After rebuilding, both MCP servers should work:

```
[tool_box] Loading MCP tools...
[mcp_client] Loading tools from MCP server: arxiv
[mcp_client] Loaded 4 tools from arxiv
[mcp_client] Loading tools from MCP server: agent-web-search
[mcp_client] Loaded 4 tools from agent-web-search  ✅
[tool_box] Successfully loaded 8 MCP tools
```

## Pydantic Version Matrix

| Pydantic Version | MCP Support | FastAPI 0.115+ | Status |
|------------------|-------------|----------------|---------|
| 2.8.x           | ❌ No       | ✅ Yes          | Too old for MCP |
| 2.9.x           | ⚠️ Maybe    | ✅ Yes          | Might work |
| 2.10.x+         | ✅ Yes      | ✅ Yes          | **Recommended** |

## Additional Notes

### Why the `KeyError: 'fields'` Error?

Pydantic's internal schema structure changed between 2.8 and 2.10. The MCP library uses Pydantic's internal APIs (`_internal._core_utils`) which rely on the newer schema format.

### Why Not Pin to Exact Version?

We use `>=2.10.0` instead of `==2.10.x` because:
1. Allows bug fixes and security updates
2. Pydantic follows semantic versioning (2.x.y are compatible)
3. Makes dependency resolution easier
4. Future-proof for MCP updates

### Local Development

If you're running locally (not in Docker), update your local environment:

```bash
pip install 'pydantic>=2.10.0' --upgrade
```

## References

- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Pydantic Changelog](https://docs.pydantic.dev/latest/changelog/)
- [FastAPI Pydantic Compatibility](https://fastapi.tiangolo.com/release-notes/#0115
0)
