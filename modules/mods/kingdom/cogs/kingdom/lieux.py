"""lieux-portage-v1 (Drasah 21/11) — the castle's FIVE illustrated places.

PORTAGE of the diverged branch's `lieux-et-conseil-v1` (vibe/drasah/main,
kingdom_lieux.py), à l'identique : the engaged realm's 🏰 Entrée opens
« Où souhaitez-vous vous rendre ? » — the five doors of the castle
(⚔️ Salle du conseil · 🧱 Remparts · 🏛️ Chambre des comptes · ⛪ Paroisse
· 🏗️ Volière), each opening an ILLUSTRATED window (the 8 PNG of
assets/lieux, uploaded by Drasah 01/11). Tranche 1 = the CONSULTATION
faces (the ROUGE/VERT action cards, the 🎯 Objectifs, the Classement
and the in-place wizards ride tranche 2).

Architecture (the portage rules): the VIEWS are the reference branch's
(faithful labels, illustrations, Sortir-in-red-last), the DATA rides
the NEW engine's seams only — stack.kingdoms (lords/kingdoms/parish),
stack.territories, stack.attacks.technology_state (+ base_ai_level),
stack.config.parish (the palier ladder). The dormant realm's hub is
UNTOUCHED (hors-sas = the chez-soi window stays the Entrée's door);
ONLY an ENGAGED realm routes Entrée here (Drasah 21/11 : « l'ancienne
vue ne doit pas être écrasée — la vue dans le sas réattribue ce
qu'on avait fait auparavant »).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import discord

from .common import (
    fmt_paris,
    open_unique_ephemeral,
    surface,
    wiring,
)

logger = logging.getLogger("kingdom.lieux")

# The deployment-local illustrations (uploaded by Drasah 01/11 — the
# file names on disk are irregular ON PURPOSE, they mirror the upload).
_LIEUX_ASSETS = Path(__file__).resolve().parents[2] / "assets" / "lieux"

_NS = "kingdoms:lieux"
# realm-content-v1 : la vue de cueilleur d'objectifs (Roi-only)
OBJECTIF_SURFACE = "panel:mod:kingdom:lieux:objectif"
CONSEIL_SURFACE = "panel:mod:kingdom:lieux:conseil"

GOLD = discord.Colour(0xE6B800)
TEAL = discord.Colour.dark_teal()
GREEN = discord.Colour.green()

ENTREE_SURFACE = "panel:mod:kingdom:lieux:entree"
CONSEIL_SURFACE = "panel:mod:kingdom:lieux:conseil"
REMPARTS_SURFACE = "panel:mod:kingdom:lieux:remparts"
COMPTES_SURFACE = "panel:mod:kingdom:lieux:comptes"
PAROISSE_SURFACE = "panel:mod:kingdom:lieux:paroisse"
VOLIERE_SURFACE = "panel:mod:kingdom:lieux:voliere"
# vague2-actions-v1 (Drasah 21/11) : les nouvelles fenêtres d'action
PAROISSE_UPGRADE_SURFACE = "panel:mod:kingdom:lieux:paroisse-upgrade"
HIST_SURFACE = "panel:mod:kingdom:lieux:hist"
TRAQUENARD_SURFACE = "panel:mod:kingdom:lieux:traquenard"

# Les étiquettes du registre (portées de la référence, market_tech +
# market_action fusionnés) — l'item inconnu garde sa clé brute.
_HIST_LABELS: dict[str, dict[str, str]] = {
    "fr": {
        "embuscade": "🥷 Embuscade",
        "traquenard": "🪤 Traquenard",
        "contre_espionnage": "👀 Contre-espionnage",
        "sabotage": "🗡️ Sabotage",
        "jeu_d_armes": "⚔️ Jeu d'armes",
        "explorateur": "🧭 Explorateur",
        "corruption": "💰 Corruption",
        "garde_royale": "💂 Garde Royale",
        "patrouille": "👣 Patrouille",
        "mariage_arrange": "💐 Mariage arrangé",
    },
    "en": {
        "embuscade": "🥷 Ambush",
        "traquenard": "🪤 Traquenard",
        "contre_espionnage": "👀 Counter-espionage",
        "sabotage": "🗡️ Sabotage",
        "jeu_d_armes": "⚔️ Arms Mastery",
        "explorateur": "🧭 Explorer",
        "corruption": "💰 Corruption",
        "garde_royale": "💂 Royal Guard",
        "patrouille": "👣 Patrol",
        "mariage_arrange": "💐 Arranged marriage",
    },
}
_HIST_EMOJI: dict[str, str] = {
    "embuscade": "🥷",
    "traquenard": "🪤",
    "contre_espionnage": "👀",
    "sabotage": "🗡️",
    "jeu_d_armes": "⚔️",
    "explorateur": "🧭",
    "corruption": "💰",
    "garde_royale": "💂",
    "patrouille": "👣",
    "mariage_arrange": "💐",
}


def _hist_label(strings: dict[str, str], item: str) -> str:
    return str(_HIST_LABELS.get(_locale_of_catalog(strings), _HIST_LABELS["fr"]).get(item, item))

# The volière bird catalog (voliere-v2 : pigeon / corbeau / faucon).
_BIRD_EMOJI = {"pigeon": "🕊️", "corbeau": "🐦‍⬛", "faucon": "🦅"}


# ---------------------------------------------------------------------------
# The strings — VERBATIM from the reference branch (kingdom_lieux.py +
# kingdom_realm_content.py + kingdom_voliere_panel.py, fr THEN en mirror).
# retrait-chez-soi (Drasah 21/11) : « on n'en a pas besoin » — la
# 6ᵉ porte qui vivait ici a disparu avec les strings qui la portaient.
# ---------------------------------------------------------------------------

LIEUX_STRINGS: dict[str, dict[str, str]] = {
    "fr": {
        "entree_button": "🏰 Entrée",
        "entree_title": "Où souhaitez-vous vous rendre ?",
        "conseil_button": "⚔️ Salle du conseil",
        "remparts_button": "🧱 Remparts",
        "comptes_button": "🏛️ Chambre des comptes",
        "paroisse_button": "⛪ Paroisse",
        "voliere_button": "🏗️ Volière",
        "sortir_button": "🚪 Sortir",
        "not_lord": (
            "Seuls les seigneurs du royaume peuvent entrer dans ses lieux."
        ),
        "no_service": "Le service Kingdoms n'est pas câblé.",
        "conseil_title": "⚔️ Salle du conseil — {0}",
        "conseil_intro_l1": (
            "Jetez un coup d'œil aux attaques et défenses de vos seigneurs —"
            " leurs mariages comme leurs verrouillages."
        ),
        "conseil_intro_l2": (
            "Vous pouvez définir vos objectifs pour mieux vous coordonner :"
            " attaque de royaume, map recherchée ou alliance recherchée."
        ),
        "conseil_intro_l3": (
            "Vous pouvez aussi organiser vos explorations ou vos traquenards"
            " depuis cette interface."
        ),
        "conseil_classement": "**Classement** : {0}",
        "conseil_classement_hint": (
            "-# Classement par nombre de territoires — en cas d'égalité :"
            " alliances, puis points technologiques."
        ),
        "conseil_objectifs_title": "🎯 Objectifs",
        "conseil_objectif_kingdom": "⚔️ Royaume à focus : **{0}**",
        "conseil_objectif_map": "🗺️ Territoire recherché : **{0}**",
        "conseil_objectif_alliance": "🤝 Alliance recherchée : **{0}**",
        "conseil_objectifs_none": (
            "Aucun objectif fixé pour le moment — le Roi peut les définir"
            " avec le bouton 🎯 Objectif."
        ),
        "conseil_traquenard_title": "**🪤 Traquenard**",
        "conseil_traquenard_line": (
            "Vous avez affaibli le niveau de l'IA du royaume **{0}** —"
            " actif pendant {1}"
        ),
        "objectif_button": "🎯 Objectif",
        "objectif_king_only": "🎯 Réservé au Roi du royaume.",
        "objectif_picker_title": "🎯 Objectifs du royaume — {0}",
        "objectif_select_kingdom": "⚔️ Royaume à attaquer en priorité",
        "objectif_select_map": "🗺️ Territoire recherché",
        "objectif_select_alliance": "🤝 Alliance souhaitée",
        "objectif_none_label": "🚫 Aucun — ne pas définir",
        "objectif_validate_button": "✅ Valider",
        "objectif_flip_prev": "◀️ Précédent",
        "objectif_flip_next": "▶️ Suivant",
        "objectif_flip_pages": "Page {0}/{1} · {2}",
        "objectif_edit_hint": (
            "-# Chaque menu choisi devient un objectif, affiché à tes"
            " membres — ◀️ Précédent / ▶️ Suivant feuillettent les pages de"
            " la liste, ✅ Valider pour sauvegarder, 🚪 Quitter pour fermer"
            " sans sauvegarder."
        ),
        "objectif_save_failed": "⚠️ Sauvegarde échouée — réessaie dans un instant.",
        "objectif_done_note": "🎯 Objectifs sauvegardés — l'épinglé de Discussions est à jour.",
        "conseil_seigneurie_button": "🛡️ Seigneurie",
        "conseil_stats": (
            "**Trésorerie** : {0} ⚙️ · **Territoires** : {1} 🗺️ ·"
            " **Alliances** : {2} 🤝"
        ),
        "patrol_title": "🧱 Remparts — {0}",
        "remparts_ai_level": "🤖 Niveau de votre IA : **{0}/5 {1}**",
        "remparts_patrouille_title": "👣 **Patrouille :**",
        "remparts_patrouille_title_reinforced": "👣 **Patrouilles Renforcées :**",
        "remparts_state_missing": (
            "❌ Vous ne disposez pas de patrouille [{0}/2] —"
            " achat au Marché (2 ⚙️)"
        ),
        "remparts_state_unplaced": (
            "⚠️ Vous disposez d'une patrouille [{0}/2] —"
            " cliquez sur le bouton Patrouille pour la paramétrer"
        ),
        "remparts_state_active": (
            "⏲ Votre patrouille [{0}/2] est bien active entre"
            " {1:02d}h00 et {2:02d}h00"
        ),
        "remparts_garde_title": "💂 **Garde Royal :**",
        "remparts_garde_owned_one": "Vous disposez de {0} garde royal",
        "remparts_garde_owned_many": "Vous disposez de {0} gardes royaux",
        "remparts_garde_owned_none": "Vous ne disposez d'aucun Garde Royal",
        "remparts_guard_line": "✅ {0} — protégée jusqu'à {1}",
        "remparts_guard_stock": "En réserve : {0}",
        # vague2-actions-v1 (Drasah 21/11) : rangée 2 des Remparts
        "remparts_use_jeu": "⚔️ Jeu d'armes",
        "remparts_use_patrouille": "🚨 Patrouille",
        "remparts_use_garde": "💂 Garde royale",
        "conseil_card_exploration": "🧭 Exploration",
        "conseil_card_traquenard": "🪤 Traquenard",
        "traquenard_select": "Choisissez le royaume à piéger :",
        "traquenard_done": (
            "✅ Traquenard armé contre **{0}** — l'IA affrontée devient "
            "Facile <t:{1}:R>. {2} verrou(s) vivant(s) étendu(s) +2h."
        ),
        "action_error_note": "❌ {0}",
        "paroisse_marry_button": "💍 Se marier",
        "paroisse_upgrade_button": "⛪ Améliorer : {0}",
        "paroisse_upgrade_max": "⛪ Palier maximum atteint",
        "paroisse_upgrade_confirm": "Améliorer la Paroisse vers **{0}** pour **{1}** ⚙️ ?",
        "paroisse_upgrade_ok": "✅ Améliorer",
        "paroisse_upgrade_cancel": "❌ Annuler",
        "paroisse_upgrade_done": "✅ La Paroisse est désormais **{0}**.",
        "hist_achats_button": "📜 Historique achats",
        "hist_actions_button": "⚔️ Historique actions",
        "hist_achats_title": "📜 Historique des achats",
        "hist_actions_title": "⚔️ Historique des actions",
        "hist_achats_empty": "Aucun achat pour le moment.",
        "hist_actions_empty": "Aucune carte utilisée pour le moment.",
        "hist_purchase_line": "{0} {1} — {2} · {3} ⚙️ · {4}",
        "hist_action_line": "{0} {1} — {2} · {3}",
        "comptes_title": "🏛️ Chambre des comptes — {0}",
        "paroisse_title": "⛪ Paroisse — {0}",
        "paroisse_tier_line": (
            "Palier : {0} ({1}/{2}) — Offrande 🎁 : +{3} ⚙️ par mariage"
        ),
        "paroisse_stats_line": (
            "💍 Bague : {0} · 💐 Mariage arrangé : {1} · ⚙️ Point Technologie : {2}"
        ),
        "voliere_title": "# 🪶 Volière de {kingdom}",
        "voliere_line": (
            "Gratuite dès l'Âge Féodal — cooldowns partagés par tout le royaume."
        ),
        "bird_ready": "🪶 **{bird}** — sur son perchoir, prêt",
        "bird_flying": "🕊️ **{bird}** — en vol, retour <t:{ts}:R>",
        "voliere_corbeau": "**Corbeau**",
        "voliere_faucon": "**Faucon**",
        "voliere_pigeon": "**Pigeon**",
        "ai_levels": (
            "Très facile|Standard|Intermédiaire|Difficile|Plus difficile|Expert"
        ),
    },
    "en": {
        "entree_button": "🏰 Entrance",
        "entree_title": "Where would you like to go?",
        "conseil_button": "⚔️ Council room",
        "remparts_button": "🧱 Ramparts",
        "comptes_button": "🏛️ Chamber of accounts",
        "paroisse_button": "⛪ Parish",
        "voliere_button": "🏗️ Aviary",
        "sortir_button": "🚪 Leave",
        "not_lord": (
            "Only the lords of this kingdom may enter its places."
        ),
        "no_service": "The Kingdoms service is not wired.",
        "conseil_title": "⚔️ Council room — {0}",
        "conseil_intro_l1": (
            "Keep an eye on your lords' attacks and defenses — their"
            " marriages as well as their locks."
        ),
        "conseil_intro_l2": (
            "You may set your objectives to coordinate better: a kingdom"
            " to strike, a map you seek or an alliance you covet."
        ),
        "conseil_intro_l3": (
            "You can also organise your explorations or your traps from"
            " this interface."
        ),
        "conseil_classement": "**Rank** : {0}",
        "conseil_classement_hint": (
            "-# Ranked by territories — ties broken by alliances, then"
            " technology points."
        ),
        "conseil_objectifs_title": "🎯 Objectives",
        "conseil_objectif_kingdom": "⚔️ Kingdom to focus : **{0}**",
        "conseil_objectif_map": "🗺️ Territory sought : **{0}**",
        "conseil_objectif_alliance": "🤝 Alliance wanted : **{0}**",
        "conseil_objectifs_none": (
            "No objective set yet — the King may define them with the"
            " 🎯 Objective button."
        ),
        "conseil_traquenard_title": "**🪤 Trap**",
        "conseil_traquenard_line": (
            "You weakened the AI level of the kingdom **{0}** — active"
            " for {1}"
        ),
        "objectif_button": "🎯 Objectives",
        "objectif_king_only": "🎯 Reserved to the King of the realm.",
        "objectif_picker_title": "🎯 Kingdom objectives — {0}",
        "objectif_select_kingdom": "⚔️ Kingdom to strike first",
        "objectif_select_map": "🗺️ Territory you seek",
        "objectif_select_alliance": "🤝 Alliance you covet",
        "objectif_none_label": "🚫 None — leave undefined",
        "objectif_validate_button": "✅ Apply",
        "objectif_flip_prev": "◀️ Previous",
        "objectif_flip_next": "▶️ Next",
        "objectif_flip_pages": "Page {0}/{1} · {2}",
        "objectif_edit_hint": (
            "-# Every menu picked becomes an objective, shown to your"
            " members — ◀️ Previous / ▶️ Next flip the list pages,"
            " ✅ Apply to save, 🚪 Leave to close without saving."
        ),
        "objectif_save_failed": "⚠️ Save failed — try again in a moment.",
        "objectif_done_note": "🎯 Objectives saved — the Discussions recap is fresh.",
        "conseil_seigneurie_button": "🛡️ Lordship",
        "conseil_stats": (
            "**Treasury** : {0} ⚙️ · **Territories** : {1} 🗺️ ·"
            " **Alliances** : {2} 🤝"
        ),
        "patrol_title": "🧱 Ramparts — {0}",
        "remparts_ai_level": "🤖 Your AI level: **{0}/5 {1}**",
        "remparts_patrouille_title": "👣 **Patrol:**",
        "remparts_patrouille_title_reinforced": "👣 **Reinforced Patrols:**",
        "remparts_state_missing": (
            "❌ You have no patrol [{0}/2] — purchase one at the"
            " Market (2 ⚙️)"
        ),
        "remparts_state_unplaced": (
            "⚠️ You own a patrol [{0}/2] — click the Patrol button"
            " to configure it"
        ),
        "remparts_state_active": (
            "⏲ Your patrol [{0}/2] is active between {1:02d}:00"
            " and {2:02d}:00"
        ),
        "remparts_garde_title": "💂 **Royal Guard:**",
        "remparts_garde_owned_one": "You own {0} Royal Guard",
        "remparts_garde_owned_many": "You own {0} Royal Guards",
        "remparts_garde_owned_none": "You do not own any Royal Guard",
        "remparts_guard_line": "✅ {0} — shielded until {1}",
        "remparts_guard_stock": "In reserve: {0}",
        # vague2-actions-v1 (Drasah 21/11): the Remparts action row 2
        "remparts_use_jeu": "⚔️ Arms Mastery",
        "remparts_use_patrouille": "🚨 Patrol",
        "remparts_use_garde": "💂 Royal Guard",
        "conseil_card_exploration": "🧭 Exploration",
        "conseil_card_traquenard": "🪤 Traquenard",
        "traquenard_select": "Pick the kingdom to trap:",
        "traquenard_done": (
            "✅ Traquenard armed against **{0}** — the AI faced turns "
            "Easy <t:{1}:R>. {2} living lock(s) extended +2h."
        ),
        "action_error_note": "❌ {0}",
        "paroisse_marry_button": "💍 Get married",
        "paroisse_upgrade_button": "⛪ Upgrade: {0}",
        "paroisse_upgrade_max": "⛪ Top tier reached",
        "paroisse_upgrade_confirm": "Upgrade the Parish to **{0}** for **{1}** ⚙️?",
        "paroisse_upgrade_ok": "✅ Upgrade",
        "paroisse_upgrade_cancel": "❌ Cancel",
        "paroisse_upgrade_done": "✅ The Parish now stands at **{0}**.",
        "hist_achats_button": "📜 Purchase history",
        "hist_actions_button": "⚔️ Action history",
        "hist_achats_title": "📜 Purchase history",
        "hist_actions_title": "⚔️ Action history",
        "hist_achats_empty": "No purchase yet.",
        "hist_actions_empty": "No card used yet.",
        "hist_purchase_line": "{0} {1} — {2} · {3} ⚙️ · {4}",
        "hist_action_line": "{0} {1} — {2} · {3}",
        "comptes_title": "🏛️ Chamber of accounts — {0}",
        "paroisse_title": "⛪ Parish — {0}",
        "paroisse_tier_line": (
            "Tier: {0} ({1}/{2}) — Offering 🎁: +{3} ⚙️ per marriage"
        ),
        "paroisse_stats_line": (
            "💍 Ring: {0} · 💐 Arranged marriage: {1} · ⚙️ Tech Point: {2}"
        ),
        "voliere_title": "# 🪶 Aviary of {kingdom}",
        "voliere_line": (
            "Free from the Feudal Age — cooldowns shared by the whole kingdom."
        ),
        "bird_ready": "🪶 **{bird}** — on its perch, ready",
        "bird_flying": "🕊️ **{bird}** — flying, back <t:{ts}:R>",
        "voliere_corbeau": "**Corbeau**",
        "voliere_faucon": "**Faucon**",
        "voliere_pigeon": "**Pigeon**",
        "ai_levels": (
            "Very easy|Standard|Intermediate|Hard|Harder|Expert"
        ),
    },
}


def lieux_strings(locale: Any) -> dict[str, str]:
    """The lieux catalog (fr default, like every mod surface)."""
    raw = getattr(locale, "value", locale) or "fr"
    text = str(raw)
    return LIEUX_STRINGS["fr"] if text.lower().startswith("fr") else LIEUX_STRINGS["en"]


def _locale_of(interaction: discord.Interaction) -> str:
    return str(getattr(interaction, "locale", "fr") or "fr")


# ---------------------------------------------------------------------------
# The illustrations (deployment-local files — best-effort, never a raise)
# ---------------------------------------------------------------------------


def _lieu_file(filename_on_disk: str, filename: str) -> discord.File | None:
    """Best-effort illustration of one lieu (deployment-local asset)."""
    try:
        path = _LIEUX_ASSETS / filename_on_disk
        if not path.is_file():
            logger.warning("kingdom lieux: illustration %s missing", filename_on_disk)
            return None
        return discord.File(path, filename=filename, spoiler=False)
    except Exception:
        logger.warning("kingdom lieux: illustration %s read failed", filename_on_disk, exc_info=True)
        return None


def _lieu_files(filename_on_disk: str, filename: str) -> list[discord.File]:
    file = _lieu_file(filename_on_disk, filename)
    return [file] if file is not None else []


def _bird_label(strings: dict[str, str], bird: str) -> str:
    key = f"voliere_{bird}"
    if key in strings:
        return str(strings[key])
    emoji = _BIRD_EMOJI.get(bird, "🪶")
    return f"{emoji} **{bird}**"


# ---------------------------------------------------------------------------
# The window template — illustration on top, the panel under (the
# reference branch's _panel_view_with_buttons, ports-2 layout face).
# ---------------------------------------------------------------------------


def _lieu_window(
    strings: dict[str, str],
    view_id: str,
    accent: discord.Colour,
    title: str,
    body: str,
    media: str | None,
    rows: list[list[discord.ui.Item[Any]]] | None = None,
) -> discord.ui.LayoutView:
    """One lieu window : illustration TOP, the panel under, Sortir last."""
    blocks: list[discord.ui.Item[discord.ui.LayoutView]] = []
    if media:
        blocks.append(discord.ui.MediaGallery(discord.MediaGalleryItem(media)))
    container_items: list[discord.ui.Item[discord.ui.LayoutView]] = [
        discord.ui.TextDisplay(f"# {title}"),
        discord.ui.Separator(),
        discord.ui.TextDisplay(body),
    ]
    for row in rows or []:
        if row:
            container_items.append(discord.ui.ActionRow(*row))
    blocks.append(discord.ui.Container(*container_items, accent_colour=accent))
    return surface(view_id, *blocks)


def _sortir_item(strings: dict[str, str]) -> discord.ui.Button:
    return _lieu_item(strings, "sortir", discord.ButtonStyle.danger)


def _lieu_item(
    strings: dict[str, str], kind: str, style: discord.ButtonStyle, label: str | None = None
) -> discord.ui.Button:
    """A plain wire button — every lieux door is restart-proof BELOW."""
    return discord.ui.Button(
        label=str(label or strings[f"{kind}_button"])[:80],
        custom_id=f"{_NS}:{kind}",
        style=style,
    )


# ---------------------------------------------------------------------------
# The engine reads (the NEW seams only — lords, kingdoms, technology,
# territories, the parish ladder : stack.kingdoms/.attacks/.territories/.config)
# ---------------------------------------------------------------------------


async def _lord_kingdom_of(
    interaction: discord.Interaction, strings: dict[str, str]
) -> tuple[Any, Any, Any] | tuple[None, None, Any]:
    """Resolve the clicker's lord + kingdom + stack (None,None,stack on miss).

    lieux-portage-v1-hotfix (Drasah 21/11) : le resolveur lit le SEAM
    CANONIQUE du mod — ``lord_of`` (l'admin sans fiche pilote le Roi du
    royaume de test, la règle kingdom-test-v1 portée de la référence).
    Le portage initial lisait ``lord.player_id``, un champ que le moteur
    n'a JAMAIS eu (un seigneur EST son id) → le Roi d'un royaume accepté
    était lu « pas seigneur » (le cas Blanc). ailleurs-vision : le lieu
    montre TOUJOURS le royaume DU CLIQUEUR (l'ancienne branche, jamais
    le hub cliqué) — strict en saison normale, arbitré 21/11.
    """
    from .common import kingdom_by_id, lord_of

    stack = wiring()
    kingdoms = getattr(stack, "kingdoms", None)
    if kingdoms is None:
        await open_unique_ephemeral(interaction, content=strings["no_service"])
        return (None, None, stack)
    user_id = str(getattr(interaction.user, "id", ""))
    lord = await lord_of(kingdoms, user_id, interaction)
    lord = None if lord is None or bool(getattr(lord, "left", False)) else lord
    if lord is None:
        await open_unique_ephemeral(interaction, content=strings["not_lord"])
        return (None, None, stack)
    kingdom = await kingdom_by_id(kingdoms, getattr(lord, "kingdom_id", None))
    if kingdom is None:
        await open_unique_ephemeral(interaction, content=strings["not_lord"])
        return (None, None, stack)
    return (lord, kingdom, stack)


async def _gather_state(stack: Any, kingdom: Any) -> dict[str, Any]:
    """The consultation data (defensive — a missing seam reads empty)."""
    kid = str(getattr(kingdom, "id", ""))
    state: dict[str, Any] = {"wallet": int(getattr(kingdom, "tech_points_bank", 0) or 0)}
    try:
        attacks = getattr(stack, "attacks", None)
        technology = await attacks.technology_state(kid) if attacks is not None else None
        state["purchases"] = dict(getattr(technology, "purchases", {}) or {})
        state["base_ai"] = await attacks.base_ai_level() if attacks is not None else 0
    except Exception:
        state["purchases"] = {}
        state["base_ai"] = 0
    try:
        territories = getattr(stack, "territories", None)
        owned = []
        if territories is not None:
            for territory in await territories.territories():
                if str(getattr(territory, "owner_kingdom_id", "")) == kid:
                    owned.append(territory)
        state["territories"] = owned
    except Exception:
        state["territories"] = []
    return state


def _ai_display(strings: dict[str, str], state: dict[str, Any], kingdom: Any) -> tuple[int, str]:
    """The motor scale IS Drasah's scale (base 0 — fifths to Expert)."""
    import time as _time

    purchases = state.get("purchases") or {}
    level = 0
    try:
        level = min(5, int(state.get("base_ai", 0) or 0) + int(purchases.get("jeu_d_armes", 0) or 0))
        until = int(getattr(kingdom, "traquenard_until", 0) or 0) if getattr(kingdom, "traquenard_until", None) else 0
        if until and until > int(_time.time()):
            level = 0  # the Traquenard window forces the weakened state
    except Exception:
        level = 0
    names = str(strings.get("ai_levels", "") or "").split("|")
    name = names[level].strip() if 0 <= level < len(names) else str(level)
    return level, name


