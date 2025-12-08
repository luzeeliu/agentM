#!/usr/bin/env python
"""
Test script to verify MCP server and LangGraph integration locally.
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_mcp_tools_discovery():
    """Test 1: Verify MCP tools can be discovered from the server"""
    print("=" * 60)
    print("TEST 1: MCP Tools Discovery")
    print("=" * 60)

    from agent.MCP.mcp_adaptor import build_langchain_tools_from_mcp

    mcp_command = os.getenv("MCP_COMMAND")
    print(f"MCP_COMMAND: {mcp_command}\n")

    try:
        tools = build_langchain_tools_from_mcp(mcp_command)
        print(f"✓ Successfully discovered {len(tools)} MCP tools:\n")

        for tool in tools:
            print(f"  - {tool.name}")
            print(f"    Description: {tool.description}\n")

        return tools
    except Exception as e:
        print(f"✗ Error discovering MCP tools: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_mcp_tool_execution(tools):
    """Test 2: Execute a simple search using MCP tool"""
    print("\n" + "=" * 60)
    print("TEST 2: MCP Tool Execution")
    print("=" * 60)

    if not tools:
        print("✗ No tools available to test")
        return

    # Test DuckDuckGo search
    ddg_tool = next((t for t in tools if "duckduckgo" in t.name.lower()), None)

    if not ddg_tool:
        print("✗ DuckDuckGo tool not found")
        return

    print(f"Testing tool: {ddg_tool.name}\n")

    try:
        import json
        test_query = {"query": "Python programming", "max_results": 2}
        args_json = json.dumps(test_query)

        print(f"Input: {test_query}")
        result = ddg_tool.func(args_json)
        print(f"\n✓ Tool executed successfully!")
        print(f"Result type: {type(result)}")
        print(f"Result: {result}\n")

    except Exception as e:
        print(f"✗ Error executing tool: {e}")
        import traceback
        traceback.print_exc()

def test_langgraph_integration():
    """Test 3: Test full LangGraph agent with MCP tools"""
    print("\n" + "=" * 60)
    print("TEST 3: LangGraph Agent Integration")
    print("=" * 60)

    try:
        from agent.agent_runner import compile_app, initialize

        # Initialize services (RAG, etc.)
        initialize()

        app = compile_app()
        print("✓ LangGraph app compiled successfully")
        print(f"  Nodes: {list(app.get_graph().nodes.keys())}")
        print(f"  Entry point: agent")
        print(f"  Tool node configured with MCP tools\n")

        # Test a simple query
        print("Testing with query: 'What is Python?'\n")

        from agent.graph_state import GraphState
        init_state: GraphState = {
            "query": "What is Python?",
            "facts": [],
            "message": [],
            "user_id": "test_user"
        }

        result = app.invoke(init_state)

        print("✓ Agent execution completed!")
        print(f"\nFinal output: {result.get('output', 'No output')}")
        print(f"Facts collected: {len(result.get('facts', []))}")
        print(f"Messages: {len(result.get('message', []))}")

    except Exception as e:
        print(f"✗ Error in LangGraph integration: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " MCP LOCAL TESTING SUITE ".center(58) + "║")
    print("╚" + "=" * 58 + "╝")
    print("\n")

    # Test 1: Discover MCP tools
    tools = test_mcp_tools_discovery()

    if tools:
        # Test 2: Execute a tool
        test_mcp_tool_execution(tools)

        # Test 3: Test LangGraph integration
        test_langgraph_integration()

    print("\n" + "=" * 60)
    print("Testing Complete")
    print("=" * 60 + "\n")
