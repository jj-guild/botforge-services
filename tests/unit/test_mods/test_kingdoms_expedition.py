"""Kingdoms mod expedition (exploration-expedition-v1) - unit tests.

Drasah 30/10/2026: the Explorateur token funds a whole EXPEDITION now —
the 🧭 salon boards a CHEF (one AVAILABLE defence point, never
consumed) and a self-enrolled CREW (each −4h of travel, floor 24h);
« Lâcher les amarres » is the single token-consuming step and the tick
resolves the return (a fresh map, or the compensation civ + 2 ⚙️ when
the map pool ran dry)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from kingdoms.mods.kingdoms.config import default_season_config
from kingdoms.mods.kingdoms.economy import (
    EXPEDITION_MIN_SECONDS,
    EXPLORATEUR_STOCK,
    EconomyError,
    EconomyService,
)
from kingdoms.mods.kingdoms import economy as economy_module
from kingdoms.mods.kingdoms.models import LordRole, TechnologyState
from tests.mocks.discord_mock import MockGuild

from .test_kingdoms_attacks import Bundle as _AttackBundle

_CIVS = ("bretons", "perses", "byzantins")


@pytest.fixture(autouse=True)
def _prod_token_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    """exploration-beta-illimite (Drasah 02/11): the beta ships with
    UNLIMITED voyages, so the module flag is True in production — the
    suite freezes the prod token rules back ON (boarding needs a
    token, the launch consumes it, a cancel refunds it)."""
    monkeypatch.setattr(economy_module, "EXPEDITION_BETA_UNLIMITED", False)
_MONDAY = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)


def _config_with_civs(*civs: str):
    """A default config carrying a civilization catalog (compensation)."""
    from kingdoms.mods.kingdoms.config import (
        CivilizationCondition,
        KingdomsSeasonConfig,
    )

    config = default_season_config()
    data = config.model_dump()
    data["civilizations"] = [
        CivilizationCondition(key=key, display_name=key.title()).model_dump()
        for key in civs
    ]
    return KingdomsSeasonConfig.model_validate(data)


class Bundle(_AttackBundle):
    """The attack bundle extended with the economy service."""

    def __init__(self, config=None) -> None:
        super().__init__(config)
        self.economy = EconomyService(  # type: ignore[arg-type]
            self.store, self.config, self.kingdoms, self.territories, self.attacks
        )

    async def token(self, kingdom_id: str, count: int = 1) -> None:
        """Put Explorateur tokens in the kingdom's reserve."""
        state = TechnologyState(
            _id=kingdom_id, season_id="s", tech_points=0, purchases={}
        )
        state.purchases[EXPLORATEUR_STOCK] = count
        await self.store.upsert_technology(state.to_mongo())

    async def stock_left(self, kingdom_id: str) -> int:
        """Read the kingdom's remaining Explorateur tokens."""
        state = await self.attacks.technology_state(kingdom_id)
        return int(state.purchases.get(EXPLORATEUR_STOCK, 0) or 0)

    async def fund(self, kingdom_id: str, points: int) -> None:
        await self.economy.grant_tech_points(kingdom_id, points)


async def test_boarding_requires_a_token_and_is_idempotent() -> None:
    """No token → no boarding; a live boarding re-opens untouched."""
    bundle = Bundle()
    await bundle.launch_season()
    aquitaine = await bundle.kingdom_id("Aquitaine")
    with pytest.raises(EconomyError):
        await bundle.economy.begin_expedition(aquitaine)
    await bundle.token(aquitaine)
    doc = await bundle.economy.begin_expedition(aquitaine)
    assert doc["state"] == "boarding"
    assert doc["chef_lord_id"] is None
    assert doc["crew"] == []
    # The token is NOT consumed by the boarding — only the launch does.
    assert await bundle.stock_left(aquitaine) == 1
    again = await bundle.economy.begin_expedition(aquitaine)
    assert again == doc
    assert await bundle.stock_left(aquitaine) == 1


async def test_chef_needs_an_available_defence_point_never_consumed() -> None:
    """The defence point is a PREREQUISITE — enrolling never spends it."""
    bundle = Bundle()
    await bundle.launch_season()
    aquitaine = await bundle.kingdom_id("Aquitaine")
    await bundle.token(aquitaine)
    await bundle.economy.begin_expedition(aquitaine)
    # lord-a already spent his weekly defence: refused.
    lord = next(l for l in await bundle.kingdoms.lords() if l.id == "lord-a")
    lord.defense_used = 1
    await bundle.store.upsert_lord(lord.to_mongo())
    with pytest.raises(EconomyError):
        await bundle.economy.toggle_expedition_chef(aquitaine, "lord-a")
    # king-a still has his: enrolled — and the point stays.
    doc = await bundle.economy.toggle_expedition_chef(aquitaine, "king-a")
    assert doc["chef_lord_id"] == "king-a"
    king = next(l for l in await bundle.kingdoms.lords() if l.id == "king-a")
    assert king.defense_used == 0
    # Toggle off: the chef steps down.
    doc = await bundle.economy.toggle_expedition_chef(aquitaine, "king-a")
    assert doc["chef_lord_id"] is None


