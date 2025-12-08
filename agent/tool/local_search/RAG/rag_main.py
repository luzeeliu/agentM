from __future__ import annotations
import asyncio
import os
import time
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List
import json
import numpy as np
import torch
from torch.amp import autocast_mode
from sentence_transformers import SentenceTransformer
from .base import EmbeddingFunc
from .faiss_build import FaissVectorStorage
from .image_faiss_build import FaissImageStorage
from .kv_storage import KVStorage
from ....log.logger import logger
from .tokenizer import TiktokenTokenizer
from ..pdf_process import local_doc_process, _move_to_save


def _resolve_device() -> str:
    """Prefer CUDA when available unless forced to CPU or running CPU-only in Docker."""
    force_cpu = os.environ.get("RAG_FORCE_CPU", "").lower() in {"1", "true", "yes"}

    if force_cpu:
        return "cpu"
    if torch.cuda.is_available():
        return "cuda"
    # In Docker without visible GPUs, stay on CPU explicitly.
    return "cpu"


class _BgeM3Embedder:
    """Thread-safe wrapper around the SentenceTransformer model."""

    def __init__(self, model_name: str = "BAAI/bge-m3"):
        self.model_name = model_name
        self._model: SentenceTransformer | None = None
        self._load_lock = asyncio.Lock()
        self.device = _resolve_device()

    async def _ensure_model(self):
        if self._model is None:
            async with self._load_lock:
                loop = asyncio.get_running_loop()

                def _load():
                    logger.info(f"Loading model {self.model_name}")
                    return SentenceTransformer(self.model_name, device=self.device)

                self._model = await loop.run_in_executor(None, _load)

    async def encode(self, texts: List[str]) -> np.ndarray:
        await self._ensure_model()
        assert self._model is not None
        loop = asyncio.get_running_loop()

        def _encode():
            if self.device == "cuda":
                with autocast_mode.autocast("cuda"):
                    out = self._model.encode(texts, normalize_embeddings=False, batch_size=16, convert_to_numpy=True)
            else:
                logger.warning(f"[{self.model_name}]using cpu mode")
                out = self._model.encode(texts, normalize_embeddings=False, batch_size=16, convert_to_numpy=True)
            return out.astype("float32")
                    

        return await loop.run_in_executor(None, _encode)

# image multimodel 
class clipembedder:
    # load clip moel and instantiate it for warm up
    def __init__(self, model_name: str = "sentence-transformers/clip-ViT-B-32"):
        self.model_name = model_name
        self._model: SentenceTransformer | None = None
        self.lock = asyncio.Lock()
        self.device = _resolve_device()
    
    async def initial(self):
        if self._model is None:
            async with self.lock:
                loop = asyncio.get_running_loop()
                def _load():
                    logger.info(f"Loading model {self.model_name}")
                    # Some SentenceTransformer versions do not accept use_fast
                    return SentenceTransformer(self.model_name, device=self.device)
                self._model = await loop.run_in_executor(None, _load)
                
                
    async def _encode(self, image) -> np.ndarray:
        await self.initial()
        loop = asyncio.get_running_loop()
        
        def encode():
            if self.device == "cuda":
                with autocast_mode.autocast("cuda"):
                    out = self._model.encode(image, normalize_embeddings=False, batch_size=16, convert_to_numpy=True)
            else:
                logger.warning(f"[{self.model_name}]using cpu mode")
                out = self._model.encode(image, normalize_embeddings=False, batch_size=16, convert_to_numpy=True)
            return out.astype("float32")
        return await loop.run_in_executor(None, encode)
            


# instantiate the model
_EMBEDDER = _BgeM3Embedder()
_IMAGE_EMBEDDER = clipembedder()

async def _embedding_func(texts: List[str], embedding_dim: int = 1024, **_) -> np.ndarray:
    vectors = await _EMBEDDER.encode(texts)
    if vectors.shape[1] != embedding_dim:
        logger.warning(
            "[vanilla-rag] embedding dimension mismatch %s != %s",
            vectors.shape[1],
            embedding_dim,
        )
    return vectors

