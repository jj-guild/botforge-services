"""Dev console tests: prod gate, propagation rules, grants replacement.

Everything runs against fakes \u2014 no test ever touches the real Discord
API (MockDiscord rule). The destructive paths are exercised through
seams, the gates through environment dicts.
"""

from __future__ import annotations

from typing import Any

from botforge.core.services.guild_access import GuildAccessService
from botforge.core.services.mod_definition import (
    ChannelCategoryDef,
    ModDefinition,
    RoleDef,
)
from botforge.core.services.mod_registry import ModRegistry
from botforge.discord.console import _propagate
from botforge.discord.console_guilds import (
    TEST_GUILD_IDS_ENV_VAR,
    is_test_guild,
    parse_test_guild_ids,
)


class FakeGuildAccessDB:
    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {}

    async def get_guild_access(self, guild_id: str) -> dict[str, Any] | None:
        return self.docs.get(guild_id)

    async def upsert_guild_access(self, document: dict[str, Any]) -> None:
        self.docs[str(document["guild_id"])] = {k: v for k, v in document.items() if k != "_id"}

    async def list_guild_access(self) -> list[dict[str, Any]]:
        return list(self.docs.values())


def _registry() -> ModRegistry:
    return ModRegistry(
        {
            "ladder": ModDefinition(
                name="ladder",
                seasonal=True,
                channel_categories=(ChannelCategoryDef(key="rankings", display_name="Rankings"),),
                roles=(RoleDef(key="ladder_admin", display_name="Ladder Admin"),),
                required_games=("aoe2",),
            ),
            "register": ModDefinition(
                name="register",
                seasonal=False,
                channel_categories=(ChannelCategoryDef(key="announce", display_name="Announces"),),
                roles=(),
                required_games=(),
            ),
        }
    )


def test_prod_env_is_recognized() -> None:
    from botforge.discord.console import PROD_ENV_NAMES

    assert "prod" in PROD_ENV_NAMES
    assert "production" in PROD_ENV_NAMES


def test_test_guild_allowlist_parses_and_validates(monkeypatch: Any) -> None:
    ids = parse_test_guild_ids(
        {TEST_GUILD_IDS_ENV_VAR: "123456789, 987654321;42"}
    )
    assert ids == frozenset({"123456789", "987654321", "42"})
    import importlib

    import botforge.discord.console_guilds as console_guilds

    monkeypatch.setenv(TEST_GUILD_IDS_ENV_VAR, "42")
    reloaded = importlib.reload(console_guilds)
    try:
        assert reloaded.is_test_guild(42)
        assert reloaded.is_test_guild("42")
        assert not reloaded.is_test_guild("111")
        assert not reloaded.is_test_guild(None)
    finally:
        monkeypatch.delenv(TEST_GUILD_IDS_ENV_VAR, raising=False)
        importlib.reload(console_guilds)


def test_test_guild_allowlist_refuses_non_numeric() -> None:
    ids = parse_test_guild_ids(
        {TEST_GUILD_IDS_ENV_VAR: "123, not-a-guild, 456"}
    )
    assert ids == frozenset({"123", "456"})


def test_test_guild_allowlist_fails_closed() -> None:
    assert parse_test_guild_ids({}) == frozenset()
    assert parse_test_guild_ids({TEST_GUILD_IDS_ENV_VAR: ""}) == frozenset()
    assert parse_test_guild_ids({TEST_GUILD_IDS_ENV_VAR: "nope"}) == frozenset()


def test_empty_allowlist_disables_everywhere() -> None:
    """An empty allowlist denies every guild \u2014 fail closed."""
    assert not any(is_test_guild(g) for g in ("123456789", "1", "999999999999"))


