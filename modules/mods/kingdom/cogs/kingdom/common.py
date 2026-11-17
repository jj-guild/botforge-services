"""The attack surfaces' shared plumbing (P4.1b tranche 1).

Everything the declare panel, the wizard and the attack salons share:
the service wiring (through the §7 contract — never the mod's
internals), the locale, the fenêtre-unique ephemeral registry, the
Paris clock formatters and the salon helpers. Ported from the
reference ``kingdom_persistent.py``/``kingdom_attack_panel.py``
helpers, harmonized onto the core seams (botforge.discord.ephemeral,
locales, guards).
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import discord

logger = logging.getLogger("kingdom.attack")

_PARIS = ZoneInfo("Europe/Paris")
_ACCENTS = re.compile(r"[\W_]+", re.UNICODE)

# the fenêtre-unique registry: ONE live ephemeral window per player
# (fenetre-unique-v3, Drasah 28/10). A new flow entry closes the
# player's previous window instead of stacking bubbles.
_EPHEMERAL_WINDOWS: dict[str, tuple[discord.Interaction, float]] = {}


# ---------------------------------------------------------------------------
# The service wiring (§7: the cog talks ONLY through the contract)
# ---------------------------------------------------------------------------


def wiring() -> Any:
    """Return the mod's service stack holder (``stack`` may be None).

    The stack resolves LAZILY on every call — a bot that wired its
    Mongo later (or rebuilt it) self-heals, exactly like the
    reference's on-demand resolution.
    """
    from botforge.core.services.mod_entrypoint import mod_service

    service = mod_service("kingdom")
    return getattr(service, "stack", lambda: None)()


def _bot_admins(interaction: discord.Interaction | None = None) -> tuple[str, ...]:
    """The platform's bot-admins ids (best-effort, empty in CI)."""
    if interaction is None:
        return ()
    try:
        admins = getattr(getattr(interaction.client, "status_service", None), "bot_admins", ())
        return tuple(str(admin) for admin in admins or ())
    except Exception:
        return ()


async def lord_of(kingdoms: Any, user_id: str, interaction: discord.Interaction | None = None) -> Any | None:
    """Return the active lord record of the user (any role, None otherwise).

    kingdom-test-v1: an admin with no record falls back to the test
    kingdom's king (the admin-as-king rule).
    """
    if kingdoms is None:
        return None
    try:
        lords = await kingdoms.lords()
    except Exception:
        logger.warning("kingdom: lord scan failed", exc_info=True)
        return None
    lord = next((item for item in lords if str(item.id) == str(user_id) and not item.left), None)
    if lord is not None:
        return lord
    if str(user_id) not in {str(admin) for admin in _bot_admins(interaction)}:
        return None
    # the admin hat: pilot the test kingdom's king when one exists
    from botforge.mods.kingdom.service import TEST_KINGDOM_ID

    return next(
        (
            item
            for item in lords
            if not item.left and str(item.kingdom_id or "") == str(TEST_KINGDOM_ID)
        ),
        None,
    )


# ---------------------------------------------------------------------------
# Locale + strings
# ---------------------------------------------------------------------------


def locale_of(interaction: discord.Interaction) -> str:
    """The interaction's locale (the reference's default: fr)."""
    return str(interaction.locale) if interaction.locale else "fr"


def strings_for(interaction: discord.Interaction) -> dict[str, str]:
    from .strings import strings

    return strings(locale_of(interaction))


# ---------------------------------------------------------------------------
# The fenêtre unique (one ephemeral window per player)
# ---------------------------------------------------------------------------


async def close_previous_ephemeral(user_id: str) -> None:
    """Best-effort: delete the player's previous ephemeral window."""
    previous = _EPHEMERAL_WINDOWS.pop(user_id, None)
    if previous is None:
        return
    old_interaction = previous[0]
    try:
        await old_interaction.delete_original_response()
        logger.info("kingdom: previous ephemeral window closed for %s", user_id)
    except Exception:
        logger.info("kingdom: previous ephemeral window close failed (ignored)")


