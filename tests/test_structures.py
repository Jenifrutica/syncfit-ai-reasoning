import pytest

from syncfit_ai.structures import LRUCache, PriorityQueue


def test_priority_queue_orders_by_priority():
    queue: PriorityQueue[str] = PriorityQueue()
    queue.push("low", priority=10)
    queue.push("high", priority=1)
    queue.push("mid", priority=5)
    assert [queue.pop() for _ in range(3)] == ["high", "mid", "low"]


def test_priority_queue_is_stable():
    queue: PriorityQueue[str] = PriorityQueue()
    queue.push("first", priority=1)
    queue.push("second", priority=1)
    assert queue.pop() == "first"
    assert queue.pop() == "second"


def test_priority_queue_empty_errors():
    queue: PriorityQueue[int] = PriorityQueue()
    assert queue.is_empty()
    with pytest.raises(IndexError):
        queue.pop()
    with pytest.raises(IndexError):
        queue.peek()


def test_lru_cache_evicts_least_recently_used():
    cache: LRUCache[str, int] = LRUCache(capacity=2)
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.get("a") == 1  # 'a' becomes most recent
    cache.put("c", 3)  # evicts 'b'
    assert cache.get("b") is None
    assert cache.get("a") == 1
    assert cache.get("c") == 3
    assert cache.hits == 3
    assert cache.misses == 1


def test_lru_cache_invalid_capacity():
    with pytest.raises(ValueError):
        LRUCache(capacity=0)
