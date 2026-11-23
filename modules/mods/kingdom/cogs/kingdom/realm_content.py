"""Kingdom mod — the realm salons' content engine (realm-content-v1).

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
        # gaia-territory-v1 (Drasah 23/11) : la fiche Territoire de Gaïa,
        # verbatim de la référence (restructuration-serveur-v1 c)
        "gaia_ai_level": "🤖 Niveau de l'IA Gaïa : {0}/5",
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
        "gaia_ai_level": "🤖 Gaïa AI level: {0}/5",
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


# locked-salon-v1 (Drasah 23/11) : le décodage décor-aveugle vit dans
# realms (l'ancre d'adoption des salons) ; ce module le RE-EXPORTE car
# le scan Gaïa de la fenêtre État l'utilise aussi (mêmes décorations).
from .realms import _bot_can_view, _slug_blind  # noqa: E402


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
    """Resolve the realm's salons (discussions/territory/alliances).

    locked-salon-v1 (Drasah 23/11) : l'id stocké d'abord — MAIS un salon
    que le bot NE PEUT PAS LIRE (l'ancienne dormancy l'avait verrouillé)
    n'est PAS une résolution : la fiche y mourrait en 403 pour toujours.
    Le fallback est décor-aveugle (une charte renommée reste la même) et
    PRÉFÈRE un salon accessible — un salon verrouillé n'est choisi qu'en
    dernier recours, l'ensure le remplacera.
    """
    from .realms import REALM_SALONS, _find_realm_category

    disc = dict(getattr(realm, "discord", None) or {})
    out: dict[str, Any] = {}
    names = {k: display for k, display in REALM_SALONS}
    category = _find_realm_category(guild, str(realm.name))
    for key in ("discussions", "territory", "alliances"):
        channel = None
        skipped_locked = False
        stored = str(disc.get(key, "") or "")
        if stored.isdigit():
            getter = getattr(guild, "get_channel", None)
            candidate = None
            if getter is not None:
                try:
                    candidate = getter(int(stored))
                except Exception:  # noqa: BLE001
                    candidate = None
            if candidate is not None and _bot_can_view(guild, candidate):
                channel = candidate
            elif candidate is not None:
                skipped_locked = True
        if channel is None and category is not None and key in names:
            wanted = _slug_blind(names[key])
            siblings = [
                c
                for c in (getattr(category, "channels", []) or [])
                if _slug_blind(getattr(c, "name", "")) == wanted
            ]
            accessible = [c for c in siblings if _bot_can_view(guild, c)]
            channel = (accessible or siblings or [None])[0]
        if channel is None:
            if skipped_locked:
                logger.warning(
                    "kingdom realm content: le salon %s stocké est verrouillé (realm %s) — heal en amont",
                    key, str(getattr(realm, "name", "?")),
                )
            continue
        out[key] = channel
    return out


# ---------------------------------------------------------------------------
# The marked-message upsert — edit in place, purge duplicates, send once.
# ---------------------------------------------------------------------------


def _marker(key: str) -> str:
    return f"{MARKER_PREFIX}:{key}"


# dernier-mètre-v1 (Drasah 23/11) : le « dernier mètre » avalait ses
# échecs en silence (l'envoi de la fiche échouait, seul le log voyait
# l'erreur). Le registre en mémoire capture L'ERREUR EXACTE par fiche
# à chaque passe — la fenêtre État l'affiche, le succès l'efface. Un
# redémarrage le vide : c'est dit à l'admin, jamais caché.
_SURFACE_ERRORS: dict[str, str] = {}


def _record_surface_error(scope: str, exc: BaseException | None) -> None:
    """Record the last send error of one fiche (None clears it)."""
    if exc is None:
        _SURFACE_ERRORS.pop(scope, None)
        return
    text = f"{type(exc).__name__}: {exc}".strip()[:200]
    _SURFACE_ERRORS[scope] = text


def surface_errors() -> dict[str, str]:
    """A copy of the live surface errors (the État window's lines)."""
    return dict(_SURFACE_ERRORS)


async def _history_channel_messages(channel: Any) -> list[Any]:
    try:
        return [message async for message in channel.history(limit=25)]
    except Exception:  # noqa: BLE001
        return []


def _text_of(message: Any) -> str:
    """The readable text of a message — content PLUS the components tree.

    alliances-panel-v2-fix (Drasah 23/11) : un message Composants V2
    voyage avec un ``content`` VIDE — son texte (et le marqueur de la
    fiche) vivent dans les TextDisplay de l'arbre des composants. Le
    scan « marked » porté de la référence (message_text) marchait sur
    le seul ``content`` : il retrouvait un panneau V2 à chaque passe…
    et le DUPLIQUAIT au lieu de l'éditer. La lecture parcourt donc
    l'arbre entier (components, layout, view — défensif), en collectant
    chaque ``content`` de TextDisplay.
    """
    parts = [str(getattr(message, "content", "") or "")]
    stack: list[Any] = list(getattr(message, "components", None) or [])
    for extra in ("layout", "view"):
        item = getattr(message, extra, None)
        if item is not None:
            stack.append(item)
    while stack:
        item = stack.pop()
        text = getattr(item, "content", None)
        if isinstance(text, str):
            parts.append(text)
        stack.extend(getattr(item, "children", None) or [])
    return "\n".join(parts)


async def _upsert_marked(
    channel: Any,
    key: str,
    content: str | None,
    view: Any = None,
    pin: bool = False,
    files: list[Any] | None = None,
) -> str:
    """Edit the marked message in place, or send it once. Returns its id.

    alliances-panel-v2-fix (Drasah 23/11) : un panneau Composants V2
    voyage avec un content VIDE — le texte vit dans la vue. Quand le
    ``content`` est None, il n'est PASSÉ NI à l'édition NI à l'envoi :
    Discord extipe « The 'content' field cannot be used when using
    MessageFlags.IS_COMPONENTS_V2 » (l'incident live 15:38, salon 🏆
    vide à chaque passe). La recherche du marqueur lit l'arbre des
    composants (le marqueur vit dans la vue aussi).
    """
    marker = _marker(key)
    marked = [m for m in await _history_channel_messages(channel) if marker in _text_of(m)]
    for duplicate in marked[1:]:
        try:
            await duplicate.delete()
        except Exception:  # noqa: BLE001
            pass
    if marked:
        existing = marked[0]
        kwargs: dict[str, Any] = {}
        if content is not None:
            kwargs["content"] = content
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
) -> tuple[str | None, Any]:
    """The 🏆 panel — ONE Components V2 message, text INSIDE the view.

    alliances-panel-v2-fix (Drasah 23/11, incident live 15:38) : un
    message Composants V2 supporte TROIS États, pas un mélange : le
    texte dans ``content`` (interdit avec le drapeau V2 — « The 'content'
    field cannot be used when using MessageFlags.IS_COMPONENTS_V2 »,
    l'erreur 15:38 qui laissait le salon 🏆 vide), le texte en blocs
    DANS la vue (la construction de la RÉFÉRENCE : titre, corps,
    légende et marqueur vivaient dans ses TextDisplay, et le message
    partait vue seule), ou les deux v0 (aucun drapeau V2). On suit la
    référence : le titre, le corps ET le marqueur de la fiche vivent
    en TextDisplay dans la vue, le message part SANS content.
    """
    body = await _alliances_body(strings, stack, kingdom, guild)
    head = (
        f"## {strings['alliances_panel_title'].format(str(getattr(kingdom, 'name', '')))}"
        f"\n\n{body}\n\n{_marker('alliances')}"
    )
    # les composants interactifs voyagent dans une ActionRow (règle de
    # la référence) : en racine, un bouton NU serait rejeté (« Value of
    # field "type" must be one of (1, 9, 10, 12, 13, 14, 17) », l'erreur
    # 10:12). Racine = [TextDisplay, ActionRow, MediaGallery, pied].
    buttons = [
        RealmAlliancesNextButton(strings["alliances_btn_next"]).item,
        RealmAlliancesLockedButton(strings["alliances_btn_locked"]).item,
        RealmAlliancesDurationsButton(strings["alliances_btn_durations"]).item,
        RealmAlliancesHistoryButton(strings["alliances_btn_history"]).item,
    ]
    items: list[Any] = [
        discord.ui.TextDisplay(head),
        discord.ui.ActionRow(*buttons),
    ]
    if mosaic:
        # mosaic-render-fix (porté T3b): a Components V2 attachment only
        # renders when a gallery REFERENCES it — the mosaic rides above
        # the panel, the crests never stack as bare attachments.
        items.append(discord.ui.MediaGallery(discord.MediaGalleryItem("attachment://alliances.png")))
    view = surface(ALLIANCES_SURFACE, *items)
    return None, view


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


