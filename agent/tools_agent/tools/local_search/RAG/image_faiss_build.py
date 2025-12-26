# build imae faiss storage
import os
import time
import json
import asyncio
from pathlib import Path
from typing import List, Optional, final, Any
from PIL import Image
import numpy as np
import faiss
from dataclasses import dataclass
from tqdm.auto import tqdm

from .base import BaseVectorStorage
from .....log.logger import logger

"""
metadata structure:
{
    "faiss_id": {
        "__id__": "custom_id",
        "created_at": <timestamp>,
        "vector": [float, ...],
        ...
    }
}
"""

@final
@dataclass
class FaissImageStorage(BaseVectorStorage):
    # follow interface
    def __post_init__(self):
        self.threshold = self.cosine_similarity_threshold

        workspace_dir = Path(__file__).resolve().parent / "image_cache" / self.workspace
        if not workspace_dir.is_absolute():
            workspace_dir = Path(".") / "image_cache" / self.workspace
        workspace_dir.mkdir(parents=True, exist_ok=True)

        self.workspace_dir = workspace_dir
        self._faiss_index_file = workspace_dir / f"{self.namespace}_faiss.index"
        self._metadata_file = Path(str(self._faiss_index_file) + ".meta.json")
        
        self._dim = self.embedding_func.embedding_dim
        
        self.embedding_batch = 8
        self._hnsw_m = 16
        self.hnsw_ef_construction = 80
        self.hnsw_ef_search = 16
        
        self.lock = asyncio.Lock()
        self._index = self._create_hnsw_index()
        self._id_to_meta: dict[int, dict[str, Any]] = {}
        
        
    def _create_hnsw_index(self):
        # set hnsw calcuate dot product
        index = faiss.IndexHNSWFlat(self._dim, self._hnsw_m, faiss.METRIC_INNER_PRODUCT)
        # teh hnsw_m will affect the connect quantity of the vector
        index.hnsw.efConstruction = self.hnsw_ef_construction
        # how deep the algorithm searches to find the best neighbors when add new vector
        index.hnsw.efSearch = self.hnsw_ef_search
        # the deepth of search can be changed after index is built without re-indexing
        return index
    
    def initialize(self):
        # step: check if index file exists
        # 2. initial index and load exist .index and metadata
        # 3. 
        if self._faiss_index_file.exists():
            try:
                self._index = faiss.read_index(str(self._faiss_index_file))
                # check if the dim is equal
                if self._index.d != self._dim:
                    logger.warning(
                        f"[{self.workspace}] FAISS index dim mismatch ({self._index.d} != {self._dim}), reinitializing."
                    )
                if self._metadata_file.exists():
                    # load metadata
                    with open(self._metadata_file, "r", encoding="utf-8") as f:
                        stored_dict = json.load(f) or {}
                    self._id_to_meta = {int(fid): meta for fid, meta in stored_dict.items()}
                else:
                    self._id_to_meta = {}
                logger.info(f"[{self.workspace}] images FAISS index and metadata loaded successfully.")
            except Exception as e:  # pragma: no cover - defensive load
                logger.error(f"[{self.workspace}] Error loading FAISS index or metadata: {e}")
                logger.warning(f"[{self.workspace}] Initializing empty FAISS index and metadata.")
                self._index = self._create_hnsw_index()
                self._id_to_meta = {}
        else:
            self._index = self._create_hnsw_index()
            self._id_to_meta = {}
            
    # for async safe
    async def get_index(self):
        return self._index
    
    # save faiss and metadata
    def save_faiss_index(self):
        # check if workspace dir exists
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(self._faiss_index_file))
        
        # str key for safety json
        box = {str(fid): meta for fid, meta in self._id_to_meta.items()}
        with open(self._metadata_file, "w", encoding="utf-8") as f:
            json.dump(box, f, ensure_ascii=False, indent=2)
    
    
    def _find_faiss_id(self, custom_id):
        for fid, meta in self._id_to_meta.items():
            if meta.get("__id__") == custom_id:
                return fid
        return None
    
    async def _remove_fasii_by_id(self, id: List[int]):
        keep = [fid for fid in self._id_to_meta.keys() if fid not in id]
        
        vector_keep = []
        new_id_to_meta = {}
        
        # when update faiss index we need fetch original vector from keep box
        # then initial index add all vector in to index
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
            self.save_faiss_index()
            
        
    
    async def upsert(self, data: dict[str, dict[str, Any]]):
        """
        Upsert embeddings into FAISS index.

        data structure:
        {
            "custom_id": {
                "images": <image>,
                "<meta_field>": ...
            }
        }
        """
        logger.debug(f"[{self.workspace}] FAISS: inserting {len(data)} vectors into {self.namespace} index.")
        if not data:
            return []
        
        # record time of create at
        current_time = time.time()
        images = []
        # here the data is list sequence input all file in updata box will become input
        meatadatas = []
        
        # fetche images and meta from data
        for i, v in data.items():
            meta = {mf: v[mf] for mf in self.meta_fields if mf in v}
            meta["__id__"] = i
            meta["created_at"] = current_time
            images.append(v["images"])
            meatadatas.append(meta)
        
        # add batch manipulate for handle images
        batchs = [
            images[i : i + self.embedding_batch] for i in range(0, len(images), self.embedding_batch)
        ]
        
        embeddings_split: list[np.ndarray] = []
        if batchs:
            with tqdm(total=len(batchs), desc=f"[{self.workspace}] FAISS: inserting {self.namespace} index.", unit="batch") as pbar:
                for batch_paths in batchs:
                    # SentenceTransformer image encoders can take PIL Images directly.
                    batch_images = [Image.open(p).convert("RGB") for p in batch_paths]
                    # each embedding of a image in one row
                    embedding = await self.embedding_func(batch_images)
                    embedding = np.asarray(embedding, dtype="float32")
                    # faiss normalize is row-wise
                    faiss.normalize_L2(embedding)
                    embeddings_split.append(embedding)
                    pbar.update(1)

        #flatten embedding to 2D for faiss add
        all_embedding = np.concatenate(embeddings_split, axis=0) if embeddings_split else np.empty((0, self._dim), dtype="float32")

        if len(all_embedding) != len(meatadatas):
            logger.error(
                f"[{self.workspace}] FAISS image: embedding length {len(all_embedding)} not match metadata length {len(meatadatas)}"
            )
            return []
        
        # update current storage remove duplicate
        need_remove = []
        for metas in meatadatas:
            rm_faiss_id = self._find_faiss_id(metas["__id__"])
            if rm_faiss_id is not None:
                need_remove.append(rm_faiss_id)
        
        if need_remove:
            await self._remove_fasii_by_id(need_remove)
            
        # insert new embedding to faiss
        async with self.lock:
            # async safety load index
            index = await self.get_index()
            # insert in the end of index fro meta collection
            start = index.ntotal
            if len(all_embedding):
                index.add(all_embedding)
            
        # UPDATE META
        # the mertadatas is the data we need updata not include old data
            for i, meta in enumerate(meatadatas):
                faiss_id = start + i   
                meta["__vector__"] = all_embedding[i].tolist()
                self._id_to_meta.update({faiss_id: meta})
            self.save_faiss_index()
        
        logger.debug(f"[{self.workspace}] FAISS: inserted {len(data)} vectors into {self.namespace} index.")
        
        return [m["__id__"] for m in meatadatas]
    
    
    def _resolve_path(self, path: str) -> str:
        """Helper to resolve paths that might be from a different OS."""
        if not path:
            return ""
        
        # Helper to get safe filename from potential Windows path on Linux
        def _get_safe_name(p: str) -> str:
            s = str(p)
            if "\\" in s:
                return s.split("\\")[-1]
            return Path(s).name

        p = Path(path)
        if p.exists():
            return str(p.resolve())
        
        # Try finding in standard locations relative to this file
        # __file__ is agent/tool/local_search/RAG/image_faiss_build.py
        # pdf_pro is agent/tool/local_search/pdf_pro
        try:
            base_dir = Path(__file__).resolve().parent.parent / "pdf_pro"
            if not base_dir.exists():
                return path

            filename = _get_safe_name(path)
            
            # Try images folder
            candidate = base_dir / "images" / filename
            if candidate.exists():
                return str(candidate.resolve())
            
            # Try texts folder
            candidate = base_dir / "texts" / filename
            if candidate.exists():
                return str(candidate.resolve())
                
        except Exception:
            pass
            
        return path

    async def query(
        self,
        images: Optional[list[str]] = None,
        text: Optional[str] = None,
        top_k: int = 10,
        query_embedding: list[float] | None = None,
    ):
        # Build a query embedding from explicit vector, images, or text (for CLIP text->image search).
        if query_embedding is not None:
            embedding = np.array([query_embedding], dtype="float32")
        elif images:
            batch_images = [Image.open(p).convert("RGB") for p in images]
            embedding = await self.embedding_func(batch_images)
            embedding = np.asarray(embedding, dtype="float32")
        elif text:
            embedding = await self.embedding_func([text])
            embedding = np.asarray(embedding, dtype="float32")
        else:
            return []

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
            
            # Resolve paths
            if "image_path" in filtered_meta:
                filtered_meta["image_path"] = self._resolve_path(filtered_meta["image_path"])
            if "source_path" in filtered_meta:
                filtered_meta["source_path"] = self._resolve_path(filtered_meta["source_path"])
                
            results.append({
                **filtered_meta,
                "id": meta.get("__id__", ""),
                "distance": float(dist),
                "created_at": meta.get("created_at", 0),
            })
        return results

    async def index_done_callback(self) -> None:
        async with self.lock:
            self.save_faiss_index()

    async def get_by_id(self, id: str):
        fid = self._find_faiss_id(id)
        if fid is None:
            return None

        metadata = self._id_to_meta.get(fid, {})
        if not metadata:
            return None

        filtered_meta = {k: v for k, v in metadata.items() if k != "__vector__"}
        
        # Resolve paths
        if "image_path" in filtered_meta:
            filtered_meta["image_path"] = self._resolve_path(filtered_meta["image_path"])
        if "source_path" in filtered_meta:
            filtered_meta["source_path"] = self._resolve_path(filtered_meta["source_path"])

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

    async def delete(self, ids: list[str]):
        to_remove = []
        for cid in ids:
            faiss_id = self._find_faiss_id(cid)
            if faiss_id is not None:
                to_remove.append(faiss_id)

        if to_remove:
            await self._remove_fasii_by_id(to_remove)

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

    @property
    def client_storage(self):
        return {"data": list(self._id_to_meta.values())}
