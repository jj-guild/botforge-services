"""Kingdoms mod — the realm salons' content engine (realm-content-v1).

PORTAGE of the diverged branch's ``kingdom_realm_content.py`` (vibe/
drasah/main, Drasah 21-11) into the new architecture — vague 1 :

- 🗺️ Territoire : l'état d'attente « distribution au lancement » tant
  que la saison siège en ``setup``, la fiche des terres réelles après
  le départ (territoires du moteur, gardes ⏳ ⛪) ;
- 🏆 Alliances : le panneau unifié — la main + les origines +
  les contrats, avec SES QUATRE boutons éphémères (📅 Prochain cycle ·
  🚫 Verrouillées · ⏳ Durées · 📖 Historique), restart-proof ;
- 💬 Discussions : le message d'accueil RP (un marker, jamais
  dupliqué) + le résumé épinglé des 🎯 objectifs ;
- le MP au Roi à l'acceptation (synfoni-v1 porté).

Idiome : chaque salon porte SES messages marqués (``-# kingdom:realm-
content:<key>``) — l'upsert édite en place, purge les doublons, et ne
recrée que ce qui manque. Les ids des messages vivent sur la coquille
(habitat) : ``territory_message`` / ``alliances_message`` /
``welcome_message`` / ``objectifs_message``.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import discord

from .common import (
    fmt_paris,
    kingdom_by_id,
    locale_of,
    lord_of,
    open_unique_ephemeral,
    surface,
    surface_footer,
    wiring,
)
from .common import locale_of

logger = logging.getLogger("kingdom.realms.content")

_NS = "kingdom:realm"
MARKER_PREFIX = "-# kingdom:realm-content"
NO_MENTIONS = discord.AllowedMentions.none()

# The declared surface ids (conf/views.yaml)
TERRITORY_SURFACE = "panel:mod:kingdom:realm:territory"
ALLIANCES_SURFACE = "panel:mod:kingdom:realm:alliances"
WELCOME_SURFACE = "panel:mod:kingdom:realm:welcome"

# The origin emoji of a civilization's acquisition (CIV_ACQUISITION_ORIGINS).
_ORIGIN_EMOJI = {
    "starter": "🎲",
    "condition": "🗺️",
    "marriage": "💍",
    "royal": "👑",
    "mercenary": "📜",
    "exploration": "🧭",
}


# ---------------------------------------------------------------------------
# The strings — verbatim from the reference branch where they existed,
# FR THEN EN mirror (the mod's design rule).
# ---------------------------------------------------------------------------

_CONTENT_STRINGS: dict[str, dict[str, str]] = {
    "fr": {
        "territory_title": "🗺️ Territoire — {0}",
        "territory_count": "{0} territoire(s)",
        "territory_empty": "Aucun territoire pour le moment.",
        "territory_guard": "💂 protégée jusqu'à {0}",
        "territory_note": "La Corruption transfère le territoire de salon (D58).",
        "territory_pending_body": (
            "La carte reste secrète pour l'instant.\n"
            "Au démarrage de la saison, chaque royaume recevra ses "
            "territoires par tirage aléatoire."
        ),
        "territory_sacred": "⛪ SACRÉ — jusqu'à la fin de la saison",
        "territory_chantier": "⏳ Lieu Sacrée — chantier jusqu'au {0}",
        "alliances_panel_title": "🏆 Alliances — {0}",
        "alliances_panel_intro_hand": (
            "Ici se trouve ta main — les civilisations que tu as le droit"
            " d'utiliser actuellement durant tes confrontations !"
        ),
        "alliances_panel_intro_rules": (
            "Tu commences avec tes civilisations de départ, mais attention :"
            " tes alliances évoluent en fonction de tes conquêtes, de tes"
            " mariages et de tes contrats avec des mercenaires."
        ),
        "alliances_panel_intro_cycle": (
            "À chaque passage au prochain cycle, tes alliances s'actualisent !"
        ),
        "alliances_panel_empty": (
            "Aucune civilisation en main — les alliances arrivent par le jeu"
            " (conditions, mariages, Chef Mercenaire)."
        ),
        "alliances_panel_hand": "Ta main : {0}",
        "alliances_panel_pending": (
            "Les alliances se scellent au fil du jeu — la main du royaume"
            " s'affichera ici dès le lancement de la saison."
        ),
        "alliances_panel_help": (
            "-# ❓ Conditions d'alliance : 📜 Scriptorium → rubrique Diplomatie."
        ),
        "alliances_panel_help_named": (
            "-# ❓ Conditions d'obtention des civilisations : {0} → rubrique « 🤝 Diplomatie »."
        ),
        "alliances_btn_next": "📅 Prochain cycle",
        "alliances_btn_locked": "🚫 Verrouillées",
        "alliances_btn_durations": "⏳ Durées",
        "alliances_btn_history": "📖 Historique",
        "alliances_no_data": "❌ Aucune donnée d'alliance disponible pour le moment.",
        "alliances_not_lord": "Seuls les seigneurs du royaume consultent ses alliances.",
        "alliances_next_title": "🔭 Prochain cycle — {0}",
        "alliances_next_intro": (
            "Projection de ta main au prochain cycle d'alliances — ce qui"
            " sera gardé, ce qui arrive, ce qui part."
        ),
        "alliances_next_kept": "✅ Gardées : {0}",
        "alliances_next_nodata": (
            "La projection vit au rythme des cycles du moteur — dès le"
            " premier passage, tout s'actualise ici."
        ),
        "alliances_locked_title": "🚫 Verrouillées par les mariages des autres royaumes — {0}",
        "alliances_locked_line": "🚫 **{0}**",
        "alliances_locked_none": (
            "Aucune civilisation verrouillée par mariage — tout le catalogue"
            " reste jouable."
        ),
        "alliances_durations_title": "⏳ Durées — {0}",
        "alliances_durations_line": "{0} **{1}** — {2}",
        "alliances_durations_none": "Aucune civilisation en main.",
        "alliances_durations_since": "détenue depuis le {0}",
        "alliances_history_title": "📖 Historique — {0}",
        "alliances_history_line": "{0} **{1}** — {2}",
        "alliances_history_none": "Aucune acquisition enregistrée pour le moment.",
        "welcome_title": "💬 Discussions — {0}",
        "welcome_body": (
            "Les portes viennent de s'ouvrir — bienvenue au foyer du royaume.\n\n"
            "Autour de cette table se règlent les affaires du trône : les"
            " stratégies murmurées, les alliances promises, les rumeurs des"
            " marches. Chaque seigneur y a voix — le Roi y a le dernier mot.\n\n"
            "Que le règne commence !"
        ),
        "welcome_hint": (
            "-# Le conseil du Roi FIXEDE les 🎯 objectifs du royaume —"
            " ils s'affichent juste ici, à la suite."
        ),
        "kingdom_accepted_dm": (
            "👑 Ton royaume **{kingdom}** a été accepté !"
            " Ses salons sont prêts : direction {mention} —"
            " l'Entrée du royaume pour commencer. Bonne conquête !"
        ),
        "objectifs_pin_title": "🎯 Objectifs du royaume — {0}",
        "objectifs_pin_none": "Aucun objectif défini — le Roi tranche en Salle du conseil.",
        "objectifs_pin_line": "{0} {1}",
        "objectifs_pin_kind_kingdom": "⚔️",
        "objectifs_pin_kind_territory": "🗺️",
        "objectifs_pin_kind_alliance": "🤝",
    },
    "en": {
        "territory_title": "🗺️ Territory — {0}",
        "territory_count": "{0} territor(y|ies)",
        "territory_empty": "No territory yet.",
        "territory_guard": "💂 shielded until {0}",
        "territory_note": "Corruption moves the territory across salons (D58).",
        "territory_pending_body": (
            "The map stays secret for now.\n"
            "At the season start, each kingdom will receive its "
            "territories through a random draw."
        ),
        "territory_sacred": "⛪ SACRED — until the season ends",
        "territory_chantier": "⏳ Sacred Site — build site until {0}",
        "alliances_panel_title": "🏆 Alliances — {0}",
        "alliances_panel_intro_hand": (
            "Here is your hand — the civilizations you may currently"
            " field in your confrontations!"
        ),
        "alliances_panel_intro_rules": (
            "You start with your starting civilizations, but beware:"
            " your alliances evolve with your conquests, your marriages"
            " and your mercenary contracts."
        ),
        "alliances_panel_intro_cycle": (
            "At every next cycle, your alliances refresh!"
        ),
        "alliances_panel_empty": (
            "No civilization in hand — alliances arrive through play"
            " (conditions, marriages, Chief Mercenary)."
        ),
        "alliances_panel_hand": "Your hand: {0}",
        "alliances_panel_pending": (
            "Alliances are sealed through play — the kingdom's hand"
            " will show here from the season's launch."
        ),
        "alliances_panel_help": (
            "-# ❓ Alliance conditions: 📜 Scriptorium → Diplomacy rubric."
        ),
        "alliances_panel_help_named": (
            "-# ❓ Civilization conditions: {0} → « 🤝 Diplomacy » rubric."
        ),
        "alliances_btn_next": "📅 Next cycle",
        "alliances_btn_locked": "🚫 Locked",
        "alliances_btn_durations": "⏳ Durations",
        "alliances_btn_history": "📖 History",
        "alliances_no_data": "❌ No alliance data available at the moment.",
        "alliances_not_lord": "Only the realm's lords read its alliances.",
        "alliances_next_title": "🔭 Next cycle — {0}",
        "alliances_next_intro": (
            "The projection of your hand at the next alliance cycle —"
            " kept, arriving, leaving."
        ),
        "alliances_next_kept": "✅ Kept: {0}",
        "alliances_next_nodata": (
            "The projection rides the engine's cycles — everything"
            " refreshes here from the first passage."
        ),
        "alliances_locked_title": "🚫 Locked by the marriages of the other realms — {0}",
        "alliances_locked_line": "🚫 **{0}**",
        "alliances_locked_none": (
            "No civilization locked by marriage — the whole catalog"
            " stays playable."
        ),
        "alliances_durations_title": "⏳ Durations — {0}",
        "alliances_durations_line": "{0} **{1}** — {2}",
        "alliances_durations_none": "No civilization in hand.",
        "alliances_durations_since": "held since {0}",
        "alliances_history_title": "📖 History — {0}",
        "alliances_history_line": "{0} **{1}** — {2}",
        "alliances_history_none": "No acquisition recorded yet.",
        "welcome_title": "💬 Discussions — {0}",
        "welcome_body": (
            "The gates have just opened — welcome to the realm's hearth.\n\n"
            "Around this table the throne's business is settled: whispered"
            " strategies, promised alliances, rumors from the marches."
            " Every lord has a voice here — the King has the last word.\n\n"
            "Let the reign begin!"
        ),
        "welcome_hint": (
            "-# The King's council sets the realm's 🎯 objectives —"
            " they show right here, below."
        ),
        "kingdom_accepted_dm": (
            "👑 Your kingdom **{kingdom}** has been accepted!"
            " Its salons are ready: head to {mention} —"
            " the Kingdom's entrance to get started. Good conquest!"
        ),
        "objectifs_pin_title": "🎯 Kingdom objectives — {0}",
        "objectifs_pin_none": "No objective set — the King decides in the Council room.",
        "objectifs_pin_line": "{0} {1}",
        "objectifs_pin_kind_kingdom": "⚔️",
        "objectifs_pin_kind_territory": "🗺️",
        "objectifs_pin_kind_alliance": "🤝",
    },
}


def content_strings(locale: Any) -> dict[str, str]:
    """The realm-content strings for one locale."""
    return _CONTENT_STRINGS["fr"] if not str(locale).lower().startswith("en") else _CONTENT_STRINGS["en"]


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")


def _civ_name(stack: Any, civ_key: str) -> str:
    """A civilization's display name (the config catalog, key fallback)."""
    try:
        for civ in getattr(getattr(stack, "config", None), "civilizations", ()) or ():
            if str(getattr(civ, "key", "")) == str(civ_key):
                return str(getattr(civ, "display_name", "") or civ_key)
    except Exception:  # noqa: BLE001 — a name is never a blocker
        pass
    return str(civ_key)


