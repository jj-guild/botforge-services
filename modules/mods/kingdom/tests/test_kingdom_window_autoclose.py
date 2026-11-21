"""settings-window-autoclose (Drasah 21/11) — une action ferme SA fenêtre.

« Quand j'appuie sur Démarrer/Fermer la bêta, Faux départ..., je veux que
la fenêtre se ferme — sinon, ça me pollue trop. » The designer's rule:

- a DIRECT settings action (``_SETTINGS_HANDLERS``) that produced its
  note from inside a window RETIRES the window — the note stays alone;
- the confirm cards (provisioning + cycle) retire with their verdict,
  on YES and on NO alike;
- a handler that OPENED a window (the status card) keeps it — the
  close never kills the NEW surface (the identity guard);
- a pin-side click (nothing tracked) is a no-op — the cockpit is a
  pinned message and never deletes itself.
"""

from __future__ import annotations

from types import SimpleNamespace as NS
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# The fakes (Check-107 lesson: a fake interaction ALWAYS carries its locale)
# ---------------------------------------------------------------------------


class _Resp:
    def __init__(self) -> None:
        self.done = False
        self.sent: Any = None

    def is_done(self) -> bool:
        return self.done

    async def defer(self, ephemeral: bool = False) -> None:
        self.done = True

    async def send_message(self, content: Any = None, **kwargs: Any) -> None:
        self.done = True
        self.sent = (content, kwargs)


class _Follow:
    def __init__(self) -> None:
        self.sent: list[Any] = []

    async def send(self, content: Any = None, **kwargs: Any) -> Any:
        self.sent.append((content, kwargs))
        return NS(id="f1")


def _interaction(user: str = "31") -> Any:
    resp = _Resp()
    follow = _Follow()
    message = NS(id="m1", deleted=False)

    async def _delete() -> None:
        message.deleted = True

    message.delete = _delete
    outer = NS(
        user=NS(id=user, guild_permissions=None),
        locale="fr",
        guild_id="42",
        client=NS(
            status_service=NS(bot_admins=(user,)),
            roles_service=None,
            state_service=None,
        ),
        response=resp,
        followup=follow,
        message=message,
        deleted_original=False,
    )

    async def _delete_original() -> None:
        outer.deleted_original = True

    outer.delete_original_response = _delete_original
    return outer


def _strings() -> dict[str, str]:
    from botforge.mods.kingdom.cogs.common import mod_catalog

    return dict(mod_catalog().section("kingdom.settings", "fr"))


@pytest.fixture(autouse=True)
def _clean_windows():
    yield
    from botforge.discord.ui import ephemeral_windows as ew

    ew._live.clear()


async def _open_a_window(interaction: Any, text: str = "fenêtre") -> None:
    """Open a real single-mode window for the interaction's player."""
    from botforge.mods.kingdom.cogs.common import open_unique_ephemeral

    await open_unique_ephemeral(interaction, text)


# ---------------------------------------------------------------------------
# The template (live_unique_window + close_window_if_unmoved)
# ---------------------------------------------------------------------------


async def test_the_retrieval_reads_the_single_scope() -> None:
    from botforge.discord.ui import ephemeral_windows as ew
    from botforge.mods.kingdom.cogs.common import (
        KINGDOM_WINDOW_SCOPE,
        live_unique_window,
    )

    it = _interaction()
    assert live_unique_window(it) is None
    await _open_a_window(it)
    assert live_unique_window(it) is ew.get_live_window(KINGDOM_WINDOW_SCOPE, "31")


async def test_the_close_retires_the_same_window() -> None:
    from botforge.discord.ui import ephemeral_windows as ew
    from botforge.mods.kingdom.cogs.common import (
        KINGDOM_WINDOW_SCOPE,
        close_window_if_unmoved,
        live_unique_window,
    )

    it = _interaction()
    await _open_a_window(it)
    before = live_unique_window(it)
    await close_window_if_unmoved(it, before)
    assert ew.get_live_window(KINGDOM_WINDOW_SCOPE, "31") is None
    assert it.deleted_original, "the window message was deleted"


async def test_the_close_never_kills_a_new_window() -> None:
    from botforge.discord.ui import ephemeral_windows as ew
    from botforge.mods.kingdom.cogs.common import (
        KINGDOM_WINDOW_SCOPE,
        close_window_if_unmoved,
        live_unique_window,
    )

    it = _interaction()
    await _open_a_window(it, "le tiroir")
    before = live_unique_window(it)
    # the HANDLER opened its own surface (the status card): SINGLE mode
    # retired the drawer, the record now points at the new card
    it2 = _interaction()
    await _open_a_window(it2, "la carte état")
    new = live_unique_window(it2)
    await close_window_if_unmoved(it2, before)
    assert ew.get_live_window(KINGDOM_WINDOW_SCOPE, "31") is new, "the new card survived"


