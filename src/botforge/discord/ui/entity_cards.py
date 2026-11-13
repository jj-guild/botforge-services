"""Entity cards: the shared Components V2 templates for catalog posts.

One builder per surface family — map, pool, faction (civ), and the
generic entity card the mods reuse (kingdoms territories, ladder
objects, ...). Every card follows the same pseudo-embed contract
(issue #321):

* a header Section (title, optional thumbnail accessory) — a Section
  holds at most 3 text children (Discord 50035), so the header is a
  single text block by construction;
* the resource id in backticks as the subtitle's first line — THE
  anchor every human feedback refers to, at the same place on every
  card whatever the entity's state;
* property lines (one setting per line) behind no divider;
* a divider, the description, the member sections, the media, the
  cross-links, the source link — each block behind a divider;
* an action row (the surface's buttons, persistent DynamicItems);
* the view id in backticks as the small footer — ALWAYS the last
  line, after the buttons.

The template's own chrome labels (the variants heading, the creator
and source prefixes, the truncation notes) resolve through the shared
MessageCatalog on the spec's ``locale`` — the callers own the data,
the template owns the chrome, neither hardcodes the other's strings.

The builders are game/mod-agnostic: they take plain strings and
return items; the callers (the games forums, the mods' forums) own
the data and the buttons. No game or mod imports here.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from typing import Any, NamedTuple

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
# Each kept paragraph becomes its own TextDisplay: the clamp also
# respects Discord's 40-component cap (a very fragmented description
# would otherwise blow the component budget before the text one).
MAX_DESCRIPTION_PARAGRAPHS = 12
# The member sections (a pool's maps): capped so a 20-map pool stays
# under the 40-component cap — the overflow rides as text lines.
MAX_MEMBER_SECTIONS = 10


class _CardLabels(NamedTuple):
    """The template's chrome labels, resolved per locale."""

    variants_heading: str
    creator_prefix: str
    source_prefix: str
    truncated_note: str
    more_note: str


_CATALOGS: dict[str, Any] = {}


def _card_labels(locale: str) -> _CardLabels:
    """Resolve the chrome labels through the shared MessageCatalog.

    One loader for the template's own strings (the ``entity_cards``
    catalog section, en+fr in the same change) — the catalog never
    raises, so an unknown key degrades to its dotted name.
    """
    from botforge.core.services.i18n import MessageCatalog

    catalog = _CATALOGS.setdefault("config", MessageCatalog("config"))
    return _CardLabels(
        variants_heading=str(catalog.render("entity_cards.variants_heading", locale)),
        creator_prefix=str(catalog.render("entity_cards.creator_prefix", locale)),
        source_prefix=str(catalog.render("entity_cards.source_prefix", locale)),
        truncated_note=str(catalog.render("entity_cards.truncated_note", locale)),
        more_note=str(catalog.render("entity_cards.more_note", locale)),
    )


def _subtitle_text(spec: EntityCardSpec) -> str:
    """Build the subtitle: the id in backticks, then the caller's lines.

    The #321 contract: the resource id sits at the same place on
    every card — the subtitle's first line, in backticks.
    """
    lines = [f"`{spec.entity_id}`"]
    if spec.subtitle:
        lines.append(spec.subtitle)
    return "\n".join(lines)


def _member_titles(spec: EntityCardSpec) -> list[str]:
    """Build the member sections' titles (link when the target post exists)."""
    titles: list[str] = []
    for name, link, _image in spec.member_sections:
        titles.append(f"### [{name}]({link})" if link else f"### {name}")
    return titles


def _fixed_text(spec: EntityCardSpec, labels: _CardLabels) -> int:
    """Measure the card's displayable text WITHOUT the description block."""
    total = len(f"## {spec.title[:1].upper()}{spec.title[1:]}")
    total += len(_subtitle_text(spec))
    if spec.props:
        total += len("\n".join(spec.props))
    titles = _member_titles(spec)
    if titles:
        total += len("\n".join(titles[:MAX_MEMBER_SECTIONS]))
        overflow = [name for name, _link, _image in spec.member_sections][MAX_MEMBER_SECTIONS:]
        if overflow:
            total += len("\n".join(f"- {name}" for name in overflow))
    if spec.links:
        if spec.links_heading:
            total += len(f"**{spec.links_heading}**\n")
        total += len("\n".join(spec.links))
    if spec.versions:
        lines = [
            f"\u2022 **{v['name']}** \u2014 {v['description']}" if v.get("description") else f"\u2022 **{v['name']}**"
            for v in spec.versions
        ]
        total += len("\n".join([f"**{labels.variants_heading}**", *lines]))
    if spec.creator:
        total += len(f"{labels.creator_prefix}{spec.creator}")
    if spec.source_url:
        total += len(f"{labels.source_prefix}[{spec.source_label}]({spec.source_url})")
    total += len(f"-# `{spec.view_id or spec.entity_id}`")
    return total


