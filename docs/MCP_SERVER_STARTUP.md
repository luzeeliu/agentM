# How MCP Servers Start

## Quick Answer

**MCP servers are NOT started manually.** They are started **automatically** as subprocesses by `langchain_mcp_adapters` when your agent loads tools.

## The Process

### 1. Configuration ([mcp-server-config.json](../agent/tool/mcp/mcp-server-config.json))

```json
{
  "mcpServers": {
    "arxiv": {
      "command": "npx",
      "args": ["-y", "@langgpt/arxiv-paper-mcp@latest"]
    },
    "agent-web-search": {
      "command": "python",
      "args": ["-m", "agent.tool.mcp.server"]
    }
  }
}
```

This config tells `langchain_mcp_adapters`:
- **What command to run** to start each MCP server
- **What arguments** to pass to that command

### 2. Automatic Startup

When your agent starts:

```
Agent starts
    │
    ├─> tool_box() called
    │
    ├─> get_mcp_tools() called
    │
    ├─> For each server in config:
    │   │
    │   ├─> langchain_mcp_adapters runs:
    │   │   subprocess.Popen(['npx', '-y', '@langgpt/arxiv-paper-mcp@latest'])
    │   │
    │   ├─> Server subprocess starts
    │   │
    │   ├─> Connects via stdin/stdout
    │   │
    │   ├─> Sends MCP protocol messages:
    │   │   - "initialize"
    │   │   - "list_tools"
    │   │
    │   └─> Receives tool definitions
    │
    └─> Returns all tools to agent
```

### 3. Server Lifecycle

```
┌──────────────────────────────────────────────────────┐
│ Your Application Process                             │
│                                                       │
│  ┌────────────────────────────────┐                  │
│  │ agent/tool/tool_box.py         │                  │
│  │ (Your agent's main code)       │                  │
│  └───────────┬────────────────────┘                  │
│              │                                        │
│              │ calls get_mcp_tools()                 │
│              v                                        │
│  ┌────────────────────────────────┐                  │
│  │ agent/tool/mcp/mcp_client.py   │                  │
│  │ (Loads MCP tools)              │                  │
│  └───────────┬────────────────────┘                  │
│              │                                        │
│              │ langchain_mcp_adapters.load_mcp_tools()│
│              v                                        │
└──────────────┼───────────────────────────────────────┘
               │
               │ Spawns subprocess
               │
┌──────────────v───────────────────────────────────────┐
│ Subprocess 1: npx -y @langgpt/arxiv-paper-mcp@latest │
│                                                       │
│  - Starts arxiv MCP server                           │
│  - Listens on stdin                                  │
│  - Responds via stdout                               │
│  - Stays alive during entire session                 │
└───────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────┐
│ Subprocess 2: python -m agent.tool.mcp.server         │
│                                                       │
│  - Starts agent-web-search MCP server                │
│  - Listens on stdin                                  │
│  - Responds via stdout                               │
│  - Stays alive during entire session                 │
└───────────────────────────────────────────────────────┘
```

## Key Points

### No Startup File Needed

You **do NOT need** to create a separate file to start MCP servers. The command in the config is enough:

```json
{
  "command": "npx",
  "args": ["-y", "@langgpt/arxiv-paper-mcp@latest"]
}
```

This is equivalent to running in a terminal:
```bash
npx -y @langgpt/arxiv-paper-mcp@latest
```

But `langchain_mcp_adapters` runs this automatically as a subprocess.

### Servers Stay Alive

Once started, the MCP server subprocesses **stay alive** for the entire session. They:
- Listen for MCP protocol messages on stdin
- Respond with results via stdout
- Are automatically cleaned up when your application exits

### Communication Protocol

MCP servers communicate using JSON-RPC messages over stdin/stdout:

```
Your Agent                          MCP Server (subprocess)
    │                                      │
    ├──── initialize ──────────────────>  │
    │                                      │
    │  <──── initialized ───────────────  │
    │                                      │
    ├──── list_tools ──────────────────>  │
    │                                      │
    │  <──── tools: [...]  ─────────────  │
    │                                      │
    ├──── call_tool(search_arxiv) ────>  │
    │                                      │
    │  <──── result: {...} ─────────────  │
    │                                      │
```

## Example: Manual MCP Server Start (for testing)

If you want to start an MCP server manually to test it:

```bash
# Start arxiv server
npx -y @langgpt/arxiv-paper-mcp@latest

# Start agent-web-search server
python -m agent.tool.mcp.server
```

The server will wait for JSON-RPC messages on stdin. You can send messages manually:

```json
{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}}}
```

But **you don't need to do this** - `langchain_mcp_adapters` handles it automatically!

## In Docker

In Docker, the exact same process happens, but:

1. **Pre-installed binaries** - MCP servers are installed during image build:
   ```dockerfile
   RUN npm install -g @langgpt/arxiv-paper-mcp
   ```

2. **Direct command** - Config uses the installed binary directly:
   ```json
   {
     "command": "arxiv-paper-mcp",  // Not "npx -y ..."
     "args": []
   }
   ```

3. **Same subprocess model** - Still spawned as subprocesses, just faster startup

## Testing

To see MCP servers start in real-time:

```bash
# See the full process
python -m agent.tool.mcp.mcp_client

# See server configuration and lifecycle
python scripts/show_mcp_process.py

# In Docker
docker exec -it agentm python scripts/test_mcp_in_docker.py
```

## Summary

- **No startup file needed** - MCP servers start automatically
- **Config defines the command** - `mcp-server-config.json` has the startup command
- **langchain_mcp_adapters handles it** - Spawns subprocess, connects, loads tools
- **Servers run as subprocesses** - Stay alive during session
- **Transparent to your code** - Just call `get_mcp_tools()` and everything works!
