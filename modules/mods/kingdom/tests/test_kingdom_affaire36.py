"""Affaire 36 / T-D (Drasah 26/11) : paroisse rangée 2 + objectifs
enrichis + comptes-cv2 + le moteur du Lieu Sacrée.

Le seul NOUVEAU moteur est la cathédrale (cathedrale.py) : le PREMIER
écrivain de ``cathedral_until`` — les immunités (sacred,
is_tech_protected_at, les gardes d'attacks/economy) étaient portées
depuis toujours sans appelant. Le reste consomme les seams existants
(diplomacy.arranged_marriage, chamber_held_cards, _use_wizard).
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest

NOW = datetime(2026, 11, 26, 12, 0, tzinfo=UTC)


class _Store:
    def __init__(self) -> None:
        self.kingdoms: dict[str, dict] = {}
        self.territories: dict[str, dict] = {}

    async def upsert_kingdom(self, document: dict) -> None:
        self.kingdoms[document["_id"]] = document

    async def upsert_territory(self, document: dict) -> None:
        self.territories[document["_id"]] = document


def _walk_kinds(view: Any) -> list[str]:
    kinds: list[str] = []
    pending = list(view.children)
    while pending:
        item = pending.pop(0)
        kinds.append(type(item).__name__)
        pending.extend(getattr(item, "children", []) or [])
    return kinds


def _config() -> Any:
    from botforge.mods.kingdom.config import default_season_config

    return default_season_config()


def _async(value: Any) -> Any:
    class _Awaitable:
        async def __call__(self, *_args: Any, **_kwargs: Any) -> Any:
            return value

    return _Awaitable()


def _async_list(items: list[Any]) -> Any:
    class _List:
        async def __call__(self, *_args: Any, **_kwargs: Any) -> list[Any]:
            return items

    return _List()


def _territory(
    tid: str, map_key: str, owner: str, *, sacred: bool = False,
    until: datetime | None = None, running: bool = False,
) -> Any:
    return SimpleNamespace(
        id=tid, map_key=map_key, owner_kingdom_id=owner, sacred=sacred,
        cathedral_until=until, is_chantier_at=lambda now: running,
        to_mongo=lambda: {"_id": tid, "map_key": map_key},
    )


def _engine(
    *,
    tier: int = 3,
    bank: int = 5,
    king_role: str = "king",
    territories: list[Any] | None = None,
) -> tuple[Any, _Store]:
    from botforge.mods.kingdom.cathedrale import CathedralService
    from botforge.mods.kingdom.models import LordRole

    kingdom = SimpleNamespace(
        id="k1", name="Aquitaine", parish_tier=tier, tech_points_bank=bank
    )
    # the bank must persist the PAID price through to_mongo (mutation-reflecting)
    kingdom.to_mongo = lambda: {  # type: ignore[method-assign, misc]
        "_id": "k1", "tech_points_bank": int(kingdom.tech_points_bank)
    }
    king = SimpleNamespace(
        id="u1",
        role=LordRole.KING if king_role == "king" else LordRole.LORD,
        kingdom_id="k1",
    )
    if territories is None:
        territories = [
            _territory("t1", "Prairie", "k1"),
            _territory("t2", "Steppe", "k2"),
        ]
    kingdoms = SimpleNamespace(
        kingdoms=_async_list([kingdom]),
        lords=_async_list([king]),
        current_season=_async(SimpleNamespace(finished=False)),
    )
    store = _Store()
    service = CathedralService(
        store, _config(), kingdoms, SimpleNamespace(territories=_async_list(territories))
    )
    return service, store


def _strings() -> dict[str, str]:
    from botforge.mods.kingdom.cogs.lieux import lieux_strings

    return lieux_strings("fr")


# ---------------------------------------------------------------------------
# The engine : consecrate, refuse, verdict
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_cathedral_engine_consecrates_and_pays() -> None:
    """Max tier, funded king: 72h chantier set, the price paid at once."""
    service, store = _engine(bank=5)

    territory = await service.consecrate("u1", "Prairie", now=NOW)

    until = getattr(territory, "cathedral_until", None)
    assert until == NOW + timedelta(hours=72), "the chantier's app: 72h of config"
    assert store.kingdoms["k1"]["tech_points_bank"] == 2, "3 ⚙️ paid from the bank"
    assert store.territories["t1"]["map_key"] == "Prairie", "the chantier persists"


@pytest.mark.asyncio
async def test_the_cathedral_engine_refuses_every_wrong_path() -> None:
    """King-only, palier, foreign land, chantier déjà lancé, trésor vide."""
    from botforge.mods.kingdom.cathedrale import (
        CathedralActiveError,
        CathedralKingOnlyError,
        CathedralNotFoundError,
        CathedralTierError,
    )

    service, _store = _engine(king_role="lord")
    with pytest.raises(CathedralKingOnlyError):
        await service.consecrate("u1", "Prairie", now=NOW)

    service, _store = _engine(tier=2)
    with pytest.raises(CathedralTierError):
        await service.consecrate("u1", "Prairie", now=NOW)

    service, _store = _engine()
    with pytest.raises(CathedralNotFoundError):
        await service.consecrate("u1", "Steppe", now=NOW)

    from botforge.mods.kingdom.cathedrale import CathedralInsufficientTechError

    service, _store = _engine(bank=1)
    with pytest.raises(CathedralInsufficientTechError):
        await service.consecrate("u1", "Prairie", now=NOW)

    chanting = [
        _territory("t1", "Prairie", "k1", until=NOW + timedelta(hours=1), running=True),
        _territory("t2", "Steppe", "k2"),
    ]
    service, _store = _engine(territories=chanting)
    with pytest.raises(CathedralActiveError):
        await service.consecrate("u1", "Prairie", now=NOW)


@pytest.mark.asyncio
async def test_the_verdict_tick_flips_expired_chantiers_once() -> None:
    """An expired chantier becomes SACRED; the replay changes nothing."""
    from botforge.mods.kingdom.cathedrale import CathedralService

    expired = _territory(
        "t1", "Prairie", "k1", until=NOW - timedelta(hours=1), running=False
    )
    running = _territory(
        "t2", "Steppe", "k2", until=NOW + timedelta(hours=1), running=True
    )
    kingdoms = SimpleNamespace(
        kingdoms=_async_list([]),
        lords=_async_list([]),
        current_season=_async(SimpleNamespace(finished=False)),
    )
    store = _Store()
    service = CathedralService(
        store, _config(), kingdoms, SimpleNamespace(territories=_async_list([expired, running]))
    )

    verdicts = await service.resolve_due(now=NOW)

    assert [item.id for item in verdicts] == ["t1"], "only the expired chantier"
    assert expired.sacred is True and expired.cathedral_until is None
    assert running.sacred is False, "a running chantier is untouched"
    assert await service.resolve_due(now=NOW) == [], "the tick is idempotent"


def test_the_stack_wires_the_cathedral_seam() -> None:
    """The grpc stack builds the engine, the contract declares the seam."""
    from pathlib import Path

    from botforge.mods.kingdom.grpc import contract as contract_pkg
    from botforge.mods.kingdom.grpc.contract import KingdomStack

    impl_source = (
        Path(contract_pkg.__file__).resolve().parent / "service.py"
    ).read_text(encoding="utf-8")
    assert "Cathedrals" not in impl_source or True  # guard: the file resolved
    assert "CathedralService" in impl_source, "the stack builds the cathedral engine"
    assert "self._cathedrals = CathedralService(" in impl_source, "wired alongside"
    assert hasattr(KingdomStack, "cathedrals"), "the contract declares the seam"
    assert hasattr(KingdomStack, "cathedrals")


# ---------------------------------------------------------------------------
# The paroisse sheet : rangée 2 + the enriched council
# ---------------------------------------------------------------------------


def _paroisse_kingdom(tier: int, stock: int) -> Any:
    return SimpleNamespace(
        id="k1", name="Aquitaine", parish_tier=tier,
        arranged_marriage_stock=stock, marriage_points=2,
        civilizations=[], tech_points_bank=4,
    )


def _wires(view: Any) -> list[str]:
    wires: list[str] = []
    for child in view.children:
        for row in getattr(child, "children", []) or []:
            for button in getattr(row, "children", []) or []:
                custom_id = str(getattr(button, "custom_id", "") or "")
                if custom_id:
                    wires.append(custom_id)
    return wires


@pytest.mark.asyncio
async def test_the_paroisse_row_two_greens_only_when_usable(monkeypatch: Any) -> None:
    """💐 vert dès l'Église + un jeton, ⛪ vert au palier max — jamais cachés."""
    from botforge.mods.kingdom.cogs import lieux

    stack = SimpleNamespace(config=_config())
    monkeypatch.setattr(lieux, "wiring", lambda: stack)

    view, _files = await lieux._paroisse_window(_strings(), _paroisse_kingdom(1, 0), {})
    wires = _wires(view)
    assert "kingdoms:lieux:paroisse:arrange" in wires, "never hidden — grayed"
    assert "kingdoms:lieux:paroisse:consecrate" in wires, "never hidden — grayed"
    assert "kingdoms:lieux:paroisse:info" in wires, "row one carries En savoir plus"
    assert "kingdoms:lieux:sortir" in wires, "row one keeps Sortir last"

    def _buttons(view: Any) -> dict[str, Any]:
        found: dict[str, Any] = {}
        for child in view.children:
            for row in getattr(child, "children", []) or []:
                for button in getattr(row, "children", []) or []:
                    cid = str(getattr(button, "custom_id", "") or "")
                    if cid:
                        found[cid] = button
        return found

    buttons = _buttons(view)
    assert buttons["kingdoms:lieux:paroisse:arrange"].disabled is True
    assert "Mariage arrangé (0)" in buttons["kingdoms:lieux:paroisse:arrange"].label
    assert buttons["kingdoms:lieux:paroisse:consecrate"].disabled is True

    view, _files = await lieux._paroisse_window(_strings(), _paroisse_kingdom(3, 1), {})
    buttons = _buttons(view)
    assert buttons["kingdoms:lieux:paroisse:arrange"].disabled is False
    assert "Mariage arrangé (1)" in buttons["kingdoms:lieux:paroisse:arrange"].label
    assert buttons["kingdoms:lieux:paroisse:consecrate"].disabled is False


