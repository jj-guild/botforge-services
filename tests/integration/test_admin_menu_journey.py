"""The admin-menu security contract, enforced as a journey (critical path).

The owner's rule (2026-11-08): a public post NEVER carries admin
buttons — one ⚙️ Admin button opens an EPHEMERAL management menu,
permission-checked at click time. A non-authorized user never sees an
admin button beyond the single ⚙️ (and clicking it denies, ephemerally);
the post's own message is never rewritten with admin controls.
"""

from __future__ import annotations

from typing import Any

import discord
import pytest

from tests.integration.test_pool_lifecycle_journey import (
    _CannedMapSeeds,
    _CatalogFake,
    _RegistryFake,
    _reset_caches,
    _restore_caches,
    _start_server,
)

pytestmark = pytest.mark.simcord(strict_sync=False)


def _payload_buttons(components: list) -> list[dict]:
    """Collect every button payload from a raw components tree (V2 included)."""
    out: list[dict] = []

    def walk(node: dict) -> None:
        if node.get("type") == 2:  # button
            out.append(node)
        for key in ("components", "items"):
            for child in node.get(key) or []:
                if isinstance(child, dict):
                    walk(child)

    for top in components:
        if isinstance(top, dict):
            walk(top)
    return out


def _object_buttons(components: list) -> list:
    """Collect every button from discord.py component objects (a post)."""
    out: list = []

    def walk(node: Any) -> None:
        children = getattr(node, "children", None)
        if children is not None:
            for child in children:
                walk(child)
            return
        if getattr(node, "custom_id", None) is not None:
            out.append(node)

    for top in components:
        walk(top)
    return out


class TestAdminMenuJourney:
    """Click Admin as a stranger, then as an admin — the contract holds."""

    async def test_the_admin_menu_is_ephemeral_and_the_post_stays_public(
        self, simcord_env, simcord_bot, monkeypatch: pytest.MonkeyPatch
    ) -> None:  # type: ignore[no-untyped-def]
        import os

        from botforge.core.services.faction_content import FactionContentService
        from botforge.core.services.game_data import GameDataService
        from botforge.game_aoe2.remote_catalog import RemoteGameDataService
        from botforge.game_aoe2.server import _CatalogGateway

        guild = simcord_env.create_guild()
        channel = guild.create_text_channel("general")
        forum = guild.create_forum_channel("maps")
        alice = guild.add_member(simcord_env.create_user("alice"))
        mallory = guild.add_member(simcord_env.create_user("mallory"))

        registry = _RegistryFake()
        registry.docs[f"{guild.id}:tree:games/aoe2:maps"] = {
            "_id": f"{guild.id}:tree:games/aoe2:maps",
            "channel_id": str(forum.id),
        }

        catalog = _CatalogGateway(
            GameDataService(_CatalogFake()), FactionContentService(_RegistryFake())
        )
        server, port = await _start_server(catalog, _CannedMapSeeds())
        uri = f"127.0.0.1:{port}"
        monkeypatch.setenv("GAME_AOE2_URI", uri)
        import botforge.core.models.db as db_module

        monkeypatch.setattr(db_module, "get_async_database", lambda: registry)
        remote = RemoteGameDataService(uri)
        monkeypatch.setattr(
            type(simcord_bot.status_service),
            "bot_admins",
            property(lambda self: (str(alice.id),)),
        )

        from botforge.discord.admin_panel_games import register_games_admin_items

        register_games_admin_items(simcord_bot)

        saved = _reset_caches()
        try:
            # ── import Arabia — the forum post lands in the provisioned maps forum
            from tests.integration.test_pool_lifecycle_journey import IMPORT_BUTTON_ID, _modal_fields

            @simcord_bot.tree.command(name="mapspanel")
            async def mapspanel(interaction: discord.Interaction) -> None:
                from botforge.discord.admin_panel_games import maps_section_layout

                await interaction.response.send_message(
                    view=await maps_section_layout("aoe2", str(interaction.guild_id))
                )

            await alice.slash(channel, "mapspanel")
            panel = channel.last_message
            assert panel is not None
            shown = await alice.click(panel, custom_id=IMPORT_BUTTON_ID)
            assert shown.modal is not None
            fields = _modal_fields(shown)
            lines_id = fields["Maps (id, nom ou URL, une par ligne)"]
            done = await alice.submit_modal(shown, {lines_id: "Arabia"})
            report = " ".join(m.content for m in done.followups)
            assert "Arabia" in report, report

            (arabia,) = await remote.list_maps("aoe2")
            thread = next(t for t in forum.threads if t.name == "Arabia")
            (starter,) = thread.history()

            def _post_buttons() -> list[str]:
                """The post's live button custom_ids (re-read each time)."""
                return sorted(
                    str(b.custom_id)
                    for b in _object_buttons(thread.history()[0].components)
                )

            # ── CONTRACT 1: the public post carries ONLY the Admin button
            buttons = _object_buttons(starter.components)
            admin_ids = [
                b for b in buttons if str(b.custom_id).startswith("panel:admin:map:")
            ]
            assert len(buttons) == 1 and len(admin_ids) == 1, (
                f"a public post carries exactly one button — the ⚙️ Admin. got: {buttons}"
            )
            admin_custom_id = str(admin_ids[0].custom_id)

            # ── CONTRACT 2: a stranger's click denies, ephemerally — and
            # the post is never rewritten with admin controls
            denied = await mallory.click(starter, custom_id=admin_custom_id)
            assert denied.ephemeral, "the denial is ephemeral — no one else sees it"
            denial = denied.response or (denied.followups[-1] if denied.followups else None)
            assert denial is not None and "bot admin" in denial.content.lower(), (
                "the guard answers the denial"
            )
            assert _post_buttons() == [admin_custom_id], (
                "the post's own message is untouched by a stranger's click"
            )
            assert await remote.get_map(arabia.id) is not None, "nothing was mutated"

            # ── CONTRACT 3: an admin's click opens the EPHEMERAL menu —
            # the admin buttons live ONLY in that ephemeral answer
            opened = await alice.click(starter, custom_id=admin_custom_id)
            assert opened.ephemeral, "the admin menu is ephemeral"
            menu = opened.response
            assert menu is not None, "the admin menu answers"
            menu_buttons = _payload_buttons(menu.components)
            assert menu_buttons, "the ephemeral menu carries the admin buttons"
            assert all(
                str(b.get("custom_id", "")).startswith(("games:", "admin:", "panel:"))
                for b in menu_buttons
            ), f"the menu's buttons are the admin controls — got {menu_buttons}"
            assert _post_buttons() == [admin_custom_id], (
                "the post never gains admin buttons — they stay in the ephemeral"
            )
        finally:
            await server.stop(0)
            _restore_caches(saved)
            os.environ.pop("GAME_AOE2_URI", None)
