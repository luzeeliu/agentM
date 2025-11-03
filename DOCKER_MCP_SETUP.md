# Docker MCP Setup Guide

## Overview
This guide explains how MCP servers are configured to work in Docker to avoid timeout issues.

## Problem
MCP servers using `uvx`, `uv`, or `npx` download packages at runtime, causing:
- Timeout errors during container startup
- Network-dependent failures
- Slow initialization

## Solution
All MCP servers are **pre-installed during Docker build**, not at runtime.

## Architecture

### File Structure
```
AgentM/
├── Dockerfile                          # Pre-installs all MCP servers
├── docker-compose.yml                  # Container configuration
├── .env                                # Environment variables (API keys)
├── .env.example                        # Template for required env vars
├── agent/tool/mcp/
│   ├── mcp-server-config.json         # MCP server definitions
│   ├── mcp_server_config.py           # Config loader with env var expansion
│   ├── mcp_tool.py                    # MCP toolkit implementation
│   └── README.md                      # Detailed MCP documentation
└── scripts/
    ├── test_mcp_config.py             # Test config loading
    └── check_mcp_servers.py           # Health check for servers
```

### Environment Variable Flow

1. **`.env` file** (you create this):
   ```bash
   GEMINI_API_KEY=your_actual_api_key_here
   ```

2. **`docker-compose.yml`** loads `.env`:
   ```yaml
   env_file:
     - .env
     - agent/.env
   ```

3. **`mcp-server-config.json`** uses placeholders:
   ```json
   {
     "imagen3": {
       "env": {
         "GEMINI_API_KEY": "${GEMINI_API_KEY}"
       }
     }
   }
   ```

4. **`mcp_server_config.py`** expands variables:
   ```python
   # ${GEMINI_API_KEY} → actual value from os.environ
   ```

## MCP Server Types

### 1. Python-based (PyPI packages)
**Example:** `mcp-server-fetch`, `arxiv-mcp-server`

**Dockerfile:**
```dockerfile
RUN /root/.cargo/bin/uv tool install mcp-server-fetch
```

**Config:**
```json
"fetch": {
  "command": "uvx",
  "args": ["mcp-server-fetch"]
}
```

### 2. Node-based (npm packages)
**Example:** `@playwright/mcp`

**Dockerfile:**
```dockerfile
RUN npm install -g @playwright/mcp
```

**Config:**
```json
"playwright": {
  "command": "npx",
  "args": ["@playwright/mcp"]
}
```

### 3. Rust-based (GitHub source)
**Example:** `imagen3-mcp`

**Dockerfile:**
```dockerfile
RUN git clone https://github.com/hamflx/imagen3-mcp.git /tmp/imagen3-mcp \
    && cd /tmp/imagen3-mcp \
    && cargo build --release \
    && cp target/release/imagen3-mcp /usr/local/bin/imagen3-mcp \
    && rm -rf /tmp/imagen3-mcp
```

**Config:**
```json
"imagen3": {
  "command": "/usr/local/bin/imagen3-mcp",
  "args": [],
  "env": {
    "GEMINI_API_KEY": "${GEMINI_API_KEY}"
  }
}
```

## Path Handling: Docker vs Local

### Docker (Linux container)
```json
"command": "/usr/local/bin/imagen3-mcp"  // Linux path
```

### Windows Local Development
Use environment variable for flexibility:

```json
"command": "${IMAGEN3_MCP_PATH}"
```

Then set in `.env`:
```bash
# Docker
IMAGEN3_MCP_PATH=/usr/local/bin/imagen3-mcp

# Windows
# IMAGEN3_MCP_PATH=C:\bin\imagen3-mcp.exe
```

## Build & Deploy

### 1. Set up environment
```bash
cp .env.example .env
# Edit .env and add your API keys
```

### 2. Build Docker image
```bash
docker-compose build
```

This will:
- Install Node.js and npm
- Install Python and uv
- Install Rust toolchain
- Pre-install all MCP servers
- Copy your code

### 3. Run container
```bash
docker-compose up
```

### 4. Verify MCP servers (optional)
Inside the container:
```bash
docker exec -it agentm python scripts/test_mcp_config.py
docker exec -it agentm python scripts/check_mcp_servers.py
```

## Adding New MCP Servers

### Step 1: Install in Dockerfile
Choose the appropriate method based on the server type (see examples above).

### Step 2: Add to mcp-server-config.json
```json
{
  "mcpServers": {
    "my-server": {
      "command": "command-to-run",
      "args": ["arg1", "arg2"],
      "env": {
        "API_KEY": "${MY_API_KEY}"
      }
    }
  }
}
```

### Step 3: Add env vars to .env
```bash
MY_API_KEY=your_key_here
```

### Step 4: Rebuild
```bash
docker-compose build
docker-compose up
```

## Troubleshooting

### `uv: not found`
**Cause:** PATH not set correctly for uv

**Fix:** Use full path `/root/.cargo/bin/uv` in Dockerfile

### Environment variable not expanded
**Cause:** Variable not in `.env` or wrong syntax

**Fix:**
```bash
# Test locally
python scripts/test_mcp_config.py

# Check .env file
cat .env | grep MY_VAR
```

### MCP server timeout
**Cause:** Server not pre-installed, trying to download at runtime

**Fix:** Add installation step to Dockerfile

### Build fails on requirements.txt
**Cause:** Invalid package names or version conflicts

**Fix:**
- Don't include `uv` or `mcp-server-fetch` in requirements.txt
- These are tools, not Python libraries
- Keep only actual Python packages

## References

- [MCP Server Config README](agent/tool/mcp/README.md) - Detailed MCP documentation
- [Dockerfile](Dockerfile) - Full build configuration
- [.env.example](.env.example) - Environment variable template
