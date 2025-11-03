import asyncio
import json
from pathlib import Path
from typing import List

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_mcp_adapters.sessions import StdioConnection



class CustomEncoder(json.JSONEncoder):
    """Custom JSON encoder for handling special types."""
    def default(self, obj):
        if hasattr(obj, '__dict__'):
            return obj.__dict__
        return super().default(obj)


def _load_mcp_config() -> dict:
    """Load MCP server configuration from mcp-server-config.json"""
    config_path = Path(__file__).with_name("mcp-server-config.json")
    if not config_path.exists():
        return {}

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"[mcp_client] Error decoding JSON from {config_path}")
        return {}


async def load_mcp_tools_from_config() -> List[BaseTool]:
    """
    Load all MCP tools from the configuration file using langchain_mcp_adapters.

    Returns:
        List of LangChain BaseTool instances from all configured MCP servers.
    """
    config = _load_mcp_config()
    mcp_servers = config.get("mcpServers", {})

    if not mcp_servers:
        print("[mcp_client] No MCP servers configured")
        return []

    all_tools: List[BaseTool] = []

    for server_name, server_config in mcp_servers.items():
        command = server_config.get("command")
        args = server_config.get("args", [])
        env = server_config.get("env")

        if not command:
            print(f"[mcp_client] Skipping {server_name}: no command specified")
            continue

        try:
            # Create StdioConnection for the MCP server
            connection: StdioConnection = {
                'transport': 'stdio',
                'command': command,
                'args': args,
            }

            # Add optional env if provided
            if env:
                connection['env'] = env

            print(f"[mcp_client] Loading tools from MCP server: {server_name}")

            # Use langchain_mcp_adapters to load tools
            tools = await load_mcp_tools(
                session=None,
                connection=connection,
                server_name=server_name
            )

            print(f"[mcp_client] Loaded {len(tools)} tools from {server_name}")
            all_tools.extend(tools)

        except Exception as e:
            print(f"[mcp_client] Error loading tools from {server_name}: {e}")
            import traceback
            traceback.print_exc()
            continue

    return all_tools


def get_mcp_tools() -> List[BaseTool]:
    """
    Synchronous wrapper to load MCP tools from config.

    Returns:
        List of LangChain BaseTool instances.
    """
    try:
        # Check if there's already a running event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're already in an async context, we need to run in a new thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, load_mcp_tools_from_config())
                return future.result()
        else:
            # No running loop, we can use asyncio.run
            return asyncio.run(load_mcp_tools_from_config())
    except RuntimeError:
        # No event loop exists, create one
        return asyncio.run(load_mcp_tools_from_config())
    except Exception as e:
        print(f"[mcp_client] Failed to load MCP tools: {e}")
        return []


# For testing purposes
if __name__ == "__main__":
    print("Testing MCP client...")
    tools = get_mcp_tools()
    print(f"\nLoaded {len(tools)} tools:")
    for tool in tools:
        print(f"  - {tool.name}: {tool.description}")
