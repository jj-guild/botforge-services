"""Kingdoms mod — the 🧪 Laboratoire (laboratoire-v1, Drasah 05/11).

Drasah's rule (2026-11-05): a visual-validation lab — ONE admin-only
category « 🧪 Laboratoire » with ONE salon « 🧪 Labo » whose pinned
COCKPIT panel renders the mod's real views in the salon, so every
change is judged BEFORE (or right after) a deployment, without
touching the game salons and without replaying the player flows.

- a MULTI-SELECTION « 🔬 Vues à tester » select — several views checked
  in one open, rendered in sequence (the player-journey order), each
  one labelled — no more one-by-one (Drasah 05/11);
- four one-click PROGRAMMES (presets): 🎞️ Tout dérouler, 🏰 Lieux,
  🃏 Marché & cartes, 🧾 Chantier du jour — the last one is an
  editable constant pointed at the current patch's validation scope;
- a version selector with 📜 Original / 🆕 Version 1 (V2/V3 slots
  reserved) — Version 1 answers « not yet » until a refonte lands;
- 🖼️ Vitrine assets — the live asset inventory (weight + size), the
  hook where the compression before/after pairs will land;
- 🧹 Nettoyer — sweeps the bot's vitrine messages, the cockpit spared.

INDEPENDENCE (Drasah's key rule): every render rides the Nilrem test
kingdom's data (read-only), posts in the Labo salon ONLY, and the
rendered components are NEUTRALIZED (every button/select disabled) —
the vitrine is a maquette, not a clone: nothing can be consumed,
clicked or written from the lab. Every label is rebuilt from THIS
module's strings at ``from_custom_id`` time (the Check 30 lesson).
"""
from __future__ import annotations

import logging
import re
import struct
from pathlib import Path
from typing import Any

import discord

from kingdoms.mods.kingdoms.panel_messages import (
    NO_MENTIONS,
    channel_messages,
    message_text,
)

logger = logging.getLogger("kingdoms.kingdom_lab")

LAB_CHANNEL_SLUG = "labo"
LAB_PANEL_MARKER = "kingdoms:lab:cockpit"

