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
    from botforge.mods.kingdom.cogs.kingdom import selfheal

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
    bot = SimpleNamespace(
        guilds=[SimpleNamespace(id=111), SimpleNamespace(id=222)],
        tree=_Tree(has_kingdom=True),
    )
    out = asyncio.run(selfheal.ensure_kingdom_surfaces(bot))
    assert calls == [("111", "kingdom"), ("222", "kingdom")]
    assert len(out) == 2
    assert out[0] == ("111", "4 pins, commands: already there")


def test_the_pass_never_raises(monkeypatch) -> None:
    """A broken pin seam becomes an error summary, not a boot crash."""
    selfheal = _selfheal()

    async def boom(bot, guild_id, name):
        raise TypeError("seam down")

    monkeypatch.setattr(_scope_pins(), "ensure_mod_pins", boom)
    bot = SimpleNamespace(guilds=[SimpleNamespace(id=111)], tree=_Tree())
    out = asyncio.run(selfheal.ensure_kingdom_surfaces(bot))
    assert out == [("111", "error pins, commands: already there")]


def test_missing_commands_get_synced() -> None:
    """A guild without the kingdom slash gets the tree copied+synced."""
    selfheal = _selfheal()
    tree = _Tree(has_kingdom=False)
    bot = SimpleNamespace(guilds=[SimpleNamespace(id=111)], tree=tree)
    asyncio.run(selfheal.ensure_kingdom_surfaces(bot))
    assert tree.synced == [111]


def test_a_broken_fetch_still_syncs() -> None:
    """The fetch is a fast-path only — down fetch degrades to a sync."""
    selfheal = _selfheal()
    tree = _Tree(has_kingdom=True, broken_fetch=True)
    bot = SimpleNamespace(guilds=[SimpleNamespace(id=111)], tree=tree)
    asyncio.run(selfheal.ensure_kingdom_surfaces(bot))
    assert tree.synced == [111]


def test_arm_boot_self_heal_is_idempotent(monkeypatch) -> None:
    """Arming twice schedules ONE pass, and the pass runs once per bot."""
    selfheal = _selfheal()
    monkeypatch.setattr(selfheal, "_DELAY_S", 0)

    runs: list[bool] = []

    async def fake_pass(bot):
        runs.append(True)
        return []

    monkeypatch.setattr(selfheal, "ensure_kingdom_surfaces", fake_pass)
    listeners: list[tuple[object, str]] = []
    bot = SimpleNamespace(guilds=[], tree=None, add_listener=lambda fn, name: listeners.append((fn, name)))
    selfheal.arm_boot_self_heal(bot)
    selfheal.arm_boot_self_heal(bot)
    assert len(listeners) == 1
    (run_once, name) = listeners[0]
    assert name == "on_ready"

    # First ready dispatch runs the pass; a reconnect (second dispatch) is a no-op.
    asyncio.run(run_once())
    asyncio.run(run_once())
    assert runs == [True]
    assert getattr(bot, "_kingdom_selfheal_ran", False) is True