def test_the_comptes_card_art_rides_inside_the_container() -> None:
    """comptes-cv2-v1 : la galerie de la carte vit DANS le container sous
    le corps — l'illustration de tête reste seule (Drasah 05/11)."""
    from botforge.mods.kingdom.cogs import lieux

    assert lieux._COMPTES_USABLE == {
        "explorateur", "corruption", "jeu_d_armes", "garde_royale", "patrouille"
    }
    window = lieux._lieu_window(
        _strings(), lieux.COMPTES_SURFACE, lieux.GOLD, "titre", "corps",
        "attachment://chambre_des_comptes.png", [[
            lieux._sortir_item(_strings())
        ]], card_media="attachment://carte.png",
    )
    kinds = _walk_kinds(window)
    assert kinds.count("Container") == 1, "one container panel"
    assert "MediaGallery" in kinds, "the revealed card gallery renders"
    source = inspect.getsource(lieux._comptes_window)
    assert "comptes:use:" in source, "the 🚀 Utiliser button rides row 1"
    assert "chamber_held_cards" in source, "the cards come from the market seam"


@pytest.mark.asyncio
async def test_a_held_goal_reads_as_defend_or_marry() -> None:
    """objectif-possede-v1 : une map possédée = DÉFENSE, une civ en main =
    MARIAGE ; sinon la map porte son propriétaire vivant."""
    from botforge.mods.kingdom.cogs import lieux

    territories = [
        SimpleNamespace(map_key="Prairie", owner_kingdom_id="k1"),
        SimpleNamespace(map_key="Steppe", owner_kingdom_id="k2"),
    ]
    kingdoms = [
        SimpleNamespace(id="k1", name="Aquitaine"),
        SimpleNamespace(id="k2", name="Bourgogne"),
    ]
    stack = SimpleNamespace(
        territories=SimpleNamespace(territories=_async_list(territories)),
        kingdoms=SimpleNamespace(
            kingdoms=_async_list(kingdoms),
            lords=_async_list([
                SimpleNamespace(
                    id="20", left=False, display_name="Bernard",
                    married_civilization="rome",
                )
            ]),
        ),
    )
    goals_kingdom = SimpleNamespace(
        id="k1", civilizations=["rome"],
        council_objectives={
            "target_territory": "Prairie", "target_territory_label": "Prairie",
            "target_alliance": "rome", "target_alliance_label": "Rome",
        },
    )
    text = await lieux._objectifs_lines(_strings(), stack, goals_kingdom)
    assert "Territoire à défendre" in text, "an OWNED map reads DEFEND"
    assert "Alliance à consolider" in text, "a HELD civ reads MARRIAGE"
    assert "appartient" not in text, "no owner suffix on an owned map"

    goals_sought = SimpleNamespace(
        id="k1", civilizations=[],
        council_objectives={
            "target_territory": "Steppe", "target_territory_label": "Steppe",
            "target_alliance": "rome", "target_alliance_label": "Rome",
        },
    )
    text = await lieux._objectifs_lines(_strings(), stack, goals_sought)
    assert "appartient à Bourgogne" in text, "the sought map carries its live owner"
    assert "mariée à Bernard" in text, "the wedded civ carries its lord"

    dead_stack = SimpleNamespace(territories=None, kingdoms=None)
    text = await lieux._objectifs_lines(_strings(), dead_stack, goals_sought)
    assert "Steppe" in text and "Rome" in text, "a dead stack keeps the plain lines"


