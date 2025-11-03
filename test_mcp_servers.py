"""Test script to verify MCP servers are working"""
import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def test_server(name: str, command: str, args: list):
    """Test a single MCP server"""
    print(f"\n{'='*60}")
    print(f"Testing {name} server...")
    print(f"Command: {command} {' '.join(args)}")
    print(f"{'='*60}")

    try:
        server_params = StdioServerParameters(
            command=command,
            args=args
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # List available tools
                tools = await session.list_tools()
                print(f"\n✓ Server connected successfully!")
                print(f"\nAvailable tools ({len(tools.tools)}):")
                for tool in tools.tools:
                    print(f"  - {tool.name}: {tool.description or 'No description'}")

                return True

    except Exception as e:
        print(f"\n✗ Error connecting to {name} server:")
        print(f"  {type(e).__name__}: {e}")
        return False

async def main():
    # Load config
    with open(r"E:\AgentM\agent\tool\mcp\mcp-server-config.json", "r") as f:
        config = json.load(f)

    print("MCP Servers Configuration Test")
    print("="*60)

    results = {}
    for server_name, server_config in config["mcpServers"].items():
        success = await test_server(
            server_name,
            server_config["command"],
            server_config["args"]
        )
        results[server_name] = success

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for server_name, success in results.items():
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status} - {server_name}")

    all_passed = all(results.values())
    print(f"\n{'='*60}")
    if all_passed:
        print("✓ All servers are working correctly!")
    else:
        print("✗ Some servers failed. Check the errors above.")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    asyncio.run(main())
