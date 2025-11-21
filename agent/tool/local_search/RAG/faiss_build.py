# build FAISS vector DB and use the interface from base
from __future__ import annotations

import os
import time
import json
import asyncio
from pathlib import Path
from typing import List, final, Any

import numpy as np
import faiss
from dataclasses import dataclass

from .base import BaseVectorStorage
from ....log.logger import logger

"""
Metadata structure stored alongside the FAISS index:
{
    "faiss_id": {
        "__id__": "custom_id",
        "__vector__": [float, ...],
        "created_at": <timestamp>,
        "src_id": ...,
        "tgt_id": ...,
        ...
    }
}
"""


@final
@dataclass
class FaissVectorStorage(BaseVectorStorage):
    """Simple FAISS vector wrapper that persists index + metadata to disk."""

    def __post_init__(self):
        self.threshold = self.cosine_similarity_threshold

        # Resolve workspace under ./rag_cache unless an absolute path is provided
        workspace_dir = Path("__file__").resolve().parent / "rag_cache" / self.workspace
        if not workspace_dir.is_absolute():
            workspace_dir = Path(".") / "rag_cache" / self.workspace
        workspace_dir.mkdir(parents=True, exist_ok=True)
        self.workspace_dir = workspace_dir

        self._faiss_index_file = workspace_dir / f"{self.namespace}_faiss.index"
        self._metadata_file = Path(str(self._faiss_index_file) + ".meta.json")
        self._dim = self.embedding_func.embedding_dim
        # batching too many texts at once easily exhausts memory on CPU-only hosts
        batch_env = os.getenv("RAG_EMBED_BATCH_SIZE")
        try:
            self._embedding_batch = max(8, int(batch_env)) if batch_env else 128
        except ValueError:
            logger.warning(f"[{self.workspace}] Invalid RAG_EMBED_BATCH_SIZE={batch_env}, fallback to 128.")
            self._embedding_batch = 128
        self._hnsw_m = 16
        self._hnsw_ef_construction = 80
        self._hnsw_ef_search = 16

        # use cosine similarity with normalized vectors
        self._index = self._create_hnsw_index()
        self._id_to_meta: dict[int, dict[str, Any]] = {}
        self.lock = asyncio.Lock()

        self.initialize()

    # fetch the faiss index and metadata if exist
    def initialize(self):
        if self._faiss_index_file.exists():
            try:
                self._index = faiss.read_index(str(self._faiss_index_file))
                if self._index.d != self._dim:
                    logger.warning(
                        f"[{self.workspace}] FAISS index dim mismatch ({self._index.d} != {self._dim}), reinitializing."
                    )
                    self._index = self._create_hnsw_index()

                if self._metadata_file.exists():
                    with open(self._metadata_file, "r", encoding="utf-8") as f:
                        stored_dict = json.load(f) or {}
                    self._id_to_meta = {int(fid): meta for fid, meta in stored_dict.items()}
                else:
                    self._id_to_meta = {}

                logger.info(f"[{self.workspace}] FAISS index and metadata loaded successfully.")
            except Exception as e:  # pragma: no cover - defensive load
                logger.error(f"[{self.workspace}] Error loading FAISS index or metadata: {e}")
                logger.warning(f"[{self.workspace}] Initializing empty FAISS index and metadata.")
                self._index = self._create_hnsw_index()
                self._id_to_meta = {}
        else:
            self._index = self._create_hnsw_index()
            self._id_to_meta = {}

    def _create_hnsw_index(self):
        index = faiss.IndexHNSWFlat(self._dim, self._hnsw_m, faiss.METRIC_INNER_PRODUCT)
        index.hnsw.efConstruction = self._hnsw_ef_construction
        index.hnsw.efSearch = self._hnsw_ef_search
        return index

    # hook for concurrency control
    async def get_index(self):
        return self._index

    # when new data insert update the faiss index and metadata file
    async def upsert(self, data: dict[str, dict[str, Any]]):
        """
        Upsert embeddings into FAISS index.

        data structure:
        {
            "custom_id": {
                "content": <text>,
                "<meta_field>": ...
            }
        }
        """
        logger.debug(f"[{self.workspace}] FAISS: inserting {len(data)} vectors into {self.namespace} index.")

        if not data:
            return []

        current_time = time.time()
        contents = []
        metadatas = []
        for i, v in data.items():
            meta = {mf: v[mf] for mf in self.meta_fields if mf in v}
            meta["__id__"] = i
            meta["created_at"] = current_time
            contents.append(v["content"])
            metadatas.append(meta)

        batches = [
            contents[i : i + self._embedding_batch] for i in range(0, len(contents), self._embedding_batch)
        ]

        embeddings_split: list[np.ndarray] = []
        for batch in batches:
            embed = await self.embedding_func(batch)
            embeddings_split.append(np.asarray(embed, dtype="float32"))

        embeddings = np.concatenate(embeddings_split, axis=0) if embeddings_split else np.empty((0, self._dim))

        if len(embeddings) != len(metadatas):
            logger.error(
                f"[{self.workspace}] FAISS: embedding length {len(embeddings)} not match metadata length {len(metadatas)}"
            )
            return []

        faiss.normalize_L2(embeddings)

        # remove duplicates if needed
        need_remove = []
        for meta in metadatas:
            faiss_internal_id = self._find_faiss_id(meta["__id__"])
            if faiss_internal_id is not None:
                need_remove.append(faiss_internal_id)

        if need_remove:
            await self._remove_faiss_ids(need_remove)

        async with self.lock:
            index = await self.get_index()
            start_idx = index.ntotal
            index.add(embeddings)

            for i, meta in enumerate(metadatas):
                faiss_id = start_idx + i
                meta["__vector__"] = embeddings[i].tolist()
                self._id_to_meta.update({faiss_id: meta})

            self._save_faiss_index()

        logger.debug(f"[{self.workspace}] FAISS: inserted {len(data)} vectors into {self.namespace} index.")

        return [m["__id__"] for m in metadatas]

    # support function
    def _find_faiss_id(self, custom_id):
        for fid, meta in self._id_to_meta.items():
            if meta.get("__id__") == custom_id:
                return fid
            # add origial document delete
            elif meta.get("source_path") == custom_id:
                return fid
            elif meta.get("source_id") == custom_id:
                return fid
        return None

    async def _remove_faiss_ids(self, faiss_ids: List[int]):
        keep = [fid for fid in self._id_to_meta if fid not in faiss_ids]

        vector_keep = []
        new_id_to_meta = {}

        for new_id, old_fid in enumerate(keep):
            vector_meta = self._id_to_meta[old_fid]
            vector_keep.append(vector_meta["__vector__"])
            new_id_to_meta[new_id] = vector_meta

        async with self.lock:
            self._index = self._create_hnsw_index()
            if vector_keep:
                arr = np.array(vector_keep, dtype="float32")
                faiss.normalize_L2(arr)
                self._index.add(arr)

            self._id_to_meta = new_id_to_meta
            self._save_faiss_index()

    # process query and find similarity vectors
    async def query(self, query: str, top_k: int = 10, query_embedding: list[float] | None = None):
        if query_embedding is not None:
            embedding = np.array([query_embedding], dtype="float32")
        else:
            embedding = await self.embedding_func([query], _priority=5)
            embedding = np.array(embedding, dtype="float32")

        faiss.normalize_L2(embedding)

        index = await self.get_index()
        distance, indices = index.search(embedding, k=top_k)

        results = []
        if len(distance) == 0:
            return results

        for dist, idx in zip(distance[0], indices[0]):
            if idx == -1 or dist < self.threshold:
                continue

            meta = self._id_to_meta.get(int(idx), {})
            filtered_meta = {k: v for k, v in meta.items() if k != "__vector__"}
            results.append(
                {
                    **filtered_meta,
                    "id": meta.get("__id__", ""),
                    "distance": float(dist),
                    "created_at": meta.get("created_at", 0),
                }
            )
        return results

    @property
    def client_storage(self):
        return {"data": list(self._id_to_meta.values())}

    # finish father class abstract method
    async def delete(self, idx: list[str]):
        logger.debug(f"[{self.workspace}] FAISS: deleting {len(idx)} vectors from {self.namespace} index.")

        to_remove = []
        for cid in idx:
            faiss_id = self._find_faiss_id(cid)
            if faiss_id is not None:
                to_remove.append(faiss_id)

        if to_remove:
            await self._remove_faiss_ids(to_remove)

        logger.debug(f"[{self.workspace}] FAISS: deleted {len(to_remove)} vectors from {self.namespace} index.")


    # helper function to save current FAISS index + meta to disk
    def _save_faiss_index(self):
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(self._faiss_index_file))

        box = {str(fid): meta for fid, meta in self._id_to_meta.items()}
        with open(self._metadata_file, "w", encoding="utf-8") as f:
            json.dump(box, f, ensure_ascii=False, indent=2)

    async def index_done_callback(self) -> None:
        async with self.lock:
            self._save_faiss_index()

    async def get_by_id(self, id: str):
        fid = self._find_faiss_id(id)
        if fid is None:
            return None

        metadata = self._id_to_meta.get(fid, {})
        if not metadata:
            return None

        filtered_meta = {k: v for k, v in metadata.items() if k != "__vector__"}
        return {
            **filtered_meta,
            "id": metadata.get("__id__", ""),
            "created_at": metadata.get("created_at", 0),
        }

    async def get_by_ids(self, ids: list[str]) -> list[dict[str, Any]]:
        if not ids:
            return []

        results: list[dict[str, Any] | None] = []
        for id in ids:
            record = await self.get_by_id(id)
            results.append(record)

        return results

    async def get_vectors_by_ids(self, ids: list[str]) -> dict[str, list[float]]:
        if not ids:
            return {}

        vectors_dict = {}
        for id in ids:
            fid = self._find_faiss_id(id)
            if fid is not None and fid in self._id_to_meta:
                metadata = self._id_to_meta[fid]
                if "__vector__" in metadata:
                    vectors_dict[id] = metadata["__vector__"]

        return vectors_dict

    async def drop(self) -> dict[str, str]:
        try:
            async with self.lock:
                self._index = self._create_hnsw_index()
                self._id_to_meta = {}

                if self._faiss_index_file.exists():
                    os.remove(self._faiss_index_file)
                if self._metadata_file.exists():
                    os.remove(self._metadata_file)

            logger.info(f"[{self.workspace}] Process {os.getpid()} drop FAISS index {self.namespace}")
            return {"status": "success", "message": "data dropped"}
        except Exception as e:  # pragma: no cover - defensive
            logger.error(f"[{self.workspace}] Error dropping FAISS index {self.namespace}: {e}")
            return {"status": "error", "message": str(e)}