async def _upsert_sheet(
    guild: Any,
    realm: Any,
    channel: Any,
    key: str,
    content: str | None,
    *,
    view: Any = None,
    files: list[Any] | None = None,
    pin: bool = False,
) -> str | None:
    """Send ONE sheet, sealing the salon's own structure on a 403.

    missing-access-v1 (Drasah 23/11) — l'incident live AEGIS/HeN, PROUVÉ
    par la fenêtre État (« 403 Missing Access » sur les fiches) : un
    salon avec SES PROPRES overwrites n'hérite plus l'allow de la
    catégorie, et le bot pouvait se retrouver scellé HORS de SON
    propre royaume. La passe ne masque plus jamais un refus : sur un
    Forbidden, elle re-ensure la structure (le seam adoption + dormancy,
    qui porte l'allow du bot ET remplace un salon verrouillé — ce que
    la simulation a prouvé irréparable par édition), PUIS réessaie UNE
    fois SUR LE SALON RÉSOLU APRÈS LE HEAL (l'ancien salon verrouillé
    restait l'objet du retry : la fiche mourait en 403 sur un cadavre).
    Tout autre échec reste best-effort, consigné dans la fenêtre État.
    """
    rname = str(getattr(realm, "name", "?"))
    kwargs: dict[str, Any] = {"view": view, "files": files, "pin": pin}
    mid: str | None = None
    try:
        mid = await _upsert_marked(channel, key, content, **kwargs)
        _record_surface_error(f"{rname}·{key}", None)
        return mid
    except discord.Forbidden as exc:
        _record_surface_error(f"{rname}·{key}", exc)
        logger.warning(
            "kingdom realm content: %s deploy FORBIDDEN (realm %s) — healing the structure and retrying once",
            key, rname,
        )
    except Exception as exc:  # noqa: BLE001
        _record_surface_error(f"{rname}·{key}", exc)
        logger.warning("kingdom realm content: %s deploy failed", key, exc_info=True)
        return None
    # le heal : le salon se scellait seul, le seam le rouvre au bot —
    # et un salon VERROUILLÉ (que le bot ne peut plus lire : Discord
    # refuse l'édition) est REMPLACÉ par l'ensure, la résolution
    # repart donc de l'habitat GUÉRI, jamais du cadavre d'origine.
    try:
        from .realms import ensure_realm_structure

        ensured = await ensure_realm_structure(guild, realm, dormant=False)
    except Exception as exc:  # noqa: BLE001 — le heal reste best-effort
        _record_surface_error(f"{rname}·{key}", exc)
        logger.warning(
            "kingdom realm content: %s heal failed (realm %s)", key, rname, exc_info=True
        )
        return None
    healed: Any = None
    ensured_id = str(ensured.get(key, "") or "")
    getter = getattr(guild, "get_channel", None)
    if ensured_id.isdigit() and getter is not None:
        try:
            healed = getter(int(ensured_id))
        except Exception:  # noqa: BLE001
            healed = None
    if healed is None:
        healed = (await _realm_channels(guild, realm)).get(key)
    if healed is None or healed is channel:
        logger.warning(
            "kingdom realm content: %s heal resolved no fresh salon (realm %s)", key, rname
        )
        return None
    try:
        mid = await _upsert_marked(healed, key, content, **kwargs)
    except Exception as exc:  # noqa: BLE001 — le retry reste best-effort
        _record_surface_error(f"{rname}·{key}", exc)
        logger.warning(
            "kingdom realm content: %s heal retry failed (realm %s)", key, rname, exc_info=True
        )
        return None
    _record_surface_error(f"{rname}·{key}", None)
    logger.info(
        "kingdom realm content: %s of %s self-healed after a Forbidden", key, rname
    )
    return mid


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
    if not channels:
        # territory-reveal-v1 (23/11) : un réveil raté ne se masque plus —
        # adoption par slug déjà tentée, la panne est ici NOMMÉE.
        logger.info(
            "kingdom realm content: no salon resolved for realm %s — the wake or the structure failed",
            getattr(realm, "name", "?"),
        )
        # dernier-mètre-v1 (Drasah 23/11) : le miss muet devient une
        # ligne LISIBLE dans la fenêtre État — l'admin ne lit pas de logs.
        _record_surface_error(
            f"{getattr(realm, 'name', '?')}·territoire",
            RuntimeError("aucun salon résolu (le réveil ou la structure)"),
        )
    ids: dict[str, str] = {}
    started = await season_started(stack)
    rname = str(getattr(realm, "name", "?"))

    territory = channels.get("territory")
    if territory is not None:
        if started:
            owned = await _owned_territories(stack, kingdom)
            body = _territory_body(strings, stack, kingdom, owned)
        else:
            body = strings["territory_pending_body"]
        content = (
            f"## {strings['territory_title'].format(str(getattr(kingdom, 'name', '')))}"
            f"\n\n{body}\n\n{surface_footer(TERRITORY_SURFACE)}\n\n{_marker('territory')}"
        )
        # missing-access-v1 (Drasah 23/11) : la fiche passe par le
        # seam _upsert_sheet — un 403 sur SON salon déclenche le
        # heal (re-ensure structure) et UN retry, sans clic admin.
        mid = await _upsert_sheet(guild, realm, territory, "territory", content)
        if mid is not None:
            ids["territory_message"] = mid

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
            # alliances-panel-v2-fix : le texte ET le marqueur vivent dans
            # la vue — le panneau part SANS content (le mélange était
            # 400-rejeté, l'incident live 15:38).
            _, view = await _alliances_view(
                strings, stack, kingdom, guild, locale, mosaic=mosaic_file is not None
            )
            # missing-access-v1 (Drasah 23/11) : même seam que la fiche
            # territoire — heal + UN retry sur un 403, la mosaïque suit.
            mid = await _upsert_sheet(
                guild,
                realm,
                alliances,
                "alliances",
                None,
                view=view,
                files=[mosaic_file] if mosaic_file is not None else None,
            )
            if mid is not None:
                ids["alliances_message"] = mid
        except Exception as exc:  # noqa: BLE001
            _record_surface_error(f"{rname}·alliances", exc)
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


