"""Kingdoms mod attack panel (P4.1b tranche 1) — wiring smoke tests (#368).

The Discord surfaces degrade quietly when their stack (Mongo) is not
wired: these tests pin that contract — the cog modules import, the
strings carry every locale, and the panel build falls back to the
defaults without a catalog or a database.
"""

from __future__ import annotations

import pytest


def test_cog_modules_import() -> None:
    """The cog package's modules import (contract, wiring, panels)."""
    from botforge.mods.kingdom.cogs.kingdom import common, panel, strings  # noqa: F401


def test_strings_cover_both_locales() -> None:
    """FR/EN defaults carry the SAME key set (no half-translated panel)."""
    from botforge.mods.kingdom.cogs.kingdom.strings import DEFAULTS

    assert set(DEFAULTS["fr"]) == set(DEFAULTS["en"])
    assert DEFAULTS["fr"]["defend_button"]
    assert DEFAULTS["en"]["defend_button"]


def test_strings_resolve_without_catalog() -> None:
    """``strings`` degrades to the defaults when no catalog is wired."""
    from botforge.mods.kingdom.cogs.kingdom.strings import DEFAULTS, strings

    assert strings("fr")["defend_button"] == DEFAULTS["fr"]["defend_button"]
    assert strings("en")["panel_title"] == DEFAULTS["en"]["panel_title"]
    # an unknown locale falls back on the English defaults
    assert strings("zz")["panel_title"] == DEFAULTS["en"]["panel_title"]


def test_room_key_is_short_and_stable() -> None:
    """The salon buttons' digests stay under Discord's custom-id limit."""
    from botforge.mods.kingdom.cogs.kingdom.common import room_key

    key = room_key("0123456789abcdef0123456789abcdef")
    assert len(key) == 16
    assert key == room_key("0123456789abcdef0123456789abcdef")
    assert key != room_key("0123456789abcdef0123456789abcdee")


@pytest.mark.asyncio
async def test_panel_build_degrades_without_stack() -> None:
    """``build_attack_panel`` renders the pinned layout (locale fallback)."""
    from botforge.mods.kingdom.cogs.kingdom.panel import build_attack_panel

    view = await build_attack_panel("123")
    assert view is not None


@pytest.mark.asyncio
async def test_wiring_never_raises_without_mongo() -> None:
    """``wiring`` degrades (None) — the surfaces show no-service notes."""
    from botforge.mods.kingdom.cogs.kingdom.common import wiring

    wiring()
