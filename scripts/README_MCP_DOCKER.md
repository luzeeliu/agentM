# MCP Integration in Docker

This document explains how MCP (Model Context Protocol) tools are integrated into the Docker environment.

## Architecture Overview

### MCP Servers Configured

1. **arxiv-paper-mcp** - Node.js-based MCP server for arXiv paper search
   - Pre-installed globally in Docker: `npm install -g @langgpt/arxiv-paper-mcp`
   - Provides tools: `search_arxiv`, `get_recent_ai_papers`, `get_arxiv_pdf_url`, `parse_paper_content`

2. **agent-web-search** - Python-based MCP server for web search
   - Local server at: `agent/tool/mcp/server.py`
   - Provides tools: `yahoo_search`, `duckduckgo_search`, `google_search`, `bing_search`

### Configuration Files

- **mcp-server-config.json** - Defines MCP server commands and arguments
  - Located at: `agent/tool/mcp/mcp-server-config.json`
  - Updated for Docker environment to use installed commands

- **mcp_client.py** - Loads MCP tools using `langchain-mcp-adapters`
  - Located at: `agent/tool/mcp/mcp_client.py`
  - Uses `StdioConnection` to connect to MCP servers

- **tool_box.py** - Integrates MCP tools into the agent
  - Located at: `agent/tool/tool_box.py`
  - Automatically loads MCP tools on first call

## Docker Environment Setup

### Key Changes for Docker

1. **Dockerfile Updates:**
   - Pre-installs `@langgpt/arxiv-paper-mcp` globally (line 31)
   - Adds `langchain-mcp-adapters` to Python requirements
   - Includes Node.js 20.x for running Node-based MCP servers

2. **MCP Server Config Updates:**
   ```json
   {
     "arxiv": {
       "command": "arxiv-paper-mcp",  // Direct command (installed globally)
       "args": []
     },
     "agent-web-search": {
       "command": "python",
       "args": ["-m", "agent.tool.mcp.server"]  // Module import style
     }
   }
   ```

## Testing MCP Integration

### 1. Build the Docker Image

```bash
docker-compose build
```

### 2. Test MCP Tools Inside Container

```bash
# Start the container
docker-compose up -d

# Run the test script inside the container
docker exec -it agentm python scripts/test_mcp_in_docker.py
```

Expected output:
```
🐳 Docker MCP Integration Test Suite

============================================================
Testing MCP Client Integration
============================================================

[1/3] Loading MCP tools...
[mcp_client] Loading tools from MCP server: arxiv
[mcp_client] Loaded 4 tools from arxiv
[mcp_client] Loading tools from MCP server: agent-web-search
[mcp_client] Loaded 4 tools from agent-web-search

[2/3] Successfully loaded 8 MCP tools

[3/3] Tool details:
  1. search_arxiv
  2. get_recent_ai_papers
  3. get_arxiv_pdf_url
  4. parse_paper_content
  5. yahoo_search
  6. duckduckgo_search
  7. google_search
  8. bing_search

============================================================
✅ MCP Integration Test: PASSED
============================================================
```

### 3. Test Standalone MCP Client

```bash
# Test just the mcp_client module
docker exec -it agentm python -m agent.tool.mcp.mcp_client
```

### 4. Enable Build-Time Testing (Optional)

Uncomment lines 63-64 in Dockerfile to run tests during build:
```dockerfile
RUN python scripts/check_mcp_servers.py
RUN python scripts/test_mcp_in_docker.py
```

## Troubleshooting

### MCP Server Not Found

**Issue:** `command not found: arxiv-paper-mcp`

**Solution:** Ensure the package is installed globally in Dockerfile:
```dockerfile
RUN npm install -g @langgpt/arxiv-paper-mcp
```

### Connection Closed Error

**Issue:** `mcp.shared.exceptions.McpError: Connection closed`

**Possible causes:**
1. MCP server binary not executable
2. Missing dependencies in Docker image
3. Wrong command path in config

**Solution:** Verify the command works in the container:
```bash
docker exec -it agentm which arxiv-paper-mcp
docker exec -it agentm arxiv-paper-mcp --help
```

### Python Module Not Found

**Issue:** `ModuleNotFoundError: No module named 'langchain_mcp_adapters'`

**Solution:** Add to requirements.txt:
```txt
langchain-mcp-adapters>=0.1.12
```

## Local Development vs Docker

### Local Development
- Uses `npx -y @langgpt/arxiv-paper-mcp@latest` to download on-demand
- Relative paths for local Python servers

### Docker Production
- Pre-installed MCP servers for faster startup
- Absolute paths using Python module imports
- All dependencies baked into the image

## Dependencies

### Python Packages (requirements.txt)
```txt
mcp>=1.0.0
langchain-mcp-adapters>=0.1.12
langchain-core==0.3.15
```

### Node.js Packages (globally installed)
```bash
npm install -g @langgpt/arxiv-paper-mcp
```

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                   Docker Container                       │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │            agent/tool/tool_box.py              │    │
│  │  (Aggregates all tools for the agent)          │    │
│  └──────────────────┬─────────────────────────────┘    │
│                     │                                    │
│                     v                                    │
│  ┌────────────────────────────────────────────────┐    │
│  │         agent/tool/mcp/mcp_client.py           │    │
│  │  (Loads MCP tools using langchain_mcp_adapters)│    │
│  └──────────┬───────────────────┬─────────────────┘    │
│             │                   │                        │
│             v                   v                        │
│  ┌─────────────────┐ ┌──────────────────────────┐      │
│  │  arxiv-paper-mcp│ │ agent/tool/mcp/server.py │      │
│  │  (Node.js MCP)  │ │ (Python FastMCP Server)  │      │
│  └─────────────────┘ └──────────────────────────┘      │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## Next Steps

1. **Add More MCP Servers:** Edit `mcp-server-config.json` and install dependencies in Dockerfile
2. **Monitor Performance:** Check MCP server startup time and resource usage
3. **Error Handling:** Add retry logic for transient MCP connection failures
4. **Caching:** Implement tool caching to avoid re-loading on every request