def test_the_new_items_are_registered_and_the_loop_ticks() -> None:
    """Restart-proof buttons + the cathedrals pass hooks the 5-min loop."""
    from botforge.mods.kingdom.cogs import lieux, phases
    from botforge.mods.kingdom.cogs.common import strings_by_locale

    names = {item.__name__ for item in lieux.lieux_dynamic_items()}
    for expected in (
        "LieuxParoisseInfoButton",
        "LieuxParoisseStateButton",
        "LieuxParoisseArrangeButton",
        "LieuxParoisseConsecrateButton",
        "LieuxConsecrateSelect",
        "LieuxComptesCardButton",
        "LieuxComptesUseButton",
    ):
        assert expected in names, f"{expected} must be restart-proof"

    assert hasattr(phases, "run_cathedrals_due_safe")
    assert "run_cathedrals_due_safe(bot)" in inspect.getsource(
        phases.start_attack_refresher
    ), "the verdict rides the 5-minute pass"

    for locale in ("fr", "en"):
        strings = lieux.lieux_strings(locale)
        for key in (
            "paroisse_info_button", "paroisse_state_button",
            "paroisse_info_intro", "paroisse_info_sacree",
            "paroisse_arrange_button", "paroisse_arrange_done",
            "paroisse_consecrate_button", "paroisse_consecrate_done",
            "comptes_use_button",
            "conseil_objectif_map_defend", "conseil_objectif_alliance_marry",
        ):
            assert key in strings, f"{locale} misses {key}"
        assert "sacree_verdict_note" in strings_by_locale(locale)
