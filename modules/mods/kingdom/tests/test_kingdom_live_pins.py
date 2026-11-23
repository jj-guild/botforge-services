"""live-pin-v1 (Drasah 21/11) — a pin is a mirror, never a snapshot.

The incident: Drasah flipped the sas in la Régie and the console pin
kept showing « fermé » — the restart-proof pin re-rendered only at
boot. TWO generic causes, both fixed core-side:

1. the in-place edit's fingerprint ignored the TEXT (a sas line that
   flipped never flipped the fingerprint, so the edit never happened);
2. NO refresh pass covered the console pin — the 5-minute surface
   refresher only touched the seasonal posts (roster, candidates,
   participants), never a mod's admin pin.

The fix: the fingerprint sees the text; each pin DECLARES ``live``;
the surface pass re-renders every live pin (the safety net) and the
console's gestures call ``refresh_live_pins`` in the same breath as
the state change (the feedback loop).
"""

from __future__ import annotations

from typing import Any
from types import SimpleNamespace

import pytest


# ---------------------------------------------------------------------------
# The fake guild/channel/message — the pin edit in place, no Mongo needed
# ---------------------------------------------------------------------------


class _Message:
    """A live pin: edit is what the refresh must do, pin is best-effort."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.edits = 0
        self.pinned = 0

    async def edit(self, view: Any = None) -> None:
        self.edits += 1

    async def pin(self, reason: str = "") -> None:
        self.pinned += 1


class _Channel:
    def __init__(self, message: _Message) -> None:
        self._message = message

    async def fetch_message(self, message_id: int) -> _Message:
        return self._message

    async def pins(self) -> list[Any]:
        return [self._message]

    async def send(self, *args: Any, **kwargs: Any) -> Any:
        # the ensure cycle checks for send even on the refresh path
        return None


class _Guild:
    def __init__(self, channel: _Channel) -> None:
        self._channel = channel

    def get_channel(self, channel_id: int) -> _Channel:
        return self._channel


class _Bot:
    def __init__(self, guild: _Guild) -> None:
        self._guild = guild

    def get_guild(self, guild_id: int) -> _Guild:
        return self._guild


def _register_spec(key: str, live: bool, text: str) -> SimpleNamespace:
    """Register one static pin whose layout shows ``text`` (isolated)."""
    import discord

    from botforge.discord.static_pins import StaticPinnedView, register_static_pin

    async def _resolve_channel(guild_id: str) -> str:
        if not live:
            raise AssertionError(f"{key} is not live — it must not be refreshed")
        return "55"

    async def _build_layout(guild_id: str) -> Any:
        view = discord.ui.LayoutView()
        view.add_item(discord.ui.Container(discord.ui.TextDisplay(text)))
        return view

    spec = StaticPinnedView(
        key=key,
        mark_suffix=key,
        resolve_channel=_resolve_channel,
        build_layout=_build_layout,
        registry=None,
        live=live,
    )
    return register_static_pin(spec)


def test_the_fingerprint_sees_the_text() -> None:
    """The in-place edit's trigger: a flipped TEXT must flip the hash."""
    import discord

    from botforge.discord.static_pins import _layout_fingerprint

    def _view(text: str) -> discord.ui.LayoutView:
        view = discord.ui.LayoutView()
        view.add_item(discord.ui.Container(discord.ui.TextDisplay(text)))
        return view

    assert _layout_fingerprint(_view("🛂 Sas : fermé")) != (
        _layout_fingerprint(_view("🛂 Sas : ouvert"))
    ), "a sas line that flipped must flip the fingerprint"
    assert _layout_fingerprint(_view("🛂 Sas : fermé")) == (
        _layout_fingerprint(_view("🛂 Sas : fermé"))
    )


@pytest.mark.asyncio
async def test_refresh_live_pins_edits_the_live_pin_in_place() -> None:
    """A live pin: edited when the state changed, untouched when not."""
    import unittest.mock as mock

    from botforge.discord import static_pins
    from botforge.discord.static_pins import refresh_live_pins

    static_pins.reset_static_pins()
    spec = _register_spec("panel:test:live-pin", live=True, text="🛂 Sas : ouvert")
    message = _Message("old text")
    bot = _Bot(_Guild(_Channel(message)))
    # the pin already lives: its id rides the memory store, its last
    # rendered fingerprint says « fermé » — the refresh must EDIT it
    static_pins._MEMORY_STORE[(spec.key, "1")] = "999"
    static_pins._LAST_RENDER[(spec.key, "1")] = "a-stale-fingerprint"

    await refresh_live_pins(bot, "1")
    assert message.edits == 1, "the flipped sas line re-renders in place"

    # a second pass with an unchanged layout edits NOTHING (Discord quota)
    static_pins._LAST_RENDER[(spec.key, "1")] = static_pins._layout_fingerprint(
        await spec.build_layout("1")
    )
    await refresh_live_pins(bot, "1")
    assert message.edits == 1, "an unchanged surface is not re-edited"


