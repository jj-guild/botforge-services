"""Affaire 41 (Drasah 26/11) : comptes-feuille-v2 — la Chambre épurée.

Le feedback de Drasah sur la capture HeN :
- le corps se réduit au TITRE + aux POINTS TECHNOLOGIQUES du royaume
  (« Banque du royaume » disparaît, les lignes de jetons dégagent) ;
- les cartes en main restent (c'est LE but de la feuille) mais avec
  UN SEUL emoji par ligne (le bug du double 👑👑) ;
- les boutons cartes sont BLEUS, la carte sélectionnée VERTE — la
  rangée des cartes se détache des historiques verts.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest


def _lieux() -> Any:
    import botforge.mods.kingdom.cogs.lieux as lieux_module

    return lieux_module


def _strings() -> Any:
    return _lieux().lieux_strings("fr")


def _texts(view: Any) -> str:
    return "\n".join(
        str(c.content) for c in view.walk_children() if hasattr(c, "content")
    )


def _wire(monkeypatch: pytest.MonkeyPatch, held: list[tuple[str, int]]) -> None:
    """Wiring + held cards faked — chamber_text stays the REAL seam."""
    import botforge.mods.kingdom.cogs.market as market_module

    class _Attacks:
        async def technology_state(self, kid: str) -> Any:
            return SimpleNamespace(purchases={})

    monkeypatch.setattr(
        _lieux(), "wiring", lambda: SimpleNamespace(config=None, attacks=_Attacks())
    )

    async def fake_held(stack: Any, kingdom: Any, catalog: dict) -> list[tuple[str, int]]:
        return held

    monkeypatch.setattr(market_module, "chamber_held_cards", fake_held)


def _kingdom() -> SimpleNamespace:
    return SimpleNamespace(id="k-1", name="AEGIS", tech_points_bank=1)


def _wire_art(monkeypatch: pytest.MonkeyPatch) -> None:
    import botforge.mods.kingdom.cogs.marche_art as marche_art

    async def fake_card_bytes(item: str) -> bytes | None:
        return b"ART"

    async def fake_back() -> bytes | None:
        return b"BACK"

    monkeypatch.setattr(marche_art, "card_bytes", fake_card_bytes)
    monkeypatch.setattr(marche_art, "card_back_bytes", fake_back)


@pytest.mark.asyncio
async def test_the_comptes_body_is_title_and_tech_points_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lieux = _lieux()
    _wire(monkeypatch, [])
    view, _files = await lieux._comptes_window(_strings(), _kingdom(), {})
    body = _texts(view)
    assert "Points technologiques du royaume" in body
    assert "**1**" in body, "the wallet shows the tech points count"
    assert "Banque du royaume" not in body
    assert "Jetons" not in body, "the stock lines are GONE (feedback HeN)"
    assert "Patrouille :" not in body
    assert "## Cartes en main" in body, "the cards block stays"
    assert "Aucune carte en main" in body


@pytest.mark.asyncio
async def test_the_market_keeps_its_full_chamber_sheet() -> None:
    """The Marché's Comptes surface keeps the FULL sheet (not decided)."""
    from botforge.mods.kingdom.cogs.market import chamber_text
    from botforge.mods.kingdom.cogs.strings import strings

    class _Attacks:
        async def technology_state(self, kid: str) -> Any:
            return SimpleNamespace(purchases={"explorateur_stock": 2})

    stack = SimpleNamespace(attacks=_Attacks())
    kingdom = SimpleNamespace(id="k-1", name="AEGIS", tech_points_bank=5)
    text = await chamber_text(stack, kingdom, strings("fr"))
    assert "Jetons" in text, "the market's full sheet keeps its stock lines"
    compact = await chamber_text(stack, kingdom, strings("fr"), compact=True)
    assert "Jetons" not in compact
    assert compact.count("\n") == 1, "compact = title + wallet, no more"


@pytest.mark.asyncio
async def test_the_cards_lines_carry_one_emoji_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lieux = _lieux()
    _wire(monkeypatch, [("explorateur", 2), ("garde_royale", 1)])
    view, _files = await lieux._comptes_window(_strings(), _kingdom(), {})
    body = _texts(view)
    assert "🧭 **Explorateur** — x2" in body
    assert "💂 **Garde Royale** — x1" in body
    assert "🧭 🧭" not in body and "💂 💂" not in body, (
        "one emoji per card line — the counter emoji never doubles"
    )


def test_the_card_fiche_carries_one_emoji_only() -> None:
    lieux = _lieux()
    fiche = lieux._comptes_card_fiche("explorateur", "fr")
    assert fiche.startswith("## 🧭 Explorateur"), "title = one emoji + bare name"
    assert "## 🧭 🧭" not in fiche
    assert lieux._market_bare_label("👑 Garde Royale") == "Garde Royale"
    assert lieux._market_bare_label("Garde Royale") == "Garde Royale", (
        "a label without emoji passes through untouched"
    )


@pytest.mark.asyncio
async def test_the_card_buttons_are_blue_selected_green(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lieux = _lieux()
    _wire(monkeypatch, [("explorateur", 2), ("corruption", 1)])
    _wire_art(monkeypatch)
    # Rien de sélectionné : TOUTES les cartes sont BLEUES.
    view, _files = await lieux._comptes_window(_strings(), _kingdom(), {})
    styles = {
        str(b.custom_id): b.style.value
        for b in view.walk_children()
        if getattr(b, "custom_id", None)
    }
    assert styles["kingdoms:lieux:comptes:card:explorateur"] == 1, "primary = blue"
    assert styles["kingdoms:lieux:comptes:card:corruption"] == 1
    # Une carte sélectionnée : ELLE devient VERTE, les autres restent bleues.
    view, _files = await lieux._comptes_window(
        _strings(), _kingdom(), {}, selected="explorateur"
    )
    styles = {
        str(b.custom_id): b.style.value
        for b in view.walk_children()
        if getattr(b, "custom_id", None)
    }
    assert styles["kingdoms:lieux:comptes:card:explorateur"] == 3, "success = green"
    assert styles["kingdoms:lieux:comptes:card:corruption"] == 1


def test_the_wallet_label_exists_both_locales() -> None:
    from botforge.mods.kingdom.cogs.strings import strings

    assert "Points technologiques du royaume" in strings("fr")["market_wallet"]
    assert "tech points" in strings("en")["market_wallet"].lower()
    assert "Banque" not in strings("fr")["market_wallet"]
    assert "{0}" in strings("fr")["market_wallet"]
