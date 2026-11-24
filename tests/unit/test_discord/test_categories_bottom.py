"""category-bottom for the mods' own folders — the tests (Drasah 20/11).

The designer's capture: the 👑 Kingdom home folder and the mod's ADMIN
machine room sit in the sidebar's MIDDLE — the one-shot move at
provisioning time drifted away (every category created later lands
below them) and the 5-min heal pass never saw them: it only knew the
platform scopes, never the mods' declared homes and groups. Now the
declaration is data end to end (``home_bottom``, channel_groups
``bottom``) and the heal asserts EVERY declared bottom folder in
DECLARATION order, converge-idempotent (a converged guild costs zero
Discord API calls).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import discord
import pytest

from botforge.discord.ui import panels_provisioning
from botforge.discord.ui.panels import ChannelDecl, ScopeSpec, register_scope


def _fake_category(cid: int, guild: Any) -> discord.CategoryChannel:
    """A CategoryChannel shell — isinstance-true, move() reorders the list.

    A bare subclass of CategoryChannel: the parent's __slots__ keeps the
    isinstance contract (the seam under test), the subclass's own
    __dict__ carries the test's id/move attributes.
    """
    class _CategoryShell(discord.CategoryChannel):
        pass

    category = object.__new__(_CategoryShell)
    category.id = cid  # type: ignore[attr-defined]
    category.guild = guild  # type: ignore[attr-defined]
    moves: list[dict[str, Any]] = []

    async def _move(**kwargs: Any) -> None:
        moves.append(kwargs)
        cats = [c for c in guild.categories if c.id != cid]
        cats.append(category)
        guild.categories = cats

    category.move = _move  # type: ignore[attr-defined]
    category.moves = moves  # type: ignore[attr-defined]
    return category  # type: ignore[return-value]


def _definition(home_bottom: bool, group_bottom: bool) -> Any:
    """A mod definition shell carrying the new flags as parsed data."""
    from botforge.core.services.mod_definition import ChannelCategoryDef, ModDefinition

    return ModDefinition(
        name="kingdom",
        enabled=True,
        seasonal=True,
        home_bottom=home_bottom,
        channel_categories=(
            ChannelCategoryDef(key="console", display_name="⚙️", group="⚙️ ᴀᴅᴍɪɴ", group_bottom=group_bottom),
            ChannelCategoryDef(key="general", display_name="Général", group=""),
        ),
    )




def _guild() -> Any:
    """A guild shell: .id, .categories and get_channel() over them."""
    guild = type("G", (), {})()
    guild.id = 1
    guild.categories = []
    guild.get_channel = lambda cid: next((c for c in guild.categories if c.id == cid), None)
    return guild


def _bot(guilds: list[Any], definitions: dict[str, Any]) -> Any:
    class _Registry:
        def enabled(self) -> dict[str, Any]:
            return definitions

    class _Bot:
        pass

    bot = _Bot()
    bot.guilds = guilds
    bot.registry = _Registry()
    return bot


@pytest.fixture()
def _stored(monkeypatch: pytest.MonkeyPatch) -> None:
    ids = {
        ("1", "mod/kingdom", "category"): "100",
        ("1", "mod/kingdom", "cat:⚙️ ᴀᴅᴍɪɴ"): "200",
        ("1", "games/aoe2", "category"): "300",
    }

    async def fake_stored(gid: str, scope: str, key: str) -> str | None:
        return ids.get((gid, scope, key))

    monkeypatch.setattr(panels_provisioning, "stored_channel_id", fake_stored)


async def test_the_mods_bottom_folders_sink_in_declaration_order(
    _stored: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # isolate from any platform scopes left registered by an earlier suite
    monkeypatch.setattr(panels_provisioning, "registered_scopes", lambda: ())
    guild = _guild()
    guild.categories = [
        _fake_category(100, guild),  # the home (drifted up)
        _fake_category(200, guild),  # the ADMIN machine room (drifted up)
        _fake_category(1, guild),  # a realm habitat — the player surface
    ]
    bot = _bot([guild], {"kingdom": _definition(home_bottom=True, group_bottom=True)})

    from botforge.discord.ui.panels_provisioning import enforce_bottom_categories

    moved = await enforce_bottom_categories(bot)
    order = [c.id for c in guild.categories]
    assert order == [1, 200, 100], "admin closes the playable structure, the home follows"
    assert moved == 2


async def test_a_converged_guild_costs_zero_discord_calls(
    _stored: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # isolate from any platform scopes left registered by an earlier
    # suite (an integration journey registers them globally); this
    # test asserts the MOD bottom folders' convergence only
    monkeypatch.setattr(panels_provisioning, "registered_scopes", lambda: ())
    guild = _guild()
    guild.categories = [
        _fake_category(1, guild),
        _fake_category(200, guild),
        _fake_category(100, guild),
    ]
    bot = _bot([guild], {"kingdom": _definition(home_bottom=True, group_bottom=True)})

    from botforge.discord.ui.panels_provisioning import enforce_bottom_categories

    first = await enforce_bottom_categories(bot)
    second = await enforce_bottom_categories(bot)
    assert first == 0 and second == 0, "the declared tail already closes the sidebar"
    for category in guild.categories:
        assert not category.moves, "a converged guild makes ZERO Discord API calls"


async def test_platform_and_mod_bottoms_share_the_convergence(_stored: None) -> None:
    register_scope(ScopeSpec(scope="games/aoe2", category_key="ui.panels.categories.games_aoe2", category_bottom=True))
    guild = _guild()
    guild.categories = [
        _fake_category(100, guild),
        _fake_category(200, guild),
        _fake_category(300, guild),
        _fake_category(1, guild),
    ]
    bot = _bot([guild], {"kingdom": _definition(home_bottom=True, group_bottom=True)})

    from botforge.discord.ui.panels_provisioning import enforce_bottom_categories

    await enforce_bottom_categories(bot)
    assert [c.id for c in guild.categories] == [1, 200, 100, 300], (
        "the mod tail (admin, home) then the platform plumbing — always the same order"
    )


def test_the_kingdom_declaration_carries_the_new_flags_as_data() -> None:
    """The real mod.yaml parses: home_bottom + the admin group's bottom."""
    from botforge.core.services.mod_registry import _load_declaration

    declaration = _load_declaration(Path(__file__).resolve().parents[3] / "modules/mods/kingdom/conf/mod.yaml")
    assert declaration.home_bottom is True
    admin_group_channels = [
        c for c in declaration.channel_categories if getattr(c, "group", "").endswith("ᴀᴅᴍɪɴ")
    ]
    assert admin_group_channels, "the admin group's channels must resolve from channel_groups"
    assert all(c.group_bottom for c in admin_group_channels), "bottom: true rides every admin-group channel"
    plain = [c for c in declaration.channel_categories if not getattr(c, "group", "").endswith("ᴀᴅᴍɪɴ")]
    assert all(not c.group_bottom for c in plain), "the player surfaces never sink"


