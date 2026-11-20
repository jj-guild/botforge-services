"""Kingdoms mod — documented test scenarios (docs/MODS/kingdoms/TESTS.md).

Every scenario in the mod's TESTS.md has ONE test here, named after the
scenario id (``SC-KING-NNN`` in the docstring). CI runs this file
explicitly (``pytest tests modules/mods/*/tests/test_scenarios.py``), and
the botforge docs check (validate_docs.py) fails when a documented
scenario has no test here. The agent writes the missing scenario tests in
the same PR as the doc change.

R6 note: this file lives under modules/ — no direct ``import discord``
here; it drives the mod's own packages only.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest
import yaml

_MOD_ROOT = Path(__file__).resolve().parents[1]  # modules/mods/kingdom
_CONF = _MOD_ROOT / "conf"


def _conf_yaml(name: str) -> dict:
    return yaml.safe_load((_CONF / name).read_text(encoding="utf-8")) or {}


def test_SC_KING_001_console_salon_declared_no_settings_salon() -> None:
    """SC-KING-001 — the admin salon is `console`, no `settings` salon remains."""
    mod = _conf_yaml("mod.yaml")
    keys = [c["key"] for c in mod.get("channels", [])]
    assert "console" in keys
    assert "settings" not in keys


def test_SC_KING_002_all_mod_view_ids_follow_the_r9_contract() -> None:
    """SC-KING-002 — every declared view id is panel:mod:kingdom:…/menu:mod:kingdom:…."""
    views = _conf_yaml("views.yaml").get("views", {})
    assert views, "the mod declares its surfaces"
    for view_id in views:
        assert view_id.startswith(("panel:mod:kingdom:", "menu:mod:kingdom:")), view_id


def test_SC_KING_003_console_ops_scoped_to_the_mod_console() -> None:
    """SC-KING-003 — the console ops carry mod="kingdom" (mod console only)."""
    from botforge.mods.kingdom.cogs.console import kingdom_console_actions

    actions = kingdom_console_actions()
    assert len(actions) == 7
    assert all(a.mod == "kingdom" for a in actions)
    assert {a.key for a in actions} == {
        "kingdom-relaunch",
        "kingdom-reset",
        "kingdom-clock",
        "kingdom-debug-status",
        "kingdom-bypass-on",
        "kingdom-bypass-off",
        "kingdom-skip-event",
    }


def test_SC_KING_004_console_surface_id_is_the_sdk_one() -> None:
    """SC-KING-004 — the wired console surface is panel:mod:kingdom:admin:console."""
    from botforge.mods.kingdom.cogs.settings_panel import CONSOLE_VIEW_KEY

    assert CONSOLE_VIEW_KEY == "panel:mod:kingdom:admin:console"


def test_SC_KING_005_service_errors_map_to_user_facing_notes() -> None:
    """SC-KING-005 — a KingdomError code maps to its i18n note (never log-only)."""
    from botforge.mods.kingdom.cogs.common import service_failure_note
    from botforge.mods.kingdom.cogs.settings_panel import settings_strings
    from botforge.mods.kingdom.service import KingdomLimitError, NoSeasonError

    for locale in ("fr", "en"):
        s = settings_strings(locale)
        assert service_failure_note(s, "settings_failed", NoSeasonError("x")) == s[
            "settings_err_kingdoms_no_season"
        ]
        assert service_failure_note(s, "settings_failed", KingdomLimitError("x")) == s[
            "settings_err_kingdoms_kingdom_limit"
        ]


def test_SC_KING_006_modals_build_without_deprecation_warnings() -> None:
    """SC-KING-006 — discord.py 2.7: TextInputs ride discord.ui.Label."""
    from botforge.mods.kingdom.cogs import settings_panel

    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        for cls in (
            settings_panel._LaunchModal,
            settings_panel._AssignModal,
            settings_panel._AddKingdomModal,
            settings_panel._RemoveModal,
        ):
            modal = cls(settings_panel.settings_strings("fr"))
            labels = [c for c in modal.walk_children() if type(c).__name__ == "Label"]
            assert labels and all(len(l.text) <= 45 for l in labels)


def test_SC_KING_007_debug_service_builds_from_the_stack() -> None:
    """SC-KING-007 — the ported admin-debug toolkit builds from a mod stack."""
    from types import SimpleNamespace

    from botforge.mods.kingdom.admin_debug import build_debug_service

    stack = SimpleNamespace(
        _store=None, config=object(), kingdoms=object(), territories=object(),
        attacks=object(), voliere=None, time_machine=None,
    )
    debug = build_debug_service(stack)
    for method in ("list_attacks", "view_cooldowns", "skip_to_next_event", "grant_bird"):
        assert callable(getattr(debug, method)), method


def test_SC_KING_008_phases_loop_imports_cleanly() -> None:
    """SC-KING-008 — the attack phases loop imports (no stale sibling import)."""
    import importlib

    importlib.import_module("botforge.mods.kingdom.cogs.phases")


def test_SC_KING_009_locale_parity_fr_en() -> None:
    """SC-KING-009 — the mod's fr/en locale catalogs carry the same keys."""
    fr = _conf_yaml("locales/fr.yaml")
    en = _conf_yaml("locales/en.yaml")

    def keys(d: dict, prefix: str = "") -> set[str]:
        out: set[str] = set()
        for k, v in d.items():
            path = f"{prefix}{k}"
            if isinstance(v, dict):
                out |= keys(v, path + ".")
            else:
                out.add(path)
        return out

    fr_keys = {k.split(".", 1)[1] for k in keys(fr)}
    en_keys = {k.split(".", 1)[1] for k in keys(en)}
    assert fr_keys == en_keys


