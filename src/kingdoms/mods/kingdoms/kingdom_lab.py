"""Kingdoms mod — the 🧪 Laboratoire (laboratoire-v2, Drasah 05/11).

Drasah's rule (2026-11-05): a visual-validation lab — ONE admin-only
category « 🧪 Laboratoire » with THREE salons:

- 🧪 labo — the COCKPIT: a dropdown of the tests to run (each entry
  says WHAT to test and WHY — the « chantier » entry is the editable
  per-patch scope) and, after every test, a TEST CARD carrying the
  feedback panel: ✅ Valider · ✏️ Modifier · ❌ Annuler. Drasah checks
  BEFORE confirming to Mistral — the work resumes from his verdict and
  his written remarks (laboratoire-v2, Drasah 05/11);
- 📜 original — the renders of the DEPLOYED code (the reference);
- 🚧 travaux — the renders of the WORK-IN-PROGRESS version. The first
  real variant is LIVE (Drasah 05/11): every attached asset rides the
  MEDIANCUT-256 recompression (``kingdom_lab_compress`` — pure stdlib,
  best-effort decline to the original bytes); the variant seam lives in
  ``_build_lab_view`` + ``render_lab_views`` (variant="travaux").

A test DISPATCHES its render into BOTH salons at once — the
side-by-side comparison Drasah asked for. The verdicts are stateless:
the test key rides the button custom_id, each verdict freezes its
card in labo and logs a dedicated INFO line (« KINGDOM LAB: test …
VALIDATED / MODIFIED (remarks) / CANCELLED ») retrievable via /logs.
🧹 Nettoyer sweeps the two render salons — the cockpit and the verdict
cards are kept.

INDEPENDENCE (Drasah's key rule): every render rides the Nilrem test
kingdom's data (read-only), and the rendered components are NEUTRALIZED
(every button/select disabled) — the vitrine is a maquette, not a
clone: nothing can be consumed, clicked or written from the lab. Every
label is rebuilt from THIS module's strings at ``from_custom_id``
time (the Check 30 lesson).
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
LAB_ORIGINAL_SLUG = "original"
LAB_TRAVAUX_SLUG = "travaux"
LAB_PANEL_MARKER = "kingdoms:lab:cockpit"

STRINGS: dict[str, dict[str, str]] = {
    "fr": {
        "cockpit_title": "🧪 Laboratoire — poste de validation des versions",
        "cockpit_intro": (
            "Choisis le test à lancer ci-dessous — le rendu est **dispatché dans "
            "les deux salons** : 📜 **original** (code déployé) et 🚧 **travaux** "
            "(version en cours), à comparer côte à côte.\n"
            "Une **fiche de test** apparaît ici après chaque envoi : "
            "✅ **Valider** · ✏️ **Modifier** (avec tes remarques) · "
            "❌ **Annuler** — Mistral reprend le travail depuis ton verdict.\n"
            "• Données du royaume test **Nilrem**, lecture seule — aucun salon de jeu n'est touché.\n"
            "• 🧹 **Nettoyer** vide les deux salons de rendus (ce cockpit et tes fiches sont conservés)."
        ),
        "test_placeholder": "🧪 Que veux-tu tester ?",
        "test_tout": "🎞️ Tout le parcours",
        "test_why_tout": "Le parcours joueur complet, de bout en bout",
        "test_lieux": "🏰 Lieux",
        "test_why_lieux": "Hub, conseil, remparts, comptes, paroisse, volière",
        "test_marche": "🃏 Marché & cartes",
        "test_why_marche": "Le panneau du marché et la bannière marchand",
        "test_chantier": "🧾 Chantier du jour",
        "test_why_chantier": "EDITABLE — le scope du patch en cours : comptes, hub, marché",
        "vitrine_button": "🖼️ Vitrine assets",
        "clean_button": "🧹 Nettoyer",
        "refresh_button": "♻️ Actualiser",
        "not_allowed": "Le Laboratoire est réservé aux admins.",
        "no_service": "Le service Kingdoms n'est pas câblé.",
        "no_channel": "Le salon 🧪 Labo est introuvable — relance 🚀 Déployer.",
        "no_render_channel": (
            "Le salon {channel} est introuvable — relance 🚀 Déployer pour "
            "provisionner le laboratoire complet."
        ),
        "no_test_kingdom": (
            "Le royaume test **Nilrem** est introuvable — crée-le avec le bouton "
            "🧪 du Distributeur, puis relance."
        ),
        "dispatched": "✅ {count} vue(s) rendue(s) dans 📜 original et 🚧 travaux{errors}.",
        "posted_errors": " — échecs : {keys}",
        "card_title": "🧪 Test : {title}",
        "card_dispatched": (
            "→ rendu dispatché dans 📜 **original** et 🚧 **travaux** — "
            "compare côte à côte, puis tranche :"
        ),
        "verdict_validate": "✅ Valider",
        "verdict_modify": "✏️ Modifier",
        "verdict_cancel": "❌ Annuler",
        "verdict_validated": (
            "✅ **Version validée.** Tu peux la confirmer à Mistral "
            "(« ok version validée ») — le travail reprend à partir de ce verdict."
        ),
        "verdict_modified": "📝 **Version à modifier** — remarques enregistrées :",
        "verdict_cancelled": (
            "🗄️ **Version annulée** — mise de côté (archivée, consultable ici)."
        ),
        "remarks_title": "Remarques sur la version travaux",
        "remarks_label": "Écris tes remarques — elles seront enregistrées avec le test",
        "remarks_done": "📝 Remarques enregistrées.",
        "vitrine_posted": "✅ Vitrine affichée dans le salon Labo.",
        "vitrine_title": "🖼️ Vitrine des assets",
        "vitrine_intro": (
            "Inventaire en direct des illustrations (poids · dimensions) avec la "
            "recompression MEDIANCUT 256 en cours de validation — chaque ligne "
            "montre la paire déployé → travaux (−gain %) quand elle est calculée."
        ),
        "travaux_label": "🚧 version en travaux — recompression MEDIANCUT 256",
        "vitrine_missing": "⚠️ Le dossier d'assets est introuvable sur ce déploiement.",
        "cleaned": (
            "🧹 {count} message(s) supprimé(s) dans 📜 original et 🚧 travaux — "
            "le cockpit et tes fiches sont conservés."
        ),
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
        "cockpit_title": "🧪 Laboratory — version validation station",
        "cockpit_intro": (
            "Pick the test to run below — the render is DISPATCHED into both "
            "channels: 📜 **original** (the deployed code) and 🚧 **work in "
            "progress**, side by side.\n"
            "A **test card** appears here after every dispatch: "
            "✅ **Validate** · ✏️ **Modify** (with your remarks) · "
            "❌ **Cancel** — Mistral resumes the work from your verdict.\n"
            "• Data from the **Nilrem** test kingdom, read-only — no game channel is touched.\n"
            "• 🧹 **Clean** empties the two render channels (this cockpit and your cards are kept)."
        ),
        "test_placeholder": "🧪 What do you want to test?",
        "test_tout": "🎞️ Whole walkthrough",
        "test_why_tout": "The complete player journey, end to end",
        "test_lieux": "🏰 Places",
        "test_why_lieux": "Hub, council, ramparts, accounts, parish, aviary",
        "test_marche": "🃏 Market & cards",
        "test_why_marche": "The market panel and the merchant banner",
        "test_chantier": "🧾 Today's work",
        "test_why_chantier": "EDITABLE — the current patch's scope: accounts, hub, market",
        "vitrine_button": "🖼️ Asset showcase",
        "clean_button": "🧹 Clean",
        "refresh_button": "♻️ Refresh",
        "not_allowed": "The Laboratory is admin-only.",
        "no_service": "The Kingdoms service is not wired.",
        "no_channel": "The 🧪 Lab channel is missing — run 🚀 Deploy again.",
        "no_render_channel": (
            "The {channel} channel is missing — run 🚀 Deploy again to "
            "provision the full laboratory."
        ),
        "no_test_kingdom": (
            "The **Nilrem** test kingdom is missing — create it with the "
            "Distributor's 🧪 button, then retry."
        ),
        "dispatched": "✅ {count} view(s) rendered into 📜 original and 🚧 travaux{errors}.",
        "posted_errors": " — failures: {keys}",
        "card_title": "🧪 Test: {title}",
        "card_dispatched": (
            "→ render dispatched into 📜 **original** and 🚧 **work in "
            "progress** — compare side by side, then decide:"
        ),
        "verdict_validate": "✅ Validate",
        "verdict_modify": "✏️ Modify",
        "verdict_cancel": "❌ Cancel",
        "verdict_validated": (
            "✅ **Version validated.** Confirm it to Mistral "
            "(“ok version validated”) — the work resumes from this verdict."
        ),
        "verdict_modified": "📝 **Version to modify** — remarks recorded:",
        "verdict_cancelled": (
            "🗄️ **Version cancelled** — set aside (archived, readable here)."
        ),
        "remarks_title": "Remarks on the work-in-progress version",
        "remarks_label": "Write your remarks — they will be recorded with the test",
        "remarks_done": "📝 Remarks recorded.",
        "vitrine_posted": "✅ Showcase rendered in the Lab channel.",
        "vitrine_title": "🖼️ Asset showcase",
        "vitrine_intro": (
            "Live inventory of the illustrations (weight · size) with the MEDIANCUT-256 "
            "recompression under validation — each line shows the deployed → travaux "
            "pair (−gain %) once computed."
        ),
        "travaux_label": "🚧 work-in-progress version — MEDIANCUT-256 recompression",
        "vitrine_missing": "⚠️ The asset folder is missing on this deployment.",
        "cleaned": (
            "🧹 {count} message(s) deleted in 📜 original and 🚧 travaux — "
            "the cockpit and your cards are kept."
        ),
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


# The renderable views, in the player-journey order (the walkthrough
# reads like the game).
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

# laboratoire-v2 (Drasah 05/11): the dropdown's test registry — WHAT
# to test and WHY, each entry dispatching its views into BOTH salons.
LAB_TEST_ITEMS: dict[str, dict[str, Any]] = {
    "tout": {
        "title_key": "test_tout",
        "why_key": "test_why_tout",
        "views": list(LAB_VIEWS),
    },
    "lieux": {
        "title_key": "test_lieux",
        "why_key": "test_why_lieux",
        "views": ["hub", "conseil", "remparts", "comptes", "paroisse", "voliere"],
    },
    "marche": {
        "title_key": "test_marche",
        "why_key": "test_why_marche",
        "views": ["marche"],
    },
    # laboratoire-v2: EDITABLE — the per-patch validation scope. Point
    # ``views`` at the surfaces the current patch touches and say WHY in
    # ``test_why_chantier`` — update both at each patch, never the code.
    "chantier": {
        "title_key": "test_chantier",
        "why_key": "test_why_chantier",
        "views": ["comptes", "hub", "marche"],
    },
}

_LIEUX_ASSETS = Path(__file__).resolve().parent / "assets" / "lieux"
_MARCHE_ASSETS = Path(__file__).resolve().parent / "assets" / "marche"


def _find_lab_channel(guild: discord.Guild | None, slug: str = LAB_CHANNEL_SLUG) -> Any | None:
    """Find a lab salon by its decoration-blind slug (read-only)."""
    from kingdoms.mods.kingdoms.kingdom_setup import _slug

    if guild is None:
        return None
    for channel in getattr(guild, "text_channels", []) or []:
        if _slug(getattr(channel, "name", "")) == slug:
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


def _label_header(key: str, locale: str, variant: str = "original") -> discord.ui.TextDisplay:
    """The view's étiquette — travaux renders say WHAT the variant is."""
    strings = _strings(locale)
    title = f"## {strings[f'view_{key}']}"
    if variant == "travaux":
        title += f"\n-# {strings['travaux_label']}"
    return discord.ui.TextDisplay(title)


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
    variant: str = "original",
) -> tuple[Any, list[Any] | None]:
    """Build ONE lab view through the real mod builders (read-only).

    laboratoire-v2 (Drasah 05/11): ``variant`` is the ORIGINAL/TRAVAUX
    seam — « original » renders the deployed code, « travaux » renders
    the work-in-progress version. No optimization is pending yet, so
    « travaux » rides the very same builders today; the first real
    variant (the asset recompression) will branch here without
    touching any other code.
    """
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
    variant: str = "original",
) -> tuple[int, list[str]]:
    """Render the selected views into a salon (each one a fresh message)."""
    from kingdoms.mods.kingdoms.kingdom_realm_content import _gather_state

    state = await _gather_state(kingdom, wiring)
    rendered = 0
    failures: list[str] = []
    for key in keys:
        if key not in LAB_VIEWS:
            continue
        try:
            view, files = await _build_lab_view(
                key, locale, wiring, kingdom, state, variant
            )
            neutralize_view(view)
            # laboratoire-v2 travaux variant (Drasah 05/11): the FIRST real
            # optimization — every attached asset rides the MEDIANCUT-256
            # recompression (pure stdlib, cached per content hash). Any
            # decline falls back to the original bytes untouched.
            if variant == "travaux" and files:
                from kingdoms.mods.kingdoms.kingdom_lab_compress import (
                    compress_discord_file,
                )

                files = [compress_discord_file(f) for f in files]
            # the étiquette rides FIRST (the walkthrough reads in order) —
            # ``children`` returns a copy, so the view is rebuilt around it.
            try:
                children = list(view.children)
                view.clear_items()
                view.add_item(_label_header(key, locale, variant))
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
    """Return the live asset inventory (lieux illustrations + market cards).

    laboratoire-v2 travaux variant: when a MEDIANCUT-256 pair is already
    cached (a previous dispatch compressed it), the line shows the
    deployed → travaux weights (−gain %) — the pairs Drasah compares.
    """
    from kingdoms.mods.kingdoms.kingdom_lab_compress import compressed_size

    lines: list[str] = []
    for base, label in ((_LIEUX_ASSETS, "lieux"), (_MARCHE_ASSETS, "marché")):
        if not base.is_dir():
            continue
        for path in sorted(base.glob("*.png")):
            line = (
                f"• `{path.name}` — {path.stat().st_size / 1024:.0f} Ko · "
                f"{_png_size(path)} ({label})"
            )
            compressed = compressed_size(path)
            if compressed is not None:
                original = path.stat().st_size
                gain = 100 - 100 * compressed / original
                line += f" → {compressed / 1024:.0f} Ko travaux (−{gain:.0f} %)"
            lines.append(line)
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


