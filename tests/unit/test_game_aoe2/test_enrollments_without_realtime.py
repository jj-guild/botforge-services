"""The enrollments without the realtime provider (owner 2026-11-27).

aoe2lobby rides disabled in the delivery: the enrollment push must
read it as a healthy steady state - applied=True (the core's retry
loop never warns) and the STATS provider still subscribes (the
on-demand history sync, T4).
"""

from __future__ import annotations

from typing import Any

import pytest


class _Aggregator:
    def __init__(self) -> None:
        self.roster: list[dict[str, Any]] = []

    def set_roster(self, roster: list[dict[str, Any]]) -> None:
        self.roster = roster


@pytest.mark.asyncio
async def test_without_the_realtime_uri_the_enrollments_stand(monkeypatch: Any) -> None:
    """No EXT_AOE2LOBBY_URI: applied=True, the stats provider subscribes."""
    from botforge.game_aoe2.server import _EnrollmentPusher

    monkeypatch.delenv("EXT_AOE2LOBBY_URI", raising=False)
    stats_calls: list[tuple[list[str], list[str]]] = []

    class _StatsClient:
        def __init__(self, uri: str, provider: str, game: str) -> None:
            del uri, provider, game

        async def update_subscriptions(
            self, profile_ids: list[str], user_ids: list[str]
        ) -> bool:
            stats_calls.append((list(profile_ids), list(user_ids)))
            return True

    import botforge.core.rpc.game_client as game_client

    monkeypatch.setattr(game_client, "GameProviderClient", _StatsClient, raising=False)
    monkeypatch.setenv("EXT_LIBREMATCH_URI", "botforge-ext-librematch:50061")
    pusher = _EnrollmentPusher(_Aggregator())
    applied = await pusher.apply("aoe2", ["848567"], ["123"])
    assert applied == (1, True), "no realtime provider: the enrollments STAND, no retry warn"
    assert stats_calls == [(["848567"], ["123"])], "the stats provider still subscribes (T4)"


@pytest.mark.asyncio
async def test_a_failing_realtime_provider_still_warns(monkeypatch: Any) -> None:
    """A WIRED realtime provider that refuses: applied=False, the warn."""
    from botforge.game_aoe2.server import _EnrollmentPusher

    class _RefusingClient:
        def __init__(self, uri: str, provider: str, game: str) -> None:
            del uri, provider, game

        async def update_subscriptions(self, profile_ids: list[str], user_ids: list[str]) -> bool:
            raise RuntimeError("refused")

    import botforge.core.rpc.game_client as game_client

    monkeypatch.setattr(game_client, "GameProviderClient", _RefusingClient, raising=False)
    monkeypatch.setenv("EXT_AOE2LOBBY_URI", "botforge-ext-aoe2lobby:50062")
    monkeypatch.delenv("EXT_LIBREMATCH_URI", raising=False)
    pusher = _EnrollmentPusher(_Aggregator())
    applied = await pusher.apply("aoe2", ["848567"], ["123"])
    assert applied == (1, False), "a wired-but-refusing provider stays a failure (the retry warns)"