def _clamped_spec(spec: EntityCardSpec, labels: _CardLabels) -> EntityCardSpec:
    """Return the spec with its description fitted into the text budget.

    A description that would cross the budget is cut on a paragraph
    boundary (a subsection title never separates from its content) and
    ends with an explicit truncation marker — a shortened card is
    always visibly shortened, never silently shorter.
    """
    allowed = TEXT_BUDGET - BUDGET_HEADROOM - _fixed_text(spec, labels) - len(labels.truncated_note)
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
    return replace(spec, description=body + labels.truncated_note)


@dataclass(frozen=True)
class EntityCardSpec:
    """One catalog card's content, game/mod-agnostic."""

    title: str
    entity_id: str
    subtitle: str = ""
    view_id: str = ""
    locale: str = "en"
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
    member_sections: tuple[tuple[str, str, str], ...] = ()
    action_buttons: tuple[
        Callable[[], discord.ui.Item[discord.ui.LayoutView]]
        | discord.ui.ActionRow[discord.ui.LayoutView]
        | discord.ui.DynamicItem[Any],
        ...,
    ] = field(
        default_factory=tuple
    )


def _header_blocks(spec: EntityCardSpec) -> list[discord.ui.Item[discord.ui.LayoutView]]:
    """Build the header section's blocks: title, subtitle, the in-game icon."""
    blocks: list[discord.ui.Item[discord.ui.LayoutView]] = [
        discord.ui.TextDisplay(f"## {spec.title[:1].upper()}{spec.title[1:]}\n{_subtitle_text(spec)}")
    ]
    return blocks


def _header(spec: EntityCardSpec) -> discord.ui.Item[discord.ui.LayoutView]:
    """Build the header: the title block, the icon as its thumbnail.

    An icon-less header is the bare TextDisplay — a Container is a
    TOP-LEVEL V2 component only (a nested one is rejected with 50035,
    the icon-less civ post never landed).
    """
    blocks = _header_blocks(spec)
    if spec.icon_url:
        return discord.ui.Section(*blocks, accessory=discord.ui.Thumbnail(spec.icon_url))
    return blocks[0]


def _description_blocks(spec: EntityCardSpec, labels: _CardLabels) -> list[discord.ui.Item[discord.ui.LayoutView]]:
    """Build the description's blocks.

    The props line, then each paragraph behind a separator
    (owner direction 2026-11-08). The paragraph count is capped EVEN
    when the text budget is met: many short paragraphs are under the
    text cap yet cross the LayoutView's 40-children cap (the 2026-11-10
    follow-up: the clamp alone let a fragmented description raise at
    build time). A capped card states how many paragraphs are hidden.
    """
    body: list[discord.ui.Item[discord.ui.LayoutView]] = []
    if spec.props:
        body.append(discord.ui.TextDisplay("\n".join(spec.props)))
    # the paragraphs (double newline): a subsection title rides WITH
    # its content in one block — the separator never isolates a title
    paragraphs = [block for block in spec.description.split("\n\n") if block.strip()]
    if len(paragraphs) > MAX_DESCRIPTION_PARAGRAPHS:
        hidden = len(paragraphs) - MAX_DESCRIPTION_PARAGRAPHS
        paragraphs = paragraphs[:MAX_DESCRIPTION_PARAGRAPHS]
        paragraphs[-1] = f"{paragraphs[-1]}{labels.truncated_note}\n\n{labels.more_note.format(hidden=hidden)}"
    for block in paragraphs:
        if body:
            body.append(discord.ui.Separator())
        body.append(discord.ui.TextDisplay(block))
    return body


def _member_blocks(spec: EntityCardSpec) -> list[discord.ui.Item[discord.ui.LayoutView]]:
    """Build the member sections (a pool's maps).

    Each member rides a Section when it carries an image (the map's
    art as the thumbnail accessory); an imageless member is a plain
    text line. The overflow past the component-safe cap rides as
    text lines.
    """
    blocks: list[discord.ui.Item[discord.ui.LayoutView]] = []
    for name, link, image in spec.member_sections[:MAX_MEMBER_SECTIONS]:
        title = f"### [{name}]({link})" if link else f"### {name}"
        if image:
            blocks.append(
                discord.ui.Section(
                    discord.ui.TextDisplay(title),
                    accessory=discord.ui.Thumbnail(image),
                )
            )
        else:
            blocks.append(discord.ui.TextDisplay(title))
    overflow = [name for name, _link, _image in spec.member_sections][MAX_MEMBER_SECTIONS:]
    if overflow:
        blocks.append(discord.ui.TextDisplay("\n".join(f"- {name}" for name in overflow)))
    return blocks


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


