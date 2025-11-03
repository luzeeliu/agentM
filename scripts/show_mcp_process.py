#!/usr/bin/env python3
"""
Script to demonstrate how MCP servers are started as subprocesses.
This shows what happens when langchain_mcp_adapters loads tools.
"""

import asyncio
import subprocess
import json
from pathlib import Path


def show_config():
    """Show what's in the MCP config file."""
    config_path = Path(__file__).parent.parent / "agent" / "tool" / "mcp" / "mcp-server-config.json"

    print("=" * 70)
    print("MCP SERVER CONFIGURATION")
    print("=" * 70)

    with open(config_path, 'r') as f:
        config = json.load(f)

    servers = config.get('mcpServers', {})

    for name, server_config in servers.items():
        command = server_config.get('command')
        args = server_config.get('args', [])

        print(f"\n[*] Server: {name}")
        print(f"   Command: {command}")
        print(f"   Args: {args}")
        print(f"   Full command that will be executed:")
        full_cmd = [command] + args
        print(f"   $ {' '.join(full_cmd)}")
        print()


async def demonstrate_server_startup():
    """
    Demonstrate what langchain_mcp_adapters does internally.
    This shows the subprocess being created.
    """
    print("=" * 70)
    print("HOW MCP SERVERS START (Demonstration)")
    print("=" * 70)
    print()

    print("When you call get_mcp_tools(), langchain_mcp_adapters:")
    print()
    print("1. Reads the command from mcp-server-config.json")
    print("2. Spawns a subprocess with that command")
    print("3. Connects to the subprocess via stdin/stdout")
    print("4. Sends MCP protocol messages to list available tools")
    print("5. Converts MCP tools to LangChain BaseTool instances")
    print()

    print("=" * 70)
    print("EXAMPLE: Starting arxiv MCP server manually")
    print("=" * 70)
    print()

    # This is what langchain_mcp_adapters does internally
    cmd = ['npx', '-y', '@langgpt/arxiv-paper-mcp@latest']
    print(f"Command: {' '.join(cmd)}")
    print()
    print("Starting server subprocess...")
    print("(Server will start, then we'll send it a 'list tools' request)")
    print()

    try:
        # Start the server process (this is what langchain_mcp_adapters does)
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )

        print(f"[OK] Server process started (PID: {process.pid})")
        print()

        # Give it a moment to initialize
        await asyncio.sleep(2)

        print("The server is now running and waiting for MCP protocol messages.")
        print("langchain_mcp_adapters would now:")
        print("  - Send 'initialize' request")
        print("  - Send 'list_tools' request")
        print("  - Receive tool definitions")
        print("  - Convert them to LangChain tools")
        print()

        # Cleanup
        process.terminate()
        await asyncio.sleep(0.5)
        process.kill()

        print("[OK] Server process stopped")

    except FileNotFoundError:
        print("[ERROR] npx not found - this would fail in your environment")
        print("   But in Docker, npx is installed and this works!")
    except Exception as e:
        print(f"[ERROR] Error: {e}")

    print()


def show_server_lifecycle():
    """Explain the server lifecycle."""
    print("=" * 70)
    print("MCP SERVER LIFECYCLE")
    print("=" * 70)
    print()

    print("┌─────────────────────────────────────────────────────────┐")
    print("│  When your agent starts                                 │")
    print("└─────────────────────────────────────────────────────────┘")
    print("         │")
    print("         ├─> tool_box() is called")
    print("         │")
    print("         ├─> _ensure_mcp_tools() is called")
    print("         │")
    print("         ├─> get_mcp_tools() is called")
    print("         │")
    print("         ├─> load_mcp_tools_from_config() is called")
    print("         │")
    print("         ├─> For each server in config:")
    print("         │   │")
    print("         │   ├─> langchain_mcp_adapters.load_mcp_tools()")
    print("         │   │   │")
    print("         │   │   ├─> Spawns subprocess: npx -y @langgpt/arxiv-paper-mcp")
    print("         │   │   │")
    print("         │   │   ├─> Server starts and listens on stdin")
    print("         │   │   │")
    print("         │   │   ├─> Sends MCP 'initialize' request")
    print("         │   │   │")
    print("         │   │   ├─> Sends MCP 'list_tools' request")
    print("         │   │   │")
    print("         │   │   ├─> Receives tool list from server")
    print("         │   │   │")
    print("         │   │   └─> Converts to LangChain tools")
    print("         │   │")
    print("         │   └─> Returns tools array")
    print("         │")
    print("         └─> All tools cached in _mcp_tools global variable")
    print()
    print("┌─────────────────────────────────────────────────────────┐")
    print("│  When your agent uses a tool (e.g., search_arxiv)      │")
    print("└─────────────────────────────────────────────────────────┘")
    print("         │")
    print("         ├─> Tool's _arun() method is called")
    print("         │")
    print("         ├─> Sends MCP 'call_tool' request to server")
    print("         │")
    print("         ├─> Server process executes the tool")
    print("         │")
    print("         ├─> Server returns result via stdout")
    print("         │")
    print("         └─> Result returned to agent")
    print()

    print("[NOTE] Server stays alive during the entire session!")
    print("   The subprocess keeps running until the agent shuts down.")
    print()


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("MCP SERVER PROCESS DEMONSTRATION")
    print("=" * 70)
    print()

    show_config()
    show_server_lifecycle()

    # Only run the actual demo if user wants
    print("=" * 70)
    print("Want to see a live demonstration?")
    print("=" * 70)
    print()
    print("Run this to see the actual MCP servers start:")
    print("  python -m agent.tool.mcp.mcp_client")
    print()
    print("Or run the async demo:")
    print("  python scripts/show_mcp_process.py --demo")
    print()

    import sys
    if '--demo' in sys.argv:
        asyncio.run(demonstrate_server_startup())
