"""saisons-roles-v1 — the season's King/Lord roles converge (the tests).

L'incident Blanc : la saison était ENGAGÉE mais personne ne portait les
rôles qui ouvrent Kingdom-Gaïa et les champs de bataille. La convergence
relit la saison (les royaumes engagés : le Roi, ses membres), pose les
manquants, retire les en trop, ne touche RIEN d'autre — et la fin de
saison (plus d'engagement) vide les rangs toute seule.
"""

from __future__ import annotations

import asyncio
import importlib
from types import SimpleNamespace
from typing import Any

import pytest


def _sync():
    return importlib.import_module("botforge.mods.kingdom.cogs.season_roles_sync")


class _FakeRole:
    def __init__(self, rid: int, name: str) -> None:
        self.id = rid
        self.name = name
        self.members: list[_FakeMember] = []


class _FakeMember:
    def __init__(self, mid: int, guild: _FakeGuild) -> None:
        self.id = mid
        self.guild = guild
        self.granted: list[int] = []
        self.revoked: list[int] = []

    async def add_roles(self, role: Any, **kwargs: Any) -> None:
        self.granted.append(role.id)
        if role not in role.members:
            role.members.append(self)

    async def remove_roles(self, role: Any, **kwargs: Any) -> None:
        self.revoked.append(role.id)
        if self in role.members:
            role.members.remove(self)


class _FakeGuild:
    def __init__(self) -> None:
        self.id = 1
        self.members: dict[int, _FakeMember] = {}
        king_role = _FakeRole(10, "Kingdom King")
        lord_role = _FakeRole(20, "Kingdom Lord")
        self.roles = {10: king_role, 20: lord_role}

    def get_role(self, rid: int) -> _FakeRole | None:
        return self.roles.get(rid)

    def get_member(self, mid: int) -> _FakeMember | None:
        return self.members.get(mid)

    def member(self, mid: int) -> _FakeMember:
        if mid not in self.members:
            self.members[mid] = _FakeMember(mid, self)
        return self.members[mid]


class _RolesService:
    def __init__(self) -> None:
        self.mapping: dict[tuple[str, str], int] = {}

    async def resolve_role_id(self, gid: str, mod: str, role_key: str) -> str | None:
        rid = self.mapping.get((gid, role_key))
        return str(rid) if rid else None


def _shell(rid: str, king: str, members: list[str], *, engaged: bool = True, archived: int = 0) -> Any:
    return SimpleNamespace(
        id=rid,
        name=f"Realm {rid}",
        king_id=king,
        member_ids=list(members),
        engagement={"season_id": "s1", "kingdom_id": "k1"} if engaged else None,
        archived_at=archived,
    )


def _bot(guild: _FakeGuild, shells: list[Any], monkeypatch: pytest.MonkeyPatch) -> Any:
    """Wire the fake stack (the season's own truth) into the sync."""

    async def _realms() -> list[Any]:
        return shells

    stack = SimpleNamespace(realms=SimpleNamespace(realms=_realms))
    roles_service = _RolesService()
    roles_service.mapping[("1", "kingdom_king")] = 10
    roles_service.mapping[("1", "kingdom_lord")] = 20
    bot = SimpleNamespace(
        guilds=[guild],
        get_guild=lambda gid: guild if str(gid) == str(guild.id) else None,
        mod_roles_service=roles_service,
    )
    monkeypatch.setattr(_sync(), "wiring", lambda: stack)
    return bot


async def _pass(monkeypatch: pytest.MonkeyPatch, guild: _FakeGuild | None = None,
                shells: list[Any] | None = None) -> tuple[int, _FakeGuild]:
    sync = _sync()
    guild = guild or _FakeGuild()
    bot = _bot(guild, shells or [], monkeypatch)
    moved = await sync.sync_season_roles(bot)
    return moved, guild


