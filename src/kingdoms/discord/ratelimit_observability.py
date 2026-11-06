"""Discord rate-limit observability — the buckets, logged.

Discord answers every request with rate-limit headers (X-Ratelimit-Limit,
-Remaining, -Reset-After, -Bucket — see
https://docs.discord.com/developers/topics/rate-limits). discord.py
consumes them internally (its Ratelimit buckets) but logs almost nothing:
the 2026-11-06 channel-creation throttle (~7 h) surfaced as a bare
"see the bot logs".

This module subclasses discord.py's HTTPClient and logs each route's
bucket state after every request:

- DEBUG: the full bucket line (limit, remaining, reset-after, bucket)
- INFO: when a bucket is about to exhaust (remaining <= 1)
- WARNING: when discord.py raises RateLimited (the retry-after with the
  bucket)

The install is DEFENSIVE: it patches the class reference discord.Client
uses, and a discord.py upgrade that changes the internals degrades to
the stock client with a warning — never a crash.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("kingdoms.discord.ratelimit")


def install() -> None:
    """Patch the bot's HTTPClient with the rate-limit-logging subclass.

    Call ONCE, before the discord.Client is instantiated (the bot's
    factory does it at build time).
    """
    import discord
    import discord.client
    import discord.http

    base = discord.http.HTTPClient

    class RateLimitLoggingHTTPClient(base):  # type: ignore[misc,valid-type]
        """The stock client, plus the bucket logging."""

        async def request(self, route: Any, *args: Any, **kwargs: Any) -> Any:
            try:
                data = await super().request(route, *args, **kwargs)
            except discord.errors.RateLimited as exc:
                bucket = self._bucket_of(route)
                logger.warning(
                    "RATE LIMIT RAISED: %s %s — retry_after=%.0fs %s",
                    route.method,
                    route.url,
                    exc.retry_after,
                    self._bucket_line(bucket),
                )
                raise
            bucket = self._bucket_of(route)
            line = self._bucket_line(bucket)
            remaining = getattr(bucket, "remaining", None)
            if remaining is not None and remaining <= 1:
                logger.info("RATE LIMIT TIGHT: %s %s %s", route.method, route.url, line)
            else:
                logger.debug("RATE LIMIT: %s %s %s", route.method, route.url, line)
            return data

        def _bucket_of(self, route: Any) -> Any:
            """Resolve the route's ratelimit bucket (defensive)."""
            try:
                key = route.key
                major = getattr(route, "major_parameters", "")
                bucket_hash = self._bucket_hashes.get(key)
                bucket_key = (
                    f"{bucket_hash}:{major}" if bucket_hash else f"{key}:{major}"
                )
                return self._buckets.get(bucket_key)
            except Exception:
                return None

        @staticmethod
        def _bucket_line(bucket: Any) -> str:
            """Render the bucket's state (the headers' values)."""
            if bucket is None:
                return "(no bucket yet)"
            limit = getattr(bucket, "limit", "?")
            remaining = getattr(bucket, "remaining", "?")
            reset_after = getattr(bucket, "reset_after", None)
            reset = f"reset_after={reset_after:.1f}s" if reset_after else "reset_after=?"
            return f"bucket limit={limit} remaining={remaining} {reset}"

    try:
        discord.client.HTTPClient = RateLimitLoggingHTTPClient  # type: ignore[attr-defined]
        logger.info("rate-limit observability installed")
    except Exception:
        logger.warning("rate-limit observability could not install — the stock client serves", exc_info=True)
