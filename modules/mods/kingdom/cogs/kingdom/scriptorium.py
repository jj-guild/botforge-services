"""The 📜 Scriptorium salon (Affaire 39, branché depuis la référence).

La référence portait le Scriptorium comme le pannier des rubriques
publiques : un sommaire épinglé (deploy par marker) + trois rubriques
ÉPHÉMÈRES paginées (🗺️ Cadastre, 🤝 Diplomatie, 🛡️ Seigneurie) + la
fiche seigneur cliquable (identité toujours visible, statut et
chronique GATED par le corbeau_track du royaume consultant, 24h).

Le portage (règles d'architecture) : la VUE reste la référence (les
lignes, le pager, la porte corbeau), les DONNÉES viennent des seams
du nouveau moteur — ``stack.config.maps`` (le cadastre 97 maps, tags
Drasah + bonus verbatim), ``stack.config.civilizations`` (les
conditions officielles, source de vérité), ``stack.kingdoms`` (les
royaumes, les seigneurs, les budgets), ``chronicle`` (les faits
d'armes, ``is_tracked_by``") et ``stack.territories`` (les terres
détenues). Le panneau est déployé par le static-pin core (le même
seam que le Marché — jamais d'envoi ad hoc) et chaque fenêtre est
une surface DÉCLARÉE (conf/views.yaml, #381 ruling 1).
"""

from __future__ import annotations

import logging
import re
from typing import Any

import discord

from .common import (
    lord_of,
    open_unique_ephemeral,
    strings_for,
    surface,
    wiring,
)
from .panel import _MAP_TAG_KEYS

logger = logging.getLogger("kingdom.scriptorium")

SCRIPTORIUM_PIN_KEY = "panel:mod:kingdom:scriptorium"
RUBRIC_TOPICS = ("cadastre", "diplomatie", "seigneurie")
_PAGE_CHARS = 1800
_CHRONICLE_TEMPLATES: dict[str, dict[str, str]] = {
    "fr": {
        "left": "quitte la saison.",
        "crowned": "👑 Couronné Roi de {kingdom}.",
        "enrolled_kingdom": "🎬 Rejoint {kingdom} comme seigneur.",
        "enrolled_queue": "⏳ Rejoint la file d'attente.",
        "marriage": "💍 Marié à la civilisation {civ} (palier Paroisse {tier}).",
        "arranged_marriage": "💍 Mariage arrangé avec {civ} (palier Paroisse {tier}).",
        "royal_marriage": "💍 Mariage royal (Reine) avec {civ} (palier Paroisse {tier}).",
        "attack_declared": "⚔️ Attaque déclarée sur {map} ({target}).",
        "embuscade": "⚔️ Embuscade déclarée sur {map} ({target}).",
        "defense": "🛡️ Pris la défense de {map}.",
        "pickban": "♟️ Pick & ban ({side}) sur {map}.",
        "attack_result": "⚔️ Attaque sur {map} : {outcome}.",
        "defense_result": "🛡️ Défense de {map} : {outcome}.",
        "restitution": "↩️ Restitution du budget d'attaque ({map}).",
        "ffa_joined": "🎲 Inscrit à la FFA Exploration du {date}.",
        "ffa_left": "🎲 Désistement de la FFA Exploration du {date}.",
        "ffa_result": "🎲 FFA Exploration du {date} : rang {rank}, {reward} ⚙️.",
        "bird_chosen": "🪶 Oiseau choisi : {bird}.",
        "voliere_action": "🪶 Action de volière : {action}.",
        "corbeau_theft": "🐦‍⬛ Vol de ⚙️ sur {target} ({points} ⚙️, {state}).",
        "corbeau_theft_stop": "🐦‍⬛ Vol sur {target} — STOP, {points} ⚙️ gardés.",
        "corbeau_theft_dead": "💀 Corbeau tué par la contestation de {target} — tout perdu.",
        "corbeau_contested": "🛡️ Contesté le vol du Corbeau de {thief}.",
        "market_purchase": "🛒 Achat au Marché : {item} ({cost} ⚙️).",
        "parish_upgrade": "⛪ Paroisse améliorée au palier {tier}.",
        "cathedral_consecrated": "⛪ Cathédrale consacrée sur {territory}.",
    },
    "en": {
        "left": "leaves the season.",
        "crowned": "👑 Crowned King of {kingdom}.",
        "enrolled_kingdom": "🎬 Joined {kingdom} as a lord.",
        "enrolled_queue": "⏳ Joined the waiting queue.",
        "marriage": "💍 Married the civilization {civ} (Parish tier {tier}).",
        "arranged_marriage": "💍 Arranged marriage with {civ} (Parish tier {tier}).",
        "royal_marriage": "💍 Royal wedding (Reine) with {civ} (Parish tier {tier}).",
        "attack_declared": "⚔️ Declared an attack on {map} ({target}).",
        "embuscade": "⚔️ Declared an Embuscade on {map} ({target}).",
        "defense": "🛡️ Took the defense of {map}.",
        "pickban": "♟️ Pick & ban ({side}) on {map}.",
        "attack_result": "⚔️ Attack on {map}: {outcome}.",
        "defense_result": "🛡️ Defense of {map}: {outcome}.",
        "restitution": "↩️ Attack budget restituted ({map}).",
        "ffa_joined": "🎲 Enrolled in the FFA Exploration of {date}.",
        "ffa_left": "🎲 Withdrew from the FFA Exploration of {date}.",
        "ffa_result": "🎲 FFA Exploration of {date}: rank {rank}, {reward} ⚙️.",
        "bird_chosen": "🪶 Bird chosen: {bird}.",
        "voliere_action": "🪶 Volière action: {action}.",
        "corbeau_theft": "🐦‍⬛ Corbeau theft on {target} ({points} ⚙️, {state}).",
        "corbeau_theft_stop": "🐦‍⬛ Corbeau theft on {target} — stopped, {points} ⚙️ kept.",
        "corbeau_theft_dead": "💀 Corbeau killed by the contest of {target} — everything lost.",
        "corbeau_contested": "🛡️ Contested the corbeau theft of {thief}.",
        "market_purchase": "🛒 Marché purchase: {item} ({cost} ⚙️).",
        "parish_upgrade": "⛪ Parish upgraded to tier {tier}.",
        "cathedral_consecrated": "⛪ Cathedral consecrated on {territory}.",
    },
}


