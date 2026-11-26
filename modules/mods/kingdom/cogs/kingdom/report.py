"""kingdom-report-v1 (Drasah 26/11, Affaire 38) — « 🚩 Signaler ».

Le hub du royaume porte, À DROITE de « 🏰 Entrée », la porte du
signalement : un membre (Roi inclus — acté Drasah 26/11) clique, choisit
la NATURE du problème (bug de jeu, litige de score, comportement,
autre), puis le décrit en texte libre (un modal). La ligne atterrit
immédiatement dans le journal admin 📜 logs (le guichet fusionné,
T4a) via le seam ``log_admin_action_on_interaction`` avec son kind
``report`` — l'emoji vit dans la table KIND_EMOJI, DONNÉE jamais codée.

Architecture (les règles du portage) : zéro nouveau moteur. Le bouton
et le menu sont des DynamicItem restart-proof (``kingdom:realm:report…``,
les mêmes gabarits que les autres portes du hub), la fenêtre éphémère
passe par ``open_unique_ephemeral`` (le ✖️ de fermeture offert), la
ligne du journal par le seam admin (une rangée de données, pas un
envoi ad hoc — #350 : le jour du resource-post le kind migrera seul).
Un anti-spam : un signalement par membre et par tranche de 10 minutes
(mémoire vive du process — le redémarrage relâche le garde, coûte zéro
écriture, le journal reste la vérité).
"""

from __future__ import annotations

import logging
import math
import time
from typing import Any

import discord

from .admin_logs import log_admin_action_on_interaction
from .common import open_unique_ephemeral, surface

logger = logging.getLogger("kingdom.report")

_NS = "kingdom:realm"
REPORT_SURFACE = "panel:mod:kingdom:realm:report"
_COOLDOWN_SECONDS = 600
_LAST_REPORT: dict[str, float] = {}

# La nature du problème — la clé interne est STABLE (le kind du journal),
# le libellé vit dans les strings (données, saison 2 tunable sans code).
_CATEGORIES: dict[str, str] = {
    "bug": "report_cat_bug",
    "score": "report_cat_score",
    "behavior": "report_cat_behavior",
    "other": "report_cat_other",
}


def _strings_of(interaction: discord.Interaction) -> dict[str, str]:
    from .realms import realm_strings

    return realm_strings(interaction)


def _category_label(strings: dict[str, str], cat: str) -> str:
    key = _CATEGORIES.get(cat, _CATEGORIES["other"])
    return str(strings[key])


def _category_options(strings: dict[str, str]) -> list[discord.SelectOption]:
    return [
        discord.SelectOption(label=_category_label(strings, cat)[:100], value=cat)
        for cat in _CATEGORIES
    ]


def report_window(strings: dict[str, str]) -> discord.ui.LayoutView:
    """La fenêtre éphémère du signalement — le menu des natures."""
    row: Any = discord.ui.ActionRow()
    row.add_item(RealmReportCategorySelect(_category_options(strings)).item)
    blocks: list[discord.ui.Item[discord.ui.LayoutView]] = [
        discord.ui.TextDisplay(f"# {strings['report_button']}"),
        discord.ui.Separator(),
        discord.ui.TextDisplay(str(strings["report_intro"])),
        discord.ui.Separator(),
        row,
        discord.ui.Separator(),
        discord.ui.TextDisplay(str(strings["report_hint"])),
    ]
    return surface(
        REPORT_SURFACE,
        discord.ui.Container(*blocks, accent_colour=discord.Colour.orange()),
    )


def _cooldown_left(guild_id: str, user_id: str, now: float) -> int:
    """Les minutes restantes de l'anti-spam (0 = la porte est ouverte)."""
    last = _LAST_REPORT.get(f"{guild_id}:{user_id}", 0.0)
    return max(0, math.ceil((_COOLDOWN_SECONDS - (now - last)) / 60))


class RealmReportButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]], template=rf"{_NS}:report$"
):
    """« 🚩 Signaler » — la porte du signalement, à droite de l'Entrée."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=str(label)[:80],
                custom_id=f"{_NS}:report",
                style=discord.ButtonStyle.secondary,
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        return cls(_strings_of(interaction)["report_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        strings = _strings_of(interaction)
        try:
            left = _cooldown_left(
                str(interaction.guild_id or ""), str(interaction.user.id), time.time()
            )
            await interaction.response.defer(ephemeral=True)
            if left > 0:
                await open_unique_ephemeral(
                    interaction,
                    content=strings["report_cooldown_note"].format(left),
                )
                return
            await open_unique_ephemeral(interaction, view=report_window(strings))
        except Exception:  # noqa: BLE001 — the door NEVER times out silently
            logger.warning("kingdom realms: the report door failed", exc_info=True)
            try:
                await open_unique_ephemeral(interaction, content=strings["realm_error_note"])
            except Exception:  # noqa: BLE001 — even the fallback never raises
                logger.warning("kingdom realms: the report fallback failed", exc_info=True)


class RealmReportCategorySelect(
    discord.ui.DynamicItem[discord.ui.Select[Any]], template=rf"{_NS}:report:cat$"
):
    """Le menu des natures — un choix ouvre le modal de description."""

    def __init__(self, options: list[discord.SelectOption]) -> None:
        super().__init__(
            discord.ui.Select(
                custom_id=f"{_NS}:report:cat",
                options=options[:25],
                placeholder="🚩",
                min_values=1,
                max_values=1,
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        return cls(_category_options(_strings_of(interaction)))

    async def callback(self, interaction: discord.Interaction) -> None:
        strings = _strings_of(interaction)
        chosen = str(self.item.values[0] if self.item.values else "other")
        cat = chosen if chosen in _CATEGORIES else "other"
        await interaction.response.send_modal(ReportModal(strings, cat))


class ReportModal(discord.ui.Modal):
    """La description libre — la ligne du journal part à la soumission."""

    body: discord.ui.TextInput = discord.ui.TextInput(
        label="Que se passe-t-il ?",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=True,
    )

    def __init__(self, strings: dict[str, str], category: str) -> None:
        self.strings = dict(strings)
        self.category = str(category)
        super().__init__(title=str(strings["report_modal_title"])[:45], timeout=300)
        self.children[0].label = str(strings["report_text_label"])[:45]  # type: ignore[index]
        self.children[0].placeholder = str(strings["report_text_placeholder"])  # type: ignore[index]

    async def on_submit(self, interaction: discord.Interaction) -> None:
        strings = self.strings
        text = str(self.body.value or "").strip()[:1000]
        if not text:
            # une description vide ne va pas plus loin — réponse directe,
            # jamais de raise sur la soumission du member
            await interaction.response.send_message(
                str(strings["report_empty_note"]), ephemeral=True
            )
            return
        _LAST_REPORT[f"{interaction.guild_id}:{interaction.user.id}"] = time.time()
        await log_admin_action_on_interaction(
            interaction,
            kind="report",
            action=str(strings["report_log_line"]).format(
                _category_label(strings, self.category), text
            ),
        )
        await interaction.response.send_message(
            str(strings["report_done_note"]), ephemeral=True
        )


def realm_report_dynamic_items() -> tuple:
    """Les DynamicItem du signalement (enregistrés avec les surfaces realm)."""
    return (RealmReportButton, RealmReportCategorySelect)


__all__ = ["RealmReportButton", "realm_report_dynamic_items", "report_window"]
