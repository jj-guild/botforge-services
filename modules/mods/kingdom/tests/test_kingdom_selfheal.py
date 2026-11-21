"""The boot self-heal (epic #412) — pins + command visibility per guild.

R6 discipline (tests/architecture/test_layering.py): a file under
modules/ OUTSIDE cogs/ never imports discord. The seams are patched
through importlib (no ``from botforge...`` line) and the discord
namespace of the module under test is reused where needed.
"""

from __future__ import annotations

import asyncio
import importlib
from types import SimpleNamespace


def _selfheal():
    from botforge.mods.kingdom.cogs import selfheal

    return selfheal


def _scope_pins():
    return importlib.import_module("botforge.discord.scope_pins")


class _Tree:
    def __init__(self, *, has_kingdom: bool = True, broken_fetch: bool = False) -> None:
        self.has_kingdom = has_kingdom
        self.broken_fetch = broken_fetch
        self.synced: list[int] = []

    async def fetch_commands(self, guild):
        if self.broken_fetch:
            raise RuntimeError("fetch down")
        names = ["kingdom"] if self.has_kingdom else ["other"]
        return [SimpleNamespace(name=n) for n in names]

    def copy_global_to(self, guild) -> None:
        self.copied_to = getattr(guild, "id", None)

    async def sync(self, guild) -> None:
        self.synced.append(getattr(guild, "id", None))


def test_the_pass_ensures_pins_and_reports_per_guild(monkeypatch) -> None:
    """One summary line per guild, pins through the public repair seam."""
    selfheal = _selfheal()
    calls: list[tuple[str, str]] = []

    async def fake_ensure_mod_pins(bot, guild_id, name):
        calls.append((guild_id, name))
        return 4

    monkeypatch.setattr(_scope_pins(), "ensure_mod_pins", fake_ensure_mod_pins)
    # the pins-only pass (the provisioning lives in its own tests below)
    monkeypatch.setenv("BOTFORGE_KINGDOM_BOOT_PROVISION", "off")
    bot = SimpleNamespace(
        guilds=[SimpleNamespace(id=111), SimpleNamespace(id=222)],
        tree=_Tree(has_kingdom=True),
    )
    out = asyncio.run(selfheal.ensure_kingdom_surfaces(bot))
    assert calls == [("111", "kingdom"), ("222", "kingdom")]
    assert len(out) == 2
    assert out[0] == ("111", "provisioning: off; 4 pins, commands: already there")


def test_the_pass_never_raises(monkeypatch) -> None:
    """A broken pin seam becomes an error summary, not a boot crash."""
    selfheal = _selfheal()

    async def boom(bot, guild_id, name):
        raise TypeError("seam down")

    monkeypatch.setattr(_scope_pins(), "ensure_mod_pins", boom)
    monkeypatch.setenv("BOTFORGE_KINGDOM_BOOT_PROVISION", "off")
    bot = SimpleNamespace(guilds=[SimpleNamespace(id=111)], tree=_Tree())
    out = asyncio.run(selfheal.ensure_kingdom_surfaces(bot))
    assert out == [("111", "provisioning: off; error pins, commands: already there")]


def test_missing_commands_get_synced(monkeypatch) -> None:
    """A guild without the kingdom slash gets the tree copied+synced."""
    selfheal = _selfheal()
    monkeypatch.setenv("BOTFORGE_KINGDOM_BOOT_PROVISION", "off")
    tree = _Tree(has_kingdom=False)
    bot = SimpleNamespace(guilds=[SimpleNamespace(id=111)], tree=tree)
    asyncio.run(selfheal.ensure_kingdom_surfaces(bot))
    assert tree.synced == [111]


def test_a_broken_fetch_still_syncs(monkeypatch) -> None:
    """The fetch is a fast-path only — down fetch degrades to a sync."""
    selfheal = _selfheal()
    monkeypatch.setenv("BOTFORGE_KINGDOM_BOOT_PROVISION", "off")
    tree = _Tree(has_kingdom=True, broken_fetch=True)
    bot = SimpleNamespace(guilds=[SimpleNamespace(id=111)], tree=tree)
    asyncio.run(selfheal.ensure_kingdom_surfaces(bot))
    assert tree.synced == [111]