def _versions_blocks(spec: EntityCardSpec, labels: _CardLabels) -> list[discord.ui.Item[discord.ui.LayoutView]]:
    """Build the variants block (the map's Versions section)."""
    if not spec.versions:
        return []
    lines = [f"**{labels.variants_heading}**"]
    lines.extend(
        f"\u2022 **{v['name']}** \u2014 {v['description']}" if v.get("description") else f"\u2022 **{v['name']}**"
        for v in spec.versions
    )
    return [discord.ui.TextDisplay("\n".join(lines))]


def _credits_blocks(spec: EntityCardSpec, labels: _CardLabels) -> list[discord.ui.Item[discord.ui.LayoutView]]:
    """Build the credits: the creator just above the source."""
    blocks: list[discord.ui.Item[discord.ui.LayoutView]] = []
    if spec.creator:
        creator = f"[{spec.creator}]({spec.creator_url})" if spec.creator_url else spec.creator
        blocks.append(discord.ui.TextDisplay(f"{labels.creator_prefix}{creator}"))
    if spec.source_url:
        blocks.append(
            discord.ui.TextDisplay(f"{labels.source_prefix}[{spec.source_label}]({spec.source_url})")
        )
    return blocks


def _body_blocks(spec: EntityCardSpec, labels: _CardLabels) -> list[discord.ui.Item[discord.ui.LayoutView]]:
    """Build the card's content blocks, each group behind a separator."""
    groups = [
        _description_blocks(spec, labels),
        _member_blocks(spec),
        _media_blocks(spec),
        _links_blocks(spec),
        _versions_blocks(spec, labels),
        _credits_blocks(spec, labels),
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
        ...,
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

    The shared template: header (icon thumbnail, the id in backticks
    in the subtitle) / props / description / member sections / media /
    cross-links / source / action row / id footer — ALWAYS the last
    line (#321).
    """
    labels = _card_labels(spec.locale)
    spec = _clamped_spec(spec, labels)
    view = discord.ui.LayoutView(timeout=None)
    blocks: list[discord.ui.Item[discord.ui.LayoutView]] = [_header(spec)]
    body = _body_blocks(spec, labels)
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
    locale: str = "en",
) -> discord.ui.LayoutView:
    """Build a map's forum card on the shared template.

    The subtitle (owner direction 2026-11-08): the id in backticks
    (the template's first line), then the tags (the props line) and
    the map pools — the body carries the content only.
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
            locale=locale,
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
    locale: str = "en",
) -> discord.ui.LayoutView:
    """Build a pool's forum card on the shared template (#321).

    The state badge and the member count ride the props (the body's
    first group) — the id sits in the subtitle whatever the pool's
    state (draft/published/archived), never scattered by it.
    ``member_sections`` carries ``(name, map_link, image_url)`` per
    map — each becomes a Section (the name linking to the map's post)
    with the map image as the accessory.
    """
    props = (state_line,) if state_line else ()
    return build_entity_card(
        EntityCardSpec(
            title=name,
            entity_id=pool_id,
            props=props,
            locale=locale,
            description=description,
            member_sections=member_sections,
            action_buttons=buttons,
        )
    )


def civ_card(
    civ_id: str,
    name: str,
    civ_type: str,
    sections: tuple[tuple[str, tuple[str, ...]], ...],
    image_url: str,
    source_url: str,
    source_label: str,
    locale: str = "en",
) -> discord.ui.LayoutView:
    """Build a civ's forum card on the shared template (#321).

    Each parsed section (label, bullet items) becomes one description
    paragraph — the template's separators divide them — and the civ's
    art rides the header thumbnail.
    """
    paragraphs = [
        f"**{label}**\n" + "\n".join(f"\u2022 {item}" for item in items)
        for label, items in sections
        if items
    ]
    return build_entity_card(
        EntityCardSpec(
            title=name,
            entity_id=civ_id,
            subtitle=civ_type,
            locale=locale,
            description="\n\n".join(paragraphs),
            icon_url=image_url,
            source_url=source_url,
            source_label=source_label,
        )
    )


__all__ = [
    "ACCENT",
    "EntityCardSpec",
    "build_entity_card",
    "civ_card",
    "map_card",
    "pool_card",
]
