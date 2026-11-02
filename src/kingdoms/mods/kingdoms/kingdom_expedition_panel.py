"""Kingdoms mod — the 🧭 Exploration salon (exploration-refonte-v1,
Drasah 02/11).

The Explorateur token opens a JOURNEY now: the 🧭 button (Chambre des
comptes « Utiliser » + the council's exploration fiche) creates the
kingdom's 🧭 exploration salon. A lord enrolls as CAPITAINE from the
council fiche — « Devenir capitaine » (prerequisite: one AVAILABLE
defence point 🛡️, checked BEFORE the salon opens, never consumed, and
re-checked at the cast-off), every other lord embarks himself as CREW
(each −4h of travel, the captain never cuts it, plancher 24h, no
prerequisite to join). ⛵ Lâcher les amarres shows ONLY with a captain
on board (only he may click it) and is the single step that consumes
the token. The boarding window lasts 15 MINUTES — past it the voyage
launches itself (the events tick). 🚪 Quitter le navire: the captain
cancels the exploration (sailing: locks clear + the token is REFUNDED
+ the salon sweeps; boarding: nothing was consumed), a crew member
cancels his own embarkment (the travel recalculates), everyone else
gets a refusal. Once the lines are cast the mates stay aboard.

Anti-pollution (hygiene rules): the panel edits in place, the refusals
are 90-second ephemeral bubbles, the salon is gated like the realm
(everyone deny + members allow) and dies at the return. The Géopolitique
departure message stays deliberately VAGUE (no lord, no duration) — it
feeds the future rumour/raven system (Drasah, in reflection).

exploration-retour-v1 (Drasah 02/11): the journey now reads on a
three-phase rail — À QUAI, VOYAGE, RETOUR. While at sea the crew is
MASKED (member-level denies) and keeps only the expedition salon
(child allow); 🔄 Actualiser
re-renders the sailing face. At the resolve the doc flips to RETURNED
(gain drawn, locks held, NO auto-fallback) and shows the RP dock text
plus « 🪜 Descendre du navire » — any aboard lord validates the gain,
lifts the mask, clears the locks and sweeps the salon.

exploration-retour-v2 (Drasah 02/11: « oui tout masqué, comme la
Taverne »): the AT-SEA mask now covers the WHOLE SERVER — every
category and every un-synced channel, exactly like the Taverne
immersion. The tavern lesson applies: a ROLE deny loses to an
explicit role ALLOW, so the denies ride the MEMBER overwrites; the
expedition salon keeps its child allow (it beats its parent category
deny) and the unload drops ONLY our denies (an unrelated member
overwrite is never touched).
"""

from __future__ import annotations

import asyncio
import logging
import re
import time as _time
from typing import Any

import discord

from kingdoms.mods.kingdoms.kingdom_setup import _slug

logger = logging.getLogger("kingdoms.expedition_panel")

EXPEDITION_SALON_NAME = "🧭 exploration"
_ERROR_NOTE_SECONDS = 90.0
"""hygiene-ephemere-v1: every refusal bubble dies after 90 seconds."""

