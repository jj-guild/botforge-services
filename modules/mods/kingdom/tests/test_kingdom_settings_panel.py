"""The ⚙️ Paramètres panel (epic #412 T1) — wiring smoke tests.

The admin cockpit is ONE template (``view:mod:kingdom:settings``)
instantiated by the ``SETTINGS_ACTIONS`` table: every action rides a
platform seam (service contract, provisioning seams, beta phase
toggle, ``require_admin``) — these tests pin the contract down.
"""

from __future__ import annotations


def test_settings_panel_module_imports() -> None:
    """The panel exposes its template key, builder and button class."""
    from botforge.mods.kingdom.cogs.settings_panel import (
        SETTINGS_VIEW_KEY,
        build_settings_panel,
    )

    assert SETTINGS_VIEW_KEY == "view:mod:kingdom:settings"
    assert callable(build_settings_panel)


def test_settings_panel_is_one_template_of_twelve_actions() -> None:
    """The designer's 12 actions, verbatim order (capture image-12)."""
    from botforge.mods.kingdom.cogs import settings_panel

    actions = tuple(action for action, _key, _style in settings_panel._SETTINGS_ACTIONS)
    assert actions == (
        "launch",
        "start-season",
        "start-beta",
        "status",
        "deploy",
        "sync",
        "reset",
        "assign",
        "add-kingdom",
        "season-mode",
        "remove",
        "hat",
    )
    # every action key answers a DynamicItem custom id + a FR label
    from botforge.mods.kingdom.cogs.settings_panel import SettingsActionButton

    assert (
        SettingsActionButton("launch", "▶️ Lancer la saison").custom_id
        == "kingdom:settings:launch"
    )


def test_settings_buttons_custom_ids_restart_proof() -> None:
    """The confirm card rides the same template (yes/no suffixes)."""
    from botforge.mods.kingdom.cogs.settings_panel import SettingsActionButton

    assert (
        SettingsActionButton("reset-yes", "x").custom_id == "kingdom:settings:reset-yes"
    )
    assert (
        SettingsActionButton("deploy-no", "x").custom_id == "kingdom:settings:deploy-no"
    )


def test_settings_actions_declared_in_views_yaml() -> None:
    """The panel template + its confirm card are declared surfaces."""
    from pathlib import Path

    views = (
        Path(__file__).resolve().parents[1]
        / "conf"
        / "views.yaml"
    ).read_text(encoding="utf-8")
    assert "view:mod:kingdom:settings:" in views
    assert "surface:mod:kingdom:settings:confirm:" in views


def test_settings_strings_parity() -> None:
    """Every action's label exists in both locales; formats have arity."""
    from botforge.mods.kingdom.cogs.settings_panel import (
        _SETTINGS_ACTIONS,
        settings_strings,
    )

    keys = ["settings_title", "settings_denied", "settings_cancelled"]
    keys += [key for _action, key, _style in _SETTINGS_ACTIONS]
    keys += [
        "settings_deploy_done",
        "settings_sync_done",
        "settings_reset_done",
        "settings_mode_imposed",
        "settings_mode_free",
    ]
    for locale in ("fr", "en"):
        s = settings_strings(locale)
        for key in keys:
            assert s.get(key), f"missing {key} in {locale}"
        s["settings_error"].format("boom")
        s["settings_deploy_done"].format(channels=1, roles=2, pins=3)
        s["settings_sync_done"].format(pins=1)
        s["settings_reset_done"].format(channels=4)


def test_the_settings_panel_builds_with_a_fake_service() -> None:
    """The pinned panel renders with a live season (status card data)."""
    import asyncio

    from botforge.mods.kingdom.cogs.settings_panel import build_settings_panel

    view = asyncio.run(build_settings_panel("123"))
    assert view is not None