async def open_unique_ephemeral(
    interaction: discord.Interaction, content: str | None = None, **kwargs: Any
) -> None:
    """Open THE player's single ephemeral window (shared registry)."""
    user_id = str(interaction.user.id)
    await close_previous_ephemeral(user_id)
    kwargs["ephemeral"] = True
    await interaction.response.send_message(content, **kwargs)
    import time

    _EPHEMERAL_WINDOWS[user_id] = (interaction, time.monotonic())


async def silent_ack(interaction: discord.Interaction) -> None:
    """Swallow a click: a bare defer renders NOTHING, never an error."""
    try:
        await interaction.response.defer()
    except Exception:
        logger.debug("kingdom: silent ack failed", exc_info=True)


# ---------------------------------------------------------------------------
# The Paris clock formatters (the players' clock, D77)
# ---------------------------------------------------------------------------


def fmt_paris(moment: Any) -> str:
    """Format a moment in Paris time (« 29/08 19:15 »)."""
    when = moment if isinstance(moment, datetime) else datetime.fromtimestamp(moment, tz=_PARIS)
    return when.astimezone(_PARIS).strftime("%d/%m %H:%M")


def fmt_rdv_auto(moment: Any, locale: str) -> str:
    """The self-updating RDV clock — « à **10h32** (<t:epoch:R>) »."""
    when = moment if isinstance(moment, datetime) else datetime.fromtimestamp(moment, tz=_PARIS)
    local = when.astimezone(_PARIS)
    epoch = int(when.timestamp())
    if str(locale).lower().startswith("fr"):
        hm = f"{local.hour:02d}h{local.minute:02d}"
        return f"à **{hm}** (<t:{epoch}:R>)"
    hm = f"{local.hour:02d}:{local.minute:02d}"
    return f"at **{hm}** (<t:{epoch}:R>)"


def fmt_when_paris(moment: Any, strings: dict[str, str]) -> str:
    """The readable RELATIVE clock — « aujourd'hui à 18h30 »."""
    from datetime import timedelta

    when = moment if isinstance(moment, datetime) else datetime.fromtimestamp(moment, tz=_PARIS)
    local = when.astimezone(_PARIS)
    hm = str(strings["when_hm"]).format(hour=f"{local.hour:02d}", minute=f"{local.minute:02d}")
    now = datetime.now(tz=_PARIS)
    if local.date() == now.date():
        return str(strings["when_today"]).format(time=hm)
    if local.date() == now.date() + timedelta(days=1):
        return str(strings["when_tomorrow"]).format(time=hm)
    return str(strings["when_other"]).format(date=local.strftime("%d/%m"), time=hm)


def fmt_delay(minutes: int) -> str:
    """Format an itinerary as « 1h », « 1h30 » or « 45 min »."""
    if minutes <= 0:
        return "0 min"
    hours, rest = divmod(int(minutes), 60)
    if hours == 0:
        return f"{rest} min"
    if rest == 0:
        return f"{hours}h"
    return f"{hours}h{rest:02d}"


def slug(value: str) -> str:
    """The Discord-safe slug (accents stripped, lowercase)."""
    import unicodedata

    folded = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return _ACCENTS.sub("-", folded.lower()).strip("-") or "bataille"


