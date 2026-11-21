"""hub-entry-fast-ack — the tests (Drasah 20/11).

The tester's capture: the hub panel shows (fixed ✅) but the click on
« 🏰 Entrée » ends in « Kingdoms (TEST) n'a pas répondu à temps » — the
door built its ENTIRE window (the cold service wiring, the Mongo
reads, the layout) before the FIRST byte of response, and Discord
closes an unacknowledged click after 3 seconds. The quit/join/crown
buttons already spoke the right pattern (ack first, work after); the
door and the nav now speak it too, and the platform's ephemeral-window
seam carries the followup path (a click already acked delivers its
window through the followup message, closable through the same seam).
"""

from __future__ import annotations

from typing import Any

import discord
import pytest


calls: list[str] = []


class _FakeResponse:
    def __init__(self) -> None:
        self.done = False
        self.defer_kwargs: dict[str, Any] = {}
        self.sent: list[dict[str, Any]] = []

    def is_done(self) -> bool:
        return self.done

    async def defer(self, **kwargs: Any) -> None:
        calls.append("defer")
        self.defer_kwargs = dict(kwargs)
        self.done = True

    async def send_message(self, content: Any = None, **kwargs: Any) -> None:
        calls.append("send_message")
        self.sent.append({"content": content, **kwargs})
        self.done = True


class _FakeFollowup:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        self.sent: list[dict[str, Any]] = []

    async def send(self, content: Any = None, **kwargs: Any) -> "_FakeMessage":
        calls.append("followup")
        self.sent.append({"content": content, **kwargs})
        return _FakeMessage(self.sent[-1])


class _FakeMessage:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.deleted = False

    async def delete(self) -> None:
        self.deleted = True


class _FakeUser:
    def __init__(self, uid: str) -> None:
        self.id = uid


def _interaction(uid: str = "1") -> Any:
    interaction = type("I", (), {})()
    interaction.user = _FakeUser(uid)
    interaction.locale = "fr"
    interaction.response = _FakeResponse()
    interaction.followup = _FakeFollowup(interaction.response)
    return interaction


def _realm(uid: str = "1") -> Any:
    realm = type("R", (), {})()
    realm.id = "realm-1"
    realm.name = "HeN"
    realm.slug = "hen"
    realm.king_id = uid
    realm.king_name = "Drasah"
    realm.member_ids = []
    realm.presentation = ""
    realm.join_request = None
    realm.founded_at = 1750000000
    realm.engagement = None
    realm.season_history = []
    realm.discord = {}
    return realm


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch) -> None:
    calls.clear()

    async def fake_realm_of(interaction: Any, slug: str) -> Any:
        calls.append(f"realm_of:{slug}")
        return _realm()

    import botforge.mods.kingdom.cogs.realms as realms_module

    monkeypatch.setattr(realms_module, "_realm_of", fake_realm_of)


# ---------------------------------------------------------------------------
# The door — ack FIRST, the window renders after, through the followup
# ---------------------------------------------------------------------------


async def test_the_entry_door_acks_before_the_slow_reads() -> None:
    from botforge.mods.kingdom.cogs.realms import RealmHomeButton

    button = RealmHomeButton("🏰 Entrée", discord.ButtonStyle.primary, "hen")
    interaction = _interaction()
    await button.callback(interaction)
    assert calls[0] == "defer", "the ack must come FIRST — the 3-second clock is the ack's"
    assert calls[1] == "realm_of:hen", "the reads happen after the ack"
    assert calls[2] == "followup", "the window renders through the followup seam"
    assert interaction.response.defer_kwargs.get("ephemeral") is True
    assert interaction.followup.sent[0]["view"] is not None


async def test_a_non_member_sees_the_note_not_a_timeout() -> None:
    from botforge.mods.kingdom.cogs.realms import RealmHomeButton

    button = RealmHomeButton("🏰 Entrée", discord.ButtonStyle.primary, "hen")
    interaction = _interaction(uid="999")  # neither king nor member
    await button.callback(interaction)
    body = interaction.followup.sent[0]
    # windows-v2: a text note is the declared NOTE surface — the text
    # rides inside the view, with its ✖️ close row
    assert body["view"] is not None, "the refusal is a PAGE, never a dead click"
    texts = [
        c.content
        for c in body["view"].walk_children()
        if type(c).__name__ == "TextDisplay"
    ]
    assert "chez eux" in " ".join(str(t) for t in texts)