async def _dispatch_and_report(
    interaction: discord.Interaction,
    locale: str,
    item_key: str,
) -> None:
    """Deferred dispatch path: renders → 📜 original + 🚧 travaux → card.

    laboratoire-v2 (Drasah 05/11): ONE test renders into BOTH salons at
    once (the side-by-side comparison), then the feedback test card is
    posted in 🧪 labo carrying the three verdict buttons.
    """
    strings = _strings(locale)
    wiring = await _guard(interaction, locale)
    if wiring is None:
        return
    await interaction.response.defer(ephemeral=True)
    guild = getattr(interaction, "guild", None)
    labo = _find_lab_channel(guild)
    original = _find_lab_channel(guild, LAB_ORIGINAL_SLUG)
    travaux = _find_lab_channel(guild, LAB_TRAVAUX_SLUG)
    if labo is None:
        await interaction.followup.send(strings["no_channel"], ephemeral=True)
        return
    if original is None or travaux is None:
        await interaction.followup.send(
            strings["no_render_channel"].format(
                channel="📜 original" if original is None else "🚧 travaux"
            ),
            ephemeral=True,
        )
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
    item = LAB_TEST_ITEMS.get(item_key) or LAB_TEST_ITEMS["tout"]
    keys = list(item["views"])
    rendered_original, failed_original = await render_lab_views(
        original, locale, wiring, kingdom, keys, variant="original"
    )
    rendered_travaux, failed_travaux = await render_lab_views(
        travaux, locale, wiring, kingdom, keys, variant="travaux"
    )
    failures = sorted(set(failed_original) | set(failed_travaux))
    errors = ""
    if failures:
        errors = strings["posted_errors"].format(keys=", ".join(failures))
    try:
        await labo.send(
            view=_test_card_view(locale, item_key), allowed_mentions=NO_MENTIONS
        )
    except Exception:
        logger.warning("KINGDOM LAB: test card send failed", exc_info=True)
    logger.info(
        "KINGDOM LAB: test %s dispatched — original=%d travaux=%d",
        item_key,
        rendered_original,
        rendered_travaux,
    )
    await interaction.followup.send(
        strings["dispatched"].format(
            count=rendered_original + rendered_travaux, errors=errors
        ),
        ephemeral=True,
    )


