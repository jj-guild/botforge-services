"""The profile identification: in-game name or Relic ID (#402, closed).

The aoe2insights user-id resolution is GONE (the site blocks this
server's egress with a Cloudflare filter — no endpoint-based path
survives). The validation seam accepts a bare RELIC ID or a
relic-keyed URL of any site whose ids ARE relic ids; an aoe2insights
url is refused with the copy-your-Relic-ID guidance; the in-game NAME
path (the alias search and its candidate picker) stays.
"""

from __future__ import annotations

from typing import Any, ClassVar

import pytest

from botforge.core.models.game import PlayerStats, StatsBlock, StatsEntry
from botforge.discord.registration_platform import Aoe2ProfileValidationSeam

RELIC_ID = "17190369"


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
    """Build the seam with the fake provider wired as the game client."""
    import botforge.game_aoe2.client as game_client_module

    seam = Aoe2ProfileValidationSeam(provider_uri="fake:123")
    monkeypatch.setattr(game_client_module, "GameDataClient", lambda uri: client)
    return seam


class TestRelicIdPath:
    """The relic id validates as-is; the insights pastes are refused."""

    @pytest.mark.asyncio
    async def test_a_plain_relic_id_validates_as_is(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The provider knows the id — the binding keeps it verbatim."""
        client = _FakeProviderClient({RELIC_ID})
        seam = _seam(monkeypatch, client)
        validated = await seam.validate_profile(RELIC_ID)
        assert validated is not None
        assert validated["profile_id"] == RELIC_ID
        assert client.asked == [RELIC_ID]

    @pytest.mark.asyncio
    async def test_an_insights_url_is_refused_with_the_guidance(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No insights call, no binding attempt — the player is guided."""
        from botforge.core.services.registration import InvalidProfileError

        client = _FakeProviderClient({RELIC_ID})
        seam = _seam(monkeypatch, client)
        with pytest.raises(InvalidProfileError) as raised:
            await seam.validate_profile("https://www.aoe2insights.com/user/12488557/")
        assert "Relic ID" in str(raised.value)
        assert client.asked == []

    @pytest.mark.asyncio
    async def test_an_unknown_relic_id_validates_to_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The provider never heard of it — None, never a silent binding."""
        client = _FakeProviderClient(set())
        seam = _seam(monkeypatch, client)
        assert await seam.validate_profile("999999999") is None


class _SearchOnlyClient:
    """The provider-client stand-in for the alias search."""

    def __init__(self, candidates: list[dict[str, Any]]) -> None:
        self._candidates = candidates
        self.asked: list[str] = []

    async def search_profiles(self, alias: str) -> list[dict[str, Any]]:
        self.asked.append(alias)
        return list(self._candidates)


class _NullDatabase:
    """A registration database stand-in with no bindings at all."""

    async def upsert_entry(self, collection: str, document: dict[str, Any]) -> None:
        pass

    async def find_entry(self, collection: str, entry_id: str) -> dict[str, Any] | None:
        return None

    async def find_user_bindings(self, user_id: str) -> list[dict[str, Any]]:
        return []

    async def find_binding_by_profile(self, game_key: str, profile_id: str) -> dict[str, Any] | None:
        return None

    async def delete_binding(self, game_key: str, user_id: str, profile_id: str) -> bool:
        return False

    async def find_bindings_by_profiles(
        self, game_key: str, profile_ids: list[str]
    ) -> list[dict[str, Any]]:
        return []


class TestNameSearchPath:
    """The #402 name path: the typed alias searches the provider."""

    CANDIDATES: ClassVar[list[dict[str, Any]]] = [
        {
            "profile_id": RELIC_ID,
            "alias": "JeanJack",
            "steam_name": "/steam/76561199557469290",
            "country": "fr",
            "clan": "JJ",
            "elo_1v1": 1185,
            "elo_tg": 1374,
            "matches": [
                {
                    "map_name": "arabiablitz",
                    "description": "AUTOMATCH",
                    "completed_at": 1749127503,
                    "opponents": ["Hera"],
                }
            ],
        },
        {
            "profile_id": "11956265",
            "alias": "JeanJack",
            "steam_name": "/steam/76561198902339110",
            "country": "be",
            "matches": [],
        },
    ]

    @pytest.mark.asyncio
    async def test_the_seam_searches_by_alias(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """search_profiles reaches the provider with the typed alias."""
        import botforge.game_aoe2.client as game_client_module

        client = _SearchOnlyClient(self.CANDIDATES)
        monkeypatch.setattr(game_client_module, "GameDataClient", lambda uri: client)
        seam = Aoe2ProfileValidationSeam(provider_uri="fake:123")

        found = await seam.search_profiles("JeanJack")
        assert client.asked == ["JeanJack"]
        assert [c["profile_id"] for c in found] == [RELIC_ID, "11956265"]
        assert found[0]["matches"][0]["map_name"] == "arabiablitz"

    @pytest.mark.asyncio
    async def test_the_seam_degrades_to_empty_and_names_never_bind(self) -> None:
        """An empty/overflowing alias reads as no candidate, never raises."""
        seam = Aoe2ProfileValidationSeam(provider_uri="fake:123")
        assert await seam.search_profiles("") == []
        assert await seam.search_profiles("x" * 65) == []

    @pytest.mark.asyncio
    async def test_the_service_delegates_without_binding(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """search_candidates lists candidates for the player to pick — no binding."""
        import botforge.game_aoe2.client as game_client_module
        from botforge.core.services.registration import RegistrationService

        client = _SearchOnlyClient(self.CANDIDATES)
        monkeypatch.setattr(game_client_module, "GameDataClient", lambda uri: client)
        service = RegistrationService(_NullDatabase(), profile_seams={"aoe2": Aoe2ProfileValidationSeam("fake:123")})

        candidates = await service.search_candidates("aoe2", "JeanJack")
        assert [c["profile_id"] for c in candidates] == [RELIC_ID, "11956265"]

    def test_the_modal_classifies_name_id_and_url(self) -> None:
        """The classifier: digits are ids, URLs are urls, the rest is a name."""
        from botforge.discord.home import _is_name_input

        assert _is_name_input("JeanJack")
        assert _is_name_input("  Hera the 2nd ")  # a name keeps digits
        assert not _is_name_input("17190369")
        assert not _is_name_input("https://www.aoe2insights.com/user/12488557/")
        assert not _is_name_input("")

    def test_the_candidate_line_carries_clan_country_and_elos(self) -> None:
        from botforge.discord.home import _candidate_line

        line = _candidate_line(self.CANDIDATES[0])
        assert "JeanJack [JJ] (FR)" in line
        assert "1v1 1185" in line
        assert "TG 1374" in line
        no_stats = _candidate_line({"alias": "NoStats", "country": "be"})
        assert no_stats == "NoStats (BE) \u2014 1v1 ? \u00b7 TG ?"