# ---------------------------------------------------------------------------
# territory-reveal-v1 (Drasah 23/11) : le tirage référence, REBRANCHÉ.
#
# L'incident du 23/11 : les salons 🌍 Territoire restaient vides après le
# départ — le portage n'avait jamais raccordé la DISTRIBUTION initiale
# des cartes (le moteur sait la faire, plus personne ne l'appelait).
# La règle de la référence (sa regression 2026-10-11, verbatim) : le
# tirage précède le rendu, jamais l'inverse — les fiches se lisent
# dans des documents vivants, jamais dans l'état pré-tirage.
# ---------------------------------------------------------------------------


async def draw_initial_territories_safe(bot: Any) -> bool:
    """Best-effort season initial draw (guarded, never duplicates).

    The reference's own guards, unchanged: nothing is drawn while the
    season waits in ``setup`` (Drasah's phase rule — the reveal is the
    admin's departure), and an existing territory means the season
    already drew its slice.
    """
    stack = wiring()
    territories_service = getattr(stack, "territories", None)
    if territories_service is None:
        return False
    if not await season_started(stack):
        logger.info("kingdom: territory draw deferred — the season is not started")
        return False
    try:
        if await territories_service.territories():
            logger.info("kingdom: initial territory draw skipped — territories exist")
            return False
        await territories_service.draw_initial()
        logger.info("kingdom: initial territory draw ran at the season reveal")
        return True
    except Exception:  # noqa: BLE001 — the dashboard reports, never raises
        logger.warning("kingdom: initial territory draw failed", exc_info=True)
        return False


