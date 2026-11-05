"""Kingdoms mod — lieux-et-conseil-v1 (Drasah 01/11): the realm hub.

The Le-Royaume refonte: the pinned sheet becomes a CASTLE hub — the
stats move into the ⚔️ Salle du conseil, every place opens as an
ephemeral view with its illustration, and nothing else changes for the
players until the gate opens.

canary-gate-v1: the whole refonte renders ONLY for the kingdom ids
listed below (THE DECLARATION WINS — never a live-state derivation,
leçon divider-gating-v2). refonte-generale-v1 (Drasah 03/11): GO —
the beta validated on Nilrem, the gate tuples are now EMPTY and an
empty gate is an ALL-PASS: every kingdom renders the new hub. Re-list
an id to re-gate it (never a live-state derivation).

fenetre-unique-v2: every lieu view rides the shared single-window
registry — one live ephemeral per player, whatever opens it.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import discord

logger = logging.getLogger("kingdoms.kingdom_lieux")

# canary-gate-v1 (Drasah 01/11): the ids allowed to render the new hub.
# refonte-generale-v1 (Drasah 03/11): GO — both tuples emptied, the
# gate is now an ALL-PASS (see ``is_canary_realm``); re-list an id to
# re-gate a single kingdom.
CANARY_REALM_KINGDOM_IDS: tuple[str, ...] = ()
# canary-porte-nom-v1 (Drasah 02/11): a reset purges the kingdom docs
# and the recreated realm gets a fresh ``k-N`` id — the reserved test
# NAME joined the gate so a recreated realm kept the refonte.
# refonte-generale-v1 (Drasah 03/11): emptied with the ids above.
CANARY_REALM_KINGDOM_NAMES: tuple[str, ...] = ()

_LIEUX_ASSETS = Path(__file__).resolve().parent / "assets" / "lieux"

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "hub_flavor": (
            "The castle gates open — every place of the realm lives "
            "behind its door. The state of the kingdom sits in the "
            "Council room."
        ),
        "entree_button": "🏰 Entrance",
        "entree_title": "Where would you like to go?",
        "conseil_button": "⚔️ Council room",
        "remparts_button": "🧱 Ramparts",
        "comptes_button": "🏛️ Chamber of accounts",
        "paroisse_button": "⛪ Parish",
        "voliere_button": "🏗️ Aviary",
        "not_lord": "Only the lords of this kingdom may enter its places.",
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
        "conseil_stats": (
            "**Treasury** : {0} ⚙️ · **Territories** : {1} 🗺️ ·"
            " **Alliances** : {2} 🤝"
        ),
        "objectif_detail_suffix": " — {0}",
        "objectif_map_unknown_owner": "Unknown destination",
        "objectif_alliance_mercenary_suffix": " · {0}",
        "objectif_alliance_mercenary": (
            "offered as a mercenary contract at the tavern"
        ),
        "classement_button": "🏆 Ranking",
        "classement_title": "🏆 Ranking of the season",
        "classement_line": "{0} {1}. **{2}** — {3} 🗺️ · {4} 🤝",
        "classement_empty": "No kingdom to rank yet.",
        "objectif_button": "🎯 Objectives",
        "objectif_king_only": "🎯 Reserved to the King of the realm.",
        "objectif_picker_title": "🎯 Kingdom objectives — {0}",
        "objectif_select_kingdom": "⚔️ Kingdom to strike first",
        "objectif_select_map": "🗺️ Territory you seek",
        "objectif_select_alliance": "🤝 Alliance you covet",
        "objectif_none_label": "🚫 None — leave undefined",
        "objectif_edit_button": "✏️ Edit",
        "objectif_validate_button": "✅ Apply",
        "objectif_quit_button": "🚪 Quit",
        "objectif_change_button": "✏️ {0}",
        "objectif_undefined": "— undefined",
        "objectif_read_hint": (
            "-# Indicative objectives set by the King — ✏️ Edit to change"
            " them, 🚪 Quit to close."
        ),
        "objectif_edit_hint": (
            "-# Each menu picked becomes your objective — ✅ Apply to save,"
            " 🚪 Quit to close without saving."
        ),
        "objectif_save_failed": "⚠️ Save failed — try again in a moment.",
        "conseil_objectifs_title": "🎯 Objectives",
        "conseil_objectif_kingdom": "⚔️ Kingdom to focus : **{0}**",
        "conseil_objectif_map": "🗺️ Territory sought : **{0}**",
        "conseil_objectif_alliance": "🤝 Alliance wanted : **{0}**",
        "conseil_objectifs_none": (
            "No objective set yet — the King may define them with the"
            " 🎯 Objective button."
        ),
        "conseil_traquenard_title": "**🪤 Traquenard**",
        "conseil_traquenard_line": (
            "You weakened the AI level of the kingdom **{0}** — active"
            " for {1}"
        ),
        "objectif_map_defend_line": "⚔️ Priority : defend **{0}** at all costs /!\\",
        "objectif_alliance_marry_line": "💍 Marriage wished with **{0}**",
        "objectif_pin_title": "🎯 Objectives — {0}",
        "objectif_pin_none": "No objective set for the moment.",
        "objectif_pin_hint": (
            "-# The King changes these from ⚔️ Council room → 🎯 Objective."
        ),
        "objectif_achieved_map": (
            "🎯 Objective reached! The realm now holds **{0}** — the King"
            " may set a new course."
        ),
        "objectif_achieved_alliance": (
            "🎯 Objective reached! **{0}** joins the realm's alliances —"
            " the King may set a new course."
        ),
        "objectif_achieved_hint": (
            "-# The objective was cleared — 🎯 below to define a new one."
        ),
        "objectif_redefine_button": "🎯 Set a new objective",
        "conseil_actions": "Action cards",
        "sortir_button": "🚪 Leave",
        "exploration_button": "🧭 Exploration",
        "exploration_fiche_title": "🧭 Exploration",
        "exploration_effect_title": "Effect",
        "exploration_effect_l1": (
            "Enlist as Captain and sail for 48 hours in search of a new"
            " territory."
        ),
        "exploration_effect_l2": "Once the journey ends, claim an unknown new territory.",
        "exploration_effect_l3": (
            "While at sea you are « locked »: you can neither defend nor"
            " attack."
        ),
        "exploration_effect_l4": (
            "Other lords may join the voyage; each joining lord cuts 4 hours"
            " off the travel (24 hours off at most)."
        ),
        "exploration_prerequis_title": "Prerequisite",
        "exploration_prerequis": (
            "The lord enlisting as Captain must have one defence point"
            " available (the defence point is NOT consumed)."
        ),
        "exploration_capitaine_button": "🧭 Become captain",
        "exploration_annuler_button": "Cancel",
        "exploration_no_defense": (
            "🛡️ Prerequisite not met: you need one AVAILABLE defence"
            " point."
        ),
    },
    "fr": {
        "hub_flavor": (
            "Les portes du château s'ouvrent — chaque lieu du royaume "
            "vit derrière sa porte. L'état du royaume siège en Salle "
            "du conseil."
        ),
        "entree_button": "🏰 Entrée",
        "entree_title": "Où souhaitez-vous vous rendre ?",
        "conseil_button": "⚔️ Salle du conseil",
        "remparts_button": "🧱 Remparts",
        "comptes_button": "🏛️ Chambre des comptes",
        "paroisse_button": "⛪ Paroisse",
        "voliere_button": "🏗️ Volière",
        "not_lord": "Seuls les seigneurs du royaume peuvent entrer dans ses lieux.",
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
        "conseil_stats": (
            "**Trésorerie** : {0} ⚙️ · **Territoires** : {1} 🗺️ ·"
            " **Alliances** : {2} 🤝"
        ),
        "objectif_detail_suffix": " — {0}",
        "objectif_map_unknown_owner": "Destination inconnue",
        "objectif_alliance_mercenary_suffix": " · {0}",
        "objectif_alliance_mercenary": (
            "proposée par contrat de mercenaire à la taverne"
        ),
        "classement_button": "🏆 Classement",
        "classement_title": "🏆 Classement de la saison",
        "classement_line": "{0} {1}. **{2}** — {3} 🗺️ · {4} 🤝",
        "classement_empty": "Aucun royaume à classer pour le moment.",
        "objectif_button": "🎯 Objectifs",
        "objectif_king_only": "🎯 Réservé au Roi du royaume.",
        "objectif_picker_title": "🎯 Objectifs du royaume — {0}",
        "objectif_select_kingdom": "⚔️ Royaume à attaquer en priorité",
        "objectif_select_map": "🗺️ Territoire recherché",
        "objectif_select_alliance": "🤝 Alliance souhaitée",
        "objectif_none_label": "🚫 Aucun — ne pas définir",
        "objectif_edit_button": "✏️ Modifier",
        "objectif_validate_button": "✅ Valider",
        "objectif_quit_button": "🚪 Quitter",
        "objectif_change_button": "✏️ {0}",
        "objectif_undefined": "— non défini",
        "objectif_read_hint": (
            "-# Objectifs indicatifs fixés par le Roi — ✏️ Modifier pour les"
            " changer, 🚪 Quitter pour fermer."
        ),
        "objectif_edit_hint": (
            "-# Chaque menu choisi devient ton objectif — ✅ Valider pour"
            " sauvegarder, 🚪 Quitter pour fermer sans sauvegarder."
        ),
        "objectif_save_failed": "⚠️ Sauvegarde échouée — réessaie dans un instant.",
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
        "objectif_map_defend_line": "⚔️ Priorité : défendre coûte que coûte **{0}** /!\\",
        "objectif_alliance_marry_line": "💍 Mariage souhaité avec **{0}**",
        "objectif_pin_title": "🎯 Objectifs — {0}",
        "objectif_pin_none": "Aucun objectif défini pour le moment.",
        "objectif_pin_hint": (
            "-# Le Roi les modifie depuis ⚔️ Salle du conseil → 🎯 Objectif."
        ),
        "objectif_achieved_map": (
            "🎯 Objectif atteint ! Le royaume possède désormais **{0}** —"
            " le Roi peut fixer un nouveau cap."
        ),
        "objectif_achieved_alliance": (
            "🎯 Objectif atteint ! **{0}** rejoint les alliances du royaume"
            " — le Roi peut fixer un nouveau cap."
        ),
        "objectif_achieved_hint": (
            "-# L'objectif a été effacé — 🎯 ci-dessous pour en définir un"
            " nouveau."
        ),
        "objectif_redefine_button": "🎯 Redéfinir un objectif",
        "conseil_actions": "Cartes d'action",
        "sortir_button": "🚪 Sortir",
        "exploration_button": "🧭 Exploration",
        "exploration_fiche_title": "🧭 Exploration",
        "exploration_effect_title": "Effet",
        "exploration_effect_l1": (
            "Enrôlez-vous en tant que Capitaine et voyagez durant 48 h à la"
            " recherche d'un nouveau territoire."
        ),
        "exploration_effect_l2": "Après le délai, récupérez un nouveau territoire inconnu.",
        "exploration_effect_l3": (
            "Durant ce trajet vous êtes dans l'état « verrouillé » : vous ne"
            " pouvez ni défendre ni attaquer."
        ),
        "exploration_effect_l4": (
            "D'autres seigneurs peuvent participer au voyage ; chaque"
            " seigneur participant réduit le délai du voyage de 4 h"
            " (réduction maximum de 24 h)."
        ),
        "exploration_prerequis_title": "Pré-requis",
        "exploration_prerequis": (
            "Le seigneur s'enrôlant en tant que Capitaine doit avoir un"
            " point de défense disponible (le point de défense n'est pas"
            " consommé)."
        ),
        "exploration_capitaine_button": "🧭 Devenir capitaine",
        "exploration_annuler_button": "Annuler",
        "exploration_no_defense": (
            "🛡️ Pré-requis du point de défense possédé non respecté."
        ),
    },
}


def _strings(locale: str) -> dict[str, str]:
    return STRINGS["fr"] if str(locale).lower().startswith("fr") else STRINGS["en"]


def _locale(interaction: discord.Interaction) -> str:
    return str(interaction.locale) if interaction.locale else "fr"


def _merged_strings(locale: str) -> dict[str, str]:
    """The merged panel strings (labels of the market cards etc.)."""
    from kingdoms.mods.kingdoms.kingdom_persistent import _strings as _merged

    return _merged(locale)


def is_canary_realm(kingdom: Any | None) -> bool:
    """True when the kingdom renders the new hub (the gate decides).

    canary-porte-nom-v1 (Drasah 02/11): the reserved id OR the
    reserved test name (case-insensitive) — a reset-recreated
    « Nilrem » keeps the refonte whatever its generated id."""
    if kingdom is None:
        return False
    if not CANARY_REALM_KINGDOM_IDS and not CANARY_REALM_KINGDOM_NAMES:
        # refonte-generale-v1 (Drasah 03/11): an EMPTY gate is an
        # ALL-PASS — every kingdom renders the new hub.
        return True
    if str(getattr(kingdom, "id", "")) in CANARY_REALM_KINGDOM_IDS:
        return True
    return (
        str(getattr(kingdom, "name", "")).strip().casefold()
        in CANARY_REALM_KINGDOM_NAMES
    )


def _lieu_file(filename_on_disk: str, filename: str) -> discord.File | None:
    """Best-effort illustration of one lieu (deployment-local asset)."""
    try:
        path = _LIEUX_ASSETS / filename_on_disk
        if not path.is_file():
            logger.warning("KINGDOM LIEUX: illustration %s missing", filename_on_disk)
            return None
        return discord.File(path, filename=filename, spoiler=False)
    except Exception:
        logger.warning("KINGDOM LIEUX: illustration %s read failed", filename_on_disk, exc_info=True)
        return None


def _lieu_files(filename_on_disk: str, filename: str) -> list[discord.File]:
    file = _lieu_file(filename_on_disk, filename)
    return [file] if file is not None else []


def hub_file() -> discord.File | None:
    """The castle illustration of the hub (Royaume.png)."""
    return _lieu_file("Royaume.png", "royaume.png")


async def _require_lord_kingdom(
    interaction: discord.Interaction,
    wiring: Any,
    strings: dict[str, str],
) -> tuple[Any, Any] | tuple[None, None]:
    """Resolve the clicker's active lord + kingdom (admin-as-king wins)."""
    from kingdoms.mods.kingdoms.kingdom_persistent import _lord_of

    if wiring.kingdoms_service is None:
        await interaction.response.send_message(strings["no_service"], ephemeral=True)
        return (None, None)
    lord = await _lord_of(
        wiring.kingdoms_service, str(interaction.user.id), wiring.bot_admins
    )
    if lord is None or getattr(lord, "left", False):
        await interaction.response.send_message(strings["not_lord"], ephemeral=True)
        return (None, None)
    kingdoms = await wiring.kingdoms_service.kingdoms()
    kingdom = next(
        (k for k in kingdoms if str(k.id) == str(getattr(lord, "kingdom_id", None))),
        None,
    )
    if kingdom is None:
        await interaction.response.send_message(strings["not_lord"], ephemeral=True)
        return (None, None)
    return (lord, kingdom)


