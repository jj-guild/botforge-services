"""The mod pin lifecycle covers the mod's WHOLE scope (Drasah 18/11).

`ensure_mod_pins` (the install/repair path) must land every static pin
registered under ``mod/<name>`` — the SDK home/admin menus AND the
mod's own pinned surfaces (its cogs register them at boot). The
postuler-hybride-v1 regression: the repair created the declared
« apply » channel but never pinned its golden panel, because
``_mod_pin_specs`` filtered to the menus only.
"""

from __future__ import annotations

from typing import Any

from botforge.discord.scope_pins import _mod_pin_specs
from botforge.discord.static_pins import StaticPinnedView, register_static_pin, reset_static_pins


def _spec(key: str, scope: str) -> StaticPinnedView:
    async def _channel(guild_id: str) -> str:
        return "1"

    async def _layout(guild_id: str) -> Any:
        return None

    return StaticPinnedView(
        key=key,
        mark_suffix=key,
        resolve_channel=_channel,
        build_layout=_layout,
        scope=scope,
    )


def setup_function() -> None:
    reset_static_pins()


def teardown_function() -> None:
    reset_static_pins()


def test_the_mod_specs_cover_home_admin_and_the_mods_own_pins() -> None:
    """home + admin + the cog-declared panels — the WHOLE mod scope."""
    register_static_pin(_spec("panel:mod:kingdom:home", "mod/kingdom"))
    register_static_pin(_spec("panel:mod:kingdom:admin", "mod/kingdom"))
    register_static_pin(_spec("panel:mod:kingdom:apply", "mod/kingdom"))
    register_static_pin(_spec("view:mod:other:home", "mod/other"))
    register_static_pin(_spec("view:home", ""))

    keys = {spec.key for spec in _mod_pin_specs(None, "kingdom")}
    assert keys == {
        "panel:mod:kingdom:home",
        "panel:mod:kingdom:admin",
        "panel:mod:kingdom:apply",
    }, "the mod's own pinned surfaces ride the install/repair lifecycle"


def test_the_mod_specs_stay_empty_without_pins() -> None:
    """No registered pins — the mod specs degrade to empty."""
    assert _mod_pin_specs(None, "kingdom") == []
