"""The Kingdoms salons-first panels (kingdoms#138): enrollment workflow.

Three panels on top of the bootstrapped structure:

- **Postuler** (open to all) — a pinned button opens an ephemeral,
  per-player enrollment flow with no free-text role: a select menu
  offers Seigneur or Roi; a Seigneur then picks a declared kingdom
  from a list (or joins the waiting queue, for an admin to assign
  later), a Roi types a kingdom name; both then give their AoE II
  Insight link + game ID and confirm with a rules-acceptance button
  (no typing);
- **Candidatures** (admin only) — each submitted application lands as
  a message with admin-only buttons ✅ validated / ⏳ pending / ❌
  refused; validation assigns the kingdoms_lord or kingdoms_king mod
  role to the player;
- **Paramètres** (admin only) — the mod's own season actions; language
  and timezone live in the platform core (bot-admin).

The mod declares its roles in ``config/mods/kingdoms.yaml``
(kingdoms_king, kingdoms_lord); the panels assign them through the
ModRolesService — never raw Discord role IDs. Panels degrade when the
stores are not wired (local runs): the buttons answer with a note.
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import Any

import discord
from discord import app_commands

from kingdoms.core.services.logs import LogService
from kingdoms.core.services.roles import ModRolesService
from kingdoms.discord.commands_i18n import localized
from kingdoms.discord.ui import (
    GREEN,
)
from kingdoms.mods.kingdoms.game_clock import game_now
from kingdoms.mods.kingdoms.panel_messages import (
    NO_MENTIONS,
    channel_messages,
    message_text,
    message_text_squashed,
    view_text,
)
from kingdoms.mods.kingdoms.snapshot import season_label

logger = logging.getLogger("kingdoms.kingdom_panels")

# Discord auto-hides ephemeral messages after 15 minutes, but they stay
# on the user's screen until dismissed — Drasah asked for a real
# auto-cleanup of the Postuler confirmations (2026-10-11). The
# interaction webhook token lives 15 minutes: a deletion scheduled
# before that boundary succeeds, later ones fail silently.
_EPHEMERAL_TTL_SECONDS = 840
# The enrollment flow lives in ONE ephemeral bubble: after the final
# confirmation the whole thing must vanish quickly (~30 s) instead of
# staying 14 minutes (Drasah 2026-10-13 postulation-v1 spec).
_CONFIRM_TTL_SECONDS = 30  # type: int
_EPHEMERAL_TASKS: set[asyncio.Task[None]] = set()


def _schedule_ephemeral_delete(
    interaction: discord.Interaction, message: Any, seconds: int = _EPHEMERAL_TTL_SECONDS
) -> None:
    """Best-effort auto-delete of one ephemeral followup (~14 minutes)."""

    async def _delete() -> None:
        await asyncio.sleep(seconds)
        try:
            message_id = int(getattr(message, "id", 0) or 0)
            if message_id:
                await interaction.followup.delete_message(message_id)
        except Exception:
            logger.info("KINGDOM PANELS: ephemeral confirmation already gone")

    try:
        task = asyncio.create_task(_delete())
        _EPHEMERAL_TASKS.add(task)
        task.add_done_callback(_EPHEMERAL_TASKS.discard)
    except Exception:
        logger.info("KINGDOM PANELS: ephemeral TTL task not scheduled")

KINGDOM_MOD = "kingdoms"
ROLE_LORD = "kingdoms_lord"
ROLE_KING = "kingdoms_king"

APPLY_BUTTON_ID = "kingdoms:apply:open"
ROLE_SELECT_ID = "kingdoms:apply:role"
KINGDOM_SELECT_ID = "kingdoms:apply:kingdom"
DECISION_APPROVE_ID = "kingdoms:candidature:approve"
DECISION_PENDING_ID = "kingdoms:candidature:pending"
DECISION_REFUSE_ID = "kingdoms:candidature:refuse"

QUEUE_VALUE = "__queue__"
PANEL_MARKER = "kingdoms:panel:postuler"
SETTINGS_PANEL_MARKER = "kingdoms:panel:parametres"
MARKET_PANEL_MARKER = "kingdoms:panel:marche"
MARKET_CHANNEL = "marche"
SEASON_STATUS_MARKER = "kingdoms:season:status"
SEASON_STATUS_CHANNEL = "saison"
UPDATE_CHANNEL = "update"
CHANGELOG_MARKER = "kingdoms:update:changelog"


async def refresh_changelog(guild: discord.Guild, locale: str) -> bool:
    """Post (or refresh) the kingdoms changelog message in the Update channel."""
    channel = next((c for c in guild.text_channels if c.name.lower() == UPDATE_CHANNEL), None)
    if channel is None:
        return False
    fr = str(locale).lower().startswith("fr")
    items = (
        "💰 Le panneau Marché est en ligne : technologies de combat et actions spéciales"
        " (Explorateur, Corruption, Garde Royale) achetables par le Roi du royaume."
        "\n🛠️ Panneau admin enrichi : déploiement des salons + panels, resynchronisation, "
        "statut de la saison, affectation des joueurs en attente, ajout manuel de royaume — "
        "les actions sensibles demandent une confirmation."
        if fr
        else "💰 The Market panel is live: combat technologies and special actions"
        " (Explorer, Corruption, Royal Guard) purchasable by the kingdom's King."
        "\n🛠️ Richer admin panel: deploy salons + panels, resync, season status, "
        "assign waiting players, add a kingdom manually — sensitive actions ask for confirmation."
    )
    content = f"{items}\n{CHANGELOG_MARKER}"
    for message in await channel_messages(channel):
        if CHANGELOG_MARKER in message_text(message):
            try:
                await message.edit(content=content)
            except Exception:
                logger.warning("KINGDOM PANELS: changelog refresh failed", exc_info=True)
            return True
    await channel.send(content)
    return True


async def post_update_note(guild: discord.Guild, locale: str, note: str) -> bool:
    """Post a dated changelog note in the Update channel."""
    from zoneinfo import ZoneInfo

    channel = next((c for c in guild.text_channels if c.name.lower() == UPDATE_CHANNEL), None)
    if channel is None:
        return False
    try:
        tz = ZoneInfo("Europe/Paris")
    except Exception:
        tz = None
    now = game_now().astimezone(tz) if tz else game_now()
    stamp = now.strftime("%d/%m/%Y %H:%M")
    await channel.send(f"**🕘 Update — {stamp}**\n{note}")
    return True

INSIGHT_URL = re.compile(r"^https?://.+", re.IGNORECASE)
GAME_ID = re.compile(r"^\d{6,20}$")

STRINGS: dict[str, dict[str, Any]] = {
    "en": {
        "apply_button": "📋 Enroll",
        "apply_title": "Kingdoms enrollment",
        "apply_role_king_line": "👑 King — Found your kingdom, run its treasury and lead diplomacy.",
        "apply_role_lord_line": "🛡️ Lord — Join a banner and bear arms for your crown.",
        "roleinfo_king_button": "📖 View the King role",
        "roleinfo_lord_button": "📖 View the Lord role",
        "apply_sending": "⏳ Sending your application…",
        "apply_already_pending": (
            "⛔ You already have a pending application — an admin must "
            "process it before you can send another one."
        ),
        "apply_already_enrolled": (
            "⛔ You are already enrolled in a kingdom this season — "
            "only one application per person."
        ),
        "enroll_already": "⚠️ Already enrolled in the current season.",
        "enroll_service_down": (
            "⚠️ The Kingdoms service is unavailable: the enrollment and the"
            " kingdom DM could NOT be sent — this is an incident, contact an"
            " admin (the role alone was granted)."
        ),
        "role_sheet_king": (
            "# 👑 THE KING — RIGHTS & OBLIGATIONS\n"
            "\n"
            "**Role** — one single King per kingdom.\n"
            "\n"
            "**⚙️ TREASURY — SOLE HOLDER**\n"
            "• Patrol (2 h daily slot, quota/season), combat technologies, Explorer, territory purchase.\n"
            "\n"
            "**⛪ PARISH — SOLE DECISION-MAKER**\n"
            "• Tier upgrade, arranged marriage (💰 token), choice of the lord.\n"
            "\n"
            "**👑💍 ROYAL MARRIAGE — SPECIFIC REGIME**\n"
            "• Cost: 2 marriage points or 2 tokens.\n"
            "• Doubled lock: 48 h / 24 h / 12 h.\n"
            "• +2 ⚙️ to the treasury; civilisation secured for the whole season (even after a defeat).\n"
            "• Announcement in Géopolitique is mandatory.\n"
            "\n"
            "**🐦 CARRIER PIGEON — SOLE RECIPIENT**\n"
            "\n"
            "🚫 A lord can NOT spend the treasury, upgrade the Parish, nor seal an arranged marriage."
        ),
        "role_sheet_lord": (
            "# 🛡️ THE LORD — RIGHTS & OBLIGATIONS\n"
            "\n"
            "**⚔️ COMBAT — YOUR JURISDICTION**\n"
            "• Lord's Day window: Sunday 23:30 → Monday 10:00.\n"
            "• No execution during the window; declaring is allowed if the execution happens after it closes.\n"
            "• Marriage lock = forbidden to attack AND to defend.\n"
            "\n"
            "**💍 MARRIAGE — YOUR DECISION ALONE**\n"
            "• Nobody can marry you off.\n"
            "• 1 marriage point, civilisation drawn from your kingdom's hand, "
            "24 h / 12 h / 6 h lock, exclusivity between kingdoms.\n"
            "\n"
            "**🚫 WHAT YOU CANNOT DO**\n"
            "• Spend the treasury, upgrade the Parish, buy tokens for someone else.\n"
            "\n"
            "**👀 OBSERVATION**\n"
            "• Your marriage is never announced: red username 🔒 then 💍, no bot reminder.\n"
            "\n"
            "📜 Territory and Alliances are readable by every lord — espionage is legal."
        ),
        "choose_role": "Choose your role",
        "choose_kingdom": "Join a kingdom",
        "queue_option": "⏳ Wait for a kingdom",
        "queue_description": "Wait for kingdoms to be created — an admin will assign you later.",
        "no_kingdoms_hint": "No kingdom exists yet — you can wait in the queue.",
        "role_king": "👑 King",
        "role_lord": "🎖️ Lord",
        "kingdom_after_validation": "to be chosen after your application is approved",
        "king_name_dm_title": "👑 Your kingdom's name",
        "king_name_dm_body": (
            "Your King application has been accepted! Click the button "
            "below to choose your kingdom's name (max 40 characters). It "
            "will then be submitted to the admins for validation."
        ),
        "king_name_dm_fallback": "Click the button below to name your kingdom.",
        "king_name_claim_hint": (
            "👑 Free thrones are open — you can also join an existing"
            " kingdom through the dropdown."
        ),
        "king_name_button": "🏷️ Name my kingdom",
        "king_name_modal_title": "Your kingdom's name",
        "king_name_field": "Kingdom name (max 40 characters)",
        "king_name_state_invalid": (
            "No pending King application found for you — apply again or "
            "ask an admin (a season relaunch may have reset enrollments)."
        ),
        "king_name_dm_received": (
            "Your kingdom **{0}** has been proposed — it now awaits admin validation."
        ),
        "king_name_dm_error": (
            "The kingdom could not be created: {0}.\nTry again with another name "
            "(one line, max 40 characters)."
        ),
        "enroll_king_awaiting_name": (
            "👑 King enrolled — they will receive a DM to name their kingdom."
        ),
        "enroll_king_awaiting_kingdom": (
            "👑 King validated — they will receive a DM to choose their kingdom."
        ),
        "king_claim_dm_title": "👑 Choose your kingdom",
        "king_claim_dm_body": (
            "Your King application has been accepted! The kingdoms are "
            "imposed this season — pick your throne below."
        ),
        "king_claim_placeholder": "Choose your kingdom",
        "king_claim_done": "You now reign over **{0}**!",
        "king_claim_failed": "The claim failed — {0}.",
        "king_awaiting_kingdom_title": "👑 King without a kingdom yet",
        "king_awaiting_kingdom_body": (
            "Your King application has been accepted! No kingdom is "
            "available yet — you will be able to claim a throne as soon "
            "as one opens."
        ),
        "insight_field": "AoE II Insight link",
        "insight_placeholder": "https://www.aoe2insight.com/…",
        "game_id_field": "Game ID",
        "game_id_placeholder": "12345678",
        "smurfs_field": "Other AoE II Insight accounts (smurfs)",
        "smurfs_placeholder": "https://www.aoe2insight.com/… (one per line, optional)",
        "summary_title": "📋 Review your application",
        "summary_role": "Role",
        "summary_kingdom": "Kingdom",
        "summary_queue": "Status",
        "queue_value": "waiting for a kingdom",
        "summary_insight": "AoE II Insight",
        "summary_game_id": "Game ID",
        "summary_smurfs": "Declared smurf accounts",
        "rules_label": "I have read and I accept the rules",
        "submit": "✅ I accept the rules — send my application",
        "cancel": "Cancel",
        "bad_insight": "The AoE II Insight link must be a valid URL.",
        "bad_game_id": "The game ID must be 6 to 20 digits.",
        "cancelled": "Application cancelled.",
        "sent": "Your application has been sent — an admin will review it.",
        "sent_ttl": "*This message disappears by itself in a few moments.*",
        "profile_created": "Your profile has been created in your profile salon.",
        "candidature_title": "📋 New enrollment application",
        "candidature_role": "Requested role",
        "candidature_kingdom": "Kingdom",
        "candidature_queue": "Status",
        "candidature_insight": "AoE II Insight",
        "candidature_game_id": "Game ID",
        "decided": "The application has been marked {}.",
        "approved": "✅ validated",
        "pending": "⏳ pending",
        "refused": "❌ refused",
        "role_assigned": "The {} role has been assigned.",
        "no_service": "The enrollment service is not available right now.",
        "enroll_failed": "Enrollment failed ({}).",
        "enroll_queued": "The player is now waiting in the queue.",
        "enrolled_kingdom": "Enrolled in kingdom {}.",
        "settings_title": "⚙️ Kingdoms — settings",
        "welcome_title": "🏰 Welcome to Kingdoms — Season II!",
        "welcome_body": (
            "Your enrollment has been validated. Read the rules, present yourself in Présentation,"
            " and good luck on the battlefield!"
        ),
        "welcome_fallback": "(Sent here because your private messages are closed.)",
        "season_status_title": "📊 Kingdoms — Season II status",
        "season_status_kingdoms": "👑 Kingdoms",
        "season_status_queue": "⏳ Waiting players",
        "season_status_empty": "none yet",
        "season_status_hint": "This message is refreshed automatically by the bot.",
        "market_title": "💰 Kingdom Market",
        "market_hint_panel": (
            "👑 Only the King of a kingdom can buy — every purchase debits "
            "the kingdom treasury immediately (cost shown per article)."
        ),
        "market_fiche_input": "Article sheet (read only)",
        # cartes-tcg-v2 (Drasah 26/10): the revealed card carries its
        # own buttons — Buy / Cancel.
        "market_buy_button": "✅ Buy",
        "market_cancel_button": "❌ Cancel",
        "market_cancelled": "Purchase cancelled — the card goes back under the merchant's stall.",
        "market_fiche_effect": "**__EFFECT :__**\n> {0}",
        "market_fiche_cost": "**__COST :__** {0} ⚙️",
        "market_fiche_wallet": "**__CURRENT TREASURY :__** {0} ⚙️",
        "market_fiche_left": "**__LEFT THIS SEASON :__** {0}/{1}",
        "market_fiche_king_only": "*👑 King only — debited from the treasury immediately.*",
        "market_effect": {
            "embuscade": (
                "Declare an exceptional attack without spending an attack "
                "point. Defending an ambush also uses an exceptional defence."
            ),
            "traquenard": (
                "On use: the AI you face becomes Easy for a cumulative 2h "
                "window per activation, and the target kingdom's living "
                "lockouts (marriages, exploration, tavern drink) gain a "
                "one-shot +2h."
            ),
            "contre_espionnage": (
                "When attacking, you may declare the attack in the name of "
                "any other lord, except a lord from the kingdom you attack. "
                "Your identity is revealed 15 minutes before the game."
            ),
            "sabotage": (
                "Removes one civilization choice from your opponent during a "
                "confrontation. You may sabotage at most two civilizations "
                "per encounter."
            ),
            "jeu_d_armes": (
                "Buys ONE Arms-mastery token. Use it from the Chambre des "
                "comptes: +1 permanent AI level (until the season ends) on "
                "your defence bot — cap 5, reached: your Patrols become "
                "Reinforced (3h). The lord who uses it cuts 1h off his "
                "next normal attack's declaration delay (no Embuscade); "
                "not stackable — one active Arms mastery per lord."
            ),
            "explorateur": (
                "Buys ONE Explorateur token. Use it from the Chambre des "
                "comptes: the chosen lord is locked for 48h (🔒 no attack, no "
                "defence) then the kingdom receives a brand-new map. Once per "
                "season."
            ),
            "corruption": (
                "Buys ONE Corruption token. Use it from the Chambre des "
                "comptes: instantly transfers an enemy territory to your "
                "kingdom, no combat. Blocked if the map is under Royal Guard. "
                "2 per season."
            ),
            "garde_royale": (
                "Buys ONE Royal Guard token (several may be held at once, "
                "no limit). The King then places it from the Remparts "
                "salon: 12h of immunity on ONE chosen map."
            ),
            "patrouille": (
                "Unlocks ONE patrol slot (slot 1, then slot 2). The King "
                "places the daily 2h window from the Remparts salon — "
                "fixed for the cycle, redefined on the Lord's Day "
                "(3h when Reinforced)."
            ),
            "mariage_arrange": (
                "A 💰 token to consume at the Parish: arranged marriage of a "
                "lord of your choice with an unmarried civilization (6h lock)."
            ),
        },
        "market_bought": "✅ Purchased: **{0}** — the treasury holds {1} ⚙️ left.",
        "market_bought_detail": "✅ Purchased: **{0}** — {1}\nThe treasury holds {2} ⚙️ left.",
        "market_bought_left": "\nLeft this season: {0}/{1}.",
        "market_receipt_title": "🧾 Receipt — this session's purchases",
        "market_receipt_ledger_help_named": (
            "🏛️ Find every one of your purchases in the Chamber of Accounts — "
            "**Le-Royaume** panel: {mention}"
        ),
        "market_receipt_ledger_help": (
            "🏛️ Find every one of your purchases in the Chamber of Accounts — "
            "the **Le-Royaume** panel of your kingdom."
        ),
        "market_err_missing": "❌ Insufficient treasury — you are {0} ⚙️ short.",
        "market_err_limit_reached": "❌ Season limit reached ({0}/{1}).",
        "market_ledger_button": "🏛️ Chambre des comptes",
        "market_ledger_title": "🏛️ Chambre des comptes — {0}",
        "market_ledger_input": "Season register (read only)",
        "market_ledger_summary": "Season balance — spent: {0} ⚙️ · treasury: {1} ⚙️",
        "market_ledger_limits": "Limits — {0}",
        "market_ledger_empty": "No purchase yet.",
        "market_ledger_purchases_title": "Purchases",
        "market_hist_achats_button": "📜 Purchase history",
        "market_hist_actions_button": "⚔️ Action history",
        "market_hist_achats_title": "Purchase history",
        "market_hist_actions_title": "Action history",
        "market_hist_actions_empty": "No card used yet.",
        "market_action_line": "{0} {1} — {2} · {3}",
        "market_ledger_cards_title": "Cards in hand",
        "market_ledger_cards_empty": "No card in hand right now.",
        "market_ledger_card_line": "{0} **{1}** — ×{2}",
        "market_ledger_line": "{0} {1} — {2} · {3} ⚙️ · {4}",
        "market_card_effect": "Effect: {0}",
        "market_card_usage": "Usage: {0}",
        "market_usage": {
            "embuscade": (
                "In « Declare an attack », you choose between a classic "
                "attack or an ambush."
            ),
            "traquenard": (
                "Use it from the Salle du conseil (or the Chambre des "
                "comptes): the AI faced becomes Easy for a cumulative 2h "
                "window per activation, and the target kingdom's living "
                "lockouts (marriages, exploration, tavern drink) gain a "
                "one-shot +2h."
            ),
            "contre_espionnage": (
                "When declaring the attack, you can use the "
                "Counter-espionage."
            ),
            "sabotage": (
                "Used after ordering your 3 civilizations against an "
                "opponent — the « Sabotage » button becomes available."
            ),
            "jeu_d_armes": (
                "Use it from the Chambre des comptes: your defence bot gains "
                "+1 permanent AI level on the spot (cap 5) — and your next "
                "normal attack rides with 1h less of declaration delay "
                "(no Embuscade)."
            ),
            "explorateur": (
                "Use it from the Chambre des comptes: choose the lord to send "
                "exploring (48h lock) — the map comes at the end."
            ),
            "corruption": (
                "Use it from the Chambre des comptes: choose the enemy "
                "territory to corrupt — the token is only consumed once the "
                "steal lands."
            ),
        },
        "market_ledger_emoji": {
            "embuscade": "🥷",
            "traquenard": "🪤",
            "contre_espionnage": "🕵️",
            "sabotage": "🗡️",
            "jeu_d_armes": "🧪",
            "explorateur": "🛡️",
            "corruption": "🧨",
            "garde_royale": "🛡️",
            "patrouille": "🛡️",
            "mariage_arrange": "💒",
        },
        # marche-crier-off-v1 (Drasah 29/10): one merchant stall, four
        # shelves (his taxonomy + order), all buttons same colour. The
        # crier line is gone (Drasah asked for its removal live).
        "market_section_ia": "🤖 AI defense / attack management",
        "market_section_defense": "🛡️ Kingdom defense",
        "market_section_attaque": "⚔️ Attack improvements",
        "market_section_speciales": "✨ Special actions",
        "market_hint": (
            "Only the King of a kingdom can buy. Every purchase debits the"
            " kingdom's tech-point treasury ({} ⚙️ per purchase)."
        ),
        "market_not_king": "Only Kings can buy on the market.",
        "market_no_service": "The market is not available right now.",
        "market_buy_ok": "✅ Purchased: **{}** — treasury left: {} ⚙️",
        "market_buy_ok_territory": "✅ Purchased: **{}** — {}.",
        "market_err_insufficient": "❌ Not enough tech points.",
        "market_err_limit": "❌ The per-season purchase limit is reached.",
        "market_err_protected": "❌ This territory is protected.",
        "market_err_guard_active": "❌ This map is already shielded by a Royal Guard.",
        "market_err_already_married": "❌ This lord is already married.",
        "market_err_civ_taken": "❌ This civilization is already claimed by an active marriage.",
        "market_err_civ_unknown": "❌ Marriage refused.",
        "market_choose_slot": "🛡️ Choose the daily patrol slot (2h, Paris time):",
        "market_slot_line": "{:02d}:00 → {:02d}:00",
        "market_patrouille_ok": (
            "✅ Purchased: **Patrol** — daily slot {:02d}:00 → {:02d}:00"
            " — treasury left: {} ⚙️"
        ),
        "market_choose_lord": "💍 Choose the lord to wed:",
        "market_choose_explorer": "🗺️ Choose the lord to send exploring (48h):",
        "market_choose_civ": "👰 Choose the civilization of the arranged marriage:",
        "market_mariage_ok": (
            "✅ Arranged marriage sealed: **{}** is exclusive to your kingdom"
            " — treasury left: {} ⚙️"
        ),
        "market_err_unknown": "❌ Purchase refused ({}).",
        "market_arranged_token_ok": (
            "💒 Arranged-marriage token bought — stock: {}. Consume it at the Parish."
        ),
        "market_garde_token_ok": (
            "🛡️ Royal Guard bought — in reserve: {}. Place it from the 🧱 Remparts salon."
        ),
        "market_patrouille_slot_ok": (
            "🛡️ Patrol slot {} unlocked — place the window from the 🧱 Remparts salon."
        ),
        "market_use_button": "🚀 Use",
        "market_corruption_token_ok": (
            "🧨 Corruption token bought — in reserve: {}. Use it from the "
            "🏛️ Chambre des comptes."
        ),
        "market_jeu_d_armes_token_ok": (
            "🧪 Arms mastery bought — in reserve: {}. Use it from the "
            "🏛️ Chambre des comptes (+1 AI level)."
        ),
        "market_explorateur_token_ok": (
            "🛡️ Explorer bought — in reserve: {}. Use it from the "
            "🏛️ Chambre des comptes."
        ),
        "market_use_jeu_d_armes_ok": (
            "🧪 Arms mastery used — your defence bot reaches level {}/5."
        ),
        "jeu_darmes_card_title": "🧪 Arms Mastery",
        "jeu_darmes_effect_ia": (
            "On use, raises your AI's level by 1 for the whole season."
        ),
        "jeu_darmes_effect_cap": (
            "Once your AI sits at its max difficulty, it upgrades your "
            "Patrol into a Reinforced Patrol."
        ),
        "jeu_darmes_effect_patrouille": (
            "Reinforced Patrol: +1h of slot on your patrols (3h total)."
        ),
        "jeu_darmes_effect_rush": (
            "The lord using Arms Mastery cuts 1h off his next normal "
            "attack's declaration delay; after that declaration the delay "
            "goes back to normal. Never works with an Embuscade."
        ),
        "jeu_darmes_owned": "You own: **{0}**",
        "jeu_darmes_level": "Your current AI level: **{0}/5 {1}**",
        "jeu_darmes_button": "🧪 Arms Mastery",
        "jeu_darmes_activate_button": "✅ Activate",
        "jeu_darmes_cancel_button": "❌ Cancel",
        "jeu_darmes_use_ok": (
            "🧪 Arms mastery used — your defence bot reaches level {0}/5 "
            "{1}. Your next normal attack rides with 1h less of declaration "
            "delay."
        ),
        "jeu_darmes_use_ok_rush_only": (
            "🧪 Arms mastery used — your AI already sits at its max level: "
            "only the 1h cut on your next normal attack applies."
        ),
        "jeu_darmes_already_active": (
            "🧪 You already hold an active Arms mastery — it will apply to "
            "your next normal attack."
        ),
        "jeu_darmes_no_stock": "🧪 No Arms mastery in reserve — buy one at the Market.",
        "jeu_darmes_channel_note": (
            "🧪 **{0}** has activated an **Arms mastery**: their next "
            "normal attack declaration rides with a 1-hour cut, valid "
            "for ONE attack!"
        ),
        "ffa_join_button": "🗺️ Partir en expédition",
        "ffa_join_note": (
            "✅ **{lord}** holds an Expedition slot — **{time}** (Paris time). "
            "{count}/{max} participant(s)."
        ),
        "ffa_left_note": "🚪 **{lord}** released their slot — {count}/{max} participant(s).",
        "ffa_not_open": "❌ No Expedition is open for enrollment right now.",
        "ffa_full": "❌ The Expedition is full ({max} participants).",
        "ffa_kingdom_full": (
            "❌ Your kingdom already holds a slot (mode: one lord per kingdom)."
        ),
        "ffa_locked": (
            "❌ You are locked (a fresh Explorateur 48h lock or a missed FFA) — "
            "you cannot enroll."
        ),
        "ffa_announce": (
            "🧭 **Expedition — Saturday {time} (Paris time)**\n"
            "One FREE {duration}-minute game against the Gaïa AI and the other "
            "participants — {max} slots, mode: {mode}. Click "
            "**« Partir en expédition »** to reserve yours (first come, first "
            "served; click again to release it)."
        ),
        "ffa_start": (
            "🧭 **The Expedition starts now** — {count} participant(s), "
            "{duration} minutes. Good luck!"
        ),
        "ffa_mode_one": "one lord per kingdom",
        "ffa_mode_free": "free slots",
        # restructuration-serveur-v1 c (Drasah 19/10): the ephemeral FFA salon.
        "ffa_salon_title": "🗺️ Expédition",
        "market_err_no_points": "❌ The kingdom holds no marriage point.",
        "market_err_no_token": (
            "❌ No arranged marriage in stock — buy a token at the Market."
        ),
        "church_marry_intro": "👰 Choose the civilization of your marriage:",
        "church_marry_ok": (
            "💍 Marriage sealed: **{0}** — lock {1}h, Offrande +{2} ⚙️."
        ),
        "mercenary_refund_dm": (
            "⚔️ The Mercenary Chief calls your contract back: **{0}** was "
            "just sealed in marriage — your mercenary copy is stripped and "
            "your purse is refunded **{1} écu(s)**."
        ),
        "church_marry_royal_ok": (
            "👑💍 Marriage sealed: **{0}** becomes your Queen — royal lock"
            " {1}h · +2 ⚙️ to the treasury · secured for the whole season."
        ),
        "church_marry_royal_arranged_ok": (
            "👑💍 Royal arranged marriage: **{0}** becomes the Queen — royal"
            " lock {1}h · +2 ⚙️ · secured for the whole season."
        ),
        "church_err_royal_points": (
            "❌ A royal marriage costs TWO marriage points — the kingdom"
            " does not hold enough."
        ),
        "church_err_royal_token": (
            "❌ A royal arranged marriage costs TWO tokens — the kingdom"
            " does not hold enough."
        ),
        "royal_wedding_announce": (
            "👑💍 **Grand royal wedding** — {0} has taken **{1}** as Queen"
            " of the Kingdom of {2}! 📑 The details live in the « Learn"
            " more » thread below."
        ),
        "royal_wedding_couple": "{0}, promised lady of the {1} civilization",
        "royal_wedding_more_title": "Learn more",
        "royal_wedding_more_body": (
            "📑 **Learn more — the royal wedding of the Kingdom of {1}**\n"
            "🎯 **Gains** —\n"
            "🏴 **{0} civilization** ⏳ **All season long**\n"
            "⚙️ **+2 in the technology treasury**.\n"
            "🔒 **Lock** — {2}h nuptials: no attacks, no defense"
            " until **{3}**."
        ),
        "church_marry_kingdom_none": "You belong to no kingdom of the season.",
        "church_arrange_king_only": "Only the King consumes an arranged marriage.",
        "church_upgrade_king_only": "Only the King upgrades the Parish.",
        "church_upgrade_ok": (
            "⛪ Parish upgraded: **{0}** (tier {1}/{2}) — treasury left: {3} ⚙️"
        ),
        "church_upgrade_max": "❌ The Parish already sits at the top tier.",
        "cathedral_consecrate_button": "⛪ Consecrate a Lieu Sacrée (3 ⚙️)",
        "cathedral_consecrate_choose": "⛪ Choose the territory to consecrate:",
        "cathedral_consecrate_king_only": "❌ Only the King consecrates a Lieu Sacrée.",
        "cathedral_consecrate_tier": "❌ The consecration requires the Cathédrale tier.",
        "cathedral_consecrate_none": "❌ No territory is open to a consecration right now.",
        "cathedral_consecrate_ok": (
            "⛪ The chantier runs on **{0}** — verdict on {1} (Paris). "
            "Until then the territory resists every technology; a classic attack can destroy the chantier."
        ),
        "cathedral_consecrated": (
            "⛪ **{0}** consecrates a Lieu Sacrée on **{1}** — "
            "72h of chantier: immune to technologies, attackable by classic attacks."
        ),
        "cathedral_sacred": (
            "⛪ **{0}**'s Lieu Sacrée on **{1}** survived its chantier — the territory is now "
            "**SACRED**: immune to everything, forever."
        ),
        "church_err_not_in_hand": (
            "❌ This civilization is not in your Alliances hand."
        ),
        "church_err_no_hand": (
            "❌ Your kingdom holds no free civilization — the hand is"
            " redrawn at the next Lord's Day."
        ),
        "market_choose_corrupt": "🎯 Choose the territory to corrupt:",
        "market_choose_guard": "🛡️ Choose the territory to shield:",
        "market_no_options": "No option is available right now.",
        "market_territory_line": "{} — owner {}",
        "market_tech": {
            "embuscade": "Ambush",
            "traquenard": "Trap",
            "contre_espionnage": "Counter-espionage",
            "sabotage": "Sabotage",
            "jeu_d_armes": "Arms mastery",
        },
        "market_action": {
            "explorateur": "Explorer",
            "corruption": "Corruption",
            "garde_royale": "Royal Guard",
            "patrouille": "Patrol",
            "mariage_arrange": "Arranged marriage",
        },
    },
    "fr": {
        "apply_button": "📋 S'inscrire",
        "apply_title": "Inscription Kingdoms",
        "apply_role_king_line": "👑 Roi — Fonde ton royaume, gère son trésor et mène la diplomatie.",
        "apply_role_lord_line": "🛡️ Seigneur — Rejoins une bannière et porte les armes pour ta couronne.",
        "roleinfo_king_button": "📖 Voir le rôle Roi",
        "roleinfo_lord_button": "📖 Voir le rôle Seigneur",
        "apply_sending": "⏳ Envoi de ta candidature…",
        "apply_already_pending": (
            "⛔ Tu as déjà une candidature en attente — un admin doit "
            "la traiter avant que tu puisses en renvoyer une."
        ),
        "apply_already_enrolled": (
            "⛔ Tu es déjà inscrit dans un royaume cette saison — "
            "une seule candidature par personne."
        ),
        "enroll_already": "⚠️ Déjà inscrit dans la saison courante.",
        "enroll_service_down": (
            "⚠️ Le service Kingdoms est indisponible : l'inscription et le MP"
            " du royaume n'ont PAS pu être envoyés — c'est un incident, préviens"
            " un admin (seul le rôle a été attribué)."
        ),
        "role_sheet_king": (
            "# 👑 LE ROI — DROITS & OBLIGATIONS\n"
            "\n"
            "**Rôle** — un seul Roi par royaume.\n"
            "\n"
            "**⚙️ TRÉSOR — SEUL DÉTENTEUR**\n"
            "• Patrouille (créneau quotidien 2 h, quota/saison), technologies "
            "de combat, Explorateur, achat de territoire.\n"
            "\n"
            "**⛪ PAROISSE — SEUL DÉCISIONNAIRE**\n"
            "• Amélioration de palier, mariage arrangé (jeton 💰), choix du seigneur.\n"
            "\n"
            "**👑💍 MARIAGE ROYAL — RÉGIME SPÉCIFIQUE**\n"
            "• Coût : 2 points de mariage ou 2 jetons.\n"
            "• Verrou doublé : 48 h / 24 h / 12 h.\n"
            "• +2 ⚙️ au trésor ; civilisation sécurisée toute la saison, même "
            "après une défaite.\n"
            "• Annonce en Géopolitique obligatoire.\n"
            "\n"
            "**🐦 PIGEON-VOYAGEUR — SEUL DESTINATAIRE**\n"
            "\n"
            "🚫 Un seigneur ne peut PAS dépenser le trésor, améliorer la Paroisse ni sceller un mariage arrangé."
        ),
        "role_sheet_lord": (
            "# 🛡️ LE SEIGNEUR — DROITS & OBLIGATIONS\n"
            "\n"
            "**⚔️ COMBAT — TA JURIDICTION**\n"
            "• Fenêtre du Jour du Seigneur : dimanche 23 h 30 → lundi 10 h.\n"
            "• Aucune exécution pendant la fenêtre ; la déclaration est permise "
            "si l'exécution a lieu après la fermeture.\n"
            "• Verrou mariage = interdit d'attaquer ET de défendre.\n"
            "\n"
            "**💍 MARIAGE — TA DÉCISION SEULE**\n"
            "• Personne ne peut te marier.\n"
            "• 1 point de mariage, civilisation issue de la main du royaume, "
            "verrou 24 h / 12 h / 6 h, exclusivité entre royaumes.\n"
            "\n"
            "🚫 **CE QUE TU NE PEUX PAS FAIRE**\n"
            "• Dépenser le trésor, améliorer la Paroisse, acheter des jetons pour un autre.\n"
            "\n"
            "👀 **OBSERVATION**\n"
            "• Ton mariage n'est jamais annoncé : pseudo rouge 🔒 puis 💍, aucun rappel du bot.\n"
            "\n"
            "📜 Territoire et Alliances lisibles par tous les seigneurs — l'espionnage est légal."
        ),
        "choose_role": "Choisissez votre rôle",
        "choose_kingdom": "Rejoindre un royaume",
        "queue_option": "⏳ En attente",
        "queue_description": "Attendre la création des royaumes — un admin vous affectera plus tard.",
        "no_kingdoms_hint": "Aucun royaume n'existe encore — vous pouvez vous mettre en attente.",
        "role_king": "👑 Roi",
        "role_lord": "🎖️ Seigneur",
        "kingdom_after_validation": "à choisir après la validation de ta candidature",
        "king_name_dm_title": "👑 Nom de ton royaume",
        "king_name_dm_body": (
            "Ta candidature de Roi a été acceptée ! Clique sur le bouton "
            "ci-dessous pour choisir le nom de ton royaume (max 40 "
            "caractères). Il sera ensuite soumis à la validation des admins."
        ),
        "king_name_dm_fallback": "Clique sur le bouton ci-dessous pour nommer ton royaume.",
        "king_name_claim_hint": (
            "👑 Des trônes sont libres — tu peux aussi rejoindre un royaume"
            " existant via le menu déroulant."
        ),
        "king_name_button": "🏷️ Nommer mon royaume",
        "king_name_modal_title": "Nom de ton royaume",
        "king_name_field": "Nom du royaume (max 40 caractères)",
        "king_name_state_invalid": (
            "Aucune candidature de Roi en attente pour toi — postule à nouveau "
            "ou demande à un admin (un relancement de saison a pu réinitialiser "
            "les inscriptions)."
        ),
        "king_name_dm_received": (
            "Ton royaume **{0}** a été proposé — il est en attente de validation "
            "par les admins."
        ),
        "king_name_dm_error": (
            "Impossible de créer le royaume : {0}.\nRéessaie avec un autre nom "
            "(une seule ligne, max 40 caractères)."
        ),
        "enroll_king_awaiting_name": (
            "👑 Roi inscrit — il va recevoir un MP pour nommer son royaume."
        ),
        "enroll_king_awaiting_kingdom": (
            "👑 Roi validé — il va recevoir un MP pour choisir son royaume."
        ),
        "king_claim_dm_title": "👑 Choisis ton royaume",
        "king_claim_dm_body": (
            "Ta candidature de Roi a été acceptée ! Les royaumes sont "
            "imposés cette saison — choisis ton trône ci-dessous."
        ),
        "king_claim_placeholder": "Choisis ton royaume",
        "king_claim_done": "Tu règnes désormais sur **{0}** !",
        "king_claim_failed": "La réclamation a échoué — {0}.",
        "king_awaiting_kingdom_title": "👑 Roi sans royaume pour l'instant",
        "king_awaiting_kingdom_body": (
            "Ta candidature de Roi a été acceptée ! Aucun royaume n'est "
            "encore disponible — tu pourras réclamer un trône dès qu'un "
            "royaume sera libre."
        ),
        "insight_field": "Lien AoE II Insight",
        "insight_placeholder": "https://www.aoe2insight.com/…",
        "game_id_field": "ID de jeu",
        "game_id_placeholder": "12345678",
        "smurfs_field": "Autres comptes AoE II Insight (smurfs)",
        "smurfs_placeholder": "https://www.aoe2insight.com/… (une par ligne, facultatif)",
        "summary_title": "📋 Vérifiez votre candidature",
        "summary_role": "Rôle",
        "summary_kingdom": "Royaume",
        "summary_queue": "Statut",
        "queue_value": "en attente d'un royaume",
        "summary_insight": "AoE II Insight",
        "summary_game_id": "ID de jeu",
        "summary_smurfs": "Comptes smurfs déclarés",
        "rules_label": "J'ai lu et j'accepte les règles",
        "submit": "✅ J'accepte les règles — envoyer ma candidature",
        "cancel": "Annuler",
        "bad_insight": "Le lien AoE II Insight doit être une URL valide.",
        "bad_game_id": "L'ID de jeu doit contenir 6 à 20 chiffres.",
        "cancelled": "Candidature annulée.",
        "sent": "Votre candidature a été envoyée — un admin l'examinera.",
        "sent_ttl": "*Ce message disparaît de lui-même dans quelques instants.*",
        "profile_created": "Votre profil a été créé dans votre salon de profil.",
        "candidature_title": "📋 Nouvelle candidature",
        "candidature_role": "Rôle demandé",
        "candidature_kingdom": "Royaume",
        "candidature_queue": "Statut",
        "candidature_insight": "AoE II Insight",
        "candidature_game_id": "ID de jeu",
        "decided": "La candidature a été marquée {}.",
        "approved": "✅ validée",
        "pending": "⏳ en attente",
        "refused": "❌ refusée",
        "role_assigned": "Le rôle {} a été attribué.",
        "no_service": "Le service d'inscription n'est pas disponible pour le moment.",
        "enroll_failed": "L'inscription a échoué ({}).",
        "enroll_queued": "Le joueur est maintenant en attente d'un royaume.",
        "enrolled_kingdom": "Inscrit dans le royaume {}.",
        "settings_title": "⚙️ Kingdoms — paramètres",
        "welcome_title": "🏰 Bienvenue dans Kingdoms — Saison II !",
        "welcome_body": (
            "Votre inscription a été validée. Lisez les règles, présentez-vous dans Présentation,"
            " et bonne chance sur le champ de bataille !"
        ),
        "welcome_fallback": "(Envoyé ici car vos messages privés sont fermés.)",
        "season_status_title": "📊 Kingdoms — Statut de la Saison II",
        "season_status_kingdoms": "👑 Royaumes",
        "season_status_queue": "⏳ Joueurs en attente",
        "season_status_empty": "aucun pour le moment",
        "season_status_hint": "Ce message est mis à jour automatiquement par le bot.",
        "market_title": "💰 Marché du Royaume",
        "market_hint_panel": (
            "👑 Seul le Roi d'un royaume peut acheter — chaque achat débite "
            "immédiatement le trésor du royaume (coût affiché par article)."
        ),
        "market_fiche_input": "Fiche article (lecture seule)",
        # cartes-tcg-v2 (Drasah 26/10): la carte révélée porte ses
        # propres boutons — Acheter / Annuler.
        "market_buy_button": "✅ Acheter",
        "market_cancel_button": "❌ Annuler",
        "market_cancelled": "Achat annulé — la carte retourne sous l'étal du marchand.",
        "market_fiche_effect": "**__EFFET :__**\n> {0}",
        "market_fiche_cost": "**__COÛT :__** {0} ⚙️",
        "market_fiche_wallet": "**__TRÉSORERIE ACTUELLE :__** {0} ⚙️",
        "market_fiche_left": "**__RESTE CETTE SAISON :__** {0}/{1}",
        "market_fiche_king_only": "*👑 Réservé au Roi — débité immédiatement du trésor.*",
        "market_effect": {
            "embuscade": (
                "Déclare une attaque exceptionnelle sans point d'attaque. "
                "Défendre une embuscade utilise aussi une défense "
                "exceptionnelle."
            ),
            "traquenard": (
                "À l'usage : l'IA affrontée devient Facile durant une "
                "fenêtre cumulée de 2h par activation, et les verrous "
                "vivants du royaume ciblé (mariages, exploration, boisson "
                "de taverne) prennent +2h en one-shot."
            ),
            "contre_espionnage": (
                "Lorsque vous attaquez, vous pouvez la déclarer au nom de "
                "n'importe quel autre seigneur, excepté un seigneur provenant "
                "du royaume que vous attaquez. Ton identité est révélée "
                "15 min avant la partie."
            ),
            "sabotage": (
                "Permet de retirer un choix de civilisation à votre adversaire "
                "lors d'une confrontation. Vous ne pouvez saboter que deux "
                "civilisations maximum par rencontre."
            ),
            "jeu_d_armes": (
                "Achète UN jeton Jeu d'armes. Utilise-le depuis la Chambre "
                "des comptes : +1 niveau d'IA permanent (jusqu'à la fin de "
                "saison) sur ton bot de défense — plafond 5, atteint : les "
                "Patrouilles deviennent Renforcées (3h). Le seigneur qui "
                "l'utilise réduit de 1h le délai de déclaration de sa "
                "prochaine attaque normale (pas d'embuscade) ; non "
                "cumulable — un seul Jeu d'armes actif par seigneur."
            ),
            "explorateur": (
                "Achète UN jeton Explorateur. Utilise-le depuis la Chambre "
                "des comptes : le seigneur choisi est verrouillé 48h (🔒 ni "
                "attaque ni défense) puis le royaume reçoit une map inédite. "
                "1 par saison."
            ),
            "corruption": (
                "Achète UN jeton Corruption. Utilise-le depuis la Chambre des "
                "comptes : transfert d'un territoire adverse vers ton royaume, "
                "sans combat. Bloquée si la map est sous Garde Royale. "
                "2 par saison."
            ),
            "garde_royale": (
                "Achète UNE Garde Royale en réserve (plusieurs gardes "
                "possibles, sans limite). Le Roi la pose ensuite depuis "
                "le salon Remparts : 12h d'immunité sur UNE map au choix."
            ),
            "patrouille": (
                "Débloque UN emplacement de patrouille (slot 1 puis slot 2). "
                "Le Roi pose le créneau quotidien de 2h depuis le salon "
                "Remparts — figé pour le cycle, redéfini le Jour du "
                "Seigneur (3h si Renforcée)."
            ),
            "mariage_arrange": (
                "Jeton 💰 à consommer à la Paroisse : mariage arrangé d'un "
                "seigneur de ton choix avec une civilisation non mariée "
                "(verrou 6h)."
            ),
        },
        "market_bought": "✅ Acheté : **{0}** — il reste {1} ⚙️ au trésor.",
        "market_bought_detail": "✅ Acheté : **{0}** — {1}\nIl reste {2} ⚙️ au trésor.",
        "market_bought_left": "\nReste cette saison : {0}/{1}.",
        "market_receipt_title": "🧾 Reçu — achats de la session",
        "market_receipt_ledger_help_named": (
            "🏛️ Retrouve l'ensemble de tes achats dans la Chambre des comptes "
            "— panneau **Le-Royaume** : {mention}"
        ),
        "market_receipt_ledger_help": (
            "🏛️ Retrouve l'ensemble de tes achats dans la Chambre des comptes "
            "— panneau **Le-Royaume** de ton royaume."
        ),
        "market_err_missing": "❌ Trésorerie insuffisante — il te manque {0} ⚙️.",
        "market_err_limit_reached": "❌ Limite de saison atteinte ({0}/{1}).",
        "market_ledger_button": "🏛️ Chambre des comptes",
        "market_ledger_title": "🏛️ Chambre des comptes — {0}",
        "market_ledger_input": "Registre de la saison (lecture seule)",
        "market_ledger_summary": "Bilan de saison — dépensé : {0} ⚙️ · trésor : {1} ⚙️",
        "market_ledger_limits": "Limites — {0}",
        "market_ledger_empty": "Aucun achat pour le moment.",
        "market_ledger_purchases_title": "Achats",
        "market_hist_achats_button": "📜 Historique achats",
        "market_hist_actions_button": "⚔️ Historique actions",
        "market_hist_achats_title": "Historique des achats",
        "market_hist_actions_title": "Historique des actions",
        "market_hist_actions_empty": "Aucune carte utilisée pour le moment.",
        "market_action_line": "{0} {1} — {2} · {3}",
        "market_ledger_cards_title": "Cartes en main",
        "market_ledger_cards_empty": "Aucune carte en main pour le moment.",
        "market_ledger_card_line": "{0} **{1}** — ×{2}",
        "market_ledger_line": "{0} {1} — {2} · {3} ⚙️ · {4}",
        "market_card_effect": "Effet : {0}",
        "market_card_usage": "Usage : {0}",
        "market_usage": {
            "embuscade": (
                "Dans « Déclarer une attaque », vous avez le choix entre une "
                "attaque classique ou une embuscade."
            ),
            "traquenard": (
                "S'utilise depuis la Salle du conseil (ou la Chambre des "
                "comptes) : l'IA affrontée devient Facile durant une fenêtre "
                "cumulée de 2h par activation, et les verrous vivants du "
                "royaume ciblé (mariages, exploration, boisson de taverne) "
                "prennent +2h en one-shot."
            ),
            "contre_espionnage": (
                "À la déclaration de l'attaque, vous pouvez utiliser le "
                "Contre-espionnage."
            ),
            "sabotage": (
                "S'utilise après avoir choisi l'ordre de vos 3 civilisations "
                "contre un adversaire — le bouton « Saboter » devient "
                "disponible."
            ),
            "jeu_d_armes": (
                "S'utilise depuis la Chambre des comptes : ton bot de défense "
                "gagne immédiatement +1 niveau d'IA permanent (plafond 5) et "
                "ta prochaine attaque normale partira avec 1h de délai en "
                "moins (pas d'embuscade)."
            ),
            "explorateur": (
                "S'utilise depuis la Chambre des comptes : choisis le seigneur "
                "à envoyer explorer (verrou 48h) — la map arrive au terme."
            ),
            "corruption": (
                "S'utilise depuis la Chambre des comptes : choisis le "
                "territoire adverse à corrompre — le jeton n'est consommé "
                "qu'une fois le vol réussi."
            ),
        },
        "market_ledger_emoji": {
            "embuscade": "🥷",
            "traquenard": "🪤",
            "contre_espionnage": "🕵️",
            "sabotage": "🗡️",
            "jeu_d_armes": "🧪",
            "explorateur": "🛡️",
            "corruption": "🧨",
            "garde_royale": "🛡️",
            "patrouille": "🛡️",
            "mariage_arrange": "💒",
        },
        # marche-crier-off-v1 (Drasah 29/10): une seule table de marchand,
        # quatre rayons (sa taxonomie + son ordre), boutons uniformes.
        # La phrase du crieur est retirée (demande live de Drasah).
        "market_section_ia": "🤖 Gestion de la défense / attaque IA",
        "market_section_defense": "🛡️ Défense du royaume",
        "market_section_attaque": "⚔️ Amélioration de l'attaque",
        "market_section_speciales": "✨ Actions spéciales",
        "market_hint": (
            "Seul le Roi d'un royaume peut acheter. Chaque achat débite le"
            " trésor de points de tech du royaume ({} ⚙️ par achat)."
        ),
        "market_not_king": "Seuls les Rois peuvent acheter au marché.",
        "market_no_service": "Le marché n'est pas disponible pour le moment.",
        "market_buy_ok": "✅ Achat effectué : **{}** — trésor restant : {} ⚙️",
        "market_buy_ok_territory": "✅ Achat effectué : **{}** — {}.",
        "market_err_insufficient": "❌ Pas assez de points de tech.",
        "market_err_limit": "❌ La limite d'achats pour cette saison est atteinte.",
        "market_err_protected": "❌ Ce territoire est protégé.",
        "market_err_guard_active": "❌ Cette map est déjà protégée par une Garde Royale.",
        "market_err_already_married": "❌ Ce seigneur est déjà marié.",
        "market_err_civ_taken": "❌ Cette civilisation est déjà visée par un mariage actif.",
        "market_err_civ_unknown": "❌ Mariage refusé.",
        "market_choose_slot": "🛡️ Choisissez le créneau quotidien de patrouille (2h, heure de Paris) :",
        "market_slot_line": "{:02d}h00 → {:02d}h00",
        "market_patrouille_ok": (
            "✅ Achat effectué : **Patrouille** — créneau quotidien {:02d}h00 → {:02d}h00"
            " — trésor restant : {} ⚙️"
        ),
        "market_choose_lord": "💍 Choisissez le seigneur à marier :",
        "market_choose_explorer": "🗺️ Choisissez le seigneur à envoyer explorer (48h) :",
        "market_choose_civ": "👰 Choisissez la civilisation du mariage arrangé :",
        "market_mariage_ok": (
            "✅ Mariage arrangé scellé : **{}** est exclusive à votre royaume"
            " — trésor restant : {} ⚙️"
        ),
        "market_err_unknown": "❌ Achat refusé ({}).",
        "market_arranged_token_ok": (
            "💒 Mariage arrangé acheté — stock : {}. Consommez-le à la Paroisse."
        ),
        "market_garde_token_ok": (
            "🛡️ Garde Royale achetée — en réserve : {}. Pose-la depuis le salon 🧱 Remparts."
        ),
        "market_patrouille_slot_ok": (
            "🛡️ Emplacement de patrouille {} débloqué — pose le créneau depuis le salon 🧱 Remparts."
        ),
        "market_use_button": "🚀 Utiliser",
        "market_corruption_token_ok": (
            "🧨 Jeton Corruption acheté — en réserve : {}. Utilise-le depuis "
            "la 🏛️ Chambre des comptes."
        ),
        "market_jeu_d_armes_token_ok": (
            "🧪 Jeu d'armes acheté — en réserve : {}. Utilise-le depuis la "
            "🏛️ Chambre des comptes (+1 niveau d'IA)."
        ),
        "market_explorateur_token_ok": (
            "🛡️ Explorateur acheté — en réserve : {}. Utilise-le depuis la "
            "🏛️ Chambre des comptes."
        ),
        "market_use_jeu_d_armes_ok": (
            "🧪 Jeu d'armes utilisé — ton bot de défense monte au niveau {}/5."
        ),
        "jeu_darmes_card_title": "🧪 Jeu d'armes",
        "jeu_darmes_effect_ia": (
            "À l'usage, augmente le niveau de votre IA de 1 durant toute la "
            "saison."
        ),
        "jeu_darmes_effect_cap": (
            "Si la difficulté de votre IA est au niveau max, améliore votre "
            "Patrouille en Patrouille Renforcée."
        ),
        "jeu_darmes_effect_patrouille": (
            "Patrouille Renforcée : +1h de créneau sur vos patrouilles "
            "(3h total)."
        ),
        "jeu_darmes_effect_rush": (
            "Le seigneur utilisant Jeu d'armes réduit de 1h le délai de "
            "déclaration de sa prochaine attaque normale ; après cette "
            "déclaration, le délai redevient normal. Ne fonctionne pas avec "
            "une embuscade."
        ),
        "jeu_darmes_owned": "Vous possédez : **{0}**",
        "jeu_darmes_level": "Votre niveau d'IA actuel : **{0}/5 {1}**",
        "jeu_darmes_button": "🧪 Jeu d'armes",
        "jeu_darmes_activate_button": "✅ Activer",
        "jeu_darmes_cancel_button": "❌ Annuler",
        "jeu_darmes_use_ok": (
            "🧪 Jeu d'armes utilisé — ton bot de défense monte au niveau "
            "{0}/5 {1}. Ta prochaine attaque normale partira avec 1h de "
            "délai en moins."
        ),
        "jeu_darmes_use_ok_rush_only": (
            "🧪 Jeu d'armes utilisé — ton IA est déjà au niveau max : seule "
            "la réduction de 1h sur ta prochaine attaque normale s'applique."
        ),
        "jeu_darmes_already_active": (
            "🧪 Tu as déjà un Jeu d'armes actif — il s'appliquera à ta "
            "prochaine attaque normale."
        ),
        "jeu_darmes_no_stock": "🧪 Aucun Jeu d'armes en réserve — achat au Marché.",
        "jeu_darmes_channel_note": (
            "🧪 **{0}** a activé un **Jeu d'armes** : il dispose d'une "
            "réduction de 1h sur la déclaration de sa prochaine attaque "
            "normale, valable pour UNE attaque !"
        ),
        "ffa_join_button": "🗺️ Partir en expédition",
        "ffa_join_note": (
            "✅ **{lord}** tient un créneau de l'Expédition — **{time}** "
            "(heure de Paris). {count}/{max} participant(s)."
        ),
        "ffa_left_note": "🚪 **{lord}** a libéré son créneau — {count}/{max} participant(s).",
        "ffa_not_open": "❌ Aucune expédition n'est ouverte aux inscriptions pour le moment.",
        "ffa_full": "❌ L'expédition est complète ({max} participants).",
        "ffa_kingdom_full": (
            "❌ Ton royaume tient déjà un créneau (mode : 1 seigneur par royaume)."
        ),
        "ffa_locked": (
            "❌ Tu es verrouillé (verrou Explorateur 48h en cours ou FFA manqué) — "
            "inscription impossible."
        ),
        "ffa_announce": (
            "🧭 **Expédition — samedi {time} (heure de Paris)**\n"
            "Une partie GRATUITE de {duration} minutes contre l'IA Gaïa et les "
            "autres participants — {max} places, mode : {mode}. Clique sur "
            "**« Partir en expédition »** pour réserver ton créneau (1er arrivé, "
            "1er servi ; re-clique pour le libérer)."
        ),
        "ffa_start": (
            "🧭 **L'expédition commence maintenant** — {count} participant(s), "
            "{duration} minutes. Bonne chance !"
        ),
        "ffa_mode_one": "1 seigneur par royaume",
        "ffa_mode_free": "places libres",
        # restructuration-serveur-v1 c (Drasah 19/10): le salon FFA éphémère.
        "ffa_salon_title": "🗺️ Expédition",
        "market_err_no_points": "❌ Le royaume ne détient plus de point de mariage.",
        "market_err_no_token": (
            "❌ Aucun mariage arrangé en stock — achetez un jeton au Marché."
        ),
        "church_marry_intro": "👰 Choisissez la civilisation de votre mariage :",
        "church_marry_ok": (
            "💍 Mariage scellé : **{0}** — verrou {1}h, Offrande +{2} ⚙️."
        ),
        "mercenary_refund_dm": (
            "⚔️ Le Chef Mercenaire rappelle ton contrat : **{0}** vient "
            "d'être scellée en mariage — ta copie mercenaire est retirée "
            "et ta bourse est remboursée de **{1} écu(s)**."
        ),
        "church_marry_royal_ok": (
            "👑💍 Mariage scellé : **{0}** devient votre Reine — verrou royal"
            " {1}h · +2 ⚙️ au trésor · sécurisée toute la saison."
        ),
        "church_marry_royal_arranged_ok": (
            "👑💍 Mariage arrangé royal : **{0}** devient la Reine — verrou"
            " royal {1}h · +2 ⚙️ · sécurisée toute la saison."
        ),
        "church_err_royal_points": (
            "❌ Un mariage royal coûte DEUX points de mariage — le royaume"
            " n'en détient pas assez."
        ),
        "church_err_royal_token": (
            "❌ Un mariage arrangé royal coûte DEUX jetons — le royaume n'en"
            " détient pas assez."
        ),
        "royal_wedding_announce": (
            "👑💍 **Grand mariage royal** — {0} a pris **{1}** pour Reine"
            " du Royaume {2} ! 📑 Le détail est dans le fil « En savoir"
            " plus » ci-dessous."
        ),
        "royal_wedding_couple": "{0}, promise de la civilisation {1}",
        "royal_wedding_more_title": "En savoir plus",
        "royal_wedding_more_body": (
            "📑 **En savoir plus — le mariage royal du Royaume {1}**\n"
            "🎯 **Gains** —\n"
            "🏴 **Civilisation {0}** ⏳ **Toute la saison**\n"
            "⚙️ **+2 en trésorerie technologique**.\n"
            "🔒 **Verrou** — Durée des Noces {2} h : ne peut ni attaquer"
            " ni défendre jusqu'à **{3}**."
        ),
        "church_marry_kingdom_none": "Tu n'appartiens à aucun royaume de la saison.",
        "church_arrange_king_only": "Seul le Roi consomme un mariage arrangé.",
        "church_upgrade_king_only": "Seul le Roi améliore la Paroisse.",
        "church_upgrade_ok": (
            "⛪ Paroisse améliorée : **{0}** (palier {1}/{2}) — trésorerie restante : {3} ⚙️"
        ),
        "church_upgrade_max": "❌ La Paroisse est déjà au palier maximal.",
        "cathedral_consecrate_button": "⛪ Consacrer un Lieu Sacrée (3 ⚙️)",
        "cathedral_consecrate_choose": "⛪ Choisis le territoire à consacrer :",
        "cathedral_consecrate_king_only": "❌ Seul le Roi consacre un Lieu Sacrée.",
        "cathedral_consecrate_tier": "❌ La consécration exige le palier Cathédrale.",
        "cathedral_consecrate_none": "❌ Aucun territoire n'est disponible à la consécration pour le moment.",
        "cathedral_consecrate_ok": (
            "⛪ Le chantier est posé sur **{0}** — verdict le {1} (Paris). "
            "Jusque-là le territoire résiste à toute technologie ; une attaque classique peut détruire le chantier."
        ),
        "cathedral_consecrated": (
            "⛪ **{0}** consacre un Lieu Sacrée sur **{1}** — "
            "72h de chantier : immunisé contre les technologies, attaquable en classique."
        ),
        "cathedral_sacred": (
            "⛪ Le Lieu Sacrée de **{0}** sur **{1}** a survécu à son chantier — le territoire est désormais "
            "**SACRÉ** : immunisé contre tout, à vie."
        ),
        "church_err_not_in_hand": (
            "❌ Cette civilisation n'est pas dans votre main d'Alliances."
        ),
        "church_err_no_hand": (
            "❌ Votre royaume ne détient aucune civilisation libre — la main est"
            " renouvelée au prochain Jour du Seigneur."
        ),
        "market_choose_corrupt": "🎯 Choisissez le territoire à corrompre :",
        "market_choose_guard": "🛡️ Choisissez le territoire à protéger :",
        "market_no_options": "Aucune option disponible pour le moment.",
        "market_territory_line": "{} — propriétaire {}",
        "market_tech": {
