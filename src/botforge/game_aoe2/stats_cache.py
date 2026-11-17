"""The game service's stats answer cache (#404 T4).

A click never costs a provider call: the GameData proxies cache the
stats answers with adapted TTLs — Redis when the service runs with a
``REDIS_URI`` (shared across restarts), an in-memory dict otherwise
(the dev sandbox). The sync (periodic + on-demand) refreshes the
source; the cache only paces the reads.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Protocol

logger = logging.getLogger("botforge.game_aoe2.stats_cache")

TTL_USER_STATS_S = 600
TTL_ACCOUNT_STATS_S = 600
TTL_MATCH_HISTORY_S = 300


class _RedisLike(Protocol):
    """The narrow Redis seam (redis.asyncio client or a test double)."""

    async def get(self, key: str) -> Any: ...

    async def set(self, key: str, value: str, ex: int = 0) -> Any: ...


class StatsCache:
    """A TTL cache over the provider's stats answers."""

    def __init__(self, redis_client: _RedisLike | None = None) -> None:
        self._redis = redis_client
        self._memory: dict[str, tuple[float, str]] = {}

    async def get_json(self, key: str) -> Any | None:
        """Return the cached JSON value; None when absent or expired."""
        if self._redis is not None:
            try:
                raw = await self._redis.get(key)
            except Exception:
                logger.warning("stats cache read failed (key %s)", key, exc_info=True)
                return None
            return json.loads(raw) if raw else None
        expires_at, raw = self._memory.get(key, (0.0, ""))
        if not raw or expires_at < time.time():
            self._memory.pop(key, None)
            return None
        return json.loads(raw)

    async def set_json(self, key: str, value: Any, ttl_s: int) -> None:
        """Cache one JSON value for ``ttl_s`` seconds (best-effort)."""
        raw = json.dumps(value)
        if self._redis is not None:
            try:
                await self._redis.set(key, raw, ex=max(1, ttl_s))
                return
            except Exception:
                logger.warning("stats cache write failed (key %s)", key, exc_info=True)
                return
        self._memory[key] = (time.time() + ttl_s, raw)


def _key(prefix: str, parts: list[str]) -> str:
    """Build one cache key from the request's stable parts."""
    return "botforge:stats:" + prefix + ":" + "|".join(sorted(str(p) for p in parts))
