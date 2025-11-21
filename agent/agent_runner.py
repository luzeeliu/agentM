import dotenv
import json
from langgraph.graph import StateGraph
from langgraph.constants import END
from .graph_state import GraphState
from langchain_core.messages import AIMessage, ToolMessage
from .llm_core import agent
from .tool.tool_box import tool_box
from .tool.local_search.RAG.rag_main import warmup_vanilla_rag


dotenv.load_dotenv()
warmup_vanilla_rag(auto_build=True)

# the agent will include planner, tool, knn intent, generate
def check_tool_call(state: GraphState):
    messages = state.get("message", [])
    if messages and isinstance(messages[-1], AIMessage):
        return bool(getattr(messages[-1], "tool_calls", None))
    return False

# Cache tools to avoid reloading on every call
_tools_cache = None

def _get_tools():
    """Lazy initialization of tools."""
    global _tools_cache
    if _tools_cache is None:
        _tools_cache = {tool.name: tool for tool in tool_box()}
    return _tools_cache

# the tool_wrapper manually executes tools without using ToolNode
async def tool_wrapper(state: GraphState):
    """
    Async wrapper to execute tool calls from the AI message.
    Calls tools directly to avoid LangGraph configuration issues with ToolNode.
    """
    messages = state.get("message", [])

    if not messages:
        return state

    last_message = messages[-1]

    # Check if the last message has tool calls
    if not isinstance(last_message, AIMessage) or not hasattr(last_message, 'tool_calls'):
        return state

    tool_calls = getattr(last_message, 'tool_calls', [])
    if not tool_calls:
        return state

    # Get available tools
    tools = _get_tools()

    # Execute each tool call
    tool_messages = []
    for tool_call in tool_calls:
        tool_name = tool_call.get('name')
        tool_args = tool_call.get('args', {})
        tool_call_id = tool_call.get('id', '')

        print(f"[tool_wrapper] Executing tool: {tool_name} with args: {tool_args}")

        if tool_name not in tools:
            error_msg = f"Tool '{tool_name}' not found. Available tools: {list(tools.keys())}"
            print(f"[tool_wrapper] Error: {error_msg}")
            tool_messages.append(ToolMessage(
                content=error_msg,
                tool_call_id=tool_call_id,
                name=tool_name
            ))
            continue

        tool = tools[tool_name]

        try:
            # Try different invocation methods based on tool type
            result = None

            # Method 1: Try ainvoke (for MCP tools and modern LangChain tools)
            if hasattr(tool, 'ainvoke'):
                try:
                    result = await tool.ainvoke(tool_args)
                except TypeError as e:
                    # MCP tools might need config parameter
                    if 'config' in str(e):
                        from langchain_core.runnables import RunnableConfig
                        config = RunnableConfig()
                        result = await tool.ainvoke(tool_args, config=config)
                    else:
                        raise

            # Method 2: Try _arun (for custom async tools)
            elif hasattr(tool, '_arun'):
                result = await tool._arun(**tool_args)

            # Method 3: Fall back to sync invoke
            elif hasattr(tool, 'invoke'):
                result = tool.invoke(tool_args)

            # Method 4: Fall back to sync _run
            elif hasattr(tool, '_run'):
                result = tool._run(**tool_args)
            else:
                raise ValueError(f"Tool {tool_name} has no invocation method")

            print(f"[tool_wrapper] Tool {tool_name} result: {str(result)[:200]}...")

            tool_messages.append(ToolMessage(
                content=str(result),
                tool_call_id=tool_call_id,
                name=tool_name
            ))
        except Exception as e:
            error_msg = f"Error executing tool '{tool_name}': {str(e)}"
            print(f"[tool_wrapper] {error_msg}")
            import traceback
            traceback.print_exc()

            tool_messages.append(ToolMessage(
                content=error_msg,
                tool_call_id=tool_call_id,
                name=tool_name
            ))

    # Return updated state with tool results
    updated_messages = messages + tool_messages
    return {
        **state,
        "message": updated_messages
    }

def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("agent", agent)
    graph.add_node("tool", tool_wrapper)
    # define start
    graph.set_entry_point("agent")
    # if the last AI message has tool_calls, go to tools else end
    graph.add_conditional_edges(
        "agent",
        check_tool_call,
        {True: "tool", False: END},
    )
    # after tool results, return to agent to continue the loop
    graph.add_edge("tool", "agent")
    return graph

def compile_app():
    return build_graph().compile()

def run_query(query: str, user_id: str = "default_user") -> GraphState:
    app = compile_app()
    init: GraphState = {"query": query, "facts": [], "message": [], "user_id": user_id}
    final = app.invoke(init)
    return final

