"""Affaire 46 (Drasah 26/11) : panthéon-polish-v1 — la vitrine lisible.

Le retour visuel de Drasah sur la capture : plus jamais l'identifiant
technique de saison, plus jamais la phase en anglais, et le gros bloc
par défaut = le PODIUM de la dernière saison terminée (le vainqueur
porte sa mention). Sans archive, la vitrine retombe sur le score live
: elle n'est jamais vide.
"""

from __future__ import annotations

import re
from types import SimpleNamespace
from typing import Any

import pytest


def _pantheon() -> Any:
    import botforge.mods.kingdom.cogs.pantheon as pantheon_module

    return pantheon_module


def _strings(locale: str = "fr") -> dict[str, str]:
    from botforge.mods.kingdom.cogs.strings import strings

    return strings(locale)


def _texts(view: Any) -> str:
    return "\n".join(
        str(c.content) for c in view.walk_children() if hasattr(c, "content")
    )


def _stack(
    kingdoms: list[SimpleNamespace] | None = None,
    counts: dict[str, int] | None = None,
    season: Any = None,
    archives: list[dict[str, Any]] | None = None,
) -> SimpleNamespace:
    class _Kingdoms:
        async def kingdoms(self) -> list[SimpleNamespace]:
            return kingdoms or []

        async def lords(self) -> list[SimpleNamespace]:
            return []

        async def current_season(self) -> Any:
            return season

        async def season_archives(self) -> list[dict[str, Any]]:
            return archives or []

    class _Territories:
        async def territory_count_by_kingdom(self) -> dict[str, int]:
            return counts or {}

    return SimpleNamespace(kingdoms=_Kingdoms(), territories=_Territories())


def _archive(sid: str, note_kind: str = "counts") -> dict[str, Any]:
    return {
        "season_id": sid,
        "kingdoms": [{"_id": "k-1", "name": "AEGIS"}, {"_id": "gaia", "name": "Gaïa"}],
        "seasons": [{"winner_kingdom_id": "k-1"}],
        "showmatches": (
            [{"finished": True, "score_a": 2, "score_b": 1}] if note_kind == "showmatch" else []
        ),
        "territories": [
            {"owner_kingdom_id": "k-1"},
            {"owner_kingdom_id": "k-1"},
            {"owner_kingdom_id": "gaia"},
            {"owner_kingdom_id": "gaia"},
            {"owner_kingdom_id": "gaia"},
        ],
    }


def _wire_locale(monkeypatch: pytest.MonkeyPatch) -> None:
    import botforge.mods.kingdom.cogs.panel as panel_module

    async def _fake_locale(gid: str) -> str:
        return "fr"

    monkeypatch.setattr(panel_module, "_guild_locale", _fake_locale)


# ---------------------------------------------------------------------------
# The season line is READABLE (no raw id, no english phase)
# ---------------------------------------------------------------------------


def test_the_phase_reads_like_a_phrase_not_a_code() -> None:
    pantheon = _pantheon()
    strings = _strings()
    assert "les armes sont levées" in pantheon._phase_text(strings, "started")
    assert "les royaumes se forment" in pantheon._phase_text(strings, "setup")
    assert pantheon._phase_text(strings, "unknown_future") == "unknown_future", (
        "a future phase (season 2) falls back to its raw name, never a crash"
    )


def test_the_season_label_never_shows_a_raw_id() -> None:
    pantheon = _pantheon()
    strings = _strings()
    named = SimpleNamespace(id="s-2026", name="Saison des Rois", phase="started")
    assert pantheon._season_label(strings, named) == "Saison des Rois"
    unnamed = SimpleNamespace(id="s-20261126", phase="started")
    assert pantheon._season_label(strings, unnamed) == "Saison en cours"
    technical = SimpleNamespace(id="s-20261126-182152", name="s-20261126-182152")
    assert pantheon._season_label(strings, technical) == "Saison en cours", (
        "a season whose name IS its id (the engine's default) reads "
        "« Saison en cours », never s-20261126-182152"
    )


