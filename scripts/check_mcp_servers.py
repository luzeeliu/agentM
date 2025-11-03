#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Health check script to verify MCP servers are accessible before starting the app.
This prevents timeout issues during initialization.
"""
import asyncio
import sys
from pathlib import Path

# Fix encoding on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.tool.mcp.mcp_server_config import load_mcp_server_configs
from agent.tool.mcp.mcp_tool import convert_mcp_tool_to_langchain_tool


async def check_all_servers():
    """Verify all configured MCP servers can be initialized."""
    configs = load_mcp_server_configs()

    if not configs:
        print("⚠️  No MCP servers configured")
        return True

    print(f"🔍 Checking {len(configs)} MCP server(s)...")

    failed = []
    for config in configs:
        try:
            print(f"  • {config.server_name}: ", end="", flush=True)
            toolkit = await asyncio.wait_for(
                convert_mcp_tool_to_langchain_tool(config, force_update=False),
                timeout=10.0
            )
            tool_count = len(toolkit.get_tools())
            print(f"✓ ({tool_count} tools)")
            await toolkit.close()
        except asyncio.TimeoutError:
            print("✗ TIMEOUT")
            failed.append(f"{config.server_name} (timeout)")
        except Exception as e:
            print(f"✗ ERROR: {e}")
            failed.append(f"{config.server_name} ({e})")

    if failed:
        print(f"\n❌ {len(failed)} server(s) failed:")
        for fail in failed:
            print(f"   - {fail}")
        return False

    print(f"\n✅ All MCP servers ready!")
    return True


if __name__ == "__main__":
    success = asyncio.run(check_all_servers())
    sys.exit(0 if success else 1)