_STRINGS: dict[str, dict[str, str]] = {
    "fr": {
        "open_button": "🧭 Exploration",
        "panel_title": "# 🧭 Exploration de {kingdom}",
        "chef_line": "🧭 **Capitaine :** {name}",
        "crew_line": "⚓ **Équipage :** {names}",
        "eta_line": "⏳ **Trajet au départ :** **{hours} h** (48 h − 4 h par matelot, plancher 24 h)",
        "chef_rule": "🧭 Le capitaine doit disposer d'un point de défense 🛡️ disponible (non consommé).",
        "crew_rule": (
            "⚓ Chaque seigneur embarque de lui-même (pas de pré-requis"
            " pour participer au voyage)."
        ),
        "window_line": (
            "🕐 Vous disposez de 15 minutes pour embarquer au sein de"
            " l'équipage, après ce délai le voyage se lancera"
            " automatiquement."
        ),
        "rail_quai": "◉ À quai ────── ○ Voyage ────── ○ Retour",
        "rail_voyage": "○ À quai ────── ◉ Voyage ────── ○ Retour",
        "rail_retour": "○ À quai ────── ○ Voyage ────── ◉ Retour",
        "separator": "──────────────────",
        "crew_button": "⚓ Participer au voyage",
        "launch_button": "⛵ Lâcher les amarres",
        "quit_button": "🚪 Quitter le navire",
        "refresh_button": "🔄 Actualiser",
        "unload_button": "🪜 Descendre du navire",
        "sailing_title": "# 🧭 Exploration de {kingdom}",
        "sailing_line": "⏳ **Retour estimé :** <t:{ends}:f> (<t:{ends}:R>).",
        "returned_rp": (
            "*Après de longues semaines en mer, le navire a enfin"
            " accosté. L'équipage descend à quai, une découverte en cale.*"
        ),
        "returned_gain_map": "🗺️ **Découverte :** le territoire **{map}**",
        "returned_gain_civ": "🤝 **Recrue :** la civilisation **{civ}** (+2 ⚙️)",
        "returned_gain_tech": "⚙️ **Butin :** 2 ⚙️ de compensation",
        "unload_note": (
            "⚓ L'équipage a débarqué — le royaume garde sa découverte,"
            " le salon se referme."
        ),
        "sailing_note": (
            "⛵ Les amarres sont lâchées — le jeton 🧭 Explorateur est consommé."
            " Bon voyage, l'équipage revient <t:{ends}:R>."
        ),
        "depart_announce": (
            "🧭 Le royaume {kingdom} part explorer de"
            " nouveaux horizons..."
        ),
        "return_announce_map": (
            "🧭 Le royaume {kingdom} revient d'un long périple et découvre"
            " le territoire **{map}** !"
        ),
        "return_announce_civ": (
            "🧭 Le royaume {kingdom} revient d'un long périple — l'horizon"
            " ne révèle aucune terre nouvelle, mais l'équipage recrute la"
            " civilisation **{civ}** (+2 ⚙️) !"
        ),
        "return_announce_tech": (
            "🧭 Le royaume {kingdom} revient d'un long périple — aucune"
            " terre nouvelle : le royaume empoche **2 ⚙️** de compensation."
        ),
        "open_note": "🧭 Le salon d'expédition est ouvert : {channel}",
        "not_a_lord": "❌ Tu n'es pas un seigneur actif d'un royaume.",
        "no_service": "❌ Le service de l'économie est indisponible.",
        "no_token": "❌ Aucun jeton Explorateur en réserve — achètes-en un au Marché.",
        "already_sailing": "⛔ Une expédition est déjà en mer.",
        "locked": "⛔ Tu es dans un état verrouillé (mariage, exploration ou FFA).",
        "no_defense": "🛡️ Le capitaine doit disposer d'un point de défense disponible pour lâcher les amarres.",
        "chef_not_crew": "⛔ Le capitaine n'embarque pas comme matelot.",
        "not_captain_launch": "⛔ Seul le capitaine peut lâcher les amarres.",
        "not_captain_cancel": "⛔ Seul le capitaine peut annuler l'exploration.",
        "crew_locked": "⛔ Une fois les amarres lâchées, les matelots restent à bord jusqu'au retour.",
        "not_aboard": "⛔ Tu n'es pas à bord de l'exploration.",
        "cancel_note_boarding": "🚪 Le capitaine a quitté le navire — l'exploration est annulée.",
        "cancel_note_sailing": (
            "🚪 Le capitaine a quitté le navire — l'exploration est"
            " annulée et le jeton 🧭 Explorateur est remboursé au royaume."
        ),
        "open_failed": "⚠️ Le salon d'exploration n'a pas pu être ouvert — réessaie dans un instant.",
        "failed": "❌ {message}",
    },
    "en": {
        "open_button": "🧭 Exploration",
        "panel_title": "# 🧭 Exploration of {kingdom}",
        "chef_line": "🧭 **Captain:** {name}",
        "crew_line": "⚓ **Crew:** {names}",
        "eta_line": "⏳ **Travel at departure:** **{hours} h** (48 h − 4 h per mate, floor 24 h)",
        "chef_rule": "🧭 The captain needs one AVAILABLE defence point 🛡️ (never consumed).",
        "crew_rule": (
            "⚓ Every lord embarks himself (no prerequisite to join the"
            " voyage)."
        ),
        "window_line": (
            "🕐 You have 15 minutes to board the crew — past that delay"
            " the voyage launches on its own."
        ),
        "rail_quai": "◉ Docked ────── ○ Voyage ────── ○ Return",
        "rail_voyage": "○ Docked ────── ◉ Voyage ────── ○ Return",
        "rail_retour": "○ Docked ────── ○ Voyage ────── ◉ Return",
        "separator": "──────────────────",
        "crew_button": "⚓ Join the voyage",
        "launch_button": "⛵ Cast off",
        "quit_button": "🚪 Leave the ship",
        "refresh_button": "🔄 Refresh",
        "unload_button": "🪜 Disembark",
        "sailing_title": "# 🧭 Exploration of {kingdom}",
        "sailing_line": "⏳ **Back around:** <t:{ends}:f> (<t:{ends}:R>).",
        "returned_rp": (
            "*After long weeks at sea, the ship has finally docked. The"
            " crew steps down with a discovery in the hold.*"
        ),
        "returned_gain_map": "🗺️ **Discovery:** the territory **{map}**",
        "returned_gain_civ": "🤝 **Recruit:** the civilization **{civ}** (+2 ⚙️)",
        "returned_gain_tech": "⚙️ **Loot:** 2 ⚙️ of compensation",
        "unload_note": (
            "⚓ The crew has disembarked — the kingdom keeps its"
            " discovery, the salon closes."
        ),
        "sailing_note": (
            "⛵ The lines are cast — the 🧭 Explorateur token is consumed."
            " Safe travels, the crew returns <t:{ends}:R>."
        ),
        "depart_announce": (
            "🧭 The kingdom {kingdom} sails out to explore new"
            " horizons..."
        ),
        "return_announce_map": (
            "🧭 The kingdom {kingdom} returns from a long journey and"
            " discovers the territory **{map}**!"
        ),
        "return_announce_civ": (
            "🧭 The kingdom {kingdom} returns from a long journey — the"
            " horizon reveals no new land, but the crew recruits the"
            " civilization **{civ}** (+2 ⚙️)!"
        ),
        "return_announce_tech": (
            "🧭 The kingdom {kingdom} returns from a long journey — no new"
            " land: the kingdom pockets **2 ⚙️** of compensation."
        ),
        "open_note": "🧭 The expedition salon is open: {channel}",
        "not_a_lord": "❌ You are not an active lord of a kingdom.",
        "no_service": "❌ The economy service is unavailable.",
        "no_token": "❌ No Explorateur token in reserve — buy one at the Market.",
        "already_sailing": "⛔ An expedition is already at sea.",
        "locked": "⛔ You are in a locked state (marriage, exploration or FFA).",
        "no_defense": "🛡️ The captain needs one available defence point to cast off.",
        "chef_not_crew": "⛔ The captain does not embark as a mate.",
        "not_captain_launch": "⛔ Only the captain may cast off.",
        "not_captain_cancel": "⛔ Only the captain may cancel the exploration.",
        "crew_locked": "⛔ Once the lines are cast, the mates stay aboard until the return.",
        "not_aboard": "⛔ You are not aboard the exploration.",
        "cancel_note_boarding": "🚪 The captain left the ship — the exploration is cancelled.",
        "cancel_note_sailing": (
            "🚪 The captain left the ship — the exploration is cancelled"
            " and the 🧭 Explorateur token is refunded to the kingdom."
        ),
        "open_failed": "⚠️ The exploration salon could not be opened — try again in a moment.",
        "failed": "❌ {message}",
    },
}


def _strings(locale: Any) -> dict[str, str]:
    """Return the panel's strings for a Discord locale."""
    lang = str(locale or "en")
    return _STRINGS.get(lang[:2], _STRINGS["en"])


