"""The kingdom mod's cog package (§7 cogs) — the mod's Discord layer.

Lifecycle hooks (all optional, all idempotent — see
botforge.core.services.mod_entrypoint): the core calls ``register`` at
bot build time, ``setup_hook`` after a restart to re-register persistent
UI, ``close`` on shutdown. Hooks degrade quietly when their stack
(Mongo, Redis, providers) is not configured.
"""

from __future__ import annotations

from typing import Any

import discord



def register(bot: Any, config: Any) -> None:
    """Wire the cog onto the bot: commands, pins, dynamic items."""
    from botforge.discord.static_pins import StaticPinnedView, register_static_pin
    from botforge.discord.ui.panels_provisioning import stored_channel_id

    from .panel import build_attack_panel, remember_bot

    remember_bot(bot)

    # #381 ruling 3: the mod DECLARES its ephemeral navigation mode
    # (the seam owns the plumbing — idempotent with the import-time one).
    from .common import _declare_window_mode

    _declare_window_mode()

    async def _resolve_channel(guild_id: str) -> str:
        return await stored_channel_id(guild_id, "mod/kingdom", "attack") or ""

    register_static_pin(
        StaticPinnedView(
            key="panel:mod:kingdom:attack",
            mark_suffix="panel:mod:kingdom:attack",
            resolve_channel=_resolve_channel,
            build_layout=build_attack_panel,
            registry=getattr(bot, "message_registry", None),
            scope="mod/kingdom",
        )
    )


    # #339 (candidates dashboard): the detailed validation view pinned in
    # the declared « realms » admin salon — pending rows with the decision
    # buttons + the accepted and refused tables (D70 rule 35).
    from .validation import build_validation_panel

    async def _resolve_realms_channel(guild_id: str) -> str:
        return await stored_channel_id(guild_id, "mod/kingdom", "realms") or ""

    register_static_pin(
        StaticPinnedView(
            key="panel:mod:kingdom:candidates",
            mark_suffix="panel:mod:kingdom:candidates",
            resolve_channel=_resolve_realms_channel,
            build_layout=build_validation_panel,
            registry=getattr(bot, "message_registry", None),
            scope="mod/kingdom",
        )
    )

    # #339 (console ops): the mod's ops ride the platform console
    # (relaunch/reset/clock — the registry's three gates guard them).
    from .console import register_console_actions

    register_console_actions()

    # postuler-hybride-v1 (Drasah 18/11): the PLAYERS' enrollment door —
    # the golden Postuler panel pinned in the public « apply » salon
    # (the Conscription group); its single button opens the adaptive
    # window (account → season → withdraw), the engine stays the
    # platform's.
    from .apply_flow import APPLY_VIEW_KEY, REGISTER_VIEW_KEY, build_apply_panel, build_register_panel
    from .registration_gate import subscribe_profile_gate

    async def _resolve_apply_channel(guild_id: str) -> str:
        return await stored_channel_id(guild_id, "mod/kingdom", "apply") or ""

    register_static_pin(
        StaticPinnedView(
            key=APPLY_VIEW_KEY,
            mark_suffix=APPLY_VIEW_KEY,
            resolve_channel=_resolve_apply_channel,
            build_layout=build_apply_panel,
            registry=getattr(bot, "message_registry", None),
            scope="mod/kingdom",
        )
    )

    # salon-parcours-v2 (Drasah 18/11): the parcours' FIRST door —
    # the public « register » salon carries the s'enregistrer poster (ONE
    # CTA: the platform's official profile route). The Postuler salon
    # above stays gated to the registered players (the access role is
    # granted by the profile.bound event — registration_gate).
    async def _resolve_register_channel(guild_id: str) -> str:
        return await stored_channel_id(guild_id, "mod/kingdom", "register") or ""

    register_static_pin(
        StaticPinnedView(
            key=REGISTER_VIEW_KEY,
            mark_suffix=REGISTER_VIEW_KEY,
            resolve_channel=_resolve_register_channel,
            build_layout=build_register_panel,
            registry=getattr(bot, "message_registry", None),
            scope="mod/kingdom",
        )
    )

    # console-fr-v1 (Drasah 19/11): the admin console ALSO pins in its
    # OWN declared settings salon (Admin > Paramètres) — the same
    # restart-proof buttons, the ephemeral SDK window stays. The pin
    # carries its own view id so the registry keeps two surfaces.
    from .settings_panel import build_settings_panel

    async def _resolve_settings_channel(guild_id: str) -> str:
        """The settings salon, by stored id FIRST, declared name last.

        settings-pin-fallback-v1 (Drasah 20/11): the migrated guild's
        stored tree id may miss the salon (a pre-key provisioning, a
        drifted id) — the pin then NEVER lands and Admin > Paramètres
        stays EMPTY. The last-chance fallback scans the guild for the
        declared salon's literal name (fr and en renders) so the
        console panel always finds its home; the provisioning keeps
        owning the canonical ids.
        """
        stored = await stored_channel_id(guild_id, "mod/kingdom", "console")
        if stored:
            return stored
        from .common import channel_id_by_flattened_name

        # the new « console » render first, then the legacy « paramètres » /
        # « settings » renders for guilds not yet re-provisioned
        return channel_id_by_flattened_name(bot, guild_id, ("console", "parametres", "settings"))

    register_static_pin(
        StaticPinnedView(
            key="panel:mod:kingdom:console",
            mark_suffix="panel:mod:kingdom:console",
            resolve_channel=_resolve_settings_channel,
            build_layout=build_settings_panel,
            registry=getattr(bot, "message_registry", None),
            scope="mod/kingdom",
        )
    )

    # machine-temps-v3 (Drasah 19/11): the ⏱️ machine à temps cockpit —
    # the game clock, the switches, the snapshots — pinned in the
    # declared time_machine salon, next to the ephemeral windows.
    from .time_machine import build_time_machine_panel

    async def _resolve_time_machine_channel(guild_id: str) -> str:
        return await stored_channel_id(guild_id, "mod/kingdom", "time_machine") or ""

    register_static_pin(
        StaticPinnedView(
            key="panel:mod:kingdom:time-machine",
            mark_suffix="panel:mod:kingdom:time-machine",
            resolve_channel=_resolve_time_machine_channel,
            build_layout=build_time_machine_panel,
            registry=getattr(bot, "message_registry", None),
            scope="mod/kingdom",
        )
    )

    # distributeur-v1 (Drasah 19/11): the 🎁 distributeur — the test
    # injector pinned in the declared distributor salon (create/remove
    # the test kingdom, hand kingdoms points/territories/civilizations).
    from .distributor import build_distributor_panel

    async def _resolve_distributor_channel(guild_id: str) -> str:
        return await stored_channel_id(guild_id, "mod/kingdom", "distributor") or ""

    register_static_pin(
        StaticPinnedView(
            key="panel:mod:kingdom:distributor",
            mark_suffix="panel:mod:kingdom:distributor",
            resolve_channel=_resolve_distributor_channel,
            build_layout=build_distributor_panel,
            registry=getattr(bot, "message_registry", None),
            scope="mod/kingdom",
        )
    )

    # realms validation dashboard pin (ported from the reference panel:royaumes)
    from .validation import build_validation_panel

    async def _resolve_realms_channel(guild_id: str) -> str:
        return await stored_channel_id(guild_id, "mod/kingdom", "realms") or ""

    register_static_pin(
        StaticPinnedView(
            key="panel:mod:kingdom:validation",
            mark_suffix="panel:mod:kingdom:validation",
            resolve_channel=_resolve_realms_channel,
            build_layout=build_validation_panel,
            registry=getattr(bot, "message_registry", None),
            scope="mod/kingdom",
        )
    )

    # marché entry pin (ported from the reference panel:marche)
    from .market import build_market_panel

    async def _resolve_market_channel(guild_id: str) -> str:
        return await stored_channel_id(guild_id, "mod/kingdom", "market") or ""

    register_static_pin(
        StaticPinnedView(
            key="panel:mod:kingdom:market",
            mark_suffix="panel:mod:kingdom:market",
            resolve_channel=_resolve_market_channel,
            build_layout=build_market_panel,
            registry=getattr(bot, "message_registry", None),
            scope="mod/kingdom",
        )
    )

    # the salon gate's subscription (profile.bound → the access role):
    # idempotent (the sink keeps one handler reference per bot)
    subscribe_profile_gate(bot)

    # epic #412 T1: the kingdom admin console — the 12 season-management
    # operations as ONE ephemeral window (no settings salon, no pin). The
    # SDK injects the Console button on menu:mod:kingdom:admin because the
    # mod declares panel:mod:kingdom:admin:console; the router lands here.
    from botforge.discord.views_routing import wire_view

    from .common import open_unique_ephemeral
    from .settings_panel import CONSOLE_VIEW_KEY, _panel_guard, build_settings_panel

    async def _open_kingdom_console(interaction: discord.Interaction) -> None:
        if not await _panel_guard(interaction):
            return
        view = await build_settings_panel(str(interaction.guild_id or ""))
        await open_unique_ephemeral(interaction, view=view)

    wire_view(CONSOLE_VIEW_KEY, _open_kingdom_console)