async def test_crew_cuts_the_travel_but_never_the_chef() -> None:
    """Each self-enrolled crew member cuts 4h; the chef never cuts it."""
    bundle = Bundle()
    await bundle.launch_season()
    aquitaine = await bundle.kingdom_id("Aquitaine")
    await bundle.token(aquitaine)
    await bundle.economy.begin_expedition(aquitaine)
    await bundle.economy.toggle_expedition_chef(aquitaine, "king-a")
    doc = await bundle.economy.toggle_expedition_crew(aquitaine, "lord-a")
    assert doc["crew"] == ["lord-a"]
    # Toggling twice leaves the crew.
    doc = await bundle.economy.toggle_expedition_crew(aquitaine, "lord-a")
    assert doc["crew"] == []
    await bundle.economy.toggle_expedition_crew(aquitaine, "lord-a")
    # The chef cannot embark as a mate.
    with pytest.raises(EconomyError):
        await bundle.economy.toggle_expedition_crew(aquitaine, "king-a")
    # A locked lord cannot embark.
    lord = next(l for l in await bundle.kingdoms.lords() if l.id == "lord-b")
    lord.kingdom_id = aquitaine
    lord.marriage_locked_until = int((_MONDAY + timedelta(hours=2)).timestamp())
    await bundle.store.upsert_lord(lord.to_mongo())
    with pytest.raises(EconomyError):
        await bundle.economy.toggle_expedition_crew(aquitaine, "lord-b")


async def test_launch_consumes_the_token_and_locks_chef_and_crew() -> None:
    """BETA (exploration-beta-duree): 10 min − 50 s per mate, floor
    5 min — the locks ride the existing guard."""
    bundle = Bundle()
    await bundle.launch_season()
    for name in ("lord-c", "lord-d", "lord-e", "lord-f", "lord-g", "lord-h"):
        await bundle.kingdoms.enroll(
            name, name.title(), LordRole.LORD, kingdom_name="Aquitaine"
        )
    aquitaine = await bundle.kingdom_id("Aquitaine")
    await bundle.token(aquitaine)
    await bundle.economy.begin_expedition(aquitaine)
    await bundle.economy.toggle_expedition_chef(aquitaine, "king-a")
    # One crew member: 600 s − 50 s = 550 s.
    await bundle.economy.toggle_expedition_crew(aquitaine, "lord-a")
    doc = await bundle.economy.launch_expedition(aquitaine, now=_MONDAY)
    assert doc["state"] == "sailing"
    assert await bundle.stock_left(aquitaine) == 0
    ends = int((_MONDAY + timedelta(seconds=550)).timestamp())
    assert doc["ends_at"] == ends
    king = next(l for l in await bundle.kingdoms.lords() if l.id == "king-a")
    lord = next(l for l in await bundle.kingdoms.lords() if l.id == "lord-a")
    assert king.exploration_locked_until == ends
    assert lord.exploration_locked_until == ends
    doc = await bundle.economy.launch_expedition(aquitaine, now=_MONDAY)
    ends = int(doc["ends_at"])
    assert await bundle.stock_left(aquitaine) == 0
    # A second expedition cannot start while one sails.
    await bundle.token(aquitaine)
    with pytest.raises(EconomyError):
        await bundle.economy.begin_expedition(aquitaine)
    # Floor: 7 mates would cut below — the plancher holds 5 min.
    await bundle.economy.resolve_due_expeditions(
        now=_MONDAY + timedelta(seconds=600)
    )
    # exploration-retour-v1: the resolve HOLDS the locks — the crew
    # must unload before a new journey.
    doc = await bundle.economy.expedition(aquitaine)
    assert doc["state"] == "returned"
    with pytest.raises(EconomyError):
        await bundle.economy.begin_expedition(aquitaine)
    await bundle.economy.claim_expedition_return(aquitaine, "king-a")
    await bundle.token(aquitaine)
    doc = await bundle.economy.begin_expedition(aquitaine)
    for name in ("lord-a", "lord-c", "lord-d", "lord-e", "lord-f", "lord-g", "lord-h"):
        await bundle.economy.toggle_expedition_crew(aquitaine, name)
    await bundle.economy.toggle_expedition_chef(aquitaine, "king-a")
    doc = await bundle.economy.launch_expedition(aquitaine, now=_MONDAY)
    assert doc["ends_at"] == int(
        (_MONDAY + timedelta(seconds=EXPEDITION_MIN_SECONDS)).timestamp()
    )