STRINGS: dict[str, dict[str, str]] = {
    "fr": {
        "cockpit_title": "🧪 Laboratoire — cockpit de validation visuelle",
        "cockpit_intro": (
            "Choisis les vues à tester ci-dessous (plusieurs choix possibles), "
            "ou clique un programme. Chaque vue est rendue dans CE salon à partir "
            "du royaume test **Nilrem** — aucune interaction n'est possible, "
            "aucun salon de jeu n'est touché.\n"
            "• 📜 **Original** = le rendu du code déployé (l'unique version pour l'instant)\n"
            "• 🧹 **Nettoyer** efface les vitrines (ce panel survit)"
        ),
        "select_placeholder": "🔬 Vues à tester (choix multiples)",
        "preset_all": "🎞️ Tout dérouler",
        "preset_lieux": "🏰 Lieux",
        "preset_marche": "🃏 Marché & cartes",
        "preset_chantier": "🧾 Chantier du jour",
        "vitrine_button": "🖼️ Vitrine assets",
        "clean_button": "🧹 Nettoyer",
        "refresh_button": "♻️ Actualiser",
        "version_placeholder": "Version à afficher",
        "version_original": "📜 Original",
        "version_v1": "🆕 Version 1",
        "not_allowed": "Le Laboratoire est réservé aux admins.",
        "no_service": "Le service Kingdoms n'est pas câblé.",
        "no_channel": "Le salon 🧪 Labo est introuvable — relance 🚀 Déployer.",
        "no_test_kingdom": (
            "Le royaume test **Nilrem** est introuvable — crée-le avec le bouton "
            "🧪 du Distributeur, puis relance."
        ),
        "version_unavailable": (
            "ℹ️ Aucune Version 1 en attente — 📜 Original est le rendu du code déployé."
        ),
        "version_original_note": (
            "ℹ️ Original est le rendu actif — les vues rendues l'utilisent déjà."
        ),
        "posted": "✅ {count} vue(s) rendue(s) dans le salon Labo{errors}.",
        "posted_errors": " — échecs : {keys}",
        "vitrine_title": "🖼️ Vitrine des assets",
        "vitrine_intro": (
            "Inventaire en direct des illustrations (poids · dimensions). "
            "Les paires Original | Version 1 s'afficheront ici dès la "
            "recompression validée."
        ),
        "vitrine_missing": "⚠️ Le dossier d'assets est introuvable sur ce déploiement.",
        "cleaned": "🧹 {count} message(s) supprimé(s) — le cockpit est conservé.",
        "clean_none": "🧹 Rien à nettoyer.",
        "failed": "⚠️ L'action Laboratoire a échoué : `{error}`.",
        "view_hub": "🏰 Le-Royaume — hub château",
        "view_conseil": "⚔️ Salle du conseil",
        "view_remparts": "🧭 Remparts",
        "view_comptes": "🏛️ Chambre des comptes",
        "view_paroisse": "⛪ Paroisse",
        "view_voliere": "🏗️ Volière",
        "view_territoire": "🗺️ Territoire",
        "view_alliances": "🤝 Alliances",
        "view_marche": "💰 Marché",
        "view_taverne": "🍺 Taverne",
    },
    "en": {
        "cockpit_title": "🧪 Laboratory — visual validation cockpit",
        "cockpit_intro": (
            "Pick the views to test below (multiple choices allowed), or click "
            "a programme. Every view renders in THIS channel from the **Nilrem** "
            "test kingdom — no interaction is possible, no game channel is "
            "touched.\n"
            "• 📜 **Original** = the deployed code's render (the only version for now)\n"
            "• 🧹 **Clean** sweeps the showcases (this panel survives)"
        ),
        "select_placeholder": "🔬 Views to test (multiple choice)",
        "preset_all": "🎞️ Unroll everything",
        "preset_lieux": "🏰 Places",
        "preset_marche": "🃏 Market & cards",
        "preset_chantier": "🧾 Today's work",
        "vitrine_button": "🖼️ Asset showcase",
        "clean_button": "🧹 Clean",
        "refresh_button": "♻️ Refresh",
        "version_placeholder": "Version to display",
        "version_original": "📜 Original",
        "version_v1": "🆕 Version 1",
        "not_allowed": "The Laboratory is admin-only.",
        "no_service": "The Kingdoms service is not wired.",
        "no_channel": "The 🧪 Lab channel is missing — run 🚀 Deploy again.",
        "no_test_kingdom": (
            "The **Nilrem** test kingdom is missing — create it with the "
            "Distributor's 🧪 button, then retry."
        ),
        "version_unavailable": (
            "ℹ️ No Version 1 pending — 📜 Original is the deployed code's render."
        ),
        "version_original_note": (
            "ℹ️ Original is the active render — the rendered views already use it."
        ),
        "posted": "✅ {count} view(s) rendered in the Lab channel{errors}.",
        "posted_errors": " — failures: {keys}",
        "vitrine_title": "🖼️ Asset showcase",
        "vitrine_intro": (
            "Live inventory of the illustrations (weight · size). The Original | "
            "Version 1 pairs will render here once the recompression is approved."
        ),
        "vitrine_missing": "⚠️ The asset folder is missing on this deployment.",
        "cleaned": "🧹 {count} message(s) deleted — the cockpit is kept.",
        "clean_none": "🧹 Nothing to clean.",
        "failed": "⚠️ The Laboratory action failed: `{error}`.",
        "view_hub": "🏰 The-Realm — castle hub",
        "view_conseil": "⚔️ Council room",
        "view_remparts": "🧭 Ramparts",
        "view_comptes": "🏛️ Chamber of accounts",
        "view_paroisse": "⛪ Parish",
        "view_voliere": "🏗️ Aviary",
        "view_territoire": "🗺️ Territory",
        "view_alliances": "🤝 Alliances",
        "view_marche": "💰 Market",
        "view_taverne": "🍺 Tavern",
    },
}


