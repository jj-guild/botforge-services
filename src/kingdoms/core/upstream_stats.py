"""Upstream call statistics — the provider-owned health signal.

A provider process records every call it makes to its real upstream
(Liquipedia's MediaWiki, librematch's API, aoe2lobby's WebSocket...):
success or failure, latency, the last error. The counters live IN the
provider process — the only place that sees the calls — and are served
over the Status contract (``GetUpstreamStats``): the providers panel
asks, the provider answers with its own truth.

This replaces the active prober (owner direction 2026-11-04): no
synthetic ping ever touches an upstream again — a probe was indistinguishable
from real traffic for the rate-limited APIs, and it failed exactly when
the real traffic was being throttled, adding insult to injury.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any, Literal


class UpstreamStats:
    """Thread-safe call counters for one named upstream.

    Records are cheap (a lock, a few counters, a bounded ring of the
    last calls for the one-minute window). ``snapshot`` renders the
    wire-ready dict — never a live reference.
    """

    def __init__(self, upstream: str, window_s: float = 60.0, ring_size: int = 1024) -> None:
        self._upstream = upstream
        self._window_s = window_s
        self._ring: deque[tuple[float, bool, float]] = deque(maxlen=ring_size)
        self._lock = threading.Lock()
        self._consecutive_failures = 0
        self._total = 0
        self._errors = 0
        self._last_error = ""
        self._last_call_at = 0.0
        self._last_ok_at = 0.0
        self._enter_at = 0.0

    @property
    def upstream(self) -> str:
        """The upstream's name (the stats' key)."""
        return self._upstream

    def record(self, ok: bool, latency_ms: float, error: str = "") -> None:
        """Record one upstream call's outcome."""
        now = time.time()
        with self._lock:
            self._ring.append((now, ok, latency_ms))
            self._total += 1
            self._last_call_at = now
            if ok:
                self._consecutive_failures = 0
                self._last_ok_at = now
            else:
                self._errors += 1
                self._consecutive_failures += 1
                if error:
                    self._last_error = error[:200]

    def __enter__(self) -> UpstreamStats:
        """Context-manager form: ``with STATS.register("upstream"): call()``."""
        self._enter_at = time.monotonic()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> Literal[False]:
        """Record the call's outcome on exit; never swallow the exception."""
        latency_ms = (time.monotonic() - self._enter_at) * 1000
        if exc_type is None:
            self.record(True, latency_ms)
        else:
            self.record(False, latency_ms, f"{exc_type.__name__}: {exc}")
        return False  # never swallow

    def snapshot(self) -> dict[str, Any]:
        """Render the wire-ready stats (never a live reference)."""
        now = time.time()
        with self._lock:
            window = [e for e in self._ring if now - e[0] <= self._window_s]
            ok = all(e[1] for e in self._ring) and bool(self._ring)
            latencies = [e[2] for e in window] or [0.0]
            return {
                "upstream": self._upstream,
                "ok": ok and self._consecutive_failures == 0,
                "never_called": not self._ring,
                "total_calls": self._total,
                "total_errors": self._errors,
                "consecutive_failures": self._consecutive_failures,
                "last_call_at": int(self._last_call_at * 1000),
                "last_ok_at": int(self._last_ok_at * 1000),
                "calls_last_minute": len(window),
                "errors_last_minute": sum(1 for e in window if not e[1]),
                "avg_latency_ms": int(sum(latencies) / len(latencies)),
                "last_error": self._last_error,
            }


class StatsRegistry:
    """The process-wide set of upstreams it calls — served over gRPC."""

    def __init__(self) -> None:
        self._stats: dict[str, UpstreamStats] = {}
        self._lock = threading.Lock()

    def register(self, upstream: str) -> UpstreamStats:
        """Get (creating on first use) the recorder for one upstream."""
        with self._lock:
            if upstream not in self._stats:
                self._stats[upstream] = UpstreamStats(upstream)
            return self._stats[upstream]

    def snapshot(self) -> list[dict[str, Any]]:
        """Render every upstream's stats, sorted by name."""
        with self._lock:
            names = sorted(self._stats)
        return [self._stats[name].snapshot() for name in names]
