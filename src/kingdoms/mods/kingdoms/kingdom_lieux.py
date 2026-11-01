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
        "conseil_button": "⚔️ Council room",
        "remparts_button": "🧭 Ramparts",
        "comptes_button": "🏛️ Chamber of accounts",
        "paroisse_button": "⛪ Parish",
        "voliere_button": "🏗️ Aviary",
        "not_lord": "Only the lords of this kingdom may enter its places.",
        "no_service": "The Kingdoms service is not wired.",
        "conseil_title": "⚔️ Council room — {0}",
        "conseil_actions": "Action cards",
    },
    "fr": {
        "hub_flavor": (
            "Les portes du château s'ouvrent — chaque lieu du royaume "
            "vit derrière sa porte. L'état du royaume siège en Salle "
            "du conseil."
        ),
        "conseil_button": "⚔️ Salle du conseil",
        "remparts_button": "🧭 Remparts",
        "comptes_button": "🏛️ Chambre des comptes",
        "paroisse_button": "⛪ Paroisse",
        "voliere_button": "🏗️ Volière",
        "not_lord": "Seuls les seigneurs du royaume peuvent entrer dans ses lieux.",
        "no_service": "Le service Kingdoms n'est pas câblé.",
        "conseil_title": "⚔️ Salle du conseil — {0}",
        "conseil_actions": "Cartes d'action",
    },
}


def _strings(locale: str) -> dict[str, str]:
    return STRINGS["fr"] if str(locale).lower().startswith("fr") else STRINGS["en"]


def _locale(interaction: discord.Interaction) -> str:
    return str(interaction.locale) if interaction.locale else "fr"


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
    """The five doors of the canary hub (rows chunk at five upstream)."""
    strings = _strings(locale)
    return [
        KingdomLieuConseilButton(strings["conseil_button"]),
        KingdomLieuRempartsButton(strings["remparts_button"]),
        KingdomLieuComptesButton(strings["comptes_button"]),
        KingdomLieuParoisseButton(strings["paroisse_button"]),
        KingdomLieuVoliereButton(strings["voliere_button"]),
    ]


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
        view, files = build_conseil_view(strings, kingdom, state, wiring, locale)
    elif kind == "remparts":
        view, files = _build_patrol(strings, kingdom, state), _lieu_files(
            "Rempart.png", "rempart.png"
        )
    elif kind == "paroisse":
        view, files = _build_church(strings, kingdom, state), _paroisse_files(state)
    else:  # voliere
        view, files = await _build_voliere(wiring, kingdom, strings)
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
    wiring: Any, kingdom: Any, strings: dict[str, Any]
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
            [],
            media="attachment://voliere.png",
        ),
        _lieu_files("voliere.png", "voliere.png"),
    )


def build_conseil_view(
    strings: dict[str, Any],
    kingdom: Any,
    state: dict[str, Any],
    wiring: Any,
    locale: str,
) -> tuple[Any, list[discord.File]]:
    """The ⚔️ Salle du conseil — the state of the realm + action cards."""
    import discord

    from kingdoms.mods.kingdoms.kingdom_realm_content import (
        _overview_body,
        _panel_view_with_buttons,
    )
    from kingdoms.mods.kingdoms.kingdom_persistent import (
        KingdomMarketTechButton,
        KingdomSeigneurieOpenButton,
        KingdomTraquenardButton,
    )

    lieu = _strings(locale)
    body = "\n".join(
        [
            _overview_body(strings, kingdom, state),
            "",
            f"## {lieu['conseil_actions']}",
        ]
    )
    buttons: list[Any] = [KingdomSeigneurieOpenButton(strings["seigneurie_open_button"])]
    purchases = dict(state.get("purchases") or {})
    # Exploration card: only while the kingdom holds an unused token
    # (the launch consumes it — existing convention, green when present).
    if int(purchases.get("explorateur_stock", 0) or 0) > 0:
        from kingdoms.mods.kingdoms.kingdom_expedition_panel import (
            KingdomExpeditionOpenButton,
            _strings as _expedition_strings,
        )

        buttons.append(
            KingdomExpeditionOpenButton(
                _expedition_strings(locale)["open_button"]
            )
        )
    # Traquenard card: only while the kingdom holds a charge (red style).
    if int(purchases.get("traquenard", 0) or 0) > 0:
        buttons.append(KingdomTraquenardButton(strings))
    # Jeu d'armes card: the Marché buy button, green when affordable,
    # red otherwise (the couleur-convention of the council cards).
    tech_cost = _jeu_d_armes_cost(wiring)
    label = str(strings.get("market_tech", {}).get("jeu_d_armes", "Jeu d'armes"))
    affordable = int(state.get("wallet", 0) or 0) >= tech_cost
    buttons.append(
        KingdomMarketTechButton(
            "jeu_d_armes",
            f"{label} — {tech_cost} ⚙️",
            discord.ButtonStyle.success if affordable else discord.ButtonStyle.danger,
        )
    )
    view = _panel_view_with_buttons(
        lieu["conseil_title"].format(getattr(kingdom, "name", "")),
        body,
        "kingdoms:realm:view:lieu-conseil",
        discord.Colour.gold(),
        buttons,
        media="attachment://salle_du_conseil.png",
    )
    return view, _lieu_files("salle du conseil.png", "salle_du_conseil.png")


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


async def _open_comptes(
    interaction: discord.Interaction,
    wiring: Any,
    kingdom: Any,
    strings: dict[str, Any],
    locale: str,
) -> None:
    """The 🏛️ Chambre des comptes — the ledger sheet + illustration.

    Mirrors the ledger button (defer, heavy paint, followup window)
    with the lieu illustration riding along the card attachments.
    """
    from time import monotonic

    from kingdoms.mods.kingdoms.kingdom_persistent import (
        _EPHEMERAL_WINDOWS,
        _close_previous_ephemeral,
        _market_ledger_content,
    )

    await interaction.response.defer(ephemeral=True)
    try:
        content, card_files, card_info_view = await _market_ledger_content(
            wiring, kingdom, strings
        )
    except Exception:
        logger.warning("KINGDOM LIEUX: ledger sheet build failed", exc_info=True)
        from kingdoms.mods.kingdoms.kingdom_persistent import (
            _market_error_note,
        )

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
        content, files=files, view=card_info_view, ephemeral=True
    )
    _EPHEMERAL_WINDOWS[user_id] = (interaction, monotonic(), window)


def register_kingdom_lieux_items(bot: discord.Client) -> None:
    """Re-register the lieu hub doors on the bot (restart-proof)."""
    bot.add_dynamic_items(
        KingdomLieuConseilButton,
        KingdomLieuRempartsButton,
        KingdomLieuComptesButton,
        KingdomLieuParoisseButton,
        KingdomLieuVoliereButton,
    )
