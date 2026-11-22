"""windows-v2 (Drasah 21/11) — des fenêtres qui se ferment.

The designer's contract, one test per point:

- EVERY mod ephemeral window carries an explicit ✖️ close button
  (« rejeter le message » n'est pas découvrable) — views AND text
  notes (a note becomes the declared ``panel:mod:kingdom:note``);
- the drawer dead ends are gone: every console drawer carries its
  ↩️ Console back row;
- a window closes ITSELF after the scope's TTL (14 minutes of data,
  never a hardcoded sleep somewhere else);
- the single-window contract holds across consecutive opens (the
  live « two drawers at once » report): opening window 2 deletes
  window 1;
- the validation fast-ack is covered in test_kingdom_validation_surfaces.
"""

from __future__ import annotations

import re
from types import SimpleNamespace as NS
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# The fakes (the Check-107 lesson: a fake interaction ALWAYS carries
# its locale)
# ---------------------------------------------------------------------------


class _Resp:
    def __init__(self) -> None:
        self.done = False
        self.deferred = False
        self.sent: Any = None

    def is_done(self) -> bool:
        return self.done

    async def defer(self, ephemeral: bool = False) -> None:
        self.done = True
        self.deferred = True

    async def send_message(self, content: Any = None, **kwargs: Any) -> None:
        self.done = True
        self.sent = (content, kwargs)


class _Follow:
    def __init__(self) -> None:
        self.sent: list[Any] = []
        self.opened: list[Any] = []

    async def send(self, content: Any = None, **kwargs: Any) -> Any:
        self.sent.append((content, kwargs))
        # drawer-build-v1 (Check 136) : la fenêtre d'un clic acké vit
        # dans le followup ET se ferme par message.delete() — le faux
        # porte les deux (la fenêtre unique du core suit ce chemin).
        message = NS(id=f"f{len(self.sent)}", deleted=False)

        async def _delete() -> None:
            message.deleted = True

        message.delete = _delete
        self.opened.append(message)
        return message


def _interaction(user: str = "7") -> Any:
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
        # the seam closes a live window through delete_original_response
        deleted_original=False,
    )

    async def _delete_original() -> None:
        outer.deleted_original = True

    outer.delete_original_response = _delete_original
    return outer


def _ids(view: Any) -> list[str]:
    return [
        str(item.custom_id)
        for item in view.walk_children()
        if getattr(item, "custom_id", None)
    ]


def _wired_stack() -> NS:
    """A minimal service stack: a setup season, no realms, no lords."""

    async def _kingdoms() -> list[Any]:
        return []

    async def _lords() -> list[Any]:
        return []

    async def _current_season() -> Any:
        return NS(phase="setup", imposed_kingdoms=False)

    async def _realms() -> list[Any]:
        return []

    return NS(
        kingdoms=NS(
            kingdoms=_kingdoms,
            lords=_lords,
            current_season=_current_season,
        ),
        realms=NS(realms=_realms),
    )


@pytest.fixture(autouse=True)
def _clean_windows():
    yield
    from botforge.discord.ui import ephemeral_windows as ew

    ew._live.clear()
    for task in list(ew._close_tasks.values()):
        task.cancel()
    ew._close_tasks.clear()


# ---------------------------------------------------------------------------
# The ✖️ close button rides every window
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_every_view_window_carries_the_close_button() -> None:
    from botforge.mods.kingdom.cogs.common import open_unique_ephemeral
    from botforge.mods.kingdom.cogs.settings_panel import _build_drawer

    inter = _interaction()
    view = await _build_drawer("atelier", "fr", None, "42")
    await open_unique_ephemeral(inter, view=view)
    _content, kwargs = inter.response.sent
    assert "kingdom:window:close" in _ids(kwargs["view"]), "the ✖️ rides the view"
    assert kwargs["ephemeral"] is True


@pytest.mark.asyncio
async def test_a_text_note_becomes_a_closable_declared_surface() -> None:
    from botforge.mods.kingdom.cogs.common import open_unique_ephemeral

    inter = _interaction()
    await open_unique_ephemeral(inter, content="C'est noté.")
    content, kwargs = inter.response.sent
    assert content is None, "the text rides INSIDE the note surface now"
    view = kwargs["view"]
    assert "kingdom:window:close" in _ids(view)
    texts = [c.content for c in view.walk_children() if type(c).__name__ == "TextDisplay"]
    assert any("C'est noté" in str(t) for t in texts)
    assert any("panel:mod:kingdom:note" in str(t) for t in texts), "the id footer rides"


