"""Vitrine-v1 (Drasah 26/11, tranche 44) : le 🏛️ Panthéon.

Le salon solo et permanent qui vit HORS de la partie : la vitrine des
saisons. Le panel épinglé montre d'un coup d'œil le score (territoires
+ alliances par royaume), et trois navigations éphémères emmènent
dans la mémoire du jeu :

- 🏆 Palmarès : une ligne par saison passée, le vainqueur et comment
  il a gagné (comptes ou ShowMatch si égalité) ;
- 📜 Historique : le verdict complet d'une saison archivée (podium
  final, ShowMatch, chiffres clés) ;
- 📜 Chronique : la saison d'un royaume racontée par les chroniques de
  ses seigneurs, avec la COMPARAISON croisée de deux royaumes (le duel
  des deux points de vue, Drasah 26/11).

Tout est LECTURE PURE sur des seams existants (territory_count,
lords, season_archives, la chronique des seigneurs) : la vitrine
n'écrit jamais, ne modifie aucune mécanique, et survit aux saisons
comme les archives qu'elle lit. #395 : le pattern est le pin statique
du Scriptorium/Taverne ; #396-ready : chaque fenêtre est une surface
déclarée réutilisable par une future annonce.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any

import discord

from .common import locale_of, open_unique_ephemeral, surface, wiring
from .strings import strings

logger = logging.getLogger("kingdom.pantheon")

PANTHEON_PIN_KEY = "panel:mod:kingdom:pantheon"
PANTHEON_CHANNEL_KEY = "pantheon"
_MEDALS = ("🥇", "🥈", "🥉")
_PAGE_CHARS = 1700
_GAIA_NAME = "Gaïa"


def _pantheon_strings(interaction_or_locale: Any) -> dict[str, str]:
    """Return the panthéon strings for one interaction or raw locale."""
    if isinstance(interaction_or_locale, str):
        return strings(interaction_or_locale[:2])
    return strings(locale_of(interaction_or_locale)[:2])


class _SafeParams(dict[str, str]):
    """Swallow a missing format param (never a KeyError)."""

    def __missing__(self, key: str) -> str: 
        return ""


async def _alliances_by_kingdom(stack: Any) -> dict[str, int]:
    """Count each kingdom.s alliances (unique married civilizations)."""
    counts: dict[str, set[str]] = {}
    if stack is None:
        return {}
    try:
        lords = await stack.kingdoms.lords()
    except Exception:
        logger.warning("kingdom: pantheon lords read failed", exc_info=True)
        return {}
    for lord in lords:
        if getattr(lord, "left", False) or not getattr(lord, "kingdom_id", None):
            continue
        civ = getattr(lord, "married_civilization", None)
        if not civ:
            continue
        counts.setdefault(str(lord.kingdom_id), set()).add(str(civ))
    return {kid: len(civs) for kid, civs in counts.items()}


async def _score_rows(stack: Any) -> list[tuple[str, int, int, bool]]:
    """Return the panel rows: (name, territories, alliances, is_gaia), medals order."""
    if stack is None:
        return []
    try:
        kingdoms = await stack.kingdoms.kingdoms()
        counts = await stack.territories.territory_count_by_kingdom()
    except Exception:
        logger.warning("kingdom: pantheon score read failed", exc_info=True)
        return []
    alliances = await _alliances_by_kingdom(stack)
    rows = [
        (
            str(kingdom.name),
            int(counts.get(str(kingdom.id), 0)),
            int(alliances.get(str(kingdom.id), 0)),
            bool(getattr(kingdom, "is_gaia", False)),
        )
        for kingdom in kingdoms
    ]
    rows.sort(key=lambda row: row[1], reverse=True)
    return rows


def _count_words(strings: dict[str, str], territories: int, alliances: int) -> tuple[str, str]:
    """Return the plural-aware count words (le « (s) » bizarre est mort)."""
    terr_word = strings["pantheon_territory"] if territories == 1 else strings["pantheon_territories"]
    all_word = strings["pantheon_alliance"] if alliances == 1 else strings["pantheon_alliances"]
    return terr_word, all_word


def _score_text(strings: dict[str, str], rows: list[tuple[str, int, int, bool]]) -> str:
    """Render the at-a-glance LIVE score block (the panel's fallback)."""
    lines: list[str] = []
    for rank, (name, territories, alliances, is_gaia) in enumerate(rows):
        medal = _MEDALS[rank] if rank < len(_MEDALS) else "▫️"
        if is_gaia:
            terr_word, _all_word = _count_words(strings, territories, alliances)
            line = strings["pantheon_pin_gaia_line"].format(territories, terr_word)
        else:
            terr_word, all_word = _count_words(strings, territories, alliances)
            line = strings["pantheon_pin_line"].format(
                medal, name, territories, terr_word, alliances, all_word
            )
        lines.append(line)
    if not lines:
        lines.append(strings["pantheon_pin_no_season"])
    return "\n".join(lines)


def _phase_text(strings: dict[str, str], phase: str) -> str:
    """Return the phase's player-readable label (data, #369 : a new phase = a key)."""
    return strings.get(f"pantheon_phase_{phase}") or str(phase or "?")


def _season_label(strings: dict[str, str], season: Any) -> str:
    """Return the season's readable name (never a raw technical id).

    A season whose « name » IS its technical id (``s-20261126-182152``,
    the engine's default) reads « Saison en cours » — the vitrine never
    shows plumbing (le retour visuel de Drasah, 26/11).
    """
    name = str(getattr(season, "name", "") or "")
    if name and not re.fullmatch(r"s-\d[\w-]*", name):
        return name
    return strings["pantheon_pin_season_unnamed"]


async def _gaia_ids(stack: Any) -> set[str]:
    """Return the live Gaïa kingdom ids (the world is never a competitor)."""
    if stack is None:
        return set()
    try:
        kingdoms = await stack.kingdoms.kingdoms()
    except Exception:
        return set()
    return {str(k.id) for k in kingdoms if getattr(k, "is_gaia", False)}


async def _last_podium_lines(strings: dict[str, str], stack: Any) -> list[str] | None:
    """Build the LAST finished season's podium (the panel's default block).

    panthéon-polish-v1 (Drasah 26/11) : la vitrine montre par défaut
    le podium de la dernière saison terminée — le vainqueur porte sa
    mention (comptes ou ShowMatch), Gaïa n'y figure pas (le monde ne
    court pas). None = pas d'archive (le panel retombe sur le score
    live, la vitrine n'est jamais vide).
    """
    if stack is None:
        return None
    try:
        archives = await stack.kingdoms.season_archives()
    except Exception:
        return None
    if not archives:
        return None
    archive = max(archives, key=lambda a: str(a.get("season_id", "")))
    names = {
        str(k.get("_id")): str(k.get("name", k.get("_id"))) for k in archive.get("kingdoms", [])
    }
    gaia = await _gaia_ids(stack)
    counts: dict[str, int] = {}
    for territory in archive.get("territories", []):
        owner = str(territory.get("owner_kingdom_id") or "")
        if owner and owner not in gaia:
            counts[owner] = counts.get(owner, 0) + 1
    if not counts:
        return None
    ordered = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    season_name = str(archive.get("name") or archive.get("season_id", "?"))
    lines = [strings["pantheon_pin_last_title"].format(season_name)]
    note = _archive_note(strings, archive)
    for rank, (kid, count) in enumerate(ordered):
        medal = _MEDALS[rank] if rank < len(_MEDALS) else "▫️"
        terr_word, _all_word = _count_words(strings, count, 1)
        line = strings["pantheon_pin_last_line"].format(medal, names.get(kid, kid), count, terr_word)
        if rank == 0:
            line = f"{line} — {note}"
        lines.append(line)
    return lines


# ---------------------------------------------------------------------------
# The pinned panel (the salon's at-a-glance vitrine)
# ---------------------------------------------------------------------------
async def build_pantheon_panel(guild_id: str) -> discord.ui.LayoutView:
    """Build the pinned Panthéon panel — the season at a glance, one look."""
    from .panel import _guild_locale

    locale = await _guild_locale(guild_id)
    strings_map = _pantheon_strings(locale)
    stack = wiring()
    rows = await _score_rows(stack)
    try:
        season = None if stack is None else await stack.kingdoms.current_season()
    except Exception:
        season = None
    if season is not None:
        season_line = strings_map["pantheon_pin_season"].format(
            _season_label(strings_map, season),
            _phase_text(strings_map, str(getattr(season, "phase", ""))),
        )
    else:
        season_line = strings_map["pantheon_pin_no_season"]
    # panthéon-polish-v1 : le gros bloc par défaut = le PODIUM de la
    # dernière saison terminée ; sans archive (la première saison), la
    # vitrine retombe sur le score live — jamais vide.
    podium = await _last_podium_lines(strings_map, stack)
    score_text = "\n".join(podium) if podium else _score_text(strings_map, rows)
    return surface(
        PANTHEON_PIN_KEY,
        discord.ui.TextDisplay(f"# {strings_map['pantheon_pin_title']}"),
        discord.ui.TextDisplay(strings_map["pantheon_pin_hint"]),
        discord.ui.TextDisplay(season_line),
        discord.ui.Separator(),
        discord.ui.TextDisplay(score_text),
        discord.ui.Separator(),
        discord.ui.ActionRow(
            PantheonPalmaresButton(strings_map["pantheon_palmares_button"]).item,
            PantheonHistoriqueButton(strings_map["pantheon_historique_button"]).item,
            PantheonChroniqueButton(strings_map["pantheon_chronique_button"]).item,
        ),
    )


# ---------------------------------------------------------------------------
# 🏆 Palmarès — one line per past season
# ---------------------------------------------------------------------------
def _archive_note(strings: dict[str, str], archive: dict[str, Any]) -> str:
    """Explain how the archived season was decided (counts or ShowMatch)."""
    matches = [dict(m) for m in archive.get("showmatches", []) if dict(m).get("finished")]
    if matches:
        match = matches[-1]
        return strings["pantheon_palmares_showmatch"].format(
            int(match.get("score_a", 0) or 0),
            int(match.get("score_b", 0) or 0),
        )
    return strings["pantheon_palmares_counts"]


def _archive_winner(archive: dict[str, Any]) -> str:
    """Return the archived season's winner name ('?' when undecided)."""
    kingdoms = {str(k.get("_id")): str(k.get("name", k.get("_id"))) for k in archive.get("kingdoms", [])}
    winner: str | None = None
    for season in archive.get("seasons", []):
        if season.get("winner_kingdom_id"):
            winner = str(season.get("winner_kingdom_id"))
    return kingdoms.get(str(winner or ""), "?")


async def _palmares_lines(strings: dict[str, str]) -> list[str]:
    """Return the palmarès lines — the live season first, the archives after."""
    stack = wiring()
    lines: list[str] = []
    if stack is not None:
        try:
            season = await stack.kingdoms.current_season()
        except Exception:
            season = None
        if season is not None:
            lines.append(
                strings["pantheon_palmares_live"].format(
                    str(getattr(season, "name", getattr(season, "id", "?")))
                )
            )
    try:
        archives = [] if stack is None else await stack.kingdoms.season_archives()
    except Exception:
        logger.warning("kingdom: pantheon archives read failed", exc_info=True)
        archives = []
    for archive in archives:
        lines.append(
            strings["pantheon_palmares_line"].format(
                str(archive.get("season_id", "?")),
                _archive_winner(archive),
                _archive_note(strings, archive),
            )
        )
    if not lines:
        lines.append(strings["pantheon_palmares_empty"])
    return lines


class PantheonPalmaresButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]], template=r"kingdom:pantheon:palmares$"
):
    """The 🏆 Palmarès navigation (restart-proof)."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80], custom_id="kingdom:pantheon:palmares", style=discord.ButtonStyle.secondary
            )
        )

    @classmethod
    async def from_custom_id(
        cls, interaction: discord.Interaction, item: Any, match: re.Match[str], /
    ) -> PantheonPalmaresButton:
        return cls(_pantheon_strings(interaction)["pantheon_palmares_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        strings_map = _pantheon_strings(interaction)
        pages = _paginate(await _palmares_lines(strings_map))
        await open_unique_ephemeral(
            interaction,
            view=surface(
                "panel:mod:kingdom:pantheon:palmares",
                discord.ui.TextDisplay(f"# {strings_map['pantheon_palmares_title']}"),
                discord.ui.Separator(),
                discord.ui.TextDisplay(pages[0]),
            ),
        )


# ---------------------------------------------------------------------------
# 📜 Historique — one archived season's verdict
# ---------------------------------------------------------------------------
async def _historique_view(strings: dict[str, str]) -> discord.ui.LayoutView:
    """Build the season picker of the Historique window."""
    stack = wiring()
    options: list[discord.SelectOption] = []
    try:
        archives = [] if stack is None else await stack.kingdoms.season_archives()
    except Exception:
        archives = []
    for archive in archives[:25]:
        sid = str(archive.get("season_id", "?"))
        options.append(discord.SelectOption(label=sid[:100], value=sid[:100]))
    text = (
        strings["pantheon_historique_pick"]
        if options
        else strings["pantheon_palmares_empty"]
    )
    return surface(
        "panel:mod:kingdom:pantheon:historique",
        discord.ui.TextDisplay(f"# {strings['pantheon_historique_title']}"),
        discord.ui.Separator(),
        discord.ui.TextDisplay(text),
        discord.ui.ActionRow(PantheonSeasonSelect(options).item),
    )


class PantheonHistoriqueButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]], template=r"kingdom:pantheon:historique$"
):
    """The 📜 Historique navigation (restart-proof)."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80], custom_id="kingdom:pantheon:historique", style=discord.ButtonStyle.secondary
            )
        )

    @classmethod
    async def from_custom_id(
        cls, interaction: discord.Interaction, item: Any, match: re.Match[str], /
    ) -> PantheonHistoriqueButton:
        return cls(_pantheon_strings(interaction)["pantheon_historique_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        await open_unique_ephemeral(interaction, view=await _historique_view(_pantheon_strings(interaction)))


class PantheonSeasonSelect(
    discord.ui.DynamicItem[discord.ui.Select[Any]],
    template=r"kingdom:pantheon:histo:(?P<sid>[A-Za-z0-9_:-]+)",
):
    """The archived-season picker of the Historique window."""

    def __init__(self, options: list[discord.SelectOption], sid: str = "") -> None:
        # the template needs a NON-EMPTY sid (discord.py validates the
        # custom_id against it at construction — an empty marker crashed
        # the window, the live catch of Drasah's click, 26/11)
        select = discord.ui.Select(
            custom_id=f"kingdom:pantheon:histo:{sid or '-'}"[:100],
            placeholder="…",
            options=options or [discord.SelectOption(label="—", value="-")],
        )
        super().__init__(select)
        self.season_id = sid

    @classmethod
    async def from_custom_id(
        cls, interaction: discord.Interaction, item: Any, match: re.Match[str], /
    ) -> PantheonSeasonSelect:
        return cls([], "" if match["sid"] == "-" else match["sid"])

    async def callback(self, interaction: discord.Interaction) -> None:
        strings_map = _pantheon_strings(interaction)
        view = await _verdict_view(strings_map, self.season_id)
        await open_unique_ephemeral(interaction, view=view)


async def _verdict_view(strings: dict[str, str], season_id: str) -> discord.ui.LayoutView:
    """Build the full verdict of one archived season."""
    stack = wiring()
    try:
        archives = [] if stack is None else await stack.kingdoms.season_archives()
    except Exception:
        archives = []
    archive = next((a for a in archives if str(a.get("season_id", "")) == season_id), None)
    if archive is None:
        return surface(
            "panel:mod:kingdom:pantheon:histo",
            discord.ui.TextDisplay(f"# {strings['pantheon_histo_title'].format(season_id)}"),
            discord.ui.TextDisplay(strings["pantheon_palmares_empty"]),
        )
    names = {
        str(k.get("_id")): str(k.get("name", k.get("_id"))) for k in archive.get("kingdoms", [])
    }
    counts: dict[str, int] = {}
    for territory in archive.get("territories", []):
        owner = str(territory.get("owner_kingdom_id") or "")
        if owner:
            counts[owner] = counts.get(owner, 0) + 1
    ordered = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    lines = [
        strings["pantheon_histo_winner"].format(_archive_winner(archive), _archive_note(strings, archive))
    ]
    lines.append(strings["pantheon_histo_podium_title"])
    for rank, (kid, count) in enumerate(ordered):
        medal = _MEDALS[rank] if rank < len(_MEDALS) else "▫️"
        terr_word, _all_word = _count_words(strings, count, 1)
        lines.append(
            strings["pantheon_histo_podium_line"].format(
                medal, names.get(kid, kid), count, terr_word
            )
        )
    return surface(
        "panel:mod:kingdom:pantheon:histo",
        discord.ui.TextDisplay(f"# {strings['pantheon_histo_title'].format(season_id)}"),
        discord.ui.Separator(),
        discord.ui.TextDisplay(_paginate(lines)[0]),
    )


# ---------------------------------------------------------------------------
# 📜 Chronique — one kingdom's season, and the crossed comparison
# ---------------------------------------------------------------------------
async def _timeline(stack: Any, kingdom_id: str) -> list[tuple[int, str, str, dict[str, str]]]:
    """Return the merged, dated chronicle entries of one kingdom.s lords."""
    if stack is None:
        return []
    try:
        lords = await stack.kingdoms.lords()
    except Exception:
        logger.warning("kingdom: pantheon chronicle read failed", exc_info=True)
        return []
    entries: list[tuple[int, str, str, dict[str, str]]] = []
    for lord in lords:
        if getattr(lord, "left", False) or str(getattr(lord, "kingdom_id", "")) != str(kingdom_id):
            continue
        for entry in getattr(lord, "chronicle", []) or []:
            entries.append(
                (
                    int(getattr(entry, "at", 0) or 0),
                    str(getattr(lord, "display_name", getattr(lord, "id", "?"))),
                    str(getattr(entry, "kind", "")),
                    {str(k): str(v) for k, v in (getattr(entry, "params", None) or {}).items()},
                )
            )
    entries.sort(key=lambda item: item[0])
    return entries


def _entry_line(strings: dict[str, str], entry: tuple[int, str, str, dict[str, str]]) -> str:
    """Render one chronicle entry as a dated, player-readable line."""
    at, lord, kind, params = entry
    when = datetime.fromtimestamp(at, tz=UTC).strftime("%d/%m %Hh%M") if at else "?"
    template = strings.get(f"pantheon_kind_{kind}") or strings["pantheon_kind_other"]
    merged = _SafeParams(params)
    merged.setdefault("kind", kind)
    phrase = template.format_map(merged)
    return strings["pantheon_chronique_line"].format(when, lord, phrase)


async def _kingdom_names() -> dict[str, str]:
    """Return the live kingdom id → name map (for the pickers and the tags)."""
    stack = wiring()
    if stack is None:
        return {}
    try:
        return {str(k.id): str(k.name) for k in await stack.kingdoms.kingdoms()}
    except Exception:
        logger.warning("kingdom: pantheon kingdoms read failed", exc_info=True)
        return {}


async def _chronique_view(strings: dict[str, str], picked: str = "") -> discord.ui.LayoutView:
    """Build the kingdom picker of the Chronique window."""
    names = await _kingdom_names()
    options = [
        discord.SelectOption(label=name[:100], value=kid[:100])
        for kid, name in names.items()
    ]
    return surface(
        "panel:mod:kingdom:pantheon:chronique",
        discord.ui.TextDisplay(f"# {strings['pantheon_chronique_title']}"),
        discord.ui.TextDisplay(strings["pantheon_chronique_hint"]),
        discord.ui.Separator(),
        discord.ui.ActionRow(PantheonKingdomSelect(options, picked).item),
    )


def _compare_buttons(strings: dict[str, str], base: str, names: dict[str, str]) -> list[Any]:
    """Build one « compare with » button per other kingdom (max 20)."""
    buttons: list[Any] = []
    for kid, name in list(names.items())[:20]:
        if str(kid) == str(base):
            continue
        buttons.append(
            PantheonCompareButton(
                strings["pantheon_chronique_compare_button"].format(name[:40]), base, kid
            ).item
        )
    return buttons


async def _chronique_window(strings: dict[str, str], kingdom_id: str) -> discord.ui.LayoutView:
    """One kingdom's timeline + the comparison row."""
    stack = wiring()
    names = await _kingdom_names()
    entries = await _timeline(stack, kingdom_id)
    lines = [_entry_line(strings, entry) for entry in entries]
    if not lines:
        lines = [strings["pantheon_chronique_empty"]]
    buttons = _compare_buttons(strings, kingdom_id, names)
    items: list[discord.ui.Item[discord.ui.LayoutView]] = [
        discord.ui.TextDisplay(
            f"# {strings['pantheon_chronique_kingdom'].format(names.get(kingdom_id, kingdom_id))}"
        ),
        discord.ui.Separator(),
        discord.ui.TextDisplay(_paginate(lines)[0]),
    ]
    if buttons:
        items.append(discord.ui.ActionRow(*buttons))
    return surface("panel:mod:kingdom:pantheon:chronique", *items)


class PantheonChroniqueButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]], template=r"kingdom:pantheon:chronique$"
):
    """The 📜 Chronique navigation (restart-proof)."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80], custom_id="kingdom:pantheon:chronique", style=discord.ButtonStyle.secondary
            )
        )

    @classmethod
    async def from_custom_id(
        cls, interaction: discord.Interaction, item: Any, match: re.Match[str], /
    ) -> PantheonChroniqueButton:
        return cls(_pantheon_strings(interaction)["pantheon_chronique_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        await open_unique_ephemeral(
            interaction, view=await _chronique_view(_pantheon_strings(interaction))
        )


class PantheonKingdomSelect(
    discord.ui.DynamicItem[discord.ui.Select[Any]],
    template=r"kingdom:pantheon:kingdom:(?P<kid>[A-Za-z0-9_:-]+)",
):
    """Build the kingdom picker of the Chronique window."""

    def __init__(self, options: list[discord.SelectOption], kid: str = "") -> None:
        # same rule as the season select: never an EMPTY template param
        select = discord.ui.Select(
            custom_id=f"kingdom:pantheon:kingdom:{kid or '-'}"[:100],
            placeholder="…",
            options=options or [discord.SelectOption(label="—", value="-")],
        )
        super().__init__(select)
        self.kingdom_id = kid

    @classmethod
    async def from_custom_id(
        cls, interaction: discord.Interaction, item: Any, match: re.Match[str], /
    ) -> PantheonKingdomSelect:
        return cls([], "" if match["kid"] == "-" else match["kid"])

    async def callback(self, interaction: discord.Interaction) -> None:
        strings_map = _pantheon_strings(interaction)
        view = await _chronique_window(strings_map, self.kingdom_id)
        await open_unique_ephemeral(interaction, view=view)


class PantheonCompareButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:pantheon:compare:(?P<a>[A-Za-z0-9_:-]+):(?P<b>[A-Za-z0-9_:-]+)",
):
    """One « compare with X » button of the Chronique window."""

    def __init__(self, label: str, base: str, other: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=f"kingdom:pantheon:compare:{base}:{other}"[:100],
                style=discord.ButtonStyle.primary,
            )
        )
        self.base = base
        self.other = other

    @classmethod
    async def from_custom_id(
        cls, interaction: discord.Interaction, item: Any, match: re.Match[str], /
    ) -> PantheonCompareButton:
        return cls("⚖️", match["a"], match["b"])

    async def callback(self, interaction: discord.Interaction) -> None:
        strings_map = _pantheon_strings(interaction)
        view = await _compare_window(strings_map, self.base, self.other)
        await open_unique_ephemeral(interaction, view=view)


async def _compare_window(
    strings: dict[str, str], base: str, other: str
) -> discord.ui.LayoutView:
    """Build the crossed chronicle of two kingdoms, one merged timeline.

    Chaque ligne porte le nom du royaume dont elle vient, et les
    événements CROISÉS (ceux dont les paramètres citent l'autre
    royaume par son nom) sont marqués : on lit le duel des deux
    points de vue (Drasah 26/11).
    """
    stack = wiring()
    names = await _kingdom_names()
    base_name = names.get(base, base)
    other_name = names.get(other, other)
    merged: list[tuple[int, str, str, str, dict[str, str]]] = []
    for kid, tag in ((base, base_name), (other, other_name)):
        for at, lord, kind, params in await _timeline(stack, kid):
            merged.append((at, tag, lord, kind, params))
    merged.sort(key=lambda item: item[0])
    lines: list[str] = []
    for at, tag, lord, kind, params in merged:
        line = f"**{tag}** · " + _entry_line(strings, (at, lord, kind, params))
        if other_name in params.values() or base_name in params.values():
            line += strings["pantheon_chronique_cross"]
        lines.append(line)
    if not lines:
        lines = [strings["pantheon_chronique_empty"]]
    return surface(
        "panel:mod:kingdom:pantheon:compare",
        discord.ui.TextDisplay(
            f"# {strings['pantheon_compare_title'].format(base_name, other_name)}"
        ),
        discord.ui.Separator(),
        discord.ui.TextDisplay(_paginate(lines)[0]),
    )


# ---------------------------------------------------------------------------
# Paging (the scriptorium's rule, never past Discord's 2000)
# ---------------------------------------------------------------------------
def _paginate(lines: list[str], max_chars: int = _PAGE_CHARS) -> list[str]:
    """Split one window.s lines into pages Discord accepts."""
    pages: list[str] = []
    batch: list[str] = []
    used = 0
    for line in lines:
        cost = len(line) + (1 if batch else 0)
        if batch and used + cost > max_chars:
            pages.append("\n".join(batch))
            batch, used = [], 0
        batch.append(line)
        used += cost
    if batch or not pages:
        pages.append("\n".join(batch))
    return pages


def pantheon_dynamic_items() -> tuple:
    """Return the module.s restart-proof items (registered by the cog)."""
    return (
        PantheonPalmaresButton,
        PantheonHistoriqueButton,
        PantheonChroniqueButton,
        PantheonSeasonSelect,
        PantheonKingdomSelect,
        PantheonCompareButton,
    )


# ---------------------------------------------------------------------------
# panthéon-manuel-v1 (Drasah 26/11) : le salon se CRÉE depuis l'atelier
# ---------------------------------------------------------------------------
def _decl_registry(bot: Any, mod_name: str) -> Any:
    """Return the mod's definition from the registry (None-safe)."""
    registry = getattr(bot, "registry", None)
    return registry.get(mod_name) if registry is not None else None


