from pathlib import Path
import os
import asyncio
from dataclasses import dataclass
from typing import final, Any

from .....log.logger import logger
from .json_process import write_json, load_json
from .base import BaseKVStorage

"""
the data structure in json 
{
    "custom_id_1": "meta": {
        "_id": "custom_id_1",
        "create_time",
        "updata_time",
        "llm_cache_list'
        }
}

"""
@final
@dataclass
class KVStorage(BaseKVStorage):
    def __post_init__(self):
        # Resolve workspace under ./rag_cache unless an absolute path is provided
        workspace_dir = Path(self.workspace)
        if not workspace_dir.is_absolute():
            workspace_dir = Path(".") / "rag_cache" / self.workspace

        workspace_dir.mkdir(parents=True, exist_ok=True)
        self.workspace_dir = workspace_dir
        self._file_name = workspace_dir / f"kv_store_{self.namespace}.json"
        
        # initial parameters
        self._data = {}
        self._storage_lock = asyncio.Lock()
        
    async def initialize(self):
        """ initialze staorage data and lock file """
        async with self._storage_lock:
            if self._file_name.exists():
                self._data = load_json(self._file_name) or {}
            else:
                self._data = {}

        logger.info(f"[{self.workspace}] KV storage initialized.")
        
    # implement father abstract method
    async def index_done_callback(self):
        async with self._storage_lock:
            data_dict = (
                dict(self._data) if hasattr(self._data, "_getvalue") else self._data
            )
            data_count = len(data_dict)
            
            logger.debug(
               f"[{self.workspace}] Process {os.getpid()} KV writting {data_count} records to {self.namespace}"
            )
            
            # Write JSON and check if sanitization was applied
            needs_reload = write_json(data_dict, self._file_name)

            # If data was sanitized, reload cleaned data to update shared memory
            if needs_reload:
                logger.info(
                    f"[{self.workspace}] Reloading sanitized data into shared memory for {self.namespace}"
                )
                cleaned_data = load_json(self._file_name)
                if cleaned_data is not None:
                    self._data.clear()
                    self._data.update(cleaned_data)   
            
            
                
    # implement father abstract method
    async def get_by_id(self, id: str) -> dict[str, Any] | None:
        async with self._storage_lock:
            result = self._data.get(id, None)
            if result:
                result = dict(result)
                result.setdefault("create_time", 0)
                result.setdefault("updata_time", 0)
                result["_id"] = id
            
            return result
    
    # implement father abstract method
    async def get_by_ids(self, ids: list[str]) -> list[dict[str, Any]]:
        async with self._storage_lock:
            result = []
            for id in ids:
                data = self._data.get(id, None)
                if data:
                    data = dict(data)
                    data.setdefault("create_time", 0)
                    data.setdefault("updata_time", 0)
                    data["_id"] = id
                    result.append(data)
                else:
                    result.append(None)
            return result
        
    
    async def filter_keys(self, keys):
        async with self._storage_lock:
            return set(keys) - set(self._data.keys())
        
    
    async def upsert(self, data: dict[str, dict[str, Any]]) -> None:
        # change the storage data
        if not data:
            return 
        import time
        
        current_time = int(time.time())
        
        logger.debug(
            f"[{self.workspace}] KV storage: upserting {len(data)} vectors."
        )
        
        async with self._storage_lock:
            # add timestamps to data based on whether key exist
            for k, v in data.items():
                if self.namespace.endswith("text_chunk"):
                    if "llm_cache_list" not in v:
                        v["llm_cache_list"] = []
                        
                if k in self._data:
                    v["update_time"] = current_time
                else:
                    v["create_time"] = current_time
                    v["update_time"] = current_time
                
                v["_id"] = k
                
            # update data
            self._data.update(data)
            
            # write data to file
    
    async def delete(self, ids):
        # delete specific records form storage by their IDs
        
        async with self._storage_lock:
            any_deleted = False
            for doc_id in ids:
                result = self._data.pop(doc_id, None)
                if result:
                    any_deleted = True
    
    async def is_empty(self):
        async with self._storage_lock:
            return len(self._data) == 0
        
    
    async def drop(self):
        # drop all json data 
        try:
            async with self._storage_lock:
                self._data.clear()
            
            logger.info(
                f"[{self.workspace}] Process {os.getpid()} drop {self.namespace}"
            )  
            return {"status": "success", "message": "data dropped"}

        except Exception as e:
            logger.error(f"[{self.workspace}] Error dropping data: {e}")
            return {"status": "error", "message": f"Error dropping data: {e}"}
        
    async def _migrate_legay_cache_structure(self, data: dict) -> dict:
        """Migrate legacy nested cache structure to flattened structure.
        
        arg: 
            dara: original dictionary 
        """
        pass
    
    async def finalize(self):
        """
        finalize storage resources
        persistnace cache data to disk before exit"""
        
        if self.namespace.endswith("_cache"):
            async with self._storage_lock:
                await self.index_done_callback()
