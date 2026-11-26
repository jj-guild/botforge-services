"""Affaire 40 (Drasah 26/11) : la Chambre des comptes conforme à l'ancien.

comptes-cv2-conformité — les trois manques du comparatif :
- la FICHE : au clic d'une carte, titre « ## emoji nom » + Effet + Usage
  (les textes du catalogue central) collés sous le corps ;
- le DOS PAR DÉFAUT : la zone carte montre TOUJOURS une image (l'art
  de la carte choisie, sinon le Dos_de_carte) ;
- le bloc « CARTES EN MAIN » sous le corps (une ligne par carte, le
  compteur y vit) et le bouton carte au NOM SEUL.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest


def _lieux() -> Any:
    import botforge.mods.kingdom.cogs.lieux as lieux_module

    return lieux_module


def _strings(locale: str = "fr") -> Any:
    return _lieux().lieux_strings(locale)


def _texts(view: Any) -> str:
    return "\n".join(
        str(c.content) for c in view.walk_children() if hasattr(c, "content")
    )


def _ids(view: Any) -> list[str]:
    return [
        str(item.custom_id)
        for item in view.walk_children()
        if getattr(item, "custom_id", None)
    ]


def _buttons(view: Any) -> list[Any]:
    return [item for item in view.walk_children() if getattr(item, "label", None)]


def _wire_market(
    monkeypatch: pytest.MonkeyPatch, held: list[tuple[str, int]]
) -> None:
    import botforge.mods.kingdom.cogs.market as market_module

    async def fake_chamber_text(stack: Any, kingdom: Any, catalog: dict) -> str:
        return "## 🏛️ Chambre des comptes — AEGIS"

    async def fake_held(stack: Any, kingdom: Any, catalog: dict) -> list[tuple[str, int]]:
        return held

    monkeypatch.setattr(market_module, "chamber_text", fake_chamber_text)
    monkeypatch.setattr(market_module, "chamber_held_cards", fake_held)


def _kingdom() -> SimpleNamespace:
    return SimpleNamespace(id="k-1", name="AEGIS", tech_points_bank=7)


def _wire_art(
    monkeypatch: pytest.MonkeyPatch, *, card: bytes | None = b"ART", back: bytes | None = b"BACK"
) -> None:
    import botforge.mods.kingdom.cogs.marche_art as marche_art

    async def fake_card_bytes(item: str) -> bytes | None:
        return card

    async def fake_back() -> bytes | None:
        return back

    monkeypatch.setattr(marche_art, "card_bytes", fake_card_bytes)
    monkeypatch.setattr(marche_art, "card_back_bytes", fake_back)


@pytest.mark.asyncio
async def test_the_comptes_body_carries_the_cards_in_hand_block(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lieux = _lieux()
    strings = _strings()
    _wire_market(monkeypatch, [("explorateur", 2), ("corruption", 1)])
    monkeypatch.setattr(lieux, "wiring", lambda: SimpleNamespace(config=None))
    view, _files = await lieux._comptes_window(strings, _kingdom(), {})
    body = _texts(view)
    assert "## Cartes en main" in body, "the block lives UNDER the chamber body"
    assert "x2" in body and "x1" in body, "one line per held card with its counter"


@pytest.mark.asyncio
async def test_the_comptes_cards_block_is_empty_when_the_hand_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lieux = _lieux()
    _wire_market(monkeypatch, [])
    monkeypatch.setattr(lieux, "wiring", lambda: SimpleNamespace(config=None))
    view, _files = await lieux._comptes_window(_strings(), _kingdom(), {})
    body = _texts(view)
    assert "## Cartes en main" in body
    assert "Aucune carte en main pour le moment." in body


@pytest.mark.asyncio
async def test_the_card_button_wears_the_name_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lieux = _lieux()
    _wire_market(monkeypatch, [("explorateur", 2)])
    monkeypatch.setattr(lieux, "wiring", lambda: SimpleNamespace(config=None))
    view, _files = await lieux._comptes_window(_strings(), _kingdom(), {})
    labels = [str(b.label) for b in _buttons(view)]
    assert any("Explorateur" in label for label in labels)
    assert not any("(" in label and ")" in label for label in labels), (
        "the counter lives in the block, never glued to the button"
    )


@pytest.mark.asyncio
async def test_the_card_zone_always_shows_an_image_back_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lieux = _lieux()
    _wire_market(monkeypatch, [("explorateur", 2)])
    monkeypatch.setattr(lieux, "wiring", lambda: SimpleNamespace(config=None))
    # Rien de sélectionné : le DOS de carte est l'image par défaut.
    _wire_art(monkeypatch, card=b"ART", back=b"BACK")
    _view, files = await lieux._comptes_window(_strings(), _kingdom(), {})
    assert "carte.png" in [f.filename for f in files], "the back fills the zone"
    # Une carte sélectionnée : SON art remplace le dos.
    _view, files = await lieux._comptes_window(
        _strings(), _kingdom(), {}, selected="explorateur"
    )
    assert "carte.png" in [f.filename for f in files]


@pytest.mark.asyncio
async def test_the_selected_card_shows_its_art_and_stays_usable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lieux = _lieux()
    _wire_market(monkeypatch, [("explorateur", 2)])
    monkeypatch.setattr(lieux, "wiring", lambda: SimpleNamespace(config=None))
    _wire_art(monkeypatch, card=b"ART", back=None)
    view, _files = await lieux._comptes_window(
        _strings(), _kingdom(), {}, selected="explorateur"
    )
    ids = _ids(view)
    assert "kingdoms:lieux:comptes:use:explorateur" in ids


def test_the_card_fiche_carries_effect_and_usage() -> None:
    lieux = _lieux()
    fiche = lieux._comptes_card_fiche("explorateur", "fr")
    assert fiche.startswith("## ")
    assert "Effet :" in fiche, "the fiche's effect line (catalog market_effect)"
    assert "Usage :" in fiche, "the fiche's usage line (catalog market_usage)"
    assert lieux._comptes_card_fiche("explorateur", "en").count("Usage:") == 1


@pytest.mark.asyncio
async def test_the_fiche_rides_under_the_body_when_a_card_is_picked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lieux = _lieux()
    _wire_market(monkeypatch, [("explorateur", 2)])
    monkeypatch.setattr(lieux, "wiring", lambda: SimpleNamespace(config=None))
    _wire_art(monkeypatch, card=b"ART", back=None)
    fiche = lieux._comptes_card_fiche("explorateur", "fr")
    view, _files = await lieux._comptes_window(
        _strings(), _kingdom(), {}, selected="explorateur", extra_text=fiche
    )
    body = _texts(view)
    assert "Effet :" in body and "Usage :" in body
    assert body.index("Cartes en main") < body.index("Effet :"), (
        "the fiche sits UNDER the chamber body and its cards block"
    )


def test_the_catalog_carries_the_new_keys_both_locales() -> None:
    from botforge.mods.kingdom.cogs.strings import strings

    for locale in ("fr", "en"):
        catalog = strings(locale)
        assert catalog["market_ledger_cards_title"]
        assert catalog["market_ledger_cards_empty"]
        assert "{0}" in catalog["market_card_effect"]
        assert "{0}" in catalog["market_card_usage"]
        usage = dict(catalog["market_usage"])
        assert "explorateur" in usage and "corruption" in usage
        effect = dict(catalog["market_effect"])
        assert "explorateur" in effect