def _locale(interaction: discord.Interaction) -> str:
    """The interaction locale (en fallback)."""
    value = str(getattr(interaction, "locale", "") or "")
    return value[:2] if value else "en"


# ---------------------------------------------------------------------------
# The pinned sommaire (deployed by the static-pin core seam)
# ---------------------------------------------------------------------------


async def build_scriptorium_panel(guild_id: str) -> discord.ui.LayoutView:
    """The pinned Scriptorium sommaire — the three rubric buttons."""
    from .panel import _guild_locale
    from .strings import strings

    locale = await _guild_locale(guild_id)
    strings_map = strings(locale[:2])
    return surface(
        SCRIPTORIUM_PIN_KEY,
        discord.ui.TextDisplay(f"# {strings_map['scriptorium_title']}"),
        discord.ui.TextDisplay(strings_map["scriptorium_intro"]),
        discord.ui.Separator(),
        discord.ui.ActionRow(
            *[
                ScriptoriumRubricButton(topic, strings_map[f"scriptorium_topic_{topic}"])
                for topic in RUBRIC_TOPICS
            ]
        ),
    )


# ---------------------------------------------------------------------------
# The rubric content (read-only views over the engine seams)
# ---------------------------------------------------------------------------


def _map_line(strings: dict[str, str], entry: Any) -> str:
    """One Cadastre line: the map, its Drasah tags, its bonus verbatim."""
    name = str(getattr(entry, "display_name", getattr(entry, "key", "?")))
    types = getattr(entry, "types", None)
    tags = [icon for key, icon in _MAP_TAG_KEYS if bool(getattr(types, key, False))]
    bonus = str((getattr(entry, "cadastre", None) or {}).get("bonus", "") or "")
    line = f"- **{name}**"
    if tags:
        line += f" — {' '.join(tags)}"
    if bonus:
        line += f" — {bonus}"
    return line


