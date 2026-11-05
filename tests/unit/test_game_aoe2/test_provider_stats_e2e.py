"""End-to-end: the providers panel's data path over real gRPC.

The panel asks the game service; the game service fetches its providers'
stats concurrently and answers with every provider. This test spins REAL
gRPC servers (a provider with recorded stats, a dead port) and runs the
full aggregation — the wire, not mocks.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest


async def _spin_stats_server(port: int) -> asyncio.Event:
    """Bind a Status server with recorded stats on localhost:<port>."""
    from kingdoms import __version__
    from kingdoms.core.rpc.status import CoreStatus, build_status_server_with_stats
    from kingdoms.core.upstream_stats import StatsRegistry

    registry = StatsRegistry()
    registry.register("liquipedia:aoe2").record(True, 120.0)
    registry.register("liquipedia:aoe2").record(False, 900.0, "HTTPStatusError: 429")
    server = build_status_server_with_stats(
        lambda: CoreStatus(version=__version__, process="ext-liquipedia"),
        stats_provider=registry.snapshot,
    )
    server.add_insecure_port(f"[::]:{port}")
    await server.start()
    stop = asyncio.Event()

    async def _stop() -> None:
        await stop.wait()
        await server.stop(0)

    asyncio.get_running_loop().create_task(_stop())
    return stop


@pytest.mark.asyncio
async def test_panel_fetch_through_game_service(monkeypatch: Any) -> None:

    stop = await _spin_stats_server(50971)
    try:
        # the game service's aggregation, pointed at the live provider and
        # a dead port (the 'unreachable' path)
        monkeypatch.setenv("EXT_LIBREMATCH_URI", "127.0.0.1:50972")  # dead
        monkeypatch.setenv("EXT_AOE2LOBBY_URI", "")
        monkeypatch.setenv("EXT_AOE2TECHTREE_URI", "")
        monkeypatch.setenv("EXT_LIQUIPEDIA_URI", "127.0.0.1:50971")
        from kingdoms.game_aoe2.server import _aggregate_provider_stats

        entries = await asyncio.wait_for(_aggregate_provider_stats(), timeout=10.0)
    finally:
        stop.set()
    by_provider = {e["provider_id"]: e for e in entries}
    # the live provider's stats came over the wire, tagged with its id
    live = by_provider["ext-liquipedia"]
    assert live["upstream"] == "liquipedia:aoe2"
    assert live["total_calls"] == 2
    assert live["consecutive_failures"] == 1
    assert "429" in live["last_error"]
    # the dead port answers 'unreachable', the missing URIs 'not deployed'
    assert by_provider["ext-librematch"]["detail"].startswith("unreachable")
    assert by_provider["ext-aoe2lobby"]["detail"] == "not deployed"
    # and the panel renders it all without raising
    from kingdoms.discord.providers_panel import _render_view

    view = _render_view({"entries": entries}, None, "fr")
    assert view is not None
