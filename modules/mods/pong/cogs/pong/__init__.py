"""The pong mod's Discord cog (§7 cogs): the mod's only Discord layer.

Owner direction 2026-11-24 (D-PONG-037): the slice ships NO mod slash
command — the Discord surface is the CORE commands (``/home`` +
``/admin``) plus the platform's auto-generated menus
(botforge.discord.mod_views: ``menu:mod:pong`` and
``menu:mod:pong:admin``, declared from ``conf/mod.yaml`` at boot —
the developer declares nothing, botforge-services#377). The
declaration's ``commands:`` list stays empty.

The registration front door (SC-PONG-001/002 — the
``pong:register:<discord_id>`` declared action button wired through
``wire_action`` + the SDK's ConfirmationView consent gate) lands with
step 3 (season/engine), riding the generated menus.
"""

from __future__ import annotations

from typing import Any


def register(bot: Any, config: Any) -> None:
    """Wire the cog onto the bot — deliberately nothing at slice v1.

    The mod.yaml ``commands: []`` declaration and the tests assert
    that no command is added to the tree; the auto-generated menus
    carry the mod's surface until the front-door buttons land (step 3).
    Kept as an explicit no-op so the entrypoint loads the mod and logs
    its registration (``MOD pong registered``).
    """


def setup_hook(bot: Any) -> None:
    """Re-register persistent UI after a restart (none at slice v1)."""


def close(bot: Any) -> None:
    """Stop the mod's background tasks (none at slice v1)."""