def _cadastre_lines(strings: dict[str, str], stack: Any) -> list[str]:
    """The Cadastre rubric: the map catalog, tags and textual bonus."""
    maps = list(getattr(stack.config, "maps", ()) or ())
    lines = [f"# {strings['scriptorium_cadastre_title']}", "", strings["scriptorium_cadastre_intro"], ""]
    if not maps:
        lines.append(strings["scriptorium_cadastre_empty"])
        return lines
    lines.extend(_map_line(strings, entry) for entry in maps)
    return lines


def _map_keys_condition(strings: dict[str, str], civ: Any, by_name: dict[str, str]) -> str | None:
    """The map(-count) leg of the condition (None when unset)."""
    keys = tuple(getattr(civ, "requires_map_keys", ()) or ())
    if not keys:
        return None
    names = ", ".join(by_name.get(str(key), str(key)) for key in keys)
    count = int(getattr(civ, "min_map_key_count", 1) or 1)
    if count <= 1:
        return str(strings["scriptorium_condition_map"]).format(maps=names)
    return str(strings["scriptorium_condition_map_count"]).format(count=count, maps=names)


def _map_types_condition(strings: dict[str, str], civ: Any) -> str | None:
    """The map-type leg of the condition (None when unset)."""
    types_ = tuple(getattr(civ, "requires_map_types", ()) or ())
    if not types_:
        return None
    return str(strings["scriptorium_condition_map_type"]).format(
        count=int(getattr(civ, "min_map_type_count", 1) or 1),
        types=", ".join(str(t) for t in types_),
    )


def _condition_text(strings: dict[str, str], civ: Any, by_name: dict[str, str]) -> str:
    """One civilization's OFFICIAL acquisition condition (Diplomatie = truth)."""
    conditions: list[str] = []
    for leg in (
        _map_keys_condition(strings, civ, by_name),
        _map_types_condition(strings, civ),
    ):
        if leg:
            conditions.append(leg)
    if getattr(civ, "min_map_count", None) is not None:
        conditions.append(
            str(strings["scriptorium_condition_min_maps"]).format(count=int(civ.min_map_count))
        )
    if getattr(civ, "max_map_count", None) is not None:
        conditions.append(
            str(strings["scriptorium_condition_max_maps"]).format(count=int(civ.max_map_count))
        )
    if getattr(civ, "requires_civilization", None):
        name = by_name.get(str(civ.requires_civilization), str(civ.requires_civilization))
        conditions.append(str(strings["scriptorium_condition_civ"]).format(civ=name))
    if getattr(civ, "requires_kingdom_name_pattern", None):
        conditions.append(
            str(strings["scriptorium_condition_pattern"]).format(
                pattern=str(civ.requires_kingdom_name_pattern)
            )
        )
    if getattr(civ, "requires_tech_points", None) is not None:
        conditions.append(
            str(strings["scriptorium_condition_tech"]).format(count=int(civ.requires_tech_points))
        )
    if getattr(civ, "requires_marriages", None) is not None:
        conditions.append(
            str(strings["scriptorium_condition_marriages"]).format(
                count=int(civ.requires_marriages)
            )
        )
    if getattr(civ, "requires_civilization_count", None) is not None:
        conditions.append(
            str(strings["scriptorium_condition_civ_count"]).format(
                count=int(civ.requires_civilization_count)
            )
        )
    return " · ".join(conditions)


def _diplomatie_lines(strings: dict[str, str], stack: Any) -> list[str]:
    """The Diplomatie rubric: civilizations + official conditions."""
    catalog = list(getattr(stack.config, "civilizations", ()) or ())
    by_name = {
        str(getattr(civ, "key", "")): str(getattr(civ, "display_name", civ.key))
        for civ in catalog
    }
    lines = [
        f"# {strings['scriptorium_diplomatie_title']}",
        "",
        strings["scriptorium_diplomatie_intro"],
        "",
    ]
    if not catalog:
        lines.append(strings["scriptorium_diplomatie_empty"])
        return lines
    for civ in catalog:
        name = str(getattr(civ, "display_name", getattr(civ, "key", "?")))
        condition = _condition_text(strings, civ, by_name)
        lines.append(f"- **{name}** — {condition}" if condition else f"- **{name}**")
    return lines