async def test_launch_without_chef_or_token_is_refused() -> None:
    """Refusals never consume anything (anti-abus invariant)."""
    bundle = Bundle()
    await bundle.launch_season()
    aquitaine = await bundle.kingdom_id("Aquitaine")
    await bundle.token(aquitaine)
    await bundle.economy.begin_expedition(aquitaine)
    with pytest.raises(EconomyError):
        await bundle.economy.launch_expedition(aquitaine)
    await bundle.economy.toggle_expedition_chef(aquitaine, "king-a")
    # The token vanished between boarding and launch: refused.
    state = await bundle.attacks.technology_state(aquitaine)
    state.purchases[EXPLORATEUR_STOCK] = 0
    await bundle.store.upsert_technology(state.to_mongo())
    with pytest.raises(EconomyError):
        await bundle.economy.launch_expedition(aquitaine)
    doc = await bundle.economy.expedition(aquitaine)
    assert doc["state"] == "boarding"


async def test_resolve_draws_a_map_and_waits_for_the_unload() -> None:
    """exploration-retour-v1: the resolve draws the map but HOLDS the
    locks — the doc flips to RETURNED and the crew unloads it (« 🪜 »)."""
    bundle = Bundle()
    await bundle.launch_season()
    aquitaine = await bundle.kingdom_id("Aquitaine")
    await bundle.token(aquitaine)
    await bundle.economy.begin_expedition(aquitaine)
    await bundle.economy.toggle_expedition_chef(aquitaine, "king-a")
    await bundle.economy.toggle_expedition_crew(aquitaine, "lord-a")
    doc = await bundle.economy.launch_expedition(aquitaine, now=_MONDAY)
    ends = int(doc["ends_at"])
    # Before the return: nothing resolves.
    assert (
        await bundle.economy.resolve_due_expeditions(
            now=_MONDAY + timedelta(hours=43)
        )
    ) == []
    resolved = await bundle.economy.resolve_due_expeditions(
        now=_MONDAY + timedelta(hours=45)
    )
    assert len(resolved) == 1
    kingdom, kind, value, salon_id = resolved[0]
    assert kingdom.id == aquitaine
    assert kind == "map"
    assert value in [
        entry.key for entry in bundle.config.maps
    ]
    assert salon_id == 0
    territory = next(
        t for t in await bundle.territories.territories() if t.map_key == value
    )
    assert territory.owner_kingdom_id == aquitaine
    # the doc flips to RETURNED — gain stored, locks HELD (no fallback).
    doc = await bundle.economy.expedition(aquitaine)
    assert doc["state"] == "returned"
    assert doc["gain_kind"] == "map"
    assert doc["gain_value"] == value
    king = next(l for l in await bundle.kingdoms.lords() if l.id == "king-a")
    lord = next(l for l in await bundle.kingdoms.lords() if l.id == "lord-a")
    assert king.exploration_locked_until == ends
    assert lord.exploration_locked_until == ends
    # Idempotent: a second pass resolves nothing (the doc is no longer
    # sailing).
    assert (
        await bundle.economy.resolve_due_expeditions(
            now=_MONDAY + timedelta(hours=46)
        )
    ) == []
    # a stranger may NOT unload the return.
    with pytest.raises(EconomyError):
        await bundle.economy.claim_expedition_return(aquitaine, "lord-b")
    # any ABOARD lord may: the mate's click wins — locks clear, doc empties.
    claimed = await bundle.economy.claim_expedition_return(aquitaine, "lord-a")
    assert claimed["gain_kind"] == "map"
    assert claimed["chef_lord_id"] == "king-a"
    assert claimed["crew"] == ["lord-a"]
    king = next(l for l in await bundle.kingdoms.lords() if l.id == "king-a")
    lord = next(l for l in await bundle.kingdoms.lords() if l.id == "lord-a")
    assert king.exploration_locked_until is None
    assert lord.exploration_locked_until is None
    assert await bundle.economy.expedition(aquitaine) == {}
    with pytest.raises(EconomyError):
        await bundle.economy.claim_expedition_return(aquitaine, "king-a")


async def test_exhausted_pool_pays_a_civ_and_two_points() -> None:
    """Pool dry at the return → one NEW civ (origin exploration) + 2 ⚙️."""
    bundle = Bundle(_config_with_civs(*_CIVS))
    await bundle.launch_season()
    aquitaine = await bundle.kingdom_id("Aquitaine")
    bourgogne = await bundle.kingdom_id("Bourgogne")
    await bundle.token(aquitaine)
    await bundle.economy.begin_expedition(aquitaine)
    await bundle.economy.toggle_expedition_chef(aquitaine, "king-a")
    doc = await bundle.economy.launch_expedition(aquitaine, now=_MONDAY)
    # Drain the whole map catalog before the return.
    for entry in bundle.config.maps:
        await bundle.territories.draw_map_for(bourgogne, entry.key)
    resolved = await bundle.economy.resolve_due_expeditions(
        now=_MONDAY + timedelta(hours=49)
    )
    assert len(resolved) == 1
    kingdom, kind, value, _ = resolved[0]
    assert kind == "civ"
    assert value in _CIVS
    assert value in kingdom.civilizations
    assert kingdom.civilization_acquisitions[value]["origin"] == "exploration"
    assert await bundle.economy.wallet(aquitaine) == 2


