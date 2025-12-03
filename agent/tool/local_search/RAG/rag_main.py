from __future__ import annotations
import argparse
import asyncio
import time
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List
import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from .base import EmbeddingFunc
from .faiss_build import FaissVectorStorage
from .kv_storage import KVStorage
from ....log.logger import logger
from .tokenizer import TiktokenTokenizer
from ..pdf_process import local_doc_process, _move_to_save


class _BgeM3Embedder:
    """Thread-safe wrapper around the SentenceTransformer model."""

    def __init__(self, model_name: str = "BAAI/bge-m3"):
        self.model_name = model_name
        self._model: SentenceTransformer | None = None
        self._load_lock = asyncio.Lock()

    async def _ensure_model(self):
        if self._model is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            async with self._load_lock:
                if self._model is None:
                    loop = asyncio.get_running_loop()

                    def _load():
                        return SentenceTransformer(self.model_name, device=device)

                    self._model = await loop.run_in_executor(None, _load)

    async def encode(self, texts: List[str]) -> np.ndarray:
        await self._ensure_model()
        assert self._model is not None
        loop = asyncio.get_running_loop()

        def _encode():
            return self._model.encode(
                texts,
                normalize_embeddings=False,
                batch_size=16,
                convert_to_numpy=True,
            ).astype("float32")

        return await loop.run_in_executor(None, _encode)

# image multimodel 
class clipembedder:
    # load clip moel and instantiate it for warm up
    def __init__(self, model_name: str = "openai/clip-vit-base-patch32"):
        self.model_name = model_name
        self._model: SentenceTransformer | None = None



_EMBEDDER = _BgeM3Embedder()


async def _embedding_func(texts: List[str], embedding_dim: int = 1024, **_) -> np.ndarray:
    vectors = await _EMBEDDER.encode(texts)
    if vectors.shape[1] != embedding_dim:
        logger.warning(
            "[vanilla-rag] embedding dimension mismatch %s != %s",
            vectors.shape[1],
            embedding_dim,
        )
    return vectors


@dataclass
class VanillaRAG:

    namespace: str = "vanilla"
    workspace: str = "vanilla"
    top_k: int = 5
    embedding_dim: int = 1024
    shard_dir: Path = field(
        default_factory=lambda: Path(__file__).resolve().parent.parent / "out_shards"
    )
    update_dir: Path = field(
        default_factory=lambda: Path(__file__).resolve().parent.parent / "update_box"
    )

    def __post_init__(self):
        self.embedding_func = EmbeddingFunc(
            embedding_dim=self.embedding_dim,
            func=_embedding_func,
        )
        # meta_feilds is intentionally misspelled in the base class
        meta_fields = {
            "source_id",
            "content",
            "source_path",
            "chunk_index"
            }
        self.vector_storage = FaissVectorStorage(
            namespace=self.namespace,
            workspace=self.workspace,
            embedding_func=self.embedding_func,
            meta_fields=meta_fields,
        )
        self.kv_storage = KVStorage(
            namespace=f"{self.namespace}_text_chunk",
            workspace=self.workspace,
            embedding_func=self.embedding_func,
        )
        self._init_lock = asyncio.Lock()
        self.tokenizer = TiktokenTokenizer()

    async def initialize(self):
        async with self._init_lock:
            await self.kv_storage.initialize()
            # FAISS initialize runs in __post_init__, but ensure metadata reload if persisted
            self.vector_storage.initialize()
            
    # deprecated
    def _iter_shards(self, limit: int | None = None) -> list[Path]:
        if not self.shard_dir.exists():
            logger.warning(f"[vanilla-rag] shard directory not found: {self.shard_dir}")
            return []
        files = sorted(self.shard_dir.glob("*.txt"))
        
        return files[:limit] if limit else files

    def _chunk_text(
        self, 
        content: str, 
        split_by_character: str | None = None,
        only_character: bool = False,
        chunk_overlap: int = 100,
        chunk_token_size = 1200,
        ) -> list[str]:

        # chunk content by the token size or character
        token = self.tokenizer.encode(content)
        #logger.info(f"[process moniter] rm line144")
        result: list[dict[str, Any]] = []
        if split_by_character:
            chunks = content.split(split_by_character)
            new_chunk = []
            if only_character:
                for chunk in chunks:
                    new_chunk.append((len(chunk.strip()), chunk))
            else:
                # reguler with token size 
                for chunk in chunks:
                    chunk_token = self.tokenizer.encode(chunk)
                    if len(chunk_token) > chunk_token_size:
                        for start in range(
                            0, len(chunk_token), chunk_token_size - chunk_overlap
                        ):
                            chunk_content = self.tokenizer.decode(
                                chunk_token[start : start + chunk_token_size]
                            )
                            new_chunk.append((min(chunk_token_size, len(chunk_token) - start), chunk_content))
                            
                    else:
                        new_chunk.append((len(chunk_token), chunk))
            for index, (length, chunk) in enumerate(new_chunk):
                result.append({
                    "content": chunk.strip(),
                    "chunk_length": length,
                    "chunk_index": index
                })
                
        else:
            for start in range(0, len(token), chunk_token_size - chunk_overlap):
                chunk_content = self.tokenizer.decode(
                    token[start : start + chunk_token_size]
                )
                result.append({
                    "content": chunk_content.strip(),
                    "chunk_length": min(chunk_token_size, len(token[start : start + chunk_token_size])),
                    "chunk_index": start
                })
        #logger.info(f"[process moniter] rm line184")
        return result

    async def build_from_shards(self) -> dict[str, Any]:
        await self.initialize()
        files, images = local_doc_process(self.update_dir)
        if not files:
            return {"status": "error", "message": "no shard files found"}

        kv_payload: dict[str, dict[str, Any]] = {}
        vector_payload: dict[str, dict[str, Any]] = {}

        for file in files:
            try:
                #logger.info(f"[process moniter] rm line199")
                content = file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                content = file.read_text(encoding="utf-8", errors="ignore")

            doc_id = file.stem
            
            #start = time.time()
            
            chunks = self._chunk_text(content)
            
            #end = time.time()

            #logger.info(f"[process moniter] rm line206")
            for chunk in chunks:
                chunk_id = f"{doc_id}_chunk_{chunk['chunk_index']}"
                metadata = {
                    "source_id": doc_id,
                    "source_path": file.name,
                    "chunk_index": chunk["chunk_index"],
                }
                kv_payload[chunk_id] = {
                    "content": chunk["content"],
                    "file_path": file.name,
                    **metadata,
                }
                vector_payload[chunk_id] = {
                    "content": chunk["content"],
                    **metadata,
                }

        if not vector_payload:
            return {"status": "error", "message": "no chunks generated"}
        #logger.info(f"[process moniter] rm line226")
        start1 = time.time()
        await self.kv_storage.upsert(kv_payload)
        await self.vector_storage.upsert(vector_payload)
        # index done callbacks is to save result
        await self.kv_storage.index_done_callback()
        await self.vector_storage.index_done_callback()
        #logger.info(f"[process moniter] rm line232")
        end1 = time.time()
        logger.info(
            f"[{self.workspace}] indexing {len(vector_payload)} chunks took {end1 - start1} seconds"
        )
        return {
            "status": "success",
            "files": [f.name for f in files],
            "chunks_indexed": len(vector_payload),
        }

    async def query(self, query: str, top_k: int | None = None) -> list[dict[str, Any]]:

        hits = await self.vector_storage.query(query, top_k=top_k or self.top_k)
        if not hits:
            return []

        ids = [hit.get("id") for hit in hits if hit and hit.get("id")]
        kv_records = await self.kv_storage.get_by_ids(ids)

        results = []
        for hit, kv in zip(hits, kv_records):
            if not kv:
                continue
            results.append(
                {
                    "id": hit.get("id"),
                    "content": kv.get("content", ""),
                    "source": kv.get("file_path") or kv.get("source_path"),
                    "score": hit.get("distance", 0.0),
                }
            )
        return results