def _map_name(stack: Any, map_key: str) -> str:
    for entry in getattr(getattr(stack, "config", None), "maps", ()) or ():
        if str(getattr(entry, "key", "")) == str(map_key):
            return str(getattr(entry, "display_name", "") or map_key)
    return str(map_key)


# ---------------------------------------------------------------------------
# The habitat channel resolution — the shell's stored ids FIRST, the
# category-slug adoption as the safety net.
# ---------------------------------------------------------------------------


async def _realm_channels(guild: Any, realm: Any) -> dict[str, Any]:
    """Resolve the realm's salons (discussions/territory/alliances)."""
    disc = dict(getattr(realm, "discord", None) or {})
    out: dict[str, Any] = {}
    for key in ("discussions", "territory", "alliances"):
        channel = None
        stored = str(disc.get(key, "") or "")
        if stored.isdigit():
            try:
                channel = guild.get_channel(int(stored))
            except Exception:  # noqa: BLE001
                channel = None
        if channel is None:
            from .realms import REALM_SALONS, _find_realm_category

            names = {k: display for k, display in REALM_SALONS}
            category = _find_realm_category(guild, str(realm.name))
            if category is not None and key in names:
                wanted = _slug(names[key])
                channel = next(
                    (
                        c
                        for c in getattr(category, "channels", []) or []
                        if _slug(getattr(c, "name", "")) == wanted
                    ),
                    None,
                )
        if channel is None:
            continue
        out[key] = channel
    return out