def _locale(interaction: discord.Interaction) -> str:
    """Extract the interaction locale (``fr``/``en``)."""
    raw = str(getattr(interaction, "locale", "") or "en")
    return "fr" if raw.lower().startswith("fr") else "en"


async def _error_note(interaction: discord.Interaction, text: str) -> None:
    """One 90-second ephemeral refusal bubble (hygiene-ephemere-v1)."""
    try:
        await interaction.response.send_message(text, ephemeral=True)
    except Exception:
        logger.warning("KINGDOMS EXPEDITION: refusal bubble failed", exc_info=True)
        return

    async def _delete_later() -> None:
        await asyncio.sleep(_ERROR_NOTE_SECONDS)
        try:
            await interaction.delete_original_response()
        except Exception:
            pass  # the bubble already died on its own

    try:
        asyncio.create_task(_delete_later())
    except Exception:
        pass


def _map_error(strings: dict[str, str], exc: Exception) -> str:
    """Translate one economy refusal into the panel's own bubbles."""
    from kingdoms.mods.kingdoms.economy import EconomyError

    text = str(exc)
    if "no explorateur token" in text:
        return strings["no_token"]
    if "already at sea" in text:
        return strings["already_sailing"]
    if "locked" in text:
        return strings["locked"]
    if "defence point" in text:
        return strings["no_defense"]
    if "not embark as crew" in text or "does not embark" in text:
        return strings["chef_not_crew"]
    if "only the exploration captain" in text:
        return strings["not_captain_cancel"]
    if "no exploration to unload" in text or "exploration crew may unload" in text:
        return strings["not_aboard"]
    if isinstance(exc, EconomyError):
        return str(strings["failed"]).format(message=text)
    return str(strings["failed"]).format(message=text)


async def _require_lord(
    interaction: discord.Interaction, strings: dict[str, str], wiring: Any
) -> tuple[Any, Any]:
    """Resolve the acting lord + kingdom or answer the refusal."""
    from kingdoms.mods.kingdoms.kingdom_persistent import _lord_of

    lord = await _lord_of(
            wiring.kingdoms_service, str(interaction.user.id), wiring.bot_admins
        )
    if lord is None or not lord.kingdom_id or lord.left:
        await _error_note(interaction, strings["not_a_lord"])
        return (None, None)
    kingdom = next(
        (k for k in await wiring.kingdoms_service.kingdoms() if k.id == lord.kingdom_id),
        None,
    )
    if kingdom is None:
        await _error_note(interaction, strings["not_a_lord"])
        return (None, None)
    return (lord, kingdom)


def _expedition_hours(doc: dict[str, Any]) -> int:
    """The travel time at departure (48h − 4h per mate, floor 24h)."""
    from kingdoms.mods.kingdoms.economy import (
        EXPEDITION_BASE_HOURS,
        EXPEDITION_HOURS_PER_LORD,
        EXPEDITION_MIN_HOURS,
    )

    crew = len([item for item in doc.get("crew", []) if item])
    return max(
        EXPEDITION_MIN_HOURS,
        EXPEDITION_BASE_HOURS - EXPEDITION_HOURS_PER_LORD * crew,
    )


def _rail(strings: dict[str, str], state: str) -> str:
    """The three-phase rail — the filled dot marks the current phase."""
    if state == "sailing":
        return str(strings["rail_voyage"])
    if state == "returned":
        return str(strings["rail_retour"])
    return str(strings["rail_quai"])


def _panel_text(
    strings: dict[str, str], kingdom: Any, doc: dict[str, Any], lord_names: dict[str, str]
) -> str:
    """The salon's pinned panel body (quai, voyage or retour)."""
    title = str(strings["panel_title"]).format(kingdom=getattr(kingdom, "name", ""))
    state = str(doc.get("state", ""))
    rail = _rail(strings, state)
    if state in ("sailing", "returned"):
        ends = int(doc.get("ends_at", 0) or 0)
        chef_id = str(doc.get("chef_lord_id", "") or "")
        crew = [str(item) for item in doc.get("crew", []) if item]
        chef_name = lord_names.get(chef_id, "—")
        crew_names = ", ".join(f"<@{item}>" for item in crew) if crew else "—"
        lines = [
            title,
            "",
            rail,
            "",
            str(strings["chef_line"]).format(name=chef_name),
            str(strings["crew_line"]).format(names=crew_names),
        ]
        if state == "sailing":
            lines.append(str(strings["sailing_line"]).format(ends=ends))
        else:
            kind = str(doc.get("gain_kind", "") or "")
            value = str(doc.get("gain_value", "") or "")
            lines += [
                "",
                strings["returned_rp"],
                "",
                str(strings["returned_gain_map"]).format(map=value)
                if kind == "map"
                else str(strings["returned_gain_civ"]).format(civ=value)
                if kind == "civ"
                else str(strings["returned_gain_tech"]),
            ]
        return "\n".join(lines)
    chef_id = str(doc.get("chef_lord_id", "") or "")
    crew = [str(item) for item in doc.get("crew", []) if item]
    chef_name = lord_names.get(chef_id, "—")
    crew_names = ", ".join(f"<@{item}>" for item in crew) if crew else "—"
    lines = [
        title,
        "",
        rail,
        "",
        str(strings["chef_line"]).format(name=chef_name),
        str(strings["crew_line"]).format(names=crew_names),
        str(strings["eta_line"]).format(hours=_expedition_hours(doc)),
        "",
        strings["separator"],
        "",
        strings["chef_rule"],
        strings["crew_rule"],
        strings["window_line"],
    ]
    return "\n".join(lines)


