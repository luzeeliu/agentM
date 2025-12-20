import os
from pathlib import Path
import dotenv
from langchain_deepseek import ChatDeepSeek
from typing import Any
import json
# from langchain_community.chat_models import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from graph_state import GraphState
from tool.tool_box import tool_box

dotenv.load_dotenv()

system_prompt_path = Path(__file__).parent / "tool_systemprompt.md"
system_prompt = system_prompt_path.read_text(encoding="utf-8") if system_prompt_path.exists() else ""

# DeepSeek uses OpenAI-compatible API; pass api_key/base_url in model_kwargs to avoid payload errors
based_llm = ChatDeepSeek(
    model="deepseek-chat",
    temperature=0,
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url=os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com"),
)

"""
based_llm = ChatOllama(
    model=os.getenv("OLLAMA_MODEL", "deepseek:R1-8B"),
    temperature=0.1,  # Low but not zero helps with consistency
    base_url=ollama_base_url,
    # Additional options for better tool calling with small models
    num_ctx=4096,  # Reasonable context window
    repeat_penalty=1.1,  # Prevent repetitive outputs
)
"""

def agent(state: GraphState) -> GraphState:
    messages = state.get("message", [])
    if not messages:
        q = state.get("query", "")
        if q:
            messages = [HumanMessage(content=q)]

    if not messages:
        return {**state, "message": []}
    
    
    if not isinstance(messages[0], SystemMessage) and system_prompt:
        messages = [SystemMessage(content=system_prompt)] + messages

    try:
        tools = tool_box()
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
            normalized_output = response.content
            new_state["output"] = normalized_output
            print(f"[agent] Setting output: {normalized_output[:100]}...")
        return new_state
    except Exception as e:
        import traceback
        print(f"[agent] ERROR: {e}")
        traceback.print_exc()
        error_msg = f"I encountered an error: {str(e)}. Please try again or ask a different question."
        fallback = AIMessage(content=error_msg)
        return {**state, "message": messages + [fallback], "output": error_msg}