# ---------------------------------------------------------------------------
# The marked-message upsert — edit in place, purge duplicates, send once.
# ---------------------------------------------------------------------------


def _marker(key: str) -> str:
    return f"{MARKER_PREFIX}:{key}"


async def _history_channel_messages(channel: Any) -> list[Any]:
    try:
        return [message async for message in channel.history(limit=25)]
    except Exception:  # noqa: BLE001
        return []


def _text_of(message: Any) -> str:
    return str(getattr(message, "content", "") or "")


async def _upsert_marked(
    channel: Any,
    key: str,
    content: str,
    view: Any = None,
    pin: bool = False,
    files: list[Any] | None = None,
) -> str:
    """Edit the marked message in place, or send it once. Returns its id."""
    marker = _marker(key)
    marked = [m for m in await _history_channel_messages(channel) if marker in _text_of(m)]
    for duplicate in marked[1:]:
        try:
            await duplicate.delete()
        except Exception:  # noqa: BLE001
            pass
    if marked:
        existing = marked[0]
        kwargs: dict[str, Any] = {"content": content}
        if view is not None:
            kwargs["view"] = view
        if files:
            kwargs["files"] = files
        try:
            await existing.edit(**kwargs)
            return str(getattr(existing, "id", ""))
        except Exception:  # noqa: BLE001 — a dead edit falls back to a fresh send
            logger.warning("kingdom realm content: edit %s failed, resending", key)
    message = await channel.send(
        content=content, view=view, files=files or None, allowed_mentions=NO_MENTIONS
    )
    if pin:
        try:
            await message.pin()
        except Exception:  # noqa: BLE001 — the pin is cosmetic, never a blocker
            pass
    return str(getattr(message, "id", ""))