async def test_exhausted_pool_without_civs_pays_points_only() -> None:
    """No map AND no civ left: the compensation falls back to 2 ⚙️."""
    bundle = Bundle()  # the default config carries NO civilizations
    await bundle.launch_season()
    aquitaine = await bundle.kingdom_id("Aquitaine")
    bourgogne = await bundle.kingdom_id("Bourgogne")
    await bundle.token(aquitaine)
    await bundle.economy.begin_expedition(aquitaine)
    await bundle.economy.toggle_expedition_chef(aquitaine, "king-a")
    await bundle.economy.launch_expedition(aquitaine, now=_MONDAY)
    for entry in bundle.config.maps:
        await bundle.territories.draw_map_for(bourgogne, entry.key)
    resolved = await bundle.economy.resolve_due_expeditions(
        now=_MONDAY + timedelta(hours=49)
    )
    assert len(resolved) == 1
    kingdom, kind, value, _ = resolved[0]
    assert kind == "tech"
    assert value == ""
    assert await bundle.economy.wallet(aquitaine) == 2


async def test_the_salon_opens_in_the_realm_category_with_its_panel() -> None:
    """The 🧭 salon lives in the kingdom's category, gated, panel pinned."""
    from kingdoms.mods.kingdoms import kingdom_expedition_panel as panel

    bundle = Bundle()
    await bundle.launch_season()
    aquitaine = await bundle.kingdom_id("Aquitaine")
    await bundle.token(aquitaine)
    guild = MockGuild()
    await guild.create_category("🏰 Aquitaine")
    wiring = _PanelWiring(bundle)
    kingdom = next(
        k for k in await bundle.kingdoms.kingdoms() if k.id == aquitaine
    )
    channel = await panel.open_expedition_salon_safe(guild, wiring, kingdom)
    assert channel is not None
    assert channel.category is not None
    doc = await bundle.economy.expedition(aquitaine)
    assert int(doc["salon_id"]) == int(channel.id)
    assert doc["panel_message_id"] is not None
    # exploration-refonte-v1: the boarding face carries ⚓ + 🚪 (the
    # captain enrolls from the council fiche, never from the salon) —
    # ⛵ stays hidden until a captain is on board, and the body carries
    # the boarding window (5 minutes, beta).
    message = await channel.fetch_message(int(doc["panel_message_id"]))
    view = message.view
    assert view is not None
    custom_ids = [item.custom_id for item in view.children]
    assert "kingdoms:expedition:crew" in custom_ids
    assert "kingdoms:expedition:quit" in custom_ids
    assert "kingdoms:expedition:launch" not in custom_ids
    text = str(message.content)
    assert "Capitaine" in text
    assert "5 minutes" in text
    # The overwrites carry the INVARIANT: @everyone denied, the bot in.
    overwrites = channel.overwrites
    assert not overwrites[guild.default_role].view_channel
    assert overwrites[guild.me].view_channel


class _PanelWiring:
    """The minimal wiring the expedition panel needs (the real shape)."""

    def __init__(self, bundle: Bundle) -> None:
        self.kingdoms_service = bundle.kingdoms
        self.economy_service = bundle.economy


# ---------------------------------------------------------------------------
# exploration-refonte-v1 (Drasah 02/11) — the captain-first fiche, the
# 15-minute window, the quit semantics and the refund.
# ---------------------------------------------------------------------------


async def test_captain_expedition_checks_the_defence_point_first() -> None:
    """conseil-exploration-v1: no token → nothing; no defence point →
    the boarding opens but NO captain (and the fiche never opens a
    salon); eligible → captain enrolled, idempotent."""
    bundle = Bundle()
    await bundle.launch_season()
    aquitaine = await bundle.kingdom_id("Aquitaine")
    # no token: refused before anything.
    with pytest.raises(EconomyError):
        await bundle.economy.captain_expedition(aquitaine, "king-a")
    assert await bundle.economy.expedition(aquitaine) == {}
    await bundle.token(aquitaine)
    # the weekly defence already spent: refused, no captain, no salon.
    king = next(l for l in await bundle.kingdoms.lords() if l.id == "king-a")
    king.defense_used = 1
    await bundle.store.upsert_lord(king.to_mongo())
    with pytest.raises(EconomyError):
        await bundle.economy.captain_expedition(aquitaine, "king-a")
    doc = await bundle.economy.expedition(aquitaine)
    assert doc["state"] == "boarding"
    assert doc["chef_lord_id"] is None
    assert doc["salon_id"] is None
    # eligible: enrolled — and the point stays unconsumed.
    king.defense_used = 0
    await bundle.store.upsert_lord(king.to_mongo())
    doc = await bundle.economy.captain_expedition(aquitaine, "king-a")
    assert doc["chef_lord_id"] == "king-a"
    king = next(l for l in await bundle.kingdoms.lords() if l.id == "king-a")
    assert king.defense_used == 0
    # idempotent: a second click never steps him down.
    doc = await bundle.economy.captain_expedition(aquitaine, "king-a")
    assert doc["chef_lord_id"] == "king-a"