async def draw_starting_civilizations_safe(bot: Any) -> dict[str, list[str]]:
    """Best-effort starting-hand catch-up (guarded, the seam is optional).

    alliances-last-mile-v1 (Drasah 23/11) — le MÊME principe que le
    tirage de territoires : le panneau Alliances (la main, la mosaïque
    de blasons, la fenêtre « Prochaine main ») lit UNE seule source de
    vérité, la main du royaume côté moteur. Une saison partie sans son
    draft de départ y montrait une main vide pour toujours ; la passe
    de 5 min rattrape donc les mains MANQUANTES AVANT de rendre les
    fiches (le tirage précède le rendu, la règle de la référence) via
    le seam moteur ``draw_missing_starting_draft`` — jamais de
    réimplémentation, jamais de rendu ad hoc.
    """
    stack = wiring()
    kingdoms_service = getattr(stack, "kingdoms", None)
    seam = getattr(kingdoms_service, "draw_missing_starting_draft", None)
    if seam is None:
        return {}
    if not await season_started(stack):
        logger.info("kingdom: starting-hand catch-up deferred — the season is not started")
        return {}
    try:
        report = await seam()
        if report:
            logger.info("kingdom: starting hands caught up at the pass — %s", list(report))
        return report
    except Exception:  # noqa: BLE001 — the report reports, never raises
        logger.warning("kingdom: starting-hand catch-up failed", exc_info=True)
        return {}