def _test_card_view(
    locale: str,
    item_key: str,
    status_key: str | None = None,
    remarks: str | None = None,
) -> discord.ui.LayoutView:
    """Build a test card — the feedback panel that follows every dispatch.

    Fresh card: the three live verdict buttons. After a verdict the card
    FREEEZES: the buttons are disabled, the status (and the remarks)
    join the card — the verdict stays readable in labo forever.
    """
    strings = _strings(locale)
    item = LAB_TEST_ITEMS.get(item_key) or LAB_TEST_ITEMS["tout"]
    title = strings[item["title_key"]]
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(discord.ui.TextDisplay(f"## {strings['card_title'].format(title=title)}"))
    view.add_item(discord.ui.TextDisplay(strings[item["why_key"]]))
    if status_key is None:
        view.add_item(discord.ui.TextDisplay(strings["card_dispatched"]))
    view.add_item(
        discord.ui.ActionRow(
            KingdomLabVerdictButton("validate", item_key, locale, disabled=status_key is not None),
            KingdomLabVerdictButton("modify", item_key, locale, disabled=status_key is not None),
            KingdomLabVerdictButton("cancel", item_key, locale, disabled=status_key is not None),
        )
    )
    if status_key is not None:
        view.add_item(discord.ui.TextDisplay(strings[status_key]))
        if remarks:
            view.add_item(discord.ui.TextDisplay(f"> {remarks}"))
    return view


