import os
from pathlib import Path
import dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from typing import Any
import json

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from .graph_state import GraphState
from .tool.tool_box import tool_box

dotenv.load_dotenv()

system_prompt_path = Path(__file__).parent / "systemprompt.md"
system_prompt = system_prompt_path.read_text(encoding="utf-8") if system_prompt_path.exists() else ""


based_llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0,
        google_api_key=os.environ["GEMINI_API_KEY"],
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
            normalized_output = _flatten_content(response.content)
            # go generate part add wrapper fot gemini output
            # here we dont need to extract images only when we need show it in UI
            """
            # Attempt to parse JSON payload from RAG tool to extract images
            # make gemini see image in finally for output
            try:
                parsed = json.loads(normalized_output)
                if isinstance(parsed, list):
                    image_urls = []
                    for item in parsed:
                        for img in item.get("images", []) if isinstance(item, dict) else []:
                            url = img.get("data_url") or img.get("url")
                            if url:
                                image_urls.append(url)
                    if image_urls:
                        new_state["images"] = image_urls
            except Exception:
                pass
            """
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

