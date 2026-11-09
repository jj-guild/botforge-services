"""Entity cards: the shared Components V2 templates for catalog posts.

One builder per surface family — map, pool, faction (civ), and the
generic entity card the mods reuse (kingdoms territories, ladder
objects, ...). Every card follows the same contract:

* a header Section (title, optional thumbnail accessory) — a Section
  holds at most 3 text children (Discord 50035), so the header is a
  single text block by construction;
* property lines (one setting per line) behind no divider;
* a divider, the description, the media, the cross-links, the source
  link, and the id as the small footer — each block behind a divider;
* an action row (the surface's buttons, persistent DynamicItems).

The builders are game/mod-agnostic: they take plain strings and
return items; the callers (the games forums, the mods' forums) own
the data and the buttons. No game or mod imports here.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

import discord

ACCENT = 0x5865F2

# Discord rejects a V2 message whose total displayable text (every
# TextDisplay + button label) crosses 4000 characters (50035). The
# description is the only unbounded block on a card — everything else
# is built from short, bounded fields — so the budget is enforced by
# clamping the description, never by letting the send fail.
TEXT_BUDGET = 4000
# The callers may add text on top of the card (the admin preview's
# banner) and the buttons' labels count too: a flat headroom keeps
# the card safe for every consumer.
BUDGET_HEADROOM = 256
_TRUNCATION_MARK = "\n\u2026 *(description tronqu\u00e9e \u2014 la suite sur la page source)*"
# Each kept paragraph becomes its own TextDisplay: the clamp also
# respects Discord's 40-component cap (a very fragmented description
# would otherwise blow the component budget before the text one).
MAX_DESCRIPTION_PARAGRAPHS = 12


def _fixed_text(spec: EntityCardSpec) -> int:
    """Measure the card's displayable text WITHOUT the description block."""
    total = len(f"## {spec.title[:1].upper()}{spec.title[1:]}")
    if spec.subtitle:
        total += len(f"_{spec.subtitle}_")
    if spec.props:
        total += len("\n".join(spec.props))
    if spec.links:
        if spec.links_heading:
            total += len(f"**{spec.links_heading}**\n")
        total += len("\n".join(spec.links))
    if spec.versions:
        lines = [
            f"\u2022 **{v['name']}** \u2014 {v['description']}" if v.get("description") else f"\u2022 **{v['name']}**"
            for v in spec.versions
        ]
        total += len("\n".join(["**Variantes**", *lines]))
    if spec.creator:
        total += len(f"Cr\u00e9ateur : {spec.creator}")
    if spec.source_url:
        total += len(f"Source : [{spec.source_label}]({spec.source_url})")
    total += len(f"-# `{spec.view_id or spec.entity_id}`")
    return total


def _clamped_spec(spec: EntityCardSpec) -> EntityCardSpec:
    """Return the spec with its description fitted into the text budget.

    A description that would cross the budget is cut on a paragraph
    boundary (a subsection title never separates from its content) and
    ends with an explicit truncation marker — a shortened card is
    always visibly shortened, never silently shorter.
    """
    allowed = TEXT_BUDGET - BUDGET_HEADROOM - _fixed_text(spec) - len(_TRUNCATION_MARK)
    if len(spec.description) <= allowed:
        return spec
    if allowed < 0:
        allowed = 0
    kept: list[str] = []
    total = 0
    for paragraph in spec.description.split("\n\n"):
        cost = len(paragraph) + 2
        if total + cost > allowed or len(kept) >= MAX_DESCRIPTION_PARAGRAPHS:
            break
        kept.append(paragraph)
        total += cost
    body = "\n\n".join(kept) if kept else spec.description[:allowed]
    return replace(spec, description=body + _TRUNCATION_MARK)


@dataclass(frozen=True)
class EntityCardSpec:
    """One catalog card's content, game/mod-agnostic."""

    title: str
    entity_id: str
    subtitle: str = ""
    view_id: str = ""
    props: tuple[str, ...] = ()
    description: str = ""
    image_url: str = ""
    icon_url: str = ""
    gallery_images: tuple[str, ...] = ()
    source_url: str = ""
    source_label: str = "Liquipedia"
    creator: str = ""
    creator_url: str = ""
    versions: tuple[dict[str, str], ...] = ()
    links_heading: str = ""
    links: tuple[str, ...] = ()
    action_buttons: tuple[
        Callable[[], discord.ui.Item[discord.ui.LayoutView]]
        | discord.ui.ActionRow[discord.ui.LayoutView]
        | discord.ui.DynamicItem[Any],
        ...
    ] = field(
        default_factory=tuple
    )