def test_boot_self_heal_runs_once_per_bot(monkeypatch) -> None:
    """The boot pass runs once per bot process (flag), via the setup_hook task."""
    selfheal = _selfheal()
    monkeypatch.setattr(selfheal, "_DELAY_S", 0)

    runs: list[bool] = []

    async def fake_pass(bot):
        runs.append(True)
        return []

    monkeypatch.setattr(selfheal, "ensure_kingdom_surfaces", fake_pass)
    bot = SimpleNamespace(guilds=[])
    asyncio.run(selfheal.boot_self_heal(bot))
    asyncio.run(selfheal.boot_self_heal(bot))
    assert runs == [True]
    assert getattr(bot, "_kingdom_selfheal_ran", False) is True


def test_the_pass_provisions_the_declared_salons_before_pinning(monkeypatch) -> None:
    """admin-category-v1 (Drasah 20/11): the boot pass BRINGS the declared
    salons into existence (the Repair-click seams) before the pins —
    a guild that never received a provisioning gets its ⚙️ paramètres
    salon without a manual click."""
    selfheal = _selfheal()
    order: list[str] = []

    async def fake_roles(bot, guild_id, name):
        order.append(f"roles:{guild_id}")
        return 2

    async def fake_channels(bot, guild_id, name):
        order.append(f"channels:{guild_id}")
        return 3

    async def fake_pins(bot, guild_id, name):
        order.append(f"pins:{guild_id}")
        return 5

    mods_forum = importlib.import_module("botforge.discord.mods_forum")
    monkeypatch.setattr(selfheal, "_boot_provision_enabled", lambda: True)
    monkeypatch.setattr(mods_forum, "provision_mod_roles", fake_roles)
    monkeypatch.setattr(mods_forum, "provision_mod_channels", fake_channels)
    monkeypatch.setattr(_scope_pins(), "ensure_mod_pins", fake_pins)
    bot = SimpleNamespace(guilds=[SimpleNamespace(id=42)], tree=_Tree(has_kingdom=True))
    out = asyncio.run(selfheal.ensure_kingdom_surfaces(bot))
    # roles first (the channels' policies resolve them), then channels,
    # then the pins (in existing salons), per guild
    assert order == ["roles:42", "channels:42", "pins:42"]
    assert out == [("42", "provisioning: 3 channels, 2 roles; 5 pins, commands: already there")]


def test_the_pass_provisioning_obeys_the_kill_switch(monkeypatch) -> None:
    """`BOTFORGE_KINGDOM_BOOT_PROVISION=off` skips the provisioning (the
    pins/commands passes stay) — the guild report says « off »."""
    selfheal = _selfheal()

    async def fail_roles(bot, guild_id, name):  # pragma: no cover — must not run
        raise AssertionError("the kill switch must skip provisioning")

    mods_forum = importlib.import_module("botforge.discord.mods_forum")
    monkeypatch.setattr(mods_forum, "provision_mod_roles", fail_roles)
    monkeypatch.setenv("BOTFORGE_KINGDOM_BOOT_PROVISION", "off")
    seen: list[str] = []

    async def fake_pins(bot, guild_id, name):
        seen.append(guild_id)
        return 2

    monkeypatch.setattr(_scope_pins(), "ensure_mod_pins", fake_pins)
    bot = SimpleNamespace(guilds=[SimpleNamespace(id=7)], tree=_Tree(has_kingdom=True))
    out = asyncio.run(selfheal.ensure_kingdom_surfaces(bot))
    assert seen == ["7"], "the pins pass runs WITHOUT provisioning"
    assert out[0][1].startswith("provisioning: off;")


def test_the_kill_switch_reads_the_env() -> None:
    """The switch: default on; off/0/false/no disable."""
    selfheal = _selfheal()
    import os

    for value, expected in (
        (None, True),
        ("on", True),
        ("OFF", False),
        ("0", False),
        ("false", False),
        ("no", False),
    ):
        if value is None:
            os.environ.pop("BOTFORGE_KINGDOM_BOOT_PROVISION", None)
        else:
            os.environ["BOTFORGE_KINGDOM_BOOT_PROVISION"] = value
        assert selfheal._boot_provision_enabled() is expected, value
    os.environ.pop("BOTFORGE_KINGDOM_BOOT_PROVISION", None)