def _budget_line(strings: dict[str, str], member: Any, attack_budget: int, defense_budget: int, now_ts: int) -> str:
    """One Seigneurie member line: remaining budgets + live lock stamps."""
    attack_left = max(0, attack_budget - int(getattr(member, "attack_used", 0) or 0))
    defense_left = max(0, defense_budget - int(getattr(member, "defense_used", 0) or 0))
    line = f" — ⚔️ {attack_left}/{attack_budget} · 🛡️ {defense_left}/{defense_budget}"
    for emoji, until in (
        ("💍", getattr(member, "marriage_locked_until", None)),
        ("🧭", getattr(member, "exploration_locked_until", None)),
        ("🍺", getattr(member, "tavern_locked_until", None)),
        ("🎲", getattr(member, "ffa_locked_until", None)),
    ):
        locked_until = int(until or 0)
        if locked_until > now_ts:
            line += f" · {emoji} <t:{locked_until}:R>"
    return line


async def _seigneurie_lines(
    strings: dict[str, str], stack: Any, kingdoms: list[Any], lords: list[Any]
) -> list[str]:
    """The Seigneurie rubric: every lord per kingdom, remaining budgets."""
    from botforge.mods.kingdom.game_clock import game_now

    now_ts = int(game_now().timestamp())
    attacks = getattr(stack.config, "attacks", None)
    attack_budget = int(getattr(attacks, "attacks_per_week", 1) or 1)
    defense_budget = int(getattr(attacks, "defenses_per_week", 1) or 1)
    lines = [
        f"# {strings['scriptorium_seigneurie_title']}",
        "",
        strings["scriptorium_seigneurie_intro"],
        "",
    ]
    active = [lord for lord in lords if not getattr(lord, "left", False)]
    named = [k for k in kingdoms if not getattr(k, "is_gaia", False)]
    if not named:
        lines.append(strings["scriptorium_seigneurie_empty"])
        return lines
    for kingdom in sorted(named, key=lambda k: str(k.name)):
        members = [
            lord
            for lord in active
            if str(getattr(lord, "kingdom_id", "")) == str(kingdom.id)
            and not getattr(lord, "in_queue", False)
        ]
        king = next(
            (m for m in members if str(getattr(m.role, "value", m.role)) == "king"), None
        )
        if king is not None:
            lines.append(
                f"**{kingdom.name}**\n- 👑 {strings['scriptorium_seigneurie_king']} :"
                f" {king.display_name}{_budget_line(strings, king, attack_budget, defense_budget, now_ts)}"
            )
        else:
            lines.append(f"**{kingdom.name}**\n- 👑 {strings['scriptorium_seigneurie_king']} : —")
        for member in members:
            if king is not None and str(member.id) == str(king.id):
                continue
            lines.append(
                f"  - 🎖️ {member.display_name}"
                f"{_budget_line(strings, member, attack_budget, defense_budget, now_ts)}"
            )
        lines.append("")
    waiting = [lord for lord in active if getattr(lord, "in_queue", False)]
    if waiting:
        names = ", ".join(lord.display_name for lord in waiting)
        lines.append(f"⏳ {strings['scriptorium_seigneurie_pending']} : {names}")
    return lines


def paginate(lines: list[str], max_chars: int = _PAGE_CHARS) -> list[str]:
    """Split one rubric into pages Discord accepts (never past 2000)."""
    flat: list[str] = []
    for line in lines:
        flat.extend(line[start : start + max_chars] for start in range(0, max(len(line), 1), max_chars))
    pages: list[str] = []
    batch: list[str] = []
    used = 0
    for line in flat:
        cost = len(line) + (1 if batch else 0)
        if batch and used + cost > max_chars:
            pages.append("\n".join(batch))
            batch, used = [], 0
        batch.append(line)
        used += cost
    pages.append("\n".join(batch))
    return pages


