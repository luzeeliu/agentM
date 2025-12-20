import json
import os
from inspect import Parameter, signature
from pathlib import Path
from typing import Any, Dict, List, Optional

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
    Lightweight wrapper around mem0 to store and search agent memories.

    Configuration:
    - MEM0_CONFIG: Optional path to a JSON config file or a JSON string.
    - MEM0_NAMESPACE: Logical namespace tag stored with each memory (default: "default").
    """

    def __init__(self, user_id: str, namespace: Optional[str] = None, config_path: Optional[str] = None):
        self.user_id = user_id
        self.namespace = namespace or os.getenv("MEM0_NAMESPACE", "default")
        self.config_path = config_path or os.getenv("MEM0_CONFIG")
        self.memory = self._init_memory()

    def _init_memory(self):
        if Memory is None:
            raise Mem0MemoryError(
                "mem0 is not installed. Add `mem0` to requirements and install the package to enable long-term memory."
            )

        config = self._load_config()
        errors: List[str] = []

        if hasattr(Memory, "from_config"):
            if config is not None:
                try:
                    return Memory.from_config(config)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"from_config(config) failed: {exc}")
            try:
                return Memory.from_config()
            except Exception as exc:  # noqa: BLE001
                errors.append(f"from_config() failed: {exc}")

        try:
            return Memory()
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Memory() failed: {exc}")

        raise Mem0MemoryError(f"Unable to initialize mem0 client: {'; '.join(errors) if errors else 'unknown error'}")

    def _load_config(self) -> Optional[Any]:
        if not self.config_path:
            return None

        path = Path(self.config_path)
        if path.exists():
            raw = path.read_text(encoding="utf-8")
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return raw

        try:
            return json.loads(self.config_path)
        except json.JSONDecodeError:
            return None

    def _call_mem0(self, method_name: str, *args: Any, **kwargs: Any) -> Any:
        method = getattr(self.memory, method_name, None)
        if method is None:
            raise Mem0MemoryError(f"mem0 client does not expose '{method_name}'")

        sig = signature(method)
        accepts_kwargs = any(param.kind == Parameter.VAR_KEYWORD for param in sig.parameters.values())
        filtered_kwargs: Dict[str, Any]
        if accepts_kwargs:
            filtered_kwargs = kwargs
        else:
            filtered_kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}
        return method(*args, **filtered_kwargs)

    def _with_namespace_metadata(self, metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        meta: Dict[str, Any] = dict(metadata) if metadata else {}
        meta.setdefault("namespace", self.namespace)
        return meta

    def add_fact(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> Any:
        """Store a single fact for the user."""
        meta = self._with_namespace_metadata(metadata)
        return self._call_mem0("add", text, user_id=self.user_id, metadata=meta)

    def add_interaction(
        self, user_message: str, ai_message: str, metadata: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Persist a chat turn."""
        meta = self._with_namespace_metadata(metadata)
        meta.setdefault("type", "interaction")
        payload = f"[user]\n{user_message}\n\n[assistant]\n{ai_message}"
        return self._call_mem0("add", payload, user_id=self.user_id, metadata=meta)

    def search(self, query: str, limit: int = 5) -> Any:
        """Search for relevant memories for this user."""
        return self._call_mem0("search", query, user_id=self.user_id, limit=limit, namespace=self.namespace)

    def get_all(self) -> List[Any]:
        """Fetch all memories for this user (may fallback to search if get_all is unavailable)."""
        if hasattr(self.memory, "get_all"):
            result = self._call_mem0("get_all", user_id=self.user_id, namespace=self.namespace)
            return list(result) if isinstance(result, list) else [result] if result else []
        return list(self.search("", limit=100)) if hasattr(self.memory, "search") else []

    def update(self, memory_id: str, new_text: str, metadata: Optional[Dict[str, Any]] = None) -> Any:
        """Update an existing memory by id."""
        meta = self._with_namespace_metadata(metadata)
        return self._call_mem0("update", memory_id, new_text, user_id=self.user_id, metadata=meta)

    def delete(self, memory_id: str) -> Any:
        """Delete a memory by id."""
        return self._call_mem0("delete", memory_id, user_id=self.user_id)

    def clear_user(self) -> List[str]:
        """Delete all memories for the user."""
        deleted: List[str] = []
        for item in self.get_all():
            memory_id = self._extract_id(item)
            if not memory_id:
                continue
            try:
                self.delete(memory_id)
                deleted.append(memory_id)
            except Exception:  # noqa: BLE001
                continue
        return deleted

    @staticmethod
    def _extract_id(entry: Any) -> Optional[str]:
        if isinstance(entry, dict):
            for key in ("id", "memory_id", "_id"):
                if key in entry:
                    return str(entry[key])
        return None
