"""console-v2 (Drasah 21/11) — the cockpit and its four drawers.

The approved mockup's contract: the flat 11-button list becomes a
CONTEXTUAL cockpit (the season state up top, ONE « Le cycle » row,
the fixed drawer rows), each drawer a declared ephemeral surface
carrying EXISTING registrations (no new mechanic, #395's direction).
"""

from __future__ import annotations

from types import SimpleNamespace


def _ids(view: object) -> list[str]:
    return [
        str(item.custom_id)
        for item in view.walk_children()  # type: ignore[attr-defined]
        if getattr(item, "custom_id", None)
    ]


def _texts(view: object) -> list[str]:
    return [
        child.content
        for child in view.walk_children()  # type: ignore[attr-defined]
        if type(child).__name__ == "TextDisplay"
    ]


def test_the_cockpit_is_zoned_and_contextual() -> None:
    """The panel carries the cockpit's zones + the drawer nav ids."""
    import asyncio

    from botforge.mods.kingdom.cogs.settings_panel import build_settings_panel
    from botforge.mods.kingdom.cogs.settings_panel import settings_strings

    view = asyncio.run(build_settings_panel("123"))
    ids = _ids(view)
    joined = "\n".join(_texts(view))
    fr = settings_strings("fr")
    en = settings_strings("en")
    for zone in (
        "settings_zone_cycle_label",
        "settings_zone_regie_label",
        "settings_zone_atelier_label",
    ):
        assert str(fr[zone]) in joined or str(en[zone]) in joined, (
            f"the cockpit must carry the {zone} zone"
        )
    # off-season cockpit: the cycle row offers the PREPARE gesture and
    # the fixed rows open the three working drawers — the sas has
    # nothing to sort before a season exists (off, no admissions nav)
    assert "kingdom:settings:launch" in ids
    for drawer in ("regie", "atelier", "beta"):
        assert f"kingdom:console-nav:{drawer}" in ids, f"the {drawer} drawer must be a click away"
    assert "kingdom:console-nav:admissions" not in ids, (
        "off-season, the admissions sas has nothing to sort yet"
    )
    assert "kingdom:settings:start-season" not in ids, (
        "off-season, the DÉMARRAGE gesture must NOT be offered (the sas ruling)"
)


def test_the_setup_cockpit_opens_the_sas_not_the_launch() -> None:
    """A SETUP season = the admissions sas + the start gesture,
    never a fresh launch (launching would wipe the season)."""
    import asyncio
    import unittest.mock as mock

    from botforge.mods.kingdom.cogs import settings_panel as sp

    season = SimpleNamespace(phase="setup", imposed_kingdoms=False)

    class _Kingdoms:
        async def kingdoms(self):
            return []

        async def lords(self):
            return []

        async def current_season(self):
            return season

    stack = SimpleNamespace(
        kingdoms=_Kingdoms(),
        realms=SimpleNamespace(realms=lambda: _async_none()),
    )

    async def _async_none():
        return []

    stack.realms.realms = _async_none
    with mock.patch.object(sp, "wiring", lambda: stack):
        view = asyncio.run(sp.build_settings_panel("123"))
    ids = _ids(view)
    assert "kingdom:console-nav:admissions" in ids, "setup: the sas must be a click away"
    assert "kingdom:settings:start-season" in ids, "setup: the start gesture stays reachable (no hard lock)"
    assert "kingdom:settings:launch" not in ids, "setup: a fresh launch would wipe the sas"
    assert not any(i in ("kingdom:console:relaunch", "kingdom:console:reset", "kingdom:console:clock") for i in ids), (
        "setup: the running-season ops have nothing to run yet"
    )


def test_the_nav_template_never_collides_with_the_actions() -> None:
    """Fullmatch rule: no id fullmatches two registered templates.

    discord.py 2.7 dispatches a click to EVERY registered dynamic
    template that fullmatches the id — a colliding id fires two
    handlers (the second dies with 40060).
    """
    import re

    from botforge.mods.kingdom.cogs.settings_panel import (
        KingdomSettingsNavButton,
        SettingsActionButton,
    )

    settings_template = re.compile(SettingsActionButton.__discord_ui_compiled_template__.pattern)
    nav_template = re.compile(KingdomSettingsNavButton.__discord_ui_compiled_template__.pattern)
    for candidate in (
        "kingdom:console-nav:admissions",
        "kingdom:console-nav:regie",
        "kingdom:console-nav:atelier",
        "kingdom:console-nav:beta",
    ):
        assert nav_template.fullmatch(candidate)
        assert not settings_template.fullmatch(candidate)
    for candidate in (
        "kingdom:settings:launch",
        "kingdom:settings:start-season",
        "kingdom:settings:reset",
    ):
        assert settings_template.fullmatch(candidate)
        assert not nav_template.fullmatch(candidate)