async def _rubric_pages(topic: str, strings: dict[str, str], stack: Any) -> list[str]:
    """One rubric's live content, paginated under Discord's limit."""
    if topic == "cadastre":
        return paginate(_cadastre_lines(strings, stack))
    if topic == "diplomatie":
        return paginate(_diplomatie_lines(strings, stack))
    kingdoms = await stack.kingdoms.kingdoms()
    lords = await stack.kingdoms.lords()
    return paginate(await _seigneurie_lines(strings, stack, kingdoms, lords))


# ---------------------------------------------------------------------------
# The fiche seigneur (identity always; status + chronique gated by corbeau)
# ---------------------------------------------------------------------------


def _chronicle_line(locale: str, entry: Any) -> str:
    """Render one chronicle entry, timestamped (Discord's native <t:…:f>)."""
    templates = _CHRONICLE_TEMPLATES["fr" if locale.lower().startswith("fr") else "en"]
    params = {str(k): str(v) for k, v in (getattr(entry, "params", {}) or {}).items()}
    kind = str(getattr(entry, "kind", ""))
    if kind == "enrolled":
        template = templates[
            "enrolled_queue" if params.get("status") == "queue" else "enrolled_kingdom"
        ]
    else:
        template = templates.get(kind)
    if template is None:  # pragma: no cover — forward compatibility
        template = f"{kind} {params}".strip()
    known = {k: v for k, v in params.items() if k in template}
    return f"<t:{int(getattr(entry, 'at', 0))}:f> — {template.format(**known)}"


def _fiche_identity(strings: dict[str, str], lord: Any, kingdom: Any) -> str:
    """The ALWAYS-visible identity block (Drasah's gating floor)."""
    is_king = str(getattr(lord, "role", "lord")) == "king"
    role = strings["scriptorium_seigneurie_king" if is_king else "scriptorium_seigneurie_lords"]
    insight = str(getattr(lord, "insight_name", None) or strings["scriptorium_unknown"])
    kingdom_name = str(getattr(kingdom, "name", None) or strings["scriptorium_unknown"])
    return str(strings["scriptorium_fiche_identity"]).format(
        name=str(getattr(lord, "display_name", "?")),
        insight=insight,
        kingdom=kingdom_name,
        role=role,
    )


async def _fiche_body(
    strings: dict[str, str], locale: str, stack: Any, lord_id: str, consultant: Any
) -> str:
    """One lord's fiche — the corbeau_track gate (15/10, Drasah's rule)."""
    from botforge.mods.kingdom import chronicle
    from botforge.mods.kingdom.game_clock import game_now

    lords = await stack.kingdoms.lords()
    lord = next((item for item in lords if str(item.id) == str(lord_id)), None)
    if lord is None:
        return strings["scriptorium_unknown"]
    kingdoms = await stack.kingdoms.kingdoms()
    kingdom = next(
        (k for k in kingdoms if str(k.id) == str(getattr(lord, "kingdom_id", ""))), None
    )
    lines = [str(strings["scriptorium_fiche_title"]).format(name=str(lord.display_name))]
    lines.append(_fiche_identity(strings, lord, kingdom))
    consultant_kingdom = None
    if consultant is not None:
        consultant_kingdom = next(
            (
                k
                for k in kingdoms
                if str(k.id) == str(getattr(consultant, "kingdom_id", "") or "")
            ),
            None,
        )
    tracked = consultant_kingdom is not None and chronicle.is_tracked_by(
        consultant_kingdom, str(lord.id), game_now()
    )
    if not tracked:
        lines.append(strings["scriptorium_fiche_gated"])
        return "\n".join(lines)
    territory_count = 0
    try:
        territories = await stack.territories.territories()
        territory_count = len(
            [
                t
                for t in territories
                if str(getattr(t, "owner_kingdom_id", "")) == str(lord.kingdom_id)
            ]
        )
    except Exception:
        territory_count = 0
    lines.append(strings["scriptorium_fiche_tracked"])
    lines.append(f"**{strings['scriptorium_fiche_status']}**")
    married = getattr(lord, "married_civilization", None)
    if married:
        lines.append(str(strings["scriptorium_fiche_married"]).format(civ=str(married)))
    secured = [str(civ) for civ in (getattr(kingdom, "secured_civilizations", []) or [])]
    if secured:
        lines.append(str(strings["scriptorium_fiche_secured"]).format(civs=", ".join(secured)))
    lines.append(str(strings["scriptorium_fiche_territories"]).format(count=territory_count))
    lines.append(
        str(strings["scriptorium_fiche_parish"]).format(
            tier=int(getattr(kingdom, "parish_tier", 1) or 1)
        )
    )
    entries = chronicle.recent(lord, 3)
    if entries:
        lines.append(f"**{strings['scriptorium_fiche_chronicle']}**")
        lines.extend(_chronicle_line(locale, entry) for entry in entries)
        total = len(getattr(lord, "chronicle", []) or [])
        if total > len(entries):
            lines.append(
                str(strings["scriptorium_fiche_chronicle_more"]).format(count=total - len(entries))
            )
    return "\n".join(lines)


