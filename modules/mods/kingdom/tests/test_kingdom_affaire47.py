"""Affaire 47 (Drasah 26/11) : la vitrine suit l'état du monde.

Une saison COURT, le gros bloc du Panthéon = le CLASSEMENT LIVE
(royaumes + territoires, les alliances restent PRIVÉES). Les royaumes
DORMENT, le bloc = le podium de la dernière saison terminée.
"""


from __future__ import annotations

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


def _archive(sid: str) -> dict[str, Any]:
    return {
        "season_id": sid,
        "kingdoms": [{"_id": "k-1", "name": "AEGIS"}, {"_id": "gaia", "name": "Gaïa"}],
        "seasons": [{"winner_kingdom_id": "k-1"}],
        "showmatches": [],
        "territories": [
            {"owner_kingdom_id": "k-1"},
            {"owner_kingdom_id": "k-1"},
            {"owner_kingdom_id": "gaia"},
        ],
    }


def _wire_locale(monkeypatch: pytest.MonkeyPatch) -> None:
    import botforge.mods.kingdom.cogs.panel as panel_module

    async def _fake_locale(gid: str) -> str:
        return "fr"

    monkeypatch.setattr(panel_module, "_guild_locale", _fake_locale)


# ---------------------------------------------------------------------------
# A running season: the LIVE standings, WITHOUT the alliances
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_running_season_shows_the_live_standings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pantheon = _pantheon()
    stack = _stack(
        kingdoms=[
            SimpleNamespace(id="k-1", name="AEGIS", is_gaia=False),
            SimpleNamespace(id="k-2", name="HeN", is_gaia=False),
        ],
        counts={"k-1": 3, "k-2": 1},
        season=SimpleNamespace(id="s-1", name="Saison des rois", phase="started"),
        archives=[_archive("s-2026-1")],
    )
    monkeypatch.setattr(pantheon, "wiring", lambda: stack)
    _wire_locale(monkeypatch)
    body = _texts(await pantheon.build_pantheon_panel("555"))
    assert "🥇 **AEGIS** — 3 territoires" in body, "the live ranking leads the panel"
    assert "🥈 **HeN** — 1 territoire" in body
    assert "alliance" not in body, "the alliances stay PRIVATE while a season runs"
    assert "Dernier podium" not in body, "the podium waits between seasons, not during"


@pytest.mark.asyncio
async def test_gaia_still_reads_like_the_wild_world_in_season(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pantheon = _pantheon()
    stack = _stack(
        kingdoms=[SimpleNamespace(id="gaia", name="Gaïa", is_gaia=True)],
        counts={"gaia": 2},
        season=SimpleNamespace(id="s-1", name="", phase="age"),
    )
    monkeypatch.setattr(pantheon, "wiring", lambda: stack)
    _wire_locale(monkeypatch)
    body = _texts(await pantheon.build_pantheon_panel("555"))
    assert "▫️ Gaïa — 2 territoires, le monde sauvage" in body


@pytest.mark.asyncio
async def test_a_dormant_world_shows_the_last_podium(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pantheon = _pantheon()
    stack = _stack(
        kingdoms=[SimpleNamespace(id="k-1", name="AEGIS", is_gaia=False)],
        counts={"k-1": 2},
        season=None,
        archives=[_archive("s-2026-1")],
    )
    monkeypatch.setattr(pantheon, "wiring", lambda: stack)
    _wire_locale(monkeypatch)
    body = _texts(await pantheon.build_pantheon_panel("555"))
    assert "Dernier podium — s-2026-1 (terminée)" in body
    assert "verdict aux comptes de territoires" in body
    assert "🌙 Les royaumes dorment" in body


# ---------------------------------------------------------------------------
# The live line is data (fr + en), the alliances stay out
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("locale", ["fr", "en"])
def test_the_live_line_lives_in_both_locales(locale: str) -> None:
    assert "pantheon_pin_live_line" in _strings(locale)


def test_the_live_line_never_shows_an_alliance_count() -> None:
    pantheon = _pantheon()
    rows = [("AEGIS", 2, 5, False)]
    text = pantheon._score_text(_strings(), rows, with_alliances=False)
    assert "5" not in text, "an alliance count never leaks into the live line"
    assert "**AEGIS** — 2 territoires" in text
