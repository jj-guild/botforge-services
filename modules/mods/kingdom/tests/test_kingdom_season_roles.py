"""liaison-roless-saison-v1 — the season's Discord roles (Drasah 24/11).

The live incident : Blanc ENGAGED in season saw neither the battlefields
nor Kingdom-Gaïa — the salons unlock through « Kingdom King » /
« Kingdom Lord » (declared view roles) and NOTHING granted them. The
sync reads the engaged realms, hands the King his crown, the members
their sword, and collects the orphans — converged, zero API call.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import botforge.mods.kingdom.cogs.season_roles as sr
import pytest


class _Role:
    def __init__(self, role_id: str) -> None:
        self.id = role_id


class _Member:
    def __init__(self, uid: str, roles: list[str]) -> None:
        self.id = uid
        self.uid = uid
        self.roles = [_Role(r) for r in roles]


class _Guild:
    def __init__(self, members: list[_Member]) -> None:
        self.id = 42
        self._members = {m.uid: m for m in members}
        self.members = members

    def get_member(self, mid: int) -> _Member | None:
        return self._members.get(str(mid))


class _RolesService:
    def __init__(self, ids: dict[str, str] | None = None) -> None:
        self.ids = ids if ids is not None else {"kingdom_king": "10", "kingdom_lord": "11"}
        self.calls: list[tuple[str, str, str]] = []

    async def resolve_role_id(self, guild_id: str, mod: str, role_key: str) -> str | None:
        del guild_id, mod
        return self.ids.get(role_key)

    async def assign_platform_role(
        self, guild_id: str, user_id: str, role_id: str, mod: str, role_key: str
    ) -> None:
        del guild_id, mod
        self.calls.append(("grant", user_id, role_key))

    async def remove_platform_role(
        self, guild_id: str, user_id: str, role_id: str, mod: str, role_key: str
    ) -> None:
        del guild_id, mod, role_key
        self.calls.append(("revoke", user_id, f"id:{role_id}"))


def _realms(*realms: Any) -> Any:
    async def _list() -> list[Any]:
        return list(realms)

    return SimpleNamespace(realms=SimpleNamespace(realms=_list))


def _engaged(king: str, members: list[str]) -> Any:
    return SimpleNamespace(
        id="r1", king_id=king, member_ids=members, engagement={"kingdom_id": "k"}, archived_at=0
    )


def test_the_engaged_realm_gets_the_crown_and_the_swords(monkeypatch: pytest.MonkeyPatch) -> None:
    """The ✅ realm : Roi → King, membres → Lord, one pass."""
    king_only = _engaged("1", ["2", "3"])
    monkeypatch.setattr(sr, "wiring", lambda: _realms(king_only))
    guild = _Guild([_Member("1", []), _Member("2", []), _Member("3", [])])
    service = _RolesService()
    moved = asyncio.run(sr.sync_season_roles(SimpleNamespace(mod_roles_service=service), guild))
    assert sorted(service.calls) == [
        ("grant", "1", "kingdom_king"),
        ("grant", "2", "kingdom_lord"),
        ("grant", "3", "kingdom_lord"),
    ], "the engaged realm's members all receive their role"
    assert moved == 3


def test_a_converged_guild_costs_zero_discord_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Idempotent : a guild already wearing its roles makes no gesture."""
    realm = _engaged("1", ["2"])
    monkeypatch.setattr(sr, "wiring", lambda: _realms(realm))
    guild = _Guild([_Member("1", ["10"]), _Member("2", ["11"])])
    service = _RolesService()
    moved = asyncio.run(sr.sync_season_roles(SimpleNamespace(mod_roles_service=service), guild))
    assert moved == 0 and service.calls == [], "converged costs zero API call"


def test_the_dormant_and_archived_realms_never_hand_roles(monkeypatch: pytest.MonkeyPatch) -> None:
    """The ✅ rule : engagement set, not archived — otherwise nothing."""
    dormant = SimpleNamespace(
        id="r2", king_id="7", member_ids=["8"], engagement=None, archived_at=0
    )
    archived = SimpleNamespace(
        id="r3", king_id="9", member_ids=[], engagement={"kingdom_id": "k"}, archived_at=123
    )
    monkeypatch.setattr(sr, "wiring", lambda: _realms(dormant, archived))
    guild = _Guild([_Member("7", []), _Member("8", []), _Member("9", [])])
    service = _RolesService()
    moved = asyncio.run(sr.sync_season_roles(SimpleNamespace(mod_roles_service=service), guild))
    assert moved == 0 and service.calls == [], "no engagement, no crown"


def test_the_ejected_members_lose_the_roles_in_the_cycle(monkeypatch: pytest.MonkeyPatch) -> None:
    """Drasah's rule : an orphan carrier (ejected, archived) is revoked."""
    monkeypatch.setattr(sr, "wiring", lambda: _realms())
    orphan_king = _Member("1", ["10"])
    orphan_lord = _Member("2", ["11"])
    guild = _Guild([orphan_king, orphan_lord])
    service = _RolesService()
    moved = asyncio.run(sr.sync_season_roles(SimpleNamespace(mod_roles_service=service), guild))
    assert sorted(service.calls) == [
        ("revoke", "1", "id:10"),
        ("revoke", "2", "id:11"),
    ], "no engaged realm ⇒ the carriers go home"
    assert moved == 2


def test_the_wrong_role_is_collected_and_the_right_one_handed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A stale crown leaves, the sword arrives (the convergence recomputes)."""
    realm = _engaged("1", ["2"])
    monkeypatch.setattr(sr, "wiring", lambda: _realms(realm))
    # the king wears the LORD role (stale), the lord wears nothing
    guild = _Guild([_Member("1", ["11"]), _Member("2", [])])
    service = _RolesService()
    moved = asyncio.run(sr.sync_season_roles(SimpleNamespace(mod_roles_service=service), guild))
    assert ("grant", "1", "kingdom_king") in service.calls
    assert ("grant", "2", "kingdom_lord") in service.calls
    assert ("revoke", "1", "id:11") in service.calls, "the wrong role is collected"
    assert moved == 3


def test_unresolved_roles_mean_a_silent_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unmapped roles : the pass degrades quietly (the roles wait)."""
    realm = _engaged("1", ["2"])
    monkeypatch.setattr(sr, "wiring", lambda: _realms(realm))
    guild = _Guild([_Member("1", ["10"]), _Member("2", [])])
    service = _RolesService(ids={})
    moved = asyncio.run(sr.sync_season_roles(SimpleNamespace(mod_roles_service=service), guild))
    assert moved == 0 and service.calls == [], "no resolution, no gesture — never a raise"


def test_an_unresolvable_member_skips_loudly_never_breaks(monkeypatch: pytest.MonkeyPatch) -> None:
    """The 2026-10-18 lesson : an unresolvable member logs and waits."""
    realm = _engaged("1", ["2"])
    monkeypatch.setattr(sr, "wiring", lambda: _realms(realm))
    guild = _Guild([_Member("1", [])])  # member 2 is not on this guild
    service = _RolesService()
    moved = asyncio.run(sr.sync_season_roles(SimpleNamespace(mod_roles_service=service), guild))
    assert sorted(service.calls) == [("grant", "1", "kingdom_king")]
    assert moved == 1
