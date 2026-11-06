"""shirar-v2 (Drasah 06/11): the validated market emojis, the per-player
anti-double-click gate and the council-sheet regeneration.

antidoubleclic-v1: ONE interaction per player at a time — a second click
while the first is still processing is silently ACKNOWLEDGED (a bare
defer renders nothing) instead of racing the single-window registry (his
live report: two stacked Remparts views) or flashing an « interaction
failed » that makes the bot look broken.

conseil-regen-v1: the goals save closes the stale ⚔️ Salle du conseil
sheet and REGENERATES it from the validate click's LIVE token — the
conseil-rafraichi in-place edit died silently whenever the sheet's own
token was dead (>15 min) and left the STALE goals on screen.

Emoji couples (validated one by one by Drasah): Embuscade 🥷 ·
Traquenard 🪤 · Contre-espionnage 👀 · Sabotage 🗡️ · Jeu d'armes ⚔️ ·
Explorateur 🧭 · Corruption 💰 · Garde Royale 💂 · Patrouille 👣 ·
Mariage arrangé 💐 — the market buttons AND the ledger wear the same
couple (no more triple 🛡️ in the Chambre des comptes).
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from kingdoms.mods.kingdoms import kingdom_lieux as lieux
from kingdoms.mods.kingdoms import kingdom_persistent as kp
from kingdoms.mods.kingdoms import kingdom_realm_content as realm_content
from kingdoms.mods.kingdoms.kingdom_panels import _strings as _panel_strings
from tests.mocks.discord_mock import MockInteraction, MockUser


# ---------------------------------------------------------------------------
# shirar-v2 — the ten VALIDATED card↔emoji couples, FR and EN.
# ---------------------------------------------------------------------------


def test_the_ten_market_couples_match_drasah_validation() -> None:
    """Same card, same emoji everywhere: the market buttons AND the
    Chambre des comptes ledger wear the validated couple."""
    couples = {
        "embuscade": "🥷",
        "traquenard": "🪤",
        "contre_espionnage": "👀",
        "sabotage": "🗡️",
        "jeu_d_armes": "⚔️",
        "explorateur": "🧭",
        "corruption": "💰",
        "garde_royale": "💂",
        "patrouille": "👣",
        "mariage_arrange": "💐",
    }
    tech_keys = {"embuscade", "traquenard", "contre_espionnage", "sabotage", "jeu_d_armes"}
    for locale in ("fr", "en"):
        strings = _panel_strings(locale)
        for key, emoji in couples.items():
            section = "market_tech" if key in tech_keys else "market_action"
            assert str(strings[section][key]).startswith(emoji), (locale, key)
            assert strings["market_ledger_emoji"][key] == emoji, (locale, key)


def test_no_leftover_old_emojis_in_the_market_strings() -> None:
    """The retired emojis (🧪 jeu d'armes, 💒 mariage, 🧨 corruption,
    🕵️ contre-espionnage) are gone from the panel catalog."""
    from kingdoms.mods.kingdoms import kingdom_panels

    assert getattr(kingdom_panels, "STRINGS", None) is not None
    for locale in ("fr", "en"):
        strings = _panel_strings(locale)
        for key, value in strings["market_tech"].items():
            assert "🧪" not in str(value), (locale, key)
        for key, value in strings["market_action"].items():
            assert "💒" not in str(value), (locale, key)
        for key, value in strings["market_ledger_emoji"].items():
            assert value not in {"🧪", "💒", "🧨", "🕵️"}, (locale, key)


# ---------------------------------------------------------------------------
# antidoubleclic-v1 — ONE interaction per player at a time.
# ---------------------------------------------------------------------------


async def test_a_second_click_while_inflight_is_silently_acked() -> None:
    """His live report: a double-click stacked two Remparts views. The
    gate acks the second click with a bare defer (renders NOTHING) and
    never runs it — no « interaction failed », no duplicated window."""
    kp._USER_INFLIGHT.clear()
    ran: list[str] = []

    class _SlowItem:
        async def callback(self, interaction):  # noqa: ANN001
            await asyncio.sleep(0.01)
            ran.append("run")
            return "DONE"

    item = kp.antidoubleclic_wrap(_SlowItem)()
    first: object = MockInteraction(user=MockUser(id=77))
    second: object = MockInteraction(user=MockUser(id=77))

    task = asyncio.ensure_future(item.callback(first))
    await asyncio.sleep(0.002)  # the first click is mid-flight
    assert await item.callback(second) is None

    assert getattr(second.response, "deferred", False) is True  # silent ack
    assert ran == []  # the second click never ran
    assert await task == "DONE"
    assert ran == ["run"]
    assert getattr(first.response, "deferred", False) is False  # normal run

    third: object = MockInteraction(user=MockUser(id=77))
    assert await item.callback(third) == "DONE"  # the lock released
    kp._USER_INFLIGHT.clear()


async def test_wrapping_is_idempotent() -> None:
    """A re-registration never double-wraps — a nested gate would ack
    its own first click and wedge the player forever."""
    kp._USER_INFLIGHT.clear()

    class _Item:
        async def callback(self, interaction):  # noqa: ANN001
            return "OK"

    once = kp.antidoubleclic_wrap(_Item)
    assert kp.antidoubleclic_wrap(once) is once

    interaction: object = MockInteraction(user=MockUser(id=5))
    assert await once().callback(interaction) == "OK"
    kp._USER_INFLIGHT.clear()


async def test_a_crashing_callback_releases_the_lock() -> None:
    """The finally-release: a crashed handler never wedges the player."""

    class _Boom:
        async def callback(self, interaction):  # noqa: ANN001
            raise RuntimeError("boom")

    item = kp.antidoubleclic_wrap(_Boom)()
    interaction: object = MockInteraction(user=MockUser(id=9))
    try:
        await item.callback(interaction)
    except RuntimeError:
        pass
    assert "9" not in kp._USER_INFLIGHT

    class _Next:
        async def callback(self, interaction):  # noqa: ANN001
            return "NEXT"

    nxt = kp.antidoubleclic_wrap(_Next)()
    again: object = MockInteraction(user=MockUser(id=9))
    assert await nxt().callback(again) == "NEXT"


def test_every_registered_persistent_item_is_gated() -> None:
    """The registration seam wraps the whole catalogue — a future item
    added to the list rides the gate for free."""

    class _RecordingBot:
        def __init__(self) -> None:
            self.registered: list[type] = []

        def add_dynamic_items(self, *classes: type) -> None:
            self.registered.extend(classes)

    from kingdoms.mods.kingdoms.kingdom_lab import register_kingdom_lab_items
    from kingdoms.mods.kingdoms.kingdom_lieux import (
        register_kingdom_lieux_items,
    )

    bot = _RecordingBot()
    kp.register_kingdoms_persistent_items(bot)  # type: ignore[arg-type]
    register_kingdom_lieux_items(bot)  # type: ignore[arg-type]
    register_kingdom_lab_items(bot)  # type: ignore[arg-type]

    assert bot.registered, "nothing registered"
    for cls in bot.registered:
        assert getattr(cls, "_antidoubleclic", False) is True, cls.__name__


# ---------------------------------------------------------------------------
# conseil-regen-v1 — the council sheet is REGENERATED, never edited.
# ---------------------------------------------------------------------------


async def test_validate_regen_council_window_from_the_live_token(
    monkeypatch,
) -> None:
    """conseil-regen-v1 (Drasah 06/11): the goals save DELETES the stale
    sheet (best-effort) and sends a FRESH council view through the
    validate click's followup — a live token, so the refresh can no
    longer fail the way the dead-token in-place edit did."""
    kp._EPHEMERAL_WINDOWS.pop("9", None)

    async def fake_gather_state(kingdom, wiring):  # noqa: ANN001
        return {}

    async def fake_conseil_view(
        strings, kingdom, state, wiring, locale, **kwargs  # noqa: ANN001
    ):
        return ("FRESH_VIEW", ["conseil.png"])

    async def fake_rank(wiring, kingdom):  # noqa: ANN001
        return (1, 3)

    monkeypatch.setattr(realm_content, "_gather_state", fake_gather_state)
    monkeypatch.setattr(lieux, "build_conseil_view", fake_conseil_view)
    monkeypatch.setattr(lieux, "_conseil_rank", fake_rank)

    deletes: list[bool] = []

    async def fake_delete() -> None:
        deletes.append(True)

    parent = SimpleNamespace(delete=fake_delete)
    interaction: object = MockInteraction(user=MockUser(id=9))
    kingdom = SimpleNamespace(id="k1", name="Nilrem")
    wiring = SimpleNamespace()

    await lieux._regen_council_window_safe(
        wiring, kingdom, "fr", interaction, parent
    )

    assert deletes == [True]  # the stale sheet is closed
    entry = kp._EPHEMERAL_WINDOWS.get("9")
    assert entry is not None and len(entry) > 2
    window = entry[2]
    assert getattr(window, "view", None) == "FRESH_VIEW"  # the fresh view
    kp._EPHEMERAL_WINDOWS.pop("9", None)
