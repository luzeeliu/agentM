import os
from pathlib import Path
import dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from .graph_state import GraphState
from .tool.tool_box import tool_box

dotenv.load_dotenv()

system_prompt_path = Path(__file__).parent / "systemprompt.md"
system_prompt = system_prompt_path.read_text(encoding="utf-8") if system_prompt_path.exists() else ""


based_llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        temperature=0,
        google_api_key=os.environ["GEMINI_API_KEY"],
    )

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
            new_state["output"] = response.content
            print(f"[agent] Setting output: {response.content[:100]}...")
        return new_state
    except Exception as e:
        import traceback
        print(f"[agent] ERROR: {e}")
        traceback.print_exc()
        error_msg = f"I encountered an error: {str(e)}. Please try again or ask a different question."
        fallback = AIMessage(content=error_msg)
        return {**state, "message": messages + [fallback], "output": error_msg}

