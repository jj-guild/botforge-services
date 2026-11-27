"""self-manage-channels-v1 (Drasah 27/11) — the mod stays master of
the channels it creates.

Drasah's live finding (affaire 49): the battle-room voice channels
and the attack salons carried a @me allow WITHOUT manage_channels,
while the realm categories carried it — a broken inheritance chain
(pre-migration ghosts) then left the bot 403-locked out of closing
its own rooms forever. The rule: EVERY channel the mod creates (or
adopts) carries the bot's own manage_channels allow, and the sweep
heals a healable ghost before skipping it.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest


def test_battle_room_overwrites_carry_manage_channels() -> None:
    """The vocal battle room's @me allow includes manage_channels."""

    from botforge.mods.kingdom.cogs.battle import _battle_room_overwrites

    ow = _battle_room_overwrites("⚔️ bataille")
    me = ow["@me"]
    assert me["manage_channels"] is True, "the room the bot opens must stay the bot's to close"
    assert me["connect"] is True and me["view_channel"] is True


def test_salon_overwrites_carry_manage_channels() -> None:
    """The attack salon + FFA @me allows include manage_channels."""

    from botforge.mods.kingdom.cogs.common import FFA_SALON_OVERWRITES, SALON_OVERWRITES

    assert SALON_OVERWRITES["@me"]["manage_channels"] is True
    assert FFA_SALON_OVERWRITES["@me"]["manage_channels"] is True


class _HealableChannel:
    """A ghost the bot may heal: unmanageable until set_permissions runs."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.healed = False
        self.set_calls: list[tuple[Any, Any]] = []

    def permissions_for(self, member: Any) -> Any:
        return SimpleNamespace(manage_channels=self.healed)

    def overwrites_for(self, member: Any) -> Any:
        return SimpleNamespace(view_channel=True, connect=True)

    async def set_permissions(self, target: Any, overwrite: Any = None, **kwargs: Any) -> None:
        self.set_calls.append((target, overwrite))
        self.healed = bool(getattr(overwrite, "manage_channels", False))

    async def delete(self) -> None:
        self.healed = "deleted"


def _guild(channel: _HealableChannel, guild_grant: bool) -> Any:
    me = SimpleNamespace(
        guild_permissions=SimpleNamespace(manage_channels=guild_grant),
        top_role=SimpleNamespace(position=2),
    )

    class _Guild:
        pass

    g = _Guild()
    g.me = me
    g.get_channel = lambda _id: channel  # type: ignore[attr-defined]
    g.get_role = lambda _id: None  # type: ignore[attr-defined]
    return g


@pytest.mark.asyncio
async def test_the_sweep_heals_then_deletes_a_healable_ghost() -> None:
    """Guild-level grant + broken channel chain → heal, then SAME-pass delete."""

    from botforge.mods.kingdom.cogs import battle

    ghost = _HealableChannel("⚔️ blank-vs-drasah")
    guild = _guild(ghost, guild_grant=True)
    attack = SimpleNamespace(
        score={"attack_channel_id": 0, "room_channel_id": 7, "room_role_id": 0},
        map_key="pataugeoire",
    )
    swept = await battle._sweep_recorded_refs_safe(SimpleNamespace(guilds=[guild]), [attack])
    assert swept == 1, "the healed ghost is deleted on the same pass"
    assert ghost.healed == "deleted"
    assert len(ghost.set_calls) == 1, "exactly ONE heal write (converging, no storm)"
    target, overwrite = ghost.set_calls[0]
    assert overwrite.manage_channels is True


@pytest.mark.asyncio
async def test_no_heal_without_the_guild_level_grant() -> None:
    """No server-level manage_channels → no write, silent skip (affaire-27)."""

    from botforge.mods.kingdom.cogs import battle

    ghost = _HealableChannel("⚔️ blank-vs-drasah")
    guild = _guild(ghost, guild_grant=False)
    attack = SimpleNamespace(
        score={"attack_channel_id": 0, "room_channel_id": 7, "room_role_id": 0},
        map_key="pataugeoire",
    )
    swept = await battle._sweep_recorded_refs_safe(SimpleNamespace(guilds=[guild]), [attack])
    assert swept == 0
    assert ghost.set_calls == [], "the bot writes nothing it could not apply"


@pytest.mark.asyncio
async def test_no_heal_when_already_master_of_the_channel() -> None:
    """An already-manageable channel is never rewritten (zero steady-state cost)."""

    from botforge.mods.kingdom.cogs import battle

    ghost = _HealableChannel("⚔️ fine")
    ghost.healed = True
    guild = _guild(ghost, guild_grant=True)
    attack = SimpleNamespace(
        score={"attack_channel_id": 0, "room_channel_id": 7, "room_role_id": 0},
        map_key="pataugeoire",
    )
    swept = await battle._sweep_recorded_refs_safe(SimpleNamespace(guilds=[guild]), [attack])
    assert swept == 1
    assert ghost.set_calls == [], "converged channels cost zero writes"
