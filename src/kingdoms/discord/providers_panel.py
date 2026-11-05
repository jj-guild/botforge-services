"""The providers admin panel (panel:game:aoe2:providers, ADR-0021).

The admin sub-menu of the aoe2 game admin: every provider configured
on the game service, with its last health-test results (the prober's
capabilities ping: ok, latency, consecutive failures). The data comes
from the game service — ``GetProviderTests`` on the GameData contract —
never from the providers directly (the bot never talks to them).
"""

from __future__ import annotations

import logging
import os
from typing import Any

import discord

logger = logging.getLogger("kingdoms.discord.providers_panel")

GAME_KEY = "aoe2"

_STATE_ICONS = {True: "🟢", False: "🟠"}


async def view_providers(interaction: discord.Interaction) -> None:
    """Render the providers panel (ephemeral, admin-guarded).

    No synthetic probe (owner direction 2026-11-04): the panel ASKS each
    provider process for its OWN call statistics (GetUpstreamStats on the
    Status contract) — the last call, the consecutive failures, the
    calls/errors of the last minute. The provider is the only place
    that sees its calls; reading it never touches any upstream.
    """
    from kingdoms.discord.wiring import guard_admin

    if not await guard_admin(interaction):
        return
    game_uri = os.environ.get("GAME_AOE2_URI", "")
    await interaction.response.defer(ephemeral=True)
    if not game_uri:
        await interaction.followup.send(
            "Providers panel unavailable: GAME_AOE2_URI is not configured "
            "(the game-aoe2 service owns the providers).",
            ephemeral=True,
        )
        return
    from kingdoms.core.rpc.status import fetch_upstream_stats

    # The game service OWNS its providers (owner direction 2026-11-05):
    # the bot never interrogates a provider — it asks the game service,
    # which answers with every provider's stats (its own aggregation).
    try:
        entries = await fetch_upstream_stats(game_uri, timeout_s=15.0)
    except Exception:
        logger.warning("providers panel fetch failed", exc_info=True)
        await interaction.followup.send(
            "Providers panel unavailable: the game-aoe2 service is not responding.",
            ephemeral=True,
        )
        return
    locale = str(interaction.locale) if interaction.locale else "fr"
    await interaction.followup.send(
        view=_render_view({"entries": entries}, interaction.client, locale),
        ephemeral=True,
    )


def _tr(bot: Any, locale: str, key: str, fallback: str, **kwargs: Any) -> str:
    """Render one panel string in the interaction's locale (fallback)."""
    catalog = getattr(bot, "messages", None)
    if catalog is None:
        return fallback.format(**kwargs) if kwargs else fallback
    try:
        rendered = str(catalog.render(f"providers.{key}", locale))
    except Exception:
        return fallback.format(**kwargs) if kwargs else fallback
    return rendered.format(**kwargs) if kwargs else rendered


def _declared(provider_id: str) -> dict[str, Any]:
    """Load the provider's declared entry (config/games/aoe2/providers.yaml).

    The owner's spec: status (in use / planned) + the feature tags +
    the note — everything DECLARED IN CONFIG, translated at render.
    """
    from pathlib import Path

    import yaml

    path = Path("config/games/aoe2/providers.yaml")
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except Exception:
        return {}
    entry = (data.get("providers") or {}).get(provider_id) or {}
    return dict(entry)


def _render_view(results: dict[str, Any], bot: Any = None, locale: str = "fr") -> discord.ui.LayoutView:
    """Build the providers panel view — the map posts' shape.

    One Container per provider: its call stats (last call, consecutive
    failures, the last minute's calls/errors, average latency) and its
    DECLARED features (config/games/aoe2/providers.yaml). The view id
    rides the last line (the SDK's build_view).
    """
    entries_list = results.get("entries") or []
    # group by provider (a provider may own several upstreams)
    entries: dict[str, dict[str, Any]] = {}
    for entry in entries_list:
        provider_id = str(entry.get("provider_id", "")) or str(entry.get("upstream", "?"))
        entries.setdefault(provider_id, entry)
    from kingdoms.discord.ui.view_footer import build_view, require_declared_view_id

    require_declared_view_id("panel:game:aoe2:providers")
    header_lines: list[str] = [
        "# " + _tr(bot, locale, "title", "\U0001F6E0 Providers — Age of Empires II"),
        "",
        _tr(
            bot,
            locale,
            "subtitle",
            "Upstream call statistics of each provider — last call, failures, last minute.",
        ),
    ]
    items: list[Any] = [
        discord.ui.Container(discord.ui.TextDisplay("\n".join(header_lines)), accent_colour=0xF1C40F)
    ]
    if not entries:
        items.append(
            discord.ui.Container(
                discord.ui.TextDisplay(
                    _tr(bot, locale, "no_providers", "No provider configured on the game-aoe2 service.")
                )
            )
        )
    for provider_id, entry in entries.items():
        upstream = str(entry.get("upstream", provider_id))
        detail = str(entry.get("detail", ""))
        if detail.startswith("unreachable"):
            icon = "\u26d4"
            state = _tr(bot, locale, "unreachable", "injoignable")
            block = [f"{icon} **{provider_id} {state}**"]
        elif entry.get("never_called"):
            icon = "\u2796"
            state = (
                _tr(bot, locale, "not_deployed", "pas d\u00e9ploy\u00e9")
                if entry.get("detail") == "not deployed"
                else _tr(bot, locale, "no_calls", "aucun appel")
            )
            block = [f"{icon} **{provider_id} {state}**"]
        else:
            ok = bool(entry.get("ok", False))
            icon = _STATE_ICONS[ok]
            state = _tr(bot, locale, "probe_ok" if ok else "probe_ko", "OK" if ok else "KO")
            last_call = int(entry.get("last_call_at", 0) or 0)
            when = f" <t:{last_call // 1000}:R>" if last_call else ""
            failures = int(entry.get("consecutive_failures", 0))
            minute_calls = int(entry.get("calls_last_minute", 0))
            minute_errors = int(entry.get("errors_last_minute", 0))
            latency = int(entry.get("avg_latency_ms", 0))
            lines = [
                _tr(
                    bot,
                    locale,
                    "last_call",
                    "Dernier appel : {calls} appel(s) {when} ({errors} erreur(s))",
                    calls=minute_calls,
                    when=when.strip() or "—",
                    errors=minute_errors,
                ),
                _tr(bot, locale, "failures", "\u00c9checs cons\u00e9cutifs : {count}", count=failures),
                _tr(bot, locale, "latency", "Latence moyenne : {ms} ms", ms=latency),
            ]
            last_error = str(entry.get("last_error", ""))
            if not ok and last_error:
                lines.append(f"`{last_error[:100]}`")
            block = [f"{icon} **{provider_id} {state}** ({upstream})", *lines]
        declared = _declared(provider_id)
        features = [str(f) for f in (declared.get("features") or [])]
        labels = [_tr(bot, locale, f"features_labels.{f}", f) for f in features]
        if labels:
            feats = _tr(bot, locale, "features", "Fonctionnalit\u00e9s")
            block.append(f"*{feats}:*")
            for label in labels:
                block.append(f"- {label}")
        ok = not entry.get("never_called") and bool(entry.get("ok", False))
        items.append(
            discord.ui.Container(
                discord.ui.TextDisplay("\n".join(block)),
                accent_colour=0x2ECC71 if ok else 0xE74C3C,
            )
        )
    return build_view("panel:game:aoe2:providers", *items)