async def test_launch_rechecks_the_captain_defence_point() -> None:
    """The captain spent his point during the window → the cast-off
    refuses, nothing is consumed."""
    bundle = Bundle()
    await bundle.launch_season()
    aquitaine = await bundle.kingdom_id("Aquitaine")
    await bundle.token(aquitaine)
    await bundle.economy.begin_expedition(aquitaine)
    await bundle.economy.toggle_expedition_chef(aquitaine, "king-a")
    king = next(l for l in await bundle.kingdoms.lords() if l.id == "king-a")
    king.defense_used = 1
    await bundle.store.upsert_lord(king.to_mongo())
    with pytest.raises(EconomyError):
        await bundle.economy.launch_expedition(aquitaine, now=_MONDAY)
    doc = await bundle.economy.expedition(aquitaine)
    assert doc["state"] == "boarding"
    assert await bundle.stock_left(aquitaine) == 1


async def test_only_the_captain_may_cancel_a_boarding() -> None:
    """🚪 on a boarding: the doc clears, nothing was consumed — and
    nobody but the captain may cancel."""
    bundle = Bundle()
    await bundle.launch_season()
    aquitaine = await bundle.kingdom_id("Aquitaine")
    await bundle.token(aquitaine)
    await bundle.economy.captain_expedition(aquitaine, "king-a")
    with pytest.raises(EconomyError):
        await bundle.economy.cancel_expedition(aquitaine, "lord-a")
    doc = await bundle.economy.expedition(aquitaine)
    assert doc["state"] == "boarding"
    result = await bundle.economy.cancel_expedition(aquitaine, "king-a")
    assert result["kind"] == "boarding"
    assert result["refunded"] is False
    assert await bundle.economy.expedition(aquitaine) == {}
    assert await bundle.stock_left(aquitaine) == 1


async def test_cancelling_a_sailing_exploration_refunds_and_unlocks() -> None:
    """🚪 on a sailing ship: the captain alone may leave — every lock
    clears and the Explorateur token is refunded."""
    bundle = Bundle()
    await bundle.launch_season()
    aquitaine = await bundle.kingdom_id("Aquitaine")
    await bundle.token(aquitaine)
    await bundle.economy.begin_expedition(aquitaine)
    await bundle.economy.toggle_expedition_chef(aquitaine, "king-a")
    await bundle.economy.toggle_expedition_crew(aquitaine, "lord-a")
    doc = await bundle.economy.launch_expedition(aquitaine, now=_MONDAY)
    ends = int(doc["ends_at"])
    # a mate cannot quit a sailing ship.
    with pytest.raises(EconomyError):
        await bundle.economy.cancel_expedition(aquitaine, "lord-a")
    result = await bundle.economy.cancel_expedition(aquitaine, "king-a")
    assert result["kind"] == "sailing"
    assert result["refunded"] is True
    assert await bundle.stock_left(aquitaine) == 1
    assert await bundle.economy.expedition(aquitaine) == {}
    king = next(l for l in await bundle.kingdoms.lords() if l.id == "king-a")
    lord = next(l for l in await bundle.kingdoms.lords() if l.id == "lord-a")
    assert king.exploration_locked_until is None
    assert lord.exploration_locked_until is None


async def test_auto_launch_fires_once_the_window_elapses() -> None:
    """The 5-minute window (beta): no captain → it waits; 4 minutes →
    nothing; 6 minutes → the voyage launches itself; idempotent."""
    bundle = Bundle()
    await bundle.launch_season()
    aquitaine = await bundle.kingdom_id("Aquitaine")
    await bundle.token(aquitaine)
    await bundle.economy.begin_expedition(aquitaine, now=_MONDAY)
    # no captain yet: the window keeps waiting.
    assert (
        await bundle.economy.auto_launch_due_expeditions(
            now=_MONDAY + timedelta(minutes=8)
        )
    ) == []
    await bundle.economy.toggle_expedition_chef(aquitaine, "king-a")
    await bundle.economy.toggle_expedition_crew(aquitaine, "lord-a")
    assert (
        await bundle.economy.auto_launch_due_expeditions(
            now=_MONDAY + timedelta(minutes=4)
        )
    ) == []
    results = await bundle.economy.auto_launch_due_expeditions(
        now=_MONDAY + timedelta(minutes=6)
    )
    assert len(results) == 1
    _kingdom, kind, value, _salon = results[0]
    assert kind == "launched"
    assert int(value) == int((_MONDAY + timedelta(minutes=6, seconds=550)).timestamp())
    doc = await bundle.economy.expedition(aquitaine)
    assert doc["state"] == "sailing"
    assert await bundle.stock_left(aquitaine) == 0
    assert (
        await bundle.economy.auto_launch_due_expeditions(
            now=_MONDAY + timedelta(minutes=7)
        )
    ) == []


