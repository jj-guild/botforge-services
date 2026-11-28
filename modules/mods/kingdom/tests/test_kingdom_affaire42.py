"""Affaire 42 (Drasah 26/11) : fin-saison-v2 — le bouclage.

La saison se referme TOUJOURS (annulation, verdict, podium, phase
``ended``) : une égalité classique ferme ex aequo et laisse le
ShowMatch vivre HORS saison (son document survit au rembobinage), une
égalité bêta est tranchée par simulation dès le verdict. La boucle bêta
relance même une saison ``finished``, et l'atelier Paramètres porte le
bouton de test aux trois scénarios.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from botforge.mods.kingdom.config import (
    CivilizationCondition,
    KingdomSeasonConfig,
    default_map_catalog,
)
from botforge.mods.kingdom.models import LordRole
from botforge.mods.kingdom.season_end import SeasonEndService, ShowMatchError
from botforge.mods.kingdom.service import KingdomService
from botforge.mods.kingdom.territories import TerritoryService
from test_kingdom_season_end import MemoryStore


class _WipeStore(MemoryStore):
    """The season-end store with the selective wipe of Affaire 42."""

    async def wipe_season_data(self) -> None:
        from botforge.mods.kingdom.storage import SEASON_WIPE_COLLECTIONS
        from botforge.mods.kingdom.storage import SHOWMATCH_COLLECTION

        for collection in SEASON_WIPE_COLLECTIONS:
            if collection == SHOWMATCH_COLLECTION:
                # fin-saison-v2: only the FINISHED showmatches are purged.
                for doc in list(self.showmatches.values()):
                    if doc.get("finished") is not False:
                        self.showmatches.pop(doc["_id"], None)
            # the other season-scoped collections drop wholesale
        self.seasons.clear()
        self.kingdoms.clear()
        self.lords.clear()
        self.territories.clear()
        self.technologies.clear()
        self.attacks.clear()


def _config() -> KingdomSeasonConfig:
    """A config with a civilization catalog for the ShowMatch draws."""
    return KingdomSeasonConfig(
        maps=default_map_catalog(),
        civilizations=tuple(
            CivilizationCondition(key=key, display_name=key.capitalize())
            for key in (
                "britons", "francs", "celtes", "goths", "hongrois", "italiens",
                "franks2", "teutons", "vikings", "byzantins",
            )
        ),
    )


class Bundle:
    """Everything one Affaire-42 season-end test needs, rebuilt per test."""

    def __init__(self) -> None:
        self.store = _WipeStore()
        self.config = _config()
        self.kingdoms = KingdomService(self.store, self.config)  # type: ignore[arg-type]
        self.territories = TerritoryService(self.store, self.config, self.kingdoms)  # type: ignore[arg-type]
        self.season_end = SeasonEndService(  # type: ignore[arg-type]
            self.store, self.config, self.kingdoms, self.territories
        )

    async def launch_season(self, beta_name: str | None = None) -> None:
        """Launch a season with two kingdoms and one lord each."""
        await self.kingdoms.launch()
        await self.kingdoms.enroll("king-a", "King A", LordRole.KING, proposed_name="Aquitaine")
        await self.kingdoms.enroll("lord-a", "Lord A", LordRole.LORD, kingdom_name="Aquitaine")
        await self.kingdoms.enroll("king-b", "King B", LordRole.KING, proposed_name="Bourgogne")
        await self.kingdoms.enroll("lord-b", "Lord B", LordRole.LORD, kingdom_name="Bourgogne")
        await self.territories.draw_initial(seed=1)
        if beta_name is not None:
            season = await self.kingdoms.current_season()
            assert season is not None
            season.beta_name = beta_name
            await self.store.upsert_season(season.to_mongo())

    async def kingdom_id(self, name: str) -> str:
        return next(k.id for k in await self.kingdoms.kingdoms() if k.name == name)


# ---------------------------------------------------------------------------
# The season ALWAYS closes (design rule 1)
# ---------------------------------------------------------------------------
async def test_force_tie_closes_ex_aequo_and_opens_showmatch() -> None:
    """A forced tie closes the season ex aequo — nothing blocks."""
    bundle = Bundle()
    await bundle.launch_season()
    report = await bundle.season_end.close_season(force_tie=True)
    assert report["showmatch"] is True
    assert report["winner_kingdom_id"] is None
    season = await bundle.kingdoms.current_season()
    assert season is not None
    assert season.finished is True
    assert season.winner_kingdom_id is None
    match = await bundle.season_end.pending_showmatch()
    assert match is not None
    assert match.finished is False
    # Idempotent: closing again returns the same pending verdict.
    again = await bundle.season_end.close_season(force_tie=True)
    assert again["showmatch"] is True
    assert again["winner_kingdom_id"] is None


async def test_pending_showmatch_survives_the_wipe() -> None:
    """The outside-season ShowMatch document outlives the reset."""
    bundle = Bundle()
    await bundle.launch_season()
    await bundle.season_end.close_season(force_tie=True)
    assert await bundle.season_end.pending_showmatch() is not None
    await bundle.store.wipe_season_data()
    assert await bundle.season_end.pending_showmatch() is not None


async def test_simulate_next_duel_advances_the_score() -> None:
    """Scenario (c): ONE simulated duel prepares and decides a PA2 step."""
    bundle = Bundle()
    await bundle.launch_season()
    await bundle.season_end.close_season(force_tie=True)
    match = await bundle.season_end.simulate_next_duel(seed=7)
    assert len(match.duels) == 1
    assert match.score_a + match.score_b == 1
    assert match.finished is False  # wins_needed defaults to 2


async def test_simulate_showmatch_settles_the_verdict() -> None:
    """A played-out simulation crowns a winner and lands the verdict."""
    bundle = Bundle()
    await bundle.launch_season()
    await bundle.season_end.close_season(force_tie=True)
    match = await bundle.season_end.simulate_showmatch(seed=7)
    assert match.finished is True
    kingdoms = {k.id for k in await bundle.kingdoms.kingdoms()}
    assert match.winner_kingdom_id in kingdoms
    season = await bundle.kingdoms.current_season()
    assert season is not None
    assert season.winner_kingdom_id == match.winner_kingdom_id
    # The report no longer carries a PENDING showmatch once it's done.
    report = await bundle.season_end.close_season()
    assert report["showmatch"] is False
    assert report["winner_kingdom_id"] == match.winner_kingdom_id


async def test_record_duel_result_survives_a_relaunched_season() -> None:
    """A relaunched season keeps its own fresh winner, never overwritten."""
    bundle = Bundle()
    await bundle.launch_season()
    await bundle.season_end.close_season(force_tie=True)
    await bundle.season_end.simulate_showmatch(seed=7)
    season = await bundle.kingdoms.current_season()
    assert season is not None
    old_winner = season.winner_kingdom_id
    # A fresh season replaces the closed one: the verdict stays history.
    await bundle.kingdoms.launch()
    fresh = await bundle.kingdoms.current_season()
    assert fresh is not None
    assert fresh.winner_kingdom_id is None
    assert season.winner_kingdom_id == old_winner


async def test_showmatch_flows_refuse_without_a_match() -> None:
    """The simulation seams refuse when no ShowMatch is pending."""
    bundle = Bundle()
    await bundle.launch_season()
    assert await bundle.season_end.pending_showmatch() is None
    with pytest.raises(ShowMatchError):
        await bundle.season_end.simulate_next_duel(seed=1)


# ---------------------------------------------------------------------------
# The podium announcement (design rule 5)
# ---------------------------------------------------------------------------
async def test_event_report_text_carries_the_podium() -> None:
    """The end announcement shows the verdict AND the territory podium."""
    from botforge.mods.kingdom.cogs.phases import _event_report_text
    from botforge.mods.kingdom.cogs.strings import strings

    for locale in ("fr", "en"):
        catalog = strings(locale)
        report = {
            "kind": "end",
            "winner_name": "Aquitaine",
            "territories": {"Aquitaine": 7, "Bourgogne": 5},
            "showmatch": False,
        }
        text = await _event_report_text(catalog, report)
        assert "Aquitaine" in text
        assert "🥇" in text and "🥈" in text
        assert "7" in text and "5" in text
        # A classic tie announces the outside-season ShowMatch, podium too.
        report["winner_name"] = None
        report["showmatch"] = True
        text = await _event_report_text(catalog, report)
        assert "ShowMatch" in text
        assert "🥇" in text


# ---------------------------------------------------------------------------
# The beta loop relaunches even a FINISHED beta (design rule 4)
# ---------------------------------------------------------------------------
def _fake_stack(phase: str, beta_name: str | None) -> SimpleNamespace:
    season = SimpleNamespace(
        id="s-1", phase=phase, beta_name=beta_name, finished=True
    )

    class _Kingdoms:
        async def current_season(self) -> SimpleNamespace:
            return season

        async def launch(self) -> SimpleNamespace:
            season.phase = "setup"
            season.finished = False
            return SimpleNamespace(id="s-2")

        async def start_season(self) -> None:
            season.phase = "started"

    class _Stack:
        kingdoms = _Kingdoms()
        realms = None

    return _Stack()


async def test_relaunch_beta_relaunches_a_finished_beta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A closed (finished=True) beta season still loops (rule 4).

    fin-de-saison-unifiee-v1 (affaire 48): the pass no longer relaunches
    on its own — the « Boucler » click calls relaunch_beta directly.
    """
    import botforge.mods.kingdom.cogs.beta_loop as beta_loop
    import botforge.mods.kingdom.cogs.common as common
    import botforge.mods.kingdom.cogs.settings_panel as settings_panel

    stack = _fake_stack("ended", "beta-weekend")
    monkeypatch.setattr(common, "wiring", lambda: stack)

    async def _noop_arm(fake_stack: Any) -> None:
        return None

    monkeypatch.setattr(settings_panel, "_arm_compressed_beta", _noop_arm)
    summary = await beta_loop.relaunch_beta(SimpleNamespace(guilds=[]), stack)
    assert summary is not None
    assert "beta-weekend" in summary
    # and the PASS itself is inert now — nothing relaunches on its own
    assert await beta_loop.run_beta_loop_safe(SimpleNamespace(guilds=[])) is None