# ---------------------------------------------------------------------------
# The five doors + the two traveling buttons (restart-proof DynamicItems)
# ---------------------------------------------------------------------------


def _lieu_button_class(kind: str, style: discord.ButtonStyle):
    class _Button(
        discord.ui.DynamicItem[discord.ui.Button[Any]], template=rf"{_NS}:{kind}"
    ):
        """One restart-proof hub door of the Entrée chooser."""

        def __init__(self, label: str) -> None:
            super().__init__(
                discord.ui.Button(
                    label=str(label)[:80],
                    custom_id=f"{_NS}:{kind}",
                    style=style,
                )
            )

        @classmethod
        async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
            return cls(lieux_strings(_locale_of(interaction))[f"{kind}_button"])

        async def callback(self, interaction: discord.Interaction) -> None:
            await _open_lieu(interaction, kind)

    _Button.__name__ = f"Lieux{kind.capitalize()}Button"
    _Button.__qualname__ = _Button.__name__
    return _Button


LieuxConseilButton = _lieu_button_class("conseil", discord.ButtonStyle.secondary)
LieuxRempartsButton = _lieu_button_class("remparts", discord.ButtonStyle.secondary)
LieuxComptesButton = _lieu_button_class("comptes", discord.ButtonStyle.secondary)
LieuxParoisseButton = _lieu_button_class("paroisse", discord.ButtonStyle.secondary)
LieuxVoliereButton = _lieu_button_class("voliere", discord.ButtonStyle.secondary)


class LieuxEntreeButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]], template=rf"{_NS}:entree"
):
    """The 🏰 Entrée door — opens the chooser (the ENGAGED realm's hub)."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80], custom_id=f"{_NS}:entree", style=discord.ButtonStyle.primary
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        return cls(lieux_strings(_locale_of(interaction))["entree_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        await open_entree(interaction)


class LieuxSortirButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]], template=rf"{_NS}:sortir"
):
    """The red 🚪 Sortir of every lieu — walks back to the Entrée chooser."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80], custom_id=f"{_NS}:sortir", style=discord.ButtonStyle.danger
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        return cls(lieux_strings(_locale_of(interaction))["sortir_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        await open_entree(interaction)


def lieux_dynamic_items() -> tuple:
    """Every restart-proof DynamicItem of the lieux surfaces."""
    return (
        LieuxEntreeButton,
        LieuxConseilButton,
        LieuxRempartsButton,
        LieuxComptesButton,
        LieuxParoisseButton,
        LieuxVoliereButton,
        LieuxSortirButton,
        LieuxSeigneurieButton,
        LieuxObjectifButton,
        LieuxObjectifSelect,
        LieuxObjectifFlip,
        LieuxObjectifValidateButton,
        # vague2-actions-v1 (Drasah 21/11)
        LieuxRempartsUseButton,
        LieuxExplorationButton,
        LieuxTraquenardButton,
        LieuxTraquenardSelect,
        LieuxParoisseUpgradeButton,
        LieuxParoisseUpgradeOkButton,
        LieuxParoisseUpgradeCancelButton,
        LieuxHistButton,
    )


# ---------------------------------------------------------------------------
# The Entrée chooser — « Où souhaitez-vous vous rendre ? »
# ---------------------------------------------------------------------------


def entree_view(strings: dict[str, str]) -> discord.ui.LayoutView:
    """The ephemeral chooser behind 🏰 Entrée — the five doors in one
    ActionRow (the reference branch's entree_view). retrait-chez-soi
    (Drasah 21/11) : « on n'en a pas besoin » — la 6ᵉ porte disparaît."""
    row: Any = discord.ui.ActionRow(
        LieuxConseilButton(strings["conseil_button"]).item,
        LieuxRempartsButton(strings["remparts_button"]).item,
        LieuxComptesButton(strings["comptes_button"]).item,
        LieuxParoisseButton(strings["paroisse_button"]).item,
        LieuxVoliereButton(strings["voliere_button"]).item,
    )
    return surface(
        ENTREE_SURFACE,
        discord.ui.Container(
            discord.ui.TextDisplay(f"## {strings['entree_title']}"),
            discord.ui.Separator(),
            row,
            accent_colour=GOLD,
        ),
    )


async def open_entree(interaction: discord.Interaction) -> None:
    """Open the Entrée chooser as the clicker's single ephemeral window."""
    strings = lieux_strings(_locale_of(interaction))
    lord, kingdom, stack = await _lord_kingdom_of(interaction, strings)
    if lord is None or kingdom is None:
        return
    await open_unique_ephemeral(interaction, view=entree_view(strings))


async def _shell_of(stack: Any, user_id: str) -> Any:
    """Best-effort — the clicker's realm shell (None when unreadable)."""
    try:
        realms = getattr(stack, "realms", None)
        if realms is None:
            return None
        return await realms.realm_of_member(user_id)
    except Exception:
        return None


async def _open_lieu(interaction: discord.Interaction, kind: str) -> None:
    """Open one lieu as the clicker's single ephemeral window."""
    await interaction.response.defer(ephemeral=True)
    strings = lieux_strings(_locale_of(interaction))
    lord, kingdom, stack = await _lord_kingdom_of(interaction, strings)
    if lord is None or kingdom is None:
        return
    try:
        state = await _gather_state(stack, kingdom)
        if kind == "conseil":
            view, files = await _conseil_window(interaction, strings, lord, kingdom, state)
        elif kind == "remparts":
            view, files = _remparts_window(strings, kingdom, state)
        elif kind == "comptes":
            view, files = await _comptes_window(strings, kingdom, state)
        elif kind == "paroisse":
            view, files = await _paroisse_window(strings, kingdom, state)
        else:  # voliere
            view, files = _voliere_window(strings, kingdom)
    except Exception:
        logger.warning("kingdom lieux: the %s window failed", kind, exc_info=True)
        from .realms import realm_strings as _rs

        await open_unique_ephemeral(interaction, content=str(_rs(_locale_of(interaction))["realm_error_note"]))
        return
    await open_unique_ephemeral(interaction, view=view, files=files or None)


# ---------------------------------------------------------------------------
# ⚔️ Salle du conseil — the FULL sheet (realm-content-v1, Drasah 21/11) :
# intro 3 lignes + Classement (médaille + rang) + stats + 🎯 Objectifs
# (les lignes du Roi) + le statut Traquenard live. Bouton 🎯 Objectif
# ROUGE pour tout le monde hors le Roi (vert pour lui, jamais caché) ;
# cartes Exploration/Traquenard + actions Remparts/Paroisse/Comptes =
# Vague 2 (actions de jeu), PAS cette vague.
# ---------------------------------------------------------------------------

_RANK_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


def _rank_medal(rank: int) -> str:
    rank = int(rank or 0)
    return _RANK_MEDALS.get(rank, "🏰" if rank >= 4 else "")


async def _classement_rows(stack: Any) -> list[tuple[Any, int, int]]:
    """The ranking rows — territories desc, ties by alliances then tech."""
    kingdoms = getattr(stack, "kingdoms", None)
    if kingdoms is None:
        return []
    try:
        items = [k for k in await kingdoms.kingdoms() if not getattr(k, "is_gaia", False)]
        counts = {str(k.id): 0 for k in items}
        territories = getattr(stack, "territories", None)
        if territories is not None:
            for territory in await territories.territories():
                owner = str(getattr(territory, "owner_kingdom_id", ""))
                if owner in counts:
                    counts[owner] += 1
        rows = [(k, counts[str(k.id)], len(getattr(k, "civilizations", []) or [])) for k in items]
        rows.sort(key=lambda row: (-row[1], -row[2], -int(getattr(row[0], "tech_points_bank", 0) or 0)))
        return rows
    except Exception:  # noqa: BLE001
        logger.warning("kingdom lieux: classement rows failed", exc_info=True)
        return []


async def _conseil_rank(stack: Any, kingdom: Any) -> tuple[int, int]:
    rows = await _classement_rows(stack)
    if not rows:
        return (0, 0)
    ids = [str(getattr(row[0], "id", "")) for row in rows]
    kid = str(getattr(kingdom, "id", ""))
    if kid not in ids:
        return (0, len(ids))
    return (ids.index(kid) + 1, len(ids))


async def _traquenard_status_lines(
    strings: dict[str, str], stack: Any, kingdom: Any
) -> list[str]:
    """traquenard-echelle-v1 (porté) : le statut LIVE — une ligne par
    fenêtre Facile encore OUVERTE (``traquenard_uses``), délai « 2h05 »."""
    import time as _time

    uses = dict(getattr(kingdom, "traquenard_uses", None) or {})
    now_ts = int(_time.time())
    live = {str(t): int(u or 0) for t, u in uses.items() if int(u or 0) > now_ts}
    if not live:
        return []
    names: dict[str, str] = {}
    try:
        for item in await stack.kingdoms.kingdoms():
            kid = str(getattr(item, "id", "") or "")
            if kid in live:
                names[kid] = str(getattr(item, "name", "") or kid)
    except Exception:  # noqa: BLE001
        names = {}
    lines = ["", str(strings["conseil_traquenard_title"])]
    for target_id, until in sorted(live.items()):
        remaining = max(0, until - now_ts)
        lines.append(
            str(strings["conseil_traquenard_line"]).format(
                names.get(str(target_id), str(target_id)),
                f"{remaining // 3600}h{(remaining % 3600) // 60:02d}",
            )
        )
    return lines


def _objectifs_lines(strings: dict[str, str], kingdom: Any) -> str:
    """The 🎯 block — one line per defined goal, the none-note otherwise."""
    goals = dict(getattr(kingdom, "council_objectives", None) or {})
    rows = {
        "target_kingdom": strings["conseil_objectif_kingdom"],
        "target_territory": strings["conseil_objectif_map"],
        "target_alliance": strings["conseil_objectif_alliance"],
    }
    parts = []
    for kind, line in rows.items():
        label = str(goals.get(f"{kind}_label", "") or "").strip()
        if label:
            parts.append(line.format(label))
    return "\n".join(parts) if parts else str(strings["conseil_objectifs_none"])


async def _conseil_window(
    interaction: discord.Interaction,
    strings: dict[str, str],
    lord: Any,
    kingdom: Any,
    state: dict[str, Any],
) -> tuple[discord.ui.LayoutView, list[discord.File]]:
    stack = wiring()
    rank = await _conseil_rank(stack, kingdom)
    rank_display = (
        f"{_rank_medal(int(rank[0]))} {int(rank[0])}/{int(rank[1])}".strip()
        if int(rank[0] or 0) > 0 and int(rank[1] or 0) > 0
        else "—"
    )
    body = "\n".join(
        [
            strings["conseil_intro_l1"],
            strings["conseil_intro_l2"],
            strings["conseil_intro_l3"],
            "",
            strings["conseil_classement"].format(rank_display),
            strings["conseil_stats"].format(
                int(state.get("wallet", 0) or 0),
                len(state.get("territories") or []),
                len(getattr(kingdom, "civilizations", []) or []),
            ),
            strings["conseil_classement_hint"],
            "",
            f"## {strings['conseil_objectifs_title']}",
            _objectifs_lines(strings, kingdom),
            *await _traquenard_status_lines(strings, stack, kingdom),
        ]
    )
    viewer_is_king = str(getattr(lord, "role", "")) == "king"
    objectif = LieuxObjectifButton(strings["objectif_button"], king=viewer_is_king)
    rows = [[
        LieuxSeigneurieButton(strings["conseil_seigneurie_button"]).item,
        objectif.item,
        _sortir_item(strings),
    ]]
    # vague2-actions-v1 (Drasah 21/11) : rangée 2 — les cartes d'action
    # 🧭 Exploration / 🪤 Traquenard (vertes si en réserve, grisées sinon,
    # jamais cachées — pattern _remparts_rows de la référence)
    rows.append(_conseil_cards_row(strings, state, kingdom))
    view = _lieu_window(
        strings,
        CONSEIL_SURFACE,
        discord.Colour.gold(),
        strings["conseil_title"].format(str(getattr(kingdom, "name", ""))),
        body,
        "attachment://salle_du_conseil.png",
        rows,
    )
    return view, _lieu_files("salle du conseil.png", "salle_du_conseil.png")


class LieuxSeigneurieButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]], template=rf"{_NS}:seigneurie"
):
    """🛡️ Seigneurie — the lords' roster (the real window is the realm's)."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80], custom_id=f"{_NS}:seigneurie", style=discord.ButtonStyle.success
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        return cls(lieux_strings(_locale_of(interaction))["conseil_seigneurie_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        from .realms import realm_strings, seigneurie_window

        await interaction.response.defer(ephemeral=True)
        stack = wiring()
        realm = await _shell_of(stack, str(getattr(interaction.user, "id", "")))
        strings = realm_strings(_locale_of(interaction))
        if realm is None:
            await open_unique_ephemeral(interaction, content=strings["realm_gone_note"])
            return
        await open_unique_ephemeral(
            interaction, view=await seigneurie_window(interaction, realm, strings)
        )


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# 🎯 Objectif — the King's goal picker (realm-content-v1, porté synfoni-v1)
#
# Trois objectifs INDÉPENDANTS : ⚔️ royaume à focus, 🗺️ territoire
# recherché, 🤝 alliance souhaitée. Les pages (maps/civs > 25) se
# feuillettent ◀️ ▶️, chaque menu devient un objectif stagé, ✅ Valider
# sauvegarde (moteur) et rafraîchit l'épinglé 🎯 de Discussions.
# Le staging vit en mémoire (user id → choix) — éphémère par nature.
# ---------------------------------------------------------------------------

_OBJECTIF_KINDS = ("target_kingdom", "target_territory", "target_alliance")
_OBJECTIF_STAGING: dict[str, dict[str, str]] = {}
_OBJECTIF_PAGES: dict[str, int] = {"target_territory": 0, "target_alliance": 0}


def _staged(user_id: str) -> dict[str, str]:
    return _OBJECTIF_STAGING.setdefault(str(user_id), {})


class LieuxObjectifButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]], template=rf"{_NS}:objectif"
):
    """🎯 Objectif — ROUGE pour tous hors le Roi, VERT pour lui (jamais caché)."""

    def __init__(self, label: str, king: bool = False) -> None:
        super().__init__(
            discord.ui.Button(
                label=str(label)[:80],
                custom_id=f"{_NS}:objectif",
                style=discord.ButtonStyle.success if king else discord.ButtonStyle.danger,
                disabled=not king,
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        # after a restart the role is re-read — the button renders
        # harmless until the callback re-checks the King's crown
        return cls(lieux_strings(_locale_of(interaction))["objectif_button"], king=True)

    async def callback(self, interaction: discord.Interaction) -> None:
        from botforge.mods.kingdom.models import LordRole

        await interaction.response.defer(ephemeral=True)
        strings = lieux_strings(_locale_of(interaction))
        lord, kingdom, stack = await _lord_kingdom_of(interaction, strings)
        if lord is None or kingdom is None:
            return
        if str(getattr(lord, "role", "")) != str(LordRole.KING):
            await open_unique_ephemeral(interaction, content=strings["objectif_king_only"])
            return
        # le staging démarre depuis les objectifs LIVE (éditer ≠ repartir de zéro)
        goals = dict(getattr(kingdom, "council_objectives", None) or {})
        staged = _staged(str(getattr(interaction.user, "id", "")))
        for kind in _OBJECTIF_KINDS:
            if not staged.get(kind) and not staged.get(f"{kind}_label"):
                staged[kind] = str(goals.get(kind, "") or "")
                staged[f"{kind}_label"] = str(goals.get(f"{kind}_label", "") or "")
        await open_unique_ephemeral(
            interaction, view=await _objectif_picker_view(interaction, strings, kingdom)
        )


async def _objectif_options(
    strings: dict[str, str], stack: Any, kingdom: Any, kind: str, page: int
) -> list[discord.SelectOption]:
    """One page of options (max 25) + the none option on page one."""
    out: list[discord.SelectOption] = []
    if kind == "target_kingdom":
        try:
            items = [
                item
                for item in await stack.kingdoms.kingdoms()
                if str(getattr(item, "id", "")) != str(getattr(kingdom, "id", ""))
                and not getattr(item, "is_gaia", False)
            ]
        except Exception:  # noqa: BLE001
            items = []
        out = [
            discord.SelectOption(
                label=str(getattr(item, "name", "?"))[:100], value=str(getattr(item, "id", ""))
            )
            for item in items
        ]
    elif kind == "target_territory":
        entries = list(getattr(getattr(stack, "config", None), "maps", ()) or [])
        out = [
            discord.SelectOption(
                label=str(getattr(entry, "display_name", "") or getattr(entry, "key", "?"))[:100],
                value=str(getattr(entry, "key", "")),
            )
            for entry in entries[page * 25 : page * 25 + 25]
        ]
    else:  # target_alliance
        entries = list(getattr(getattr(stack, "config", None), "civilizations", ()) or ())
        out = [
            discord.SelectOption(
                label=str(getattr(entry, "display_name", "") or getattr(entry, "key", "?"))[:100],
                value=str(getattr(entry, "key", "")),
            )
            for entry in entries[page * 25 : page * 25 + 25]
        ]
    if page == 0:
        out.append(discord.SelectOption(label=strings["objectif_none_label"], value=""))
    return out[:25]


class LieuxObjectifSelect(
    discord.ui.DynamicItem[discord.ui.Select[Any]],
    template=rf"{_NS}:objectif:pick:(?P<kind>[a-z_]+):(?P<page>[0-9]+)",
):
    """One staged select of the picker — a choice becomes a goal."""

    def __init__(
        self, kind: str, page: int, placeholder: str, options: list[discord.SelectOption]
    ) -> None:
        super().__init__(
            discord.ui.Select(
                custom_id=f"{_NS}:objectif:pick:{kind}:{page}",
                options=options[:25],
                placeholder=placeholder[:100],
                min_values=1,
                max_values=1,
            )
        )
        self.kind = kind
        self.page = page

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        strings = lieux_strings(_locale_of(interaction))
        stack = wiring()
        lord, kingdom, _s = await _lord_kingdom_of(interaction, strings)
        kind = str(match["kind"])
        page = int(match["page"])
        options = await _objectif_options(strings, stack, kingdom, kind, page) if kingdom else []
        keys = {
            "target_kingdom": "objectif_select_kingdom",
            "target_territory": "objectif_select_map",
            "target_alliance": "objectif_select_alliance",
        }
        return cls(kind, page, strings[keys.get(kind, "objectif_select_kingdom")], options)

    async def callback(self, interaction: discord.Interaction) -> None:
        strings = lieux_strings(_locale_of(interaction))
        lord, kingdom, stack = await _lord_kingdom_of(interaction, strings)
        if kingdom is None:
            return
        value = str(self.item.values[0] if self.item.values else "")
        label = ""
        if value:
            if self.kind == "target_kingdom":
                try:
                    match = next(
                        item
                        for item in await stack.kingdoms.kingdoms()
                        if str(getattr(item, "id", "")) == value
                    )
                    label = str(getattr(match, "name", value))
                except Exception:  # noqa: BLE001
                    label = value
            else:
                catalog = (
                    getattr(getattr(stack, "config", None), "maps", ())
                    if self.kind == "target_territory"
                    else getattr(getattr(stack, "config", None), "civilizations", ())
                )
                for entry in catalog or ():
                    if str(getattr(entry, "key", "")) == value:
                        label = str(getattr(entry, "display_name", "") or value)
                        break
                label = label or value
        staged = _staged(str(getattr(interaction.user, "id", "")))
        staged[self.kind] = value
        staged[f"{self.kind}_label"] = label
        await open_unique_ephemeral(
            interaction, view=await _objectif_picker_view(interaction, strings, kingdom)
        )


class LieuxObjectifFlip(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:objectif:flip:(?P<kind>[a-z_]+):(?P<page>[0-9]+):(?P<dir>back|next)",
):
    """◀️ ▶️ — flip one catalog's pages (maps/civilizations > 25)."""

    def __init__(self, label: str, kind: str, page: int, direction: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=str(label)[:80],
                custom_id=f"{_NS}:objectif:flip:{kind}:{page}:{direction}",
                style=discord.ButtonStyle.secondary,
            )
        )
        self.kind = kind
        self.page = page
        self.direction = direction

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        strings = lieux_strings(_locale_of(interaction))
        direction = str(match["dir"])
        label = strings["objectif_flip_prev"] if direction == "back" else strings["objectif_flip_next"]
        return cls(label, str(match["kind"]), int(match["page"]), direction)

    async def callback(self, interaction: discord.Interaction) -> None:
        strings = lieux_strings(_locale_of(interaction))
        lord, kingdom, stack = await _lord_kingdom_of(interaction, strings)
        if kingdom is None:
            return
        _OBJECTIF_PAGES[self.kind] = max(0, self.page)
        await open_unique_ephemeral(
            interaction, view=await _objectif_picker_view(interaction, strings, kingdom)
        )


class LieuxObjectifValidateButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]], template=rf"{_NS}:objectif:validate"
):
    """✅ Valider — save the staged goals to the engine, refresh the pin."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=str(label)[:80],
                custom_id=f"{_NS}:objectif:validate",
                style=discord.ButtonStyle.success,
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        return cls(lieux_strings(_locale_of(interaction))["objectif_validate_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        import time as _time

        from .realm_content import refresh_objectifs_pin_safe

        await interaction.response.defer(ephemeral=True)
        strings = lieux_strings(_locale_of(interaction))
        lord, kingdom, stack = await _lord_kingdom_of(interaction, strings)
        if kingdom is None or stack is None:
            return
        staged = _staged(str(getattr(interaction.user, "id", "")))
        objectives = dict(getattr(kingdom, "council_objectives", None) or {})
        for kind in _OBJECTIF_KINDS:
            objectives[kind] = str(staged.get(kind, "") or "")
            objectives[f"{kind}_label"] = str(staged.get(f"{kind}_label", "") or "")
        objectives["updated_at"] = int(_time.time())
        try:
            kingdom.council_objectives = objectives
            await stack.kingdoms.save_kingdom(kingdom)
        except Exception:  # noqa: BLE001
            logger.warning("kingdom lieux: objectives save failed", exc_info=True)
            await open_unique_ephemeral(interaction, content=strings["objectif_save_failed"])
            return
        guild = getattr(interaction, "guild", None)
        if guild is not None:
            realm = await _shell_of(stack, str(getattr(interaction.user, "id", "")))
            if realm is not None:
                await refresh_objectifs_pin_safe(guild, kingdom, _locale_of(interaction), realm)
        await open_unique_ephemeral(interaction, content=strings["objectif_done_note"])


def _catalog_len(stack: Any, kind: str) -> int:
    catalog = (
        getattr(getattr(stack, "config", None), "maps", ())
        if kind == "target_territory"
        else getattr(getattr(stack, "config", None), "civilizations", ())
    )
    try:
        return len(list(catalog or ()))
    except Exception:  # noqa: BLE001
        return 0


async def _objectif_picker_view(
    interaction: discord.Interaction, strings: dict[str, str], kingdom: Any
) -> discord.ui.LayoutView:
    """The picker sheet — 3 selects, flip rows for the paginated ones."""
    stack = wiring()
    staged = _staged(str(getattr(interaction.user, "id", "")))
    rows: list[discord.ui.Item[discord.ui.LayoutView]] = []
    kinds = [
        ("target_kingdom", "objectif_select_kingdom", 0),
        ("target_territory", "objectif_select_map", _OBJECTIF_PAGES["target_territory"]),
        ("target_alliance", "objectif_select_alliance", _OBJECTIF_PAGES["target_alliance"]),
    ]
    for kind, key, page in kinds:
        options = await _objectif_options(strings, stack, kingdom, kind, page)
        select = LieuxObjectifSelect(kind, page, strings[key], options)
        rows.append(discord.ui.ActionRow(select.item))
        if kind != "target_kingdom":
            total = max(1, (_catalog_len(stack, kind) + 24) // 25)
            row: Any = discord.ui.ActionRow()
            if page > 0:
                row.add_item(
                    LieuxObjectifFlip(strings["objectif_flip_prev"], kind, page - 1, "back").item
                )
            if page + 1 < total:
                row.add_item(
                    LieuxObjectifFlip(strings["objectif_flip_next"], kind, page + 1, "next").item
                )
            rows.append(row)
    rows.append(discord.ui.ActionRow(LieuxObjectifValidateButton(strings["objectif_validate_button"]).item))
    return surface(
        OBJECTIF_SURFACE,
        discord.ui.Container(
            discord.ui.TextDisplay(
                f"## {strings['objectif_picker_title'].format(str(getattr(kingdom, 'name', '')))}"
            ),
            discord.ui.Separator(),
            *rows,
            discord.ui.TextDisplay(strings["objectif_edit_hint"]),
            accent_colour=GOLD,
        ),
    )


# ---------------------------------------------------------------------------
# 🧱 Remparts — the live state face (IA, patrouille, gardes)
# ---------------------------------------------------------------------------


def _remparts_window(
    strings: dict[str, str], kingdom: Any, state: dict[str, Any]
) -> tuple[discord.ui.LayoutView, list[discord.File]]:
    import time as _time

    purchases = dict(state.get("purchases") or {})
    level, name = _ai_display(strings, state, kingdom)
    now_ts = int(_time.time())
    lines = [strings["remparts_ai_level"].format(level, name), ""]
    lines.append(strings["remparts_patrouille_title"])
    for slot_no in (1, 2):
        slot_key = f"patrouille_slot_{slot_no}"
        unlock_key = f"patrouille_unlock_{slot_no}"
        if slot_key in purchases:
            start = int(purchases[slot_key])
            line = strings["remparts_state_active"].format(slot_no, start, start + 2)
        elif unlock_key in purchases:
            line = strings["remparts_state_unplaced"].format(slot_no)
        else:
            line = strings["remparts_state_missing"].format(slot_no)
        lines.append(line)
    lines.append("")
    lines.append(strings["remparts_garde_title"])
    shielded = []
    for territory in state.get("territories") or []:
        until_dt = getattr(territory, "protected_until", None)
        if until_dt is None:
            continue
        try:
            until_ts = int(until_dt.timestamp())
        except Exception:
            continue
        if until_ts > now_ts:
            shielded.append((str(getattr(territory, "map_key", "")), until_ts))
    if shielded:
        for map_key, until_ts in shielded:
            lines.append(strings["remparts_guard_line"].format(map_key, fmt_paris(until_ts)))
    else:
        lines.append(strings["remparts_garde_owned_none"])
    reserve = int(purchases.get("garde_royale_stock", 0) or 0)
    if reserve > 0:
        lines.append(strings["remparts_guard_stock"].format(reserve))
    # vague2-actions-v1 (Drasah 21/11) : rangée 2 — Jeu d'armes,
    # Patrouille, Garde royale (verts si détenus, gris sinon, jamais cachés)
    rows = [[_sortir_item(strings)], _remparts_use_row(strings, state)]
    view = _lieu_window(
        strings,
        REMPARTS_SURFACE,
        TEAL,
        strings["patrol_title"].format(str(getattr(kingdom, "name", ""))),
        "\n".join(lines),
        "attachment://rempart.png",
        rows,
    )
    return view, _lieu_files("Rempart.png", "rempart.png")


# ---------------------------------------------------------------------------
# 🏛️ Chambre des comptes — the ledger sheet (the market's chamber_text seam)
# ---------------------------------------------------------------------------


async def _comptes_window(
    strings: dict[str, str], kingdom: Any, state: dict[str, Any]
) -> tuple[discord.ui.LayoutView, list[discord.File]]:
    from .market import chamber_text
    from .strings import strings as mod_strings

    stack = wiring()
    mod_catalog = mod_strings(_locale_of_catalog(strings))
    body = await chamber_text(stack, kingdom, mod_catalog)
    # vague2-actions-v1 (Drasah 21/11) : 📜 Historique achats · ⚔️
    # Historique actions (portés de la référence, comptes-rows-v1)
    rows = [[
        LieuxHistButton("achats", strings).item,
        LieuxHistButton("actions", strings).item,
        _sortir_item(strings),
    ]]
    view = _lieu_window(
        strings,
        COMPTES_SURFACE,
        GOLD,
        strings["comptes_title"].format(str(getattr(kingdom, "name", ""))),
        body,
        "attachment://chambre_des_comptes.png",
        rows,
    )
    return view, _lieu_files("chambre des comptes.png", "chambre_des_comptes.png")


def _locale_of_catalog(strings: dict[str, str]) -> str:
    return "fr" if strings is LIEUX_STRINGS["fr"] else "en"


# ---------------------------------------------------------------------------
# ⛪ Paroisse — the palier sheet + the palier-tiered illustration
# ---------------------------------------------------------------------------


async def _paroisse_window(
    strings: dict[str, str], kingdom: Any, state: dict[str, Any]
) -> tuple[discord.ui.LayoutView, list[discord.File]]:
    stack = wiring()
    tier = int(getattr(kingdom, "parish_tier", 1) or 1)
    tiers: list[Any] = []
    name, offering = "", 0
    try:
        tiers = list(getattr(stack.config.parish, "tiers", ()) or [])
        if 0 < tier <= len(tiers):
            name = str(getattr(tiers[tier - 1], "display_name", ""))
            offering = int(getattr(tiers[tier - 1], "offering", 0) or 0)
    except Exception:
        tiers = []
    body = "\n".join([
        strings["paroisse_tier_line"].format(name or "?", tier, max(len(tiers), 3), offering),
        strings["paroisse_stats_line"].format(
            int(getattr(kingdom, "marriage_points", 0) or 0),
            int(getattr(kingdom, "arranged_marriage_stock", 0) or 0),
            int(state.get("wallet", 0) or 0),
        ),
    ])
    # vague2-actions-v1 (Drasah 21/11) : 💍 Se marier (la DynamicItem de
    # marry.py, harmonisation gratuite) + ⛪ Améliorer + Sortir
    from .marry import MarryButton

    next_name, next_cost, at_top = "", 0, True
    if 0 <= tier - 1 < len(tiers):
        at_top = tier >= len(tiers)
        if not at_top:
            next_name = str(getattr(tiers[tier], "display_name", ""))
            next_cost = int(getattr(tiers[tier], "cost", 0) or 0)
    upgrade = (
        discord.ui.Button(
            label=str(strings["paroisse_upgrade_max"])[:80],
            custom_id=f"{_NS}:paroisse:upgrade",
            style=discord.ButtonStyle.secondary,
            disabled=True,
        )
        if at_top
        else LieuxParoisseUpgradeButton(
            strings["paroisse_upgrade_button"].format(next_name)
        ).item
    )
    rows = [[
        MarryButton(strings["paroisse_marry_button"]).item,
        upgrade,
        _sortir_item(strings),
    ]]
    view = _lieu_window(
        strings,
        PAROISSE_SURFACE,
        discord.Colour.blurple(),
        strings["paroisse_title"].format(str(getattr(kingdom, "name", ""))),
        body,
        "attachment://paroisse.png",
        rows,
    )
    tier_file = min(3, max(1, tier))
    return view, _lieu_files(f"paroisse{tier_file}.png", "paroisse.png")


# ---------------------------------------------------------------------------
# 🏗️ Volière — the birds' sommaire (model-side cooldowns)
# ---------------------------------------------------------------------------


def _voliere_window(
    strings: dict[str, str], kingdom: Any
) -> tuple[discord.ui.LayoutView, list[discord.File]]:
    import time as _time

    now_ts = int(_time.time())
    lines = [
        strings["voliere_title"].format(kingdom=str(getattr(kingdom, "name", ""))).lstrip("# "),
        strings["voliere_line"],
        "",
    ]
    cooldowns = {
        str(k): int(v) for k, v in (dict(getattr(kingdom, "voliere_cooldowns", {}) or {})).items()
    }
    for bird in [str(b) for b in (list(getattr(kingdom, "voliere_slots", []) or []))]:
        ready_at = cooldowns.get(bird, 0)
        if ready_at > now_ts:
            lines.append(strings["bird_flying"].format(bird=_bird_label(strings, bird), ts=ready_at))
        else:
            lines.append(strings["bird_ready"].format(bird=_bird_label(strings, bird)))
    rows = [[_sortir_item(strings)]]
    view = _lieu_window(
        strings,
        VOLIERE_SURFACE,
        GREEN,
        strings["voliere_title"].format(kingdom=str(getattr(kingdom, "name", ""))).lstrip("# "),
        "\n".join(lines),
        "attachment://voliere.png",
        rows,
    )
    return view, _lieu_files("voliere.png", "voliere.png")


# ---------------------------------------------------------------------------
# vague2-actions-v1 (Drasah 21/11) — les rangées d'action + leurs
# restart-proof DynamicItems. Règle des cartes : VERT si en réserve,
# GRIS + disabled sinon, jamais caché (pattern _remparts_rows référence).
# ---------------------------------------------------------------------------


def _stock_button(
    custom_id: str, label: str, held: bool, strings: dict[str, str]
) -> discord.ui.Button:
    """One wire button — green when held, gray+disabled otherwise."""
    return discord.ui.Button(
        label=str(label)[:80],
        custom_id=custom_id[:100],
        style=discord.ButtonStyle.success if held else discord.ButtonStyle.secondary,
        disabled=not held,
    )


def _remparts_use_row(strings: dict[str, str], state: dict[str, Any]) -> list[Any]:
    """Rangée 2 des Remparts : ⚔️ Jeu d'armes · 🚨 Patrouille · 💂 Garde."""
    purchases = dict(state.get("purchases") or {})
    patrouille_held = any(
        f"patrouille_slot_{slot_no}" in purchases or f"patrouille_unlock_{slot_no}" in purchases
        for slot_no in (1, 2)
    )
    return [
        _stock_button(
            f"{_NS}:remparts:use:jeu_d_armes",
            strings["remparts_use_jeu"],
            int(purchases.get("jeu_d_armes_stock", 0) or 0) > 0,
            strings,
        ),
        _stock_button(
            f"{_NS}:remparts:use:patrouille",
            strings["remparts_use_patrouille"],
            patrouille_held,
            strings,
        ),
        _stock_button(
            f"{_NS}:remparts:use:garde_royale",
            strings["remparts_use_garde"],
            int(purchases.get("garde_royale_stock", 0) or 0) > 0,
            strings,
        ),
    ]