def setup_hook(bot: Any) -> None:
    """Re-register persistent UI after a restart (dynamic items)."""
    from .panel import (
        CancelButton,
        DeclareButton,
        DefendButton,
        HistoryButton,
        InfoButton,
        JoinButton,
    )
    from .pickban import (
        PickBanModifyButton,
        PickBanSelect,
        PickBanValidateButton,
        SabotageOpenButton,
        SabotagePassButton,
    )
    from .battle import (
        DisputeChoiceSelect,
        DisputeConfirmButton,
        DraftViewButton,
        RoomReadyButton,
        RoomResultButton,
        RoomUrlButton,
    )
    from .plan import PlanButton, PlanCancelButton
    from .marry import MarryButton
    from .alliances import AlliancesButton
    from .market import ChamberButton, MarketButton
    from .tavern import MercenaryButton, TavernButton
    from .ffa import FFAJoinButton
    from .console import KingdomClockButton, KingdomRelaunchButton, KingdomResetButton
    from .validation import (
        ValidationCrownButton,
        ValidationDecisionButton,
        ValidationDeleteButton,
        ValidationRealmEntryButton,
    )
    from .apply_flow import KingdomApplyOpenButton, KingdomPostulerButton
    from .settings_panel import SettingsActionButton
    from .time_machine import machine_dynamic_items
    from .distributor import distributor_dynamic_items
    from .camp_beta import camp_dynamic_items
    from .realms import realm_dynamic_items

    for item in (
        DeclareButton,
        HistoryButton,
        InfoButton,
        DefendButton,
        JoinButton,
        CancelButton,
        PickBanSelect,
        PickBanModifyButton,
        PickBanValidateButton,
        SabotageOpenButton,
        SabotagePassButton,
        DraftViewButton,
        RoomUrlButton,
        RoomReadyButton,
        RoomResultButton,
        DisputeChoiceSelect,
        DisputeConfirmButton,
        PlanButton,
        PlanCancelButton,
        MarryButton,
        AlliancesButton,
        MarketButton,
        ChamberButton,
        TavernButton,
        MercenaryButton,
        FFAJoinButton,
        KingdomRelaunchButton,
        KingdomResetButton,
        KingdomClockButton,
        ValidationDecisionButton,
        ValidationDeleteButton,
        ValidationCrownButton,
        ValidationRealmEntryButton,
        KingdomApplyOpenButton,
        KingdomPostulerButton,
        SettingsActionButton,
        *machine_dynamic_items(),
        *distributor_dynamic_items(),
        *camp_dynamic_items(),
        *realm_dynamic_items(),
    ):
        try:
            bot.add_dynamic_items(item)
        except Exception:  # noqa: S110 — idempotent across restarts
            pass

    # P4.1b tranche 2e: the attack phases loop (plans, reveals, DMs,
    # rooms, forfeits, scores) — the test journeys gate it off.
    from .phases import start_attack_refresher

    try:
        start_attack_refresher(bot)
    except Exception:  # noqa: S110 — a loop failure never blocks the boot
        pass

    # machine-temps-v4 (Drasah 20/11): the ⏱️ machine à temps pin
    # re-renders itself — « Panneau épinglé auto-mis à jour ».
    try:
        from .time_machine import start_machine_refresher

        start_machine_refresher(bot)
    except Exception:  # noqa: S110 — a loop failure never blocks the boot
        pass

    # The boot passes (epic #412): one pass per guild shortly after the
    # gateway is ready — the pins land (the Repair seam) and the mod's
    # declared surfaces exist on every served guild.
    try:
        import asyncio

        from .registration_gate import boot_reconcile
        from .selfheal import boot_self_heal

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is not None:
            # boot passes ride tasks: discord.py 2.7 has no add_listener
            # and bot.event would override the core's on_ready
            loop.create_task(boot_reconcile(bot))
            loop.create_task(boot_self_heal(bot))
    except Exception:  # noqa: S110 — the self-heal never blocks the boot
        pass


def close(bot: Any) -> None:
    """Stop the mod's background tasks (best-effort)."""