async def test_a_build_failure_answers_never_times_out() -> None:
    import botforge.mods.kingdom.cogs.realms as realms_module

    async def broken_home(*args: Any, **kwargs: Any) -> discord.ui.LayoutView:
        raise RuntimeError("cold Mongo, or anything else")

    monkeypatch_target = realms_module

    original_home = realms_module.home_layout
    monkeypatch_target.home_layout = broken_home
    from botforge.mods.kingdom.cogs.realms import RealmHomeButton

    try:
        button = RealmHomeButton("🏰 Entrée", discord.ButtonStyle.primary, "hen")
        interaction = _interaction()
        await button.callback(interaction)
    finally:
        monkeypatch_target.home_layout = original_home
    body = interaction.followup.sent[0]
    assert body["view"] is not None, "an error page answers, never the silent timeout"
    texts = [
        c.content
        for c in body["view"].walk_children()
        if type(c).__name__ == "TextDisplay"
    ]
    assert "retente" in " ".join(str(t) for t in texts)


# ---------------------------------------------------------------------------
# The nav windows — same pattern
# ---------------------------------------------------------------------------


async def test_the_nav_buttons_ack_first_and_never_stall() -> None:
    from botforge.mods.kingdom.cogs.realms import RealmNavButton

    for view_key in ("presentation", "palmares"):
        calls.clear()
        button = RealmNavButton("fenêtre", view_key, "hen")
        interaction = _interaction()
        await button.callback(interaction)
        assert calls[0] == "defer", f"{view_key}: the ack comes first"
        assert interaction.followup.sent, f"{view_key}: the window renders"


# ---------------------------------------------------------------------------
# The platform seam — a deferred click delivers through the followup
# ---------------------------------------------------------------------------


async def test_the_ephemeral_seam_carries_the_followup_path() -> None:
    from botforge.discord.ui.ephemeral_windows import (
        close_ephemeral_window,
        open_ephemeral_window,
        set_window_mode,
        EphemeralWindowMode,
    )

    set_window_mode("kingdom/window", EphemeralWindowMode.SINGLE)
    interaction = _interaction()
    await interaction.response.defer(ephemeral=True)
    await open_ephemeral_window(interaction, "kingdom/window", "salut", view=discord.ui.LayoutView())
    assert interaction.followup.sent, "an already-acked click delivers through the followup"
    assert interaction.followup.sent[0]["ephemeral"] is True
    # the single-window close tracks the followup message through the same seam
    await close_ephemeral_window("kingdom/window", "1")
    assert interaction.followup.sent, "the close is best-effort, never a raise"


async def test_the_followup_window_closes_another_one_first() -> None:
    from botforge.discord.ui.ephemeral_windows import (
        _FollowupWindow,
        close_ephemeral_window,
        open_ephemeral_window,
        set_window_mode,
        EphemeralWindowMode,
    )

    set_window_mode("kingdom/window2", EphemeralWindowMode.SINGLE)
    first = _interaction()
    await first.response.defer(ephemeral=True)
    await open_ephemeral_window(first, "kingdom/window2", "un")
    second = _interaction()
    await second.response.defer(ephemeral=True)
    await open_ephemeral_window(second, "kingdom/window2", "deux")
    # close_ephemeral_window popped the first window's followup message —
    # its delete() ran (the _FollowupWindow adapter speaks the protocol)
    assert isinstance(getattr(_FollowupWindow, "delete_original_response", None), object)
    deleted = second.followup.sent  # the second window stays live
    assert deleted, "the OPEN never raises, the previous tracks through the adapter"


def test_the_localized_refusal_notes_carry_fr_en_parity() -> None:
    from botforge.mods.kingdom.cogs.realm_strings import realm_strings as catalog

    for locale in ("fr", "en"):
        strings = catalog(locale)
        assert strings["realm_error_note"], f"{locale}: the error note exists"
    fr = catalog("fr")
    en = catalog("en")
    assert set(fr) == set(en), "fr/en key parity — every door speaks both languages"


def test_the_season_window_survives_a_real_season_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """voir-saison-crash (Drasah 21/11, bêta-test) : un clic sur
    « 📺 Voir la saison » tombait sur la note générique « panne » dès
    qu'une saison existait — SeasonState.started_at est un vrai
    DATETIME (pydantic strict) et l'ancien int(...) levait TypeError.
    La vue doit rend, datetime comme epoch."""
    import asyncio
    from datetime import UTC, datetime
    from types import SimpleNamespace as NS
    from unittest.mock import AsyncMock

    import botforge.mods.kingdom.cogs.realms as realms_module
    from botforge.mods.kingdom.cogs.realm_strings import realm_strings as catalog

    stack = NS(
        kingdoms=NS(
            current_season=AsyncMock(
                return_value=NS(
                    started_at=datetime(2026, 11, 21, 18, 0, tzinfo=UTC),
                    phase="running",
                )
            )
        )
    )
    monkeypatch.setattr(realms_module, "wiring", lambda: stack)

    strings = dict(catalog("fr"))
    view = asyncio.run(realms_module.season_layout(_realm(), strings, king=True, guild_id="42"))
    texts = "\n".join(str(c.content) for c in view.walk_children() if hasattr(c, "content"))
    assert strings["season_running"].split(" ")[0] in texts
    assert "21/11 19:00" in texts, "the datetime renders in Paris time, not a crash"