# ---------------------------------------------------------------------------
# The default block = the LAST finished season's podium
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_panel_defaults_to_the_last_seasons_podium() -> None:
    pantheon = _pantheon()
    stack = _stack(
        kingdoms=[SimpleNamespace(id="gaia", name="Gaïa", is_gaia=True)],
        archives=[_archive("s-2026-1"), _archive("s-2026-2")],
    )
    lines = await pantheon._last_podium_lines(_strings(), stack)
    assert lines is not None
    text = "\n".join(lines)
    assert "Dernier podium — s-2026-2 (terminée)" in text, (
        "the LATEST archive wins, not the first"
    )
    assert "🥇 **AEGIS** — 2 territoires — verdict aux comptes de territoires" in text, (
        "the winner carries his verdict note"
    )
    assert "Gaïa" not in text, "Gaïa (the world) never rides the podium"


@pytest.mark.asyncio
async def test_a_showmatch_verdict_note_rides_the_winner_line() -> None:
    pantheon = _pantheon()
    stack = _stack(archives=[_archive("s-2026-1", note_kind="showmatch")])
    lines = await pantheon._last_podium_lines(_strings(), stack)
    assert "ShowMatch (2-1)" in "\n".join(lines or [])


@pytest.mark.asyncio
async def test_without_archives_the_panel_falls_back_to_the_live_score() -> None:
    pantheon = _pantheon()
    stack = _stack()
    assert await pantheon._last_podium_lines(_strings(), stack) is None
    rows = [("AEGIS", 1, 1, False)]
    text = pantheon._score_text(_strings(), rows)
    assert "🥇 **AEGIS** — 1 territoire · 1 alliance" in text, (
        "singular counts read « 1 territoire · 1 alliance », never « 1 territoires »"
    )


@pytest.mark.asyncio
async def test_an_archive_of_only_gaia_is_not_a_podium() -> None:
    pantheon = _pantheon()
    archive = _archive("s-2026-1")
    archive["territories"] = [{"owner_kingdom_id": "gaia"}]
    stack = _stack(
        kingdoms=[SimpleNamespace(id="gaia", name="Gaïa", is_gaia=True)],
        archives=[archive],
    )
    assert await pantheon._last_podium_lines(_strings(), stack) is None


# ---------------------------------------------------------------------------
# The whole panel — readable season line + podium block together
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_panel_reads_like_the_mockup(monkeypatch: pytest.MonkeyPatch) -> None:
    pantheon = _pantheon()
    stack = _stack(
        kingdoms=[SimpleNamespace(id="gaia", name="Gaïa", is_gaia=True)],
        season=SimpleNamespace(id="s-20261126", name="", phase="started"),
        archives=[_archive("s-2026-1")],
    )
    monkeypatch.setattr(pantheon, "wiring", lambda: stack)
    _wire_locale(monkeypatch)
    view = await pantheon.build_pantheon_panel("555")
    body = _texts(view)
    assert "📅 **Saison en cours** — phase : ⚔️ les armes sont levées" in body
    assert "🌱 La vitrine des saisons" in body
    # affaire 47 : une saison COURT = le gros bloc est le classement LIVE
    # (le podium vit dans la fenêtre Palmarès, plus dans le panneau).
    assert "Dernier podium" not in body, "the podium block moved to the Palmarès window"
    assert "🌙" not in body, "a live season is never « dormant »"


@pytest.mark.asyncio
async def test_the_panel_without_season_shows_the_dormant_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pantheon = _pantheon()
    stack = _stack(archives=[_archive("s-2026-1")])
    monkeypatch.setattr(pantheon, "wiring", lambda: stack)
    _wire_locale(monkeypatch)
    view = await pantheon.build_pantheon_panel("555")
    body = _texts(view)
    assert "🌙 Les royaumes dorment, l'Histoire attend la prochaine saison." in body
    assert "Dernier podium" in body, "the podium stays even between seasons"