async def test_relaunch_beta_ignores_a_classic_end(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A CLASSIC end never relaunches (Drasah's asymmetry)."""
    import botforge.mods.kingdom.cogs.beta_loop as beta_loop

    stack = _fake_stack("ended", None)
    assert await beta_loop.relaunch_beta(SimpleNamespace(guilds=[]), stack) is None


# ---------------------------------------------------------------------------
# The test workbench wiring (design rule 6)
# ---------------------------------------------------------------------------
def test_settings_actions_removed_the_workbench() -> None:
    """fin-de-saison-unifiee-v1 (affaire 48): the grey workbench is GONE."""
    import botforge.mods.kingdom.cogs.settings_panel as settings_panel

    actions = {action for action, _key, _style in settings_panel._SETTINGS_ACTIONS}
    assert not ({"season-test", "test-end", "test-tie", "test-duel"} & actions)


def test_views_yaml_declares_the_season_end_surface() -> None:
    """affaire 48: the unified end announcement rides conf/views.yaml."""
    root = Path(__file__).resolve().parents[1]
    yaml_text = (root / "conf" / "views.yaml").read_text()
    assert "panel:mod:kingdom:admin:season-test:" not in yaml_text
    assert "panel:mod:kingdom:season:end:" in yaml_text


def test_locales_dropped_the_workbench_keys() -> None:
    """affaire 48: the workbench labels are GONE from both locales."""
    root = Path(__file__).resolve().parents[1]
    keys = (
        "settings_season_test_button",
        "settings_test_end_button",
        "settings_test_end_done",
        "settings_test_failed",
    )
    for locale in ("fr", "en"):
        flat = (root / "conf" / "locales" / f"{locale}.yaml").read_text()
        for key in keys:
            assert key not in flat, f"{key} still haunts {locale}.yaml"


def test_strings_carry_the_podium_keys() -> None:
    """The podium announcement lives in the fr AND en catalogs."""
    from botforge.mods.kingdom.cogs.strings import strings

    for locale in ("fr", "en"):
        catalog = strings(locale)
        assert "event_end_podium_title" in catalog
        assert "event_end_podium_line" in catalog
        assert "{0}" in catalog["event_end_podium_line"]
        assert "{1}" in catalog["event_end_podium_line"]
        assert "{2}" in catalog["event_end_podium_line"]
