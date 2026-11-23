"""territory-reveal-v1 — the tests (Drasah 23/11).

The 23/11 live incident: the 🌍 Territoire salons stayed EMPTY after the
beta departure, every realm included, Gaïa included. The portage had
never reconnected the reference's season reveal:

- the INITIAL LAND DRAW runs at the departure, BEFORE the sheets read
  the documents (the reference's own 2026-10-11 regression rule), with
  the reference's guards: nothing in setup, nothing when the season
  already drew its slice;
- the departure and the beta loop both ride the ONE feeding seam;
- Gaïa — an engine kingdom with no shell — carries its OWN territory
  sheet (the live AI level + its lands with the same badges).
"""

from __future__ import annotations

from typing import Any

import pytest

calls: list[str] = []


class _Message:
    def __init__(self, mid: str, content: str) -> None:
        self.id = mid
        self.content = content
        self.edits = 0
        self.deleted = False
        self.pinned = False
        self._channel: Any = None

    async def edit(self, **kwargs: Any) -> None:
        self.content = str(kwargs.get("content", self.content))
        self.edits += 1

    async def delete(self) -> None:
        self.deleted = True
        if self in self._channel.history_msgs:
            self._channel.history_msgs.remove(self)

    async def pin(self) -> None:
        self.pinned = True


class _Channel:
    def __init__(self, name: str) -> None:
        self.id = f"chan-{name}"
        self.name = name
        self.history_msgs: list[Any] = []

    async def history(self, limit: int) -> Any:
        for message in list(self.history_msgs):
            yield message

    async def send(self, content: str = "", view: Any = None, **kwargs: Any) -> _Message:
        message = _Message(f"m-{len(self.history_msgs) + 1}", content)
        message.view = view
        message._channel = self
        self.history_msgs.append(message)
        calls.append("send")
        return message


class _Category:
    def __init__(self, name: str, channels: list[Any]) -> None:
        self.id = f"cat-{name}"
        self.name = name
        self.channels = channels


class _Territory:
    def __init__(self, map_key: str, owner: str) -> None:
        self.map_key = map_key
        self.owner_kingdom_id = owner
        self.protected_until = None
        self.cathedral_until = None


class _GaiaKingdom:
    def __init__(self) -> None:
        self.id = "k-gaia"
        self.name = "Gaïa"
        self.is_gaia = True


def _guild() -> Any:
    guild = type("G", (), {})()
    guild.id = "g-1"
    guild.channels = []
    terr = _Channel("🌍 Territoire")
    guild.categories = [_Category("Kingdom-Gaïa", [terr])]
    guild.territory_channel = terr
    return guild


def _stack(phase: str, territories: list[Any]) -> Any:
    given = list(territories)

    class _Stack:
        class config:  # noqa: N801
            maps = (type("M", (), {"key": "arabia", "display_name": "Arabie"})(),)
            civilizations = ()

        class kingdoms:  # noqa: N801
            @staticmethod
            async def current_season() -> Any:
                return type("S", (), {"phase": phase})()

            @staticmethod
            async def kingdoms() -> list[Any]:
                return [_GaiaKingdom()]

        class territories:  # noqa: N801
            @staticmethod
            async def territories() -> list[Any]:
                return list(given)

            @staticmethod
            async def draw_initial() -> list[Any]:
                calls.append("draw")
                return []

        class attacks:  # noqa: N801
            @staticmethod
            async def base_ai_level() -> int:
                return 3

    return _Stack


@pytest.fixture(autouse=True)
def _clean() -> None:
    calls.clear()


@pytest.mark.asyncio
async def test_the_draw_waits_for_the_departure_never_duplicates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reference's own guards: setup defers, an existing slice skips."""
    import botforge.mods.kingdom.cogs.realm_content as content

    monkeypatch.setattr(content, "wiring", lambda: _stack("setup", []))
    assert await content.draw_initial_territories_safe(object()) is False
    assert calls == []

    monkeypatch.setattr(content, "wiring", lambda: _stack("started", [_Territory("arabia", "k-1")]))
    assert await content.draw_initial_territories_safe(object()) is False
    assert calls == [], "the season already drew its slice — no second draw"

    monkeypatch.setattr(content, "wiring", lambda: _stack("started", []))
    assert await content.draw_initial_territories_safe(object()) is True
    assert calls == ["draw"], "the reveal draw runs BEFORE the sheets render"


@pytest.mark.asyncio
async def test_gaia_carries_her_own_territory_sheet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gaïa has no shell — her sheet rides its own deployer."""
    import botforge.mods.kingdom.cogs.realm_content as content

    monkeypatch.setattr(
        content, "wiring", lambda: _stack("started", [_Territory("arabia", "k-gaia")])
    )
    guild = _guild()

    assert await content.deploy_gaia_content(guild, "fr") is True
    sheet = guild.territory_channel.history_msgs[0].content
    assert "Niveau de l'IA Gaïa : 3/5" in sheet, "the AI level is LIVE from the season epoch"
    assert "Arabie" in sheet, "Gaïa's lands wear the same badges as the player realms"
    assert content._marker("territory-gaia") in sheet

    # idemotence: the marker governs — the marked sheet is EDITED in place
    sheet_edits = guild.territory_channel.history_msgs[0].edits
    calls.clear()
    assert await content.deploy_gaia_content(guild, "fr") is True
    assert calls == [], "a marked sheet is edited, never duplicated"
    assert guild.territory_channel.history_msgs[0].edits == sheet_edits + 1


@pytest.mark.asyncio
async def test_the_gaia_sheet_stays_silent_without_her_structure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import botforge.mods.kingdom.cogs.realm_content as content

    monkeypatch.setattr(content, "wiring", lambda: _stack("started", []))
    guild = _guild()
    guild.categories = []
    assert await content.deploy_gaia_content(guild, "fr") is False
    assert calls == []


def test_the_content_strings_carry_the_gaia_lines_in_both_locales() -> None:
    import botforge.mods.kingdom.cogs.realm_content as content

    fr = content.content_strings("fr")
    en = content.content_strings("en")
    assert "gaia_ai_level" in fr and "gaia_ai_level" in en