_DEFAULT_SERVICE = VanillaRAG()
_warmup_lock = threading.Lock()
_warmup_task: asyncio.Task | None = None
_warmup_complete = False


async def _warmup_default_service(auto_build: bool) -> None:
    await _DEFAULT_SERVICE.initialize()
    if auto_build and not _DEFAULT_SERVICE.vector_storage.client_storage.get("data"):
        await _DEFAULT_SERVICE.build_from_shards()


def warmup_vanilla_rag(auto_build: bool = False) -> None:
    """
    Preload the default VanillaRAG service so the FAISS index and KV cache are
    ready before the first tool invocation.

    When no event loop is running, warmup runs synchronously. When invoked from
    within an active loop, the coroutine is scheduled in the background.
    """
    global _warmup_task, _warmup_complete

    # because the task is asyncio event loop, so it need thread to run
    # remember the asyncio need thread to avoid occupied event loop
    with _warmup_lock:
        if _warmup_complete:
            print("[warmup_vanilla_rag] already completed")
            return
        task = _warmup_task

    if task is not None and not task.done():
        print("[warmup_vanilla_rag] already completed")
        return

    async def _runner():
        try:
            await _warmup_default_service(auto_build)
            await _EMBEDDER._ensure_model()
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("[vanilla-rag] Warmup failed: %s", exc)
            raise
        else:
            with _warmup_lock:
                _warmup_complete = True
        finally:
            with _warmup_lock:
                _warmup_task = None

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(_runner())
    else:
        with _warmup_lock:
            if _warmup_complete:
                print("[warmup_vanilla_rag] already completed")
                return
            _warmup_task = loop.create_task(_runner())


async def async_query_local_rag(query: str, top_k: int = 5, auto_build: bool = True) -> list[dict[str, Any]]:
    """
    Async entry-point used by tools:
    1. Load caches
    2. Optionally build a demo cache from a few shards if nothing exists
    3. Return matched chunks with original content
    """
    #warmup_vanilla_rag(auto_build)
    return await _DEFAULT_SERVICE.query(query, top_k=top_k)

async def _cli_build():
    result = await _DEFAULT_SERVICE.build_from_shards()
    logger.info("[vanilla-rag] build result: %s", result)
    return result


def main():
    asyncio.run(_cli_build())


if __name__ == "__main__":
    main()