def test_the_engaged_season_hands_the_crown_and_the_lords_ranks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Blanc en saison : le Roi reçoit King, ses membres Lord."""
    guild = _FakeGuild()
    king = guild.member(31)
    lord_a = guild.member(32)
    lord_b = guild.member(33)
    moved, _ = asyncio.run(_pass(monkeypatch, guild, [_shell("1", "31", ["32", "33"])]))
    assert king.granted == [10], "the King wears the crown"
    assert lord_a.granted == [20] and lord_b.granted == [20], "the members follow as Lords"
    assert moved == 3


def test_king_wins_never_both(monkeypatch: pytest.MonkeyPatch) -> None:
    """A king who is also a member keeps the highest rank, never both."""
    guild = _FakeGuild()
    king = guild.member(31)
    _, _ = asyncio.run(_pass(monkeypatch, guild, [_shell("1", "31", ["31", "32"])]))
    assert king.granted == [10], "the crown only"
    assert 20 not in king.granted, "never both ranks"


def test_dormant_or_archived_realms_grant_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hors saison : pas d'engagement, pas de rang."""
    guild = _FakeGuild()
    guild.member(31)
    moved, _ = asyncio.run(
        _pass(
            monkeypatch,
            guild,
            [
                _shell("1", "31", ["32"], engaged=False),
                _shell("2", "41", ["42"], archived=99),
            ],
        )
    )
    assert moved == 0, "no engaged realm, no rank"


def test_the_season_moving_on_empties_the_ranks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fin de saison : l'état attendu est vide, les rôles partent."""
    guild = _FakeGuild()
    king = guild.member(31)
    lord = guild.member(32)
    _, _ = asyncio.run(_pass(monkeypatch, guild, [_shell("1", "31", ["32"])]))
    moved, _ = asyncio.run(_pass(monkeypatch, guild, []))
    assert king.revoked == [10] and lord.revoked == [20], "back to the original state"
    assert moved == 2


def test_a_stray_holder_loses_the_mod_rank_and_nothing_else(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sync stricte : un rôle porté en trop part, seul le rôle du mod."""
    guild = _FakeGuild()
    king = guild.member(31)
    stray = guild.member(77)
    guild.roles[10].members.append(stray)
    moved, _ = asyncio.run(_pass(monkeypatch, guild, [_shell("1", "31", [])]))
    assert stray.revoked == [10], "the stray holder loses the crown"
    assert king.granted == [10], "the King keeps the crown"
    assert moved == 2  # grant + revoke


def test_a_converged_guild_costs_zero_discord_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Convergé : zéro grant, zéro revoke (la leçon 429)."""
    guild = _FakeGuild()
    king = guild.member(31)
    guild.roles[10].members.append(king)
    moved, _ = asyncio.run(_pass(monkeypatch, guild, [_shell("1", "31", [])]))
    assert moved == 0
    assert king.granted == [] and king.revoked == []


def test_an_unresolvable_target_logs_and_moves_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un membre hors serveur : loggé fort, jamais un crash."""
    guild = _FakeGuild()
    guild.member(31)  # le Roi vit ici, le fantôme 999 n'y vit pas
    moved, _ = asyncio.run(_pass(monkeypatch, guild, [_shell("1", "31", ["999"])]))
    assert moved == 1, "the King landed, the ghost skipped"


def test_the_boot_pass_owns_the_ranks_too(monkeypatch: pytest.MonkeyPatch) -> None:
    """selfheal : la passe de boot resserre les rangs (gated provision)."""
    selfheal = importlib.import_module("botforge.mods.kingdom.cogs.selfheal")
    seen: list[Any] = []

    async def fake_sync(bot: Any, guild_id: str = "") -> int:
        seen.append(bot)
        return 0

    monkeypatch.setattr(_sync(), "sync_season_roles", fake_sync)
    import botforge.discord.scope_pins as scope_pins

    async def fake_pins(bot: Any, guild_id: str, name: str) -> int:
        return 4

    monkeypatch.setattr(scope_pins, "ensure_mod_pins", fake_pins)
    monkeypatch.setenv("BOTFORGE_KINGDOM_BOOT_PROVISION", "on")
    import botforge.discord.mods_forum as mods_forum

    async def fake_channels(bot: Any, guild_id: str, name: str) -> int:
        return 0

    async def fake_roles(bot: Any, guild_id: str, name: str) -> int:
        return 0

    monkeypatch.setattr(mods_forum, "provision_mod_channels", fake_channels)
    monkeypatch.setattr(mods_forum, "provision_mod_roles", fake_roles)
    bot = SimpleNamespace(
        guilds=[SimpleNamespace(id=111, categories=None, tree=SimpleNamespace())],
        tree=None,
    )
    asyncio.run(selfheal.ensure_kingdom_surfaces(bot))
    assert seen, "the boot pass converges the season ranks"