def _lieu_view_class(kind: str):
    """Build the DynamicItem class of one hub door."""

    class _KingdomLieuButton(
        discord.ui.DynamicItem[discord.ui.Button[Any]],
        template=rf"kingdoms:lieux:{kind}",
    ):
        """The restart-proof hub door of one lieu (canary render only)."""

        def __init__(self, label: str) -> None:
            super().__init__(
                discord.ui.Button(
                    label=label[:80],
                    custom_id=f"kingdoms:lieux:{kind}",
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
        ) -> _KingdomLieuButton:
            """Rebuild from the wire — THIS module's strings only."""
            return cls(_strings(_locale(interaction))[f"{kind}_button"])

        async def callback(self, interaction: discord.Interaction) -> None:
            await _open_lieu(interaction, kind)

    _KingdomLieuButton.__name__ = f"KingdomLieu{kind.capitalize()}Button"
    _KingdomLieuButton.__qualname__ = _KingdomLieuButton.__name__
    return _KingdomLieuButton


KingdomLieuConseilButton = _lieu_view_class("conseil")
KingdomLieuRempartsButton = _lieu_view_class("remparts")
KingdomLieuComptesButton = _lieu_view_class("comptes")
KingdomLieuParoisseButton = _lieu_view_class("paroisse")
KingdomLieuVoliereButton = _lieu_view_class("voliere")


def hub_buttons(locale: str) -> list[Any]:
    """The five doors (they live in the Entrée chooser view)."""
    strings = _strings(locale)
    return [
        KingdomLieuConseilButton(strings["conseil_button"]),
        KingdomLieuRempartsButton(strings["remparts_button"]),
        KingdomLieuComptesButton(strings["comptes_button"]),
        KingdomLieuParoisseButton(strings["paroisse_button"]),
        KingdomLieuVoliereButton(strings["voliere_button"]),
    ]


def entree_view(locale: str) -> Any:
    """The ephemeral chooser behind 🏰 Entrée — « Où souhaitez-vous

    vous rendre ? » — the five doors in one ActionRow (fenetre-unique-v2
    keeps it the clicker's single live window).
    """
    import discord

    strings = _strings(locale)
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(discord.ui.TextDisplay(f"## {strings['entree_title']}"))
    view.add_item(discord.ui.ActionRow(*hub_buttons(locale)))
    return view


def _green(button: Any) -> Any:
    """lieux-rows-v1: a default place action renders GREEN."""
    button.item.style = discord.ButtonStyle.success
    return button


def _gray(button: Any) -> Any:
    """lieux-rows-v1: an out-of-stock card renders GRAY and disabled."""
    button.item.style = discord.ButtonStyle.secondary
    button.item.disabled = True
    return button


def _stock_style(button: Any, has_stock: bool) -> Any:
    """Green while held, gray+disabled otherwise (never hidden)."""
    return _green(button) if has_stock else _gray(button)


class KingdomLieuSortirButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdoms:lieux:sortir",
):
    """The red 🚪 Sortir of every lieu view (lieux-rows-v1, Drasah 01/11).

    Line 1 rule: the place's default actions render green and Sortir
    closes the LAST slot in red — one click walks the player back to
    the Entrée orientation (the single ephemeral window is REPLACED,
    fenetre-unique-v2).
    """

    def __init__(self, label: str, row: int | None = None) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id="kingdoms:lieux:sortir",
                style=discord.ButtonStyle.danger,
                row=row,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> "KingdomLieuSortirButton":
        """Rebuild from the wire — THIS module's strings only."""
        return cls(_strings(_locale(interaction))["sortir_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        await _open_entree(interaction)


def _sortir(locale: str, row: int | None = None) -> KingdomLieuSortirButton:
    """The red exit of a lieu view (classic rows may pin it to a row)."""
    return KingdomLieuSortirButton(_strings(locale)["sortir_button"], row=row)


async def _open_entree(interaction: discord.Interaction) -> None:
    """Open the Entrée chooser as the clicker's single ephemeral window."""
    from kingdoms.mods.kingdoms.kingdom_persistent import (
        _open_unique_ephemeral,
        _strings as _merged_strings,
        _wiring,
    )

    locale = _locale(interaction)
    strings = _merged_strings(locale)
    wiring = _wiring()
    if wiring.kingdoms_service is None:
        await interaction.response.send_message(
            _strings(locale)["no_service"], ephemeral=True
        )
        return
    lord, kingdom = await _require_lord_kingdom(
        interaction, wiring, _strings(locale)
    )
    if lord is None or kingdom is None:
        return
    await _open_unique_ephemeral(interaction, view=entree_view(locale))


class KingdomLieuEntreeButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdoms:lieux:entree",
):
    """The hub's ONE door — 🏰 Entrée opens the ephemeral chooser."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id="kingdoms:lieux:entree",
                style=discord.ButtonStyle.primary,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> "KingdomLieuEntreeButton":
        """Rebuild from the wire — THIS module's strings only."""
        return cls(_strings(_locale(interaction))["entree_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        await _open_entree(interaction)


def hub_entree_button(locale: str) -> KingdomLieuEntreeButton:
    """The single 🏰 Entrée button the canary hub renders."""
    return KingdomLieuEntreeButton(_strings(locale)["entree_button"])


def canary_salon_display(key: str, name: str, kingdom: Any) -> str:
    """lieux-et-conseil-v1: the council salon becomes « Discussions ».

    Only the canary kingdoms adopt the new display — the player
    kingdoms keep the current name while the gate is active.
    """
    if key == "salle-du-conseil" and is_canary_realm(kingdom):
        return "💬 discussions"
    return name


async def _open_lieu(interaction: discord.Interaction, kind: str) -> None:
    """Open one lieu as the clicker's single ephemeral window."""
    from kingdoms.mods.kingdoms.kingdom_persistent import (
        _open_unique_ephemeral,
        _strings as _merged_strings,
        _wiring,
    )

    locale = _locale(interaction)
    strings = _merged_strings(locale)
    wiring = _wiring()
    if wiring.kingdoms_service is None:
        await interaction.response.send_message(
            _strings(locale)["no_service"], ephemeral=True
        )
        return
    lord, kingdom = await _require_lord_kingdom(interaction, wiring, _strings(locale))
    if lord is None or kingdom is None:
        return
    if kind == "comptes":
        # The ledger is a defer+followup window (heavy mosaic paint).
        await _open_comptes(interaction, wiring, kingdom, strings, locale)
        return
    from kingdoms.mods.kingdoms.kingdom_realm_content import (
        _build_church,
        _build_patrol,
        _gather_state,
    )

    state = await _gather_state(kingdom, wiring)
    if kind == "conseil":
        # conseil-objectif-v1 (Drasah 01/11): the base body carries the
        # Classement computed LIVE from the whole season, and the Objectif
        # button follows the clicker's crown (king-only).
        view, files = await build_conseil_view(
            strings,
            kingdom,
            state,
            wiring,
            locale,
            rank=await _conseil_rank(wiring, kingdom),
            viewer_is_king=str(getattr(lord, "role", "")) == "king",
        )
    elif kind == "remparts":
        view, files = (
            _build_patrol(
                strings,
                kingdom,
                state,
                media="attachment://rempart.png",
                rows=_remparts_rows(strings, state, wiring, locale),
            ),
            _lieu_files("Rempart.png", "rempart.png"),
        )
    elif kind == "paroisse":
        view, files = (
            _build_church(
                strings,
                kingdom,
                state,
                media="attachment://paroisse.png",
                rows=_paroisse_rows(strings, kingdom, state, locale),
            ),
            _paroisse_files(state),
        )
    else:  # voliere
        view, files = await _build_voliere(wiring, kingdom, strings, locale)
    await _open_unique_ephemeral(interaction, view=view, files=files or None)


async def edit_remparts_view(interaction: discord.Interaction) -> bool:
    """remparts-fenetre-v1 (Drasah 03/11): re-render the 🧱 Remparts
    view IN PLACE — the player's ephemeral window KEEPS its message
    (the Garde Royale wizard's Valider / Annuler exits walk back to
    the Remparts view instead of leaving a bare note behind).

    False when the view could not be rebuilt (the caller falls back
    to its own note); the caller OWNS the interaction response.
    """
    import time as _time

    from kingdoms.mods.kingdoms.kingdom_persistent import (
        _EPHEMERAL_WINDOWS,
        _lord_of,
        _strings as _merged_strings,
        _wiring,
    )
    from kingdoms.mods.kingdoms.kingdom_realm_content import (
        _build_patrol,
        _gather_state,
    )

    locale = _locale(interaction)
    strings = _merged_strings(locale)
    wiring = _wiring()
    kingdoms_service = wiring.kingdoms_service
    if kingdoms_service is None:
        return False
    lord = await _lord_of(
        kingdoms_service, str(interaction.user.id), wiring.bot_admins
    )
    if lord is None or getattr(lord, "left", False):
        return False
    kingdom = next(
        (
            k
            for k in await kingdoms_service.kingdoms()
            if str(k.id) == str(getattr(lord, "kingdom_id", None))
        ),
        None,
    )
    if kingdom is None:
        return False
    state = await _gather_state(kingdom, wiring)
    view = _build_patrol(
        strings,
        kingdom,
        state,
        media="attachment://rempart.png",
        rows=_remparts_rows(strings, state, wiring, locale),
    )
    await interaction.response.edit_message(
        view=view, attachments=_lieu_files("Rempart.png", "rempart.png")
    )
    _EPHEMERAL_WINDOWS[str(getattr(interaction.user, "id", ""))] = (
        interaction,
        _time.monotonic(),
    )
    return True


def _paroisse_files(state: dict[str, Any]) -> list[discord.File]:
    """The parish illustration follows the live tier (Chapelle→Cathédrale)."""
    tier = 1
    try:
        tier = min(3, max(1, int((state.get("parish") or {}).get("tier", 1) or 1)))
    except Exception:
        tier = 1
    return _lieu_files(f"paroisse{tier}.png", "paroisse.png")


async def _build_voliere(
    wiring: Any, kingdom: Any, strings: dict[str, Any], locale: str
) -> tuple[Any, list[discord.File]]:
    """The Volière lieu view — the voliere panel content + illustration."""
    from kingdoms.mods.kingdoms.kingdom_voliere_panel import (
        _voliere_content,
        _voliere_state,
        _voliere_view,
    )

    voliere_state = await _voliere_state(wiring, str(kingdom.id))
    content = await _voliere_content(wiring, kingdom, strings, voliere_state)
    view = _voliere_view(strings, voliere_state)
    # The lieu view wraps the voliere content in the lieu panel so the
    # illustration can ride with it (fenetre-unique keeps one window).
    from kingdoms.mods.kingdoms.kingdom_realm_content import _panel_view_with_buttons

    return (
        _panel_view_with_buttons(
            str(strings.get("voliere_title", "Volière")),
            str(content),
            "kingdoms:realm:view:lieu-voliere",
            discord.Colour.green(),
            [_sortir(locale)],
            media="attachment://voliere.png",
        ),
        _lieu_files("voliere.png", "voliere.png"),
    )


_OBJECTIF_PAGE_SIZE = 23
# conseil-objectif-v2-fix (Drasah 01/11): Discord REQUIRES a select
# option value of 1-100 characters — the « Aucun » sentinel rides a
# real "none" value on the wire, mapped back to « clear » in _on_pick
# (an empty value made followup.send 400 AFTER the defer: the King
# clicked and NOTHING answered — his 01/11 live report).
_OBJECTIF_NONE_VALUE = "none"


def _objectif_replaces_previous(entry: Any) -> bool:
    """objectif-fenetre-coexist-v1 (Drasah 01/11): True only when the
    previous registry entry is a defer+followup PICKER window (a
    3-tuple) — the council sheet rides a send_message 2-tuple and
    SURVIVES the 🎯 Objectif click: the picker opens ALONGSIDE the
    window the button sits on (his 01/11 live report)."""
    return entry is not None and len(entry) > 2


def _objectif_max_page(catalog: dict[str, str]) -> int:
    """The last page index of a goal catalog (23 options per page)."""
    return max(0, (max(len(catalog), 1) - 1) // _OBJECTIF_PAGE_SIZE)


def _objectif_page_options(
    locale: str,
    catalog: dict[str, str],
    current: str,
    offset: int,
) -> list[discord.SelectOption]:
    """One page of a goal dropdown — 25 options max (the Discord cap).

    conseil-objectif-v2 (Drasah 01/11): free text is GONE — the King
    picks from the catalogs. The « Aucun » sentinel leads, the CURRENT
    goal sits right behind it with its check mark (so the King re-opens
    his choice whatever the page), then the catalog's slice.
    """
    lieu = _strings(locale)
    options = [
        discord.SelectOption(
            label=lieu["objectif_none_label"], value=_OBJECTIF_NONE_VALUE
        )
    ]
    if current and current in catalog:
        options.append(
            discord.SelectOption(label=f"✅ {catalog[current]}"[:100], value=current)
        )
    keys = [key for key in catalog if key != current]
    window = keys[
        offset * _OBJECTIF_PAGE_SIZE : (offset + 1) * _OBJECTIF_PAGE_SIZE
    ]
    for key in window:
        options.append(
            discord.SelectOption(label=str(catalog[key])[:100], value=key)
        )
    return options[:25]


_OBJECTIF_KINDS = (
    ("target_kingdom", "⚔️", "objectif_select_kingdom", "conseil_objectif_kingdom"),
    (
        "target_territory",
        "🗺️",
        "objectif_select_map",
        "conseil_objectif_map",
    ),
    (
        "target_alliance",
        "🤝",
        "objectif_select_alliance",
        "conseil_objectif_alliance",
    ),
)


def _objectifs_lines(
    locale: str, goals: dict[str, Any], undefined: bool = False
) -> list[str]:
    """The three goal lines — one display line per kind."""
    lieu = _strings(locale)
    lines: list[str] = []
    for kind, _emoji, _select, template in _OBJECTIF_KINDS:
        label = str(goals.get(f"{kind}_label") or "").strip()
        if not label and undefined:
            label = lieu["objectif_undefined"]
        if label:
            lines.append(lieu[template].format(label))
    return lines


async def _territory_owned_by_kingdom(
    wiring: Any, kingdom: Any, map_key: str
) -> bool:
    """objectif-possede-v1 (Drasah 02/11): True when the territory
    behind ``map_key`` already belongs to ``kingdom`` — the goal then
    reads as a DEFEND priority, never as a « sought » map. Wiring
    without a territories service answers False (never a crash)."""
    if not map_key:
        return False
    try:
        territories_service = getattr(wiring, "territories_service", None)
        if territories_service is None:
            return False
        for territory in await territories_service.territories():
            if str(getattr(territory, "map_key", "")) == map_key:
                return (
                    str(getattr(territory, "owner_kingdom_id", "") or "")
                    == str(getattr(kingdom, "id", ""))
                )
    except Exception:
        logger.warning(
            "KINGDOM LIEUX: territory ownership check failed", exc_info=True
        )
    return False


def _kingdom_holds_civ(kingdom: Any, civ_key: str) -> bool:
    """objectif-possede-v1: True when the kingdom already holds the
    civilization — the alliance goal then reads as a MARRIAGE wish."""
    if not civ_key:
        return False
    return civ_key in [
        str(item) for item in (getattr(kingdom, "civilizations", None) or [])
    ]


async def _territory_owner_suffix(
    locale: str, wiring: Any, map_key: str
) -> str:
    """conseil-objectif-axe1 (Drasah 01/11): the sought territory's line
    carries its OWNER — or « Destination inconnue » while the map
    belongs to nobody (never released). Live data: the line re-renders
    each time the sheet is built, so a change of hands moves it."""
    if not map_key:
        return ""
    lieu = _strings(locale)
    try:
        service = getattr(wiring, "kingdoms_service", None)
        territories_service = getattr(wiring, "territories_service", None)
        if service is None or territories_service is None:
            return ""
        owner = ""
        for territory in await territories_service.territories():
            if str(getattr(territory, "map_key", "")) == map_key:
                owner = str(getattr(territory, "owner_kingdom_id", "") or "")
                break
        if not owner:
            return lieu["objectif_detail_suffix"].format(
                lieu["objectif_map_unknown_owner"]
            )
        for kingdom in await service.kingdoms():
            if str(getattr(kingdom, "id", "")) == owner:
                return lieu["objectif_detail_suffix"].format(
                    str(getattr(kingdom, "name", owner))
                )
        return lieu["objectif_detail_suffix"].format(
            lieu["objectif_map_unknown_owner"]
        )
    except Exception:
        logger.warning(
            "KINGDOM LIEUX: territory owner suffix failed", exc_info=True
        )
        return ""


async def _alliance_detail_suffix(
    locale: str, wiring: Any, civ_key: str, civ_label: str
) -> str:
    """conseil-objectif-axe1 (Drasah 01/11): the sought alliance's line
    carries its live detail. A MARRIAGE wins — only the wedded lord
    shows; otherwise the official acquisition condition (the
    Scriptorium renderer). Independently, a live mercenary lot at the
    tavern rides as a trailing note."""
    if not civ_key:
        return ""
    lieu = _strings(locale)
    detail = ""
    try:
        service = getattr(wiring, "kingdoms_service", None)
        if service is not None:
            married = [
                lord
                for lord in await service.lords()
                if not getattr(lord, "left", False)
                and str(getattr(lord, "married_civilization", "") or "")
                == civ_key
            ]
            if married:
                detail = lieu["objectif_detail_suffix"].format(
                    str(getattr(married[0], "display_name", "?"))
                )
            else:
                config = getattr(service, "config", None)
                civ = next(
                    (
                        entry
                        for entry in (
                            getattr(config, "civilizations", ()) or ()
                        )
                        if str(getattr(entry, "key", "")) == civ_key
                    ),
                    None,
                )
                if civ is not None:
                    from kingdoms.mods.kingdoms.kingdom_scriptorium import (
                        _diplomatie_condition_text,
                        _strings as _scriptorium_strings,
                    )

                    condition = _diplomatie_condition_text(
                        civ,
                        _scriptorium_strings(locale),
                        list(getattr(config, "maps", ()) or ()),
                    )
                    if condition:
                        detail = lieu["objectif_detail_suffix"].format(
                            condition
                        )
        market = None
        try:
            from kingdoms.mods.kingdoms.kingdom_mercenary_panel import (
                _read_market_safe,
            )

            market = await _read_market_safe(wiring)
        except Exception:
            market = None
        if isinstance(market, dict) and not market.get("closed"):
            needles = {civ_key, civ_label}
            offered = any(
                str(lot.get("civ", "") or "") in needles
                for lot in market.get("lots", []) or []
            )
            if offered:
                detail += lieu["objectif_alliance_mercenary_suffix"].format(
                    lieu["objectif_alliance_mercenary"]
                )
    except Exception:
        logger.warning(
            "KINGDOM LIEUX: alliance detail suffix failed", exc_info=True
        )
        return ""
    return detail


async def _objectifs_display_lines(
    locale: str, kingdom: Any, wiring: Any | None = None
) -> list[str]:
    """The three goal lines, ENRICHED with live data (axe1): the
    territory's owner (or « Destination inconnue ») and the alliance's
    marriage lord / acquisition condition (+ mercenary note). Wiring
    None (or a failure) keeps the plain lines — never a crash."""
    lieu = _strings(locale)
    goals = dict(getattr(kingdom, "council_objectives", {}) or {})
    lines: list[str] = []
    for kind, _emoji, _select, template in _OBJECTIF_KINDS:
        label = str(goals.get(f"{kind}_label") or "").strip()
        if not label:
            continue
        if wiring is not None:
            # objectif-possede-v1 (Drasah 02/11): a goal on something
            # the kingdom ALREADY holds never reads « sought » — an
            # owned map becomes a DEFEND priority, a held alliance a
            # MARRIAGE wish. The reformulation is LIVE: the line
            # re-renders at every sheet build.
            if kind == "target_territory" and await _territory_owned_by_kingdom(
                wiring, kingdom, str(goals.get("target_territory") or "")
            ):
                lines.append(lieu["objectif_map_defend_line"].format(label))
                continue
            if kind == "target_alliance" and _kingdom_holds_civ(
                kingdom, str(goals.get("target_alliance") or "")
            ):
                lines.append(lieu["objectif_alliance_marry_line"].format(label))
                continue
        text = lieu[template].format(label)
        if wiring is not None:
            if kind == "target_territory":
                text += await _territory_owner_suffix(
                    locale, wiring, str(goals.get("target_territory") or "")
                )
            elif kind == "target_alliance":
                text += await _alliance_detail_suffix(
                    locale,
                    wiring,
                    str(goals.get("target_alliance") or ""),
                    label,
                )
        lines.append(text)
    return lines


async def _objectifs_read_content(
    locale: str, kingdom: Any, wiring: Any | None = None
) -> str:
    """The picker's READ sheet — the realm's goals, one line each."""
    lieu = _strings(locale)
    lines = await _objectifs_display_lines(locale, kingdom, wiring)
    return "\n".join(
        [
            f"## {lieu['objectif_picker_title'].format(getattr(kingdom, 'name', ''))}",
            "",
            *(lines or [lieu["conseil_objectifs_none"]]),
            "",
            lieu["objectif_read_hint"],
        ]
    )


def _objectifs_edit_content(
    locale: str, kingdom: Any, staged: dict[str, Any]
) -> str:
    """The picker's EDIT sheet — the STAGED goals, « non défini » holes."""
    lieu = _strings(locale)
    lines = _objectifs_lines(locale, staged, undefined=True)
    return "\n".join(
        [
            f"## {lieu['objectif_picker_title'].format(getattr(kingdom, 'name', ''))}",
            "",
            *lines,
            "",
            lieu["objectif_edit_hint"],
        ]
    )


async def _save_objectives(
    wiring: Any, kingdom: Any, staged: dict[str, Any]
) -> bool:
    """Persist ALL THREE goal choices in ONE save (best effort).

    conseil-objectif-v3 (Drasah 01/11): the choices stay STAGED in the
    window — only ✅ Valider commits them, all at once, with their
    display labels and an updated_at stamp.
    """
    from time import time

    objectives = dict(getattr(kingdom, "council_objectives", {}) or {})
    for kind, _emoji, _select, _template in _OBJECTIF_KINDS:
        objectives[kind] = str(staged.get(kind) or "").strip()
        objectives[f"{kind}_label"] = str(
            staged.get(f"{kind}_label") or ""
        ).strip()
    # objectif-possede-v1 (Drasah 02/11): stamp whether the target was
    # ALREADY held at save time — the achieve check (announce + erase)
    # only fires on a goal that was NOT owned when it was set.
    objectives["target_territory_at_save_owned"] = (
        bool(objectives.get("target_territory"))
        and await _territory_owned_by_kingdom(
            wiring, kingdom, str(objectives.get("target_territory") or "")
        )
    )
    objectives["target_alliance_at_save_owned"] = _kingdom_holds_civ(
        kingdom, str(objectives.get("target_alliance") or "")
    )
    objectives["updated_at"] = int(time())
    service = getattr(wiring, "kingdoms_service", None)
    try:
        kingdom.council_objectives = objectives
        if service is not None and hasattr(service, "save_kingdom"):
            await service.save_kingdom(kingdom)
    except Exception:
        logger.warning("KINGDOM LIEUX: objectives save failed", exc_info=True)
        return False
    return True


# ---------------------------------------------------------------------------
# objectif-annonces-v1 (Drasah 02/11): the achievement announce in the
# Discussions salon + the ONE pinned recap that follows every save.
# ---------------------------------------------------------------------------

_OBJECTIFS_PIN_MARKER = "kingdoms:objectifs:pin"


async def objectifs_achieved(kingdom: Any, wiring: Any) -> list[tuple[str, str]]:
    """The goals the kingdom has just REALIZED — (kind, label) pairs.

    objectif-annonces-v1 (Drasah 02/11): a territory goal fires when
    the kingdom now OWNS the map it did NOT own at save time; an
    alliance goal when the civilization entered a hand it was not in
    at save time. A goal set on something ALREADY held stays a
    reformulated line (defend / marriage — objectif-possede-v1) and
    NEVER announces. The kingdom goal carries no state — never fires.
    """
    goals = dict(getattr(kingdom, "council_objectives", None) or {})
    achieved: list[tuple[str, str]] = []
    map_key = str(goals.get("target_territory") or "")
    map_label = str(goals.get("target_territory_label") or "").strip()
    if (
        map_key
        and map_label
        and not bool(goals.get("target_territory_at_save_owned"))
        and await _territory_owned_by_kingdom(wiring, kingdom, map_key)
    ):
        achieved.append(("target_territory", map_label))
    civ_key = str(goals.get("target_alliance") or "")
    civ_label = str(goals.get("target_alliance_label") or "").strip()
    if (
        civ_key
        and civ_label
        and not bool(goals.get("target_alliance_at_save_owned"))
        and _kingdom_holds_civ(kingdom, civ_key)
    ):
        achieved.append(("target_alliance", civ_label))
    return achieved


async def erase_objectifs_kinds(wiring: Any, kingdom: Any, kinds: list[str]) -> bool:
    """Clear the ACHIEVED goals (Drasah 02/11: an achieved objective is
    auto-erased — the announce + the redefine shortcut replace it)."""
    from time import time

    service = getattr(wiring, "kingdoms_service", None)
    objectives = dict(getattr(kingdom, "council_objectives", None) or {})
    for kind in kinds:
        objectives[kind] = ""
        objectives[f"{kind}_label"] = ""
        objectives.pop(f"{kind}_at_save_owned", None)
    objectives["updated_at"] = int(time())
    try:
        kingdom.council_objectives = objectives
        if service is not None and hasattr(service, "save_kingdom"):
            await service.save_kingdom(kingdom)
    except Exception:
        logger.warning(
            "KINGDOM LIEUX: achieved objectives erase failed", exc_info=True
        )
        return False
    return True


async def _discussions_channel(guild: Any, kingdom: Any) -> Any:
    """The kingdom's Discussions salon (the renamed council salon of
    the canary hub) — slug-blind on the display name."""
    try:
        from kingdoms.mods.kingdoms.kingdom_realms import _find_realm_category
        from kingdoms.mods.kingdoms.kingdom_setup import _slug

        category = _find_realm_category(guild, str(getattr(kingdom, "name", "")))
        if category is None:
            return None
        for wanted in ("discussions", "salle-du-conseil"):
            for channel in getattr(category, "channels", []) or []:
                if _slug(getattr(channel, "name", "")) == wanted:
                    return channel
    except Exception:
        logger.warning(
            "KINGDOM LIEUX: discussions channel resolve failed", exc_info=True
        )
    return None


def _objectifs_active(kingdom: Any) -> bool:
    """True when at least one goal carries a label."""
    goals = dict(getattr(kingdom, "council_objectives", None) or {})
    return any(
        str(goals.get(f"{kind}_label") or "").strip()
        for kind, _emoji, _select, _template in _OBJECTIF_KINDS
    )


async def _objectifs_pin_content(
    locale: str, kingdom: Any, wiring: Any, active: bool
) -> str:
    """The pinned recap text — the same enriched lines as the council
    sheet, or the « none » line when no goal is active."""
    lieu = _strings(locale)
    lines = (
        await _objectifs_display_lines(locale, kingdom, wiring) if active else []
    )
    return "\n".join(
        [
            f"## {lieu['objectif_pin_title'].format(getattr(kingdom, 'name', ''))}",
            "",
            *(lines or [lieu["objectif_pin_none"]]),
            "",
            lieu["objectif_pin_hint"],
            f"-# {_OBJECTIFS_PIN_MARKER}:{getattr(kingdom, 'id', '')}",
        ]
    )


async def _refresh_council_parent_safe(
    wiring: Any, kingdom: Any, locale: str, parent: Any
) -> None:
    """conseil-rafraichi-v1 (Drasah 02/11): re-render the ⚔️ Salle du
    conseil ephemeral IN PLACE after a goals save — his live report:
    validating the picker left the council sheet showing the STALE
    goals (the sheet was rendered BEFORE the save). Best effort: a
    failure never blocks the save's own flow."""
    from kingdoms.mods.kingdoms.kingdom_realm_content import _gather_state
    from kingdoms.mods.kingdoms.kingdom_persistent import (
        _strings as _merged_strings,
    )

    try:
        state = await _gather_state(kingdom, wiring)
        view, _files = await build_conseil_view(
            _merged_strings(locale),
            kingdom,
            state,
            wiring,
            locale,
            rank=await _conseil_rank(wiring, kingdom),
            viewer_is_king=True,
        )
        await parent.edit(view=view)
        logger.info(
            "KINGDOM LIEUX: council sheet refreshed in place (%s)",
            str(getattr(kingdom, "id", "")),
        )
    except Exception:
        logger.warning(
            "KINGDOM LIEUX: council sheet refresh failed (ignored)",
            exc_info=True,
        )


async def refresh_objectifs_pin_safe(
    guild: Any, wiring: Any, kingdom: Any, locale: str
) -> bool:
    """The pinned objective recap in Discussions — ONE pinned message
    per kingdom, edited in place (objectif-annonces-v1, Drasah 02/11:
    redefining the objective replaces the previous pin, never stacks).
    An EMPTY goals sheet unpins the message (nothing left to show)."""
    from kingdoms.mods.kingdoms.panel_messages import NO_MENTIONS

    if not is_canary_realm(kingdom):
        return False
    channel = await _discussions_channel(guild, kingdom)
    if channel is None:
        # pin-diagnostic-v1 (Drasah 02/11): this failure was SILENT —
        # his live report had nothing in Discussions after a save, and
        # the logs said nothing. Name what the realm actually carries.
        cat_name, salons = "?", "?"
        try:
            from kingdoms.mods.kingdoms.kingdom_realms import (
                _find_realm_category,
            )

            category = _find_realm_category(
                guild, str(getattr(kingdom, "name", ""))
            )
            cat_name = (
                str(getattr(category, "name", "?"))
                if category is not None
                else "MISSING"
            )
            salons = (
                ",".join(
                    str(getattr(c, "name", "?"))
                    for c in (getattr(category, "channels", []) or [])
                )
                if category is not None
                else "-"
            )
        except Exception:
            logger.warning(
                "KINGDOM LIEUX: objectives pin diagnostic failed",
                exc_info=True,
            )
        logger.warning(
            "KINGDOM LIEUX: objectives pin SKIPPED — no discussions salon"
            " for %s (category=%s, salons=[%s])",
            str(getattr(kingdom, "name", "")),
            cat_name,
            salons,
        )
        return False
    active = _objectifs_active(kingdom)
    content = await _objectifs_pin_content(locale, kingdom, wiring, active)
    goals = dict(getattr(kingdom, "council_objectives", None) or {})
    message = None
    pin_id = int(goals.get("pin_message_id") or 0)
    if pin_id:
        try:
            message = await channel.fetch_message(pin_id)
        except Exception:
            message = None
    if message is None:
        if not active:
            return False  # nothing to show, nothing pinned
        try:
            message = await channel.send(content, allowed_mentions=NO_MENTIONS)
        except Exception:
            logger.warning(
                "KINGDOM LIEUX: objectives pin send failed", exc_info=True
            )
            return False
    else:
        try:
            if (getattr(message, "content", "") or "") != content:
                await message.edit(content=content)
        except Exception:
            logger.warning(
                "KINGDOM LIEUX: objectives pin edit failed", exc_info=True
            )
    if active:
        if not getattr(message, "pinned", False):
            try:
                await message.pin()
            except Exception:
                logger.warning(
                    "KINGDOM LIEUX: objectives pin failed", exc_info=True
                )
    elif getattr(message, "pinned", False):
        try:
            await message.unpin()
        except Exception:
            logger.warning(
                "KINGDOM LIEUX: objectives unpin failed", exc_info=True
            )
    # persist the pin ref on the objectives doc (best effort).
    if active:
        try:
            fresh = dict(getattr(kingdom, "council_objectives", None) or {})
            if int(fresh.get("pin_message_id") or 0) != int(message.id):
                fresh["pin_message_id"] = int(message.id)
                kingdom.council_objectives = fresh
                service = getattr(wiring, "kingdoms_service", None)
                if service is not None and hasattr(service, "save_kingdom"):
                    await service.save_kingdom(kingdom)
        except Exception:
            logger.warning(
                "KINGDOM LIEUX: objectives pin ref save failed",
                exc_info=True,
            )
    logger.info(
        "KINGDOM LIEUX: objectives pin refreshed (%s, #%s, active=%s)",
        str(getattr(kingdom, "id", "")),
        str(getattr(channel, "name", "?")),
        active,
    )
    return True


async def announce_objectif_achieved_safe(
    guild: Any,
    wiring: Any,
    kingdom: Any,
    achieved: list[tuple[str, str]],
    locale: str,
) -> None:
    """Post the achievement announce in Discussions with the redefine
    shortcut (objectif-annonces-v1) — the goals were already erased on
    the caller's side, the announce alone carries the news."""
    from kingdoms.mods.kingdoms.panel_messages import NO_MENTIONS

    channel = await _discussions_channel(guild, kingdom)
    if channel is None:
        return
    lieu = _strings(locale)
    view = discord.ui.View(timeout=None)
    view.add_item(KingdomLieuObjectifButton(lieu["objectif_redefine_button"]))
    for kind, label in achieved:
        key = (
            "objectif_achieved_map"
            if kind == "target_territory"
            else "objectif_achieved_alliance"
        )
        text = "\n".join(
            [str(lieu[key]).format(label=label), "", lieu["objectif_achieved_hint"]]
        )
        try:
            await channel.send(text, view=view, allowed_mentions=NO_MENTIONS)
        except Exception:
            logger.warning(
                "KINGDOM LIEUX: achievement announce failed", exc_info=True
            )


async def _close_ephemeral_window(interaction: discord.Interaction) -> None:
    """Close the ephemeral window the component sits on (type-6 defer +
    delete the original response), and drop the registry entry when it
    matches — the shared exit of the Objectif picker AND the Classement
    view (conseil-objectif-axe2/axe3, Drasah 01/11)."""
    from kingdoms.mods.kingdoms.kingdom_persistent import _EPHEMERAL_WINDOWS

    await interaction.response.defer()
    try:
        await interaction.delete_original_response()
    except Exception:
        logger.info(
            "KINGDOM LIEUX: ephemeral window close failed (ignored)",
            exc_info=True,
        )
    user_id = str(getattr(interaction.user, "id", ""))
    previous = _EPHEMERAL_WINDOWS.get(user_id)
    window = (
        previous[2] if previous is not None and len(previous) > 2 else None
    )
    if (
        window is not None
        and getattr(getattr(interaction, "message", None), "id", None)
        == getattr(window, "id", None)
    ):
        _EPHEMERAL_WINDOWS.pop(user_id, None)


def _objectif_quit_button(
    lieu: dict[str, Any], row: int = 3, label: str | None = None
) -> Any:
    """The 🚪 exit of a sub-window — OVERWRITES it with the Entrée
    hub (Drasah 02/11: « il écrase et remplace la vue » — Sortir in a
    sub-view walks the player back to the orientation chooser so he
    can redirect, never a dead-end close)."""
    button = discord.ui.Button(
        label=label or lieu["objectif_quit_button"],
        style=discord.ButtonStyle.secondary,
        row=row,
    )

    async def _walk_to_entree(interaction: discord.Interaction) -> None:
        await _open_entree(interaction)

    button.callback = _walk_to_entree
    return button


def _objectifs_read_view(
    wiring: Any,
    kingdom: Any,
    locale: str,
    kingdoms_catalog: dict[str, str],
    maps_catalog: dict[str, str],
    civs_catalog: dict[str, str],
) -> discord.ui.View:
    """The READ view — the goals sheet + [✏️ Modifier][🚪 Quitter]."""
    lieu = _strings(locale)
    view = discord.ui.View(timeout=None)

    async def _edit(interaction: discord.Interaction) -> None:
        staged = {
            key: value
            for key, value in dict(
                getattr(kingdom, "council_objectives", {}) or {}
            ).items()
            if key != "updated_at"
        }
        await interaction.response.edit_message(
            content=_objectifs_edit_content(locale, kingdom, staged),
            view=_objectifs_picker(
                wiring,
                kingdom,
                locale,
                kingdoms_catalog,
                maps_catalog,
                civs_catalog,
                staged,
            ),
        )

    edit_button = discord.ui.Button(
        label=lieu["objectif_edit_button"],
        style=discord.ButtonStyle.success,
        row=0,
    )
    edit_button.callback = _edit
    view.add_item(edit_button)
    view.add_item(_objectif_quit_button(lieu, row=0))
    return view


def _objectifs_picker(
    wiring: Any,
    kingdom: Any,
    locale: str,
    kingdoms_catalog: dict[str, str],
    maps_catalog: dict[str, str],
    civs_catalog: dict[str, str],
    staged: dict[str, Any] | None = None,
    map_page: int = 0,
    civ_page: int = 0,
    reveal: tuple[str, ...] = (),
) -> discord.ui.View:
    """The EDIT view (conseil-objectif-v3, Drasah 01/11).

    One row per goal: a dropdown (the maps/civs page through ◀️▶️)
    that TRANSFORMS into a « ✏️ <choix> » change button once picked —
    the choices stay STAGED until ✅ Valider saves them all at once;
    🚪 Quitter closes without saving (the council sheet survives,
    coexist). The « Aucun » sentinel clears a staged goal.
    """
    lieu = _strings(locale)
    staged = dict(staged or {})
    view = discord.ui.View(timeout=None)

    def _rerender(
        interaction: discord.Interaction,
        new_staged: dict[str, Any],
        map_p: int = map_page,
        civ_p: int = civ_page,
        new_reveal: tuple[str, ...] = reveal,
    ) -> Any:
        async def _go() -> None:
            await interaction.response.edit_message(
                content=_objectifs_edit_content(locale, kingdom, new_staged),
                view=_objectifs_picker(
                    wiring,
                    kingdom,
                    locale,
                    kingdoms_catalog,
                    maps_catalog,
                    civs_catalog,
                    new_staged,
                    map_p,
                    civ_p,
                    new_reveal,
                ),
            )

        return _go

    def _on_pick(kind: str, catalog: dict[str, str], select: Any) -> Any:
        async def _choose(interaction: discord.Interaction) -> None:
            raw = str(select.values[0]) if select.values else _OBJECTIF_NONE_VALUE
            # the sentinel maps back to « clear the goal »
            value = "" if raw == _OBJECTIF_NONE_VALUE else raw
            new_staged = dict(staged)
            new_staged[kind] = value
            new_staged[f"{kind}_label"] = str(
                catalog.get(value, "") if value else ""
            )
            await _rerender(
                interaction, new_staged, new_reveal=tuple(set(reveal) - {kind})
            )()

        return _choose

    def _on_change(kind: str) -> Any:
        async def _change(interaction: discord.Interaction) -> None:
            # « changer » — the dropdown of that goal comes back
            await _rerender(
                interaction, staged, new_reveal=tuple(set(reveal) | {kind})
            )()

        return _change

    def _on_flip(which: str, delta: int) -> Any:
        async def _flip(interaction: discord.Interaction) -> None:
            if which == "target_territory":
                await _rerender(
                    interaction,
                    staged,
                    map_p=min(
                        max(map_page + delta, 0),
                        _objectif_max_page(maps_catalog),
                    ),
                )()
            else:
                await _rerender(
                    interaction,
                    staged,
                    civ_p=min(
                        max(civ_page + delta, 0),
                        _objectif_max_page(civs_catalog),
                    ),
                )()

        return _flip

    rows = {
        "target_kingdom": 0,
        "target_territory": 1,
        # the alliance select rides row 3 (its flips share row 4
        # with Valider/Quitter) — row 2 belongs to the maps flips.
        "target_alliance": 3,
    }
    for kind, emoji, select_key, _template in _OBJECTIF_KINDS:
        staged_key = str(staged.get(kind) or "")
        if staged_key and kind not in reveal:
            change = discord.ui.Button(
                label=lieu["objectif_change_button"]
                .format(
                    f"{emoji} {staged.get(f'{kind}_label') or staged_key}"
                )[:80],
                style=discord.ButtonStyle.secondary,
                row=rows[kind],
            )
            change.callback = _on_change(kind)
            view.add_item(change)
            continue
        catalog, page = (
            (kingdoms_catalog, 0)
            if kind == "target_kingdom"
            else (maps_catalog, map_page)
            if kind == "target_territory"
            else (civs_catalog, civ_page)
        )
        select = discord.ui.Select(
            placeholder=lieu[select_key],
            options=_objectif_page_options(locale, catalog, staged_key, page),
            min_values=1,
            max_values=1,
            row=rows[kind],
        )
        select.callback = _on_pick(kind, catalog, select)
        view.add_item(select)
        # objectif-select-rows-fix (Drasah 01/11): Discord requires a
        # select ALONE in its action row — the ◀️▶️ flips rode the
        # selects' rows and the map/alliance dropdowns went dead (his
        # live report: only the kingdom dropdown answered). The maps
        # flips own row 2; the civs flips share row 4 with Valider +
        # Quitter so the view stays within Discord's five rows.
        if kind != "target_kingdom" and _objectif_max_page(catalog) > 0:
            flip_row = 2 if kind == "target_territory" else 4
            prev = discord.ui.Button(
                emoji="◀️", row=flip_row, disabled=page <= 0
            )
            prev.callback = _on_flip(kind, -1)
            view.add_item(prev)
            nxt = discord.ui.Button(
                emoji="▶️",
                row=flip_row,
                disabled=page >= _objectif_max_page(catalog),
            )
            nxt.callback = _on_flip(kind, 1)
            view.add_item(nxt)

    async def _validate(interaction: discord.Interaction) -> None:
        # conseil-rafraichi-v1 (Drasah 02/11): the council sheet the
        # picker was opened from is RE-RENDERED in place at the save —
        # his live report: validating left the sheet showing the STALE
        # goals. The parent rides the registry entry's 4th slot (the
        # CHILD back-reference), captured BEFORE the close pops it.
        from kingdoms.mods.kingdoms.kingdom_persistent import _EPHEMERAL_WINDOWS

        _entry = _EPHEMERAL_WINDOWS.get(str(getattr(interaction.user, "id", "")))
        parent = _entry[3] if _entry is not None and len(_entry) > 3 else None
        saved = await _save_objectives(wiring, kingdom, staged)
        if not saved:
            # the window STAYS open — the ⚠️ note rides the edit sheet
            # so the King retries without losing his staging.
            await interaction.response.edit_message(
                content=(
                    f"{_objectifs_edit_content(locale, kingdom, staged)}"
                    f"\n{lieu['objectif_save_failed']}"
                ),
                view=_objectifs_picker(
                    wiring,
                    kingdom,
                    locale,
                    kingdoms_catalog,
                    maps_catalog,
                    civs_catalog,
                    staged,
                    map_page,
                    civ_page,
                    reveal,
                ),
            )
            return
        # conseil-objectif-axe2 (Drasah 01/11): a valid save CLOSES the
        # window — no read sheet back, no note: the council sheet above
        # already shows the fresh goals (his « comportement plus
        # naturel » wish).
        await _close_ephemeral_window(interaction)
        # objectif-annonces-v1 (Drasah 02/11): the pinned recap of the
        # Discussions salon follows the save — one pinned message,
        # edited in place, never a stack.
        try:
            await refresh_objectifs_pin_safe(
                interaction.guild, wiring, kingdom, locale
            )
        except Exception:
            logger.warning(
                "KINGDOM LIEUX: objectives pin refresh failed", exc_info=True
            )
        if parent is not None:
            await _refresh_council_parent_safe(
                wiring, kingdom, locale, parent
            )

    validate = discord.ui.Button(
        label=lieu["objectif_validate_button"],
        style=discord.ButtonStyle.success,
        row=4,
    )
    validate.callback = _validate
    view.add_item(validate)
    view.add_item(_objectif_quit_button(lieu, row=4))
    return view


class KingdomLieuObjectifButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdoms:lieux:objectif",
):
    """conseil-objectif-v3 (Drasah 01/11): the King's 🎯 Objectif button
    of the Salle du conseil — line 1, RIGHT of Seigneurie. The window
    opens as a READ sheet of the realm's INDICATIVE goals (the catalogs,
    never free text); ✏️ Modifier turns each goal into a dropdown that
    TRANSFORMS into the chosen value, ✅ Valider saves all at once and
    🚪 Quitter closes the window — the council sheet survives (coexist).
    Green for the King, red+disabled for everyone else (never hidden)."""

    def __init__(self, label: str, enabled: bool = True) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id="kingdoms:lieux:objectif",
                style=(
                    discord.ButtonStyle.success
                    if enabled
                    else discord.ButtonStyle.danger
                ),
                disabled=not enabled,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> "KingdomLieuObjectifButton":
        """Rebuild from the wire (the crown check re-runs on click)."""
        return cls(_strings(_locale(interaction))["objectif_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        from time import monotonic

        from kingdoms.mods.kingdoms.kingdom_realm_content import _catalog_names
        from kingdoms.mods.kingdoms.kingdom_persistent import (
            _EPHEMERAL_WINDOWS,
            _close_previous_ephemeral,
            _kingdom_by_id_safe,
            _lord_of,
            _wiring,
        )

        locale = _locale(interaction)
        lieu = _strings(locale)
        wiring = _wiring()
        if wiring.kingdoms_service is None:
            await interaction.response.send_message(
                lieu["no_service"], ephemeral=True
            )
            return
        lord = await _lord_of(
            wiring.kingdoms_service, str(interaction.user.id), wiring.bot_admins
        )
        if lord is None or getattr(lord, "left", False):
            await interaction.response.send_message(lieu["not_lord"], ephemeral=True)
            return
        if str(getattr(lord, "role", "")) != "king":
            await interaction.response.send_message(
                lieu["objectif_king_only"], ephemeral=True
            )
            return
        kingdom = await _kingdom_by_id_safe(
            wiring.kingdoms_service, str(getattr(lord, "kingdom_id", "") or "")
        )
        if kingdom is None:
            await interaction.response.send_message(lieu["not_lord"], ephemeral=True)
            return
        # objectif-coexist-type7-fix (Drasah 01/11): a bare
        # defer(ephemeral=True) on a component rides a TYPE-6 ack —
        # "DEFERRED UPDATE of the message the button sits on". On an
        # EPHEMERAL parent (the council sheet) the client then drops
        # the sheet waiting for an update that never comes — his live
        # report: one Objectif click and EVERYTHING vanished. The
        # window flow needs the TYPE-7 ack (deferred NEW message):
        # thinking=True.
        await interaction.response.defer(ephemeral=True, thinking=True)
        # the three catalogs — the kingdoms minus one's own realm, the
        # full map cadastre, the full civilization catalog.
        kingdoms_catalog: dict[str, str] = {}
        try:
            kingdoms_catalog = {
                str(item.id): str(item.name)
                for item in await wiring.kingdoms_service.kingdoms()
                if not getattr(item, "is_gaia", False)
                and str(item.id) != str(getattr(kingdom, "id", ""))
            }
        except Exception:
            logger.warning(
                "KINGDOM LIEUX: objectives kingdom catalog failed",
                exc_info=True,
            )
        user_id = str(getattr(interaction.user, "id", ""))
        try:
            maps_catalog = _catalog_names(wiring.kingdoms_service, "maps")
            civs_catalog = _catalog_names(
                wiring.kingdoms_service, "civilizations"
            )
            content = await _objectifs_read_content(locale, kingdom, wiring)
            view = _objectifs_read_view(
                wiring,
                kingdom,
                locale,
                kingdoms_catalog,
                maps_catalog,
                civs_catalog,
            )
            # objectif-fenetre-coexist-v1: the council sheet
            # SURVIVES the click — only a previous PICKER is replaced.
            if _objectif_replaces_previous(_EPHEMERAL_WINDOWS.get(user_id)):
                await _close_previous_ephemeral(user_id)
            window = await interaction.followup.send(
                content, view=view, ephemeral=True
            )
        except Exception:
            # AFTER a type-6 defer Discord stays SILENT on failure —
            # the King would see nothing at all (his 01/11 live report
            # on the v2 rollout). Surface a visible error note instead.
            logger.warning(
                "KINGDOM LIEUX: objectives picker failed", exc_info=True
            )
            from kingdoms.mods.kingdoms.kingdom_persistent import (
                _market_error_note,
                _strings as _merged_strings,
            )

            await interaction.followup.send(
                _market_error_note(
                    Exception("objectif"), _merged_strings(locale)
                ),
                ephemeral=True,
            )
            return
        # conseil-rafraichi-v1 (Drasah 02/11): a 4th slot carries the
        # EPHEMERAL PARENT back-reference (the council sheet the button
        # sits on) so the validate re-renders it in place. The
        # Discussions ANNOUNCE is a channel message, never an ephemeral
        # parent — no back-reference there.
        _parent = getattr(interaction, "message", None)
        if not bool(
            getattr(getattr(_parent, "flags", None), "ephemeral", False)
        ):
            _parent = None
        _EPHEMERAL_WINDOWS[user_id] = (interaction, monotonic(), window, _parent)


_RANK_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


def _rank_medal(rank: int) -> str:
    """The rank's emoji — the podium medals, 🏰 beyond (axe4, Drasah
    01/11): « Classement : 🥈 2/3 » and the ranking view lines."""
    rank = int(rank or 0)
    if rank in _RANK_MEDALS:
        return _RANK_MEDALS[rank]
    return "🏰" if rank >= 4 else ""


async def _classement_rows(wiring: Any) -> list[tuple[Any, int, int]]:
    """The season ranking rows — (kingdom, territories, alliances),
    sorted territories desc, ties by alliances then tech points (the
    shared engine of the Classement line AND the ranking view)."""
    service = getattr(wiring, "kingdoms_service", None)
    territories_service = getattr(wiring, "territories_service", None)
    if service is None:
        return []
    try:
        kingdoms = [
            item
            for item in await service.kingdoms()
            if not getattr(item, "is_gaia", False)
        ]
        counts: dict[str, int] = {str(item.id): 0 for item in kingdoms}
        if territories_service is not None:
            for territory in await territories_service.territories():
                owner = str(getattr(territory, "owner_kingdom_id", ""))
                if owner in counts:
                    counts[owner] += 1
        rows = [
            (
                item,
                counts[str(item.id)],
                len(getattr(item, "civilizations", []) or []),
            )
            for item in kingdoms
        ]
        rows.sort(
            key=lambda row: (
                -row[1],
                -row[2],
                -int(getattr(row[0], "tech_points_bank", 0) or 0),
            )
        )
        return rows
    except Exception:
        logger.warning("KINGDOM LIEUX: classement rows failed", exc_info=True)
        return []


async def _conseil_rank(wiring: Any, kingdom: Any) -> tuple[int, int]:
    """The kingdom's Classement — territories first, ties broken by
    alliances then technology points (conseil-objectif-v1, Drasah
    01/11). Defensive: (0, 0) renders the line as « — »."""
    rows = await _classement_rows(wiring)
    if not rows:
        return (0, 0)
    ids = [str(getattr(row[0], "id", "")) for row in rows]
    kid = str(getattr(kingdom, "id", ""))
    if kid not in ids:
        return (0, len(ids))
    return (ids.index(kid) + 1, len(ids))


def _classement_content(locale: str, rows: list[tuple[Any, int, int]]) -> str:
    """conseil-objectif-axe3 (Drasah 01/11): the ephemeral Classement —
    one line per kingdom, 🥇🥈🥉 for the podium, 🏰 beyond, a BLANK
    line between the 3rd and the 4th so the podium stands out."""
    lieu = _strings(locale)
    lines = [lieu["classement_title"], ""]
    for index, (kingdom, territories, alliances) in enumerate(rows, start=1):
        if index == 4:
            lines.append("")
        lines.append(
            lieu["classement_line"].format(
                _rank_medal(index),
                index,
                str(getattr(kingdom, "name", "?")),
                territories,
                alliances,
            )
        )
    lines += ["", lieu["conseil_classement_hint"]]
    return "\n".join(lines)


def _classement_view(locale: str) -> discord.ui.View:
    """The Classement view — one 🚪 Sortir that OVERWRITES the window
    with the Entrée hub (exploration-retour-v4, Drasah 02/11 — the old
    plain close left a dead end, the player could not redirect)."""
    lieu = _strings(locale)
    view = discord.ui.View(timeout=None)
    view.add_item(
        _objectif_quit_button(
            lieu, row=0, label=lieu["sortir_button"]
        )
    )
    return view


class KingdomLieuClassementButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdoms:lieux:classement",
):
    """conseil-objectif-axe3 (Drasah 01/11): the 🏆 Classement button of
    the Salle du conseil — line 1, between 🎯 Objectif and 🚪 Sortir.
    Opens the season ranking as an ephemeral window (type-7 ack + a
    followup so the council sheet SURVIVES, coexist), with a 🚪 Sortir
    that simply closes it. Open to every lord of the realm."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id="kingdoms:lieux:classement",
                style=discord.ButtonStyle.primary,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> "KingdomLieuClassementButton":
        """Rebuild from the wire."""
        return cls(_strings(_locale(interaction))["classement_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        from time import monotonic

        from kingdoms.mods.kingdoms.kingdom_persistent import (
            _EPHEMERAL_WINDOWS,
            _close_previous_ephemeral,
            _market_error_note,
            _strings as _merged_strings,
            _wiring,
        )

        locale = _locale(interaction)
        lieu = _strings(locale)
        wiring = _wiring()
        if wiring.kingdoms_service is None:
            await interaction.response.send_message(
                lieu["no_service"], ephemeral=True
            )
            return
        rows = await _classement_rows(wiring)
        if not rows:
            await interaction.response.send_message(
                lieu["classement_empty"], ephemeral=True
            )
            return
        # type-7 ack — the council sheet (an ephemeral parent) survives.
        await interaction.response.defer(ephemeral=True, thinking=True)
        user_id = str(getattr(interaction.user, "id", ""))
        try:
            if _objectif_replaces_previous(_EPHEMERAL_WINDOWS.get(user_id)):
                await _close_previous_ephemeral(user_id)
            window = await interaction.followup.send(
                _classement_content(locale, rows),
                view=_classement_view(locale),
                ephemeral=True,
            )
        except Exception:
            logger.warning(
                "KINGDOM LIEUX: classement window failed", exc_info=True
            )
            await interaction.followup.send(
                _market_error_note(
                    Exception("classement"), _merged_strings(locale)
                ),
                ephemeral=True,
            )
            return
        _EPHEMERAL_WINDOWS[user_id] = (interaction, monotonic(), window)


# ---------------------------------------------------------------------------
# conseil-exploration-v1 (Drasah 01/11) — the 🧭 Exploration action card.
# ---------------------------------------------------------------------------


def _exploration_fiche_content(locale: str) -> str:
    """The fiche body — the card's effect and prerequisite, Drasah's own
    words (the boarding flow itself stays the salon's business)."""
    lieu = _strings(locale)
    return "\n".join(
        [
            f"## {lieu['exploration_fiche_title']}",
            "",
            f"**{lieu['exploration_effect_title']}**",
            lieu["exploration_effect_l1"],
            lieu["exploration_effect_l2"],
            lieu["exploration_effect_l3"],
            lieu["exploration_effect_l4"],
            "",
            f"**{lieu['exploration_prerequis_title']}**",
            lieu["exploration_prerequis"],
        ]
    )


def _exploration_capitaine(
    wiring: Any, kingdom: Any, lord: Any, locale: str
) -> Any:
    """The 🧭 Devenir capitaine callback factory — exploration-refonte-v1
    (Drasah 02/11): the defence point 🛡️ is verified BEFORE anything
    else (``captain_expedition`` checks it first). No eligible clicker →
    NO salon at all, the note « Pré-requis du point de défense possédé
    non respecté » rides alone. On success one click CREATES the 🧭
    exploration salon and enrolls the clicker as CAPITAINE."""

    from time import monotonic

    async def _go(interaction: discord.Interaction) -> None:
        from kingdoms.mods.kingdoms.kingdom_expedition_panel import (
            _map_error,
            _strings as _expe_strings,
            open_expedition_salon_safe,
            refresh_expedition_panel_safe,
            returned_refusal_note_and_view,
        )
        from kingdoms.mods.kingdoms.kingdom_persistent import _EPHEMERAL_WINDOWS

        expe = _expe_strings(locale)
        lieu = _strings(locale)
        user_id = str(getattr(interaction.user, "id", ""))
        # the fiche closes — the note replaces it (the interaction's
        # original response is the fiche window itself).
        await interaction.response.defer(ephemeral=True)
        _EPHEMERAL_WINDOWS.pop(user_id, None)
        try:
            await interaction.delete_original_response()
        except Exception:
            logger.info(
                "KINGDOM LIEUX: exploration fiche close failed (ignored)",
                exc_info=True,
            )
        economy = getattr(wiring, "economy_service", None)
        view = None
        if economy is None:
            note = expe["no_service"]
        else:
            try:
                await economy.captain_expedition(str(kingdom.id), str(lord.id))
            except Exception as exc:
                # the defence point FIRST — no salon opens without it.
                if "defence point" in str(exc):
                    note = lieu["exploration_no_defense"]
                elif "is back" in str(exc):
                    # returned-orphan-soupape-v1 (Drasah 02/11): his
                    # live report — this very flow said « descendez du
                    # navire » with NOWHERE to do it (the salon was
                    # swept, the bubble carried no button). The note
                    # names who is back AND carries the 🪜 unload.
                    doc = {}
                    try:
                        doc = await economy.expedition(str(kingdom.id))
                    except Exception:
                        logger.warning(
                            "KINGDOM LIEUX: returned refusal doc read failed",
                            exc_info=True,
                        )
                    note, view = returned_refusal_note_and_view(expe, doc)
                else:
                    note = _map_error(expe, exc)
            else:
                channel = await open_expedition_salon_safe(
                    interaction.guild, wiring, kingdom
                )
                if channel is None:
                    note = expe["open_failed"]
                else:
                    note = str(expe["open_note"]).format(
                        channel=f"<#{int(channel.id)}>"
                    )
                    try:
                        await refresh_expedition_panel_safe(
                            interaction.guild, wiring, str(kingdom.id)
                        )
                    except Exception:
                        logger.warning(
                            "KINGDOM LIEUX: exploration panel refresh failed",
                            exc_info=True,
                        )
        try:
            message = await interaction.followup.send(
                note, view=view, ephemeral=True
            )
            _EPHEMERAL_WINDOWS[user_id] = (interaction, monotonic(), message)
        except Exception:
            logger.warning(
                "KINGDOM LIEUX: exploration capitaine note failed",
                exc_info=True,
            )

    return _go


def _exploration_fiche_view(
    wiring: Any, kingdom: Any, lord: Any, locale: str
) -> discord.ui.View:
    """The fiche's two buttons — 🧭 Devenir capitaine (green) and
    Annuler (secondary) which closes the window, nothing else."""
    lieu = _strings(locale)
    view = discord.ui.View(timeout=None)
    capitaine = discord.ui.Button(
        label=lieu["exploration_capitaine_button"],
        style=discord.ButtonStyle.success,
        row=0,
    )
    capitaine.callback = _exploration_capitaine(wiring, kingdom, lord, locale)
    annuler = discord.ui.Button(
        label=lieu["exploration_annuler_button"],
        style=discord.ButtonStyle.secondary,
        row=0,
    )
    # Annuler simply closes the fiche — the shared ephemeral exit.
    annuler.callback = _close_ephemeral_window
    view.add_item(capitaine)
    view.add_item(annuler)
    return view


class KingdomLieuExplorationButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdoms:lieux:exploration",
):
    """conseil-exploration-v1 (Drasah 01/11): the 🧭 Exploration action
    card of the Salle du conseil — line 2, green while an Explorateur
    token is held (gray+disabled otherwise, never hidden). The click
    opens the FICHE as the clicker's side window (type-7 ack: the
    council sheet SURVIVES, coexist) — the card's art + its effect +
    its prerequisite, with two buttons: 🧭 Devenir capitaine checks the
    defence point FIRST (no salon on refusal), then CREATES the
    exploration salon and enrolls the clicker as CAPITAINE; Annuler
    closes the window, nothing else."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id="kingdoms:lieux:exploration",
                style=discord.ButtonStyle.primary,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> "KingdomLieuExplorationButton":
        """Rebuild from the wire — THIS module's strings only."""
        return cls(_strings(_locale(interaction))["exploration_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        from time import monotonic

        from kingdoms.mods.kingdoms.kingdom_persistent import (
            _EPHEMERAL_WINDOWS,
            _close_previous_ephemeral,
            _market_card_back_file,
            _market_card_file,
            _market_error_note,
            _strings as _merged_strings,
            _wiring,
        )

        locale = _locale(interaction)
        lieu = _strings(locale)
        wiring = _wiring()
        if wiring.kingdoms_service is None:
            await interaction.response.send_message(
                lieu["no_service"], ephemeral=True
            )
            return
        lord, kingdom = await _require_lord_kingdom(interaction, wiring, lieu)
        if lord is None or kingdom is None:
            return
        # type-7 ack — the council sheet (an ephemeral parent) survives
        # (objectif-coexist-type7-fix lesson).
        await interaction.response.defer(ephemeral=True, thinking=True)
        user_id = str(getattr(interaction.user, "id", ""))
        try:
            content = _exploration_fiche_content(locale)
            view = _exploration_fiche_view(wiring, kingdom, lord, locale)
            # the card's own art rides the fiche (fallback: the back).
            file = _market_card_file("explorateur") or _market_card_back_file()
            files = [file] if file is not None else None
            if _objectif_replaces_previous(_EPHEMERAL_WINDOWS.get(user_id)):
                await _close_previous_ephemeral(user_id)
            window = await interaction.followup.send(
                content, view=view, files=files, ephemeral=True
            )
        except Exception:
            # AFTER a defer Discord stays silent on failure — surface a
            # visible error note instead (the v2-fix lesson).
            logger.warning(
                "KINGDOM LIEUX: exploration fiche failed", exc_info=True
            )
            await interaction.followup.send(
                _market_error_note(
                    Exception("exploration"), _merged_strings(locale)
                ),
                ephemeral=True,
            )
            return
        _EPHEMERAL_WINDOWS[user_id] = (interaction, monotonic(), window)


async def _traquenard_status_lines(locale: str, kingdom: Any, wiring: Any) -> list[str]:
    """traquenard-echelle-v1 (Drasah 03/11): the LIVE Traquenard status
    of the council sheet — a BLANK line, the « 🪤 Traquenard » title,
    then one line per STILL-OPEN Facile window the realm opened
    (``traquenard_uses``), delay in hours+minutes (« 2h05 »); the block
    simply disappears once every window expires."""
    from time import time as _time

    lieu = _strings(locale)
    uses = dict(getattr(kingdom, "traquenard_uses", None) or {})
    now_ts = int(_time())
    live = {
        str(target_id): int(until or 0)
        for target_id, until in uses.items()
        if int(until or 0) > now_ts
    }
    if not live:
        return []
    names: dict[str, str] = {}
    service = getattr(wiring, "kingdoms_service", None)
    if service is not None:
        try:
            for item in await service.kingdoms():
                # kingdom-id-fix (Drasah live report 03/11): the
                # kingdom doc carries ``id`` — ``kingdom_id`` is a
                # LORD field, the lookup never matched.
                kid = str(getattr(item, "id", "") or "")
                if kid in live:
                    names[kid] = str(getattr(item, "name", "") or kid)
        except Exception:
            logger.warning(
                "KINGDOM LIEUX: traquenard status lookup failed (ignored)",
                exc_info=True,
            )
    # traquenard-echelle-v1: delay en heures+minutes (Drasah 03/11 —
    # « 2h05 », plus de <t:…:R> « dans 2 heures »).
    lines = ["", str(lieu["conseil_traquenard_title"])]
    for target_id, until in sorted(live.items()):
        remaining = max(0, int(until) - now_ts)
        lines.append(
            str(lieu["conseil_traquenard_line"]).format(
                names.get(str(target_id), str(target_id)),
                f"{remaining // 3600}h{(remaining % 3600) // 60:02d}",
            )
        )
    return lines


async def build_conseil_view(
    strings: dict[str, Any],
    kingdom: Any,
    state: dict[str, Any],
    wiring: Any,
    locale: str,
    rank: tuple[int, int] = (0, 0),
    viewer_is_king: bool = False,
) -> tuple[Any, list[discord.File]]:
    """The ⚔️ Salle du conseil — the realm's state + action cards.

    conseil-objectif-v2 (Drasah 01/11): the base body is the
    orientation sheet — the intro, the Classement (territories, ties
    broken by alliances then technology points), the
    Trésorerie/Territoires/Alliances line and NOW the 🎯 Objectifs —
    the King's goals, one pipe-separated line, with the targeted
    alliance's blason attached under the panel (they no longer render
    in the Discussions salon). The 🎯 Objectif button rides line 1
    RIGHT of Seigneurie: green for the King, red+disabled for everyone
    else (never hidden).
    """
    import discord

    from kingdoms.mods.kingdoms.kingdom_realm_content import (
        _panel_view_with_buttons,
    )
    from kingdoms.mods.kingdoms.kingdom_persistent import KingdomSeigneurieOpenButton

    lieu = _strings(locale)
    rank_display = (
        f"{_rank_medal(int(rank[0]))} {int(rank[0])}/{int(rank[1])}".strip()
        if int(rank[0] or 0) > 0 and int(rank[1] or 0) > 0
        else "—"
    )
    classement = lieu["conseil_classement"].format(rank_display)
    # conseil-objectif-axe1 (Drasah 01/11): the goal lines ride the sheet
    # ENRICHED — the territory's owner (or « Destination inconnue »),
    # the alliance's marriage lord / acquisition condition (+ mercenary
    # note). Wiring failures keep the plain lines.
    goal_parts = await _objectifs_display_lines(locale, kingdom, wiring)
    objectives = dict(getattr(kingdom, "council_objectives", {}) or {})
    # conseil-objectif-lignes-fix (Drasah 01/11): one goal per line —
    # the pipe-separated line read badly (his live report).
    goals_line = (
        "\n".join(goal_parts) if goal_parts else lieu["conseil_objectifs_none"]
    )
    # traquenard-fiche-v1 (Drasah 03/11): the LIVE Traquenard status —
    # one line per still-open window, right under the Objectifs block.
    traquenard_lines = await _traquenard_status_lines(locale, kingdom, wiring)
    body = "\n".join(
        [
            lieu["conseil_intro_l1"],
            lieu["conseil_intro_l2"],
            lieu["conseil_intro_l3"],
            "",
            classement,
            lieu["conseil_stats"].format(
                int(state.get("wallet", 0) or 0),
                len(state.get("territories") or []),
                len(getattr(kingdom, "civilizations", []) or []),
            ),
            lieu["conseil_classement_hint"],
            "",
            f"## {lieu['conseil_objectifs_title']}",
            goals_line,
            *traquenard_lines,
            "",
            f"## {lieu['conseil_actions']}",
        ]
    )
    purchases = dict(state.get("purchases") or {})
    # lieux-rows-v1 (Drasah 01/11) — the council button RULES:
    # line 1 = the default action (green) + the King's 🎯 Objectif +
    # Sortir (red, last), line 2 = the technology cards, ALWAYS
    # visible — green while held, gray+disabled while out of stock.
    from kingdoms.mods.kingdoms.kingdom_persistent import KingdomTraquenardButton

    row_one = [
        _green(KingdomSeigneurieOpenButton(strings["seigneurie_open_button"])),
        KingdomLieuObjectifButton(lieu["objectif_button"], enabled=viewer_is_king),
        # conseil-objectif-axe3: the Classement rides line 1, between
        # Objectif and Sortir — the ranking is EVERY lord's business.
        KingdomLieuClassementButton(lieu["classement_button"]),
        _sortir(locale),
    ]
    row_two = [
        # conseil-exploration-v1 (Drasah 01/11): the Exploration card
        # opens the FICHE first — the reminder + the effect + the two
        # buttons (🧭 Devenir capitaine / Annuler).
        _stock_style(
            KingdomLieuExplorationButton(lieu["exploration_button"]),
            int(purchases.get("explorateur_stock", 0) or 0) > 0,
        ),
        _stock_style(
            KingdomTraquenardButton(strings),
            int(purchases.get("traquenard", 0) or 0) > 0,
        ),
    ]
    # the targeted alliance's blason rides as a REFERENCED attachment —
    # Components V2 never renders an unreferenced file.
    files = list(_lieu_files("salle du conseil.png", "salle_du_conseil.png"))
    civ_key = str(objectives.get("target_alliance") or "").strip()
    extra_medias: list[str] | None = None
    if civ_key:
        from kingdoms.mods.kingdoms.civ_crests import civ_crest_files

        crest_files = await civ_crest_files([civ_key])
        if crest_files:
            files = files + list(crest_files)
            extra_medias = [f"attachment://{civ_key}.png"]
    view = _panel_view_with_buttons(
        lieu["conseil_title"].format(getattr(kingdom, "name", "")),
        body,
        "kingdoms:realm:view:lieu-conseil",
        discord.Colour.gold(),
        row_one,
        media="attachment://salle_du_conseil.png",
        rows=[row_one, row_two],
        extra_medias=extra_medias,
    )
    return view, files


def _remparts_rows(
    strings: dict[str, Any],
    state: dict[str, Any],
    wiring: Any,
    locale: str,
) -> list[list[Any]]:
    """lieux-rows-v1 — the Remparts button rules (Drasah 01/11).

    Line 1: the default war actions (green) + 🔎 En savoir plus (blue)
    + Sortir (red, last). remparts-boutons-v1 (Drasah 03/11): Line 2 order = Jeu d'armes,
    then ONE 👣 Patrouille cockpit button (it rules BOTH slots),
    Garde Royal last — each green while its stock/unlock is held
    (gray+disabled otherwise). jeu-darmes-bonus-v1 (Drasah 03/11):
    the Jeu d'armes button opens the CONFIRMATION CARD — green when a
    token is HELD (stock > 0), gray+disabled otherwise (the wallet no
    longer rules it).
    """
    from kingdoms.mods.kingdoms.kingdom_attack_panel import (
        KingdomAttackManagerButton,
        KingdomDefenseManagerButton,
    )
    from kingdoms.mods.kingdoms.kingdom_persistent import (
        KingdomRempartsGuardButton,
        KingdomRempartsPatrouilleHubButton,
        KingdomRempartsInfoButton,
        KingdomJeuDarmesUseButton,
    )

    purchases = dict(state.get("purchases") or {})
    row_one = [
        _green(
            KingdomDefenseManagerButton(
                strings.get("defense_manager_button", "🛡️ Gestion de la défense")
            )
        ),
        _green(
            KingdomAttackManagerButton(
                strings.get("attack_manager_button", "⚔️ Gestion d'attaque")
            )
        ),
        # remparts-etats-v1 (Drasah 03/11): the 🔎 En savoir plus button
        # (BLUE primary) between the war actions and Sortir — it swaps
        # the view to its explanations face.
        KingdomRempartsInfoButton(strings),
        _sortir(locale),
    ]
    guard = _stock_style(
        KingdomRempartsGuardButton(strings),
        int(purchases.get("garde_royale_stock", 0) or 0) > 0,
    )
    patrouille_unlocked = any(
        f"patrouille_unlock_{slot_no}" in purchases
        or f"patrouille_slot_{slot_no}" in purchases
        for slot_no in (1, 2)
    )
    patrouille = _stock_style(
        KingdomRempartsPatrouilleHubButton(strings),
        patrouille_unlocked,
    )
    # jeu-darmes-bonus-v1 (Drasah 03/11): the button opens the 🧪
    # confirmation card — green while the kingdom HOLDS a token,
    # gray+disabled otherwise (never hidden, wallet no longer rules).
    jeu = KingdomJeuDarmesUseButton(
        strings, enabled=int(purchases.get("jeu_d_armes_stock", 0) or 0) > 0
    )
    return [row_one, [jeu, patrouille, guard]]



def _remparts_info_rows(
    strings: dict[str, Any], locale: str
) -> list[list[Any]]:
    """remparts-etats-v1: the En savoir plus face — only Compris + Sortir."""
    from kingdoms.mods.kingdoms.kingdom_persistent import KingdomRempartsStateButton

    return [[KingdomRempartsStateButton(strings), _sortir(locale)]]

def _paroisse_rows(
    strings: dict[str, Any],
    kingdom: Any,
    state: dict[str, Any],
    locale: str,
) -> list[list[Any]]:
    """lieux-rows-v1 — the Paroisse button rules (Drasah 01/11).

    Line 1: the parish's default actions (green) + Sortir (red, last).
    Line 2: the 💒 Mariage arrangé card, ALWAYS visible — green from the
    Église palier while a token is held, gray+disabled otherwise.
    """
    from kingdoms.mods.kingdoms.kingdom_realm_content import _church_buttons

    base = _church_buttons(strings, kingdom, state)
    arrange: Any = None
    others: list[Any] = []
    for button in base:
        if str(getattr(button.item, "custom_id", "")) == "kingdoms:church:arrange":
            arrange = button
        else:
            others.append(button)
    row_one: list[Any] = []
    for button in others:
        # The max-palier Améliorer stays disabled (its own convention).
        if not button.item.disabled:
            _green(button)
        row_one.append(button)
    row_one.append(_sortir(locale))
    parish = state.get("parish") or {}
    tier = int(parish.get("tier", 1) or 1)
    stock = int(getattr(kingdom, "arranged_marriage_stock", 0) or 0)
    if arrange is None:
        from kingdoms.mods.kingdoms.kingdom_persistent import (
            KingdomChurchArrangeButton,
        )

        arrange = KingdomChurchArrangeButton(strings, 0)
    _stock_style(arrange, tier >= 2 and stock > 0)
    return [row_one, [arrange]]




def _strip_purchases(content: str, strings: dict[str, Any]) -> str:
    """comptes-rows-v1 (Drasah 01/11): the canary Chambre des comptes
    keeps the balance + the cards in hand ONLY — the purchases section
    moves behind the 📜 Historique achats button."""
    start = content.find(f"## {strings['market_ledger_purchases_title']}")
    cards = content.find(f"## {strings['market_ledger_cards_title']}")
    if start == -1 or cards == -1 or start > cards:
        return content
    return content[:start].rstrip("\n") + "\n\n" + content[cards:]


def _comptes_canary_view(
    body: str,
    strings: dict[str, Any],
    locale: str,
    held: list[tuple[str, str, int]],
    selected_card: str | None = None,
    card_media: str | None = None,
) -> Any:
    """comptes-cv2-v1 (Drasah 05/11): the Chambre des comptes sheet is
    a Components V2 window on the PROVEN remarts gabarit — the chambre
    illustration rides ABOVE the panel (top-level MediaGallery), the
    Container holds the body text, the card image (the dos de carte by
    default, the revealed art while a card is selected) and the
    buttons. Line 1 = 🚀 Utiliser (ONLY while the SELECTED card is a
    usable one) · 📜 Historique achats · ⚔️ Historique actions · 🚪
    Sortir (red) — the card buttons ride the rows below, five per row."""
    from kingdoms.mods.kingdoms.kingdom_persistent import KingdomMarketUseButton

    container: discord.ui.Container[Any] = discord.ui.Container(
        discord.ui.TextDisplay(body),
        accent_colour=discord.Colour.gold(),
    )
    # comptes-cv2-v1: the card image lives INSIDE the container, under
    # the body — the dos de carte (or the revealed art) keeps its own
    # gallery and NEVER sits side by side with the illustration
    # (Drasah 05/11: l'illustration est INTERDITE dans la zone carte,
    # elle vit uniquement en tête de fenêtre).
    if card_media:
        container.add_item(
            discord.ui.MediaGallery(discord.MediaGalleryItem(media=card_media))
        )
    row1: list[Any] = []
    if selected_card is not None and _card_is_usable(selected_card):
        row1.append(KingdomMarketUseButton(selected_card, strings))
    row1.append(KingdomLieuHistButton("achats", strings))
    row1.append(KingdomLieuHistButton("actions", strings))
    row1.append(_sortir(locale))
    rows: list[list[Any]] = [row1]
    current: list[Any] = []
    for key, _line, _stock in held:
        current.append(KingdomLieuCardInfoButton(key, strings))
        if len(current) == 5:
            rows.append(current)
            current = []
    if current:
        rows.append(current)
    for row in rows:
        container.add_item(discord.ui.ActionRow(*row))
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(
        discord.ui.MediaGallery(
            discord.MediaGalleryItem(media="attachment://chambre_des_comptes.png")
        )
    )
    view.add_item(container)
    return view


def _card_is_usable(card: str) -> bool:
    """The cards carrying the 🚀 Utiliser button (chambre-utiliser-v1)."""
    from kingdoms.mods.kingdoms.kingdom_persistent import _MARKET_USABLE_CARDS

    return card in _MARKET_USABLE_CARDS


async def _comptes_canary(
    wiring: Any,
    kingdom: Any,
    strings: dict[str, Any],
    locale: str,
    selected_card: str | None = None,
    extra_text: str | None = None,
) -> tuple[Any, list[Any]]:
    """Build the CANARY Chambre des comptes sheet (comptes-cv2-v1,
    Drasah 05/11): balance + cards in hand only, the purchases and the
    uses living behind their history buttons. Returns (LayoutView,
    files) — the window is a Components V2 message: the chambre
    illustration rides in the TOP gallery (au-dessus de la vue,
    Drasah 05/11), the card image (dos de carte, or the revealed art)
    in the container gallery, the body (+ fiche) text in TextDisplays.
    A CV2 attachment that no component references does NOT render at
    all — every file sent must be referenced by a gallery."""
    from kingdoms.mods.kingdoms.kingdom_persistent import (
        _market_card_back_file,
        _market_card_file,
        _market_ledger_cards,
        _market_ledger_content,
    )

    content, _card_files, _classic_view = await _market_ledger_content(
        wiring, kingdom, strings
    )
    held = await _market_ledger_cards(wiring, str(getattr(kingdom, "id", "")), strings)
    content = _strip_purchases(content, strings)
    if extra_text:
        # keep the v6 blank line between the body and the fiche block
        content = "\n\n".join([content, extra_text])
    # comptes-cv2-v1: the card image keeps its v6 behaviour (Drasah:
    # « la partie carte est bien codée » — dos de carte par défaut,
    # art de la carte sélectionnée à la révélation, pas de retour au
    # dos). The unreferenced held-card arts of the classic sheet no
    # longer travel — the container gallery is the single card image.
    if selected_card is not None:
        card_file = _market_card_file(selected_card) or _market_card_back_file()
    else:
        card_file = _market_card_back_file()
    files: list[Any] = []
    card_media: str | None = None
    if card_file is not None:
        files.append(card_file)
        card_media = f"attachment://{card_file.filename}"
    # The chambre illustration ALWAYS rides along — the top gallery
    # references it (mandatory in CV2).
    files.extend(_lieu_files("chambre des comptes.png", "chambre_des_comptes.png"))
    view = _comptes_canary_view(
        content, strings, locale, held, selected_card, card_media
    )
    return view, files


class KingdomLieuHistButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdoms:lieux:hist:(?P<kind>achats|actions)",
):
    """comptes-rows-v1 (Drasah 01/11): the 📜 Historique achats and ⚔️
    Historique actions buttons of the canary Chambre des comptes — the
    base window keeps the balance + the cards in hand, the histories
    open on click as the player's single ephemeral window (fenêtre
    unique) with the red 🚪 Sortir riding along. Restart-proof."""

    def __init__(
        self, kind: str, strings: dict[str, Any], row: int | None = None
    ) -> None:
        key = (
            "market_hist_achats_button" if kind == "achats" else "market_hist_actions_button"
        )
        super().__init__(
            discord.ui.Button(
                label=str(strings[key])[:80],
                custom_id=f"kingdoms:lieux:hist:{kind}",
                style=discord.ButtonStyle.success,
                row=row,
            )
        )
        self.kind = str(kind)

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> "KingdomLieuHistButton":
        """Rebuild from the wire — THIS module's strings only."""
        return cls(match["kind"], _merged_strings(_locale(interaction)))

    async def callback(self, interaction: discord.Interaction) -> None:
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from kingdoms.mods.kingdoms.kingdom_persistent import (
            _kingdom_by_id_safe,
            _lord_of,
            _market_label,
            _open_unique_ephemeral,
            _strings as _merged,
            _wiring,
        )

        locale = _locale(interaction)
        strings = _merged(locale)
        wiring = _wiring()
        lord = await _lord_of(
            wiring.kingdoms_service, str(interaction.user.id), wiring.bot_admins
        )
        kingdom_id = str(getattr(lord, "kingdom_id", "") or "") if lord else ""
        kingdom = (
            await _kingdom_by_id_safe(wiring.kingdoms_service, kingdom_id)
            if kingdom_id
            else None
        )
        if kingdom is None:
            await interaction.response.send_message(
                strings["church_marry_kingdom_none"], ephemeral=True
            )
            return
        if self.kind == "achats":
            title = str(strings["market_hist_achats_title"])
            registry = list(getattr(kingdom, "market_registry", None) or [])
            if not registry:
                body_lines = [str(strings["market_ledger_empty"])]
            else:
                emojis = strings.get("market_ledger_emoji") or {}
                body_lines = []
                for entry in sorted(
                    registry, key=lambda e: int(e.get("at", 0) or 0), reverse=True
                ):
                    item = str(entry.get("item", ""))
                    at = int(entry.get("at", 0) or 0)
                    when = datetime.fromtimestamp(
                        at, tz=ZoneInfo("Europe/Paris")
                    ).strftime("%d/%m %H:%M")
                    body_lines.append(
                        str(strings["market_ledger_line"]).format(
                            emojis.get(item, "•"),
                            _market_label(item, strings),
                            str(entry.get("detail", "")),
                            int(entry.get("cost", 0) or 0),
                            when,
                        )
                    )
        else:
            title = str(strings["market_hist_actions_title"])
            actions = list(getattr(kingdom, "market_actions", None) or [])
            if not actions:
                body_lines = [str(strings["market_hist_actions_empty"])]
            else:
                emojis = strings.get("market_ledger_emoji") or {}
                body_lines = []
                for entry in sorted(
                    actions, key=lambda e: int(e.get("at", 0) or 0), reverse=True
                ):
                    item = str(entry.get("item", ""))
                    at = int(entry.get("at", 0) or 0)
                    when = datetime.fromtimestamp(
                        at, tz=ZoneInfo("Europe/Paris")
                    ).strftime("%d/%m %H:%M")
                    body_lines.append(
                        str(strings["market_action_line"]).format(
                            emojis.get(item, "•"),
                            _market_label(item, strings),
                            str(entry.get("detail", "")),
                            when,
                        )
                    )
        # comptes-illustration-v1 (Drasah 05/11): the history windows
        # REPLACE the comptes window (fenêtre unique) — they keep the
        # Chambre des comptes illustration in the header so the window
        # never loses its dressing mid-navigation.
        view = discord.ui.LayoutView(timeout=None)
        # comptes-illustration-v2 (Drasah 05/11): the history window now
        # mirrors the PROVEN remarts gabarit — a top-level MediaGallery
        # riding ABOVE a Container holding the title, the body and the
        # Sortir row. The v1 attempt placed BARE top-level TextDisplays
        # and an ActionRow next to the gallery: the API accepted the
        # message but the Discord client refused to render it (live
        # 09:10 — « Le message n'a pas pu être chargé »). Structure-only
        # change: same strings, same behaviour, same asset.
        # NB: MediaGalleryItem is TOP-LEVEL discord.MediaGalleryItem
        # (the deployed discord.py 2.7.1 has no discord.ui variant).
        view.add_item(
            discord.ui.MediaGallery(
                discord.MediaGalleryItem(media="attachment://chambre_des_comptes.png")
            )
        )
        container: discord.ui.Container[Any] = discord.ui.Container(
            discord.ui.TextDisplay(f"# {title}"),
            discord.ui.Separator(),
            discord.ui.TextDisplay("\n".join(body_lines)),
            accent_colour=discord.Colour.gold(),
        )
        container.add_item(discord.ui.ActionRow(_sortir(locale)))
        view.add_item(container)
        await _open_unique_ephemeral(
            interaction,
            view=view,
            files=_lieu_files("chambre des comptes.png", "chambre_des_comptes.png"),
        )


class KingdomLieuCardInfoButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdoms:lieux:cardinfo:(?P<card>[a-z_]+)",
):
    """comptes-rows-v1 (Drasah 01/11): the canary card-reveal button of
    the Chambre des comptes — clicking EDITS the window in place (the
    card's art + Effet + Usage) and line 1 gains the 🚀 Utiliser button
    FIRST while the selected card is a usable one. Mirrors the classic
    KingdomMarketCardInfoButton, never replaces it."""

    def __init__(
        self, card: str, strings: dict[str, Any], row: int | None = None
    ) -> None:
        from kingdoms.mods.kingdoms.kingdom_persistent import _market_label

        label = _market_label(card, strings)
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=f"kingdoms:lieux:cardinfo:{card}",
                style=discord.ButtonStyle.secondary,
                row=row,
            )
        )
        self.card = str(card)

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> "KingdomLieuCardInfoButton":
        """Rebuild from the wire — THIS module's strings only."""
        return cls(match["card"], _merged_strings(_locale(interaction)))

    async def callback(self, interaction: discord.Interaction) -> None:
        from kingdoms.mods.kingdoms.kingdom_persistent import (
            _EPHEMERAL_WINDOWS,
            _kingdom_by_id_safe,
            _lord_of,
            _market_label,
            _strings as _merged,
            _wiring,
        )

        locale = _locale(interaction)
        strings = _merged(locale)
        wiring = _wiring()
        lord = await _lord_of(
            wiring.kingdoms_service, str(interaction.user.id), wiring.bot_admins
        )
        kingdom_id = str(getattr(lord, "kingdom_id", "") or "") if lord else ""
        kingdom = (
            await _kingdom_by_id_safe(wiring.kingdoms_service, kingdom_id)
            if kingdom_id
            else None
        )
        if kingdom is None:
            await interaction.response.send_message(
                strings["church_marry_kingdom_none"], ephemeral=True
            )
            return
        # Type-6 defer on the window's own component: the edit below
        # lands on the ledger window itself (the classic v6 semantics).
        await interaction.response.defer()
        emojis = strings.get("market_ledger_emoji") or {}
        fiche = [
            f"## {emojis.get(self.card, '•')} "
            f"{_market_label(self.card, strings)}",
            str(strings["market_card_effect"]).format(
                (strings.get("market_effect") or {}).get(self.card, "")
            ),
            str(strings["market_card_usage"]).format(
                (strings.get("market_usage") or {}).get(self.card, "")
            ),
        ]
        view, files = await _comptes_canary(
            wiring,
            kingdom,
            strings,
            locale,
            selected_card=self.card,
            extra_text="\n".join(fiche),
        )
        try:
            await interaction.edit_original_response(view=view, attachments=files)
        except Exception:
            # comptes-cv2-v1: PATCHing a CV2 media gallery plus fresh
            # attachments is a known-shaky Discord edit path — fall
            # back to a fresh ephemeral window (the sheet still lands,
            # never a dead click).
            from time import monotonic

            logger.warning(
                "KINGDOM LIEUX: comptes cardinfo edit failed — fresh window",
                exc_info=True,
            )
            window = await interaction.followup.send(
                view=view, files=files, ephemeral=True
            )
            _EPHEMERAL_WINDOWS[str(getattr(interaction.user, "id", ""))] = (
                interaction,
                monotonic(),
                window,
            )


async def _open_comptes(
    interaction: discord.Interaction,
    wiring: Any,
    kingdom: Any,
    strings: dict[str, Any],
    locale: str,
) -> None:
    """The 🏛️ Chambre des comptes — the ledger sheet + illustration.

    comptes-rows-v1 (Drasah 01/11): the CANARY sheet keeps the balance
    + the cards in hand only — the purchases live behind 📜 Historique
    achats, the card uses behind ⚔️ Historique actions, line 1 reads
    [Utiliser (selected usable card) · hist achats · hist actions ·
    Sortir]. Mirrors the ledger button (defer, heavy paint, followup
    window).

    comptes-cv2-v1 (Drasah 05/11): the window is a Components V2
    message — the chambre illustration rides ABOVE the panel, the dos
    de carte (or the revealed art) in its own gallery under the body,
    never side by side with the illustration.
    """
    from time import monotonic

    from kingdoms.mods.kingdoms.kingdom_persistent import (
        _EPHEMERAL_WINDOWS,
        _close_previous_ephemeral,
        _market_error_note,
    )

    await interaction.response.defer(ephemeral=True)
    try:
        view, files = await _comptes_canary(wiring, kingdom, strings, locale)
    except Exception:
        logger.warning("KINGDOM LIEUX: ledger sheet build failed", exc_info=True)
        await interaction.followup.send(
            _market_error_note(Exception("ledger"), strings), ephemeral=True
        )
        return
    user_id = str(getattr(interaction.user, "id", ""))
    await _close_previous_ephemeral(user_id)
    # comptes-cv2-v1: the window is a Components V2 message — no
    # content kwarg (the body lives in the container's TextDisplay).
    window = await interaction.followup.send(
        view=view, files=files, ephemeral=True
    )
    _EPHEMERAL_WINDOWS[user_id] = (interaction, monotonic(), window)


def register_kingdom_lieux_items(bot: discord.Client) -> None:
    """Re-register the lieu hub doors on the bot (restart-proof)."""
    bot.add_dynamic_items(
        KingdomLieuSortirButton,
        KingdomLieuObjectifButton,
        KingdomLieuClassementButton,
        KingdomLieuExplorationButton,
        KingdomLieuHistButton,
        KingdomLieuCardInfoButton,
        KingdomLieuEntreeButton,
        KingdomLieuConseilButton,
        KingdomLieuRempartsButton,
        KingdomLieuComptesButton,
        KingdomLieuParoisseButton,
        KingdomLieuVoliereButton,
    )

