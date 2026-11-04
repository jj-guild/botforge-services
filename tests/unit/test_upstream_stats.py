"""Unit tests for the provider-owned upstream call statistics."""

from __future__ import annotations

from kingdoms.core.upstream_stats import StatsRegistry, UpstreamStats


def test_record_ok_and_snapshot() -> None:
    stats = UpstreamStats("liquipedia:aoe2")
    stats.record(True, 120.0)
    stats.record(True, 80.0)
    snap = stats.snapshot()
    assert snap["ok"] is True
    assert snap["total_calls"] == 2
    assert snap["total_errors"] == 0
    assert snap["consecutive_failures"] == 0
    assert snap["avg_latency_ms"] == 100
    assert snap["last_call_at"] > 0
    assert snap["never_called"] is False


def test_consecutive_failures_and_last_error() -> None:
    stats = UpstreamStats("librematch")
    stats.record(True, 50.0)
    stats.record(False, 10.0, "HTTPStatusError: 429")
    stats.record(False, 10.0, "ConnectError: boom")
    snap = stats.snapshot()
    assert snap["ok"] is False
    assert snap["consecutive_failures"] == 2
    assert snap["total_errors"] == 2
    assert "ConnectError" in snap["last_error"]


def test_context_manager_records_success_and_failure() -> None:
    stats = UpstreamStats("aoe2lobby:ws")
    with stats:
        pass
    assert stats.snapshot()["ok"] is True
    try:
        with stats:
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    snap = stats.snapshot()
    assert snap["consecutive_failures"] == 1
    assert "RuntimeError" in snap["last_error"]


def test_never_called_and_last_minute_window() -> None:
    stats = UpstreamStats("nothing")
    snap = stats.snapshot()
    assert snap["never_called"] is True
    assert snap["ok"] is False
    stats.record(True, 5.0)
    stats.record(False, 5.0, "x")
    snap = stats.snapshot()
    assert snap["calls_last_minute"] == 2
    assert snap["errors_last_minute"] == 1


def test_registry_serves_every_upstream_sorted() -> None:
    registry = StatsRegistry()
    registry.register("b-upstream").record(True, 1.0)
    registry.register("a-upstream").record(True, 2.0)
    snap = registry.snapshot()
    assert [e["upstream"] for e in snap] == ["a-upstream", "b-upstream"]