def _conseil_cards_row(strings: dict[str, str], state: dict[str, Any], kingdom: Any) -> list[Any]:
    """Rangée 2 du Conseil : 🧭 Exploration · 🪤 Traquenard."""
    purchases = dict(state.get("purchases") or {})
    return [
        _stock_button(
            f"{_NS}:exploration",
            strings["conseil_card_exploration"],
            int(purchases.get("explorateur_stock", 0) or 0) > 0,
            strings,
        ),
        _stock_button(
            f"{_NS}:traquenard",
            strings["conseil_card_traquenard"],
            int(purchases.get("traquenard", 0) or 0) > 0,
            strings,
        ),
    ]


class LieuxRempartsUseButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:remparts:use:(?P<card>[a-z_]+)",
):
    """Une carte d'action des Remparts — délègue au wizard du Marché
    (market._use_wizard gère EXACTEMENT jeu d'armes/patrouille/garde :
    choix IA, créneau patrouille, territoire protégé — zéro doublon)."""

    def __init__(self, card: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=card,
                custom_id=f"{_NS}:remparts:use:{card}",
                style=discord.ButtonStyle.success,
            )
        )
        self.card = str(card)

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        return cls(str(match["card"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        from .common import strings_for
        from .market import _use_wizard

        strings = lieux_strings(_locale_of(interaction))
        lord, kingdom, stack = await _lord_kingdom_of(interaction, strings)
        if lord is None or kingdom is None or stack is None:
            return
        await _use_wizard(interaction, stack, strings_for(interaction), self.card, kingdom)


class LieuxExplorationButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]], template=rf"{_NS}:exploration"
):
    """🧭 Exploration — le wizard Explorateur du Marché (choix du
    seigneur, verrou 48h), jamais dupliqué ici."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=str(label)[:80], custom_id=f"{_NS}:exploration", style=discord.ButtonStyle.success
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        return cls(lieux_strings(_locale_of(interaction))["conseil_card_exploration"])

    async def callback(self, interaction: discord.Interaction) -> None:
        from .common import strings_for
        from .market import _use_wizard

        strings = lieux_strings(_locale_of(interaction))
        lord, kingdom, stack = await _lord_kingdom_of(interaction, strings)
        if lord is None or kingdom is None or stack is None:
            return
        await _use_wizard(interaction, stack, strings_for(interaction), "explorateur", kingdom)


class LieuxTraquenardButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]], template=rf"{_NS}:traquenard"
):
    """🪤 Traquenard — ouvre la fenêtre éphémère de choix de cible."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=str(label)[:80], custom_id=f"{_NS}:traquenard", style=discord.ButtonStyle.success
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        return cls(lieux_strings(_locale_of(interaction))["conseil_card_traquenard"])

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        strings = lieux_strings(_locale_of(interaction))
        lord, kingdom, stack = await _lord_kingdom_of(interaction, strings)
        if lord is None or kingdom is None or stack is None:
            return
        options = await _traquenard_options(stack, kingdom)
        if not options:
            await open_unique_ephemeral(interaction, content=strings["traquenard_select"])
            return
        view = surface(
            TRAQUENARD_SURFACE,
            discord.ui.Container(
                discord.ui.TextDisplay(f"## 🪤 {strings['traquenard_select']}"),
                discord.ui.Separator(),
                discord.ui.ActionRow(LieuxTraquenardSelect(options).item),
                accent_colour=GOLD,
            ),
        )
        await open_unique_ephemeral(interaction, view=view)


