#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to verify MCP configuration is loaded correctly with env var expansion.
"""
import os
import sys
from pathlib import Path

# Fix encoding on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set test env var if not already set
if "GEMINI_API_KEY" not in os.environ:
    os.environ["GEMINI_API_KEY"] = "test_key_12345"
    print("⚠️  GEMINI_API_KEY not found, using test value")

from agent.tool.mcp.mcp_server_config import load_mcp_server_configs


def test_config_loading():
    """Test that all MCP server configs load correctly."""
    print("🔍 Loading MCP server configurations...\n")

    try:
        configs = load_mcp_server_configs()

        if not configs:
            print("⚠️  No MCP servers configured")
            return True

        print(f"✅ Found {len(configs)} MCP server(s):\n")

        for config in configs:
            print(f"📦 {config.server_name}")
            print(f"   Command: {config.server_param.command}")
            print(f"   Args: {config.server_param.args}")

            if config.server_param.env:
                print(f"   Environment variables:")
                for key, value in config.server_param.env.items():
                    # Mask sensitive values
                    display_value = value if len(value) < 20 else f"{value[:10]}...{value[-5:]}"
                    # Check if env var was expanded
                    if value.startswith("${"):
                        print(f"      ❌ {key}: {value} (NOT EXPANDED!)")
                    else:
                        print(f"      ✅ {key}: {display_value}")

            if config.excluded_tools:
                print(f"   Excluded tools: {config.excluded_tools}")

            print()

        print("✅ All configurations loaded successfully!")
        return True

    except Exception as e:
        print(f"❌ Error loading configurations: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_config_loading()
    sys.exit(0 if success else 1)
