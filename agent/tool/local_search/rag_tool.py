from __future__ import annotations

import asyncio
from typing import Optional, ClassVar, List
import base64
from pathlib import Path
import json
import time

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from .RAG.rag_main import async_query_local_rag, _DEFAULT_SERVICE, logger
from .RAG.image_faiss_build import FaissImageStorage


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
        start_time = time.time()
        logger.info(f"[vanilla_rag_search] Processing query: '{query[:50]}...'")
        
        results = await async_query_local_rag(query, top_k=top_k or self.top_k, auto_build=True)
        
        query_time = time.time() - start_time
        logger.info(f"[vanilla_rag_search] Primary query took {query_time:.2f}s. Found {len(results)} results.")
        
        if not results:
            return "No relevant passages found in the local RAG cache."

        # Build payload with text hits and inline image data URLs for VLM consumption.
        payload = []
        image_search_start = time.time()
        for r in results:
            entry = {
                "score": r.get("score", 0.0),
                "source": r.get("source", "unknown"),
                "content": r.get("content", ""),
                "source_type": r.get("source_type"),
                "pdf_name": r.get("pdf_name"),
                "pdf_page": r.get("pdf_page"),
                "images": [],
            }
            
            if r.get("linked_images",[]):
            # add top-k images from cross-modal search for relevance
                image_searcher = _DEFAULT_SERVICE.image_vector_storage
                image_results = await image_searcher.query(text=query, top_k=top_k or self.top_k)
                for ir in image_results or []:
                    img_path = ir.get("image_path") or ir.get("source_path") or ""
                    if img_path:
                        data_url = self._encode_image_to_data_url(img_path)
                        entry["images"].append({"path": img_path, "data_url": data_url})

            payload.append(entry)
            
        logger.info(f"[vanilla_rag_search] Image enrichment took {time.time() - image_search_start:.2f}s")
        logger.info(f"[vanilla_rag_search] Total execution took {time.time() - start_time:.2f}s")

        return json.dumps(payload, ensure_ascii=False, indent=2)

    # most VLM can only accecpt base 64 url
    @staticmethod
    def _encode_image_to_data_url(path: str) -> str:
        try:
            p = Path(path)
            mime = "image/" + (p.suffix.lstrip(".").lower() or "png")
            data = p.read_bytes()
            b64 = base64.b64encode(data).decode("ascii")
            return f"data:{mime};base64,{b64}"
        except Exception:
            return ""


