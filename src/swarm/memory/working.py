import asyncio
from collections import OrderedDict
from typing import Any
import structlog

logger = structlog.get_logger()


class WorkingMemory:
    def __init__(self, max_size_mb: float = 100):
        self._store: OrderedDict[str, Any] = OrderedDict()
        self._max_size_mb = max_size_mb
        self._lock = asyncio.Lock()

    async def put(self, key: str, value: Any) -> None:
        async with self._lock:
            if key in self._store:
                del self._store[key]
            self._store[key] = value
            self._store.move_to_end(key)
            logger.debug("working_memory_put", key=key)

    async def get(self, key: str, default: Any = None) -> Any:
        async with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
                return self._store[key]
            return default

    async def get_many(self, keys: list[str]) -> dict[str, Any]:
        async with self._lock:
            return {k: self._store[k] for k in keys if k in self._store}

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._store.pop(key, None)
            logger.debug("working_memory_delete", key=key)

    async def clear(self) -> None:
        async with self._lock:
            self._store.clear()
            logger.debug("working_memory_cleared")

    async def keys(self) -> list[str]:
        async with self._lock:
            return list(self._store.keys())

    async def has(self, key: str) -> bool:
        async with self._lock:
            return key in self._store
