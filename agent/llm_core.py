import os
from pathlib import Path
import dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from typing import Any
from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from .graph_state import PlannerState
from .memory.mem0 import Mem0Memory
from .planner_tool.delegate import DelegateTool

dotenv.load_dotenv()

system_prompt_path = Path(__file__).parent / "systemprompt.md"
system_prompt_raw = system_prompt_path.read_text(encoding="utf-8") if system_prompt_path.exists() else ""

"""
based_llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash", 
        temperature=0,
        google_api_key=os.environ["GEMINI_API_KEY"],
    )
"""
based_llm = ChatDeepSeek(
    model="deepseek-chat",
    temperature=0,
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url=os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com"),
)



def _flatten_content(content: Any) -> str:
    """
    Gemini responses may return either a plain string or a structured list of blocks.
    Convert anything non-string into a readable string to satisfy downstream schemas.
    """
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        pieces = []
        for block in content:
            if isinstance(block, dict):
                block_type = block.get("type")
                if block_type == "text":
                    pieces.append(block.get("text", ""))
                else:
                    pieces.append(str(block))
            else:
                pieces.append(str(block))
        return "\n".join(piece for piece in pieces if piece).strip()

    return str(content)

def get_planner_tools():
    """
    Returns a reduced set of tools for the planner.
    """
    return [DelegateTool()]

def agent(state: PlannerState) -> PlannerState:
    messages = state.get("message", [])
    user_id = state.get("user_id", "default_user")
    query = state.get("query", "")

    # Initialize memory
    memory_client = None
    long_memory_context = ""
    short_memory_context = ""
    try:
        memory_client = Mem0Memory(user_id=user_id)
        relevant_Lmemories = memory_client.search(query)
        if relevant_Lmemories:
            # Extract text from memory results
            # Results structure: {'results': [{'text': '...', ...}, ...]} or [{'text': '...', ...}, ...]
            mem_list = relevant_Lmemories.get('results', []) if isinstance(relevant_Lmemories, dict) else relevant_Lmemories
            if mem_list:
                memory_texts = [m['memory'] for m in mem_list if 'memory' in m]
                if memory_texts:
                    long_memory_context = """
                    ## Context from Previous Interactions\n
                    The following facts are remembered from previous conversations which match this user personlity. 
                    Use them to personalize your response.\n""" + "\n".join([f"- {text}" for text in memory_texts]) + "\n\n"
                    print(f"[agent] Found {len(memory_texts)} relevant memories")
                    print(f"[agent] Memory context:\n{long_memory_context}")

        relevant_Smemories = memory_client.search(query, run_id=state.get("session_id", "default_session"))
        if relevant_Smemories:
            # Extract text from memory results
            # Results structure: {'results': [{'text': '...', ...}, ...]} or [{'text': '...', ...}, ...]
            mem_list = relevant_Smemories.get('results', []) if isinstance(relevant_Smemories, dict) else relevant_Smemories
            if mem_list:
                memory_texts = [m['memory'] for m in mem_list if 'memory' in m]
                if memory_texts:
                    short_memory_context = """
                    ## Context from Previous Interactions\n
                    The following facts are remembered from previous conversations with this current chat memory. 
                    Use them to personalize your response.\n""" + "\n".join([f"- {text}" for text in memory_texts]) + "\n\n"
                    print(f"[agent] Found {len(memory_texts)} relevant memories")
                    print(f"[agent] Memory context:\n{short_memory_context}")

    except Exception as e:
        print(f"[agent] Memory initialization or search failed: {repr(e)}")

    # Always fall back to the base system prompt; append memory context when available.
    current_system_prompt = system_prompt_raw + long_memory_context + short_memory_context
        
    # [Optimization] We no longer dump all state['facts'] into the prompt.
    # Relevant facts are already retrieved via memory_client.search(query) above.
    # This prevents context window explosion.

    if not messages:
        if query:
            messages = [HumanMessage(content=query)]

    if not messages:
        return {**state, "message": []}
    
    
    if not isinstance(messages[0], SystemMessage) and current_system_prompt:
        messages = [SystemMessage(content=current_system_prompt)] + messages

    try:
        tools = get_planner_tools()
        base = based_llm
        llm = base.bind_tools(tools) if tools else base

        print(f"[agent] Invoking LLM with {len(messages)} messages")
        response = llm.invoke(messages)
        print(f"[agent] LLM response received: {type(response).__name__}")

        has_tool = bool(getattr(response, "tool_calls", None))
        print(f"[agent] tool_calls={has_tool}")

        if has_tool:
            print(f"[agent] Tool calls: {[tc.get('name') for tc in response.tool_calls]}")

        new_messages = messages + [response]
        new_state = {**state, "message": new_messages}
        if not has_tool and isinstance(response, AIMessage):
            normalized_output = _flatten_content(response.content)
            new_state["output"] = normalized_output
            print(f"[agent] Setting output: {normalized_output[:100]}...")
            
            # Save interaction to memory
            if memory_client:
                update_mem = [
                    {
                        "role": "user",
                        "content": query
                    },
                    {
                        "role": "assistant",
                        "content": normalized_output
                    }
                ]
                try:
                    memory_client.add(messages=update_mem)  # Save last user and AI messages
                    # save short term memory as well
                    memory_client.add(messages=update_mem, session_id=state.get("session_id", "default_session"), infer=False)
                    print(f"[agent] Saved interaction to memory")
                except Exception as e:
                    print(f"[agent] Failed to save interaction to memory: {repr(e)}")

        return new_state
    except Exception as e:
        import traceback
        print(f"[agent] ERROR: {e}")
        traceback.print_exc()
        error_msg = f"I encountered an error: {str(e)}. Please try again or ask a different question."
        fallback = AIMessage(content=error_msg)
        return {**state, "message": messages + [fallback], "output": error_msg}