async def _drop_marked(channel: Any, key: str) -> None:
    """Best-effort delete of one marked message (the eject hygiene)."""
    marker = _marker(key)
    for message in await _history_channel_messages(channel):
        if marker in _text_of(message):
            try:
                await message.delete()
            except Exception:  # noqa: BLE001
                pass


# ---------------------------------------------------------------------------
# The sheets — Territoire, Alliances (+ her four windows), the welcome,
# the objectifs pin.
# ---------------------------------------------------------------------------


async def season_started(stack: Any) -> bool:
    """True when the season LEFT its sas (phase 'started')."""
    if stack is None:
        return False
    try:
        season = await stack.kingdoms.current_season()
    except Exception:  # noqa: BLE001
        return False
    return season is not None and str(getattr(season, "phase", "")) == "started"


async def _owned_territories(stack: Any, kingdom: Any) -> list[Any]:
    kid = str(getattr(kingdom, "id", ""))
    owned: list[Any] = []
    try:
        territories = getattr(stack, "territories", None)
        if territories is not None:
            for territory in await territories.territories():
                if str(getattr(territory, "owner_kingdom_id", "")) == kid:
                    owned.append(territory)
    except Exception:  # noqa: BLE001
        return []
    return owned


def _territory_body(
    strings: dict[str, str],
    stack: Any,
    kingdom: Any,
    territories: list[Any],
) -> str:
    import time as _time

    now_ts = int(_time.time())
    lines = [strings["territory_count"].format(len(territories))]
    if not territories:
        lines.append(strings["territory_empty"])
    for territory in territories:
        map_key = str(getattr(territory, "map_key", ""))
        line = f"• **{_map_name(stack, map_key)}**"
        until = getattr(territory, "protected_until", None)
        if until is not None:
            try:
                until_ts = int(until.timestamp())
            except AttributeError:
                until_ts = int(until)
            if until_ts > now_ts:
                line += f" {strings['territory_guard'].format(fmt_paris(until_ts))}"
        lines.append(line)
    lines.append(f"-# {strings['territory_note']}")
    return "\n".join(lines)