@pytest.mark.asyncio
async def test_the_close_click_deletes_the_window_and_pops_the_record() -> None:
    from botforge.discord.ui import ephemeral_windows as ew

    from botforge.mods.kingdom.cogs.common import (
        KINGDOM_WINDOW_SCOPE,
        KingdomWindowCloseButton,
        open_unique_ephemeral,
    )
    from botforge.mods.kingdom.cogs.settings_panel import _build_drawer

    inter = _interaction(user="11")
    view = await _build_drawer("atelier", "fr", None, "42")
    await open_unique_ephemeral(inter, view=view)
    assert ew.get_live_window(KINGDOM_WINDOW_SCOPE, "11") is not None

    match = re.compile("kingdom:window:close").fullmatch("kingdom:window:close")
    button = await KingdomWindowCloseButton.from_custom_id(inter, NS(label="x"), match)
    assert button.item.label == "✖️ Fermer", "from_custom_id reads the settings catalog"
    await button.callback(inter)
    assert inter.message.deleted, "the clicked window is deleted"
    assert ew.get_live_window(KINGDOM_WINDOW_SCOPE, "11") is None, "the record pops"


# ---------------------------------------------------------------------------
# The single-window contract
# ---------------------------------------------------------------------------


async def _nav_click(inter: Any, drawer: str) -> None:
    """One drawer/console open through the REAL nav callback."""
    from botforge.mods.kingdom.cogs.settings_panel import KingdomSettingsNavButton

    button = KingdomSettingsNavButton(drawer, "label")
    await button.callback(inter)


def _wired() -> Any:
    import contextlib
    import unittest.mock as mock

    from botforge.mods.kingdom.cogs import common, panel

    stack = _wired_stack()
    cm = contextlib.ExitStack()
    cm.enter_context(mock.patch.object(common, "wiring", lambda: stack))
    cm.enter_context(mock.patch.object(panel, "current_bot", lambda: None))
    return cm


@pytest.mark.asyncio
async def test_two_consecutive_windows_keep_a_single_window() -> None:
    """The live repro (21/11: admissions + atelier visible at once).

    Opening the second drawer CLOSES the first: the seam's single
    record means the last window wins — never two drawers stacked.
    """
    from botforge.discord.ui import ephemeral_windows as ew

    from botforge.mods.kingdom.cogs.common import KINGDOM_WINDOW_SCOPE

    with _wired():
        first = _interaction(user="13")
        await _nav_click(first, "admissions")
        # drawer-build-v1 (Check 136) : fast-ack — le clic est acquitté
        # immédiatement, la fenêtre vit dans le followup
        assert first.response.deferred, "the click is acked (deferred) at once"
        assert first.followup.sent, "window 1 (the drawer) rides the followup"

        second = _interaction(user="13")
        await _nav_click(second, "atelier")

    assert first.followup.opened[0].deleted, (
        "window 1 is closed (its followup message deleted) when window 2 opens"
    )
    live = ew.get_live_window(KINGDOM_WINDOW_SCOPE, "13")
    assert live is not None, "the seam tracks the LAST window only"


@pytest.mark.asyncio
async def test_a_drawer_has_no_back_button_and_no_console_target() -> None:
    """windows-v2 review (Drasah 21/11): the ↩️ Console row is GONE.

    The cockpit is a PIN — it never left the screen, so a back button
    duplicated a view the operator already has. Only ✖️ Fermer stays.
    """
    with _wired():
        inter = _interaction(user="15")
        await _nav_click(inter, "atelier")
    assert inter.response.deferred, "fast-ack: the click never races the 3-second clock"
    _content, kwargs = inter.followup.sent[0]
    ids = _ids(kwargs["view"])
    assert not any("console-nav:console" in i for i in ids), "no back-to-console ids ship"
    assert "kingdom:window:close" in ids, "the ✖️ stays — the ONLY way out"


# ---------------------------------------------------------------------------
# The TTL auto-close (Drasah: 14 minutes of data, not a hardcoded sleep)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_window_closes_itself_after_the_ttl() -> None:
    from botforge.discord.ui import ephemeral_windows as ew

    from botforge.discord.ui.ephemeral_windows import set_window_ttl

    from botforge.mods.kingdom.cogs.common import KINGDOM_WINDOW_SCOPE, open_unique_ephemeral
    from botforge.mods.kingdom.cogs.settings_panel import _build_drawer

    inter = _interaction(user="19")
    view = await _build_drawer("atelier", "fr", None, "42")
    set_window_ttl(KINGDOM_WINDOW_SCOPE, 0.05)
    try:
        await open_unique_ephemeral(inter, view=view)
        assert not inter.deleted_original, "the window is live"
        await asyncio_sleep(0.3)
    finally:
        set_window_ttl(KINGDOM_WINDOW_SCOPE, 14 * 60.0)
    assert inter.deleted_original, "the window closed ITSELF after the ttl"
    assert ew.get_live_window(KINGDOM_WINDOW_SCOPE, "19") is None


async def asyncio_sleep(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)