def _strings(locale: Any) -> dict[str, str]:
    lang = "fr" if locale is None or str(locale).startswith("fr") else "en"
    return STRINGS[lang]


def _locale(interaction: discord.Interaction) -> str:
    locale = getattr(interaction, "locale", None)
    return "fr" if locale is None or str(locale).startswith("fr") else "en"


# The renderable views, in the player-journey order (Drasah 05/11: the
# multi-selection renders in THIS sequence so the salon reads like a
# walkthrough).
LAB_VIEWS: tuple[str, ...] = (
    "hub",
    "conseil",
    "remparts",
    "comptes",
    "paroisse",
    "voliere",
    "territoire",
    "alliances",
    "marche",
    "taverne",
)

LAB_PRESETS: dict[str, tuple[str, ...]] = {
    "all": LAB_VIEWS,
    "lieux": ("hub", "conseil", "remparts", "comptes", "paroisse", "voliere"),
    "marche": ("marche",),
    # laboratoire-v1: EDITABLE — point this at the current patch's
    # validation scope (currently the comptes-cv2 beta). Update the
    # tuple at each patch, never the cockpit code.
    "chantier": ("comptes", "hub", "marche"),
}

_LIEUX_ASSETS = Path(__file__).resolve().parent / "assets" / "lieux"
_MARCHE_ASSETS = Path(__file__).resolve().parent / "assets" / "marche"


def _find_lab_channel(guild: discord.Guild | None) -> Any | None:
    """Find the 🧪 Labo salon by its decoration-blind slug (read-only)."""
    from kingdoms.mods.kingdoms.kingdom_setup import _slug

    if guild is None:
        return None
    for channel in getattr(guild, "text_channels", []) or []:
        if _slug(getattr(channel, "name", "")) == LAB_CHANNEL_SLUG:
            return channel
    return None


def _disable_every_interactive(item: Any) -> None:
    """Neutralize one component subtree — nothing in the lab is clickable.

    Walks the LayoutView children tree (ActionRow, Container, Section
    accessory) and flips ``disabled`` on every Button/Select, including
    DynamicItem-wrapped ones. The vitrine keeps its exact look, but no
    lab render can ever consume, open or write anything.
    """
    for target in (item, getattr(item, "item", None)):
        if isinstance(target, (discord.ui.Button, discord.ui.Select)):
            try:
                target.disabled = True
            except Exception:
                logger.warning("KINGDOM LAB: neutralize failed", exc_info=True)
    for child in getattr(item, "children", None) or []:
        _disable_every_interactive(child)


def neutralize_view(view: Any) -> None:
    """Neutralize a whole LayoutView (the lab renders are maquettes)."""
    for child in getattr(view, "children", None) or []:
        _disable_every_interactive(child)


def _label_header(key: str, locale: str) -> discord.ui.TextDisplay:
    return discord.ui.TextDisplay(f"## {_strings(locale)[f'view_{key}']}")


async def _build_lieu_window_lab(
    key: str, wiring: Any, kingdom: Any, strings: dict[str, Any], locale: str
) -> tuple[Any, list[Any] | None]:
    """Build the Comptes / Volière lab windows (lieux ephemeral builders)."""
    if key == "comptes":
        from kingdoms.mods.kingdoms.kingdom_lieux import _comptes_canary

        return await _comptes_canary(wiring, kingdom, strings, locale)
    from kingdoms.mods.kingdoms.kingdom_lieux import _build_voliere

    return await _build_voliere(wiring, kingdom, strings, locale)


def _build_remparts_lab(
    strings: dict[str, Any], wiring: Any, kingdom: Any, state: dict[str, Any], locale: str
) -> tuple[Any, list[Any] | None]:
    """Build the Remparts lab view (illustration attached)."""
    from kingdoms.mods.kingdoms.kingdom_lieux import _lieu_files, _remparts_rows
    from kingdoms.mods.kingdoms.kingdom_realm_content import _build_patrol

    view = _build_patrol(
        strings,
        kingdom,
        state,
        media="attachment://rempart.png",
        rows=_remparts_rows(strings, state, wiring, locale),
    )
    return view, (_lieu_files("Rempart.png", "rempart.png") or None)


