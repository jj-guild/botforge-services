"""The game service's stats answer cache (#404 T4).

A click never costs a provider call: the TTL cache paces the reads —
Redis when configured, the in-memory dict otherwise (the dev sandbox).
"""

from __future__ import annotations

import time

from botforge.game_aoe2.stats_cache import StatsCache, _key


class _FakeRedis:
    """A minimal async Redis stand-in (get/set with expiry)."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int = 0) -> None:
        self.store[key] = value


async def test_memory_cache_round_trip() -> None:
    """The in-memory cache serves the JSON value until it expires."""
    cache = StatsCache()
    key = _key("user", ["alice", "30"])
    assert await cache.get_json(key) is None
    await cache.set_json(key, {"known": True}, ttl_s=60)
    assert await cache.get_json(key) == {"known": True}


async def test_memory_cache_expires() -> None:
    """An expired entry reads as a miss."""
    cache = StatsCache()
    key = _key("account", ["123"])
    await cache.set_json(key, [1], ttl_s=1)
    # force the expiry without sleeping a real second
    cache._memory[key] = (time.time() - 2, cache._memory[key][1])
    assert await cache.get_json(key) is None


async def test_redis_cache_round_trip() -> None:
    """The Redis-backed cache serves the same contract."""
    redis = _FakeRedis()
    cache = StatsCache(redis)
    key = _key("history", ["123", "50"])
    await cache.set_json(key, {"matches": []}, ttl_s=300)
    assert redis.store, "the value landed in Redis with its TTL"
    assert await cache.get_json(key) == {"matches": []}