def _hand_line(strings: dict[str, str], stack: Any, kingdom: Any) -> str:
    ledger = dict(getattr(kingdom, "civilization_acquisitions", None) or {})
    hand = [str(civ) for civ in getattr(kingdom, "civilizations", []) or []]
    if not hand:
        return ""
    tiles = []
    for civ in hand:
        origin = str((ledger.get(civ) or {}).get("origin", "") or "")
        emoji = _ORIGIN_EMOJI.get(origin, "")
        name = _civ_name(stack, civ)
        tiles.append(f"{emoji} **{name}**".strip())
    return strings["alliances_panel_hand"].format(" · ".join(tiles))


async def _alliances_body(
    strings: dict[str, str], stack: Any, kingdom: Any, guild: Any
) -> str:
    hand = _hand_line(strings, stack, kingdom)
    mercenary: list[str] = []
    try:
        for member in await stack.kingdoms.lords():
            if str(getattr(member, "kingdom_id", "")) != str(kingdom.id):
                continue
            merc_civ = getattr(member, "mercenary_civilization", None)
            merc_uses = int(getattr(member, "mercenary_uses_left", 0) or 0)
            if merc_civ and merc_uses > 0:
                mercenary.append(
                    f"⚔️ **{getattr(member, 'display_name', '?')}** —"
                    f" {_civ_name(stack, str(merc_civ))} ({merc_uses})"
                )
    except Exception:  # noqa: BLE001
        mercenary = []
    lines = [
        strings["alliances_panel_intro_hand"],
        strings["alliances_panel_intro_rules"],
        strings["alliances_panel_intro_cycle"],
        "",
    ]
    started = await season_started(stack)
    if not started:
        lines.append(strings["alliances_panel_pending"])
    elif hand:
        lines.append(hand)
    else:
        lines.append(strings["alliances_panel_empty"])
    lines.extend(mercenary)
    lines.append("")
    mention = _scriptorium_mention(guild)
    lines.append(
        strings["alliances_panel_help_named"].format(mention)
        if mention
        else strings["alliances_panel_help"]
    )
    return "\n".join(lines)


def _scriptorium_mention(guild: Any) -> str:
    """The Scriptorium salon's clickable mention, '' when absent."""
    for channel in getattr(guild, "channels", []) or []:
        if _slug(getattr(channel, "name", "")) == "scriptorium":
            return f"<#{getattr(channel, 'id', '')}>"
    return ""


async def _alliances_view(
    strings: dict[str, str], stack: Any, kingdom: Any, guild: Any, locale: Any,
    mosaic: bool = False,
) -> Any:
    body = await _alliances_body(strings, stack, kingdom, guild)
    items: list[Any] = [
        RealmAlliancesNextButton(strings["alliances_btn_next"]).item,
        RealmAlliancesLockedButton(strings["alliances_btn_locked"]).item,
        RealmAlliancesDurationsButton(strings["alliances_btn_durations"]).item,
        RealmAlliancesHistoryButton(strings["alliances_btn_history"]).item,
    ]
    if mosaic:
        # mosaic-render-fix (porté T3b): a Components V2 attachment only
        # renders when a gallery REFERENCES it — the mosaic rides above
        # the panel, the crests never stack as bare attachments.
        items.append(discord.ui.MediaGallery(discord.MediaGalleryItem("attachment://alliances.png")))
    view = surface(ALLIANCES_SURFACE, *items)
    return f"## {strings['alliances_panel_title'].format(str(getattr(kingdom, 'name', '')))}\n\n{body}", view


def _welcome_content(
    strings: dict[str, str], realm: Any, kingdom: Any
) -> str:
    body = strings["welcome_body"]
    title = strings["welcome_title"].format(str(getattr(realm, "name", "")))
    return (
        f"# {title}\n\n{body}\n\n{strings['welcome_hint']}"
        f"\n\n{surface_footer(WELCOME_SURFACE)}\n\n{_marker('welcome')}"
    )


def _objectifs_content(
    strings: dict[str, str],
    kingdom: Any,
) -> str:
    goals = dict(getattr(kingdom, "council_objectives", None) or {})
    kinds = {
        "target_kingdom": strings["objectifs_pin_kind_kingdom"],
        "target_territory": strings["objectifs_pin_kind_territory"],
        "target_alliance": strings["objectifs_pin_kind_alliance"],
    }
    lines = [f"## {strings['objectifs_pin_title'].format(str(getattr(kingdom, 'name', '')))}", ""]
    any_goal = False
    for kind, emoji in kinds.items():
        label = str(goals.get(f"{kind}_label", "") or "").strip()
        if not label:
            continue
        any_goal = True
        lines.append(strings["objectifs_pin_line"].format(emoji, label))
    if not any_goal:
        lines.append(strings["objectifs_pin_none"])
    lines.append("")
    lines.append(_marker("objectifs"))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# The four alliances windows (ephemeral, read-only — the declared note