def _pantheon_decl(bot: Any) -> Any:
    """Return the mod's declared panthéon salon (the declaration is data)."""
    definition = _decl_registry(bot, "kingdom")
    for channel in getattr(definition, "channel_categories", ()) or ():
        if str(getattr(channel, "key", "")) == PANTHEON_CHANNEL_KEY:
            return channel
    return None


async def _pantheon_overwrites(bot: Any, guild: Any) -> dict[str, Any]:
    """Build the salon's overwrites from the DECLARED policy (data, #216)."""
    overwrites: dict[str, Any] = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
    }
    # the bot's own member always carries an explicit operating allow
    me = getattr(guild, "me", None)
    if me is not None:
        overwrites[me] = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True
        )
    decl = _pantheon_decl(bot)
    policy = getattr(decl, "access", None)
    roles_service = getattr(bot, "mod_roles_service", None)
    role_keys_by_name = {
        str(getattr(role, "display_name", "")): str(getattr(role, "key", ""))
        for role in getattr(_decl_registry(bot, "kingdom"), "roles", ()) or ()
    }
    for name in getattr(policy, "view", ()) or ():
        if roles_service is None:
            break
        role_key = role_keys_by_name.get(str(name), "")
        if not role_key:
            logger.warning("kingdom: pantheon — the view role %r is not declared", name)
            continue
        role_id = await roles_service.resolve_role_id(str(guild.id), "kingdom", role_key)
        role = guild.get_role(int(role_id)) if role_id and str(role_id).isdigit() else None
        if role is not None:
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=not getattr(policy, "everyone_post", False),
                read_message_history=True,
            )
    return overwrites


