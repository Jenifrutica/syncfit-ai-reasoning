"""Least-recently-used cache with O(1) amortized access."""

from __future__ import annotations

from collections import OrderedDict
from typing import Generic, Hashable, TypeVar

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


class LRUCache(Generic[K, V]):
    """Fixed-capacity LRU cache backed by an ordered dictionary."""

    __slots__ = ("_capacity", "_data", "hits", "misses")

    def __init__(self, capacity: int = 128) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be a positive integer")
        self._capacity = capacity
        self._data: OrderedDict[K, V] = OrderedDict()
        self.hits = 0
        self.misses = 0

    @property
    def capacity(self) -> int:
        return self._capacity

    def get(self, key: K) -> V | None:
        if key not in self._data:
            self.misses += 1
            return None
        self._data.move_to_end(key)
        self.hits += 1
        return self._data[key]

    def put(self, key: K, value: V) -> None:
        if key in self._data:
            self._data.move_to_end(key)
        self._data[key] = value
        if len(self._data) > self._capacity:
            self._data.popitem(last=False)

    def clear(self) -> None:
        self._data.clear()

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, key: object) -> bool:
        return key in self._data


__all__ = ["LRUCache"]