# ---------------------------------------------------------------------------
# gaia-territory-v1 (Drasah 23/11) : la fiche Territoire de Gaïa, REPRISE
# de la référence (restructuration-serveur-v1 c) : le niveau de l'IA lu
# LIVE dans l'epoch de la saison (D18, fallback 1), jamais codé en dur,
# puis SES territoires avec les mêmes badges que les royaumes joueurs.
# Gaïa n'a pas de main de civilisations — pas de panneau Alliances.
# ---------------------------------------------------------------------------


async def _gaia_territory_channel(guild: Any) -> Any:
    """Gaïa's 🌍 Territoire salon — the DECLARED seam first, scan second.

    gaia-seam-fix-v1 (Drasah 23/11) : le pidcase est PROUVÉ — la
    catégorie chartée « 🏰 ᴋɪɴɢᴅᴏᴍs-ɢᴀɪᴀ » ne matche JAMAIS le scan
    naive (slug « s »). La source de vérité devient le seam core du
    salon déclaré (mod/kingdom + territory, celui des 10 autres
    salons du mod — provisioning l'enregistre à la création) ; le
    scan devient le FALLBACK décoration-aveugle (adoption par nom,
    pour une structure provisionnée hors seam). Chaque miss se
    CONSIGNE : plus jamais une fiche Gaïa muette.
    """
    gid = str(getattr(guild, "id", "") or "")
    if gid:
        try:
            from botforge.discord.ui.panels_provisioning import stored_channel_id

            channel_id = await stored_channel_id(gid, "mod/kingdom", "territory")
            if channel_id and str(channel_id).isdigit():
                channel = guild.get_channel(int(channel_id))
                if channel is not None:
                    return channel
                logger.warning(
                    "kingdom realm content: stored gaia territory channel %s "
                    "not found in guild %s — falling back to the blind scan",
                    channel_id, gid,
                )
        except Exception:  # noqa: BLE001 — the seam read never blocks the scan
            logger.warning(
                "kingdom realm content: the stored gaia territory seam read failed",
                exc_info=True,
            )
    wanted = ("kingdom-gaia", "kingdoms-gaia", "kingdoms-ga-a", "kingdoms", "kingdom")
    for category in getattr(guild, "categories", []) or []:
        slug = _slug_blind(str(getattr(category, "name", "")))
        if slug not in wanted:
            continue
        for channel in getattr(category, "channels", []) or []:
            if _slug_blind(str(getattr(channel, "name", ""))) == "territoire":
                return channel
    logger.warning(
        "kingdom realm content: no gaia territory salon in guild %s — "
        "blind-candidates %s",
        gid,
        ", ".join(
            f"« {getattr(c, 'name', '?')} » → « {_slug_blind(str(getattr(c, 'name', '')))} »"
            for c in (getattr(guild, "categories", []) or [])
        )
        or "aucune catégorie",
    )
    return None


