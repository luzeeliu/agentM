import asyncio
import json
import os
import re
from dataclasses import dataclass
from threading import Thread
from pathlib import Path
import dotenv
from langchain_community.chat_models import ChatOllama

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from .graph_state import GraphState
from .tool.tool_box import tool_box

dotenv.load_dotenv()

system_prompt_path = Path(__file__).parent / "systemprompt.md"
system_prompt = system_prompt_path.read_text(encoding="utf-8") if system_prompt_path.exists() else ""


ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
# For smaller models (3b-7b), use lower temperature and repeat_penalty
# Lightweight options: qwen2.5:3b, phi3:mini, gemma2:2b
based_llm = ChatOllama(
    model=os.getenv("OLLAMA_MODEL", "qwen2.5:3b"),
    temperature=0.1,  # Low but not zero helps with consistency
    base_url=ollama_base_url,
    # Additional options for better tool calling with small models
    num_ctx=4096,  # Reasonable context window
    repeat_penalty=1.1,  # Prevent repetitive outputs
)

# Primary pattern: expects closing tag
TOOL_CALL_PATTERN = re.compile(
    r"<tool_call\s+name=[\"']?(?P<name>[\w\-_]+)[\"']?\s*>\s*(?P<args>\{.*?\})\s*</tool_call>",
    re.DOTALL | re.IGNORECASE,
)

# Fallback pattern: works without closing tag (for small models)
TOOL_CALL_PATTERN_FALLBACK = re.compile(
    r"<tool_call\s+name=[\"']?(?P<name>[\w\-_]+)[\"']?\s*>\s*(?P<args>\{[^<]*?\})",
    re.DOTALL | re.IGNORECASE,
)
MANUAL_TOOL_INSTRUCTIONS = (
    "You have access to tools. To use a tool, write:\n"
    '<tool_call name="tool_name">{"arg": "value"}</tool_call>\n'
    "Then STOP and wait for the result.\n\n"
    "Important:\n"
    "- Use exact tool names\n"
    "- Put valid JSON inside tags\n"
    "- One tool per tag\n"
    "- Wait for 'Tool result for tool_name:' before continuing\n\n"
    "Example:\n"
    '<tool_call name="web_search">{"query": "weather today"}</tool_call>'
)


@dataclass
class ManualToolCall:
    name: str
    args: dict


def _extract_manual_tool_calls(content: str) -> list[ManualToolCall]:
    if not content:
        return []

    tool_calls: list[ManualToolCall] = []

    # Debug: Check if there are any tool_call tags at all
    if "<tool_call" in content.lower():
        print(f"[agent] Found <tool_call tag in response, attempting to parse...")
        # Show the relevant part
        start_idx = content.lower().find("<tool_call")
        snippet = content[start_idx:start_idx+150]
        print(f"[agent] Tool call snippet: {snippet}")

    # Try primary pattern first (with closing tag)
    matches = list(TOOL_CALL_PATTERN.finditer(content))

    # If no matches, try fallback pattern (without closing tag)
    if not matches:
        print(f"[agent] No matches with primary pattern, trying fallback pattern...")
        matches = list(TOOL_CALL_PATTERN_FALLBACK.finditer(content))
        if matches:
            print(f"[agent] Fallback pattern matched! (model forgot closing tag)")

    for match in matches:
        raw_name = match.group("name").strip()
        raw_args = match.group("args").strip()
        print(f"[agent] Matched tool: name='{raw_name}', args='{raw_args[:50]}...'")

        if not raw_name:
            continue
        try:
            parsed_args = json.loads(raw_args) if raw_args else {}
        except json.JSONDecodeError as exc:
            print(f"[agent] Failed to parse tool args for {raw_name}: {exc}")
            print(f"[agent] Raw args: {raw_args}")
            continue
        if not isinstance(parsed_args, dict):
            parsed_args = {"input": parsed_args}
        tool_calls.append(ManualToolCall(name=raw_name, args=parsed_args))
    return tool_calls


def _run_coroutine_sync(coroutine):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        result_container: dict[str, object] = {}

        # build new event loop run in new thread
        def runner():
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                result_container["result"] = new_loop.run_until_complete(coroutine)
            except Exception as err:  # pragma: no cover - defensive
                result_container["error"] = err
            finally:
                new_loop.close()

        thread = Thread(target=runner, daemon=True)
        thread.start()
        thread.join()
        if "error" in result_container:
            raise result_container["error"]  # type: ignore[no-any-return]
        return result_container.get("result")

    return asyncio.run(coroutine)


def _invoke_tool_sync(tool, args: dict):
    try:
        # sync tool call
        return tool.invoke(args)
    except Exception as exc:
        needs_async = "does not support sync invocation" in str(exc).lower()
        if not needs_async and not hasattr(tool, "ainvoke") and not hasattr(tool, "_arun"):
            raise

        async def _call_async():
            if hasattr(tool, "ainvoke"):
                try:
                    # for new-style async langchain tools
                    return await tool.ainvoke(args)
                except TypeError as err:
                    # for old-style async langchain tools 
                    if "config" in str(err):
                        try:
                            from langchain_core.runnables import RunnableConfig  # type: ignore
                        except ImportError as import_err:
                            raise err from import_err
                        config = RunnableConfig()
                        return await tool.ainvoke(args, config=config)
                    raise
            if hasattr(tool, "_arun"):
                return await tool._arun(**args)
            raise ValueError(f"Tool '{getattr(tool, 'name', '<unknown>')}' has no async invocation method.")

        return _run_coroutine_sync(_call_async())