async def test_console_view_buttons_disabled_outside_allowlist(monkeypatch: Any) -> None:
    """Buttons render visible-but-disabled outside the allowlist, enabled inside."""
    from botforge.discord import console as console_mod
    from botforge.discord import console_guilds

    async def button_states(guild_id: str) -> list[bool]:
        view = await console_mod._console_view(guild_id)
        stack = list(getattr(view, "children", []) or [])
        states: list[bool] = []
        while stack:
            item = stack.pop()
            if type(item).__name__ == "DevDangerButton":
                states.append(bool(item.item.disabled))
            stack.extend(getattr(item, "children", []) or [])
        return states

    states = await button_states("111222333")
    assert len(states) == 1
    assert all(states)

    monkeypatch.setattr(console_guilds, "_TEST_GUILD_IDS", frozenset({"111222333"}))
    states = await button_states("111222333")
    assert len(states) == 1
    assert not any(states)


async def test_reset_guild_data_queries_are_guild_scoped(monkeypatch: Any) -> None:
    """Every reset query must carry the guild scope; global collections absent."""
    import botforge.core.models.db as db_mod
    import botforge.discord.console as console_mod

    queries: dict[str, Any] = {}

    class FakeResult:
        deleted_count = 0

    class FakeCollection:
        def __init__(self, name: str) -> None:
            self.name = name

        async def delete_many(self, query: dict[str, Any]) -> FakeResult:
            queries[self.name] = query
            return FakeResult()

    class FakeDatabase:
        def __getitem__(self, name: str) -> FakeCollection:
            return FakeCollection(name)

    monkeypatch.setattr(db_mod, "get_async_database", lambda: FakeDatabase(), raising=False)
    guild_id = "12345"
    await console_mod._reset_guild_data(guild_id)
    global_collections = {
        "maps",
        "map_pools",
        "map_packs",
        "map_pool_history",
        "factions",
        "rules",
        "users",
        "platform_identities",
        "profile_stats",
        "profile_bindings",
        "faction_content",
        "admin_audit",
        "provider_mappings",
        "user_settings",
    }
    assert not global_collections & set(queries)
    assert queries
    for name, query in queries.items():
        assert guild_id in str(query), f"{name} query is not guild-scoped: {query}"


def test_propagate_mod_installs_its_games() -> None:
    registry = _registry()
    games, mods = _propagate(registry, ("aoe2",), ("ladder", "register"), ["ladder"], [])
    assert games == ["aoe2"]
    assert mods == ["ladder"]


def test_propagate_game_uninstall_drops_dependent_mods_only() -> None:
    registry = _registry()
    games, mods = _propagate(registry, ("aoe2",), ("ladder", "register"), ["ladder", "register"], [])
    assert games == ["aoe2"]
    assert mods == ["ladder", "register"]
    games, mods = _propagate(registry, ("aoe2",), ("ladder", "register"), ["register"], [])
    assert games == []
    assert mods == ["register"]


def test_propagate_keeps_game_without_mods() -> None:
    registry = _registry()
    games, mods = _propagate(registry, ("aoe2",), ("ladder",), [], ["aoe2"])
    assert games == ["aoe2"]
    assert mods == []


async def test_set_grants_replaces_wholesale() -> None:
    db = FakeGuildAccessDB()
    service = GuildAccessService(db, games=("aoe2",), mods=("ladder", "register"))
    doc = await service.set_grants("123", games=["aoe2"], mods=["ladder"])
    assert doc["games"] == ["aoe2"]
    assert doc["mods"] == ["ladder"]
    doc = await service.set_grants("123", games=[], mods=["register"])
    assert doc["games"] == []
    assert doc["mods"] == ["register"]
    assert await service.enabled_mods("123") == ("register",)


