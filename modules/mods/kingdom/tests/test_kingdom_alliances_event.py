"""alliances-evenementiel-v1 — the tests (Drasah 23/11).

The 23/11 live incident (17h57/18:02): the panel was re-PUBLISHED
twice, five minutes apart, next to the existing one. Drasah's ruling
is absolute — the 🏆 panel updates ONLY when a hand actually changes,
and the bot EDITS the existing message, it NEVER posts a new one.
Three locks in code: a failed edit NEVER resends, the signature
guard costs zero API on unchanged data, and the 5-min pass does not
touch the panel at all (it lives on events: cycle, expedition,
marriage, departure).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import discord
import pytest


ALLIANCES_MARKER = "-# kingdom:realm-content:alliances"
TERRITORY_MARKER = "-# kingdom:realm-content:territory"


def _forbidden() -> discord.Forbidden:
    return discord.Forbidden(Mock(status=403), {"message": "Missing Access"})


def _not_found() -> discord.NotFound:
    return discord.NotFound(Mock(status=404), "Unknown Message")


class _Message:
    def __init__(self, mid: str, content: str) -> None:
        self.id = mid
        self.content = content
        self.edited = 0
        self.deleted = False
        self.edit_error: BaseException | None = None

    async def edit(self, **kwargs: Any) -> None:
        if self.edit_error is not None:
            raise self.edit_error
        self.edited += 1

    async def delete(self) -> None:
        self.deleted = True

    async def pin(self) -> None:
        return None


class _Channel:
    def __init__(self, name: str, *messages: _Message) -> None:
        self.id = f"chan-{name}"
        self.name = name
        self.history_msgs = list(messages)
        self.sends = 0

    async def history(self, limit: int) -> Any:
        for message in list(self.history_msgs):
            yield message

    async def send(self, content: str = "", **kwargs: Any) -> _Message:
        self.sends += 1
        message = _Message(f"m-new-{self.sends}", content)
        self.history_msgs.append(message)
        return message


class _Category:
    def __init__(self, name: str, channels: list[Any]) -> None:
        self.id = f"cat-{name}"
        self.name = name
        self.channels = channels


class _Kingdom:
    def __init__(self, kid: str, name: str, hand: list[str] | None = None) -> None:
        self.id = kid
        self.name = name
        self.is_gaia = False
        self.civilizations = list(hand or [])
        self.civilization_acquisitions: dict[str, Any] = {}


class _Realm:
    def __init__(self, name: str, kingdom_id: str) -> None:
        self.id = f"r-{name}"
        self.name = name
        self.engagement = {"kingdom_id": kingdom_id}
        self.discord: dict[str, Any] = {}
        self.archived_at = None


def _guild(*alliances_messages: _Message) -> Any:
    guild = type("G", (), {})()
    guild.id = "g-1"
    guild.channels = []
    alliances = _Channel("🏆 Alliances", *alliances_messages)
    guild.alliances_salon = alliances
    guild.categories = [
        _Category("🏰 Aegis", [
            _Channel("🔒 Discussions"),
            _Channel("🌍 Territoire"),
            alliances,
        ])
    ]
    return guild


def _bot(guild: Any) -> Any:
    bot = type("B", (), {})()
    bot.guilds = [guild]
    return bot


def _stack(hand: list[str]) -> Any:
    realm = _Realm("Aegis", "k-1")

    class _Stack:
        class config:  # noqa: N801
            maps = ()
            civilizations = ()

        class kingdoms:  # noqa: N801
            @staticmethod
            async def current_season() -> Any:
                return type("S", (), {"phase": "started", "name": "Bêta 1"})()

            @staticmethod
            async def kingdoms() -> list[Any]:
                return [_Kingdom("k-1", "Aegis moteur", hand)]

        class realms:  # noqa: N801
            @staticmethod
            async def realms() -> list[Any]:
                return [realm]

            @staticmethod
            async def save_habitat(realm_id: str, ids: dict[str, Any]) -> None:
                return None

    return _Stack


@pytest.mark.asyncio
async def test_a_failed_edit_never_resends(monkeypatch: pytest.MonkeyPatch) -> None:
    """THE incident's lock: an edit refused leaves the sheet as-is."""
    import botforge.mods.kingdom.cogs.realm_content as content

    sheet = _Message("m-1", f"le panneau\n{ALLIANCES_MARKER}")
    sheet.edit_error = _forbidden()
    channel = _Channel("🏆 Alliances", sheet)

    result = await content._upsert_marked(
        channel, "alliances", None, view=Mock(), stored_id="m-1"
    )

    assert result is None, "a refused edit returns no id — and never a fresh publication"
    assert channel.sends == 0, "the sheet that failed to edit is NEVER re-sent"
    assert len(channel.history_msgs) == 1, "the salon keeps exactly one panel"