def test_the_scope_spec_channel_carries_the_group_bottom() -> None:
    """_build_mod_scope_spec forwards the flag onto the platform's ChannelDecl."""
    import inspect

    from botforge.discord import mods_forum

    source = inspect.getsource(mods_forum._build_mod_scope_spec)
    assert "group_bottom" in source, "the built spec must carry the flag to provision_scope"
    decl_fields = ChannelDecl.__dataclass_fields__  # type: ignore[attr-defined]
    assert "group_bottom" in decl_fields, "the platform's ChannelDecl declares the field"


async def test_the_tail_leaves_the_slots_above_admin_free_for_the_realms(
    _stored: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """sidebar-contract-v2 (live incident 24/11): the two rules coexist.

    The bottom tail is the LAST slots only — a realm band riding just
    above the admin group never touches the tail, so the pins pass and
    the band pass stop fighting over the sidebar.
    """
    monkeypatch.setattr(panels_provisioning, "registered_scopes", lambda: ())
    guild = _guild()
    guild.categories = [
        _fake_category(100, guild),  # the home (drifted up)
        _fake_category(400, guild),  # realm 🏰 habitat
        _fake_category(200, guild),  # the admin group
        _fake_category(401, guild),  # realm 🏰 habitat
    ]
    bot = _bot([guild], {"kingdom": _definition(home_bottom=True, group_bottom=True)})

    from botforge.discord.ui.panels_provisioning import enforce_bottom_categories

    first = await enforce_bottom_categories(bot)
    assert [c.id for c in guild.categories] == [400, 401, 200, 100], (
        "the realms ride above admin, the admin closes the playable structure, home follows"
    )
    assert first == 2
    second = await enforce_bottom_categories(bot)
    assert second == 0, "a guild carrying realm habitats still converges"
