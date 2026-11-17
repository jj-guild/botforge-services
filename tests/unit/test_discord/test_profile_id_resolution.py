"""The insights/relic dual-id profile resolution (#402).

A player's aoe2insights user id is NOT always their relic id: the two
services issue their own identifiers. The validation seam must accept
EITHER id (the player never has to know which one they pasted), keep
BOTH on the binding, and answer an actionable error when nothing
resolves.
"""

from __future__ import annotations

import re
from typing import Any

import httpx
import pytest

from botforge.core.models.game import PlayerStats, StatsBlock, StatsEntry
from botforge.discord import registration_platform as platform
from botforge.discord.registration_platform import Aoe2ProfileValidationSeam

INSIGHTS_ID = "12488557"
RELIC_ID = "17190369"


class _FakeInsightsTransport(httpx.AsyncBaseTransport):
    """httpx stand-in of aoe2insights.com: plain-text relic-id pages."""

    def __init__(self, mapping: dict[str, str]) -> None:
        self.mapping = mapping

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        match = re.search(r"/user/(\d+)/relic-id/", str(request.url))
        if match and match.group(1) in self.mapping:
            return httpx.Response(200, text=self.mapping[match.group(1)])
        return httpx.Response(404, text="not found")


class _FakeProviderClient:
    """The provider stand-in: the relic id validates, nothing else."""

    def __init__(self, known_relic_ids: set[str]) -> None:
        self.known = known_relic_ids
        self.asked: list[str] = []

    async def get_capabilities(self) -> Any:
        class _Caps:
            player_stats = True

        return _Caps()

    async def get_player_stats(self, profile_id: str) -> PlayerStats | None:
        self.asked.append(profile_id)
        if profile_id not in self.known:
            return None
        return PlayerStats(
            profile_id=profile_id,
            blocks=(StatsBlock(name="identity", entries=(StatsEntry(key="alias", value="Someone"),)),),
        )


def _seam(monkeypatch: pytest.MonkeyPatch, client: _FakeProviderClient) -> Aoe2ProfileValidationSeam:
    """Build the seam with the fake provider and insights transports."""
    import botforge.game_aoe2.client as game_client_module

    seam = Aoe2ProfileValidationSeam(provider_uri="fake:123")
    monkeypatch.setattr(game_client_module, "GameDataClient", lambda uri: client)
    return seam


def _fake_insights(monkeypatch: pytest.MonkeyPatch, mapping: dict[str, str]) -> None:
    """Point the seam's resolver at the fake insights transport."""

    original = platform.resolve_relic_id_outcome

    async def _resolve_outcome(
        typed_id: str, transport: Any = None
    ) -> tuple[str | None, str]:
        return await original(typed_id, transport=_FakeInsightsTransport(mapping))

    monkeypatch.setattr(platform, "resolve_relic_id_outcome", _resolve_outcome)


def _fake_blocked_insights(monkeypatch: pytest.MonkeyPatch) -> None:
    """The live 2026-11-17 finding: the bot filter 403s the server."""

    async def _always_403(typed_id: str, transport: Any = None) -> tuple[str | None, str]:
        return None, platform.RELIC_BLOCKED

    monkeypatch.setattr(platform, "resolve_relic_id_outcome", _always_403)


async def test_insights_url_with_differing_ids_resolves_the_relic_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The #402 case: the URL's insights id differs from the relic id."""
    client = _FakeProviderClient({RELIC_ID})
    _fake_insights(monkeypatch, {INSIGHTS_ID: RELIC_ID})
    seam = _seam(monkeypatch, client)

    validated = await seam.validate_profile(
        f"https://www.aoe2insights.com/user/{INSIGHTS_ID}/"
    )
    assert validated is not None
    assert validated["profile_id"] == RELIC_ID  # the canonical relic id
    assert validated["site_ids"]["aoe2insights"] == INSIGHTS_ID  # both kept
    assert RELIC_ID in client.asked
    assert INSIGHTS_ID not in client.asked  # never validated as a relic id


async def test_relic_shaped_insights_url_validates_directly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The /user/relic/<id> shape carries the relic id — no resolution."""
    client = _FakeProviderClient({RELIC_ID})
    _fake_insights(monkeypatch, {})  # the resolver must NOT be consulted
    seam = _seam(monkeypatch, client)

    validated = await seam.validate_profile(
        f"https://www.aoe2insights.com/user/relic/{RELIC_ID}/"
    )
    assert validated is not None
    assert validated["profile_id"] == RELIC_ID
    assert client.asked == [RELIC_ID]


async def test_plain_relic_id_validates_as_is(monkeypatch: pytest.MonkeyPatch) -> None:
    """A plain relic id (the ids agree) validates directly."""
    client = _FakeProviderClient({RELIC_ID})
    seam = _seam(monkeypatch, client)

    validated = await seam.validate_profile(RELIC_ID)
    assert validated is not None
    assert validated["profile_id"] == RELIC_ID
    assert client.asked == [RELIC_ID]


async def test_plain_insights_id_resolves_when_it_differs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A plain insights id resolves to the relic id, both kept."""
    client = _FakeProviderClient({RELIC_ID})
    _fake_insights(monkeypatch, {INSIGHTS_ID: RELIC_ID})
    seam = _seam(monkeypatch, client)

    validated = await seam.validate_profile(INSIGHTS_ID)
    assert validated is not None
    assert validated["profile_id"] == RELIC_ID
    assert validated["site_ids"]["aoe2insights"] == INSIGHTS_ID


