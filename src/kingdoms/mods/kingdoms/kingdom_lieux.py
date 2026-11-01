"""Kingdoms mod — lieux-et-conseil-v1 (Drasah 01/11): the realm hub.

The Le-Royaume refonte: the pinned sheet becomes a CASTLE hub — the
stats move into the ⚔️ Salle du conseil, every place opens as an
ephemeral view with its illustration, and nothing else changes for the
players until the gate opens.

canary-gate-v1: the whole refonte renders ONLY for the kingdom ids
listed below (THE DECLARATION WINS — never a live-state derivation,
leçon divider-gating-v2). During the beta: Nilrem alone. Removing the
id from the list (empty tuple) generalises to every kingdom.

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
# Empty the tuple (or delete the ids) to generalise — no other change.
CANARY_REALM_KINGDOM_IDS: tuple[str, ...] = ("k-nilrem",)

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
        "remparts_button": "🧭 Ramparts",
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
            "**Treasury** : {0} ⚙️ · **Territories** : {1} · **Alliances** : {2}"
        ),
        "objectif_button": "🎯 Objective",
        "objectif_king_only": "🎯 Reserved to the King of the realm.",
        "objectif_modal_title": "🎯 Kingdom objectives",
        "objectif_kingdom_label": "⚔️ Kingdom to strike first",
        "objectif_territory_label": "🗺️ Territory you seek",
        "objectif_alliance_label": "🤝 Alliance you covet",
        "objectif_placeholder": "Leave empty to leave undefined",
        "objectif_saved": (
            "🎯 Objectives updated — they now guide the lords in the"
            " realm's salon."
        ),
        "objectif_view_title": "🎯 Kingdom objectives — {0}",
        "objectif_kingdom_line": "⚔️ Priority kingdom : **{0}**",
        "objectif_territory_line": "🗺️ Territory sought : **{0}**",
        "objectif_alliance_line": "🤝 Alliance wanted : **{0}**",
        "objectif_empty_line": (
            "No objective set yet — the King may define them from the"
            " Council room."
        ),
        "objectif_footer": "-# Indicative objectives set by the King.",
        "conseil_actions": "Action cards",
        "sortir_button": "🚪 Leave",
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
        "remparts_button": "🧭 Remparts",
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
            "**Trésorerie** : {0} ⚙️ · **Territoires** : {1} · **Alliances** : {2}"
        ),
        "objectif_button": "🎯 Objectif",
        "objectif_king_only": "🎯 Réservé au Roi du royaume.",
        "objectif_modal_title": "🎯 Objectifs du royaume",
        "objectif_kingdom_label": "⚔️ Royaume à attaquer en priorité",
        "objectif_territory_label": "🗺️ Territoire recherché",
        "objectif_alliance_label": "🤝 Alliance souhaitée",
        "objectif_placeholder": "Laisser vide pour ne pas définir",
        "objectif_saved": (
            "🎯 Objectifs mis à jour — ils orientent désormais les seigneurs"
            " dans le salon du royaume."
        ),
        "objectif_view_title": "🎯 Objectifs du royaume — {0}",
        "objectif_kingdom_line": "⚔️ Royaume prioritaire : **{0}**",
        "objectif_territory_line": "🗺️ Territoire recherché : **{0}**",
        "objectif_alliance_line": "🤝 Alliance recherchée : **{0}**",
        "objectif_empty_line": (
            "Aucun objectif fixé pour le moment — le Roi peut en définir"
            " depuis la Salle du conseil."
        ),
        "objectif_footer": "-# Objectifs indicatifs fixés par le Roi.",
        "conseil_actions": "Cartes d'action",
        "sortir_button": "🚪 Sortir",
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
    """True when the kingdom renders the new hub (the gate decides)."""
    return kingdom is not None and str(getattr(kingdom, "id", "")) in CANARY_REALM_KINGDOM_IDS


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
        view, files = build_conseil_view(
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


class KingdomObjectifModal(discord.ui.Modal):
    """The King's goal sheet (conseil-objectif-v1, Drasah 01/11).

    Three free INDICATIVE fields — a priority kingdom, a sought
    territory, a wanted alliance. An empty field leaves the goal
    undefined; re-opening the modal always shows the current values
    so the King modifies the choice at will.
    """

    def __init__(
        self,
        strings: dict[str, str],
        wiring: Any,
        kingdom: Any,
    ) -> None:
        super().__init__(title=str(strings["objectif_modal_title"])[:45], timeout=None)
        self._strings = strings
        self._wiring = wiring
        self._kingdom = kingdom
        objectives = dict(getattr(kingdom, "council_objectives", {}) or {})
        self.target_kingdom = discord.ui.TextInput(
            label=str(strings["objectif_kingdom_label"])[:45],
            style=discord.TextStyle.short,
            max_length=100,
            required=False,
            default=str(objectives.get("target_kingdom") or "") or None,
            placeholder=str(strings["objectif_placeholder"]),
        )
        self.target_territory = discord.ui.TextInput(
            label=str(strings["objectif_territory_label"])[:45],
            style=discord.TextStyle.short,
            max_length=100,
            required=False,
            default=str(objectives.get("target_territory") or "") or None,
            placeholder=str(strings["objectif_placeholder"]),
        )
        self.target_alliance = discord.ui.TextInput(
            label=str(strings["objectif_alliance_label"])[:45],
            style=discord.TextStyle.short,
            max_length=100,
            required=False,
            default=str(objectives.get("target_alliance") or "") or None,
            placeholder=str(strings["objectif_placeholder"]),
        )
        for field in (
            self.target_kingdom,
            self.target_territory,
            self.target_alliance,
        ):
            self.add_item(field)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        from time import time

        kingdom = self._kingdom
        objectives: dict[str, Any] = {
            "target_kingdom": str(self.target_kingdom.value or "").strip(),
            "target_territory": str(self.target_territory.value or "").strip(),
            "target_alliance": str(self.target_alliance.value or "").strip(),
            "updated_at": int(time()),
        }
        try:
            kingdom.council_objectives = objectives
            service = getattr(self._wiring, "kingdoms_service", None)
            if service is not None and hasattr(service, "save_kingdom"):
                await service.save_kingdom(kingdom)
        except Exception:
            logger.warning("KINGDOM LIEUX: objectives save failed", exc_info=True)
            await interaction.response.send_message(
                self._strings["no_service"], ephemeral=True
            )
            return
        guild = getattr(interaction, "guild", None)
        if guild is not None:
            try:
                await deploy_objectives_safe(guild, kingdom, self._wiring)
            except Exception:
                logger.warning(
                    "KINGDOM LIEUX: objectives salon refresh failed",
                    exc_info=True,
                )
        await interaction.response.send_message(
            self._strings["objectif_saved"], ephemeral=True
        )


class KingdomLieuObjectifButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdoms:lieux:objectif",
):
    """conseil-objectif-v1 (Drasah 01/11): the King's 🎯 Objectif button
    of the Salle du conseil — line 1, RIGHT of Seigneurie. The King
    sets the realm's INDICATIVE goals through a modal; they are
    injected into the realm's council salon to orient the lords, and a
    re-click re-opens the modal so the choice is always modifiable.
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
        from kingdoms.mods.kingdoms.kingdom_persistent import (
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
        await interaction.response.send_modal(
            KingdomObjectifModal(lieu, wiring, kingdom)
        )


async def _conseil_rank(wiring: Any, kingdom: Any) -> tuple[int, int]:
    """The kingdom's Classement — territories first, ties broken by
    alliances then technology points (conseil-objectif-v1, Drasah
    01/11). Defensive: (0, 0) renders the line as « — »."""
    service = getattr(wiring, "kingdoms_service", None)
    territories_service = getattr(wiring, "territories_service", None)
    if service is None:
        return (0, 0)
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

        def _sort_key(item: Any) -> tuple[int, int, int]:
            return (
                -counts[str(item.id)],
                -len(getattr(item, "civilizations", []) or []),
                -int(getattr(item, "tech_points_bank", 0) or 0),
            )

        ordered = sorted(kingdoms, key=_sort_key)
        ids = [str(item.id) for item in ordered]
        kid = str(getattr(kingdom, "id", ""))
        if kid not in ids:
            return (0, len(ids))
        return (ids.index(kid) + 1, len(ids))
    except Exception:
        logger.warning("KINGDOM LIEUX: council rank failed", exc_info=True)
        return (0, 0)


def build_objectives_view(kingdom: Any, locale: str) -> Any:
    """The 🎯 objectifs message of the realm's council salon — the
    King's indicative goals, marker-keyed so the upsert edits it in
    place (conseil-objectif-v1, Drasah 01/11)."""
    import discord

    lieu = _strings(locale)
    objectives = dict(getattr(kingdom, "council_objectives", {}) or {})
    kingdom_goal = str(objectives.get("target_kingdom") or "").strip()
    territory_goal = str(objectives.get("target_territory") or "").strip()
    alliance_goal = str(objectives.get("target_alliance") or "").strip()
    lines: list[str] = [
        f"# {lieu['objectif_view_title'].format(getattr(kingdom, 'name', ''))}"
    ]
    lines.append("")
    if not any((kingdom_goal, territory_goal, alliance_goal)):
        lines.append(lieu["objectif_empty_line"])
    else:
        if kingdom_goal:
            lines.append(lieu["objectif_kingdom_line"].format(kingdom_goal))
        if territory_goal:
            lines.append(lieu["objectif_territory_line"].format(territory_goal))
        if alliance_goal:
            lines.append(lieu["objectif_alliance_line"].format(alliance_goal))
    lines.append("")
    lines.append(lieu["objectif_footer"])
    lines.append("-# kingdoms:realm:view:objectifs")
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(
        discord.ui.Container(
            discord.ui.TextDisplay("\n".join(lines)),
            accent_colour=discord.Colour.gold(),
        )
    )
    return view


def _objectives_salon(category: Any) -> Any | None:
    """Resolve the council salon of a realm category — the canary
    « discussions » name first, the legacy « salle du conseil » second."""
    from kingdoms.mods.kingdoms.kingdom_setup import _slug

    for slug in ("discussions", "salle-du-conseil"):
        for channel in getattr(category, "channels", []) or []:
            if _slug(str(getattr(channel, "name", ""))) == slug:
                return channel
    return None


async def deploy_objectives_safe(
    guild: Any,
    kingdom: Any,
    wiring: Any,
    locale: str = "fr",
) -> bool:
    """Best-effort upsert of the 🎯 objectifs message into the realm's
    council salon (edit-in-place like every realm view, never a
    duplicate). The wiring seam keeps the signature future-proof."""
    from kingdoms.mods.kingdoms.kingdom_realm_content import _upsert_view
    from kingdoms.mods.kingdoms.kingdom_realms import _find_realm_category

    if guild is None:
        return False
    category = _find_realm_category(guild, getattr(kingdom, "name", ""))
    if category is None:
        return False
    channel = _objectives_salon(category)
    if channel is None:
        return False
    return await _upsert_view(
        channel, "objectifs", build_objectives_view(kingdom, locale)
    )


def build_conseil_view(
    strings: dict[str, Any],
    kingdom: Any,
    state: dict[str, Any],
    wiring: Any,
    locale: str,
    rank: tuple[int, int] = (0, 0),
    viewer_is_king: bool = False,
) -> tuple[Any, list[discord.File]]:
    """The ⚔️ Salle du conseil — the realm's state + action cards.

    conseil-objectif-v1 (Drasah 01/11): the base body becomes the
    orientation sheet — the intro (what the council is for), the
    Classement (territories, ties broken by alliances then technology
    points) and the Trésorerie/Territoires/Alliances line. The 🎯
    Objectif button rides line 1 RIGHT of Seigneurie: green for the
    King, red+disabled for everyone else (never hidden).
    """
    import discord

    from kingdoms.mods.kingdoms.kingdom_realm_content import (
        _panel_view_with_buttons,
    )
    from kingdoms.mods.kingdoms.kingdom_persistent import KingdomSeigneurieOpenButton

    lieu = _strings(locale)
    classement = lieu["conseil_classement"].format(
        f"{int(rank[0])}/{int(rank[1])}"
        if int(rank[0] or 0) > 0 and int(rank[1] or 0) > 0
        else "—"
    )
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
            f"## {lieu['conseil_actions']}",
        ]
    )
    purchases = dict(state.get("purchases") or {})
    # lieux-rows-v1 (Drasah 01/11) — the council button RULES:
    # line 1 = the default action (green) + the King's 🎯 Objectif +
    # Sortir (red, last), line 2 = the technology cards, ALWAYS
    # visible — green while held, gray+disabled while out of stock.
    from kingdoms.mods.kingdoms.kingdom_expedition_panel import (
        KingdomExpeditionOpenButton,
        _strings as _expedition_strings,
    )
    from kingdoms.mods.kingdoms.kingdom_persistent import KingdomTraquenardButton

    row_one = [
        _green(KingdomSeigneurieOpenButton(strings["seigneurie_open_button"])),
        KingdomLieuObjectifButton(lieu["objectif_button"], enabled=viewer_is_king),
        _sortir(locale),
    ]
    row_two = [
        _stock_style(
            KingdomExpeditionOpenButton(_expedition_strings(locale)["open_button"]),
            int(purchases.get("explorateur_stock", 0) or 0) > 0,
        ),
        _stock_style(
            KingdomTraquenardButton(strings),
            int(purchases.get("traquenard", 0) or 0) > 0,
        ),
    ]
    view = _panel_view_with_buttons(
        lieu["conseil_title"].format(getattr(kingdom, "name", "")),
        body,
        "kingdoms:realm:view:lieu-conseil",
        discord.Colour.gold(),
        row_one,
        media="attachment://salle_du_conseil.png",
        rows=[row_one, row_two],
    )
    return view, _lieu_files("salle du conseil.png", "salle_du_conseil.png")


