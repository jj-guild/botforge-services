"""voliere-taverne-v1 (Drasah 28/11) — the volière port's own tests.

Tested at the logic level (the surfaces are discord-shaped, the
DECISIONS are data):

1. the cog's strings exist in BOTH locales with the SAME keys (the
   console-crash-v1 lesson: a missing key empties a whole salon);
2. the beta compression: under an armed, started beta EVERY volière
   delay lands at 5 minutes — the action cooldown AND the theft
   execution delay (voliere-beta-5min, Drasah's ruling: « tout
   maintenant, vol inclus »);
3. the corbeau theft state machine: pending → awaiting_continue →
   contest (dead + refund + slot lost) or continue (continuing →
   settled_both at the window's close) or no answer (settled_first);
4. the volière + taverne surfaces are DECLARED (views.yaml, #381).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest

import botforge.mods.kingdom.cogs.kingdom.voliere as voliere_cog
import botforge.mods.kingdom.voliere as voliere_engine
from botforge.mods.kingdom.models import KingdomModel, KingdomType

_NOW = datetime(2026, 11, 28, 12, 0, 0, tzinfo=UTC)


@pytest.mark.parametrize("locale", ("fr", "en"))
def test_the_voliere_strings_exist_in_both_locales(locale: str) -> None:
    fr = voliere_cog._STRINGS["fr"]
    en = voliere_cog._STRINGS["en"]
    assert fr and en
    assert set(fr.keys()) == set(en.keys()), "both locales carry the SAME keys"
    for key in fr:
        assert str(voliere_cog._STRINGS[locale][key]), f"the key {key} must not be empty"


def test_the_theft_views_carry_the_persistent_ids() -> None:
    alarm = voliere_cog.theft_alarm_view("fr")
    prompt = voliere_cog.theft_prompt_view("fr", "theft-1")
    alarm_ids = [str(item.custom_id) for item in alarm.children]
    prompt_ids = [str(item.custom_id) for item in prompt.children]
    assert any(cid.startswith("kingdom:corbeau:theft:contest:") for cid in alarm_ids)
    assert any(cid.startswith("kingdom:corbeau:theft:continue:") for cid in prompt_ids)
    assert any(cid.startswith("kingdom:corbeau:theft:stop:") for cid in prompt_ids)
    assert alarm.timeout is None and prompt.timeout is None, "restart-proof views"


# ---------------------------------------------------------------------------
# The engine — stubs
# ---------------------------------------------------------------------------


class _Store:
    async def upsert_kingdom(self, doc: Any) -> None:
        return None


def async_lambda(value: Any):
    async def _call() -> Any:
        return value

    return _call


def _kingdom(name: str, bank: int) -> KingdomModel:
    return KingdomModel(
        id=f"id-{name}",
        season_id="season-1",
        type=KingdomType.PLAYER,
        name=name,
        tech_points_bank=bank,
        voliere_slots=["corbeau"],
    )


def _service(kingdoms: list[KingdomModel]) -> voliere_engine.VoliereService:
    season = SimpleNamespace(
        current_age_key="feudal_age",
        beta_name="Beta Test",
        beta_start_at=None,  # armed legacy v1 → started
    )
    stack_kingdoms = SimpleNamespace(
        kingdoms=async_lambda(kingdoms),
        lords=async_lambda([]),
        current_season=async_lambda(season),
    )
    config = SimpleNamespace(
        ages=[SimpleNamespace(key="feudal_age")],
        voliere=SimpleNamespace(
            corbeau_civ_cooldown_hours=72,
            corbeau_verify_cooldown_hours=24,
            corbeau_track_cooldown_hours=48,
            corbeau_track_window_hours=24,
            corbeau_theft_delay_hours=1,
            corbeau_theft_contest_minutes=5,
            faucon_territory_cooldown_hours=96,
            faucon_sabotage_cooldown_hours=48,
            faucon_release_cooldown_hours=168,
            faucon_release_window_hours=24,
            pigeon_civ_cooldown_hours=72,
            pigeon_question_cooldown_hours=1,
            pigeon_dm_cooldown_hours=1,
        ),
    )
    return voliere_engine.VoliereService(
        _Store(), config, stack_kingdoms, object(), object()
    )


@pytest.mark.asyncio
async def test_the_beta_compression_squeezes_every_delay_to_five_minutes() -> None:
    thief = _kingdom("Francs", bank=0)
    target = _kingdom("Omeyyades", bank=3)
    service = _service([thief, target])
    assert service._cooldown_seconds("corbeau_civ", True) == 300
    assert service._cooldown_seconds("corbeau_civ", False) == 72 * 3600
    theft = await service.send_corbeau_theft("id-Francs", "id-Omeyyades", "lord-1", now=_NOW)
    assert theft["state"] == "pending"
    assert int(theft["execute_at"]) - int(_NOW.timestamp()) == 300, "the theft executes in 5 min"
    # the tracking window and the faucon immunity compress too
    assert thief.tech_points_bank == 0


@pytest.mark.asyncio
async def test_the_theft_machine_contest_kills_the_corbeau_and_refunds() -> None:
    thief = _kingdom("Francs", bank=0)
    target = _kingdom("Omeyyades", bank=3)
    service = _service([thief, target])
    theft = await service.send_corbeau_theft("id-Francs", "id-Omeyyades", "lord-1", now=_NOW)
    # 1) the execution tick steals the 1st ⚙️ and opens the windows
    executed = await service.resolve_due_thefts(now=_NOW + timedelta(minutes=6))
    assert len(executed) == 1 and executed[0]["state"] == "awaiting_continue"
    assert executed[0]["stolen"] == 1
    assert thief.tech_points_bank == 1 and target.tech_points_bank == 2
    # 2) the robbed kingdom CONTESTS inside the window → dead + refund
    result = await service.contest_theft(
        str(theft["id"]), "id-Omeyyades", now=_NOW + timedelta(minutes=7)
    )
    assert result["state"] == "dead" and result["refunded"] == 1
    assert thief.tech_points_bank == 0 and target.tech_points_bank == 3
    assert "corbeau" not in (thief.voliere_slots or []), "the slot is lost (voliere-v2 rule)"


@pytest.mark.asyncio
async def test_the_theft_machine_continue_risks_the_second_point() -> None:
    thief = _kingdom("Francs", bank=0)
    target = _kingdom("Omeyyades", bank=3)
    service = _service([thief, target])
    theft = await service.send_corbeau_theft("id-Francs", "id-Omeyyades", "lord-1", now=_NOW)
    await service.resolve_due_thefts(now=_NOW + timedelta(minutes=6))
    # 1) the thief goes for the 2nd ⚙️ (the point moves NOW)
    result = await service.continue_theft(
        str(theft["id"]), "id-Francs", True, now=_NOW + timedelta(minutes=7)
    )
    assert result["state"] == "continuing" and result["stolen"] == 2
    assert thief.tech_points_bank == 2 and target.tech_points_bank == 1
    # 2) nobody contests → the window's close settles BOTH
    await service.resolve_due_thefts(now=_NOW + timedelta(minutes=12))
    assert str(thief.corbeau_theft.get("state")) == "settled_both"
    assert "corbeau" in (thief.voliere_slots or []), "no contest → the slot survives"


@pytest.mark.asyncio
async def test_the_theft_machine_settles_safe_without_an_answer() -> None:
    thief = _kingdom("Francs", bank=0)
    target = _kingdom("Omeyyades", bank=3)
    service = _service([thief, target])
    await service.send_corbeau_theft("id-Francs", "id-Omeyyades", "lord-1", now=_NOW)
    await service.resolve_due_thefts(now=_NOW + timedelta(minutes=6))
    await service.resolve_due_thefts(now=_NOW + timedelta(minutes=12))
    assert str(thief.corbeau_theft.get("state")) == "settled_first"
    assert thief.tech_points_bank == 1, "no answer = automatic safe return with the 1st ⚙️"


def test_the_voliere_and_tavern_surfaces_are_declared() -> None:
    """The volière window + the taverne enter window live in views.yaml."""
    from botforge.discord.ui.view_footer import require_declared_view_id

    for view_id in (
        "panel:mod:kingdom:lieux:voliere",
        "panel:mod:kingdom:tavern:pin",
        "panel:mod:kingdom:tavern:enter",
        "panel:mod:kingdom:mercenary",
    ):
        require_declared_view_id(view_id)


def test_the_tavern_art_resolver_serves_the_reference_urls() -> None:
    from botforge.mods.kingdom.cogs.kingdom.tavern_art import taverne_art_item

    item = taverne_art_item("comptoir")
    assert item is not None and "assets/taverne" in str(item.url)
    assert taverne_art_item("entree") is not None
    assert taverne_art_item("mercenaire") is not None