def test_SC_KING_010_the_mods_pins_are_declared() -> None:
    """SC-KING-010 — the pinned panels (console, validation, market, …) are registered."""
    src = (_MOD_ROOT / "cogs" / "kingdom" / "__init__.py").read_text(encoding="utf-8")
    for pin_key in (
        "panel:mod:kingdom:attack",
        "panel:mod:kingdom:candidates",
        "panel:mod:kingdom:console",
        "panel:mod:kingdom:time-machine",
        "panel:mod:kingdom:distributor",
        "panel:mod:kingdom:validation",
        "panel:mod:kingdom:market",
    ):
        assert f'key="{pin_key}"' in src, pin_key
    # apply/register pins ride their module constants
    assert "APPLY_VIEW_KEY" in src and "REGISTER_VIEW_KEY" in src


def test_SC_KING_011_machine_panel_durations_read_from_the_active_preset() -> None:
    """SC-KING-011 — the ⏱️ machine à temps reads its rhythm from data.

    machine-temps-v4 (Drasah 20/11): the official season lasts THREE
    weeks; the panel's length and rhythm labels derive from the active
    preset (official ``weeks`` / beta compressed plan), never a
    hardcoded count.
    """
    from types import SimpleNamespace

    from botforge.mods.kingdom.cogs.time_machine import (
        season_length_label,
        setup_rhythm_phrase,
    )
    from botforge.mods.kingdom.config import default_season_config

    config = default_season_config()
    assert config.weeks == 3, "the official season is three weeks (calibrage)"
    assert season_length_label("fr", config, SimpleNamespace(beta_name=None)) == "3 semaines"
    phrase = setup_rhythm_phrase("fr", config, SimpleNamespace(beta_name=None))
    assert "saison de 3 semaines" in phrase and "dimanche 23h30" in phrase
    assert season_length_label("fr", config, SimpleNamespace(beta_name="now")) == "52h (beta compressée)"
    assert "T0+52h" in setup_rhythm_phrase("fr", config, SimpleNamespace(beta_name="now"))


def test_SC_KING_012_machine_pin_refreshes_itself() -> None:
    """SC-KING-012 — the machine pin is auto-updated (the refresher loop).

    machine-temps-v4 (Drasah 20/11): « Panneau épinglé auto-mis à
    jour » — a light 5-minute pass re-ensures the cockpit pin; an
    unchanged pin costs no API call (the platform's fingerprint guard).
    """
    import asyncio

    from botforge.discord.static_pins import reset_static_pins
    from botforge.mods.kingdom.cogs.time_machine import (
        REFRESH_MINUTES,
        run_machine_refresh_pass,
    )

    assert REFRESH_MINUTES == 5
    reset_static_pins()

    class _Bot:
        guilds: list = []

    # no machine spec registered → the pass is a no-op, never a raise
    assert asyncio.run(run_machine_refresh_pass(_Bot())) == 0


def test_SC_KING_013_parametres_salon_restored() -> None:
    """SC-KING-013 — the admin salon WEARS the designer's ⚙️ paramètres
    name (capture 08/11).

    parametres-restore-v1 (Drasah 20/11): the KEY stays `console`
    (SC-KING-001) but the declared display name, the pinned panel's
    title and its « Administration » section header match the
    reference capture — the surface is recognisable at a glance.
    """
    mod = _conf_yaml("mod.yaml")
    channel = next(c for c in mod["channels"] if c["key"] == "console")
    assert channel["display_name"] == "⚙️ paramètres"
    for locale in ("fr", "en"):
        strings = _conf_yaml(f"locales/{locale}.yaml")[locale]["kingdom"]["settings"]
        assert strings["settings_title"] == "⚙️ Kingdoms — paramètres", locale
        assert strings["settings_section"] == "Administration", locale
