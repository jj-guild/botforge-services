"""delta-lab-v1 (Drasah 28/11) — the 🌱 beta lab's own tests.

The three v1 features, tested at the logic level (the surfaces are
discord-shaped, the DECISIONS are data):

1. the catalog carries EVERY delta string in both locales (a missing
   key once emptied a whole salon — the console-crash-v1 lesson), and
   the formatted previews render (no placeholder left behind);
2. the gallery covers the message families and every entry renders
   non-empty blocks (see without playing — Drasah's ruling);
3. the crew photograph: capture filters engaged/standby/archived and
   the roster matches its shells back (the 02:26 incident's fix — the
   photo is the truth that survives the ejection);
4. the three delta surfaces are DECLARED (views.yaml, the #381 rule).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import botforge.mods.kingdom.cogs.kingdom.beta_loop as beta_loop_module
import botforge.mods.kingdom.cogs.kingdom.delta as delta_module


def _catalog() -> Any:
    from botforge.mods.kingdom.cogs.kingdom.common import mod_catalog

    return mod_catalog()


def _delta_section(locale: str) -> dict[str, str]:
    return dict(_catalog().section("kingdom.delta", locale))


_REQUIRED_DELTA_KEYS = (
    "delta_title",
    "delta_hint",
    "delta_classic_refused",
    "delta_no_service",
    "delta_zone_end_label",
    "delta_zone_end_hint",
    "delta_zone_gallery_label",
    "delta_zone_gallery_hint",
    "delta_end_button",
    "end_ack",
    "end_not_running",
    "end_already_pending",
    "end_state_failed",
    "end_no_channel",
    "end_done",
    "ceremony_title",
    "ceremony_beta_line",
    "ceremony_after_hint",
    "ceremony_boucler_button",
    "ceremony_boucler_ack",
    "ceremony_boucler_done",
    "ceremony_archiver_button",
    "ceremony_archiver_ack",
    "ceremony_archiver_done",
    "ceremony_gone",
    "delta_reseat_button",
    "reseat_ack",
    "reseat_not_running",
    "reseat_done",
    "gallery_placeholder",
    "gallery_missing",
    "gallery_preview_header",
    "gallery_preview_note",
)


@pytest.mark.parametrize("locale", ["fr", "en"])
def test_the_delta_catalog_is_complete(locale: str) -> None:
    """Every delta key exists in both locales — no silent empty line."""
    section = _delta_section(locale)
    missing = [key for key in _REQUIRED_DELTA_KEYS if not str(section.get(key) or "").strip()]
    assert not missing, f"kingdom.delta[{locale}] misses: {missing}"


@pytest.mark.parametrize("locale", ["fr", "en"])
def test_the_delta_nav_button_is_declared(locale: str) -> None:
    """The settings nav knows the Delta drawer (KingdomSettingsNavButton reads it)."""
    section = dict(_catalog().section("kingdom.settings", locale))
    assert str(section.get("settings_nav_delta_button") or "").strip(), (
        "settings_nav_delta_button is missing — the nav button would degrade"
    )


@pytest.mark.parametrize("locale", ["fr", "en"])
def test_the_gallery_covers_the_message_families(locale: str) -> None:
    """Every previewable family is present and renders non-empty blocks."""
    entries = delta_module.gallery_entries(locale)
    keys = {entry["key"] for entry in entries}
    assert {
        "welcome",
        "conquest",
        "forfait",
        "cycle",
        "age",
        "end",
        "end-showmatch",
        "sacree",
        "expedition",
        "ffa",
        "bouclage",
    } <= keys
    for entry in entries:
        assert entry["blocks"], f"the {entry['key']} preview is EMPTY"
        assert str(entry["label"]).strip(), f"the {entry['key']} preview has no label"


@pytest.mark.parametrize("locale", ["fr", "en"])
def test_the_welcome_preview_formats(locale: str) -> None:
    """The welcome mock renders with the sample data (no leftover placeholder)."""
    section = _delta_section(locale)
    text = str(section["gallery_welcome_body"]).format(
        season=section["gallery_sample_season"],
        kingdoms=section["gallery_sample_kingdoms"],
        count=4,
        end_date=section["gallery_sample_end_date"],
    )
    assert "{" not in text and "}" not in text, "an unformatted placeholder leaked"
    assert "royaume" in text or "kingdom" in text.lower()


# ---------------------------------------------------------------------------
# The crew photograph — the 02:26 incident's fix
# ---------------------------------------------------------------------------


class _RealmsStub:
    """A realms service double: a fixed shell list."""

    def __init__(self, shells: list[Any]) -> None:
        self._shells = shells

    async def realms(self) -> list[Any]:
        return list(self._shells)


def _shell(
    sid: str,
    *,
    engaged: bool = True,
    archived: bool = False,
    name: str = "Francs",
) -> Any:
    return SimpleNamespace(
        id=sid,
        name=name,
        king_id="7",
        king_name="Drasah",
        member_ids=["7", "8"],
        engagement={"season_id": "s-1", "kingdom_id": "k-1"} if engaged else None,
        archived_at=123 if archived else 0,
    )


@pytest.mark.asyncio
async def test_the_roster_capture_photographs_only_the_engaged() -> None:
    """Engaged shells are photographed; standby and archived never are."""
    service = _RealmsStub(
        [
            _shell("a"),
            _shell("b", engaged=False),
            _shell("c", archived=True),
            _shell("d", name="Omeyyades"),
        ]
    )
    roster = await beta_loop_module.capture_engaged_roster(service)
    assert [entry["id"] for entry in roster] == ["a", "d"]
    photo = roster[0]
    assert photo["name"] == "Francs"
    assert photo["king_id"] == "7"
    assert photo["member_ids"] == ["7", "8"]


@pytest.mark.asyncio
async def test_the_roster_capture_survives_a_dead_service() -> None:
    """A missing realms service photographs nobody, never raises."""
    assert await beta_loop_module.capture_engaged_roster(None) == []


def test_the_roster_matches_its_shells_back() -> None:
    """The photo finds its shells after the ejection, misses skipped."""
    roster = [
        {"id": "b", "name": "Omeyyades"},
        {"id": "a", "name": "Francs"},
        {"id": "zz", "name": "Gone"},
    ]
    shells = [_shell("a"), _shell("b", engaged=False)]
    matched = beta_loop_module.match_roster_shells(roster, shells)
    assert [str(getattr(s, "id", "")) for s in matched] == ["b", "a"]


@pytest.mark.asyncio
async def test_the_standby_pool_lists_the_reseatable_shells() -> None:
    """The réembarquement pool: not engaged, never archived."""
    service = _RealmsStub(
        [
            _shell("a"),
            _shell("b", engaged=False),
            _shell("c", engaged=False, archived=True),
        ]
    )
    shells = await beta_loop_module.standby_shells(service)
    assert [str(getattr(s, "id", "")) for s in shells] == ["b"]


# ---------------------------------------------------------------------------
# The surfaces are DECLARED (the #381 ruling)
# ---------------------------------------------------------------------------


def test_the_delta_surfaces_are_declared() -> None:
    """The three delta view ids live in conf/views.yaml."""
    from botforge.discord.ui.view_footer import require_declared_view_id

    for view_id in (
        delta_module.DELTA_WINDOW_KEY,
        delta_module.DELTA_END_VIEW_KEY,
        delta_module.DELTA_GALLERY_VIEW_KEY,
    ):
        require_declared_view_id(view_id)
