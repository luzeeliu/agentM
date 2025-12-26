import asyncio
import dotenv
import json
from langgraph.graph import StateGraph
from langgraph.constants import END
from .graph_state import PlannerState
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage
from .llm_core import agent
from .tools_agent.toolagent_runner import compile_app as compile_tool_agent
import time
from .log.logger import logger
from .memory.mem0 import Mem0Memory

dotenv.load_dotenv()

# Pre-compile the tool agent app
tool_app = compile_tool_agent()

async def tool_agent_node(state: PlannerState):
    """
    Node that delegates tool execution and reasoning to the tool agent.
    Supports PARALLEL execution of multiple delegation requests.
    """
    print("[planner] Delegating to tool agent...")
    messages = state.get("message", [])
    if not messages:
        return state

    last_message = messages[-1]
    
    # Check if the transition was triggered by the DelegateTool
    if isinstance(last_message, AIMessage) and getattr(last_message, "tool_calls", None):
        tasks = []
        tool_call_ids = []
        
        # Initialize Memory Client
        memory_client = None
        try:
            user_id = state.get("user_id", "default_user")
            memory_client = Mem0Memory(user_id=user_id)
        except Exception as e:
            print(f"[agent_runner] Warning: Failed to initialize memory client: {e}")
        
        # 1. Collect all delegation tasks
        for tool_call in last_message.tool_calls:
            if tool_call["name"] == "delegate_to_tool_agent":
                # Extract task from the delegate tool arguments
                args = tool_call["args"]
                task = args.get("task", "")
                context = args.get("context", "")
                full_instruction = f"Task: {task}\nContext: {context}"
                print(f"[planner] Preparing parallel delegate: {task}...")
                
                # Create isolated input for Tool Agent
                tool_agent_input = {
                    "query": state.get("query"),
                    "user_id": state.get("user_id"),
                    "message": [HumanMessage(content=f"You are the Specialist Tool Agent. Please perform this task:\n{full_instruction}")]
                }
                
                # Add coroutine to list
                # add all task in a list then run them in parallel
                tasks.append(tool_app.ainvoke(tool_agent_input))
                tool_call_ids.append(tool_call)

        if tasks:
            print(f"[planner] Executing {len(tasks)} delegation tasks in parallel...")
            # 2. Execute all tasks concurrently
            results = await asyncio.gather(*tasks)
            
            # 3. Process results
            new_tool_messages = []
            
            for i, result in enumerate(results):
                tool_call = tool_call_ids[i]
                
                # Extract summary/process robustly (handles string or JSON output)
                content_to_report = result.get("output", "")
                print(f"[planner_runner] =======Tool Agent summary: {content_to_report}=======")

                new_tool_messages.append(ToolMessage(
                    content=f"Tool Agent Report:\n{content_to_report}",
                    tool_call_id=tool_call["id"],
                    name=tool_call["name"]
                ))

            updated_state = state.copy()          
            # Append all tool messages
            updated_state["message"] = messages + new_tool_messages
            
            print(f"[agent_runner] Parallel execution complete. {len(new_tool_messages)} reports received.")
            return updated_state

    return state

def initialize():
# ... (rest of the file)
    """
    Initialize the agent services (RAG, etc.).
    Returns the warmup task if running in an event loop, or None if synchronous.
    """
    from .tools_agent.tools.local_search.RAG.rag_main import warmup_vanilla_rag
    logger.info("[agent_runner] Initializing RAG service...")
    start_time = time.time()
    task = warmup_vanilla_rag(auto_build=True)
    
    # If synchronous (task is None), we can log completion now
    if task is None:
        logger.info(f"[agent_runner] RAG service warmup took {time.time() - start_time:.2f} seconds")
    
    return task

def check_tool_call(state: PlannerState):
    messages = state.get("message", [])
    if messages and isinstance(messages[-1], AIMessage):
        return bool(getattr(messages[-1], "tool_calls", None))
    return False

def build_graph():
    graph = StateGraph(PlannerState)
    graph.add_node("agent", agent)
    graph.add_node("tool_agent", tool_agent_node)
    # define start
    graph.set_entry_point("agent")
    # if the last AI message has tool_calls, go to tools else end
    graph.add_conditional_edges(
        "agent",
        check_tool_call,
        {True: "tool_agent", False: END},
    )
    # after tool agent results, return to agent to continue the loop
    graph.add_edge("tool_agent", "agent")
    return graph


def compile_app():
    print("[planner] current in the planner agent")
    return build_graph().compile()

def run_query(query: str, user_id: str = "default_user", session_id: str = "default_session") -> PlannerState:
    app = compile_app()
    init: PlannerState = {"query": query, "facts": [], "message": [], "user_id": user_id, "session_id": session_id}
    # tool_wrapper is async, so invoke the graph via the async API even in sync contexts
    return asyncio.run(app.ainvoke(init))

