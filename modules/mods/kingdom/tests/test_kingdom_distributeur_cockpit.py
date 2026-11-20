"""distributeur-v2 (Drasah 20/11) — the admin levers' seam tests.

The reference's injector cockpit rides SERVICE seams: the face only
reads and calls. These tests pin the engine side down (the levers
actually move the data through the store), using the same in-memory
bundle as the attack suite.
"""

from __future__ import annotations

import pytest

from botforge.mods.kingdom.attacks import UnknownTechnologyError
from botforge.mods.kingdom.models import LordRole
from botforge.mods.kingdom.service import KingdomNotFoundError, ParishError

from test_kingdom_attacks import Bundle


async def test_force_parish_tier_moves_the_palier_without_paying() -> None:
    """The Paroisse lever writes the palier, the treasury never moves."""
    bundle = Bundle()
    await bundle.kingdoms.launch()
    await bundle.kingdoms.enroll("king-a", "King A", LordRole.KING, proposed_name="Aquitaine")
    before = next(k for k in await bundle.kingdoms.kingdoms() if k.name == "Aquitaine")

    forced = await bundle.kingdoms.force_parish_tier(before.id, 3)
    assert forced.parish_tier == 3
    assert forced.tech_points_bank == before.tech_points_bank  # the lever pays nothing

    reread = next(k for k in await bundle.kingdoms.kingdoms() if k.name == "Aquitaine")
    assert reread.parish_tier == 3
    # the dial turns both ways, and an unknown palier is refused
    assert (await bundle.kingdoms.force_parish_tier(before.id, 1)).parish_tier == 1
    with pytest.raises(ParishError):
        await bundle.kingdoms.force_parish_tier(before.id, 7)


async def test_set_lord_budgets_recharges_and_locks_out() -> None:
    """0/0 recharges the weekly budgets; the max locks the lord out."""
    bundle = Bundle()
    await bundle.launch_season()
    lord = next(item for item in await bundle.kingdoms.lords() if item.id == "lord-a")
    lord.attack_used = 1
    lord.defense_used = 1
    await bundle.store.upsert_lord(lord.to_mongo())

    recharged = await bundle.kingdoms.set_lord_budgets("lord-a", 0, 0)
    assert (recharged.attack_used, recharged.defense_used) == (0, 0)
    locked = await bundle.kingdoms.set_lord_budgets("lord-a", 1, 1)
    assert (locked.attack_used, locked.defense_used) == (1, 1)

    with pytest.raises(KingdomNotFoundError):
        await bundle.kingdoms.set_lord_budgets("nobody", 0, 0)


async def test_set_lord_marriage_lock_sets_and_lifts() -> None:
    """The marriage test lock sets a timestamp and None lifts it."""
    bundle = Bundle()
    await bundle.launch_season()

    locked = await bundle.kingdoms.set_lord_marriage_lock("lord-a", 1737600000)
    assert locked.marriage_locked_until == 1737600000
    lifted = await bundle.kingdoms.set_lord_marriage_lock("lord-a", None)
    assert lifted.marriage_locked_until is None


async def test_grant_and_revoke_technology_for_free() -> None:
    """The Tech +/- moves the purchase counter, the points never move."""
    bundle = Bundle()
    aquitaine, _bourgogne, _gaia = await bundle.launch_season()
    before = next(k for k in await bundle.kingdoms.kingdoms() if k.id == aquitaine)

    state = await bundle.attacks.grant_technology(aquitaine, "embuscade")
    assert state.purchases["embuscade"] == 1
    assert (await bundle.attacks.grant_technology(aquitaine, "embuscade")).purchases["embuscade"] == 2
    assert (await bundle.attacks.revoke_technology(aquitaine, "embuscade")).purchases["embuscade"] == 1
    assert (await bundle.attacks.revoke_technology(aquitaine, "embuscade")).purchases["embuscade"] == 0
    # floored at zero, never negative
    assert (await bundle.attacks.revoke_technology(aquitaine, "embuscade")).purchases["embuscade"] == 0
    # the treasury never moved (the grant pays nothing)
    after = next(k for k in await bundle.kingdoms.kingdoms() if k.id == aquitaine)
    assert after.tech_points_bank == before.tech_points_bank
    # an unknown technology is refused
    with pytest.raises(UnknownTechnologyError):
        await bundle.attacks.grant_technology(aquitaine, "not_a_tech")


async def test_shield_unshield_retire_and_replace_territories() -> None:
    """The Territoires levers: shield (no cost), unshield, retire (out), eject."""
    bundle = Bundle()
    aquitaine, _bourgogne, _gaia = await bundle.launch_season()
    await bundle.draw(21)
    maps = await bundle.owner_maps(aquitaine)

    shielded = await bundle.territories.shield_territory(maps[0], 48)
    assert shielded.protected_until is not None
    unshielded = await bundle.territories.unshield_territory(maps[0])
    assert unshielded.protected_until is None

    # Retire: the territory disappears and the map is out for the season.
    retired = await bundle.territories.retire_territory(maps[1])
    assert retired.map_key == maps[1]
    assert maps[1] not in await bundle.owner_maps(aquitaine)
    season = await bundle.kingdoms.current_season()
    assert season is not None
    assert maps[1] in season.out_maps

    # Eject: the drawn map is REPLACED by a fresh one for the same owner.
    replacement = await bundle.territories.eject(maps[2])
    assert replacement.map_key != maps[2]
    assert replacement.owner_kingdom_id == aquitaine
    assert maps[2] not in await bundle.owner_maps(aquitaine)
    assert replacement.map_key in await bundle.owner_maps(aquitaine)