def _build_paroisse_lab(
    strings: dict[str, Any], kingdom: Any, state: dict[str, Any], locale: str
) -> tuple[Any, list[Any] | None]:
    """Build the Paroisse lab view (palier illustration attached)."""
    from kingdoms.mods.kingdoms.kingdom_lieux import _paroisse_files, _paroisse_rows
    from kingdoms.mods.kingdoms.kingdom_realm_content import _build_church

    view = _build_church(
        strings,
        kingdom,
        state,
        media="attachment://paroisse.png",
        rows=_paroisse_rows(strings, kingdom, state, locale),
    )
    return view, (_paroisse_files(state) or None)


async def _build_alliances_lab(
    strings: dict[str, Any], kingdom: Any, state: dict[str, Any]
) -> tuple[Any, list[Any] | None]:
    """Build the Alliances lab view (crest mosaic attached)."""
    from kingdoms.mods.kingdoms.civ_crests import civ_crest_mosaic_file
    from kingdoms.mods.kingdoms.kingdom_realm_content import _build_alliances_panel

    view = _build_alliances_panel(strings, kingdom, state)
    ledger = dict(getattr(kingdom, "civilization_acquisitions", None) or {})
    hand = [str(civ) for civ in getattr(kingdom, "civilizations", []) or []]
    mosaic = await civ_crest_mosaic_file(
        [
            (
                civ,
                (ledger.get(civ) or {}).get("origin") or "",
                state.get("civ_names", {}).get(civ, civ),
            )
            for civ in hand
        ]
    )
    return view, ([mosaic] if mosaic is not None else None)


async def _build_marche_lab(locale: str, wiring: Any) -> tuple[Any, list[Any] | None]:
    """Build the Marché lab view (the merchant banner attached)."""
    from kingdoms.mods.kingdoms.kingdom_panels import build_market_panel
    from kingdoms.mods.kingdoms.marche_art import banner_file

    banner = banner_file()
    banner_filename = (
        f"marche_banner{banner.suffix.lower()}" if banner is not None else None
    )
    view = await build_market_panel(
        locale, getattr(wiring, "kingdoms_service", None), banner_filename
    )
    if banner is None:
        return view, None
    return view, [discord.File(str(banner), filename=banner_filename)]


def _build_taverne_lab(locale: str) -> tuple[Any, list[Any] | None]:
    """Build the Taverne lab view (text sheet, no drinks clickable)."""
    from kingdoms.mods.kingdoms.kingdom_tavern_panel import build_tavern_content

    view = discord.ui.LayoutView(timeout=None)
    view.add_item(discord.ui.TextDisplay(build_tavern_content(locale)))
    return view, None


def _build_hub_lab(
    strings: dict[str, Any], kingdom: Any, state: dict[str, Any]
) -> tuple[Any, list[Any] | None]:
    """Build the castle-hub lab view (illustration attached)."""
    from kingdoms.mods.kingdoms.kingdom_lieux import hub_file
    from kingdoms.mods.kingdoms.kingdom_realm_content import _build_overview

    view = _build_overview(strings, kingdom, state)
    castle = hub_file()
    return view, ([castle] if castle is not None else None)


async def _build_conseil_lab(
    strings: dict[str, Any],
    kingdom: Any,
    state: dict[str, Any],
    wiring: Any,
    locale: str,
) -> tuple[Any, list[Any] | None]:
    """Build the council lab view (the admin reads it as the king)."""
    from kingdoms.mods.kingdoms.kingdom_lieux import _conseil_rank, build_conseil_view

    return await build_conseil_view(
        strings,
        kingdom,
        state,
        wiring,
        locale,
        rank=await _conseil_rank(wiring, kingdom),
        # the admin pilots Nilrem as its king (kingdom-test-v1).
        viewer_is_king=True,
    )


