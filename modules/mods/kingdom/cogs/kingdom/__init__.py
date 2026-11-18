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

from .cog import status_view


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
            key="view:mod:kingdom:attack",
            mark_suffix="view:mod:kingdom:attack",
            resolve_channel=_resolve_channel,
            build_layout=build_attack_panel,
            registry=getattr(bot, "message_registry", None),
            scope="mod/kingdom",
        )
    )

    @discord.app_commands.command(
        name="kingdom",
        description="Kingdom — statut du service",
    )
    async def _cmd(interaction: discord.Interaction) -> None:
        view = await status_view(str(interaction.guild_id or ""))
        await interaction.response.send_message(view=view, ephemeral=True)

    bot.tree.add_command(_cmd)

    # #339 (candidates dashboard): the detailed validation view pinned in
    # the declared « realms » admin salon — pending rows with the decision
    # buttons + the accepted/refused tables (D70 rule 35).
    from .validation import build_validation_panel

    async def _resolve_realms_channel(guild_id: str) -> str:
        return await stored_channel_id(guild_id, "mod/kingdom", "realms") or ""

    register_static_pin(
        StaticPinnedView(
            key="view:mod:kingdom:candidates",
            mark_suffix="view:mod:kingdom:candidates",
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

    # salon-parcours-v2 (Drasah 18/11): the parcours' FIRST door — the
    # public « register » salon carries the s'enregistrer poster (ONE
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

    # the salon gate's subscription (profile.bound → the access role):
    # idempotent (the sink keeps one handler reference per bot)
    subscribe_profile_gate(bot)


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
    from .validation import ValidationDecisionButton
    from .apply_flow import KingdomApplyOpenButton, KingdomPostulerButton

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
        KingdomApplyOpenButton,
        KingdomPostulerButton,
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


def close(bot: Any) -> None:
    """Stop the mod's background tasks (best-effort)."""