def _panel_view(strings: dict[str, str], doc: dict[str, Any]) -> discord.ui.View:
    """The panel's persistent buttons — exploration-retour-v1 (Drasah
    02/11): boarding = ⛵ (captain on board) + ⚓ + 🚪, sailing = 🔄 +
    🚪 (the captain may still cancel — refund + sweep), returned = 🪜
    alone (the crew validates the gain and closes the salon)."""
    view = discord.ui.View(timeout=None)
    state = str(doc.get("state", ""))
    if state == "returned":
        view.add_item(KingdomExpeditionUnloadButton(strings))
        return view
    if state == "sailing":
        view.add_item(KingdomExpeditionRefreshButton(strings))
        view.add_item(KingdomExpeditionQuitButton(strings))
        return view
    if doc.get("chef_lord_id"):
        view.add_item(KingdomExpeditionLaunchButton(strings))
    view.add_item(KingdomExpeditionCrewButton(strings))
    view.add_item(KingdomExpeditionQuitButton(strings))
    return view


async def _lord_names(wiring: Any, kingdom_id: str) -> dict[str, str]:
    """Map the kingdom's lord ids to display names."""
    names: dict[str, str] = {}
    try:
        for lord in await wiring.kingdoms_service.lords():
            if str(lord.kingdom_id or "") == str(kingdom_id) and not lord.left:
                names[str(lord.id)] = str(getattr(lord, "display_name", lord.id))
    except Exception:
        logger.warning("KINGDOMS EXPEDITION: lord names read failed", exc_info=True)
    return names


async def refresh_expedition_panel_safe(guild: Any, wiring: Any, kingdom_id: str) -> None:
    """Re-render the pinned panel in place (zero bubble, anti-pollution)."""
    economy = wiring.economy_service
    if economy is None or wiring.kingdoms_service is None:
        return
    try:
        doc = await economy.expedition(kingdom_id)
        if not doc or not doc.get("panel_message_id") or not doc.get("salon_id"):
            return
        channel = getattr(guild, "get_channel", lambda _id: None)(int(doc["salon_id"]))
        if channel is None:
            return
        message = await channel.fetch_message(int(doc["panel_message_id"]))
        kingdom = next(
            (k for k in await wiring.kingdoms_service.kingdoms() if k.id == kingdom_id),
            None,
        )
        if kingdom is None:
            return
        locale = "fr"
        strings = _strings(locale)
        names = await _lord_names(wiring, kingdom_id)
        if str(doc.get("state", "")) == "sailing":
            # exploration-refonte-v1: the sailing face keeps 🚪 alone —
            # the captain may still cancel (refund + sweep).
            await message.edit(
                content=_panel_text(strings, kingdom, doc, names),
                view=_panel_view(strings, doc),
            )
        else:
            await message.edit(
                content=_panel_text(strings, kingdom, doc, names),
                view=_panel_view(strings, doc),
            )
    except Exception:
        logger.warning("KINGDOMS EXPEDITION: panel refresh failed", exc_info=True)


async def open_expedition_salon_safe(
    guild: Any, wiring: Any, kingdom: Any
) -> Any | None:
    """Open (or re-open) the kingdom's 🧭 exploration salon.

    The salon lives in the kingdom's category, gated like the realm
    (everyone deny + members allow — the INVARIANT a fresh arrival
    must never miss). A leftover empty salon is purged by slug first.
    Returns the channel (None on failure — best effort, never raises).
    """
    from kingdoms.mods.kingdoms.kingdom_realms import (
        _find_realm_category,
        _realm_overwrites,
    )

    economy = wiring.economy_service
    if economy is None or wiring.kingdoms_service is None:
        return None
    kingdom_id = str(kingdom.id)
    try:
        doc = await economy.begin_expedition(kingdom_id)
    except Exception as exc:
        logger.warning(
            "KINGDOMS EXPEDITION: boarding refused for %s (%s)", kingdom_id, exc
        )
        return None
    if doc.get("salon_id"):
        channel = getattr(guild, "get_channel", lambda _id: None)(int(doc["salon_id"]))
        if channel is not None:
            await refresh_expedition_panel_safe(guild, wiring, kingdom_id)
            return channel
    category = _find_realm_category(guild, str(kingdom.name))
    if category is None:
        logger.warning(
            "KINGDOMS EXPEDITION: no realm category for %s", kingdom_id
        )
        return None
    # A leftover salon from a wiped boarding is purged first — the name
    # is fixed, at most one lives per realm.
    wanted = _slug(EXPEDITION_SALON_NAME)
    for channel in list(getattr(category, "channels", []) or []):
        if _slug(getattr(channel, "name", "")) == wanted:
            try:
                await channel.delete()
            except Exception:
                logger.warning(
                    "KINGDOMS EXPEDITION: leftover salon purge failed", exc_info=True
                )
    member_ids: list[int] = []
    for lord in await wiring.kingdoms_service.lords():
        if str(lord.kingdom_id or "") != kingdom_id or lord.left:
            continue
        try:
            member_ids.append(int(lord.id))
        except (TypeError, ValueError):
            logger.warning(
                "KINGDOMS EXPEDITION: non-numeric lord id %r skipped", lord.id
            )
    overwrites = await _realm_overwrites(guild, member_ids)
    try:
        channel = await guild.create_text_channel(
            EXPEDITION_SALON_NAME,
            category=category,
            overwrites=overwrites,
        )
    except Exception:
        logger.warning("KINGDOMS EXPEDITION: salon creation failed", exc_info=True)
        return None
    strings = _strings("fr")
    names = await _lord_names(wiring, kingdom_id)
    try:
        message = await channel.send(
            _panel_text(strings, kingdom, doc, names), view=_panel_view(strings, doc)
        )
        await economy.record_expedition_salon(
            kingdom_id, int(channel.id), int(message.id)
        )
    except Exception:
        logger.warning("KINGDOMS EXPEDITION: panel message failed", exc_info=True)
        await economy.record_expedition_salon(kingdom_id, int(channel.id))
    logger.info("KINGDOMS EXPEDITION: salon opened for %s", kingdom_id)
    return channel


async def announce_expedition_depart_safe(guild: Any, kingdom_name: str) -> None:
    """The deliberately VAGUE Géopolitique departure (no lord, no duration)."""
    from kingdoms.mods.kingdoms.kingdom_content import announce_geopolitics

    strings = _strings("fr")
    text = str(strings["depart_announce"]).format(kingdom=kingdom_name)
    try:
        await announce_geopolitics(guild, "fr", text)
    except Exception:
        logger.warning("KINGDOMS EXPEDITION: departure announcement failed", exc_info=True)


