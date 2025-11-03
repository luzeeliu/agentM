#!/usr/bin/env python3
"""
Test script to verify MCP tools can be loaded inside Docker container.
Run this inside the Docker container to verify MCP integration.
"""
import sys
import os

# Add the project root to sys.path
sys.path.insert(0, '/app')

def test_mcp_client():
    """Test MCP client can load tools."""
    print("=" * 60)
    print("Testing MCP Client Integration")
    print("=" * 60)

    try:
        from agent.tool.mcp.mcp_client import get_mcp_tools

        print("\n[1/3] Loading MCP tools...")
        tools = get_mcp_tools()

        print(f"\n[2/3] Successfully loaded {len(tools)} MCP tools")

        print(f"\n[3/3] Tool details:")
        for i, tool in enumerate(tools, 1):
            print(f"  {i}. {tool.name}")
            if hasattr(tool, 'description') and tool.description:
                desc = tool.description[:80] + "..." if len(tool.description) > 80 else tool.description
                print(f"     Description: {desc}")

        print("\n" + "=" * 60)
        print("✅ MCP Integration Test: PASSED")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n❌ MCP Integration Test: FAILED")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tool_box():
    """Test that tool_box includes MCP tools."""
    print("\n" + "=" * 60)
    print("Testing Tool Box Integration")
    print("=" * 60)

    try:
        from agent.tool.tool_box import tool_box

        print("\n[1/2] Loading tool box...")
        tools = tool_box()

        print(f"\n[2/2] Tool box contains {len(tools)} total tools")

        mcp_tool_count = 0
        print("\nAll tools in tool box:")
        for i, tool in enumerate(tools, 1):
            print(f"  {i}. {tool.name}")
            # Count MCP tools (they typically have different naming patterns)
            if any(keyword in tool.name.lower() for keyword in ['arxiv', 'search', 'paper']):
                mcp_tool_count += 1

        print(f"\nEstimated MCP tools: {mcp_tool_count}")

        print("\n" + "=" * 60)
        print("✅ Tool Box Integration Test: PASSED")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n❌ Tool Box Integration Test: FAILED")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_package_versions():
    """Check package versions for compatibility."""
    print("=" * 60)
    print("Package Version Check")
    print("=" * 60)

    try:
        import pydantic
        print(f"Pydantic version: {pydantic.__version__}")

        version = tuple(map(int, pydantic.__version__.split('.')[:2]))
        if version < (2, 10):
            print(f"[WARN] Pydantic {pydantic.__version__} might be incompatible")
            print(f"       MCP requires Pydantic >= 2.10.0")
            return False
        else:
            print("[OK] Pydantic version is compatible")
            return True
    except Exception as e:
        print(f"[ERROR] Could not check Pydantic version: {e}")
        return False


if __name__ == "__main__":
    print("\n[Docker MCP Integration Test Suite]\n")

    version_ok = check_package_versions()
    print()

    test1_passed = test_mcp_client()
    test2_passed = test_tool_box()

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Version Check:   {'[OK] PASSED' if version_ok else '[ERROR] FAILED'}")
    print(f"MCP Client Test: {'[OK] PASSED' if test1_passed else '[ERROR] FAILED'}")
    print(f"Tool Box Test:   {'[OK] PASSED' if test2_passed else '[ERROR] FAILED'}")
    print("=" * 60)

    sys.exit(0 if (version_ok and test1_passed and test2_passed) else 1)