# idiom rides only the panel; the windows are the panel's own surface).
# ---------------------------------------------------------------------------


async def _window_next(strings: dict[str, str], kingdom: Any, stack: Any) -> str:
    hand = [str(c) for c in getattr(kingdom, "civilizations", []) or []]
    names = " · ".join(_civ_name(stack, civ) for civ in hand) or "—"
    return "\n".join([
        f"## {strings['alliances_next_title'].format(str(getattr(kingdom, 'name', '')))}",
        "",
        strings["alliances_next_intro"],
        "",
        strings["alliances_next_kept"].format(names),
        "",
        strings["alliances_next_nodata"],
    ])


async def _window_locked(strings: dict[str, str], kingdom: Any, stack: Any) -> str:
    lines = [f"## {strings['alliances_locked_title'].format(str(getattr(kingdom, 'name', '')))}", ""]
    locked: list[str] = []
    try:
        hand = {str(c) for c in getattr(kingdom, "civilizations", []) or []}
        for member in await stack.kingdoms.lords():
            married = getattr(member, "married_civilization", None)
            if married and str(member.kingdom_id) != str(kingdom.id) and str(married) not in hand:
                locked.append(strings["alliances_locked_line"].format(_civ_name(stack, str(married))))
    except Exception:  # noqa: BLE001
        locked = []
    lines.extend(locked or [strings["alliances_locked_none"]])
    return "\n".join(lines)


async def _window_durations(strings: dict[str, str], kingdom: Any, stack: Any) -> str:
    lines = [f"## {strings['alliances_durations_title'].format(str(getattr(kingdom, 'name', '')))}", ""]
    ledger = dict(getattr(kingdom, "civilization_acquisitions", None) or {})
    hand = [str(c) for c in getattr(kingdom, "civilizations", []) or []]
    if not hand:
        lines.append(strings["alliances_durations_none"])
    else:
        for civ in hand:
            at = (ledger.get(civ) or {}).get("at")
            since = fmt_paris(int(at)) if at else "?"
            lines.append(
                strings["alliances_durations_line"].format(
                    _ORIGIN_EMOJI.get(str((ledger.get(civ) or {}).get("origin", "")), ""),
                    _civ_name(stack, civ),
                    strings["alliances_durations_since"].format(since),
                )
            )
    return "\n".join(lines)


async def _window_history(strings: dict[str, str], kingdom: Any, stack: Any) -> str:
    lines = [f"## {strings['alliances_history_title'].format(str(getattr(kingdom, 'name', '')))}", ""]
    ledger = dict(getattr(kingdom, "civilization_acquisitions", None) or {})
    if not ledger:
        lines.append(strings["alliances_history_none"])
    else:
        for civ, entry in sorted(ledger.items(), key=lambda kv: int((kv[1] or {}).get("at", 0) or 0)):
            at = (entry or {}).get("at")
            when = fmt_paris(int(at)) if at else "?"
            origin = _ORIGIN_EMOJI.get(str((entry or {}).get("origin", "")), "")
            lines.append(
                strings["alliances_history_line"].format(
                    origin, _civ_name(stack, str(civ)), when
                )
            )
    return "\n".join(lines)


_WINDOWS = {
    "next": _window_next,
    "locked": _window_locked,
    "durations": _window_durations,
    "history": _window_history,
}


def _alliance_button_class(kind: str) -> type[discord.ui.DynamicItem[discord.ui.Button[Any]]]:
    class _RealmAlliancesButton(
        discord.ui.DynamicItem[discord.ui.Button[Any]],
        template=rf"{_NS}:alliances:{kind}",
    ):
        def __init__(self, label: str, disabled: bool = False) -> None:
            super().__init__(
                discord.ui.Button(
                    label=label[:80],
                    custom_id=f"{_NS}:alliances:{kind}",
                    style=discord.ButtonStyle.secondary,
                    disabled=disabled,
                )
            )

        @classmethod
        async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
            return cls(content_strings(locale_of(interaction))[f"alliances_btn_{kind}"])

        async def callback(self, interaction: discord.Interaction) -> None:
            await interaction.response.defer(ephemeral=True)
            stack = wiring()
            kingdoms = getattr(stack, "kingdoms", None)
            if kingdoms is None:
                await open_unique_ephemeral(
                    interaction, content=content_strings(locale_of(interaction))["alliances_no_data"]
                )
                return
            lord = await lord_of(kingdoms, str(getattr(interaction.user, "id", "")), interaction)
            if lord is None or bool(getattr(lord, "left", False)):
                await open_unique_ephemeral(
                    interaction, content=content_strings(locale_of(interaction))["alliances_not_lord"]
                )
                return
            kingdom = await kingdom_by_id(kingdoms, getattr(lord, "kingdom_id", None))
            if kingdom is None:
                await open_unique_ephemeral(
                    interaction, content=content_strings(locale_of(interaction))["alliances_no_data"]
                )
                return
            strings = content_strings(locale_of(interaction))
            body = await _WINDOWS[kind](strings, kingdom, stack)
            await open_unique_ephemeral(interaction, content=body)

    return _RealmAlliancesButton


