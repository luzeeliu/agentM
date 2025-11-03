# Gemini Tool Schema Compatibility

## Issue

When using MCP tools with Gemini, some tools cause errors:

```
InvalidArgument: 400 * GenerateContentRequest.tools[0].function_declarations[3].parameters.properties[paperInfo].properties[authors].items: missing field.
```

## Root Cause

**Gemini's strict schema validation** requires that all array fields in tool schemas must have an `items` definition. Some MCP tools from external servers have schemas that don't meet this requirement.

### Example of Problematic Schema

```python
# Problematic (missing 'items'):
{
  "type": "object",
  "properties": {
    "authors": {
      "type": "array"  # ❌ Missing 'items' field!
    }
  }
}

# Correct (has 'items'):
{
  "type": "object",
  "properties": {
    "authors": {
      "type": "array",
      "items": {
        "type": "string"  # ✅ Defines what's in the array
      }
    }
  }
}
```

## Solution

We've implemented a **tool filtering system** in [tool_box.py](../agent/tool/tool_box.py) that:

1. Loads all MCP tools
2. Filters out tools with incompatible schemas
3. Returns only Gemini-compatible tools

### Implementation

```python
# In tool_box.py

GEMINI_INCOMPATIBLE_TOOLS = [
    'parse_paper_content',  # Has authors array without items definition
]

def _is_tool_schema_valid(tool: BaseTool) -> bool:
    """Check if a tool's schema is compatible with Gemini."""
    if tool.name in GEMINI_INCOMPATIBLE_TOOLS:
        return False
    return True
```

## Affected Tools

### Currently Excluded

1. **parse_paper_content** (from arxiv-paper-mcp)
   - Has `authors` array field without `items` definition
   - This is a bug in the arxiv-paper-mcp server
   - Other arxiv tools work fine

### Still Available

All other tools work correctly:

**From arxiv-paper-mcp (3/4 tools):**
- ✅ `search_arxiv` - Search arXiv papers
- ✅ `get_recent_ai_papers` - Get recent AI papers
- ✅ `get_arxiv_pdf_url` - Get PDF URLs
- ❌ `parse_paper_content` - EXCLUDED (schema issue)

**From agent-web-search (4/4 tools):**
- ✅ `yahoo_search` - Yahoo search
- ✅ `duckduckgo_search` - DuckDuckGo search
- ✅ `google_search` - Google search
- ✅ `bing_search` - Bing search

**Total: 7 tools available** (1 excluded for compatibility)

## Checking Tool Schemas

Use the diagnostic script to check all tool schemas:

```bash
docker exec -it agentm python scripts/check_tool_schemas.py
```

This will show:
- Which tools have valid schemas
- Which tools have issues
- Specific schema problems

## Adding More Exclusions

If you encounter more tools with schema issues:

1. Check the error message for the tool name
2. Add it to the `GEMINI_INCOMPATIBLE_TOOLS` list in [tool_box.py](../agent/tool/tool_box.py):

```python
GEMINI_INCOMPATIBLE_TOOLS = [
    'parse_paper_content',
    'your_problematic_tool_name',  # Add here
]
```

3. Restart the container:
```bash
docker-compose restart
```

## Alternative: Fix the MCP Server

The proper fix is to update the MCP server to provide valid schemas. For the arxiv server, you could:

1. Report the issue to the maintainers
2. Fork and fix the schema
3. Use a different MCP server

## Testing

After excluding tools, verify:

```bash
# Check logs
docker-compose logs agentm | grep tool_box

# Should see:
[tool_box] Successfully loaded 7 MCP tools
[tool_box] Excluded 1 incompatible tools: ['parse_paper_content']
```

## LLM Compatibility

This issue is **specific to Gemini**. Other LLMs may:

- **OpenAI GPT models**: More lenient, might accept incomplete schemas
- **Anthropic Claude**: Similar strict validation
- **Local models (Ollama, etc.)**: Often more forgiving

If you switch LLMs, you may be able to remove the filter.

## References

- [Gemini Function Calling Docs](https://ai.google.dev/gemini-api/docs/function-calling)
- [JSON Schema Specification](https://json-schema.org/)
- [arxiv-paper-mcp Repository](https://github.com/langgptai/arxiv-paper-mcp)

## Future Improvements

Potential enhancements:

1. **Automatic schema fixing**: Transform invalid schemas to valid ones
2. **Dynamic validation**: Check schemas at runtime instead of hardcoding
3. **Per-LLM filters**: Different exclusion lists for different LLMs
4. **Schema validation tool**: Pre-check tools before adding to config