async def test_unknown_insights_id_fails_the_other_way(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unknown insights id but a resolvable relic id still binds."""
    client = _FakeProviderClient({RELIC_ID})
    _fake_insights(monkeypatch, {"other": RELIC_ID})
    seam = _seam(monkeypatch, client)

    validated = await seam.validate_profile(f"https://www.aoe2insights.com/user/{INSIGHTS_ID}/")
    assert validated is None  # the insights id resolves nowhere


async def test_nothing_resolves_is_none_not_a_silent_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Neither id resolves: the seam answers None (the actionable error)."""
    client = _FakeProviderClient(set())
    _fake_insights(monkeypatch, {})
    seam = _seam(monkeypatch, client)

    assert await seam.validate_profile(INSIGHTS_ID) is None
    assert await seam.validate_profile(f"https://www.aoe2insights.com/user/{INSIGHTS_ID}/") is None
    assert await seam.validate_profile(RELIC_ID) is None


def test_extract_survives_longer_urls() -> None:
    """A longer pasted URL still yields the insights id (#402)."""
    from botforge.discord.registration_platform import extract_insights_user_id

    assert extract_insights_user_id("https://www.aoe2insights.com/user/12488557/") == INSIGHTS_ID
    assert extract_insights_user_id("https://www.aoe2insights.com/user/12488557") == INSIGHTS_ID
    assert (
        extract_insights_user_id("https://www.aoe2insights.com/user/12488557/matches")
        == INSIGHTS_ID
    )
    assert (
        extract_insights_user_id("https://aoe2insights.com/user/12488557/?tab=overview#x")
        == INSIGHTS_ID
    )
    # the relic-keyed shape carries a RELIC id, never the insights id
    assert (
        extract_insights_user_id(f"https://www.aoe2insights.com/user/relic/{RELIC_ID}/")
        is None
    )
    # another host never matches
    assert extract_insights_user_id("https://evil.com/user/12488557/") is None
    assert extract_insights_user_id("https://aoe2insights.com.evil.com/user/12488557/") is None


async def test_resolve_retries_with_a_browser_ua_on_403(monkeypatch: Any) -> None:
    """The live #402 finding: the relic-id page 403s a datacenter call.

    The identified project UA is tried first (repo rule #277); a 403
    retries once with the browser-compatible UA — the resolution must
    not die on the bot filter.
    """
    import httpx

    from botforge.discord.registration_platform import resolve_relic_id

    attempts: list[str] = []

    class _Transport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            attempts.append(request.headers.get("user-agent", ""))
            if len(attempts) == 1:
                return httpx.Response(403, text="forbidden")
            return httpx.Response(200, text=RELIC_ID)

    assert await resolve_relic_id(INSIGHTS_ID, transport=_Transport()) == RELIC_ID
    assert len(attempts) == 2
    assert "botforge-bot" in attempts[0]  # the identified UA first
    assert attempts[1] != attempts[0]  # the browser-compatible retry


async def test_a_bot_filter_403_refuses_instead_of_blindly_binding(
    monkeypatch: Any,
) -> None:
    """The live 2026-11-17 finding: the Cloudflare challenge blocks the
    relic-id endpoint for EVERY user agent from this server.

    The old fallback validated the typed insights id as a relic id —
    which bound the WRONG player whenever the ids differ (the typed
    number can be someone else's relic id). The binding must refuse and
    guide the player to the relic-keyed URL shape instead.
    """
    from botforge.core.services.registration import InvalidProfileError

    client = _FakeProviderClient({INSIGHTS_ID})  # the trap: it WOULD validate
    _fake_blocked_insights(monkeypatch)
    seam = _seam(monkeypatch, client)

    with pytest.raises(InvalidProfileError, match="blocks this server"):
        await seam.validate_profile(f"https://www.aoe2insights.com/user/{INSIGHTS_ID}/")
    assert client.asked == []  # the wrong id is never even asked of the provider

    # the relic-keyed shape needs no resolution — the blocked site cannot
    # block a direct relic id
    validated = await seam.validate_profile(
        f"https://www.aoe2insights.com/user/relic/{INSIGHTS_ID}/"
    )
    assert validated is not None
    assert validated["profile_id"] == INSIGHTS_ID