def _header_blocks(spec: EntityCardSpec) -> list[discord.ui.Item[discord.ui.LayoutView]]:
    """Build the header section's blocks: title, subtitle, the in-game icon."""
    blocks: list[discord.ui.Item[discord.ui.LayoutView]] = [
        discord.ui.TextDisplay(f"## {spec.title[:1].upper()}{spec.title[1:]}")
    ]
    if spec.subtitle:
        blocks.append(discord.ui.TextDisplay(f"_{spec.subtitle}_"))
    return blocks


def _header(spec: EntityCardSpec) -> discord.ui.Item[discord.ui.LayoutView]:
    """Build the header section: the title block with the icon as the thumbnail."""
    blocks = _header_blocks(spec)
    if spec.icon_url:
        return discord.ui.Section(*blocks, accessory=discord.ui.Thumbnail(spec.icon_url))
    return discord.ui.Container(*blocks)


def _description_blocks(spec: EntityCardSpec) -> list[discord.ui.Item[discord.ui.LayoutView]]:
    """Build the description's blocks.

    The props line, then each paragraph behind a separator
    (owner direction 2026-11-08).
    """
    body: list[discord.ui.Item[discord.ui.LayoutView]] = []
    if spec.props:
        body.append(discord.ui.TextDisplay("\n".join(spec.props)))
    # the paragraphs (double newline): a subsection title rides WITH
    # its content in one block — the separator never isolates a title
    for block in spec.description.split("\n\n"):
        if not block.strip():
            continue
        if body:
            body.append(discord.ui.Separator())
        body.append(discord.ui.TextDisplay(block))
    return body


def _media_blocks(spec: EntityCardSpec) -> list[discord.ui.Item[discord.ui.LayoutView]]:
    """Build the media gallery.

    The infobox image first, then EVERY gallery image
    (deduplicated, empties skipped).
    """
    seen: set[str] = set()
    media_urls: list[str] = []
    for url in (spec.image_url, *spec.gallery_images):
        if url and url not in seen:
            seen.add(url)
            media_urls.append(url)
    if not media_urls:
        return []
    return [
        discord.ui.MediaGallery(*[discord.MediaGalleryItem(u) for u in media_urls])
    ]


def _links_blocks(spec: EntityCardSpec) -> list[discord.ui.Item[discord.ui.LayoutView]]:
    """Build the cross-links block (the pools the map belongs to)."""
    if not spec.links:
        return []
    heading = f"**{spec.links_heading}**\n" if spec.links_heading else ""
    return [discord.ui.TextDisplay(heading + "\n".join(spec.links))]


def _versions_blocks(spec: EntityCardSpec) -> list[discord.ui.Item[discord.ui.LayoutView]]:
    """Build the variants block (the map's Versions section)."""
    if not spec.versions:
        return []
    lines = ["**Variantes**"]
    lines.extend(
        f"• **{v['name']}** — {v['description']}" if v.get("description") else f"• **{v['name']}**"
        for v in spec.versions
    )
    return [discord.ui.TextDisplay("\n".join(lines))]


def _credits_blocks(spec: EntityCardSpec) -> list[discord.ui.Item[discord.ui.LayoutView]]:
    """Build the credits: the creator just above the source."""
    blocks: list[discord.ui.Item[discord.ui.LayoutView]] = []
    if spec.creator:
        creator = f"[{spec.creator}]({spec.creator_url})" if spec.creator_url else spec.creator
        blocks.append(discord.ui.TextDisplay(f"Créateur : {creator}"))
    if spec.source_url:
        blocks.append(discord.ui.TextDisplay(f"Source : [{spec.source_label}]({spec.source_url})"))
    return blocks


def _body_blocks(spec: EntityCardSpec) -> list[discord.ui.Item[discord.ui.LayoutView]]:
    """Build the card's content blocks, each group behind a separator."""
    groups = [
        _description_blocks(spec),
        _media_blocks(spec),
        _links_blocks(spec),
        _versions_blocks(spec),
        _credits_blocks(spec),
    ]
    body: list[discord.ui.Item[discord.ui.LayoutView]] = []
    for group in groups:
        if not group:
            continue
        if body:
            body.append(discord.ui.Separator())
        body.extend(group)
    return body


def _actions(
    view: discord.ui.LayoutView,
    buttons: tuple[
        Callable[[], discord.ui.Item[discord.ui.LayoutView]]
        | discord.ui.ActionRow[discord.ui.LayoutView]
        | discord.ui.DynamicItem[Any],
        ...
    ],
) -> None:
    """Add the action rows, in the tuple's order.

    Three shapes ride the same seam: a factory builds a persistent
    item (the posts' persistent buttons), a prebuilt ActionRow lands as
    its own row (the admin menu's lifecycle row), and a DynamicItem
    instance joins the current row (the admin menu's persistent
    buttons — the 2026-11-07 pool-menu crash: they are not callable,
    and treating them as factories killed the menu render).
    """
    if not buttons:
        return
    rows: list[discord.ui.ActionRow[discord.ui.LayoutView]] = []
    current: list[discord.ui.DynamicItem[Any]] = []

    def _flush() -> None:
        if current:
            rows.append(_row_of(current))
            current.clear()

    for button in buttons:
        if isinstance(button, discord.ui.ActionRow):
            _flush()
            rows.append(button)
        elif isinstance(button, discord.ui.DynamicItem):
            current.append(button)
        else:
            _flush()
            rows.append(_row_of([button()]))
    _flush()
    for row in rows:
        view.add_item(row)