async def deploy_gaia_content(guild: Any, locale: Any = "fr") -> bool:
    """Deploy the Gaïa 🌍 Territoire sheet (idempotent, best-effort).

    Gaïa is an ENGINE kingdom with no shell — the realm feeding pass
    can never see it, its sheet rides its own deployer (the reference's
    own design, unchanged).
    """
    stack = wiring()
    channel = await _gaia_territory_channel(guild)
    if channel is None:
        _record_surface_error("Gaïa·territoire", RuntimeError("salon introuvable"))
        return False
    kingdoms_service = getattr(stack, "kingdoms", None)
    if kingdoms_service is None:
        return False
    try:
        kingdoms = await kingdoms_service.kingdoms()
    except Exception:  # noqa: BLE001
        logger.warning("kingdom realm content: gaia kingdom read failed", exc_info=True)
        return False
    kingdom = next((k for k in kingdoms if bool(getattr(k, "is_gaia", False))), None)
    if kingdom is None:
        return False
    attacks = getattr(stack, "attacks", None)
    ai_level = 1
    if attacks is not None:
        try:
            ai_level = int(await attacks.base_ai_level())
        except Exception:  # noqa: BLE001 — the fallback level stays honest
            logger.warning("kingdom realm content: gaia ai level read failed", exc_info=True)
    strings = content_strings(locale)
    owned = await _owned_territories(stack, kingdom)
    body = "\n".join([strings["gaia_ai_level"].format(int(ai_level)), _territory_body(strings, stack, kingdom, owned)])
    content = (
        f"## {strings['territory_title'].format('Gaïa')}"
        f"\n\n{body}\n\n{surface_footer(TERRITORY_SURFACE)}\n\n{_marker('territory-gaia')}"
    )
    try:
        await _upsert_marked(channel, "territory-gaia", content)
        _record_surface_error("Gaïa·territoire", None)
        return True
    except Exception as exc:  # noqa: BLE001
        _record_surface_error("Gaïa·territoire", exc)
        logger.warning("kingdom realm content: gaia territory deploy failed", exc_info=True)
        return False