async def test_auto_launch_fails_when_the_point_was_spent() -> None:
    """The captain lost his defence point at the deadline → the boarding
    cancels (nothing was consumed, no refund needed)."""
    bundle = Bundle()
    await bundle.launch_season()
    aquitaine = await bundle.kingdom_id("Aquitaine")
    await bundle.token(aquitaine)
    await bundle.economy.begin_expedition(aquitaine, now=_MONDAY)
    await bundle.economy.toggle_expedition_chef(aquitaine, "king-a")
    king = next(l for l in await bundle.kingdoms.lords() if l.id == "king-a")
    king.defense_used = 1
    await bundle.store.upsert_lord(king.to_mongo())
    results = await bundle.economy.auto_launch_due_expeditions(
        now=_MONDAY + timedelta(minutes=6)
    )
    assert len(results) == 1
    _kingdom, kind, value, _salon = results[0]
    assert kind == "cancelled"
    assert value == ""
    assert await bundle.economy.expedition(aquitaine) == {}
    assert await bundle.stock_left(aquitaine) == 1


async def test_the_sailing_panel_is_a_pure_info_panel() -> None:
    """exploration-retour-v4: after the cast-off the panel carries ZERO
    buttons (the native <t:…:R> countdown lives client-side, nobody may
    quit mid-sea); the boarding face keeps ⛵ + ⚓ + 🚪 and gains the
    💎 bounty line."""
    from kingdoms.mods.kingdoms import kingdom_expedition_panel as panel

    bundle = Bundle()
    await bundle.launch_season()
    aquitaine = await bundle.kingdom_id("Aquitaine")
    await bundle.token(aquitaine)
    guild = MockGuild()
    await guild.create_category("🏰 Aquitaine")
    wiring = _PanelWiring(bundle)
    kingdom = next(
        k for k in await bundle.kingdoms.kingdoms() if k.id == aquitaine
    )
    await bundle.economy.captain_expedition(aquitaine, "king-a")
    channel = await panel.open_expedition_salon_safe(guild, wiring, kingdom)
    assert channel is not None
    doc = await bundle.economy.expedition(aquitaine)
    message = await channel.fetch_message(int(doc["panel_message_id"]))
    ids = [item.custom_id for item in message.view.children]
    # a captain is on board: boarding = ⛵ + ⚓ + 🚪.
    assert ids == [
        "kingdoms:expedition:launch",
        "kingdoms:expedition:crew",
        "kingdoms:expedition:quit",
    ]
    # exploration-retour-v4: the boarding face carries the bounty line.
    assert "Remporte un territoire aléatoire" in str(message.content)
    await bundle.economy.launch_expedition(aquitaine)
    await panel.refresh_expedition_panel_safe(guild, wiring, aquitaine)
    ids = [item.custom_id for item in message.view.children]
    # exploration-retour-v4: the sailing face = ZERO buttons.
    assert ids == []
    text = str(message.content)
    assert "◉ Voyage" in text
    assert "Retour estimé" in text
    # the returned face = 🪜 alone, the RP dock text and the gain.
    await bundle.economy.resolve_due_expeditions(
        now=datetime(2026, 12, 1, tzinfo=UTC)
    )
    await panel.refresh_expedition_panel_safe(guild, wiring, aquitaine)
    ids = [item.custom_id for item in message.view.children]
    assert ids == ["kingdoms:expedition:unload"]
    text = str(message.content)
    assert "◉ Retour" in text
    assert "*" in text  # the italic RP dock line
    assert "Découverte" in text or "Recrue" in text or "Butin" in text


# ---------------------------------------------------------------------------
# exploration-retour-v1 (Drasah 02/11) — the AT-SEA mask and the unload.
# ---------------------------------------------------------------------------


async def test_cancel_returns_the_locked_ids_for_the_unmask() -> None:
    """The sailing cancel rides its locked ids — the caller lifts the
    AT-SEA mask with them."""
    bundle = Bundle()
    await bundle.launch_season()
    aquitaine = await bundle.kingdom_id("Aquitaine")
    await bundle.token(aquitaine)
    await bundle.economy.begin_expedition(aquitaine)
    await bundle.economy.toggle_expedition_chef(aquitaine, "king-a")
    await bundle.economy.toggle_expedition_crew(aquitaine, "lord-a")
    await bundle.economy.launch_expedition(aquitaine, now=_MONDAY)
    result = await bundle.economy.cancel_expedition(aquitaine, "king-a")
    assert result["kind"] == "sailing"
    assert result["refunded"] is True
    assert sorted(result["locked"]) == ["king-a", "lord-a"]


