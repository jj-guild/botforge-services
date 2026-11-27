"""The repair plan's guards (owner 2026-11-27).

No autoheal (owner: "si on a cassé des trucs, on clique sur réparer"):
the repair button opens a MODAL, the admin picks the perimeter - the
roles to recreate, the channels to repair, the forums to refresh, the
provider data to update. The mod and the game repairs ride the same
runner; the scope decides the options, the plan decides the run.
"""

from __future__ import annotations

import asyncio
from typing import Any

import discord
import pytest

import botforge.discord.admin_tree as tree


class _Bot:
    """A stand-in client: no wiring, every service a Mock-free stub."""

    def __init__(self, *, mods: tuple[str, ...] = ()) -> None:
        self.mods = mods
        self.guilds: list[Any] = []


def test_the_repair_sections_offer_roles_channels_forums_and_data() -> None:
    """The game repair's plan: the forums carry the scope's forum
    channels plus the heavy matchs pass (UNselected - owner: "trop
    lourd"), the data select rides the bot admins only."""
    bot = _Bot()

    async def _tr(key: str, **kwargs: Any) -> str:
        return f"[{key}]"

    specs = [
        type(
            "Spec",
            (),
            {
                "scope": "games/aoe2",
                "category_key": "ui.games.aoe2.name",
                "channels": (
                    type("Decl", (), {"key": "general", "kind": "text", "label_key": "k1", "access": "readonly"})(),
                    type("Decl", (), {"key": "civs", "kind": "forum", "label_key": "k2", "access": "readonly"})(),
                    type("Decl", (), {"key": "joueurs", "kind": "forum", "label_key": "k3", "access": "readonly"})(),
                ),
            },
        )()
    ]
    monkey = pytest.MonkeyPatch()
    monkey.setattr(tree, "_scope_specs_of", lambda scope: specs)
    try:
        sections = asyncio.run(tree._repair_sections(bot, "games/aoe2", True, _tr))
    finally:
        monkey.undo()
    assert [o["value"] for o in sections["channels"]] == ["games/aoe2"]
    assert all(o["selected"] for o in sections["channels"])
    forums = {o["value"]: o for o in sections["forums"]}
    assert forums["civs"]["selected"], "the entity forums heal by default"
    assert forums["joueurs"]["selected"], "the players' posts are checked by default"
    assert not forums["__matchs__"]["selected"], "the heavy matchs pass stays UNselected"
    assert [o["value"] for o in sections["data"]] == ["civs", "maps"]
    assert not any(o["selected"] for o in sections["data"]), "the data refresh is a CHOICE"

    plain = asyncio.run(tree._repair_sections(bot, "games/aoe2", False, _tr))
    assert "data" not in plain, "the provider data rides the BOT ADMINS only"


def test_the_repair_sections_offer_the_mods_roles_and_channels() -> None:
    """The mod repair rides the SAME sections (owner: "le repair d'un
    mod et d'un jeu doit fonctionner de manière identique")."""
    bot = _Bot(mods=("kingdom",))
    bot.registry = type("Registry", (), {"enabled": lambda self: ["kingdom"]})()

    async def _tr(key: str, **kwargs: Any) -> str:
        return f"[{key}]"

    monkey = pytest.MonkeyPatch()
    monkey.setattr(
        tree,
        "_scope_specs_of",
        lambda scope: [
            type(
                "Spec",
                (),
                {
                    "scope": "mods/kingdom",
                    "category_key": "cat",
                    "channels": (
                        type("Decl", (), {"key": "c", "kind": "text", "label_key": "k", "access": "readonly"})(),
                    ),
                },
            )()
        ],
    )
    try:
        sections = asyncio.run(tree._repair_sections(bot, "mods/kingdom", False, _tr))
    finally:
        monkey.undo()
    assert [o["value"] for o in sections["roles"]] == ["mod:kingdom"], "the mod's roles recreate"
    assert [o["value"] for o in sections["channels"]] == ["mods/kingdom"]
    assert "forums" not in sections and "data" not in sections


def test_the_repair_modal_wraps_every_select_in_a_label() -> None:
    """A bare select inside a modal is silently rejected by the API -
    every select rides its Label wrapper (the modal constraint)."""
    sections = {
        "roles": [{"value": "admin", "label": "bot-admins", "selected": True}],
        "channels": [{"value": "games/aoe2", "label": "AoE2", "selected": True}],
    }
    texts = {"title": "Repair", "label:roles": "Roles", "label:channels": "Channels"}
    modal = tree.RepairModal("games/aoe2", sections, texts)
    labels = [c for c in modal.children if isinstance(c, discord.ui.Label)]
    assert len(labels) == 2, "every select rides its Label wrapper"
    for label in labels:
        assert isinstance(label.component, discord.ui.Select)


