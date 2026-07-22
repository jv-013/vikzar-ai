"""Bounded thread-safe cache for verified immutable production models."""

from __future__ import annotations

from collections import OrderedDict
from threading import RLock
from typing import Generic, TypeVar

_ModelT = TypeVar("_ModelT")


class InferenceModelCache(Generic[_ModelT]):
    """Cache verified models by immutable evidence with deterministic LRU eviction."""

    def __init__(self, max_entries: int) -> None:
        if max_entries < 1:
            raise ValueError("Inference model cache size must be positive.")
        self._max_entries = max_entries
        self._entries: OrderedDict[str, _ModelT] = OrderedDict()
        self._lock = RLock()

    @property
    def size(self) -> int:
        """Return the current number of cached approved models."""

        with self._lock:
            return len(self._entries)

    def get(self, key: str) -> _ModelT | None:
        """Return and retain a cached model as the most recently used entry."""

        with self._lock:
            value = self._entries.get(key)
            if value is not None:
                self._entries.move_to_end(key)
            return value

    def put_if_absent(self, key: str, value: _ModelT) -> _ModelT:
        """Atomically publish one verified model, preserving any concurrent winner."""

        with self._lock:
            existing = self._entries.get(key)
            if existing is not None:
                self._entries.move_to_end(key)
                return existing
            self._entries[key] = value
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)
            return value

    def clear(self) -> None:
        """Drop in-memory copies without modifying immutable model artifacts."""

        with self._lock:
            self._entries.clear()