def test_console_ops_cli_gates(monkeypatch: Any) -> None:
    """The headless CLI enforces the same gates as the Discord surface."""
    from botforge.cli import console_ops

    # prod refused whatever the allowlist says
    monkeypatch.setenv("BOTFORGE_DEPLOY_ENV", "prod")
    monkeypatch.setenv("BOTFORGE_TEST_GUILD_IDS", "123")
    assert console_ops.main(["clean-managed", "--guild", "123"]) == 1

    # empty allowlist: refused everywhere (fail closed)
    monkeypatch.setenv("BOTFORGE_DEPLOY_ENV", "test")
    monkeypatch.setenv("BOTFORGE_TEST_GUILD_IDS", "")
    assert console_ops.main(["reset-data", "--guild", "123"]) == 1

    # a guild outside the allowlist: refused
    monkeypatch.setenv("BOTFORGE_TEST_GUILD_IDS", "123")
    assert console_ops.main(["nuke", "--guild", "999"]) == 1


def test_console_ops_cli_all_targets_are_allowlisted(monkeypatch: Any) -> None:
    """--guild all resolves to the env allowlist only, never a default."""
    from botforge.cli import console_ops
    from botforge.discord import console_guilds

    monkeypatch.setattr(console_guilds, "_TEST_GUILD_IDS", frozenset({"111", "222"}))
    assert console_ops._resolve_targets("all") == ["111", "222"]
    assert console_ops._resolve_targets("111") == ["111"]






async def test_console_action_registry_renders_extensions(monkeypatch: Any) -> None:
    """An extension action renders its button and rides the boot wiring."""
    import discord

    import botforge.discord.console as console_mod

    # a registered action reuses a concrete DynamicItem class — an
    # extension registers its own class the same way
    action = console_mod.ConsoleAction(
        key="ext-test",
        item_cls=console_mod.DevDangerButton,
        build=lambda disabled: console_mod.DevDangerButton(disabled=disabled),
        description="**Ext test** — an extension action.",
    )
    console_mod.register_console_action(action)
    try:
        keys = [a.key for a in console_mod.registered_console_actions()]
        assert keys == ["ext-test"]

        # the home renders the extension's button (disabled off-allowlist)
        view = await console_mod._console_view(None)
        rendered = str(view.to_components())
        assert "Ext test" in rendered

        # duplicate keys fail loudly
        try:
            console_mod.register_console_action(action)
            raise AssertionError("duplicate key must fail")
        except ValueError:
            pass

        # the boot wiring registers the extension's item class
        class FakeBot:
            def __init__(self) -> None:
                self.items: list[type[discord.ui.DynamicItem[Any]]] = []

            def add_dynamic_items(self, *classes: type[discord.ui.DynamicItem[Any]]) -> None:
                self.items.extend(classes)

        bot = FakeBot()
        console_mod.register_console_items(bot)  # type: ignore[arg-type]
        assert console_mod.DevDangerButton in bot.items
    finally:
        console_mod._ACTIONS.pop("ext-test", None)




def test_danger_modal_defaults_are_safe() -> None:
    """The Danger Zone modal: action-titled labels, multi-select data, safe defaults."""
    from botforge.discord.console import DevDangerModal

    modal = DevDangerModal(
        title="Danger Zone",
        label_channels="Delete channels",
        label_roles="Delete roles",
        label_data="Delete data",
        opt_none="None",
        opt_bot="Bot-created only",
        opt_all="All",
        opt_guild="Guild data",
        opt_maps="Maps (global content)",
        opt_pools="Map pools (global content)",
        nothing="Nothing selected.",
        done="done: {channels} {roles} {data}",
        data_kept="nothing deleted",
    )
    assert modal.channels_select.required is False
    assert modal.roles_select.required is False
    assert modal.data_select.required is False
    assert modal.data_select.max_values == 3
    values = {
        opt.value
        for select in (modal.channels_select, modal.roles_select, modal.data_select)
        for opt in select.options
    }
    assert values == {
        DevDangerModal.CHANNELS_NONE,
        DevDangerModal.CHANNELS_BOT,
        DevDangerModal.CHANNELS_ALL,
        DevDangerModal.ROLES_NONE,
        DevDangerModal.ROLES_BOT,
        DevDangerModal.ROLES_ALL,
        DevDangerModal.DATA_GUILD,
        DevDangerModal.DATA_MAPS,
        DevDangerModal.DATA_POOLS,
    }