RealmAlliancesNextButton = _alliance_button_class("next")
RealmAlliancesLockedButton = _alliance_button_class("locked")
RealmAlliancesDurationsButton = _alliance_button_class("durations")
RealmAlliancesHistoryButton = _alliance_button_class("history")


def realm_content_dynamic_items() -> tuple:
    """The restart-proof dynamic items of the content engine."""
    return (
        RealmAlliancesNextButton,
        RealmAlliancesLockedButton,
        RealmAlliancesDurationsButton,
        RealmAlliancesHistoryButton,
    )


def wiring() -> Any:
    from .common import wiring as _w

    return _w()


# ---------------------------------------------------------------------------
# The deploys — the acceptance pass AND the season-launch pass.
# ---------------------------------------------------------------------------


async def deploy_realm_content(
    guild: Any,
    realm: Any,
    kingdom: Any,
    locale: Any = "fr",
) -> dict[str, str]:
    """Deploy every realm-salon view of ONE engaged realm (idempotent).

    Returns the new habitat ids to persist on the shell. Best-effort
    per salon: a broken sheet never blocks the others.
    """
    stack = wiring()
    strings = content_strings(locale)
    channels = await _realm_channels(guild, realm)
    ids: dict[str, str] = {}
    started = await season_started(stack)

    territory = channels.get("territory")
    if territory is not None:
        try:
            if started:
                owned = await _owned_territories(stack, kingdom)
                body = _territory_body(strings, stack, kingdom, owned)
            else:
                body = strings["territory_pending_body"]
            content = (
                f"## {strings['territory_title'].format(str(getattr(kingdom, 'name', '')))}"
                f"\n\n{body}\n\n{surface_footer(TERRITORY_SURFACE)}\n\n{_marker('territory')}"
            )
            ids["territory_message"] = await _upsert_marked(territory, "territory", content)
        except Exception:  # noqa: BLE001
            logger.warning("kingdom realm content: territory deploy failed", exc_info=True)

    alliances = channels.get("alliances")
    if alliances is not None:
        # mosaïque-blasons-v1 (Vague 2): the panel wears ONE composite
        # mosaic of the hand's crests — every tile carries its origin
        # badge, ONE attachment whatever the hand's size.
        mosaic_file: Any = None
        try:
            from .civ_crests import civ_crest_mosaic_file

            ledger = dict(getattr(kingdom, "civilization_acquisitions", None) or {})
            catalog = list(getattr(getattr(stack, "config", None), "civilizations", ()) or ())
            names = {
                str(getattr(entry, "key", "")): str(getattr(entry, "display_name", ""))
                for entry in catalog
            }
            hand = [str(civ) for civ in getattr(kingdom, "civilizations", []) or []]
            mosaic_file = await civ_crest_mosaic_file(
                [
                    (
                        civ,
                        (ledger.get(civ) or {}).get("origin") or "",
                        names.get(civ, civ),
                    )
                    for civ in hand
                ]
            )
        except Exception:  # noqa: BLE001 — the mosaic is cosmetic
            logger.warning("kingdom realm content: alliances mosaic failed", exc_info=True)
        try:
            content, view = await _alliances_view(
                strings, stack, kingdom, guild, locale, mosaic=mosaic_file is not None
            )
            content = f"{content}\n\n{_marker('alliances')}"
            ids["alliances_message"] = await _upsert_marked(
                alliances,
                "alliances",
                content,
                view=view,
                files=[mosaic_file] if mosaic_file is not None else None,
            )
        except Exception:  # noqa: BLE001
            logger.warning("kingdom realm content: alliances deploy failed", exc_info=True)

    return ids