def _tool_result_message(tool_name: str, result: str | None):
    if isinstance(result, str):
        text_result = result
    else:
        try:
            text_result = json.dumps(result, ensure_ascii=False)
        except (TypeError, ValueError):
            text_result = str(result)
    return HumanMessage(
        content=f"Tool result for {tool_name}:\n{text_result}"
    )


def _dispatch_tool_calls(
    tool_calls: list[ManualToolCall],
    available_tools: dict[str, object],
) -> list:
    dispatched_messages = []
    for call in tool_calls:
        tool = available_tools.get(call.name)
        if tool is None:
            error_msg = f"Tool '{call.name}' is not available."
            print(f"[agent] {error_msg}")
            dispatched_messages.append(_tool_result_message(call.name, error_msg))
            continue
        try:
            print(f"[agent] Executing tool '{call.name}' with args {call.args}")
            result = _invoke_tool_sync(tool, call.args)
        except Exception as exc:
            error_msg = f"Tool '{call.name}' failed: {exc}"
            print(f"[agent] {error_msg}")
            dispatched_messages.append(_tool_result_message(call.name, error_msg))
            continue
        dispatched_messages.append(_tool_result_message(call.name, result))
    return dispatched_messages


def _build_tool_instructions(tools: list) -> str:
    """Build tool instructions with available tool list for small models."""
    tool_list = []
    for tool in tools[:10]:  # Limit to top 10 tools to save context
        name = getattr(tool, 'name', 'unknown')
        desc = getattr(tool, 'description', 'No description')
        # Truncate long descriptions
        if len(desc) > 100:
            desc = desc[:97] + "..."
        tool_list.append(f"  - {name}: {desc}")

    tools_section = "\n".join(tool_list) if tool_list else "  (no tools available)"

    return (
        f"{MANUAL_TOOL_INSTRUCTIONS}\n\n"
        f"Available tools:\n{tools_section}"
    )


def agent(state: GraphState) -> GraphState:
    messages = state.get("message", [])
    if not messages:
        q = state.get("query", "")
        if q:
            messages = [HumanMessage(content=q)]

    if not messages:
        return {**state, "message": []}

    # Get tools early to build instructions
    tools = tool_box()
    tool_lookup = {tool.name: tool for tool in tools}

    if system_prompt and not any(
        isinstance(msg, SystemMessage) and msg.content == system_prompt for msg in messages
    ):
        messages = [SystemMessage(content=system_prompt)] + messages

    # Build tool instructions with available tools list
    tool_instructions = _build_tool_instructions(tools)
    has_manual_instruction = any(
        isinstance(msg, SystemMessage) and MANUAL_TOOL_INSTRUCTIONS in msg.content
        for msg in messages
    )
    if not has_manual_instruction:
        insertion_index = 0
        while insertion_index < len(messages) and isinstance(messages[insertion_index], SystemMessage):
            insertion_index += 1
        messages = (
            messages[:insertion_index]
            + [SystemMessage(content=tool_instructions)]
            + messages[insertion_index:]
        )

    try:
        base = based_llm
        llm = base
        max_turns = 3  # Reduced for small models to prevent confusion

        print(f"[agent] Using manual tool dispatch with {len(tool_lookup)} tools (small model mode)")

        for turn in range(max_turns):
            print(f"[agent] Invoking LLM with {len(messages)} messages")
            response = llm.invoke(messages)
            print(f"[agent] LLM response received: {type(response).__name__}")

            manual_tool_calls = []
            if isinstance(response, AIMessage) and isinstance(response.content, str):
                # Debug: print the response content to see what the model generated
                print(f"[agent] Response content: {response.content[:200]}")
                manual_tool_calls = _extract_manual_tool_calls(response.content)
                print(f"[agent] Detected {len(manual_tool_calls)} manual tool calls")
                if len(manual_tool_calls) > 0:
                    for call in manual_tool_calls:
                        print(f"[agent]   - Tool: {call.name}, Args: {call.args}")

            messages.append(response)

            if manual_tool_calls:
                tool_messages = _dispatch_tool_calls(manual_tool_calls, tool_lookup)
                messages.extend(tool_messages)
                messages.append(
                    SystemMessage(
                        content="You have received tool results. Continue the conversation and provide the next response."
                    )
                )
                continue  # Ask the model to continue with tool results skip generation

            new_state = {**state, "message": messages}
            if isinstance(response, AIMessage):
                new_state["output"] = response.content
                print(f"[agent] Setting output: {response.content[:100]}...")
            return new_state

        print("[agent] Reached maximum tool-assisted turns without final response.")
        fail_msg = "I could not complete the task within the tool interaction limit."
        fallback = AIMessage(content=fail_msg)
        return {**state, "message": messages + [fallback], "output": fail_msg}
    except Exception as e:
        import traceback
        print(f"[agent] ERROR: {e}")
        traceback.print_exc()
        error_msg = f"I encountered an error: {str(e)}. Please try again or ask a different question."
        fallback = AIMessage(content=error_msg)
        return {**state, "message": messages + [fallback], "output": error_msg}