def test_the_admissions_drawer_carries_the_realm_entry_decisions() -> None:
    """The sas lists each join request with its ✅/❌ (t2a reused)."""
    from botforge.mods.kingdom.cogs.common import mod_catalog
    from botforge.mods.kingdom.cogs.settings_panel import (
        _admissions_drawer,
        settings_strings,
    )

    realm = SimpleNamespace(
        slug="aegis",
        name="Royaume d'Aegis",
        king_name="blank",
        presentation="Un royaume de testeurs endurcis." + "x" * 300,
        join_request={"requested_at": 1732202820},
    )
    vstrings = dict(mod_catalog().section("kingdom.validation", "fr"))
    view = _admissions_drawer(settings_strings("fr"), vstrings, [realm])
    ids = _ids(view)
    assert "kingdom:valid:realmjoin:aegis:ok" in ids
    assert "kingdom:valid:realmjoin:aegis:no" in ids
    # the presentation rides along, excerpted
    joined = "\n".join(_texts(view))
    assert "Un royaume de testeurs endurcis." in joined
    # an empty sas says so in plain words
    empty = _admissions_drawer(settings_strings("fr"), vstrings, [])
    assert str(settings_strings("fr")["settings_admissions_empty"]) in "\n".join(_texts(empty))


def test_the_fixed_drawers_reuse_only_existing_registrations() -> None:
    """Régie / atelier / beta ride the existing buttons, nothing new."""
    from botforge.mods.kingdom.cogs.settings_panel import (
        _beta_drawer,
        _regie_drawer,
        settings_strings,
    )

    ids = _ids(_regie_drawer(settings_strings("fr")))
    assert sorted(ids) == [
        "kingdom:settings:add-kingdom",
        "kingdom:settings:assign",
        "kingdom:settings:remove",
        "kingdom:settings:season-mode",
    ]
    assert "kingdom:settings:start-beta" in _ids(_beta_drawer(settings_strings("fr")))


def test_the_running_cockpit_builds_in_every_engine_phase() -> None:
    """console-crash-v1's regression: the cockpit renders for EVERY
    season phase — a missing per-phase hint key once crashed the pin
    refresh, and the refresh's superseded cleanup then EMPTIED the
    console salon (delete-before-recreate, recreate dying on the same
    crash). The phase-to-key mapping must stay total, FOREVER.
    """
    import asyncio
    import unittest.mock as mock

    from botforge.mods.kingdom.cogs import settings_panel as sp

    def _stack(phase: str | None) -> object:
        season = SimpleNamespace(phase=phase, imposed_kingdoms=False) if phase else None

        class _Kingdoms:
            async def kingdoms(self):
                return []

            async def lords(self):
                return []

            async def current_season(self):
                return season

        class _Realms:
            async def realms(self):
                return []

        return SimpleNamespace(kingdoms=_Kingdoms(), realms=_Realms())

    for phase in (None, "setup", "started"):
        with mock.patch.object(sp, "wiring", lambda s=_stack(phase): s):
            view = asyncio.run(sp.build_settings_panel("123"))
        assert view is not None, f"phase={phase!r}: the cockpit must NEVER crash at render"
    # and the started rendering answers the running gesture set
    with mock.patch.object(sp, "wiring", lambda s=_stack("started"): s):
        view = asyncio.run(sp.build_settings_panel("123"))
    ids = _ids(view)
    assert "kingdom:console:relaunch" in ids, "started: the running ops ride the cycle row"
    assert "kingdom:console-nav:admissions" in ids
    assert "kingdom:settings:launch" not in ids, "started: a fresh launch would wipe the season"
    assert "kingdom:settings:start-season" not in ids, "started: the season is already started"


def test_the_drawers_are_declared_surfaces() -> None:
    """#381 ruling 1: every rendered surface rides conf/views.yaml."""
    from pathlib import Path

    from botforge.mods.kingdom.cogs.settings_panel import _DRAWERS

    views = (
        Path(__file__).resolve().parents[1] / "conf" / "views.yaml"
    ).read_text(encoding="utf-8")
    for drawer, view_id in _DRAWERS.items():
        assert f"{view_id}:" in views, f"the {drawer} drawer must be declared"


def test_the_console_v2_strings_exist_in_both_locales() -> None:
    """The cockpit's zones and the drawers' lines, fr AND en."""
    from botforge.mods.kingdom.cogs.settings_panel import settings_strings

    keys = [
        "settings_cockpit_subtitle",
        "settings_cycle_off_hint",
        "settings_cycle_setup_hint",
        "settings_cycle_started_hint",
        "settings_cycle_running_hint",
        "settings_zone_cycle_label",
        "settings_zone_regie_label",
        "settings_zone_atelier_label",
        "settings_nav_admissions_button",
        "settings_nav_regie_button",
        "settings_nav_atelier_button",
        "settings_nav_beta_button",
        "settings_admissions_title",
        "settings_admissions_hint",
        "settings_admissions_empty",
        "settings_regie_title",
        "settings_regie_hint",
        "settings_atelier_title",
        "settings_atelier_hint",
        "settings_atelier_heal_note",
        "settings_beta_title",
        "settings_beta_hint",
        "settings_beta_sas_note",
        "settings_phase_setup",
        "settings_phase_started",
    ]
    for locale in ("fr", "en"):
        strings = settings_strings(locale)
        for key in keys:
            assert strings.get(key), f"missing {key} in {locale}"