class KingdomLabTestSelect(
    discord.ui.DynamicItem[discord.ui.Select], template=r"kingdoms:lab:test"
):
    """The test dropdown — WHAT to test and WHY (single choice)."""

    def __init__(self, locale: str) -> None:
        strings = _strings(locale)
        options = [
            discord.SelectOption(
                label=strings[item["title_key"]][:100],
                value=key,
                description=strings[item["why_key"]][:100],
            )
            for key, item in LAB_TEST_ITEMS.items()
        ]
        super().__init__(
            discord.ui.Select(
                options=options,
                custom_id="kingdoms:lab:test",
                placeholder=strings["test_placeholder"],
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
    ) -> KingdomLabTestSelect:
        """Rebuild from the wire — THIS module's strings only."""
        return cls(_locale(interaction))

    async def callback(self, interaction: discord.Interaction) -> None:
        """Dispatch the selected test into both salons (deferred)."""
        values = [v for v in list(self.item.values or []) if v in LAB_TEST_ITEMS]
        await _dispatch_and_report(
            interaction, _locale(interaction), (values or ["tout"])[0]
        )


class KingdomLabVerdictButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdoms:lab:verdict:(validate|modify|cancel):(\w+)",
):
    """One verdict button — Valider / Modifier / Annuler the travaux version.

    Statelesss by design: the test key rides the custom_id, so a
    restart cannot orphan a verdict. Each verdict freezes its card and
    logs a dedicated INFO line retrievable via /logs.
    """

    def __init__(
        self, action: str, item_key: str, locale: str, *, disabled: bool = False
    ) -> None:
        strings = _strings(locale)
        styles = {
            "validate": discord.ButtonStyle.success,
            "modify": discord.ButtonStyle.primary,
            "cancel": discord.ButtonStyle.danger,
        }
        super().__init__(
            discord.ui.Button(
                label=strings[f"verdict_{action}"][:80],
                custom_id=f"kingdoms:lab:verdict:{action}:{item_key}",
                style=styles.get(action, discord.ButtonStyle.secondary),
                disabled=disabled,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> KingdomLabVerdictButton:
        """Rebuild from the wire — THIS module's strings only."""
        return cls(match.group(1), match.group(2), _locale(interaction))

    async def callback(self, interaction: discord.Interaction) -> None:
        """Apply the verdict: freeze the card, log the INFO line."""
        from kingdoms.mods.kingdoms.kingdom_persistent import _is_admin, _wiring

        locale = _locale(interaction)
        strings = _strings(locale)
        wiring = _wiring()
        if not _is_admin(interaction, wiring.bot_admins):
            await interaction.response.send_message(
                strings["not_allowed"], ephemeral=True
            )
            return
        match = re.search(
            r"kingdoms:lab:verdict:(validate|modify|cancel):(\w+)$",
            self.item.custom_id or "",
        )
        action = match.group(1) if match else "validate"
        item_key = match.group(2) if match else "tout"
        if action == "modify":
            await interaction.response.send_modal(LabRemarksModal(locale, item_key))
            return
        status_key = "verdict_validated" if action == "validate" else "verdict_cancelled"
        logger.info(
            "KINGDOM LAB: test %s %s by user %s",
            item_key,
            "VALIDATED" if action == "validate" else "CANCELLED",
            getattr(getattr(interaction, "user", None), "id", None),
        )
        try:
            await interaction.response.edit_message(
                view=_test_card_view(locale, item_key, status_key)
            )
        except Exception:
            logger.warning("KINGDOM LAB: verdict card edit failed", exc_info=True)
            await interaction.response.send_message(
                strings[status_key], ephemeral=True
            )
            return
        try:
            await interaction.followup.send(strings[status_key], ephemeral=True)
        except Exception:
            logger.warning("KINGDOM LAB: verdict followup failed", exc_info=True)


class LabRemarksModal(discord.ui.Modal):
    """The ✏️ Modifier remark sheet — Drasah's notes ride the verdict.

    The remarks are frozen onto the card AND logged on the dedicated
    KINGDOM LAB INFO line, so Mistral reads them back via /logs when
    Drasah says « reprends avec les remarques ».
    """

    def __init__(self, locale: str, item_key: str) -> None:
        strings = _strings(locale)
        super().__init__(title=strings["remarks_title"][:45])
        self._locale = locale
        self._item_key = item_key
        self.remarks = discord.ui.TextInput(
            label=strings["remarks_label"][:45],
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=True,
        )
        self.add_item(self.remarks)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Freeze the card with the remarks, log them, confirm."""
        from kingdoms.mods.kingdoms.kingdom_persistent import _is_admin, _wiring

        locale = self._locale
        strings = _strings(locale)
        wiring = _wiring()
        if not _is_admin(interaction, wiring.bot_admins):
            await interaction.response.send_message(
                strings["not_allowed"], ephemeral=True
            )
            return
        remarks = str(self.remarks.value or "").strip()
        user = getattr(getattr(interaction, "user", None), "id", None)
        logger.info(
            "KINGDOM LAB: test %s MODIFIED by user %s — remarks: %s",
            self._item_key,
            user,
            remarks,
        )
        acknowledged = False
        try:
            await interaction.response.edit_message(
                view=_test_card_view(
                    locale, self._item_key, "verdict_modified", remarks
                )
            )
            acknowledged = True
        except Exception:
            logger.warning("KINGDOM LAB: remarks card edit failed", exc_info=True)
        try:
            if acknowledged:
                await interaction.followup.send(
                    strings["remarks_done"], ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    strings["remarks_done"], ephemeral=True
                )
        except Exception:
            logger.warning("KINGDOM LAB: remarks confirm failed", exc_info=True)


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
        await interaction.followup.send(strings["vitrine_posted"], ephemeral=True)


class KingdomLabCleanButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]], template=r"kingdoms:lab:clean"
):
    """The 🧹 sweep — the render salons go, the cockpit and cards stay."""

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
        """Sweep the bot's render messages in 📜 original and 🚧 travaux.

        laboratoire-v2 (Drasah 05/11): the renders live in the two
        version salons — labo (cockpit, test cards, verdicts) is NEVER
        touched by the sweep.
        """
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
        guild = getattr(interaction, "guild", None)
        client_user = getattr(getattr(interaction, "client", None), "user", None)
        bot_id = getattr(client_user, "id", None)
        deleted = 0
        for slug in (LAB_ORIGINAL_SLUG, LAB_TRAVAUX_SLUG):
            channel = _find_lab_channel(guild, slug)
            if channel is None:
                continue
            for message in await channel_messages(channel):
                author_id = getattr(getattr(message, "author", None), "id", None)
                if author_id is not None and bot_id is not None and author_id != bot_id:
                    continue
                try:
                    await message.delete()
                    deleted += 1
                except Exception:
                    logger.warning(
                        "KINGDOM LAB: message delete failed", exc_info=True
                    )
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
    # laboratoire-v1 fix (Drasah 05/11, live 50035): a LayoutView does
    # NOT wrap a bare Select into an ActionRow at send time — Discord
    # rejected the cockpit with « In components.N: type must be one
    # of (1, 9, 10, 12, 13, 14, 17) ». Every interactive item rides
    # inside an explicit ActionRow (one select per row, Discord's rule).
    view.add_item(discord.ui.ActionRow(KingdomLabTestSelect(locale)))
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
    from kingdoms.mods.kingdoms.kingdom_persistent import antidoubleclic_wrap

    bot.add_dynamic_items(
        # antidoubleclic-v1 (Drasah 06/11): the lab items ride the
        # per-player in-flight gate like every restart-proof item.
        *[antidoubleclic_wrap(item) for item in (
        KingdomLabTestSelect,
        KingdomLabVerdictButton,
        KingdomLabVitrineButton,
        KingdomLabCleanButton,
        KingdomLabRefreshButton,
        )]
    )