@pytest.mark.asyncio
async def test_refresh_live_pins_skips_the_static_pins() -> None:
    """A non-live pin never rides the refresh (its resolver is a trap)."""
    from botforge.discord import static_pins
    from botforge.discord.static_pins import refresh_live_pins

    static_pins.reset_static_pins()
    _register_spec("panel:test:pinned-menu", live=False, text="un menu figé")
    message = _Message("old text")
    bot = _Bot(_Guild(_Channel(message)))
    static_pins._MEMORY_STORE[("panel:test:pinned-menu", "1")] = "999"
    static_pins._LAST_RENDER[("panel:test:pinned-menu", "1")] = "stale"

    # the resolver raises when touched — the pass must skip it silently
    assert await refresh_live_pins(bot, "1") == 0
    assert message.edits == 0


@pytest.mark.asyncio
async def test_the_surface_pass_refreshes_live_pins_without_a_registry() -> None:
    """The 5-minute safety net: live pins refresh even registry-less."""
    import unittest.mock as mock

    from botforge.discord import static_pins
    from botforge.discord.season_panels import _refresh_all_season_pins

    static_pins.reset_static_pins()
    with mock.patch.object(
        static_pins, "refresh_live_pins", new=mock.AsyncMock()
    ) as refresh:
        bot = SimpleNamespace(
            guilds=[SimpleNamespace(id=1)],
            registry=None,
        )
        await _refresh_all_season_pins(bot)
    refresh.assert_awaited_once_with(bot, "1")


def test_the_console_pin_is_live_as_registered() -> None:
    """The designer's reported pin declares ``live`` at wiring time."""
    from botforge.discord.static_pins import registered_static_pins

    from botforge.mods.kingdom.cogs import register

    class _BootBot:
        message_registry = None
        guilds: list[object] = []

    register(_BootBot(), None)
    spec = next(
        (s for s in registered_static_pins() if s.key == "panel:mod:kingdom:console"),
        None,
    )
    assert spec is not None, "the console pin must register (boot guard)"
    assert spec.live is True, "the cockpit mirrors a mutable state — it is live"


@pytest.mark.asyncio
async def test_the_régie_flip_refreshes_the_pins_immediately() -> None:
    """The feedback loop: the switch's click re-renders the mirrors."""
    import unittest.mock as mock

    import discord

    from botforge.mods.kingdom.cogs import common, settings_panel as sp
    from botforge.mods.kingdom.cogs.regie import toggle_switch
    from botforge.mods.kingdom.cogs.settings_panel import KingdomRegieSwitchButton

    button = KingdomRegieSwitchButton(
        "season_entry_open", "Sas", True, discord.ButtonStyle.success
    )
    interaction = SimpleNamespace(client=None, guild_id="123", locale=None)
    with mock.patch.object(
        sp, "strings_of", lambda i: sp.settings_strings("fr")
    ), mock.patch.object(sp, "_panel_guard", new=mock.AsyncMock(return_value=True)), \
            mock.patch.object(sp, "_build_drawer", new=mock.AsyncMock()), \
            mock.patch.object(sp, "open_unique_ephemeral", new=mock.AsyncMock()), \
            mock.patch.object(sp, "refresh_live_pins_after", new=mock.AsyncMock()) as refresh, \
            mock.patch("botforge.mods.kingdom.cogs.regie.toggle_switch", new=mock.AsyncMock()):
        await button.callback(interaction)
    refresh.assert_awaited_once_with(interaction), (
        "the flip shows on the console pin in the same breath"
    )


@pytest.mark.asyncio
async def test_the_engine_gestures_refresh_too() -> None:
    """Departure + false start: the sas move lands on the pin at once."""
    import unittest.mock as mock

    from botforge.mods.kingdom.cogs import common, settings_panel as sp

    state: dict[tuple[str, str], dict[str, Any]] = {}

    class _StateService:
        async def get_state(self, scope: str, key: str):
            return state.get((scope, key))

        async def set_state(self, scope: str, key: str, value, ttl=None):
            state[(scope, key)] = value
            return True

    class _Kingdom:
        async def start_season(self):
            pass

        async def set_phase(self, phase: str):
            pass

        async def current_season(self):
            return SimpleNamespace(phase="started")

        async def realms(self):
            return []

    class _Realms:
        async def realms(self):
            return []

        async def release_engagement(self, realm_id: str):
            pass

    stack = SimpleNamespace(kingdoms=_Kingdom(), realms=_Realms())
    interaction = SimpleNamespace(
        client=SimpleNamespace(state_service=_StateService()),
        guild_id="123",
        response=SimpleNamespace(is_done=lambda: True),
        followup=SimpleNamespace(send=mock.AsyncMock()),
    )
    with mock.patch.object(common, "wiring", lambda: stack), \
            mock.patch.object(sp, "wiring", lambda: stack), \
            mock.patch.object(sp, "_sas_roster_counts", mock.AsyncMock(return_value=(2, 0))), \
            mock.patch.object(sp, "_consume_sas", mock.AsyncMock(return_value=2)), \
            mock.patch.object(sp, "refresh_live_pins_after", new=mock.AsyncMock()) as refresh:
        await sp._start_season(interaction, sp.settings_strings("fr"))
        refresh.assert_awaited_once(), "the departure's sas close re-renders the pin"
        await sp._false_start(interaction, sp.settings_strings("fr"))
    assert refresh.await_count == 2, "the false start's sas reopen re-renders the pin"