async def deploy_realm_welcome(
    guild: Any,
    realm: Any,
    kingdom: Any,
    locale: Any = "fr",
) -> dict[str, str]:
    """The 💬 Discussions welcome message — RP, posted ONCE per entry."""
    strings = content_strings(locale)
    channels = await _realm_channels(guild, realm)
    discussions = channels.get("discussions")
    if discussions is None:
        return {}
    try:
        ids = {
            "welcome_message": await _upsert_marked(
                discussions, "welcome", _welcome_content(strings, realm, kingdom), pin=True
            )
        }
    except Exception:  # noqa: BLE001
        logger.warning("kingdom realm content: welcome deploy failed", exc_info=True)
        return {}
    return ids


async def refresh_objectifs_pin_safe(
    guild: Any, kingdom: Any, locale: Any = "fr", realm: Any = None
) -> bool:
    """The 🎯 objectifs recap in Discussions — edited in place, never stacked."""
    if realm is None:
        return False
    strings = content_strings(locale)
    channels = await _realm_channels(guild, realm)
    discussions = channels.get("discussions")
    if discussions is None:
        return False
    try:
        await _upsert_marked(
            discussions, "objectifs", _objectifs_content(strings, kingdom), pin=True
        )
        return True
    except Exception:  # noqa: BLE001
        logger.warning("kingdom realm content: objectifs pin refresh failed", exc_info=True)
        return False


async def dm_the_king(
    guild: Any, realm: Any, kingdom: Any, locale: Any = "fr"
) -> bool:
    """The synfoni-v1 DM — a validated realm never leaves its King mute."""
    strings = content_strings(locale)
    disc = dict(getattr(realm, "discord", None) or {})
    hub_id = str(disc.get("hub", "") or "")
    mention = f"<#{hub_id}>" if hub_id.isdigit() else "l'Entrée du royaume"
    king_id = str(getattr(realm, "king_id", "") or "")
    member = None
    if king_id.isdigit():
        try:
            member = guild.get_member(int(king_id))
            if member is None:
                member = await guild.fetch_member(int(king_id))
        except Exception:  # noqa: BLE001
            member = None
    if member is None:
        logger.info("kingdom realm content: King %s unresolvable — DM skipped", king_id)
        return False
    try:
        await member.send(
            strings["kingdom_accepted_dm"].format(
                kingdom=str(getattr(kingdom, "name", "")), mention=mention
            )
        )
        return True
    except Exception:  # noqa: BLE001 — the DM is best-effort, never a blocker
        logger.warning("kingdom realm content: King DM failed", exc_info=True)
        return False


async def announce_acceptance(
    guild: Any,
    realm: Any,
    kingdom: Any,
    locale: Any = "fr",
) -> dict[str, str]:
    """The acceptance bundle — DM the King, welcome Discussions, feed the salons."""
    ids: dict[str, str] = {}
    await dm_the_king(guild, realm, kingdom, locale)
    ids.update(await deploy_realm_welcome(guild, realm, kingdom, locale))
    ids.update(await deploy_realm_content(guild, realm, kingdom, locale))
    return ids


async def wipe_realm_content(guild: Any, realm: Any) -> None:
    """The eject hygiene — the entry's messages leave with its kingdom."""
    try:
        channels = await _realm_channels(guild, realm)
        for channel in channels.values():
            for key in ("territory", "alliances", "welcome", "objectifs"):
                await _drop_marked(channel, key)
    except Exception:  # noqa: BLE001
        logger.warning("kingdom realm content: eject wipe failed", exc_info=True)


async def deploy_all_realms_content(bot: Any, locale: Any = "fr") -> int:
    """The season-launch pass — feed every ENGAGED realm of every guild."""
    from .realms import _realm_service
    from .common import wiring as _w

    stack = _w()
    service = _realm_service(stack)
    if service is None:
        return 0
    touched = 0
    try:
        realms = await service.realms()
    except Exception:  # noqa: BLE001
        return 0
    for guild in list(getattr(bot, "guilds", []) or []):
        for realm in realms:
            engagement = getattr(realm, "engagement", None)
            if not engagement:
                continue
            kingdom = await kingdom_by_id(
                getattr(stack, "kingdoms", None), engagement.get("kingdom_id", "")
            )
            if kingdom is None:
                continue
            ids = await deploy_realm_content(guild, realm, kingdom, locale)
            if ids:
                await service.save_habitat(str(realm.id), dict(ids))
            touched += 1
    return touched