def _history_body(strings: dict[str, str], locale: str, lord: Any) -> str:
    """The FULL dépliable chronicle, newest first, under Discord's 2000."""
    from botforge.mods.kingdom import chronicle

    lines = [
        str(strings["scriptorium_fiche_history"]).format(
            name=str(getattr(lord, "display_name", "?"))
        )
    ]
    for entry in chronicle.recent(lord, chronicle.CHRONICLE_CAP):
        line = _chronicle_line(locale, entry)
        if sum(len(item) + 1 for item in lines) + len(line) + 200 > 2000:
            break
        lines.append(line)
    return "\n".join(lines)


async def _fiche_view(
    strings: dict[str, str],
    locale: str,
    stack: Any,
    lord_id: str,
    consultant: Any,
) -> discord.ui.LayoutView:
    """The fiche window: identity + (gated) status & chronique + history."""
    body = await _fiche_body(strings, locale, stack, lord_id, consultant)
    items: list[Any] = [discord.ui.TextDisplay(body)]
    lords = await stack.kingdoms.lords()
    target = next((item for item in lords if str(item.id) == str(lord_id)), None)
    if target is not None and getattr(target, "chronicle", None):
        history_button: discord.ui.Button[Any] = discord.ui.Button(
            label=str(strings["scriptorium_fiche_history_button"])[:80],
            style=discord.ButtonStyle.secondary,
            custom_id=f"kingdom:scriptorium:fichhist:{lord_id}",
        )

        async def on_history(target_inter: discord.Interaction) -> None:
            await open_unique_ephemeral(
                target_inter, content=_history_body(strings, locale, target)
            )

        history_button.callback = on_history  # type: ignore[method-assign]
        items.append(discord.ui.ActionRow(history_button))
    return surface("panel:mod:kingdom:scriptorium:fiche", *items)


# ---------------------------------------------------------------------------
# The rubric windows (ephemeral, paginated; the fiche select rides Seigneurie)
# ---------------------------------------------------------------------------


async def _rubric_view(
    topic: str,
    interaction: discord.Interaction,
    strings: dict[str, str],
    locale: str,
    page: int = 0,
) -> discord.ui.LayoutView:
    """One rubric's ephemeral window — page ``page`` of the live pages."""
    stack = wiring()
    pages = await _rubric_pages(topic, strings, stack)
    page = max(0, min(page, len(pages) - 1))
    items: list[Any] = [discord.ui.TextDisplay(pages[page])]
    if len(pages) > 1:
        prev_button: discord.ui.Button[Any] = discord.ui.Button(
            label="◀️",
            style=discord.ButtonStyle.secondary,
            disabled=page == 0,
            custom_id=f"kingdom:scriptorium:page:{topic}:{page - 1}",
        )
        next_button: discord.ui.Button[Any] = discord.ui.Button(
            label="▶️",
            style=discord.ButtonStyle.secondary,
            disabled=page >= len(pages) - 1,
            custom_id=f"kingdom:scriptorium:page:{topic}:{page + 1}",
        )

        async def _turn(target: discord.Interaction, target_page: int) -> None:
            view = await _rubric_view(topic, target, strings, locale, target_page)
            await open_unique_ephemeral(target, view=view)

        prev_button.callback = (  # type: ignore[method-assign]
            lambda target, p=page - 1: _turn(target, p)
        )
        next_button.callback = (  # type: ignore[method-assign]
            lambda target, p=page + 1: _turn(target, p)
        )
        counter: discord.ui.Button[Any] = discord.ui.Button(
            label=f"{page + 1}/{len(pages)}",
            style=discord.ButtonStyle.secondary,
            disabled=True,
            custom_id=f"kingdom:scriptorium:page:{topic}:counter",
        )
        items.append(discord.ui.ActionRow(prev_button, counter, next_button))
    if topic == "seigneurie":
        select = await _fiche_select(interaction, strings, locale, stack)
        if select is not None:
            items.append(discord.ui.ActionRow(select))
    return surface(f"panel:mod:kingdom:scriptorium:{topic}", *items)


