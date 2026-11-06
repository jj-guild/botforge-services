"""The view-id footer: every surface's feedback anchor.

One rule (docs/DEVELOPMENT/VIEWS.md): every rendered surface carries
its view id as its last line, backticked — the anchor every human
feedback refers to. LayoutViews get a ``-#`` small-text line outside
every container (never inside an embed); embeds carry the id as the
embed footer, backticked.
"""

from __future__ import annotations

from typing import Any

import discord

from kingdoms.core.ids import footer


def add_view_footer(view: discord.ui.LayoutView, view_id: str) -> discord.ui.LayoutView:
    """Append the id footer line to a LayoutView, outside the containers."""
    line = footer(view_id)
    if line:
        view.add_item(discord.ui.TextDisplay(line))
    return view


def embed_footer(embed: discord.Embed, view_id: str) -> discord.Embed:
    """Set the id as an embed's footer, backticked."""
    embed.set_footer(text=f"`{view_id}`")
    return embed


__all__ = ["add_view_footer", "build_view", "embed_footer", "require_declared_view_id"]

def build_view(view_id: str, *items: Any) -> discord.ui.LayoutView:
    """Build a panel LayoutView carrying its id footer — the only way.

    The guardrail (owner direction 2026-10-31): a view's id line is
    not optional and not manual — every panel builds through this
    constructor, which appends the items then the id footer (the LAST
    line, outside the containers). A view built any other way ships
    without its anchor: the review catches it, or worse, the user's
    feedback names a panel nobody can locate.
    """
    view = discord.ui.LayoutView(timeout=None)
    for item in items:
        view.add_item(item)
    add_view_footer(view, view_id)
    return view


def require_declared_view_id(view_id: str) -> str:
    """Fail fast when a panel renders an id the registry never declared.

    The declared ids live in config/views.yaml (the menus' registry);
    a rendered-but-undeclared id means the routing answers 'unknown
    view' on the SAME id the panel claims — a broken navigation. This
    raises at the first render (the boot smoke or the first click),
    not after a user reports a dead button.
    """
    from kingdoms.discord.views_registry import get_view, registered_views

    if not registered_views():
        # the registry fills at the boot wiring; a panel rendered before
        # (a smoke test, a CLI render) loads the declared config itself
        from kingdoms.discord.views_declared import declare_platform_views

        declare_platform_views()
    if get_view(view_id) is None:
        raise ValueError(
            f"view id '{view_id}' is not declared in config/views.yaml — "
            "declare it (and its menu entry) before rendering a panel with it"
        )
    return view_id