def test_the_repair_runner_executes_the_chosen_plan_only() -> None:
    """The plan decides the run: the chosen sections run, the rest
    never fires - nothing heals silently (owner 2026-11-27)."""
    calls: dict[str, Any] = {}

    async def _fake_recreate_roles(bot: Any, guild_id: str, values: list[str]) -> int:
        calls["roles"] = list(values)
        return 2

    async def _fake_refresh(bot: Any, kinds: list[str]) -> list[str]:
        calls["data"] = list(kinds)
        return ["civs"]

    async def _fake_repair_players(bot: Any, guild_id: str, full: bool) -> dict[str, int]:
        calls["players"] = full
        return {"posts": 3, "cards": 5}

    async def _fake_syncs(guild_id: str, bot: Any, scope: str) -> int:
        calls["syncs"] = scope
        return 4

    def _say(key: str, **values: Any) -> str:
        return f"[{key}]"

    def _translate(key: str, locale: str) -> str:
        return f"[{key}]"

    _say.translate = _translate  # type: ignore[attr-defined]

    bot = _Bot()
    monkey = pytest.MonkeyPatch()
    monkey.setattr(tree, "_recreate_scope_roles", _fake_recreate_roles)
    monkey.setattr(tree, "_refresh_game_data", _fake_refresh)
    monkey.setattr(tree, "_ensure_scope_pins", _fake_ensure(0))
    monkey.setattr(tree, "_ensure_scope_roles", _fake_ensure(0))
    monkey.setattr(tree, "_scope_specs_of", lambda scope: [])
    monkey.setattr("botforge.discord.live_activity.repair_players_forum", _fake_repair_players)
    monkey.setattr("botforge.discord.scope_surfaces.run_scope_syncs", _fake_syncs)
    try:
        _answer, report = asyncio.run(
            tree.run_scope_repair(
                bot,
                "42",
                "games/aoe2",
                {"data": ["civs"], "roles": ["admin"], "forums": ["civs", "joueurs", "__matchs__"]},
                say=_say,
            )
        )
    finally:
        monkey.undo()
    assert calls["data"] == ["civs"]
    assert calls["roles"] == ["admin"]
    assert calls["players"] is True, "the matchs pass rides the HEAVY arm"
    assert calls.get("syncs") == "games/aoe2"
    # the plan's steps SPEAK - the display strings ride the report
    displays = [getattr(step, "display", step) for step in report.steps]
    assert any("repair_data_done" in str(d) for d in displays)
    assert any("repair_roles_done" in str(d) for d in displays)
    assert any("repair_matchs_done" in str(d) for d in displays)


def _fake_ensure(count: int) -> Any:
    async def _ensure(bot: Any, guild_id: str, scope: str) -> int:
        return count

    return _ensure


def test_the_dm_admin_sync_buttons_are_gone() -> None:
    """The DM sync moved into the aoe2 repair (owner 2026-11-27) - the
    buttons and the section are deleted, a stale wire degrades to the
    language section."""
    import botforge.discord.admin_dm_panel as panel

    assert not hasattr(panel, "ContentRefreshButton"), "the civs sync button is gone"
    assert not hasattr(panel, "MapsSyncButton"), "the maps sync button is gone"
    assert not hasattr(panel, "_open_sync"), "the sync sub-view is gone"
    assert "sync-aoe2" not in panel.DmOpenButton.SECTIONS, "the DM menu lost the sync section"


def test_the_refresh_game_data_runs_the_civs_and_the_maps() -> None:
    """The migrated sync: the civs ride the factions (techtree), the
    maps ride the maps (Liquipedia) - through the game service."""
    calls: list[tuple[str, str]] = []

    class _Client:
        def __init__(self, uri: str) -> None:
            del uri

        async def sync_content(self, game: str, what: str, timeout_s: float = 900.0) -> dict[str, Any]:
            calls.append((game, what))
            return {"ok": True, "counts": {}}

    bot = _Bot()
    monkey = pytest.MonkeyPatch()
    monkey.setattr("botforge.game_aoe2.client.GameDataClient", _Client)
    monkey.setenv("GAME_AOE2_URI", "127.0.0.1:1")
    monkey.setattr(
        "botforge.core.services.entity_forum.sync_entity_forum",
        _fake_mirror("civs"),
    )
    monkey.setattr("botforge.discord.maps_forum.sync_maps_forum", _fake_mirror("maps"))
    try:
        done = asyncio.run(tree._refresh_game_data(bot, ["civs", "maps"]))
    finally:
        monkey.undo()
    assert done == ["civs", "maps"]
    assert ("aoe2", "factions") in calls and ("aoe2", "maps") in calls


def _fake_mirror(tag: str) -> Any:
    async def _mirror(guild_id: str, *args: Any, **kwargs: Any) -> int:
        del guild_id, args, kwargs
        return 1 if tag else 0

    return _mirror