def room_key(attack_id: str) -> str:
    """The 16-hex digest keying a salon component (Check 73)."""
    return hashlib.sha256(str(attack_id).encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Name resolvers + failures
# ---------------------------------------------------------------------------


async def lord_name(kingdoms: Any, lord_id: str | None) -> str:
    """The lord's display name (fallback: the raw id)."""
    if kingdoms is None or not lord_id:
        return "—"
    try:
        lord = next((item for item in await kingdoms.lords() if str(item.id) == str(lord_id)), None)
        return str(getattr(lord, "display_name", "") or lord_id) if lord else str(lord_id)
    except Exception:
        return str(lord_id)


async def kingdom_name(kingdoms: Any, kingdom_id: str | None) -> str:
    """The kingdom's name (fallback: the raw id)."""
    if kingdoms is None or not kingdom_id:
        return "—"
    try:
        kingdom = next(
            (item for item in await kingdoms.kingdoms() if str(item.id) == str(kingdom_id)), None
        )
        return str(getattr(kingdom, "name", "") or kingdom_id) if kingdom else str(kingdom_id)
    except Exception:
        return str(kingdom_id)


async def lord_kingdom_name(kingdoms: Any, lord_id: str | None) -> str:
    """The kingdom NAME of one lord ('' when unresolvable)."""
    if kingdoms is None or not lord_id:
        return ""
    try:
        lord = next((item for item in await kingdoms.lords() if str(item.id) == str(lord_id)), None)
        if lord is None or lord.kingdom_id is None:
            return ""
        return await kingdom_name(kingdoms, lord.kingdom_id)
    except Exception:
        return ""


def kingdom_mention(guild: Any, name: str) -> str:
    """Mention the kingdom's Discord role when it exists (bold fallback)."""
    roles = list(getattr(guild, "roles", []) or [])
    role = next((r for r in roles if getattr(r, "name", "") == name), None)
    if role is not None:
        return str(getattr(role, "mention", f"**{name}**"))
    return f"**{name}**"


def combat_failure_note(exc: Exception, strings: dict[str, str]) -> str:
    """Map a combat-action failure to its player-facing note."""
    from botforge.mods.kingdom.attacks import LordEngagedError, LordTavernLockedError

    if isinstance(exc, LordTavernLockedError):
        return str(strings["lord_tavern_locked"])
    if isinstance(exc, LordEngagedError):
        return str(strings["lord_engaged"])
    message = getattr(exc, "message", None) or str(exc)
    return str(strings["failed"]).format(message=message)


# ---------------------------------------------------------------------------
# The attack salons (restructuration-serveur-v1 b)
# ---------------------------------------------------------------------------


def attack_salon(guild: Any, attack: Any) -> Any:
    """Return the attack's OWN salon (stored ref, never a name lookup)."""
    channel_id = int((dict(getattr(attack, "score", None) or {})).get("attack_channel_id") or 0)
    if guild is None or not channel_id:
        return None
    return getattr(guild, "get_channel", lambda _id: None)(channel_id)


async def attack_salon_send_safe(guild: Any, attack: Any, content: str) -> Any:
    """Best-effort announcement in the attack's own salon."""
    channel = attack_salon(guild, attack)
    if channel is None:
        return None
    try:
        return await channel.send(content)
    except Exception:
        logger.warning("kingdom: attack salon announcement failed", exc_info=True)
        return None


def salon_overwrites(guild: Any) -> dict[Any, discord.PermissionOverwrite]:
    """The attack salon's overwrite set (permissions-serveur-v1).

    ⚠️ lesson Check 75: the set MUST carry an explicit guild.me entry
    (the bot is no admin) or it locks itself out of its own salon.
    """
    overwrites: dict[Any, discord.PermissionOverwrite] = {}
    everyone = getattr(guild, "default_role", None)
    if everyone is not None:
        overwrites[everyone] = discord.PermissionOverwrite(
            view_channel=False,
            send_messages=False,
            read_message_history=False,
        )
    for role_name in ("Kingdom Lord", "Kingdom King", "Kingdom Admin"):
        role = discord.utils.get(getattr(guild, "roles", []), name=role_name)
        if role is not None:
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=False,
                read_message_history=True,
            )
    me = getattr(guild, "me", None)
    if me is not None:
        overwrites[me] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            manage_messages=True,
        )
    return overwrites


def room_channel_name(guild: Any, prefix: str, *parts: str) -> str:
    """The duel channel name — ``🗡️-drasah-vs-bourgogne`` (battle-room-id-v2)."""
    base = f"{prefix}-" + "-vs-".join(slug(str(part)) for part in parts) or f"{prefix}-bataille"
    base = base[:90]
    names = {str(getattr(channel, "name", "")) for channel in getattr(guild, "channels", [])}
    if base not in names:
        return base
    suffix = 2
    while f"{base}-{suffix}" in names:
        suffix += 1
    return f"{base}-{suffix}"


__all__ = [
    "attack_salon",
    "attack_salon_send_safe",
    "close_previous_ephemeral",
    "combat_failure_note",
    "fmt_delay",
    "fmt_paris",
    "fmt_rdv_auto",
    "fmt_when_paris",
    "kingdom_mention",
    "kingdom_name",
    "lord_kingdom_name",
    "lord_name",
    "lord_of",
    "locale_of",
    "open_unique_ephemeral",
    "room_channel_name",
    "room_key",
    "salon_overwrites",
    "silent_ack",
    "slug",
    "strings_for",
    "wiring",
]
