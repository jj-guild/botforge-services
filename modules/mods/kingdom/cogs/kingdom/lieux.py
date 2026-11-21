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

GOLD = discord.Colour(0xE6B800)
TEAL = discord.Colour.dark_teal()
GREEN = discord.Colour.green()

ENTREE_SURFACE = "panel:mod:kingdom:lieux:entree"
CONSEIL_SURFACE = "panel:mod:kingdom:lieux:conseil"
REMPARTS_SURFACE = "panel:mod:kingdom:lieux:remparts"
COMPTES_SURFACE = "panel:mod:kingdom:lieux:comptes"
PAROISSE_SURFACE = "panel:mod:kingdom:lieux:paroisse"
VOLIERE_SURFACE = "panel:mod:kingdom:lieux:voliere"

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
            view, files = await _conseil_window(interaction, strings, kingdom, state)
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
# ⚔️ Salle du conseil — the orientation sheet (tranche 1 : the intro, the
# stats line, the Seigneurie door ; objectifs/classement/cartes = tranche 2)
# ---------------------------------------------------------------------------


async def _conseil_window(
    interaction: discord.Interaction,
    strings: dict[str, str],
    kingdom: Any,
    state: dict[str, Any],
) -> tuple[discord.ui.LayoutView, list[discord.File]]:
    body = "\n".join([strings["conseil_intro_l1"], "", strings["conseil_stats"].format(
        int(state.get("wallet", 0) or 0),
        len(state.get("territories") or []),
        len(getattr(kingdom, "civilizations", []) or []),
    )])
    rows = [[
        LieuxSeigneurieButton(strings['conseil_seigneurie_button']).item,
        _sortir_item(strings),
    ]]
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
    rows = [[_sortir_item(strings)]]
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
    rows = [[_sortir_item(strings)]]
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
    rows = [[_sortir_item(strings)]]
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
