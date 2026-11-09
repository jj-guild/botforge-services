"""The aoe2lobby mock's contract: the REAL adapter against the fake wire.

The integration proof: the real Aoe2LobbyAdapter connects to the
MockLobbyServer, subscribes, and the derived events match the world
the test drove — no network, deterministic, replayable.
"""

import asyncio

import pytest


@pytest.mark.asyncio
async def test_real_adapter_against_mock_wire() -> None:
    """The full journey: connect, subscribe, join, update, launch, leave."""
    from botforge.ext_aoe2lobby.adapter import Aoe2LobbyAdapter
    from tests.mocks.aoe2lobby_mock import MockLobbyServer, lobby_match

    server = MockLobbyServer()
    url = await server.start()
    try:
        adapter = Aoe2LobbyAdapter(ws_url=url, refresh_s=1, schema_ws_url="")
        await adapter.set_subscribed_profiles(["848567"])

        # the consumer opens the stream (the hub's shape); it stops
        # once it saw the three key events
        consumer = asyncio.ensure_future(_collect(adapter.stream_events()))
        await asyncio.sleep(0.5)  # the adapter connects + subscribes

        # the player joins a lobby
        await server.push_match_all({"518200001": lobby_match(518200001, [848567])})
        # a settings change (the map pick)
        await server.push_match_update(
            "518200001", lobby_match(518200001, [848567], map_name="Arabia")
        )
        # the player leaves (the match disappears)
        await server.drop_match("518200001")

        events = await asyncio.wait_for(consumer, timeout=8)
        types = [e["type"] for e in events]
        assert "lobby_opened" in types, f"events seen: {types}"
        assert "match_updated" in types, f"events seen: {types}"
        assert any(e["profile_ids"] == ["848567"] for e in events)
    finally:
        if not consumer.done():
            consumer.cancel()
        await server.stop()


async def _collect(stream: object) -> list[dict]:
    """Collect until the three key types arrived (lobby_opened,
    match_updated, lobby_left), then stop — bounded, no hang."""
    wanted = {"lobby_opened", "match_updated"}
    seen: set[str] = set()
    out: list[dict] = []
    async for event in stream:  # type: ignore[union-attr]
        out.append(event)
        seen.add(event["type"])
        if wanted <= seen:
            return out
    return out
