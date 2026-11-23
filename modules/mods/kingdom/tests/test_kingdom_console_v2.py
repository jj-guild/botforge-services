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


def test_the_header_reads_one_state_per_line() -> None:
    """cockpit-lisible-v1 (Drasah 21/11 « tout est compressé »).

    The header lines: the parcours badge, then phase/sas/mode one
    line each, then the MATTER (kingdoms header counting + names, the
    crew on ONE line). Each marker rides FIRST so the eye can scan.
    """
    import asyncio
    import unittest.mock as mock
    from types import SimpleNamespace as NS

    from botforge.mods.kingdom.cogs import settings_panel as sp
    from botforge.mods.kingdom.cogs.settings_panel import settings_strings

    season = NS(phase="setup", imposed_kingdoms=False)

    class _Kingdoms:
        async def kingdoms(self):
            return [NS(name="AEGIS", is_gaia=False)]

        async def lords(self):
            return []

        async def current_season(self):
            return season

    stack = NS(
        kingdoms=_Kingdoms(),
        realms=NS(realms=lambda: _async_none()),
    )

    async def _async_none():
        return []

    stack.realms.realms = _async_none
    with mock.patch.object(sp, "wiring", lambda: stack):
        lines, state = asyncio.run(sp._season_state(
            settings_strings("fr"), bot=NS(state_service=None), guild_id="42"
        ))
    assert state == "setup"
    assert lines[0].startswith("🧭"), "the parcours badge rides FIRST"
    joined = "\n".join(lines)
    assert "**Phase : " in joined, "the phase is a bold line of its own"
    assert "**Sas ouvert**" in joined or "**Sas fermé**" in joined
    assert "**Saison libre**" in joined, "the mode reads as a line, not a label: value"
    assert "🏰 **Royaumes en saison (1)**" in joined, "the kingdoms get a COUNTED header"
    assert "AEGIS" in joined, "the admitted names stay visible"
    assert "**Seigneurs engagés :**" in joined and "En file :" in joined, "the crew is ONE line"


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
    # the sas door — sas-v2 (Drasah 23/11) : le sas vit SANS saison,
    # la salle d'attente se voit (et se trie) AVANT la première saison
    assert "kingdom:settings:launch" in ids
    assert "kingdom:console-nav:admissions" in ids, (
        "sas-v2: the waitlist door shows even without a season (Drasah must read it)"
    )
    for drawer in ("regie", "atelier"):
        assert f"kingdom:console-nav:{drawer}" in ids, f"the {drawer} drawer must be a click away"
    assert "kingdom:console-nav:beta" not in ids, (
        "drarwer-bêta retiré (Drasah 22/11) : l'état vit sur le badge du cockpit"
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
    assert "kingdom:settings:start-season" in ids, "setup: the CLASSIC departure distributes the sas"
    assert "kingdom:settings:start-beta" in ids, "depart-fourche-v1: the BETA departure distributes too"
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
    # the ADMITTED block: what the admin already let in, by NAME —
    # eject-sas-v1: the admitted are the SHELLS (the name rides them)
    admitted_shells = [
        SimpleNamespace(name="AEGIS", slug="aegis"),
        SimpleNamespace(name="Château noir", slug="chateau-noir"),
    ]
    admitted = _admissions_drawer(
        settings_strings("fr"), vstrings, [], admitted_shells
    )
    texts = "\n".join(_texts(admitted))
    assert "✅ Admis en saison" in texts
    assert "- AEGIS" in texts and "- Château noir" in texts
    # eject-sas-v1 : the sas window offers the ejection; a LAUNCHED
    # season closes it (read-only + the reason line)
    ejectable = _admissions_drawer(
        settings_strings("fr"), vstrings, [], admitted_shells, ejectable=True
    )
    assert "kingdom:valid:eject:aegis" in _ids(ejectable)
    assert "kingdom:valid:eject:chateau-noir" in _ids(ejectable)
    assert "kingdom:valid:eject:" not in "\n".join(
        i for i in _ids(admitted)
    )
    assert str(settings_strings("fr")["settings_admissions_eject_closed_hint"]) in texts
    # nothing admitted yet: the plain-words line, not a silent hole
    fresh = _admissions_drawer(settings_strings("fr"), vstrings, [], [])
    assert "Aucun royaume admis" in "\n".join(_texts(fresh))


def test_the_fixed_drawers_reuse_only_existing_registrations() -> None:
    """Régie / atelier ride the existing buttons + the régie switches."""
    from botforge.mods.kingdom.cogs.settings_panel import (
        _DRAWERS,
        _regie_drawer,
        settings_strings,
    )

    ids = _ids(_regie_drawer(settings_strings("fr")))
    # console-etats-regie-v1: the four ON/OFF switches (data
    # #369 — the labels come from the régie's label keys)
    # levier-bêta-v1 (Check 140) : le switch « 📝 Compte requis »
    # devient LE LEVIER « 🧭 Parcours » (Classique ●/Bêta ●) —
    # registration_required ne vit PLUS dans la pile de switches
    # tiroir-royaumes-v1 (Check 142) : les gestes et les listes de
    # royaumes partent dans le tiroir ROYAUMES — la régie est MINCE
    # (l'incident « le bouton muet » venait du cap Discord de 40)
    assert sorted(ids) == sorted([
        "kingdom:console-regie:registration_open",
        "kingdom:console-regie:realm_creation_open",
        "kingdom:console-regie:realm_join_open",
        "kingdom:console-regie:season_entry_open",
        "kingdom:console-regie:parcours:classic",
        "kingdom:console-regie:parcours:beta",
    ])
    # tiroir-bêta retiré (Drasah 22/11) : il ne reste QUE ces tiroirs
    assert sorted(_DRAWERS) == ["admissions", "atelier", "regie", "royaumes"]


def _buttons(view: object) -> dict[str, object]:
    out: dict[str, object] = {}
    for item in view.walk_children():  # type: ignore[attr-defined]
        if getattr(item, "custom_id", None) and hasattr(item, "label"):
            out[str(item.custom_id)] = item
    return out


def test_the_running_cycle_row_carries_the_rescue_tools() -> None:
    """tiroir-bêta retiré (Drasah 22/11) : le faux départ (classique OU
    bêta) et « Terminer la saison » vivent dans la zone Le cycle dès
    qu'une saison tourne — plus de tiroir 🧪, l'état du parcours se
    lit sur le badge du cockpit."""
    import asyncio
    import unittest.mock as mock
    from types import SimpleNamespace

    from botforge.mods.kingdom.cogs import settings_panel as sp

    season = SimpleNamespace(phase="started", imposed_kingdoms=False)

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

    stack = SimpleNamespace(kingdoms=_Kingdoms(), realms=_Realms())
    with mock.patch.object(sp, "wiring", lambda: stack):
        view = asyncio.run(sp.build_settings_panel("123"))
    ids = _ids(view)
    assert "kingdom:settings:false-start" in ids, "the rewind rides the cycle row"
    assert "kingdom:settings:end-season" in ids, "the season's end rides the cycle row"
    assert "kingdom:console-nav:beta" not in ids, "no beta drawer anymore"


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
    # console-etats-regie-v1: the started cycle is SOBER — the console
    # ops stay in the atelier, the RESCUE tools ride the cycle row
    assert "kingdom:console:relaunch" not in ids
    assert "kingdom:console-nav:admissions" in ids
    assert "kingdom:settings:launch" not in ids, "started: a fresh launch would wipe the season"
    assert "kingdom:settings:start-season" not in ids, "started: the season is already started"
    # tiroir-bêta retiré : le faux départ répond DANS la zone Le cycle
    assert "kingdom:settings:false-start" in ids, "the rewind rides the running cycle row"
    assert "kingdom:console-nav:beta" not in ids, "the beta drawer is retired"


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
        "settings_zone_cycle_hint",
        "settings_zone_regie_label",
        "settings_zone_regie_hint",
        "settings_zone_atelier_label",
        "settings_zone_atelier_hint",
        "settings_nav_admissions_button",
        "settings_nav_regie_button",
        "settings_nav_atelier_button",
        "settings_status_kingdoms_header",
        "settings_status_kingdoms_names",
        "settings_status_crew_line",
        "settings_admissions_title",
        "settings_admissions_hint",
        "settings_admissions_empty",
        "settings_admissions_admitted_title",
        "settings_admissions_admitted_empty",
        "settings_regie_title",
        "settings_regie_hint",
        "settings_atelier_title",
        "settings_atelier_hint",
        "settings_atelier_heal_note",
        "settings_end_season_button",
        "settings_end_season_confirm_title",
        "settings_end_season_confirm_hint",
        "settings_end_season_confirm_button",
        "settings_end_season_not_running",
        "settings_end_season_done",
        "settings_admissions_eject_closed_hint",
        "settings_phase_setup",
        "settings_phase_started",
    ]
    for locale in ("fr", "en"):
        strings = settings_strings(locale)
        for key in keys:
            assert strings.get(key), f"missing {key} in {locale}"