async def feed_season_surfaces(bot: Any, locale: Any = "fr") -> int:
    """The season-launch feeding — draw, every realm sheet, then Gaïa.

    ONE seam for the three call sites (classic departure, beta departure,
    the beta loop's 5-minute pass): the reveal draw runs FIRST, then
    the realm sheets read the LIVE documents, then Gaïa's own sheet.
    The loop's pass self-heals a failed launch (a skipped draw is
    retried five minutes later — nothing stays silent).
    """
    # état-surfaces-v1 (Drasah 23/11) : la passe se CONSIGNE — la
    # fenêtre État de l'atelier rapporte le dernier passage vivant
    # (l'enregistrement est en mémoire : un redémarrage le remet à
    # zéro, et c'est dit à l'admin, jamais caché).
    drawn = False
    try:
        drawn = await draw_initial_territories_safe(bot)
    except Exception:  # noqa: BLE001 — the report never blocks the feed
        logger.warning("kingdom realm content: the report's draw read failed", exc_info=True)
    # alliances-last-mile-v1 : la main de civilisations précède le rendu —
    # le panneau Alliances ne se nourrit QUE de la donnée moteur.
    await draw_starting_civilizations_safe(bot)
    touched = await deploy_all_realms_content(bot, locale)
    for guild in list(getattr(bot, "guilds", []) or []):
        try:
            await deploy_gaia_content(guild, locale)
        except Exception:  # noqa: BLE001 — Gaïa never blocks the realms
            logger.warning("kingdom realm content: gaia deploy failed", exc_info=True)
    _record_feed_pass(touched=touched, drawn=drawn)
    return touched


# ---------------------------------------------------------------------------
# état-surfaces-v1 (Drasah 23/11) : la fenêtre « 🧭 État des surfaces » de
# l'Atelier — LE DIAGNOSTIC VISIBLE DISCORD. Les fiches restaient vides
# sans qu'aucune surface ne dise POURQUOI (les échecs du tuyau étaient
# avalés en silence, Drasah ne lit pas de logs) : ce rapport lit les
# MÊMES documents vivants que la passe nourrissante (engagement de la
# coquille, royaume moteur pointé, salons résolus, tirage moteur, fiches
# marquées posées) et le dernier passage en mémoire. Chaque maillon
# cassé se lit noir sur blanc, en un clic, éphémère, admin seul.
# ---------------------------------------------------------------------------

_LAST_FEED_PASS: dict[str, Any] = {}


def _record_feed_pass(*, touched: int, drawn: bool) -> None:
    """Keep the last pass in memory (the window's `Dernière passe` line)."""
    import time as _time

    _LAST_FEED_PASS.clear()
    _LAST_FEED_PASS.update(
        {"at": int(_time.time()), "touched": int(touched), "drawn": bool(drawn)}
    )


def last_feed_pass() -> dict[str, Any]:
    """A copy of the last pass record (empty dict when never run yet)."""
    return dict(_LAST_FEED_PASS)


async def _marker_present(channel: Any, key: str) -> bool:
    """Whether the marked message of ``key`` lives in the salon (read-only)."""
    try:
        return any(
            _marker(key) in _text_of(m) for m in await _history_channel_messages(channel)
        )
    except Exception:  # noqa: BLE001 — a read, never a crash
        return False


def _gaia_category_scan(guild: Any) -> str:
    """The categories that READ like Kingdom-Gaia, raw name + both slugs.

    The line that PROVED the pidcase: the real charted name « 🏰
    ᴋɪɴɢᴅᴏᴍs-ɢᴀɪᴀ » slugs to « s » under the naive regex — the
    window shows it verbatim, naive AND decoration-blind, so the
    admin sees the mismatch heal (blind) or persist (naive) himself.
    """
    try:
        names = [
            f"« {getattr(category, 'name', '?')} » → naive « {_slug(str(getattr(category, 'name', '')))} » "
            f"· aveugle « {_slug_blind(str(getattr(category, 'name', '')))} »"
            for category in (getattr(guild, "categories", []) or [])
            if any(
                token in str(getattr(category, "name", "")).lower()
                for token in ("ingdom", "ɪɴɢ", "gaïa", "gaia")
            )
        ]
    except Exception:  # noqa: BLE001
        return ""
    return " ".join(names)