def expedition_return_text(
    locale: str, kingdom_name: str, kind: str, value: str
) -> str:
    """The Géopolitique return message (map, compensation civ, or points)."""
    strings = _strings(locale)
    if kind == "map":
        return str(strings["return_announce_map"]).format(
            kingdom=kingdom_name, map=value
        )
    if kind == "civ":
        return str(strings["return_announce_civ"]).format(
            kingdom=kingdom_name, civ=value
        )
    return str(strings["return_announce_tech"]).format(kingdom=kingdom_name)


async def sweep_expedition_salon_safe(guild: Any, salon_id: int) -> None:
    """Delete the expedition salon at the return (it never outlives the trip)."""
    if not salon_id:
        return
    channel = getattr(guild, "get_channel", lambda _id: None)(int(salon_id))
    if channel is None:
        return
    try:
        await channel.delete()
        logger.info("KINGDOMS EXPEDITION: salon swept (expedition over)")
    except Exception:
        logger.warning("KINGDOMS EXPEDITION: salon deletion failed", exc_info=True)


def _guild_member(guild: Any, member_id: str) -> Any:
    """Resolve one member id to a guild member (None on any mismatch)."""
    try:
        return getattr(guild, "get_member", lambda _id: None)(int(member_id))
    except (TypeError, ValueError):
        return None


def _merged_overwrites(channel: Any) -> dict[Any, Any]:
    """Read a channel's live overwrites (target-keyed) — falls back to
    the raw ``(id, is_role)`` store then to an empty set. Never raises."""
    try:
        live = getattr(channel, "overwrites", None)
        if isinstance(live, dict) and live:
            return dict(live)
    except Exception:
        pass
    raw = getattr(channel, "_overwrites", None)
    if isinstance(raw, dict) and raw:
        guild = getattr(channel, "guild", None)
        result: dict[Any, Any] = {}
        for key, overwrite in raw.items():
            try:
                target_id, is_role = key  # the raw (id, is_role) store
            except (TypeError, ValueError):
                continue
            if is_role:
                target = getattr(guild, "get_role", lambda _i: None)(target_id)
            else:
                target = getattr(guild, "get_member", lambda _i: None)(
                    int(target_id)
                )
            if target is not None:
                result[target] = overwrite
        return result
    return {}


async def mask_crew_for_voyage_safe(guild: Any, wiring: Any, kingdom: Any) -> None:
    """exploration-retour-v2 (Drasah 02/11: « tout masqué, comme la
    Taverne »): the AT-SEA illusion — once the lines are cast, the crew
    sees ONLY the voyage. Every aboard member (captain + mates) gets a
    MEMBER-level view deny on the realm category (the v1 batch edit)
    AND on every other category / un-synced channel of the server (the
    Taverne immersion pattern — a role deny would lose to an explicit
    role ALLOW, the member overwrites override the role layer). The
    expedition salon keeps its child allow (it beats the category
    deny). Converged denies are skipped (zero steady-state writes)."""
    from kingdoms.mods.kingdoms.kingdom_realms import _find_realm_category
    from kingdoms.mods.kingdoms.tavern_immersion import _deny_member_view

    economy = wiring.economy_service
    if economy is None:
        return
    try:
        doc = await economy.expedition(str(kingdom.id))
    except Exception:
        logger.warning("KINGDOMS EXPEDITION: mask read failed", exc_info=True)
        return
    ids = [str(doc.get("chef_lord_id", "") or "")]
    ids += [str(item) for item in doc.get("crew", [])]
    ids = [item for item in ids if item]
    if not ids:
        return
    members = []
    for member_id in ids:
        member = _guild_member(guild, member_id)
        if member is not None:
            members.append(member)
    if not members:
        return
    category = _find_realm_category(guild, str(kingdom.name))
    if category is not None:
        try:
            overwrites = _merged_overwrites(category)
            for member in members:
                overwrites[member] = discord.PermissionOverwrite(view_channel=False)
            await category.edit(overwrites=overwrites)
        except Exception:
            logger.warning(
                "KINGDOMS EXPEDITION: crew mask on category failed", exc_info=True
            )
    salon = getattr(guild, "get_channel", lambda _id: None)(
        int(doc.get("salon_id", 0) or 0)
    )
    # exploration-retour-v2: the WHOLE SERVER disappears — every other
    # category plus every un-synced channel (the Taverne lesson), one
    # member-level deny per (target, member), skipped when converged.
    for target in _voyage_mask_targets(guild, salon, category):
        for member in members:
            await _deny_member_view(target, member)
    if salon is None:
        return
    try:
        overwrites = _merged_overwrites(salon)
        for member in members:
            overwrites[member] = discord.PermissionOverwrite(
                view_channel=True, read_message_history=True
            )
        await salon.edit(overwrites=overwrites)
    except Exception:
        logger.warning("KINGDOMS EXPEDITION: crew allow on salon failed", exc_info=True)


def _voyage_mask_targets(
    guild: Any, salon: Any | None, realm_category: Any | None
) -> list[Any]:
    """Every hide-able target of the AT-SEA mask EXCEPT the ones the
    mask function already handles by hand (the realm category rides the
    v1 batch edit): the other categories plus the un-synced channels
    (a synced channel inherits its category's deny). The salon itself
    is never a target — its child allow keeps it alive."""
    targets: list[Any] = []
    realm_id = getattr(realm_category, "id", None)
    for category in list(getattr(guild, "categories", []) or []):
        if getattr(category, "id", None) != realm_id:
            targets.append(category)
    channels: list[Any] = [
        *(getattr(guild, "text_channels", []) or []),
        *(getattr(guild, "voice_channels", []) or []),
        *(getattr(guild, "forums", []) or []),
    ]
    salon_id = getattr(salon, "id", None)
    for channel in channels:
        if getattr(channel, "id", None) == salon_id:
            continue
        parent = getattr(channel, "category", None)
        if parent is not None and getattr(channel, "permissions_synced", True):
            continue  # the category deny covers the synced channels
        targets.append(channel)
    return targets


