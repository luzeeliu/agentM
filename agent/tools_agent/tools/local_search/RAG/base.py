from __future__ import annotations

import os
import dotenv
import numpy as np
from enum import Enum
from pydantic import BaseModel
from typing import Any, TypedDict, Optional
from abc import abstractmethod, ABC
from dataclasses import dataclass, field
from .....log.logger import logger

# build shape of lightRAG vector storage and embedding function call 
# in the database we need store the graph relationship
# query result retrieved form vector database
# document status storage
# ( the KV storage will store all non-vector date include entities, relations, text chunks full document, LLM cache)
# the KV make the txt chunk and document separated from vector store
    
    
# for bge-m3 1024dim and text-embedding-3-large 1536dim
@dataclass
class EmbeddingFunc:
    embedding_dim: int
    func: callable
    max_token_size: int | None = None
    send_dimensions: bool = (
        False
    )
    
    async def __call__(self, *args, **kwargs) -> np.ndarray:
        # only start when embedding_dim be given
        if self.send_dimensions:
            if "embedding_dim" in kwargs:
                model_dim = kwargs["embedding_dim"]
                
                if model_dim is None and model_dim != self.embedding_dim:
                    logger.warning(
                        f"Ignoring user-provided embedding_dim={model_dim}, "
                        f"using declared embedding_dim={self.embedding_dim} from decorator"
                    )

            kwargs["embedding_dim"] = self.embedding_dim
            
        return await self.func(*args, **kwargs)

class TextChunkSchema(TypedDict):
    tokens: int
    content: str
    full_doc_id: str
    chunk_order_index: int
    
    
    
@dataclass
class StorageNameSpace(ABC):
    namespace: str 
    workspace: str 
    
    async def initialize(self):
        # initialize storage
        pass
    
    async def finalize(self):
        # finalize the storage
        pass
    
    @abstractmethod
    async def index_done_callback(self) -> None:
        """commit the storage operations after indexing"""

    @abstractmethod
    async def drop(self) -> dict[str,str]:
        """Drop all data from storage and clean up resources

        This abstract method defines the contract for dropping all data from a storage implementation.
        Each storage type must implement this method to:
        1. Clear all data from memory and/or external storage
        2. Remove any associated storage files if applicable
        3. Reset the storage to its initial state
        4. Handle cleanup of any resources
        5. Notify other processes if necessary
        6. This action should persistent the data to disk immediately.

        Returns:
            dict[str, str]: Operation status and message with the following format:
                {
                    "status": str,  # "success" or "error"
                    "message": str  # "data dropped" on success, error details on failure
                }

        Implementation specific:
        - On success: return {"status": "success", "message": "data dropped"}
        - On failure: return {"status": "error", "message": "<error details>"}
        - If not supported: return {"status": "error", "message": "unsupported"}
        """

    
    
@dataclass
class BaseVectorStorage(StorageNameSpace, ABC):
    embedding_func: EmbeddingFunc
    cosine_similarity_threshold: float = field(default=0.4)
    meta_fields: set[str] = field(default_factory=set)
    
    @abstractmethod
    async def query(self, *args, **kwargs):
        # query the vector storage and retrieve top k results
        """Query the vector storage and retrieve top_k results.

        Args:
            query: The query string to search for
            top_k: Number of top results to return
            query_embedding: Optional pre-computed embedding for the query.
                           If provided, skips embedding computation for better performance.
        """
    
    @abstractmethod
    async def upsert(self, data: dict[str, dict[str, Any]]) -> None:
        """
        insert update vectors in the storage.
        implement notes for in-memory storage:
        1. changes will be persisted to disk during the next index_done_callback
        2. only ine process should updating the storage at a time before index_done_callback, 
        KG-storage-log should be used to avoid data corruption
        """
        
    
    # to fetch relate vector by id
    @abstractmethod
    async def get_by_id(self, id: str) -> dict[str, Any] | None:
        """get vector data by its ID
        Args:
            id: the unique identifier of the vector
            
        returns:
        the vector data if found, or None if not found
        """
    
        
    @abstractmethod
    async def get_vectors_by_ids(self, id: str) -> None:
        """get vector by their IDs, returning only ID and vector data for efficiency
        Args:
            id: the unique identifier of the vector
            
        return:
            dictionary mapping IDs to their vector embeddings
            format: {"id1": [vector1],....}
        """
    



@dataclass
class BaseKVStorage(StorageNameSpace, ABC):
    embedding_func: EmbeddingFunc

    @abstractmethod
    async def get_by_ids(self, ids: list[str]) -> list[dict[str, Any]]:
        """Get values by ids"""

    @abstractmethod
    async def filter_keys(self, keys: set[str]) -> set[str]:
        """Return un-exist keys"""

    @abstractmethod
    async def upsert(self, data: dict[str, dict[str, Any]]) -> None:
        """Upsert data

        Importance notes for in-memory storage:
        1. Changes will be persisted to disk during the next index_done_callback
        2. update flags to notify other processes that data persistence is needed
        """

    @abstractmethod
    async def delete(self, ids: list[str]) -> None:
        """Delete specific records from storage by their IDs

        Importance notes for in-memory storage:
        1. Changes will be persisted to disk during the next index_done_callback
        2. update flags to notify other processes that data persistence is needed

        Args:
            ids (list[str]): List of document IDs to be deleted from storage

        Returns:
            None
        """

    @abstractmethod
    async def is_empty(self) -> bool:
        """Check if the storage is empty

        Returns:
            bool: True if storage contains no data, False otherwise
        """




        