@pytest.mark.asyncio
async def test_a_vanished_message_rescans_before_publishing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A NotFound during the edit re-scans once, then publishes only if gone."""
    import botforge.mods.kingdom.cogs.realm_content as content

    sheet = _Message("m-1", f"le panneau\n{ALLIANCES_MARKER}")
    sheet.edit_error = _not_found()  # the message vanished under us
    channel = _Channel("🏆 Alliances", sheet)

    result = await content._upsert_marked(channel, "alliances", None, view=Mock())
    # the rescan still finds it (the mock list never dropped it) → no resend
    assert result is None
    assert channel.sends == 0

    # the SECOND fixture: an empty salon carries NO sheet — the ONE
    # publication is the legit first pose (a departure, say)
    channel2 = _Channel("🏆 Alliances")
    result2 = await content._upsert_marked(channel2, "alliances", None, view=Mock())
    assert channel2.sends == 1, "an ABSENT sheet justifies ONE publication"
    assert result2 == "m-new-1"


@pytest.mark.asyncio
async def test_the_periodic_pass_never_touches_the_alliances_panel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The 5-min pass leaves the 🏆 salon alone — the panel lives on events."""
    import botforge.mods.kingdom.cogs.realm_content as content

    sheet = _Message("m-1", f"le panneau\n{ALLIANCES_MARKER}")
    guild = _guild(sheet)
    monkeypatch.setattr(content, "wiring", lambda: _stack(["francs"]))
    # the view seam is patched: this test proves the PASS does not reach it
    reached: list[Any] = []

    async def _fake_view(*args: Any, **kwargs: Any) -> tuple[Any, Any]:
        reached.append(args)
        return None, Mock()

    monkeypatch.setattr(content, "_alliances_view", _fake_view)
    import botforge.mods.kingdom.cogs.civ_crests as crests

    monkeypatch.setattr(crests, "civ_crest_mosaic_file", _fake_mosaic)

    async def _no_gaia(guild: Any, locale: Any = "fr") -> bool:
        return False

    monkeypatch.setattr(content, "deploy_gaia_content", _no_gaia)

    await content.feed_season_surfaces(_bot(guild), include_alliances=False)

    assert reached == [], "the periodic pass never renders the alliances panel"
    assert sheet.edited == 0 and guild.alliances_salon.sends == 0


@pytest.mark.asyncio
async def test_the_event_seam_renders_only_changed_hands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The signature guard: first event renders, an unchanged second costs nothing."""
    import botforge.mods.kingdom.cogs.realm_content as content

    sheet = _Message("m-1", f"le panneau\n{ALLIANCES_MARKER}")
    guild = _guild(sheet)
    stack = _stack(["francs"])
    monkeypatch.setattr(content, "wiring", lambda: stack)
    monkeypatch.setattr(
        content, "_alliances_view", lambda *a, **k: _async_pair(None, Mock())
    )
    import botforge.mods.kingdom.cogs.civ_crests as crests

    monkeypatch.setattr(crests, "civ_crest_mosaic_file", _fake_mosaic)
    content._ALLIANCE_HAND_SIG.clear()

    touched = await content.refresh_alliance_panels(_bot(guild), ["k-1"])
    assert touched == 1, "the first event renders the changed hand"
    assert sheet.edited == 1, "the panel is EDITED in place, never re-posted"
    assert guild.alliances_salon.sends == 0, "an existing panel is never duplicated"

    # the hand is UNCHANGED (marriage recalculated the same list, say)
    touched_again = await content.refresh_alliance_panels(_bot(guild), ["k-1"])
    assert touched_again == 0, "an unchanged hand costs zero Discord call"
    assert guild.alliances_salon.sends == 0


async def _async_pair(*pair: Any) -> tuple[Any, Any]:
    return pair


async def _fake_mosaic(*args: Any, **kwargs: Any) -> None:
    return None
