import json
import os
from pathlib import Path
from pathlib import Path
from typing import Any, Dict, List, Optional
from ..log.logger import logger

import dotenv

dotenv.load_dotenv()

try:
    from mem0 import Memory
except ImportError:  # pragma: no cover - handled at runtime
    Memory = None


class Mem0MemoryError(RuntimeError):
    """Raised when the mem0-backed memory cannot be used."""


class Mem0Memory:
    """
    use normally mem0 build without graph relation
    parameter include 
    
    """
    _global_memory_instance = None

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.config_path = Path(__file__).resolve().parent / "mem0_config.json" or os.getenv("MEM0_CONFIG", None)
        self.config: Optional[Any] = None
        self.memory = self._init_memory()

    def _init_memory(self):
        if Memory is None:
            raise Mem0MemoryError(
                "mem0 is not installed. Add `mem0` to requirements and install the package to enable long-term memory."
            )
            
        if Mem0Memory._global_memory_instance is not None:
            if self.config is None:
                self.config = self._load_config()
            return Mem0Memory._global_memory_instance

        self.config = self._load_config()
        config = self.config
        errors: List[str] = []

        if config is not None:
            instance = Memory.from_config(config)
            Mem0Memory._global_memory_instance = instance
            return instance
        logger.error("[mem0] Failed to load valid configuration for mem0. in line 55")
        raise Mem0MemoryError(f"Unable to initialize mem0 client: {'; '.join(errors) if errors else 'unknown error'}")

    def _load_config(self) -> Optional[Any]:
        """Load config from json file or environment variable."""
        config = None
        config_path = self.config_path
        
        # If it's a Path object, try to read it
        if isinstance(config_path, Path):
            if config_path.exists():
                try:
                    raw = config_path.read_text(encoding="utf-8")
                    config = json.loads(raw)
                except Exception as e:
                    logger.error(f"[mem0] Failed to load config from {config_path}: {e}")
            else:
                logger.error(f"[mem0] Config file {config_path} does not exist.")
        elif isinstance(config_path, str):
            try:
                config = json.loads(config_path)
            except json.JSONDecodeError:
                path = Path(config_path)
                if path.exists():
                    config = json.loads(path.read_text(encoding="utf-8"))
        
        if config is None:
            logger.info(f"[mem0] No valid config found, using defaults.")
        return config

    def search(self, query: str, run_id = None) -> List[Dict[str, Any]]:
        """ Search memories by query """
        results = self.memory.search(
            query=query,
            user_id=self.user_id,
            # run_id is session specific
            run_id=run_id,
        )
        return results

    def add(self, messages: List[Any], session_id: str = None, infer: bool = True) -> None:
        user = self.user_id
        self.memory.add(
            messages=messages,
            user_id=user,
            run_id=session_id,
            infer=infer,
        )

    def clear_short_term_memory(self, session_id: str) -> None:
        """ Clear short-term memory for a specific session """
        self.memory.delete_all(
            user_id=self.user_id,
            run_id=session_id,
        )