async def surfaces_state(bot: Any) -> dict[str, Any]:
    """The live truth of the feeding seams — the window's ONE read.

    Pure reads, never a send: the season, the engine draw, every realm
    shell (engagement, pointed kingdom, resolved salons, cards, posted
    sheets) and Gaïa's own line. Best-effort per block: a broken read
    shows up as its own line, never a crash of the window.
    """
    stack = wiring()
    out: dict[str, Any] = {
        "stack": stack is not None,
        "season": None,
        "started": False,
        "territories": None,
        "pass": last_feed_pass(),
        "realms": [],
        "gaia": None,
    }
    if stack is None:
        return out
    try:
        season = await stack.kingdoms.current_season()
        if season is not None:
            out["season"] = {
                "name": str(getattr(season, "name", "") or ""),
                "phase": str(getattr(season, "phase", "") or ""),
            }
    except Exception:  # noqa: BLE001
        logger.warning("kingdom realm content: the state season read failed", exc_info=True)
    out["started"] = await season_started(stack)
    try:
        territories = getattr(stack, "territories", None)
        out["territories"] = len(await territories.territories()) if territories else None
    except Exception:  # noqa: BLE001
        logger.warning("kingdom realm content: the state draw read failed", exc_info=True)
    kingdoms: list[Any] = []
    try:
        kingdoms = list(await stack.kingdoms.kingdoms())
    except Exception:  # noqa: BLE001
        logger.warning("kingdom realm content: the state kingdoms read failed", exc_info=True)

    guilds = list(getattr(bot, "guilds", []) or [])
    from .realms import _realm_service

    service = _realm_service(stack)
    realms: list[Any] = []
    if service is not None:
        try:
            realms = await service.realms()
        except Exception:  # noqa: BLE001 — the window reports, never raises
            logger.warning("kingdom realm content: the state realms read failed", exc_info=True)
    for realm in realms or []:
        if getattr(realm, "archived_at", None):
            continue
        rname = str(getattr(realm, "name", "?"))
        engagement = getattr(realm, "engagement", None) or {}
        kingdom = await kingdom_by_id(getattr(stack, "kingdoms", None), engagement.get("kingdom_id", ""))
        channels: dict[str, Any] = {}
        for guild in guilds:
            channels = await _realm_channels(guild, realm)
            if channels.get("territory") or channels.get("alliances") or channels.get("discussions"):
                break
        cards = len(await _owned_territories(stack, kingdom)) if kingdom is not None else 0
        territory_channel = channels.get("territory")
        alliances_channel = channels.get("alliances")
        errors = surface_errors()
        realm_errors = [
            f"{key.rsplit('·', 1)[-1]}: {errors[key]}"
            for key in (f"{rname}·territoire", f"{rname}·alliances")
            if key in errors
        ]
        out["realms"].append(
            {
                "name": rname,
                "engaged": bool(engagement),
                "kingdom": str(getattr(kingdom, "name", "") or "") if kingdom is not None else "",
                "discussions": "discussions" in channels,
                "territory": "territory" in channels,
                "alliances": "alliances" in channels,
                "cards": cards,
                "fiche_territory": await _marker_present(territory_channel, "territory")
                if territory_channel is not None
                else False,
                "fiche_alliances": await _marker_present(alliances_channel, "alliances")
                if alliances_channel is not None
                else False,
                "error": "; ".join(realm_errors),
            }
        )
    gaia_kingdom = next((k for k in kingdoms if bool(getattr(k, "is_gaia", False))), None)
    for guild in guilds:
        channel = await _gaia_territory_channel(guild)
        out["gaia"] = {
            "kingdom": str(getattr(gaia_kingdom, "name", "") or "") if gaia_kingdom is not None else "",
            "found": channel is not None,
            "channel_name": str(getattr(channel, "name", "") or "") if channel is not None else "",
            "scan": _gaia_category_scan(guild),
            "error": surface_errors().get("Gaïa·territoire", ""),
            "cards": len(await _owned_territories(stack, gaia_kingdom))
            if gaia_kingdom is not None
            else 0,
            "fiche": await _marker_present(channel, "territory-gaia")
            if channel is not None
            else False,
        }
        break
    return out