async def _build_lab_view(
    key: str,
    locale: str,
    wiring: Any,
    kingdom: Any,
    state: dict[str, Any],
) -> tuple[Any, list[Any] | None]:
    """Build ONE lab view through the real mod builders (read-only)."""
    from kingdoms.mods.kingdoms.kingdom_persistent import _strings as _merged_strings

    strings = _merged_strings(locale)
    if key == "hub":
        return _build_hub_lab(strings, kingdom, state)
    if key == "conseil":
        return await _build_conseil_lab(strings, kingdom, state, wiring, locale)
    if key == "remparts":
        return _build_remparts_lab(strings, wiring, kingdom, state, locale)
    if key in ("comptes", "voliere"):
        return await _build_lieu_window_lab(key, wiring, kingdom, strings, locale)
    if key == "paroisse":
        return _build_paroisse_lab(strings, kingdom, state, locale)
    if key == "territoire":
        from kingdoms.mods.kingdoms.kingdom_realm_content import (
            _build_territory,
            _build_territory_pending,
            _season_phase,
        )

        phase = await _season_phase(getattr(wiring, "kingdoms_service", None))
        builder = _build_territory if phase != "setup" else _build_territory_pending
        return builder(strings, kingdom, state), None
    if key == "alliances":
        return await _build_alliances_lab(strings, kingdom, state)
    if key == "marche":
        return await _build_marche_lab(locale, wiring)
    if key == "taverne":
        return _build_taverne_lab(locale)
    raise KeyError(key)


async def _test_kingdom(wiring: Any) -> Any | None:
    """Resolve the Nilrem test kingdom READ-ONLY (the lab never creates)."""
    service = getattr(wiring, "kingdoms_service", None)
    if service is None:
        return None
    from kingdoms.mods.kingdoms.service import TEST_KINGDOM_ID

    kingdoms = await service.kingdoms()
    return next(
        (k for k in kingdoms if str(getattr(k, "id", "")) == TEST_KINGDOM_ID), None
    )


async def render_lab_views(
    channel: Any,
    locale: str,
    wiring: Any,
    kingdom: Any,
    keys: list[str],
) -> tuple[int, list[str]]:
    """Render the selected views into the Labo salon (each one a fresh message)."""
    from kingdoms.mods.kingdoms.kingdom_realm_content import _gather_state

    state = await _gather_state(kingdom, wiring)
    rendered = 0
    failures: list[str] = []
    for key in keys:
        if key not in LAB_VIEWS:
            continue
        try:
            view, files = await _build_lab_view(key, locale, wiring, kingdom, state)
            neutralize_view(view)
            # the étiquette rides FIRST (the walkthrough reads in order) —
            # ``children`` returns a copy, so the view is rebuilt around it.
            try:
                children = list(view.children)
                view.clear_items()
                view.add_item(_label_header(key, locale))
                for child in children:
                    view.add_item(child)
            except Exception:
                logger.warning("KINGDOM LAB: label header insert failed", exc_info=True)
            await channel.send(
                view=view,
                **({"files": files} if files else {}),
                allowed_mentions=NO_MENTIONS,
            )
            rendered += 1
        except Exception:
            logger.warning("KINGDOM LAB: view %s render failed", key, exc_info=True)
            failures.append(key)
    return rendered, failures


def _png_size(path: Path) -> str:
    """Read a PNG's IHDR dimensions without any image library."""
    try:
        with path.open("rb") as handle:
            head = handle.read(24)
        if head[:8] == b"\x89PNG\r\n\x1a\n" and len(head) >= 24:
            width, height = struct.unpack(">II", head[16:24])
            return f"{width}×{height}"
    except Exception:
        logger.warning("KINGDOM LAB: png size read failed", exc_info=True)
    return "—"


def _inventory_lines() -> list[str]:
    """Return the live asset inventory (lieux illustrations + market cards)."""
    lines: list[str] = []
    for base, label in ((_LIEUX_ASSETS, "lieux"), (_MARCHE_ASSETS, "marché")):
        if not base.is_dir():
            continue
        for path in sorted(base.glob("*.png")):
            lines.append(
                f"• `{path.name}` — {path.stat().st_size / 1024:.0f} Ko · {_png_size(path)} ({label})"
            )
    return lines