async def add_pantheon_salon(bot: Any, guild: Any) -> tuple[str, str]:
    """Create (or find) the panthéon salon — top of the sidebar, no category.

    Returns ``(channel_id, "created" | "exists")``. The salon is MANUAL
    (panthéon-manuel-v1, Drasah 26/11): it never rides the provisioning —
    the atelier creates it once, TOUT EN HAUT hors catégorie, and the
    organiser then drags it wherever he wants: the resolution is by
    STORED ID, so the pin and every wiring follow the move.
    """
    from botforge.discord.ui.panels_provisioning import (
        persist_resolutions,
        stored_channel_id,
    )

    guild_id = str(guild.id)
    stored = await stored_channel_id(guild_id, "mod/kingdom", PANTHEON_CHANNEL_KEY)
    if stored and stored.isdigit() and guild.get_channel(int(stored)) is not None:
        await ensure_pantheon_pin(bot, guild_id)
        return stored, "exists"
    decl = _pantheon_decl(bot)
    name = str(getattr(decl, "display_name", "🏛️ panthéon"))
    overwrites = await _pantheon_overwrites(bot, guild)
    channel = await guild.create_text_channel(
        name,
        overwrites=overwrites,
        reason="kingdom: panthéon-manuel-v1 (l'atelier crée la vitrine)",
    )
    try:  # best-effort : tout en haut, hors catégorie
        await channel.edit(position=0, reason="kingdom: panthéon — top of the sidebar")
    except discord.HTTPException:
        logger.warning("kingdom: pantheon top-position failed — best-effort", exc_info=True)
    await persist_resolutions(guild_id, "mod/kingdom", {PANTHEON_CHANNEL_KEY: str(channel.id)})
    await ensure_pantheon_pin(bot, guild_id)
    return str(channel.id), "created"


async def ensure_pantheon_pin(bot: Any, guild_id: str) -> None:
    """Ensure the panthéon panel lives in its salon (best-effort)."""
    from botforge.discord.static_pins import ensure_static_pin, registered_static_pins

    for spec in registered_static_pins():
        if spec.key == PANTHEON_PIN_KEY:
            try:
                await ensure_static_pin(bot, spec, guild_id)
            except Exception:
                logger.warning("kingdom: pantheon pin ensure failed — best-effort", exc_info=True)
            return


__all__ = [
    "PANTHEON_PIN_KEY",
    "build_pantheon_panel",
    "pantheon_dynamic_items",
]