def _remparts_rows(
    strings: dict[str, Any],
    state: dict[str, Any],
    wiring: Any,
    locale: str,
) -> list[list[Any]]:
    """lieux-rows-v1 — the Remparts button rules (Drasah 01/11).

    Line 1: the default war actions (green) + Sortir (red, last).
    Line 2: the placement + card buttons — Garde / Patrouille 1 / 2
    green while their stock/unlock is held (gray+disabled otherwise)
    and the Jeu d'armes card, green while affordable, gray otherwise.
    """
    from kingdoms.mods.kingdoms.kingdom_attack_panel import (
        KingdomAttackManagerButton,
        KingdomDefenseManagerButton,
    )
    from kingdoms.mods.kingdoms.kingdom_persistent import (
        KingdomMarketTechButton,
        KingdomRempartsGuardButton,
        KingdomRempartsPatrouilleButton,
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
        _sortir(locale),
    ]
    guard = _stock_style(
        KingdomRempartsGuardButton(strings),
        int(purchases.get("garde_royale_stock", 0) or 0) > 0,
    )
    patrols = []
    for slot_no in (1, 2):
        patrols.append(
            _stock_style(
                KingdomRempartsPatrouilleButton(slot_no, strings),
                f"patrouille_unlock_{slot_no}" in purchases
                or f"patrouille_slot_{slot_no}" in purchases,
            )
        )
    # Jeu d'armes lives HERE now (Drasah 01/11): the card activates on
    # the Ramparts — green while the treasury affords it, gray+disabled
    # otherwise (never hidden).
    tech_cost = _jeu_d_armes_cost(wiring)
    label = str(strings.get("market_tech", {}).get("jeu_d_armes", "Jeu d'armes"))
    jeu = KingdomMarketTechButton(
        "jeu_d_armes", f"{label} — {tech_cost} ⚙️", discord.ButtonStyle.success
    )
    if int(state.get("wallet", 0) or 0) < tech_cost:
        _gray(jeu)
    return [row_one, [guard, *patrols, jeu]]


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