async def image_embedding_func(images, embedding_dim):
    vectors = await _IMAGE_EMBEDDER._encode(images)
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
    image_embedding_dim: int = 512
    image_top_k: int = 3
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
        self.image_embedding_func = EmbeddingFunc(
            embedding_dim=self.image_embedding_dim,
            func=image_embedding_func,
            send_dimensions=True,
        )
        # meta_feilds is intentionally misspelled in the base class
        meta_fields = {
            "source_id",
            "content",
            "source_path",
            "chunk_index",
            "source_type",
            "pdf_name",
            "pdf_page",
            "linked_images",
            }
        self.vector_storage = FaissVectorStorage(
            namespace=self.namespace,
            workspace=self.workspace,
            embedding_func=self.embedding_func,
            meta_fields=meta_fields,
        )
        image_meta_fields = {
            "source_id",
            "source_path",
            "source_type",
            "pdf_name",
            "pdf_page",
            "image_id",
            "image_path",
        }
        self.image_vector_storage = FaissImageStorage(
            namespace=f"{self.namespace}_image",
            workspace=self.workspace,
            embedding_func=self.image_embedding_func,
            meta_fields=image_meta_fields,
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
            self.image_vector_storage.initialize()
            
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

        pdf_pro_dir = Path(__file__).resolve().parent.parent / "pdf_pro"
        pdf_meta_path = pdf_pro_dir / "PDF.json"
        pdf_meta = {}
        if pdf_meta_path.exists():
            try:
                pdf_meta = json.loads(pdf_meta_path.read_text(encoding="utf-8")) or {}
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(f"[{self.workspace}] failed to load PDF metadata: {exc}")

        # for checking if the text file in the PDF
        # those two are file-level
        def _get_safe_name(p: str) -> str:
            # Handle Windows paths on Linux (where \ is not a separator)
            s = str(p)
            if "\\" in s:
                return s.split("\\")[-1]
            return Path(s).name

        def _resolve_path(p: str) -> str:
            """Resolve path to local system, handling relative/absolute and Windows/Linux paths."""
            if not p:
                return ""
            
            # 1. Try as is (absolute or relative to CWD)
            path_obj = Path(p)
            if path_obj.exists():
                return str(path_obj.resolve())

            # 2. Try as relative to pdf_pro_dir
            # Clean the name to just filename if it looks like a path
            clean_name = _get_safe_name(p)
            
            # Check in images/
            candidate_img = pdf_pro_dir / "images" / clean_name
            if candidate_img.exists():
                return str(candidate_img.resolve())

            # Check in texts/
            candidate_txt = pdf_pro_dir / "texts" / clean_name
            if candidate_txt.exists():
                return str(candidate_txt.resolve())
            
            # 3. If it looks like 'images/foo.png' (relative path from PDF.json update)
            # Try combining with pdf_pro_dir
            # Normalize separators
            normalized_p = p.replace("\\", "/")
            candidate_rel = pdf_pro_dir / normalized_p
            if candidate_rel.exists():
                return str(candidate_rel.resolve())

            return p # Return original if cannot resolve

        text_meta_map = {}
        for item in pdf_meta.get("text", []):
            if isinstance(item, dict) and "filename" in item:
                text_meta_map[_get_safe_name(item["filename"])] = item

        image_meta_map = {}
        for item in pdf_meta.get("image", []):
            if isinstance(item, dict) and "filename" in item:
                image_meta_map[_get_safe_name(item["filename"])] = item
        
        # detail of image page in the PDF
        page_image_map: dict[tuple[str, int], list[dict[str, Any]]] = {}
        for img in pdf_meta.get("image", []):
            if not isinstance(img, dict):
                continue
            # Ensure safe access to keys
            p_name = img.get("pdf")
            p_page = img.get("page")
            if p_name and p_page:
                key = (p_name, p_page)
                page_image_map.setdefault(key, []).append(img)

        kv_payload: dict[str, dict[str, Any]] = {}
        vector_payload: dict[str, dict[str, Any]] = {}
        image_payload: dict[str, dict[str, Any]] = {}

        for file in files:
            try:
                #logger.info(f"[process moniter] rm line199")
                # .read_test is path method
                content = file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                content = file.read_text(encoding="utf-8", errors="ignore")

            doc_id = file.stem
            
            #start = time.time()
            
            chunks = self._chunk_text(content)
            
            #end = time.time()

            meta_from_pdf = text_meta_map.get(file.name)
            source_type = "pdf_text" if meta_from_pdf else "text"
            pdf_name = meta_from_pdf.get("pdf") if meta_from_pdf else None
            pdf_page = meta_from_pdf.get("page") if meta_from_pdf else None
            
            # here we get specific PDF fram 
            linked_images = [
                _resolve_path(img["filename"]) for img in page_image_map.get((pdf_name, pdf_page), []) if isinstance(img, dict)
            ] if pdf_name and pdf_page else []

            for chunk in chunks:
                chunk_id = f"{doc_id}_chunk_{chunk['chunk_index']}"
                metadata = {
                    "source_id": doc_id,
                    "source_path": str(file),
                    "source_type": source_type,
                    "chunk_index": chunk["chunk_index"],
                    "pdf_name": pdf_name,
                    "pdf_page": pdf_page,
                    "linked_images": linked_images,
                }
                kv_payload[chunk_id] = {
                    "content": chunk["content"],
                    "file_path": str(file),
                    **metadata,
                }
                vector_payload[chunk_id] = {
                    "content": chunk["content"],
                    **metadata,
                }

        for image_path in images:
            resolved_image_path = Path(_resolve_path(str(image_path)))
            if not resolved_image_path.exists():
                logger.warning(f"[{self.workspace}] image file not found: {image_path}")
                continue

            meta = image_meta_map.get(image_path.name)
            pdf_name = meta.get("pdf") if meta else None
            pdf_page = meta.get("page") if meta else None
            image_id = meta.get("image_id") if meta else image_path.stem
            pdf_stem = Path(pdf_name).stem if pdf_name else image_path.stem
            
            # here we use same KV with different ky id to store the image
            custom_id = (
                f"{pdf_stem}_page{pdf_page}_image{image_id}"
                if pdf_name and pdf_page
                else image_path.stem
            )
            base_meta = {
                "source_id": custom_id,
                "source_path": image_path.name,
                "source_type": "pdf_image" if pdf_name else "image",
                "pdf_name": pdf_name,
                "pdf_page": pdf_page,
                "image_id": image_id,
                "image_path": str(resolved_image_path),
            }
            image_payload[custom_id] = {
                "images": resolved_image_path,
                **base_meta,
            }
            kv_payload[custom_id] = {
                "content": "",
                "file_path": image_path.name,
                **base_meta,
            }

        if not vector_payload and not image_payload:
            return {"status": "error", "message": "no chunks generated"}
        #logger.info(f"[process moniter] rm line226")
        start1 = time.time()
        await self.kv_storage.upsert(kv_payload)
        await self.vector_storage.upsert(vector_payload)
        if image_payload:
            await self.image_vector_storage.upsert(image_payload)
        # index done callbacks is to save result
        await self.kv_storage.index_done_callback()
        await self.vector_storage.index_done_callback()
        if image_payload:
            await self.image_vector_storage.index_done_callback()
        #logger.info(f"[process moniter] rm line232")
        end1 = time.time()
        logger.info(
            f"[{self.workspace}] indexing {len(vector_payload)} text chunks and {len(image_payload)} images took {end1 - start1} seconds"
        )
        return {
            "status": "success",
            "files": [f.name for f in files],
            "chunks_indexed": len(vector_payload),
            "images_indexed": len(image_payload),
        }

    async def query(self, query: str, top_k: int | None = None) -> list[dict[str, Any]]:
        # after add image 
        # the logical of image search in here is 
        # 1. we check if text is PDF 
        # 2. in TEXT metadata build we add linked_images which means the image is in the same PDF
        # 3. if this text is not in the PDF those attribute is none
        # 4. when search query in FAISS the result will show if this text is in the PDF and is this PDF include images
        t0 = time.time()
        hits = await self.vector_storage.query(query, top_k=top_k or self.top_k)
        t1 = time.time()
        logger.info(f"[{self.workspace}] Vector search took {t1 - t0:.3f}s")
        
        if not hits:
            return []

        ids = [hit.get("id") for hit in hits if hit and hit.get("id")]
        kv_records = await self.kv_storage.get_by_ids(ids)
        t2 = time.time()
        logger.info(f"[{self.workspace}] KV retrieval took {t2 - t1:.3f}s")

        results = []
        for hit, kv in zip(hits, kv_records):
            if not kv:
                continue
            linked_images = kv.get("linked_images") or []
            results.append(
                {
                    "id": hit.get("id"),
                    "content": kv.get("content", ""),
                    "source": kv.get("file_path") or kv.get("source_path"),
                    "score": hit.get("distance", 0.0),
                    "source_type": kv.get("source_type"),
                    "pdf_name": kv.get("pdf_name"),
                    "pdf_page": kv.get("pdf_page"),
                    "linked_images": linked_images,
                }
            )
        return results


_DEFAULT_SERVICE = VanillaRAG()
_warmup_lock = threading.Lock()
_warmup_task: asyncio.Task | None = None
_warmup_complete = False
_warmup_in_progress = False


async def _warmup_default_service(auto_build: bool) -> None:
    logger.info("[vanilla-rag] _warmup_default_service started")
    await _DEFAULT_SERVICE.initialize()
    if auto_build and not _DEFAULT_SERVICE.vector_storage.client_storage.get("data"):
        logger.info("[vanilla-rag] Auto-building index from shards...")
        await _DEFAULT_SERVICE.build_from_shards()
    logger.info("[vanilla-rag] _warmup_default_service finished")


def warmup_vanilla_rag(auto_build: bool = False) -> asyncio.Task | None:
    """
    Preload the default VanillaRAG service so the FAISS index and KV cache are
    ready before the first tool invocation.

    When no event loop is running, warmup runs synchronously. When invoked from
    within an active loop, the coroutine is scheduled in the background.
    """
    global _warmup_task, _warmup_complete, _warmup_in_progress

    # because the task is asyncio event loop, so it need thread to run
    # remember the asyncio need thread to avoid occupied event loop
    with _warmup_lock:
        if _warmup_complete:
            print("[warmup_vanilla_rag] already completed")
            return None
        if _warmup_in_progress:
            print("[warmup_vanilla_rag] already running")
            return _warmup_task
        # mark in-progress early to prevent duplicate starts
        _warmup_in_progress = True
        task = _warmup_task

    if task is not None and not task.done():
        print("[warmup_vanilla_rag] already completed")
        with _warmup_lock:
            _warmup_in_progress = False
        return task

    async def _runner():
        global _warmup_task, _warmup_complete, _warmup_in_progress
        try:
            logger.info("[vanilla-rag] Starting warmup...")
            await _warmup_default_service(auto_build)
            
            logger.info("[vanilla-rag] Warming up text embedder...")
            await _EMBEDDER._ensure_model()
            # Run dummy inference to ensure model is loaded in memory
            await _EMBEDDER.encode(["warmup"])
            
            logger.info("[vanilla-rag] Warming up image embedder...")
            await _IMAGE_EMBEDDER.initial()
            # Run dummy inference (CLIP handles text too)
            await _IMAGE_EMBEDDER._encode(["warmup"])
            
            logger.info("[vanilla-rag] Warmup completed successfully.")
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("[vanilla-rag] Warmup failed: %s", exc)
            raise
        else:
            with _warmup_lock:
                _warmup_complete = True
        finally:
            with _warmup_lock:
                _warmup_task = None
                _warmup_in_progress = False

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        try:
            asyncio.run(_runner())
        finally:
            with _warmup_lock:
                _warmup_in_progress = False
        return None
    else:
        with _warmup_lock:
            if _warmup_complete:
                print("[warmup_vanilla_rag] already completed")
                _warmup_in_progress = False
                return None
            _warmup_task = loop.create_task(_runner())
            return _warmup_task


async def async_query_local_rag(query: str, top_k: int = 5, auto_build: bool = True) -> list[dict[str, Any]]:
    """
    Async entry-point used by tools:
    1. Load caches
    2. Optionally build a demo cache from a few shards if nothing exists
    3. Return matched chunks with original content
    """

    return await _DEFAULT_SERVICE.query(query, top_k=top_k)

async def _cli_build():
    result = await _DEFAULT_SERVICE.build_from_shards()
    logger.info("[vanilla-rag] build result: %s", result)
    return result


def main():
    asyncio.run(_cli_build())


if __name__ == "__main__":
    main()
