"""Priority queue for audit jobs (binary heap, O(log n))."""

from __future__ import annotations

import heapq
import itertools
from typing import Generic, TypeVar

T = TypeVar("T")


class PriorityQueue(Generic[T]):
    """A min-priority queue. Lower priority values are served first."""

    __slots__ = ("_heap", "_counter")

    def __init__(self) -> None:
        self._heap: list[tuple[float, int, T]] = []
        self._counter = itertools.count()

    def push(self, item: T, priority: float = 0.0) -> None:
        """Insert an item in O(log n)."""
        heapq.heappush(self._heap, (priority, next(self._counter), item))

    def pop(self) -> T:
        """Remove and return the highest-priority item in O(log n)."""
        if not self._heap:
            raise IndexError("pop from an empty priority queue")
        return heapq.heappop(self._heap)[2]

    def peek(self) -> T:
        if not self._heap:
            raise IndexError("peek from an empty priority queue")
        return self._heap[0][2]

    def is_empty(self) -> bool:
        return not self._heap

    def __len__(self) -> int:
        return len(self._heap)


__all__ = ["PriorityQueue"]