async def _traquenard_options(stack: Any, kingdom: Any) -> list[discord.SelectOption]:
    """Les royaumes cibles — jamais soi-même, jamais Gaïa."""
    try:
        items = [
            item
            for item in await stack.kingdoms.kingdoms()
            if str(getattr(item, "id", "")) != str(getattr(kingdom, "id", ""))
            and not getattr(item, "is_gaia", False)
        ]
    except Exception:  # noqa: BLE001
        return []
    return [
        discord.SelectOption(
            label=str(getattr(item, "name", getattr(item, "id", "?")))[:100],
            value=str(getattr(item, "id", "")),
        )
        for item in items
    ][:25]


class LieuxTraquenardSelect(
    discord.ui.DynamicItem[discord.ui.Select[Any]], template=rf"{_NS}:traquenard:pick"
):
    """Le select du Traquenard — consomme la carte et arme la fenêtre."""

    def __init__(self, options: list[discord.SelectOption]) -> None:
        super().__init__(
            discord.ui.Select(
                custom_id=f"{_NS}:traquenard:pick",
                options=options[:25],
                placeholder="🎯",
                min_values=1,
                max_values=1,
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        strings = lieux_strings(_locale_of(interaction))
        lord, kingdom, stack = await _lord_kingdom_of(interaction, strings)
        options = await _traquenard_options(stack, kingdom) if kingdom else []
        return cls(options)

    async def callback(self, interaction: discord.Interaction) -> None:
        strings = lieux_strings(_locale_of(interaction))
        lord, kingdom, stack = await _lord_kingdom_of(interaction, strings)
        if lord is None or kingdom is None or stack is None:
            return
        chosen = str(self.item.values[0] if self.item.values else "")
        if not chosen:
            return
        await interaction.response.defer(ephemeral=True)
        try:
            result = await stack.attacks.activate_traquenard(str(getattr(interaction.user, "id", "")), chosen)
        except Exception as exc:  # noqa: BLE001 — every engine refusal is a note
            logger.info("kingdom lieux: traquenard refused: %s", exc)
            await open_unique_ephemeral(
                interaction, content=strings["action_error_note"].format(str(exc)[:150])
            )
            return
        # le nom de la cible, ressolu au moment de la note
        target_name = chosen
        try:
            for item in await stack.kingdoms.kingdoms():
                if str(getattr(item, "id", "")) == chosen:
                    target_name = str(getattr(item, "name", "") or chosen)
                    break
        except Exception:  # noqa: BLE001
            pass
        until_ts = 0
        try:
            until_ts = int(getattr(result, "until", 0) or 0)
        except Exception:  # noqa: BLE001
            pass
        affected = len(getattr(result, "affected", ()) or ())
        await open_unique_ephemeral(
            interaction, content=strings["traquenard_done"].format(target_name, until_ts, affected)
        )


class LieuxParoisseUpgradeButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]], template=rf"{_NS}:paroisse:upgrade"
):
    """⛪ Améliorer — ouvre la carte de confirmation (achat direct)."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=str(label)[:80],
                custom_id=f"{_NS}:paroisse:upgrade",
                style=discord.ButtonStyle.success,
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        return cls(lieux_strings(_locale_of(interaction))["paroisse_upgrade_button"].format(""))

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        strings = lieux_strings(_locale_of(interaction))
        lord, kingdom, stack = await _lord_kingdom_of(interaction, strings)
        if lord is None or kingdom is None or stack is None:
            return
        next_name, next_cost, at_top = "", 0, True
        try:
            tiers = list(getattr(stack.config.parish, "tiers", ()) or ())
            tier = int(getattr(kingdom, "parish_tier", 1) or 1)
            at_top = tier >= len(tiers)
            if not at_top:
                next_name = str(getattr(tiers[tier], "display_name", ""))
                next_cost = int(getattr(tiers[tier], "cost", 0) or 0)
        except Exception:  # noqa: BLE001
            pass
        if at_top:
            await open_unique_ephemeral(interaction, content=strings["paroisse_upgrade_max"])
            return
        view = surface(
            PAROISSE_UPGRADE_SURFACE,
            discord.ui.Container(
                discord.ui.TextDisplay(
                    f"## ⛪ {strings['paroisse_upgrade_confirm'].format(next_name, next_cost)}"
                ),
                discord.ui.Separator(),
                discord.ui.ActionRow(
                    LieuxParoisseUpgradeOkButton(strings["paroisse_upgrade_ok"]).item,
                    LieuxParoisseUpgradeCancelButton(strings["paroisse_upgrade_cancel"]).item,
                ),
                accent_colour=discord.Colour.blurple(),
            ),
        )
        await open_unique_ephemeral(interaction, view=view)


class LieuxParoisseUpgradeOkButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]], template=rf"{_NS}:paroisse:upgrade:ok"
):
    """✅ Améliorer — le seam moteur upgrade_parish (service.py) paie et monte."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=str(label)[:80],
                custom_id=f"{_NS}:paroisse:upgrade:ok",
                style=discord.ButtonStyle.success,
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        return cls(lieux_strings(_locale_of(interaction))["paroisse_upgrade_ok"])

    async def callback(self, interaction: discord.Interaction) -> None:
        strings = lieux_strings(_locale_of(interaction))
        lord, kingdom, stack = await _lord_kingdom_of(interaction, strings)
        if lord is None or kingdom is None or stack is None:
            await interaction.response.defer(ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            upgraded = await stack.kingdoms.upgrade_parish(str(getattr(kingdom, "id", "")))
        except Exception as exc:  # noqa: BLE001
            logger.info("kingdom lieux: parish upgrade refused: %s", exc)
            await open_unique_ephemeral(
                interaction, content=strings["action_error_note"].format(str(exc)[:150])
            )
            return
        name = ""
        try:
            tiers = list(getattr(stack.config.parish, "tiers", ()) or [])
            tier = int(getattr(upgraded, "parish_tier", 1) or 1)
            if 0 < tier <= len(tiers):
                name = str(getattr(tiers[tier - 1], "display_name", "") or "")
        except Exception:  # noqa: BLE001
            pass
        await open_unique_ephemeral(
            interaction, content=strings["paroisse_upgrade_done"].format(name or "?")
        )


class LieuxParoisseUpgradeCancelButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]], template=rf"{_NS}:paroisse:upgrade:cancel"
):
    """❌ Annuler — rouvre la fiche Paroisse (fenêtre unique)."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=str(label)[:80],
                custom_id=f"{_NS}:paroisse:upgrade:cancel",
                style=discord.ButtonStyle.secondary,
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        return cls(lieux_strings(_locale_of(interaction))["paroisse_upgrade_cancel"])

    async def callback(self, interaction: discord.Interaction) -> None:
        await _open_lieu(interaction, "paroisse")


class LieuxHistButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:hist:(?P<kind>achats|actions)",
):
    """📜/⚔️ Historique — les fenêtres de lecture du registre (les 50
    dernières entrées, dates Paris), portées de la référence."""

    def __init__(self, kind: str, strings: dict[str, str]) -> None:
        key = "hist_achats_button" if kind == "achats" else "hist_actions_button"
        super().__init__(
            discord.ui.Button(
                label=str(strings[key])[:80],
                custom_id=f"{_NS}:hist:{kind}",
                style=discord.ButtonStyle.success,
            )
        )
        self.kind = str(kind)

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        return cls(str(match["kind"]), lieux_strings(_locale_of(interaction)))

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        strings = lieux_strings(_locale_of(interaction))
        lord, kingdom, stack = await _lord_kingdom_of(interaction, strings)
        if lord is None or kingdom is None:
            return
        lines: list[str] = []
        if self.kind == "achats":
            title = str(strings["hist_achats_title"])
            registry = list(getattr(kingdom, "market_registry", None) or [])[-50:]
            if not registry:
                lines = [str(strings["hist_achats_empty"])]
            else:
                for entry in sorted(
                    registry, key=lambda e: int(e.get("at", 0) or 0), reverse=True
                ):
                    item = str(entry.get("item", ""))
                    lines.append(
                        str(strings["hist_purchase_line"]).format(
                            _HIST_EMOJI.get(item, "•"),
                            _hist_label(strings, item),
                            str(entry.get("detail", "")),
                            int(entry.get("cost", 0) or 0),
                            fmt_paris(int(entry.get("at", 0) or 0)),
                        )
                    )
        else:
            title = str(strings["hist_actions_title"])
            actions = list(getattr(kingdom, "market_actions", None) or [])[-50:]
            if not actions:
                lines = [str(strings["hist_actions_empty"])]
            else:
                for entry in sorted(
                    actions, key=lambda e: int(e.get("at", 0) or 0), reverse=True
                ):
                    item = str(entry.get("item", ""))
                    lines.append(
                        str(strings["hist_action_line"]).format(
                            _HIST_EMOJI.get(item, "•"),
                            _hist_label(strings, item),
                            str(entry.get("detail", "")),
                            fmt_paris(int(entry.get("at", 0) or 0)),
                        )
                    )
        view = surface(
            HIST_SURFACE,
            discord.ui.Container(
                discord.ui.TextDisplay(f"# {title}"),
                discord.ui.Separator(),
                discord.ui.TextDisplay("\n".join(lines)),
                discord.ui.ActionRow(_sortir_item(strings)),
                accent_colour=GOLD,
            ),
        )
        await open_unique_ephemeral(interaction, view=view)