# ---------------------------------------------------------------------------
# The labels are data (fr + en), the plurals are words
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("locale", ["fr", "en"])
def test_the_polish_keys_live_in_both_locales(locale: str) -> None:
    strings = _strings(locale)
    for key in (
        "pantheon_pin_hint",
        "pantheon_pin_season",
        "pantheon_pin_season_unnamed",
        "pantheon_pin_line",
        "pantheon_pin_gaia_line",
        "pantheon_pin_no_season",
        "pantheon_pin_last_title",
        "pantheon_pin_last_line",
        "pantheon_territory",
        "pantheon_territories",
        "pantheon_alliance",
        "pantheon_alliances",
        "pantheon_phase_setup",
        "pantheon_phase_started",
        "pantheon_phase_age",
        "pantheon_phase_cycling",
        "pantheon_phase_ended",
    ):
        assert strings[key], f"{locale} misses {key}"


# ---------------------------------------------------------------------------
# Affaire 46b : a select built with an EMPTY marker must not crash discord.py
# (the live catch of Drasah's Chronique click — 26/11, ValueError since 44)
# ---------------------------------------------------------------------------


_HISTO_TEMPLATE = r"kingdom:pantheon:histo:(?P<sid>[A-Za-z0-9_:-]+)"
_KINGDOM_TEMPLATE = r"kingdom:pantheon:kingdom:(?P<kid>[A-Za-z0-9_:-]+)"


def test_the_season_select_builds_with_an_empty_marker() -> None:
    pantheon = _pantheon()

    select = pantheon.PantheonSeasonSelect([], "")
    assert select.item.custom_id == "kingdom:pantheon:histo:-"
    assert re.match(_HISTO_TEMPLATE, select.item.custom_id), (
        "the custom_id must match the DynamicItem template"
    )


def test_the_kingdom_select_builds_with_an_empty_marker() -> None:
    pantheon = _pantheon()

    select = pantheon.PantheonKingdomSelect([], "")
    assert select.item.custom_id == "kingdom:pantheon:kingdom:-"
    assert re.match(_KINGDOM_TEMPLATE, select.item.custom_id), (
        "the custom_id must match the DynamicItem template"
    )


def test_the_dash_marker_translates_back_to_empty_on_reload() -> None:
    """The '-' placeholder must never leak into a season/kingdom lookup."""
    import asyncio
    import re

    pantheon = _pantheon()
    for cls, key in (
        (pantheon.PantheonSeasonSelect, "sid"),
        (pantheon.PantheonKingdomSelect, "kid"),
    ):
        raw = "kingdom:pantheon:histo:-" if key == "sid" else "kingdom:pantheon:kingdom:-"
        pattern = _HISTO_TEMPLATE if key == "sid" else _KINGDOM_TEMPLATE
        match = re.match(pattern, raw)
        assert match is not None
        item = asyncio.run(cls.from_custom_id(None, None, match))
        assert getattr(item, "season_id" if key == "sid" else "kingdom_id", "-") == ""


async def test_the_chronique_window_opens_with_no_pick(monkeypatch: pytest.MonkeyPatch) -> None:
    """First click on Chronique = empty picked, must build, not raise."""
    _wire_locale(monkeypatch)

    class _Kingdoms:
        async def kingdoms(self) -> list[SimpleNamespace]:
            return [SimpleNamespace(_id="k-1", id="k-1", name="AEGIS")]

    import botforge.mods.kingdom.cogs.pantheon as pantheon_module

    monkeypatch.setattr(
        pantheon_module, "wiring", lambda: SimpleNamespace(kingdoms=_Kingdoms())
    )
    view = await pantheon_module._chronique_view(_strings(), "")
    ids = [
        getattr(child, "custom_id", "")
        for child in view.walk_children()
    ]
    assert "kingdom:pantheon:kingdom:-" in ids
    texts = _texts(view)
    assert texts.strip() != ""