async def test_a_pin_side_click_closes_nothing() -> None:
    from botforge.mods.kingdom.cogs.common import close_window_if_unmoved

    it = _interaction()
    await close_window_if_unmoved(it, None)
    assert not it.deleted_original


async def test_the_close_swallows_a_dead_window() -> None:
    from botforge.mods.kingdom.cogs.common import close_window_if_unmoved

    dead = _interaction()

    async def _boom() -> None:
        raise RuntimeError("token expiré")

    dead.delete_original_response = _boom
    # the record still points at the dead window: best-effort, never raises
    from botforge.discord.ui import ephemeral_windows as ew

    ew._live[("mod/kingdom", "31")] = (dead, 0.0)
    from botforge.mods.kingdom.cogs.common import live_unique_window

    before = live_unique_window(dead)
    await close_window_if_unmoved(dead, before)
    assert ew.get_live_window("mod/kingdom", "31") is None, "the record popped"


# ---------------------------------------------------------------------------
# The direct settings action retires the window it rode
# ---------------------------------------------------------------------------


async def test_a_direct_action_retires_its_window(monkeypatch: pytest.MonkeyPatch) -> None:
    from botforge.mods.kingdom.cogs import settings_panel as sp
    from botforge.discord.ui import ephemeral_windows as ew

    it = _interaction()
    await _open_a_window(it, "le tiroir bêta")

    note: dict[str, Any] = {}

    async def _stub(target: Any, strings: dict[str, str]) -> None:
        note["sent"] = True
        await target.followup.send("bêta armée", ephemeral=True)

    monkeypatch.setitem(sp._SETTINGS_HANDLERS, "season-mode", _stub)
    button = sp.SettingsActionButton("season-mode", "Mode saison")
    await button.callback(it)
    assert note.get("sent") is True
    assert ew.get_live_window("mod/kingdom", "31") is None, "the drawer retired"
    assert it.deleted_original


async def test_a_window_opening_handler_keeps_its_new_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from botforge.mods.kingdom.cogs import settings_panel as sp
    from botforge.mods.kingdom.cogs.common import open_unique_ephemeral
    from botforge.discord.ui import ephemeral_windows as ew

    it = _interaction()
    await _open_a_window(it, "le tiroir")

    async def _status_stub(target: Any, strings: dict[str, str]) -> None:
        await open_unique_ephemeral(target, "# la carte état")

    monkeypatch.setitem(sp._SETTINGS_HANDLERS, "status", _status_stub)
    button = sp.SettingsActionButton("status", "Statut")
    await button.callback(it)
    live = ew.get_live_window("mod/kingdom", "31")
    assert live is not None, "the status card the handler OPENED survived"


# ---------------------------------------------------------------------------
# The confirm cards retire with their verdict (yes AND no)
# ---------------------------------------------------------------------------


def _button(view: Any, custom_id: str) -> Any:
    for item in view.walk_children():
        if str(getattr(item, "custom_id", "")) == custom_id:
            return item
    raise AssertionError(f"missing {custom_id}")


async def test_the_cycle_card_retires_on_yes(monkeypatch: pytest.MonkeyPatch) -> None:
    from botforge.mods.kingdom.cogs import settings_panel as sp
    from botforge.discord.ui import ephemeral_windows as ew

    it = _interaction()
    card = sp._cycle_confirm_card(_strings(), "false-start")
    await _open_a_window(it, "carte")

    async def _stub(target: Any, strings: dict[str, str]) -> None:
        await target.followup.send("rembobiné", ephemeral=True)

    monkeypatch.setitem(sp._CYCLE_CONFIRM_HANDLERS, "false-start", _stub)
    yes = _button(card, "kingdom:cycle-confirm:false-start:yes")
    await yes.callback(it)
    assert ew.get_live_window("mod/kingdom", "31") is None
    assert it.deleted_original


async def test_the_cycle_card_retires_on_no() -> None:
    from botforge.mods.kingdom.cogs import settings_panel as sp
    from botforge.discord.ui import ephemeral_windows as ew

    it = _interaction()
    card = sp._cycle_confirm_card(_strings(), "end-season")
    await _open_a_window(it, "carte")

    no = _button(card, "kingdom:cycle-confirm:end-season:no")
    await no.callback(it)
    assert ew.get_live_window("mod/kingdom", "31") is None
    assert it.deleted_original


async def test_the_provisioning_card_retires_on_yes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from botforge.mods.kingdom.cogs import settings_panel as sp
    from botforge.discord.ui import ephemeral_windows as ew

    it = _interaction()
    card = sp._confirm_card(_strings(), "reset")
    await _open_a_window(it, "carte")

    async def _stub(target: Any, action: str) -> str:
        return "salons réinitialisés"

    monkeypatch.setattr(sp, "_run_provisioning", _stub)
    yes = _button(card, "kingdom:confirm:reset:yes")
    await yes.callback(it)
    assert ew.get_live_window("mod/kingdom", "31") is None
    assert it.deleted_original
    assert it.followup.sent and "salons r" in str(it.followup.sent[-1][0])