def _jeu_d_armes_cost(wiring: Any) -> int:
    """The configured Jeu d'armes cost (default ladder if unwired)."""
    try:
        technologies = getattr(getattr(wiring, "kingdoms_service", None), "config", None)
        technologies = getattr(technologies, "technologies", None)
        if technologies is not None:
            return int(getattr(technologies, "jeu_d_armes"))
    except Exception:
        pass
    from kingdoms.mods.kingdoms.config import TechnologyCosts

    return int(getattr(TechnologyCosts(), "jeu_d_armes"))


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
    strings: dict[str, Any],
    locale: str,
    held: list[tuple[str, str, int]],
    selected_card: str | None = None,
) -> Any:
    """Line 1 of the canary comptes view: 🚀 Utiliser (ONLY while the
    SELECTED card is a usable one) · 📜 Historique achats · ⚔️
    Historique actions · 🚪 Sortir (red) — the card buttons ride the
    rows below, five per row."""
    from kingdoms.mods.kingdoms.kingdom_persistent import KingdomMarketUseButton

    view = discord.ui.View(timeout=None)
    if selected_card is not None and _card_is_usable(selected_card):
        view.add_item(KingdomMarketUseButton(selected_card, strings, row=0))
    view.add_item(KingdomLieuHistButton("achats", strings, row=0))
    view.add_item(KingdomLieuHistButton("actions", strings, row=0))
    view.add_item(_sortir(locale, row=0))
    for offset, (key, _line, _stock) in enumerate(held):
        view.add_item(KingdomLieuCardInfoButton(key, strings, row=1 + offset // 5))
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
) -> tuple[str, list[Any], Any]:
    """Build the CANARY Chambre des comptes sheet (comptes-rows-v1):
    balance + cards in hand only, the canary line-1 view, the purchases
    and the uses living behind their history buttons."""
    from kingdoms.mods.kingdoms.kingdom_persistent import (
        _market_ledger_cards,
        _market_ledger_content,
    )

    content, card_files, _classic_view = await _market_ledger_content(
        wiring, kingdom, strings
    )
    held = await _market_ledger_cards(wiring, str(getattr(kingdom, "id", "")), strings)
    content = _strip_purchases(content, strings)
    view = _comptes_canary_view(strings, locale, held, selected_card)
    return content, list(card_files or []), view


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
        view = discord.ui.LayoutView(timeout=None)
        view.add_item(discord.ui.TextDisplay(f"# {title}"))
        view.add_item(discord.ui.TextDisplay("\n".join(body_lines)))
        view.add_item(discord.ui.ActionRow(_sortir(locale)))
        await _open_unique_ephemeral(interaction, view=view)


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
            _kingdom_by_id_safe,
            _lord_of,
            _market_card_back_file,
            _market_card_file,
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
        content, _files, view = await _comptes_canary(
            wiring, kingdom, strings, locale, selected_card=self.card
        )
        emojis = strings.get("market_ledger_emoji") or {}
        fiche = [
            "",
            f"## {emojis.get(self.card, '•')} "
            f"{_market_label(self.card, strings)}",
            str(strings["market_card_effect"]).format(
                (strings.get("market_effect") or {}).get(self.card, "")
            ),
            str(strings["market_card_usage"]).format(
                (strings.get("market_usage") or {}).get(self.card, "")
            ),
        ]
        file = _market_card_file(self.card) or _market_card_back_file()
        files = [file] if file is not None else []
        await interaction.edit_original_response(
            content="\n".join([content, *fiche]),
            attachments=files,
            view=view,
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
    window) with the lieu illustration riding along the attachments.
    """
    from time import monotonic

    from kingdoms.mods.kingdoms.kingdom_persistent import (
        _EPHEMERAL_WINDOWS,
        _close_previous_ephemeral,
        _market_error_note,
    )

    await interaction.response.defer(ephemeral=True)
    try:
        content, card_files, view = await _comptes_canary(
            wiring, kingdom, strings, locale
        )
    except Exception:
        logger.warning("KINGDOM LIEUX: ledger sheet build failed", exc_info=True)
        await interaction.followup.send(
            _market_error_note(Exception("ledger"), strings), ephemeral=True
        )
        return
    files = list(card_files or []) + _lieu_files(
        "chambre des comptes.png", "chambre_des_comptes.png"
    )
    user_id = str(getattr(interaction.user, "id", ""))
    await _close_previous_ephemeral(user_id)
    window = await interaction.followup.send(
        content, files=files, view=view, ephemeral=True
    )
    _EPHEMERAL_WINDOWS[user_id] = (interaction, monotonic(), window)


def register_kingdom_lieux_items(bot: discord.Client) -> None:
    """Re-register the lieu hub doors on the bot (restart-proof)."""
    bot.add_dynamic_items(
        KingdomLieuSortirButton,
        KingdomLieuObjectifButton,
        KingdomLieuHistButton,
        KingdomLieuCardInfoButton,
        KingdomLieuEntreeButton,
        KingdomLieuConseilButton,
        KingdomLieuRempartsButton,
        KingdomLieuComptesButton,
        KingdomLieuParoisseButton,
        KingdomLieuVoliereButton,
    )