def _row_of(
    items: Sequence[discord.ui.DynamicItem[Any] | discord.ui.Item[Any]],
) -> discord.ui.ActionRow[discord.ui.LayoutView]:
    """One action row carrying these dynamic items."""
    row: discord.ui.ActionRow[discord.ui.LayoutView] = discord.ui.ActionRow()
    for item in items:
        row.add_item(item)
    return row


def build_entity_card(spec: EntityCardSpec) -> discord.ui.LayoutView:
    """Build one catalog card from its spec.

    The shared template: header (icon thumbnail) / props / description
    / media / cross-links / source / id footer / action row.
    """
    spec = _clamped_spec(spec)
    view = discord.ui.LayoutView(timeout=None)
    blocks: list[discord.ui.Item[discord.ui.LayoutView]] = [_header(spec)]
    body = _body_blocks(spec)
    if body:
        # a separator after the subtitle, before the content (owner
        # direction 2026-11-08)
        blocks.append(discord.ui.Separator())
    blocks.extend(body)
    view.add_item(discord.ui.Container(*blocks, accent_colour=discord.Colour(ACCENT)))
    _actions(view, spec.action_buttons)
    view.add_item(discord.ui.TextDisplay(f"-# `{spec.view_id or spec.entity_id}`"))
    return view


def map_card(
    map_id: str,
    name: str,
    props: tuple[str, ...],
    description: str,
    image_url: str,
    icon_url: str,
    source_url: str,
    pool_links: tuple[str, ...],
    buttons: tuple[Callable[[], discord.ui.Item[discord.ui.LayoutView]], ...],
    creator: str = "",
    gallery_images: tuple[str, ...] = (),
    creator_url: str = "",
    versions: tuple[dict[str, str], ...] = (),
) -> discord.ui.LayoutView:
    """Build a map's forum card on the shared template.

    The subtitle (owner direction 2026-11-08): the tags (the props
    line) then the map pools — the body carries the content only.
    """
    tags_line = " ".join(part for part in props if part)
    # the pools: one per line, never inline (owner direction 2026-11-08)
    subtitle = "\n".join(line for line in (tags_line, *pool_links) if line)
    return build_entity_card(
        EntityCardSpec(
            title=name,
            entity_id=map_id,
            subtitle=subtitle,
            view_id=f"panel:{map_id}",
            description=description,
            image_url=image_url,
            icon_url=icon_url,
            gallery_images=gallery_images,
            source_url=source_url,
            creator=creator,
            creator_url=creator_url,
            versions=versions,
            action_buttons=buttons,
        )
    )


def pool_card(
    pool_id: str,
    name: str,
    state_line: str,
    description: str,
    member_sections: tuple[tuple[str, str, str], ...],
    buttons: tuple[Callable[[], discord.ui.Item[discord.ui.LayoutView]], ...],
) -> discord.ui.LayoutView:
    """Build a pool's forum card: state header + member sections.

    ``member_sections`` carries ``(name, map_link, image_url)`` per
    map — each becomes a Section (name linking to the map's post)
    with the map image as the accessory.
    """
    view = discord.ui.LayoutView(timeout=None)
    header = f"## {name[:1].upper()}{name[1:]}\n{state_line}"
    if description:
        header += f"\n{description}"
    view.add_item(
        discord.ui.Container(discord.ui.TextDisplay(header), accent_colour=discord.Colour(ACCENT))
    )
    for map_name, link, image in member_sections[:10]:
        title = f"### [{map_name}]({link})" if link else f"### {map_name}"
        if image:
            view.add_item(
                discord.ui.Section(
                    discord.ui.TextDisplay(title),
                    accessory=discord.ui.Thumbnail(image),
                )
            )
        else:
            view.add_item(discord.ui.TextDisplay(title))
    overflow = [m[0] for m in member_sections[10:]]
    if overflow:
        view.add_item(discord.ui.TextDisplay("\n".join(f"- {n}" for n in overflow)))
    _actions(view, buttons)
    # the id footer is ALWAYS the last line — after the buttons
    view.add_item(discord.ui.TextDisplay(f"-# `{pool_id}`"))
    return view


__all__ = [
    "ACCENT",
    "EntityCardSpec",
    "build_entity_card",
    "map_card",
    "pool_card",
]