async def _guard(interaction: discord.Interaction, locale: str) -> Any | None:
    """Admin gate + wiring — returns the wiring or answers and returns None."""
    from kingdoms.mods.kingdoms.kingdom_persistent import _is_admin, _wiring

    strings = _strings(locale)
    wiring = _wiring()
    if not _is_admin(interaction, wiring.bot_admins):
        await interaction.response.send_message(strings["not_allowed"], ephemeral=True)
        return None
    return wiring


async def _render_and_report(
    interaction: discord.Interaction,
    locale: str,
    keys: list[str],
) -> None:
    """Deferred render path: Nilrem data → Labo salon → summary answer."""
    strings = _strings(locale)
    wiring = await _guard(interaction, locale)
    if wiring is None:
        return
    await interaction.response.defer(ephemeral=True)
    channel = _find_lab_channel(getattr(interaction, "guild", None))
    if channel is None:
        await interaction.followup.send(strings["no_channel"], ephemeral=True)
        return
    if getattr(wiring, "kingdoms_service", None) is None:
        await interaction.followup.send(strings["no_service"], ephemeral=True)
        return
    try:
        kingdom = await _test_kingdom(wiring)
    except Exception as exc:
        await interaction.followup.send(
            strings["failed"].format(error=getattr(exc, "message", None) or exc),
            ephemeral=True,
        )
        return
    if kingdom is None:
        await interaction.followup.send(strings["no_test_kingdom"], ephemeral=True)
        return
    rendered, failures = await render_lab_views(channel, locale, wiring, kingdom, keys)
    errors = ""
    if failures:
        errors = strings["posted_errors"].format(keys=", ".join(failures))
    await interaction.followup.send(
        strings["posted"].format(count=rendered, errors=errors), ephemeral=True
    )


class _LabPresetButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]], template=r"kingdoms:lab:preset:(\w+)"
):
    """A one-click programme — a frozen list of views, rendered in order."""

    def __init__(self, preset: str, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=f"kingdoms:lab:preset:{preset}",
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
    ) -> _LabPresetButton:
        """Rebuild from the wire — THIS module's strings only."""
        preset = match.group(1)
        key = {
            "all": "preset_all",
            "lieux": "preset_lieux",
            "marche": "preset_marche",
            "chantier": "preset_chantier",
        }.get(preset, "preset_all")
        return cls(preset, _strings(_locale(interaction))[key])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Render the preset's views (deferred, one summary answer)."""
        preset = re.search(r"kingdoms:lab:preset:(\w+)$", self.item.custom_id or "")
        keys = list(LAB_PRESETS.get(preset.group(1) if preset else "all", LAB_VIEWS))
        await _render_and_report(interaction, _locale(interaction), keys)