async def unmask_crew_safe(guild: Any, kingdom: Any, member_ids: list[str]) -> None:
    """Lift the AT-SEA mask — the realm allow comes back (the same
    entry _realm_overwrites grants, one single category edit) and the
    full-server denies of exploration-retour-v2 are dropped the
    Taverne way: ONLY our member view deny is removed (an unrelated
    member overwrite — e.g. an ALLOW — is never touched). Best effort,
    never raises; the salon itself dies with the sweep."""
    from kingdoms.mods.kingdoms.kingdom_realms import _find_realm_category
    from kingdoms.mods.kingdoms.tavern_immersion import _clear_member_view_deny

    if not member_ids:
        return
    category = _find_realm_category(guild, str(kingdom.name))
    members = []
    for member_id in member_ids:
        member = _guild_member(guild, str(member_id))
        if member is not None:
            members.append(member)
    if not members:
        return
    if category is not None:
        try:
            overwrites = _merged_overwrites(category)
            for member in members:
                overwrites[member] = discord.PermissionOverwrite(
                    view_channel=True, read_message_history=True
                )
            await category.edit(overwrites=overwrites)
        except Exception:
            logger.warning(
                "KINGDOMS EXPEDITION: crew unmask failed", exc_info=True
            )
    for target in _voyage_mask_targets(guild, None, category):
        for member in members:
            await _clear_member_view_deny(target, member)


async def open_expedition_from_market(
    interaction: discord.Interaction, wiring: Any, strings: dict[str, Any], lord: Any
) -> None:
    """The 🚀 Utiliser rewiring: the explorateur card OPENS the salon.

    The old lord-select flow is retired — the token is no longer spent
    on a lord pick: it funds a whole EXPEDITION. The window closes the
    player's previous ephemeral (fenetre-unique) and the salon link
    rides a small followup bubble.
    """
    from kingdoms.mods.kingdoms.kingdom_persistent import (
        _close_previous_ephemeral,
        _EPHEMERAL_WINDOWS,
    )

    expe_strings = _strings(_locale(interaction))
    economy = wiring.economy_service
    if economy is None or wiring.kingdoms_service is None:
        await _error_note(interaction, expe_strings["no_service"])
        return
    kingdom = next(
        (
            k
            for k in await wiring.kingdoms_service.kingdoms()
            if k.id == str(lord.kingdom_id or "")
        ),
        None,
    )
    if kingdom is None:
        await _error_note(interaction, expe_strings["not_a_lord"])
        return
    user_id = str(interaction.user.id)
    await _close_previous_ephemeral(user_id)
    await interaction.response.defer(ephemeral=True)
    channel = await open_expedition_salon_safe(interaction.guild, wiring, kingdom)
    if channel is None:
        try:
            doc = await economy.expedition(str(kingdom.id))
            if str(doc.get("state", "")) == "sailing":
                note = expe_strings["already_sailing"]
            else:
                note = expe_strings["no_token"]
        except Exception:
            note = expe_strings["no_token"]
        try:
            await interaction.followup.send(note, ephemeral=True)
        except Exception:
            logger.warning("KINGDOMS EXPEDITION: refusal followup failed", exc_info=True)
        return
    note = str(expe_strings["open_note"]).format(channel=f"<#{int(channel.id)}>")
    try:
        message = await interaction.followup.send(note, ephemeral=True)
        _EPHEMERAL_WINDOWS[user_id] = (interaction, _time.monotonic(), message)
    except Exception:
        logger.warning("KINGDOMS EXPEDITION: salon link followup failed", exc_info=True)


class KingdomExpeditionOpenButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdoms:expedition:open",
):
    """The restart-proof 🧭 Exploration button (Le-Royaume view)."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id="kingdoms:expedition:open",
                style=discord.ButtonStyle.success,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> KingdomExpeditionOpenButton:
        """Rebuild the button from the wire — THIS module's strings only."""
        return cls(_strings(_locale(interaction))["open_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Open (or re-open) the kingdom's expedition salon."""
        from kingdoms.mods.kingdoms.kingdom_persistent import _wiring

        strings = _strings(_locale(interaction))
        wiring = _wiring()
        if wiring.economy_service is None or wiring.kingdoms_service is None:
            await _error_note(interaction, strings["no_service"])
            return
        lord, kingdom = await _require_lord(interaction, strings, wiring)
        if lord is None or kingdom is None:
            return
        await open_expedition_from_market(interaction, wiring, strings, lord)


async def _handle_toggle(
    interaction: discord.Interaction, toggle: Any
) -> None:
    """Shared plumbing of the two boarding toggles (chef/crew).

    The refusal rides a 90-second bubble, the success edits the panel
    in place — a toggle never leaves a message behind (anti-pollution).
    """
    from kingdoms.mods.kingdoms.kingdom_persistent import _wiring

    strings = _strings(_locale(interaction))
    wiring = _wiring()
    if wiring.economy_service is None or wiring.kingdoms_service is None:
        await _error_note(interaction, strings["no_service"])
        return
    lord, kingdom = await _require_lord(interaction, strings, wiring)
    if lord is None or kingdom is None:
        return
    try:
        await toggle(str(kingdom.id), str(lord.id))
    except Exception as exc:
        await _error_note(interaction, _map_error(strings, exc))
        return
    try:
        await interaction.response.defer()
    except Exception:
        pass
    await refresh_expedition_panel_safe(interaction.guild, wiring, str(kingdom.id))
    try:
        await interaction.delete_original_response()
    except Exception:
        pass


class KingdomExpeditionQuitButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdoms:expedition:quit",
):
    """« 🚪 Quitter le navire » — exploration-refonte-v1 (Drasah 02/11).

    The CAPTAIN cancels the exploration (boarding: the doc clears,
    nothing was consumed; sailing: every lock clears, the token is
    refunded and the salon sweeps). A CREW member cancels his own
    embarkment — the panel recalculates the travel in place. Anyone
    else gets a refusal. Once the lines are cast the mates stay aboard
    (locked until the return); only the captain may leave a sailing
    ship."""

    def __init__(self, strings: dict[str, str]) -> None:
        super().__init__(
            discord.ui.Button(
                label=str(strings["quit_button"])[:80],
                custom_id="kingdoms:expedition:quit",
                style=discord.ButtonStyle.secondary,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> KingdomExpeditionQuitButton:
        """Rebuild the button from the wire."""
        return cls(_strings(_locale(interaction)))

    async def callback(self, interaction: discord.Interaction) -> None:
        """Quit the ship — captain cancels, a mate disembarks, else note."""
        from kingdoms.mods.kingdoms.kingdom_persistent import _wiring

        strings = _strings(_locale(interaction))
        wiring = _wiring()
        if wiring.economy_service is None:
            await _error_note(interaction, strings["no_service"])
            return
        lord, kingdom = await _require_lord(interaction, strings, wiring)
        if lord is None or kingdom is None:
            return
        economy = wiring.economy_service
        try:
            doc = await economy.expedition(str(kingdom.id))
        except Exception:
            await _error_note(interaction, strings["no_service"])
            return
        state = str(doc.get("state", ""))
        is_captain = str(doc.get("chef_lord_id", "") or "") == str(lord.id)
        if state == "boarding":
            if is_captain:
                await self._cancel(
                    interaction, wiring, strings, kingdom, lord, economy
                )
            elif str(lord.id) in [str(item) for item in doc.get("crew", [])]:
                # a mate steps off BEFORE the launch — the travel
                # recalculates on the panel refresh (−4h read back).
                await _handle_toggle(interaction, economy.toggle_expedition_crew)
            else:
                await _error_note(interaction, strings["not_aboard"])
            return
        if state == "sailing":
            if is_captain:
                await self._cancel(
                    interaction, wiring, strings, kingdom, lord, economy
                )
            else:
                await _error_note(interaction, strings["crew_locked"])
            return
        await _error_note(interaction, strings["not_aboard"])

    async def _cancel(
        self,
        interaction: discord.Interaction,
        wiring: Any,
        strings: dict[str, str],
        kingdom: Any,
        lord: Any,
        economy: Any,
    ) -> None:
        """The captain steps down — the exploration is cancelled."""
        from kingdoms.mods.kingdoms.kingdom_persistent import (
            _refresh_realm_views_for_kingdom_safe,
        )

        try:
            result = await economy.cancel_expedition(str(kingdom.id), str(lord.id))
        except Exception as exc:
            await _error_note(interaction, _map_error(strings, exc))
            return
        note = strings[
            "cancel_note_sailing" if result.get("refunded") else "cancel_note_boarding"
        ]
        await _error_note(interaction, note)
        if result.get("refunded"):
            # exploration-retour-v1: the AT-SEA mask lifts with the
            # locks — the crew sees its realm again.
            await unmask_crew_safe(
                interaction.guild, kingdom, [str(i) for i in result.get("locked", [])]
            )
        await sweep_expedition_salon_safe(
            interaction.guild, int(result.get("salon_id", 0) or 0)
        )
        # the 🧭 card may light up again on the realm view (refunded).
        try:
            await _refresh_realm_views_for_kingdom_safe(
                interaction.guild, str(kingdom.id)
            )
        except Exception:
            logger.warning(
                "KINGDOMS EXPEDITION: realm refresh after cancel failed",
                exc_info=True,
            )


class KingdomExpeditionCrewButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdoms:expedition:crew",
):
    """« Participer au voyage » — each lord clicks himself, −4h of travel."""

    def __init__(self, strings: dict[str, str]) -> None:
        super().__init__(
            discord.ui.Button(
                label=str(strings["crew_button"])[:80],
                custom_id="kingdoms:expedition:crew",
                style=discord.ButtonStyle.secondary,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> KingdomExpeditionCrewButton:
        """Rebuild the button from the wire."""
        return cls(_strings(_locale(interaction)))

    async def callback(self, interaction: discord.Interaction) -> None:
        """Toggle one crew member (free, unlocked active lords only)."""
        from kingdoms.mods.kingdoms.kingdom_persistent import _wiring

        wiring = _wiring()
        if wiring.economy_service is None:
            await _error_note(interaction, _strings(_locale(interaction))["no_service"])
            return
        await _handle_toggle(interaction, wiring.economy_service.toggle_expedition_crew)


class KingdomExpeditionLaunchButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdoms:expedition:launch",
):
    """« ⛵ Lâcher les amarres » — visible ONLY with a chef on board.

    The single step that consumes the Explorateur token; the locks fall
    on the chef + crew, the vague Géopolitique announcement goes out and
    the panel flips to its sailing face (no buttons left).
    """

    def __init__(self, strings: dict[str, str]) -> None:
        super().__init__(
            discord.ui.Button(
                label=str(strings["launch_button"])[:80],
                custom_id="kingdoms:expedition:launch",
                style=discord.ButtonStyle.success,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> KingdomExpeditionLaunchButton:
        """Rebuild the button from the wire."""
        return cls(_strings(_locale(interaction)))

    async def callback(self, interaction: discord.Interaction) -> None:
        """Consume the token, lock the crew, announce and flip the panel."""
        from kingdoms.mods.kingdoms.kingdom_persistent import (
            _refresh_realm_views_for_kingdom_safe,
            _wiring,
        )

        strings = _strings(_locale(interaction))
        wiring = _wiring()
        if wiring.economy_service is None or wiring.kingdoms_service is None:
            await _error_note(interaction, strings["no_service"])
            return
        lord, kingdom = await _require_lord(interaction, strings, wiring)
        if lord is None or kingdom is None:
            return
        # exploration-refonte-v1: ONLY the captain may cast off — the
        # button is visible to everyone (Discord shows it to all), the
        # guard refuses anyone else with a bubble.
        try:
            doc = await wiring.economy_service.expedition(str(kingdom.id))
        except Exception:
            doc = {}
        if str(doc.get("chef_lord_id", "") or "") != str(lord.id):
            await _error_note(interaction, strings["not_captain_launch"])
            return
        try:
            doc = await wiring.economy_service.launch_expedition(str(kingdom.id))
        except Exception as exc:
            await _error_note(interaction, _map_error(strings, exc))
            return
        try:
            await interaction.response.defer(thinking=True)
        except Exception:
            pass
        await refresh_expedition_panel_safe(interaction.guild, wiring, str(kingdom.id))
        # exploration-retour-v1: the crew is AT SEA — it sees only the
        # voyage salon until the return is unloaded.
        await mask_crew_for_voyage_safe(interaction.guild, wiring, kingdom)
        ends = int(doc.get("ends_at", 0) or 0)
        salon = getattr(
            interaction.guild, "get_channel", lambda _id: None
        )(int(doc.get("salon_id", 0) or 0))
        if salon is not None:
            try:
                await salon.send(str(strings["sailing_note"]).format(ends=ends))
            except Exception:
                logger.warning(
                    "KINGDOMS EXPEDITION: sailing note failed", exc_info=True
                )
        await announce_expedition_depart_safe(interaction.guild, str(kingdom.name))
        try:
            await interaction.delete_original_response()
        except Exception:
            pass
        # The realm view drops the 🧭 button (the token is gone).
        try:
            await _refresh_realm_views_for_kingdom_safe(
                interaction.guild, str(kingdom.id)
            )
        except Exception:
            logger.warning("KINGDOMS EXPEDITION: realm refresh failed", exc_info=True)


class KingdomExpeditionRefreshButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdoms:expedition:refresh",
):
    """« 🔄 Actualiser » — exploration-retour-v1 (Drasah 02/11).

    The sailing face keeps no live state of its own: the countdown
    rides Discord's <t:…:R> stamp, but the crew may want the panel
    re-read (a late mate, a restarted bot). Anyone may click — the
    refresh never consumes anything, it just re-renders the panel.
    """

    def __init__(self, strings: dict[str, str]) -> None:
        super().__init__(
            discord.ui.Button(
                label=str(strings["refresh_button"])[:80],
                custom_id="kingdoms:expedition:refresh",
                style=discord.ButtonStyle.secondary,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> KingdomExpeditionRefreshButton:
        """Rebuild the button from the wire."""
        return cls(_strings(_locale(interaction)))

    async def callback(self, interaction: discord.Interaction) -> None:
        """Re-render the pinned panel in place (zero bubble)."""
        from kingdoms.mods.kingdoms.kingdom_persistent import _wiring

        strings = _strings(_locale(interaction))
        wiring = _wiring()
        if wiring.economy_service is None or wiring.kingdoms_service is None:
            await _error_note(interaction, strings["no_service"])
            return
        lord, kingdom = await _require_lord(interaction, strings, wiring)
        if lord is None or kingdom is None:
            return
        try:
            await interaction.response.defer()
        except Exception:
            pass
        await refresh_expedition_panel_safe(interaction.guild, wiring, str(kingdom.id))
        try:
            await interaction.delete_original_response()
        except Exception:
            pass


class KingdomExpeditionUnloadButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdoms:expedition:unload",
):
    """« 🪜 Descendre du navire » — exploration-retour-v1 (Drasah
    02/11).

    The RETURNED face: the gain was already drawn at the resolve (the
    tick) — the crew VALIDATES it here. Any ABOARD lord (captain or
    mate) may click: every lock clears, the AT-SEA mask lifts, the
    salon sweeps and the doc empties. NO automatic fallback — the
    button alone closes the journey (Drasah's call). A stranger gets
    the refusal bubble."""

    def __init__(self, strings: dict[str, str]) -> None:
        super().__init__(
            discord.ui.Button(
                label=str(strings["unload_button"])[:80],
                custom_id="kingdoms:expedition:unload",
                style=discord.ButtonStyle.success,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> KingdomExpeditionUnloadButton:
        """Rebuild the button from the wire."""
        return cls(_strings(_locale(interaction)))

    async def callback(self, interaction: discord.Interaction) -> None:
        """The crew disembarks — locks clear, mask lifts, salon closes."""
        from kingdoms.mods.kingdoms.kingdom_persistent import (
            _refresh_realm_views_for_kingdom_safe,
            _wiring,
        )

        strings = _strings(_locale(interaction))
        wiring = _wiring()
        if wiring.economy_service is None or wiring.kingdoms_service is None:
            await _error_note(interaction, strings["no_service"])
            return
        lord, kingdom = await _require_lord(interaction, strings, wiring)
        if lord is None or kingdom is None:
            return
        economy = wiring.economy_service
        try:
            doc = await economy.expedition(str(kingdom.id))
        except Exception:
            await _error_note(interaction, strings["no_service"])
            return
        if str(doc.get("state", "")) != "returned":
            await _error_note(interaction, strings["not_aboard"])
            return
        try:
            claimed = await economy.claim_expedition_return(
                str(kingdom.id), str(lord.id)
            )
        except Exception as exc:
            await _error_note(interaction, _map_error(strings, exc))
            return
        await _error_note(interaction, strings["unload_note"])
        # the AT-SEA mask lifts with the locks — the realm comes back.
        crew_ids = [str(claimed.get("chef_lord_id", "") or "")]
        crew_ids += [str(item) for item in claimed.get("crew", [])]
        await unmask_crew_safe(interaction.guild, kingdom, crew_ids)
        await sweep_expedition_salon_safe(
            interaction.guild, int(claimed.get("salon_id", 0) or 0)
        )
        # the 🧭 card may light up again on the realm view (a new token
        # buys a new journey).
        try:
            await _refresh_realm_views_for_kingdom_safe(
                interaction.guild, str(kingdom.id)
            )
        except Exception:
            logger.warning(
                "KINGDOMS EXPEDITION: realm refresh after unload failed",
                exc_info=True,
            )