async def test_the_at_sea_mask_hides_the_realm_and_keeps_the_salon() -> None:
    """exploration-retour-v2: once at sea the crew sees ONLY the voyage
    — member denies on the realm category AND on every other category
    of the server (the Taverne pattern), the salon keeps its child
    allow, and the unload restores everything WITHOUT touching an
    unrelated member overwrite (an ALLOW survives)."""
    from types import SimpleNamespace

    from kingdoms.mods.kingdoms import kingdom_expedition_panel as panel
    from kingdoms.mods.kingdoms.kingdom_realms import realm_category_name

    import discord

    from tests.mocks.discord_mock import MockMember

    guild = MockGuild()
    captain = MockMember(id=101, name="captain", guild=guild)
    mate = MockMember(id=102, name="mate", guild=guild)
    guild.add_member(captain)
    guild.add_member(mate)
    category = await guild.create_category(realm_category_name("Aquitaine"))
    salon = await guild.create_text_channel("🧭 exploration", category=category)
    beta = await guild.create_category(realm_category_name("Beta"))
    await guild.create_text_channel("salon beta", category=beta)
    doc = {
        "state": "sailing",
        "chef_lord_id": "101",
        "crew": ["102"],
        "salon_id": str(salon.id),
    }

    class _Economy:
        async def expedition(self, _kingdom_id: str) -> dict:
            return doc

    wiring = SimpleNamespace(economy_service=_Economy())
    kingdom = SimpleNamespace(id="k-1", name="Aquitaine")
    await panel.mask_crew_for_voyage_safe(guild, wiring, kingdom)
    assert not category.permission_overwrite_for(captain).view_channel
    assert not category.permission_overwrite_for(mate).view_channel
    assert salon.overwrites[captain].view_channel
    assert salon.overwrites[mate].view_channel
    # exploration-retour-v2: the WHOLE server disappears, Taverne-style.
    assert not beta.permission_overwrite_for(captain).view_channel
    assert not beta.permission_overwrite_for(mate).view_channel
    # the unload restores the realm allow (the _realm_overwrites entry)
    # and drops ONLY our view denies elsewhere — an unrelated member
    # overwrite (here: an outgame-style ALLOW) survives the cleanup.
    beta._overwrites[(103, False)] = discord.PermissionOverwrite(view_channel=True)
    await panel.unmask_crew_safe(guild, kingdom, ["101", "102"])
    assert category.permission_overwrite_for(captain).view_channel
    assert category.permission_overwrite_for(mate).view_channel
    assert beta.permission_overwrite_for(captain) is None
    assert beta.permission_overwrite_for(mate) is None
    survivor = beta.permission_overwrite_for(
        MockMember(id=103, name="stranger", guild=guild)
    )
    assert survivor is not None and survivor.view_channel


async def test_the_legacy_resolver_never_touches_a_live_expedition() -> None:
    """exploration-retour-v3: the SOLO resolver (the market's legacy
    engine) skips the crew of a kingdom whose expedition is alive
    (boarding/sailing/returned) — the expedition's own resolver owns
    those locks (the 02/11 double-draw: two maps for one token)."""
    bundle = Bundle()
    await bundle.launch_season()
    aquitaine = await bundle.kingdom_id("Aquitaine")
    await bundle.token(aquitaine)
    await bundle.economy.begin_expedition(aquitaine)
    await bundle.economy.toggle_expedition_chef(aquitaine, "king-a")
    await bundle.economy.toggle_expedition_crew(aquitaine, "lord-a")
    await bundle.economy.launch_expedition(aquitaine, now=_MONDAY)
    ends = int((await bundle.economy.expedition(aquitaine))["ends_at"])
    # A SOLO lord of another kingdom with an expired lock still resolves.
    solo = next(l for l in await bundle.kingdoms.lords() if l.id == "lord-b")
    solo.exploration_locked_until = ends - 60
    await bundle.store.upsert_lord(solo.to_mongo())
    resolved = await bundle.economy.resolve_due_explorations(
        now=_MONDAY + timedelta(seconds=600)
    )
    assert [lord.id for lord, _ in resolved] == ["lord-b"]
    # The expedition crew was NOT touched: locks held, no solo draw.
    king = next(l for l in await bundle.kingdoms.lords() if l.id == "king-a")
    mate = next(l for l in await bundle.kingdoms.lords() if l.id == "lord-a")
    assert king.exploration_locked_until == ends
    assert mate.exploration_locked_until == ends
    drawn = await bundle.territories.territories()
    assert all(t.owner_kingdom_id != aquitaine for t in drawn)
    # Past the voyage, the RETURNED doc keeps shielding the crew — only
    # « 🪜 Descendre du navire » may clear those locks.
    await bundle.economy.resolve_due_expeditions(
        now=_MONDAY + timedelta(seconds=600)
    )
    resolved = await bundle.economy.resolve_due_explorations(
        now=_MONDAY + timedelta(seconds=600)
    )
    assert resolved == []
    king = next(l for l in await bundle.kingdoms.lords() if l.id == "king-a")
    assert king.exploration_locked_until == ends
    # Once claimed the doc is gone — nothing left to shield (the locks
    # were already cleared by the claim itself).
    await bundle.economy.claim_expedition_return(aquitaine, "king-a")
    assert (
        await bundle.economy.resolve_due_explorations(
            now=_MONDAY + timedelta(seconds=600)
        )
    ) == []


