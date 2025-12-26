from .memory.mem0 import Mem0Memory

mem_client = Mem0Memory(user_id="default_user")
mem_client.clear_short_term_memory(session_id="default_session")

try:
    result = mem_client.search(
        query="what is my previous questions and your answers?",
        run_id="default_session",
    )
except AssertionError as err:
    # FAISS raises when the index dimension does not match the embedder output.
    print(
        "FAISS search failed (likely embedding dimension mismatch). "
        "Delete memory_cache/mem0_store/mem0_faiss.* to rebuild the index "
        "after updating embedding_model_dims."
    )
    raise err

memories = result.get("results", []) if isinstance(result, dict) else result or []
text_blocks = [m["memory"] for m in memories if isinstance(m, dict) and m.get("memory")]
texts = "\n".join(f"- {t}" for t in text_blocks)

print("Cleared short-term memory. Current memories:")
print(texts if texts else "No memories found.")
