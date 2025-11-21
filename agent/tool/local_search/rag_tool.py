from __future__ import annotations

import asyncio
from typing import Optional, ClassVar

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from .RAG.rag_main import async_query_local_rag


class VanillaRAGInput(BaseModel):
    query: str = Field(..., description="Question or text to search against the local RAG cache")
    top_k: Optional[int] = Field(None, description="Number of chunks to return (defaults to tool setting)")


class VanillaRAGSearchTool(BaseTool):
    name: ClassVar[str] = "vanilla_rag_search"
    description: ClassVar[str] = (
        "Search the local demo FAISS cache built from out_shards and return the original chunks."
    )
    args_schema: ClassVar[type[BaseModel]] = VanillaRAGInput

    top_k: int = 3

    def _run(self, query: str, top_k: Optional[int] = None) -> str:
        return asyncio.run(self._arun(query, top_k))

    async def _arun(self, query: str, top_k: Optional[int] = None) -> str:  # type: ignore[override]
        results = await async_query_local_rag(query, top_k=top_k or self.top_k, auto_build=True)
        if not results:
            return "No relevant passages found in the local RAG cache."

        lines = [
            f"[score={r.get('score', 0):.3f}] {r.get('source','unknown')}: {r.get('content','')}"
            for r in results
        ]
        return "\n".join(lines)
