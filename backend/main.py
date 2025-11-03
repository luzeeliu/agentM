import base64
import os
from typing import Optional, List, Any, Dict

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Import the agent runner utilities
import sys
import traceback

try:
    from agent.agent_runner import run_query, compile_app
    from langchain_core.messages import HumanMessage
    print("[backend] Successfully imported agent modules", file=sys.stderr)
except Exception as e:
    # Lazy/import-time errors will surface on first request; keep module import lightweight.
    run_query = None  # type: ignore
    compile_app = None  # type: ignore
    HumanMessage = None  # type: ignore
    print(f"[backend] Import error: {e}", file=sys.stderr)
    print("[backend] Full traceback:", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)


class ChatResponse(BaseModel):
    output: Optional[str] = None
    facts: Optional[List[str]] = None
    messages: Optional[List[Any]] = None


def image_to_data_url(file_bytes: bytes, filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }
    mime = mime_map.get(ext, "application/octet-stream")
    b64 = base64.b64encode(file_bytes).decode("utf-8")
    return f"data:{mime};base64,{b64}"


app = FastAPI(title="AgentM Backend", version="0.1.0")

# Allow local development from file:// or a dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    query: Optional[str] = Form(default=None),
    user_id: str = Form(default="default_user"),
    image: Optional[UploadFile] = File(default=None),
):
    if compile_app is None:
        print("[backend] compile_app is None - check import errors above", file=sys.stderr)
        raise RuntimeError(
            "Agent not available. Check Docker logs for import errors. "
            "Common issues: missing GOOGLE_API_KEY environment variable or dependency installation failures."
        )

    app_graph = compile_app()

    # Build initial GraphState
    init_state = {"facts": [], "message": [], "user_id": user_id}

    # If we have an image, prepare a multimodal HumanMessage
    if image is not None:
        data = await image.read()
        data_url = image_to_data_url(data, image.filename or "upload")
        parts = []
        if query:
            parts.append({"type": "text", "text": query})
        parts.append({"type": "image_url", "image_url": data_url})
        if HumanMessage is None:
            raise RuntimeError("LangChain messages are unavailable. Check your environment.")
        init_state["message"] = [HumanMessage(content=parts)]
    else:
        # Fallback to text-only query
        init_state["query"] = query or ""

    final = await app_graph.ainvoke(init_state)
    # final is a GraphState TypedDict

    # Extract only human and AI messages (not tool calls) for cleaner output
    messages = final.get("message", [])
    clean_messages = []
    for msg in messages:
        msg_type = type(msg).__name__
        if msg_type in ["HumanMessage", "AIMessage"]:
            # Only include if it has actual content (not just tool calls)
            if hasattr(msg, 'content') and msg.content and not getattr(msg, 'tool_calls', None):
                clean_messages.append(f"{msg_type}: {msg.content}")

    return ChatResponse(
        output=final.get("output"),
        facts=final.get("facts"),
        messages=clean_messages,
    )

# Serve frontend at root
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
