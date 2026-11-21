"""Unit tests for the Panels SDK provisioning — the tree rules + adoption.

These pin the channel-tree contract of docs/architecture/channel-tree.md
(the botforge repo): the scope folders provisioned in the guild's
locale, the canonical order, the read-only menu channels, the admin
visibility — and the legacy adoption (rename + move in place, ids
unchanged, so the managed services and their pins survive).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import discord
import pytest

from botforge.core.services.i18n import MessageCatalog
from botforge.discord.ui.panels_provisioning import (
    _Platform,
    _sorted_channels,
    provision_scope,
)
from botforge.discord.ui.panels_scopes import register_platform_scopes, scopes_from_config
from tests.mocks.discord_mock import (
    MockCategoryChannel,
    MockGuild,
    MockRole,
    MockTextChannel,
)

CONFIG_DIR = str(Path(__file__).resolve().parents[3] / "config")

_SCOPES = scopes_from_config(CONFIG_DIR)
AOE2_SCOPE = _SCOPES["games/aoe2"]
BOT_SCOPE = _SCOPES["bot"]
GAMES_SCOPE = _SCOPES["games"]
MODS_SCOPE = _SCOPES["mods"]
ROOT_SCOPE = _SCOPES["root"]

_STORED: dict[str, str] = {}


def _fake_stored_id(guild_id: str, scope: str, key: str) -> Any:
    """Awaitable stand-in for stored_channel_id (no Mongo in tests)."""

    class _Awaitable:
        def __await__(self):
            if False:  # pragma: no cover — keeps this a generator
                yield
            return _STORED.get(f"{scope}:{key}")

    return _Awaitable()


@pytest.fixture(autouse=True)
def _no_mongo_stored_ids(monkeypatch: Any) -> None:
    """Every provisioning test resolves from an empty store unless set."""
    _STORED.clear()
    monkeypatch.setattr(
        "botforge.discord.ui.panels_provisioning.stored_channel_id", _fake_stored_id
    )


def _translate(key: str, locale: str) -> str:
    """Render through the real catalog (the FR naming is the contract)."""
    catalog = MessageCatalog(CONFIG_DIR)
    rendered = catalog.render(key, locale)
    return rendered if rendered != key else catalog.render(key, "en")


class TestCanonicalOrder:
    def test_the_canonical_order_sorts_the_bands(self) -> None:
        decls = _sorted_channels(AOE2_SCOPE)
        keys = [d.key for d in decls]
        assert keys[0] == "general"
        assert keys[-1] == "admin"  # the grouping folder closes on admin
        assert keys.index("civs") < keys.index("admin")

    def test_the_bot_scope_orders_logs_first(self) -> None:
        assert [d.key for d in _sorted_channels(BOT_SCOPE)] == ["logs", "admin", "decisions"]


class TestRootScope:
    @pytest.mark.asyncio
    async def test_the_root_scope_creates_uncategorised_channels(self) -> None:
        guild = MockGuild()
        resolved = await provision_scope(guild, ROOT_SCOPE, "fr", _translate)
        assert set(resolved) == {"general", "discussions"}
        general = next(c for c in guild.text_channels if c.name == "🛡️ général")
        assert general.category is None
        assert len(guild.categories) == 0


class TestProvisioning:
    @pytest.mark.asyncio
    async def test_a_scope_provisions_category_and_channels(self) -> None:
        guild = MockGuild()
        resolved = await provision_scope(guild, BOT_SCOPE, "fr", _translate)
        assert set(resolved) == {"category", "logs", "admin", "decisions"}
        names = {c.name for c in guild.text_channels}
        assert "📜 logs" in names
        assert "⚖️ décisions" in names  # emoji + translated at creation (FR guild)
        logs = next(c for c in guild.text_channels if c.name == "📜 logs")
        assert logs.category is not None
        assert logs.category.name == "🤖 bot"

    @pytest.mark.asyncio
    async def test_provisioning_is_idempotent(self) -> None:
        guild = MockGuild()
        first = await provision_scope(guild, BOT_SCOPE, "fr", _translate)
        second = await provision_scope(guild, BOT_SCOPE, "fr", _translate)
        assert first == second
        assert len(guild.channels) == 4  # category + 3 channels, no duplicates

    @pytest.mark.asyncio
    async def test_the_games_scope_creates_the_forums(self) -> None:
        guild = MockGuild()
        resolved = await provision_scope(guild, AOE2_SCOPE, "en", _translate)
        assert resolved["civs"] and resolved["maps"] and resolved["map-pools"]
        forums = {f.name: f for f in guild.forums}
        assert set(forums) == {"🏛️ civs", "🌍 maps", "🧱 map pools"}  # EN locale: emoji + translated
        for forum in forums.values():
            assert forum.category is not None
            assert forum.category.name == "⚔️ games/aoe2"



class TestPlatformScopes:
    def test_registration_is_idempotent(self) -> None:
        register_platform_scopes()
        register_platform_scopes()
        from botforge.discord.ui.panels import registered_scopes

        keys = [spec.scope for spec in registered_scopes()]
        assert keys.count("bot") == 1
        assert keys.count("games/aoe2") == 1

    def test_every_decl_carries_a_label_key(self) -> None:
        for spec in (BOT_SCOPE, AOE2_SCOPE):
            for decl in spec.channels:
                assert decl.label_key.startswith("ui.panels.")



class TestAdoptionSeams:
    @pytest.mark.asyncio
    async def test_ensure_channel_moves_a_stray_channel_into_the_folder(self) -> None:
        guild = MockGuild()
        platform: Any = _Platform(guild)
        stray = MockTextChannel(name="discussions", guild=guild)
        guild._channels[stray.id] = stray
        category_id = await platform.ensure_category("games")
        channel_id = await platform.ensure_channel("discussions", category_id)
        assert channel_id == str(stray.id)
        assert stray.category is not None
        assert stray.category.name == "games"


class TestCategoryGate:
    """The machine-room rule (Drasah 18/11): a scope's category may
    declare itself staff-only — the folder's front door hides from
    @everyone, and the rooms' public bands follow the door (a plain
    readonly band would pierce the gate — an explicit channel
    overwrite nullifies the category's in Discord's resolution)."""

    def test_the_games_scope_declares_the_gate(self) -> None:
        assert GAMES_SCOPE.category_admin_only is True
        assert ROOT_SCOPE.category_admin_only is False
        assert BOT_SCOPE.category_admin_only is False

    @pytest.mark.asyncio
    async def test_a_gated_scope_denies_everyone_on_its_category(self) -> None:
        guild = MockGuild()
        await provision_scope(guild, GAMES_SCOPE, "fr", _translate)
        assert guild.categories
        category = guild.categories[0]
        assert isinstance(category, MockCategoryChannel)
        everyone = category.permission_overwrite_for(guild.default_role)
        assert everyone is not None
        assert everyone.view_channel is False
        # the bot operates its own category — including creating and
        # purging the rooms inside a private folder (#413)
        me = category.permission_overwrite_for(guild.me)
        assert me is not None
        assert me.view_channel is True
        assert me.manage_channels is True

    @pytest.mark.asyncio
    async def test_an_open_scope_keeps_its_category_public(self) -> None:
        guild = MockGuild()
        await provision_scope(guild, BOT_SCOPE, "fr", _translate)
        assert guild.categories
        assert guild.categories[0].permission_overwrite_for(guild.default_role) is None

    @pytest.mark.asyncio
    async def test_the_gate_grants_the_resolved_view_roles(self) -> None:
        from botforge.discord.ui.panels import ScopeSpec

        role = MockRole(name="Kingdom Admin")
        guild = MockGuild()
        guild._roles[role.id] = role
        spec = ScopeSpec(
            scope="mod/test",
            category_key="Test Home",
            category_admin_only=True,
            category_view_role_ids=(str(role.id),),
        )
        await provision_scope(guild, spec, "fr", _translate)
        assert guild.categories
        grant = guild.categories[0].permission_overwrite_for(role)
        assert grant is not None
        assert grant.view_channel is True

    @pytest.mark.asyncio
    async def test_an_admin_only_group_gates_its_own_category(self) -> None:
        """A channel group declared admin_only gates its category too —
        not only its channels (the console's blocker, #413)."""
        from botforge.discord.ui.panels import ChannelDecl, ScopeSpec

        role = MockRole(name="Kingdom Admin")
        guild = MockGuild()
        guild._roles[role.id] = role
        spec = ScopeSpec(
            scope="mod/test",
            category_key="Test Home",
            channels=(
                ChannelDecl(
                    key="settings",
                    label_key="settings",
                    group="Admin",
                    group_admin_only=True,
                    access="admin",
                    view_role_ids=(str(role.id),),
                ),
            ),
        )
        await provision_scope(guild, spec, "fr", _translate)
        admin_cat = next(c for c in guild.categories if c.name == "Admin")
        everyone = admin_cat.permission_overwrite_for(guild.default_role)
        assert everyone is not None
        assert everyone.view_channel is False
        me = admin_cat.permission_overwrite_for(guild.me)
        assert me is not None
        assert me.view_channel is True
        assert me.manage_channels is True
        grant = admin_cat.permission_overwrite_for(role)
        assert grant is not None
        assert grant.view_channel is True

    @pytest.mark.asyncio
    async def test_an_open_group_keeps_its_category_public(self) -> None:
        from botforge.discord.ui.panels import ChannelDecl, ScopeSpec

        guild = MockGuild()
        spec = ScopeSpec(
            scope="mod/test",
            category_key="Test Home",
            channels=(ChannelDecl(key="general", label_key="general", group="Public"),),
        )
        await provision_scope(guild, spec, "fr", _translate)
        public_cat = next(c for c in guild.categories if c.name == "Public")
        assert public_cat.permission_overwrite_for(guild.default_role) is None

    @pytest.mark.asyncio
    async def test_install_gates_and_uninstall_restores_platform_categories(self) -> None:
        """The install rule: installing a mod gates every platform scope's
        category (bot allow with manage_channels + @everyone deny); the
        uninstall of the last mod restores the normal (public) rights."""
        from botforge.discord.ui.panels_provisioning import set_platform_categories_private
        from botforge.discord.ui.panels_scopes import register_platform_scopes

        register_platform_scopes(CONFIG_DIR)
        guild = MockGuild()
        await provision_scope(guild, BOT_SCOPE, "fr", _translate)
        await provision_scope(guild, GAMES_SCOPE, "fr", _translate)
        for scope, spec in (("bot", BOT_SCOPE), ("games", GAMES_SCOPE)):
            cat = next(c for c in guild.categories if c.name == _translate(spec.category_key, "fr"))
            _STORED[f"{scope}:category"] = str(cat.id)
        n = await set_platform_categories_private(guild, True)
        assert n >= 2
        for cat in guild.categories:
            everyone = cat.permission_overwrite_for(guild.default_role)
            me = cat.permission_overwrite_for(guild.me)
            assert everyone is not None and everyone.view_channel is False
            assert me is not None and me.view_channel is True and me.manage_channels is True
        await set_platform_categories_private(guild, False)
        for cat in guild.categories:
            everyone = cat.permission_overwrite_for(guild.default_role)
            assert everyone is None or everyone.view_channel is not False

    @pytest.mark.asyncio
    async def test_install_gates_categories_without_stored_ids_by_name(self) -> None:
        """The name fallback: a guild whose ids were never persisted still
        gets gated — the platform categories resolve by their translated
        name (the fr/en renders of the declared category key) when the
        stored id is missing (the Kingdoms - Tests guild case)."""
        from botforge.discord.ui.panels_provisioning import set_platform_categories_private
        from botforge.discord.ui.panels_scopes import register_platform_scopes

        register_platform_scopes(CONFIG_DIR)
        guild = MockGuild()
        await provision_scope(guild, BOT_SCOPE, "fr", _translate)
        assert _STORED == {}, "no stored id: the resolution was never persisted"
        n = await set_platform_categories_private(guild, True)
        assert n >= 1
        cat = next(
            c for c in guild.categories if c.name == _translate(BOT_SCOPE.category_key, "fr")
        )
        everyone = cat.permission_overwrite_for(guild.default_role)
        me = cat.permission_overwrite_for(guild.me)
        assert everyone is not None and everyone.view_channel is False
        assert me is not None and me.view_channel is True and me.manage_channels is True
        await set_platform_categories_private(guild, False)
        assert cat.permission_overwrite_for(guild.default_role) is None

    @pytest.mark.asyncio
    async def test_the_rooms_follow_the_front_door_of_the_gate(self) -> None:
        """The room follows its folder (machine-room, completed): a
        readonly room inside a gated category carries the @everyone
        view deny too — an explicit channel overwrite NULLIFIES the
        category's in Discord's resolution, so a plain readonly band
        would pierce the gate and show the whole folder to passers-by
        (the games/aoe2 case: a brand-new member saw a staff-only
        category with its public rooms)."""
        guild = MockGuild()
        await provision_scope(guild, GAMES_SCOPE, "fr", _translate)
        general = discord.utils.get(guild.text_channels, category=guild.categories[0])
        assert general is not None
        overwrite = general.permission_overwrite_for(guild.default_role)
        assert overwrite is not None
        assert overwrite.view_channel is False
        assert overwrite.send_messages is False
        assert overwrite.add_reactions is True

    @pytest.mark.asyncio
    async def test_an_open_folder_keeps_the_plain_readonly_band(self) -> None:
        """The reverse direction: a PUBLIC category's readonly rooms keep
        the plain band (send denied, view open) — the rule adds nothing
        to an open folder."""
        from botforge.discord.ui.panels_provisioning import _restore_category_access

        guild = MockGuild()
        await provision_scope(guild, GAMES_SCOPE, "fr", _translate)
        general = discord.utils.get(guild.text_channels, category=guild.categories[0])
        assert general is not None
        # the uninstall restore lifts the front door…
        await _restore_category_access(guild, str(guild.categories[0].id))
        # …and the next band pass reads the live state: plain readonly again
        decl = next(d for d in _sorted_channels(GAMES_SCOPE) if d.key == "general")
        from botforge.discord.ui.panels_provisioning import _apply_access

        await _apply_access(guild, str(general.id), decl)
        overwrite = general.permission_overwrite_for(guild.default_role)
        assert overwrite is not None
        assert overwrite.view_channel is not False
        assert overwrite.send_messages is False

    @pytest.mark.asyncio
    async def test_an_admin_only_group_gate_covers_its_readonly_rooms(self) -> None:
        """A gated GROUP category gates its readonly rooms too — the door
        of a staff room inside a staff folder stays shut on both levels."""
        from botforge.discord.ui.panels import ChannelDecl, ScopeSpec

        guild = MockGuild()
        spec = ScopeSpec(
            scope="mod/test",
            category_key="Test Home",
            channels=(
                ChannelDecl(
                    key="logs",
                    label_key="logs",
                    group="Machine",
                    group_admin_only=True,
                    access="readonly",
                ),
            ),
        )
        await provision_scope(guild, spec, "fr", _translate)
        machine_cat = next(c for c in guild.categories if c.name == "Machine")
        room = next(ch for ch in guild.text_channels if ch.category is machine_cat)
        overwrite = room.permission_overwrite_for(guild.default_role)
        assert overwrite is not None
        assert overwrite.view_channel is False
        assert overwrite.send_messages is False

    @pytest.mark.asyncio
    async def test_the_install_pass_heals_the_pierced_rooms(self) -> None:
        """The install rule heals rooms provisioned BEFORE the rule (the
        pierced-bands era): gating the categories re-reads the live
        door and re-writes each room's band gated; the uninstall
        restore writes the plain bands back."""
        from botforge.discord.ui.panels_provisioning import set_platform_categories_private
        from botforge.discord.ui.panels_scopes import register_platform_scopes

        register_platform_scopes(CONFIG_DIR)
        guild = MockGuild()
        await provision_scope(guild, GAMES_SCOPE, "fr", _translate)
        general = discord.utils.get(guild.text_channels, category=guild.categories[0])
        assert general is not None
        cat_id = str(guild.categories[0].id)
        _STORED[f"games:category"] = cat_id
        _STORED[f"games:general"] = str(general.id)
        # the pre-rule pierced band: readonly WITHOUT the view deny
        general._permissions[(guild.default_role.id, True)] = None
        n = await set_platform_categories_private(guild, True)
        assert n >= 1
        overwrite = general.permission_overwrite_for(guild.default_role)
        assert overwrite is not None and overwrite.view_channel is False
        await set_platform_categories_private(guild, False)
        overwrite = general.permission_overwrite_for(guild.default_role)
        assert overwrite is not None and overwrite.view_channel is not False


@pytest.mark.asyncio
async def test_the_boot_pass_gates_platform_categories_when_a_mod_is_installed(monkeypatch: Any) -> None:
    """The install rule is state-driven, not only event-driven: at boot,
    every guild with a mod installed gets the platform categories gated
    (the install event may predate the stored ids — the name fallback
    resolves them). A guild with no mod keeps the normal rights."""
    from types import SimpleNamespace

    import botforge.discord.wiring as wiring_mod
    from botforge.discord.bot import factory
    from botforge.discord.ui import panels_provisioning

    guild = MockGuild()
    bot = SimpleNamespace(guilds=[guild])

    class _Access:
        def __init__(self, mods: tuple[str, ...]) -> None:
            self._mods = mods

        async def enabled_mods(self, guild_id: str) -> tuple[str, ...]:
            return self._mods

    calls: list[tuple[str, bool]] = []

    async def _fake_gate(g: Any, private: bool) -> int:
        calls.append((str(g.id), private))
        return 1

    monkeypatch.setattr(panels_provisioning, "set_platform_categories_private", _fake_gate)
    monkeypatch.setattr(wiring_mod, "build_guild_access_service", lambda: _Access(("kingdom",)))
    await factory._boot_gate_platform_categories(bot)
    assert calls == [(str(guild.id), True)]

    monkeypatch.setattr(wiring_mod, "build_guild_access_service", lambda: _Access(()))
    calls.clear()
    await factory._boot_gate_platform_categories(bot)
    assert calls == []


class TestSidebarOrder:
    """conscription-4-salons (Drasah 20/11): the sidebar IS the journey —
    the declared order is applied to Discord's stored positions, so an
    adopted channel (renamed in place, history's order) ends up where
    the tree rules say, not where chance left it."""

    @pytest.mark.asyncio
    async def test_provisioning_reorders_adopted_channels(self) -> None:
        guild = MockGuild()
        expected = [_translate(d.label_key, "fr") for d in _sorted_channels(BOT_SCOPE)]
        assert len(expected) >= 2
        # history's order: the channels exist, REVERSED (an adopted
        # channel keeps the position it was born with)
        for index, name in enumerate(reversed(expected)):
            stray = MockTextChannel(name=name, guild=guild, position=index)
            guild._channels[stray.id] = stray
        resolved = await provision_scope(guild, BOT_SCOPE, "fr", _translate)
        in_folder = sorted(
            (c for c in guild.text_channels if c.category is not None),
            key=lambda c: getattr(c, "position", 0),
        )
        assert [c.name for c in in_folder] == expected
        assert all(int(resolved[d.key]) for d in _sorted_channels(BOT_SCOPE))

    @pytest.mark.asyncio
    async def test_the_order_pass_is_idempotent_repin(self) -> None:
        guild = MockGuild()
        first = await provision_scope(guild, BOT_SCOPE, "fr", _translate)
        positions = {
            key: getattr(guild.get_channel(int(cid)), "position", None)
            for key, cid in first.items()
            if key != "category"
        }
        await provision_scope(guild, BOT_SCOPE, "fr", _translate)
        positions_again = {
            key: getattr(guild.get_channel(int(cid)), "position", None)
            for key, cid in first.items()
            if key != "category"
        }
        assert positions == positions_again

    @pytest.mark.asyncio
    async def test_reorder_channels_moves_only_the_drifted(self) -> None:
        guild = MockGuild()
        platform: Any = _Platform(guild)
        category_id = await platform.ensure_category("parcours")
        stay = MockTextChannel(name="stay", guild=guild, category=None)
        move = MockTextChannel(name="move", guild=guild, category=None)
        guild._channels[stay.id] = stay
        guild._channels[move.id] = move
        stay.position = 0
        move.position = 1
        # already in order: no edit at all
        await platform.reorder_channels(category_id, [str(stay.id), str(move.id)])
        await platform.reorder_channels(category_id, [str(move.id), str(stay.id)])
        assert move.position == 0
        assert stay.position == 1