async def _fiche_select(
    interaction: discord.Interaction,
    strings: dict[str, str],
    locale: str,
    stack: Any,
) -> discord.ui.Select[Any] | None:
    """The fiche selector of the Seigneurie rubric (max 25)."""
    kingdoms = await stack.kingdoms.kingdoms()
    lords = await stack.kingdoms.lords()
    names = {str(k.id): str(k.name) for k in kingdoms if not getattr(k, "is_gaia", False)}
    options: list[discord.SelectOption] = []
    for lord in lords:
        if len(options) >= 25:
            break
        if getattr(lord, "left", False) or getattr(lord, "in_queue", False):
            continue
        options.append(
            discord.SelectOption(
                label=str(lord.display_name)[:100],
                value=str(lord.id)[:100],
                description=names.get(str(getattr(lord, "kingdom_id", "")), "?")[:100],
            )
        )
    if not options:
        return None
    select: discord.ui.Select[Any] = discord.ui.Select(
        custom_id="kingdom:scriptorium:fichselect",
        placeholder=str(strings["scriptorium_fiche_choose"])[:100],
        options=options,
    )

    async def on_pick(target: discord.Interaction) -> None:
        values = getattr(target, "data", None) or {}
        chosen = [str(v) for v in values.get("values", [])]
        if not chosen:
            return
        consultant = await lord_of(stack.kingdoms, str(target.user.id), target)
        view = await _fiche_view(strings, locale, stack, chosen[0], consultant)
        await open_unique_ephemeral(target, view=view)

    select.callback = on_pick  # type: ignore[method-assign]
    return select


# ---------------------------------------------------------------------------
# The persistent rubric button (restart-proof DynamicItem)
# ---------------------------------------------------------------------------


class ScriptoriumRubricButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=r"kingdom:scriptorium:rubric:(?P<topic>cadastre|diplomatie|seigneurie)",
):
    """One rubric button of the pinned Scriptorium sommaire."""

    def __init__(self, topic: str, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=f"kingdom:scriptorium:rubric:{topic}",
                style=discord.ButtonStyle.secondary,
            )
        )
        self.topic = topic

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> ScriptoriumRubricButton:
        strings = strings_for(interaction)
        return cls(str(match.group("topic")), strings[f"scriptorium_topic_{match.group('topic')}"])

    async def callback(self, interaction: discord.Interaction) -> None:
        strings = strings_for(interaction)
        locale = _locale(interaction)
        stack = wiring()
        if stack is None:
            await open_unique_ephemeral(interaction, content=strings["plan_no_service"])
            return
        try:
            view = await _rubric_view(self.topic, interaction, strings, locale)
        except Exception:
            logger.warning("SCRIPTORIUM: rubric build failed", exc_info=True)
            await open_unique_ephemeral(interaction, content=strings["scriptorium_unknown"])
            return
        await open_unique_ephemeral(interaction, view=view)


def scriptorium_dynamic_items() -> tuple:
    """The module's restart-proof items (registered by the cog)."""
    return (ScriptoriumRubricButton,)


__all__ = [
    "RUBRIC_TOPICS",
    "SCRIPTORIUM_PIN_KEY",
    "build_scriptorium_panel",
    "paginate",
    "scriptorium_dynamic_items",
]