class KingdomLabViewSelect(
    discord.ui.DynamicItem[discord.ui.Select], template=r"kingdoms:lab:views"
):
    """The multi-selection « vues à tester » — several views in one open."""

    def __init__(self, locale: str) -> None:
        strings = _strings(locale)
        options = [
            discord.SelectOption(label=strings[f"view_{key}"][:100], value=key)
            for key in LAB_VIEWS
        ]
        super().__init__(
            discord.ui.Select(
                options=options,
                custom_id="kingdoms:lab:views",
                placeholder=strings["select_placeholder"],
                min_values=1,
                max_values=len(options),
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> KingdomLabViewSelect:
        """Rebuild from the wire — THIS module's strings only."""
        return cls(_locale(interaction))

    async def callback(self, interaction: discord.Interaction) -> None:
        """Render every selected view, journey-ordered (deferred)."""
        keys = [v for v in list(self.item.values or []) if v in LAB_VIEWS]
        # the salon reads in the player-journey order whatever the order
        # the clicks happened in (Drasah 05/11).
        keys = [k for k in LAB_VIEWS if k in keys] or list(LAB_VIEWS)
        await _render_and_report(interaction, _locale(interaction), keys)


class KingdomLabVersionSelect(
    discord.ui.DynamicItem[discord.ui.Select], template=r"kingdoms:lab:version"
):
    """The version selector — Original now, the V2/V3 slots reserved."""

    def __init__(self, locale: str) -> None:
        strings = _strings(locale)
        super().__init__(
            discord.ui.Select(
                options=[
                    discord.SelectOption(
                        label=strings["version_original"], value="original", default=True
                    ),
                    discord.SelectOption(label=strings["version_v1"], value="v1"),
                ],
                custom_id="kingdoms:lab:version",
                placeholder=strings["version_placeholder"],
                min_values=1,
                max_values=1,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> KingdomLabVersionSelect:
        """Rebuild from the wire — THIS module's strings only."""
        return cls(_locale(interaction))

    async def callback(self, interaction: discord.Interaction) -> None:
        """Answer the version question (Original is the only one for now)."""
        strings = _strings(_locale(interaction))
        value = (list(self.item.values or []) or ["original"])[0]
        if value == "v1":
            await interaction.response.send_message(
                strings["version_unavailable"], ephemeral=True
            )
            return
        await interaction.response.send_message(
            strings["version_original_note"], ephemeral=True
        )


class KingdomLabVitrineButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]], template=r"kingdoms:lab:vitrine"
):
    """The 🖼️ asset showcase — the live inventory (compression pairs later)."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id="kingdoms:lab:vitrine",
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
    ) -> KingdomLabVitrineButton:
        """Rebuild from the wire — THIS module's strings only."""
        return cls(_strings(_locale(interaction))["vitrine_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Post the asset inventory in the Labo salon (admin-only)."""
        from kingdoms.mods.kingdoms.kingdom_persistent import _is_admin, _wiring

        locale = _locale(interaction)
        strings = _strings(locale)
        wiring = _wiring()
        if not _is_admin(interaction, wiring.bot_admins):
            await interaction.response.send_message(
                strings["not_allowed"], ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        channel = _find_lab_channel(getattr(interaction, "guild", None))
        if channel is None:
            await interaction.followup.send(strings["no_channel"], ephemeral=True)
            return
        lines = _inventory_lines()
        view = discord.ui.LayoutView(timeout=None)
        if not lines:
            view.add_item(discord.ui.TextDisplay(strings["vitrine_missing"]))
        else:
            view.add_item(discord.ui.TextDisplay(f"## {strings['vitrine_title']}"))
            view.add_item(discord.ui.TextDisplay(strings["vitrine_intro"]))
            view.add_item(discord.ui.TextDisplay("\n".join(lines)))
        await channel.send(view=view, allowed_mentions=NO_MENTIONS)
        await interaction.followup.send(
            strings["posted"].format(count=1, errors=""), ephemeral=True
        )


class KingdomLabCleanButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]], template=r"kingdoms:lab:clean"
):
    """The 🧹 sweep — the bot's vitrine messages go, the cockpit stays."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id="kingdoms:lab:clean",
                style=discord.ButtonStyle.danger,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> KingdomLabCleanButton:
        """Rebuild from the wire — THIS module's strings only."""
        return cls(_strings(_locale(interaction))["clean_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Sweep the bot's vitrine messages, the cockpit spared."""
        from kingdoms.mods.kingdoms.kingdom_persistent import _is_admin, _wiring

        locale = _locale(interaction)
        strings = _strings(locale)
        wiring = _wiring()
        if not _is_admin(interaction, wiring.bot_admins):
            await interaction.response.send_message(
                strings["not_allowed"], ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        channel = _find_lab_channel(getattr(interaction, "guild", None))
        if channel is None:
            await interaction.followup.send(strings["no_channel"], ephemeral=True)
            return
        deleted = 0
        client_user = getattr(getattr(interaction, "client", None), "user", None)
        bot_id = getattr(client_user, "id", None)
        for message in await channel_messages(channel):
            if LAB_PANEL_MARKER in message_text(message):
                continue
            author_id = getattr(getattr(message, "author", None), "id", None)
            if author_id is not None and bot_id is not None and author_id != bot_id:
                continue
            try:
                await message.delete()
                deleted += 1
            except Exception:
                logger.warning("KINGDOM LAB: message delete failed", exc_info=True)
        if deleted:
            await interaction.followup.send(
                strings["cleaned"].format(count=deleted), ephemeral=True
            )
        else:
            await interaction.followup.send(strings["clean_none"], ephemeral=True)


class KingdomLabRefreshButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]], template=r"kingdoms:lab:refresh"
):
    """The ♻️ refresh — the cockpit re-renders in place after a deploy."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id="kingdoms:lab:refresh",
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
    ) -> KingdomLabRefreshButton:
        """Rebuild from the wire — THIS module's strings only."""
        return cls(_strings(_locale(interaction))["refresh_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        """Re-render the cockpit in place (edit, the panel stays pinned)."""
        locale = _locale(interaction)
        strings = _strings(locale)
        try:
            await interaction.response.edit_message(view=build_lab_cockpit(locale))
        except Exception:
            logger.warning("KINGDOM LAB: cockpit refresh edit failed", exc_info=True)
            await interaction.response.send_message(
                strings["failed"].format(error="refresh"), ephemeral=True
            )


def build_lab_cockpit(locale: str) -> discord.ui.LayoutView:
    """Build the pinned cockpit LayoutView (no send — pure builder)."""
    strings = _strings(locale)
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(discord.ui.TextDisplay(f"## {strings['cockpit_title']}"))
    view.add_item(discord.ui.TextDisplay(strings["cockpit_intro"]))
    view.add_item(
        discord.ui.ActionRow(
            _LabPresetButton("all", strings["preset_all"]),
            _LabPresetButton("lieux", strings["preset_lieux"]),
            _LabPresetButton("marche", strings["preset_marche"]),
            _LabPresetButton("chantier", strings["preset_chantier"]),
        )
    )
    view.add_item(KingdomLabViewSelect(locale))
    view.add_item(KingdomLabVersionSelect(locale))
    view.add_item(
        discord.ui.ActionRow(
            KingdomLabVitrineButton(strings["vitrine_button"]),
            KingdomLabCleanButton(strings["clean_button"]),
            KingdomLabRefreshButton(strings["refresh_button"]),
        )
    )
    view.add_item(discord.ui.TextDisplay(f"-# ||{LAB_PANEL_MARKER}||"))
    return view


async def deploy_lab_panel(guild: discord.Guild | None, locale: str) -> bool:
    """Pin (or edit in place) the cockpit in the 🧪 Labo salon (idempotent)."""
    channel = _find_lab_channel(guild)
    if channel is None:
        return False
    view = build_lab_cockpit(locale)
    marked: list[Any] = []
    try:
        marked = [
            message
            for message in await channel_messages(channel)
            if LAB_PANEL_MARKER in message_text(message)
        ]
    except Exception:
        logger.warning("KINGDOM LAB: cockpit scan failed", exc_info=True)
    if marked:
        for duplicate in marked[1:]:
            try:
                await duplicate.delete()
            except Exception:
                logger.warning(
                    "KINGDOM LAB: cockpit duplicate purge failed", exc_info=True
                )
        try:
            await marked[0].edit(view=view)
            return True
        except Exception:
            logger.warning("KINGDOM LAB: cockpit edit failed, resending", exc_info=True)
    try:
        message = await channel.send(view=view, allowed_mentions=NO_MENTIONS)
        try:
            await message.pin()
        except Exception:
            logger.warning("KINGDOM LAB: cockpit pin failed", exc_info=True)
        return True
    except Exception:
        logger.warning("KINGDOM LAB: cockpit send failed", exc_info=True)
        return False


def register_kingdom_lab_items(bot: discord.Client) -> None:
    """Re-register every lab component on the bot (restart-proof)."""
    bot.add_dynamic_items(
        _LabPresetButton,
        KingdomLabViewSelect,
        KingdomLabVersionSelect,
        KingdomLabVitrineButton,
        KingdomLabCleanButton,
        KingdomLabRefreshButton,
    )