async def test_the_refresh_reposts_a_vanished_panel() -> None:
    """exploration-retour-v3: when the pinned panel message is GONE
    (404 Unknown Message, 02/11 logs) the refresh re-posts a fresh
    panel into the salon and re-records its id — the ◉ Retour face
    never silently disappears."""
    from kingdoms.mods.kingdoms import kingdom_expedition_panel as panel

    bundle = Bundle()
    await bundle.launch_season()
    aquitaine = await bundle.kingdom_id("Aquitaine")
    await bundle.token(aquitaine)
    guild = MockGuild()
    await guild.create_category("🏰 Aquitaine")
    wiring = _PanelWiring(bundle)
    kingdom = next(
        k for k in await bundle.kingdoms.kingdoms() if k.id == aquitaine
    )
    channel = await panel.open_expedition_salon_safe(guild, wiring, kingdom)
    assert channel is not None
    doc = await bundle.economy.expedition(aquitaine)
    old_id = int(doc["panel_message_id"])
    # The panel message vanishes (deleted by a human, a purge, anything).
    channel.messages.clear()
    await panel.refresh_expedition_panel_safe(guild, wiring, aquitaine)
    doc = await bundle.economy.expedition(aquitaine)
    new_id = int(doc["panel_message_id"])
    assert new_id != old_id
    assert len(channel.messages) == 1
    fresh = await channel.fetch_message(new_id)
    assert "Capitaine" in str(fresh.content)
    # The next refresh edits the RE-POSTED message in place (no growth).
    await panel.refresh_expedition_panel_safe(guild, wiring, aquitaine)
    assert len(channel.messages) == 1
    assert int((await bundle.economy.expedition(aquitaine))["panel_message_id"]) == new_id



async def test_beta_unlimited_voyages_never_touch_the_stock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """exploration-beta-illimite (Drasah 02/11): under the beta flag the
    voyages are UNLIMITED — no token needed to board, none consumed at
    the cast-off, and a cancel must NOT mint a phantom refund."""
    monkeypatch.setattr(economy_module, "EXPEDITION_BETA_UNLIMITED", True)
    bundle = Bundle()
    await bundle.launch_season()
    aquitaine = await bundle.kingdom_id("Aquitaine")
    # boarding with an EMPTY reserve: allowed under the flag.
    doc = await bundle.economy.begin_expedition(aquitaine, now=_MONDAY)
    assert doc["state"] == "boarding"
    await bundle.economy.toggle_expedition_chef(aquitaine, "king-a")
    launched = await bundle.economy.launch_expedition(aquitaine, now=_MONDAY)
    assert launched["state"] == "sailing"
    assert await bundle.stock_left(aquitaine) == 0
    # a cancel under the flag refunds NOTHING (no token was spent).
    result = await bundle.economy.cancel_expedition(aquitaine, "king-a")
    assert result["kind"] == "sailing"
    assert result["refunded"] is False
    assert await bundle.stock_left(aquitaine) == 0


async def test_sailing_and_returned_refusals_are_distinct_messages() -> None:
    """expedition-messages-v1 (Drasah 02/11): his live report showed a
    RETURNED expedition answered « already at sea » — the refusals are
    now split: sailing says "at sea", returned says "disembark"."""
    bundle = Bundle()
    await bundle.launch_season()
    aquitaine = await bundle.kingdom_id("Aquitaine")
    await bundle.token(aquitaine)
    await bundle.economy.begin_expedition(aquitaine, now=_MONDAY)
    await bundle.economy.toggle_expedition_chef(aquitaine, "king-a")
    launched = await bundle.economy.launch_expedition(aquitaine, now=_MONDAY)
    # still sailing: the old wording.
    with pytest.raises(EconomyError, match="already at sea"):
        await bundle.economy.begin_expedition(aquitaine)
    # the journey returns: the NEW wording, never "at sea" again.
    resolved = await bundle.economy.resolve_due_expeditions(
        now=_MONDAY + timedelta(seconds=int(launched["ends_at"]) - int(_MONDAY.timestamp()) + 10)
    )
    assert len(resolved) == 1
    doc = await bundle.economy.expedition(aquitaine)
    assert doc["state"] == "returned"
    with pytest.raises(EconomyError, match="disembark"):
        await bundle.economy.begin_expedition(aquitaine)


def test_map_error_translates_the_split_refusals_to_french_bubbles() -> None:
    """expedition-messages-v1 (Drasah 02/11): his wording — the exhausted
    explorer reads « épuisé » (never "a voyage is already at sea"), the
    returned journey reads « retour », the sailing one « en mer »."""
    from kingdoms.mods.kingdoms import kingdom_expedition_panel as panel

    strings = panel._strings("fr")
    assert "épuisé" in panel._map_error(
        strings, EconomyError("no explorateur token in stock — buy one at the market first")
    )
    assert "retour" in panel._map_error(
        strings, EconomyError("the expedition is back and its crew has not yet disembarked")
    )
    # expedition-messages-v2 (Drasah 02/11): his wording — it is the
    # CAPTAIN (and the crew, if any) who is back, not « l'expédition ».
    assert "capitaine" in strings["return_pending"]
    assert "en mer" in panel._map_error(
        strings, EconomyError("an expedition is already at sea")
    )
