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
    """Render the providers panel (ephemeral, admin-guarded)."""
    from kingdoms.discord.wiring import guard_admin

    if not await guard_admin(interaction):
        return
    game_uri = os.environ.get("GAME_AOE2_URI", "")
    await interaction.response.defer(ephemeral=True)
    if not game_uri:
        await interaction.followup.send(
            "Providers panel unavailable: GAME_AOE2_URI is not configured "
            "(the game-aoe2 service serves the tests).",
            ephemeral=True,
        )
        return
    try:
        from kingdoms.game_aoe2.client import GameDataClient

        client = GameDataClient(game_uri)
        results = await client.get_provider_tests(GAME_KEY)
    except Exception:
        logger.warning("providers panel fetch failed", exc_info=True)
        await interaction.followup.send(
            "Providers panel unavailable: the game-aoe2 service is not responding.",
            ephemeral=True,
        )
        return
    locale = str(interaction.locale) if interaction.locale else "fr"
    await interaction.followup.send(
        view=_render_view(results, interaction.client, locale), ephemeral=True
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

    A header Container, then ONE Container per provider with a real
    Separator between them (the map posts' pattern — no markdown '---');
    each provider carries its probe status (the ping with its RELATIVE
    TIMESTAMP, the consecutive failures) and its DECLARED features
    (config/games/aoe2/providers.yaml) as one bullet per line. The
    view id rides the last line (the SDK's build_view).
    """
    raw_tests = results.get("tests") or []
    # the wire sends a LIST (the gRPC GetProviderTests shape); the
    # local prober's results() hands a dict — accept both, never crash
    tests: list[tuple[str, dict[str, Any]]] = (
        [(str(t.get("provider_id", "?")), t) for t in raw_tests]
        if isinstance(raw_tests, list)
        else list(raw_tests.items())
    )
    from kingdoms.discord.ui.view_footer import build_view, require_declared_view_id

    require_declared_view_id("panel:game:aoe2:providers")
    header_lines: list[str] = [
        "# " + _tr(bot, locale, "title", "\U0001F6E0 Providers — Age of Empires II"),
        "",
        _tr(
            bot,
            locale,
            "subtitle",
            "Health of the game-{game} service's providers — ping, capabilities, refreshed every minute.",
            game="aoe2",
        ),
    ]
    items: list[Any] = [
        discord.ui.Container(discord.ui.TextDisplay("\n".join(header_lines)), accent_colour=0xF1C40F)
    ]
    if not tests:
        items.append(
            discord.ui.Container(
                discord.ui.TextDisplay(
                    _tr(bot, locale, "no_providers", "No provider configured on the game-aoe2 service.")
                )
            )
        )
    for provider_id, test in tests:
        ok = bool(test.get("ok", False))
        icon = _STATE_ICONS[ok]
        latency = int(test.get("latency_ms", 0))
        failures = int(test.get("failures", 0))
        checked_at = int(test.get("checked_at", 0) or 0)
        # the relative timestamp: <t:epoch_seconds:R> renders 'il y a 37 secondes'
        when = f" <t:{checked_at // 1000}:R>" if checked_at else ""
        ping = _tr(bot, locale, "latency", "Ping: {ms} ms", ms=latency)
        fails = _tr(bot, locale, "failures", "Consecutive failures: {count}", count=failures)
        # the probe status word rides the locales, driven by the probe result
        state = _tr(bot, locale, "probe_ok" if ok else "probe_ko", "OK" if ok else "KO")
        block: list[str] = [f"{icon} **{provider_id} {state}**", f"{ping}{when}", fails]
        declared = _declared(provider_id)
        features = [str(f) for f in (declared.get("features") or [])]
        labels = [_tr(bot, locale, f"features_labels.{f}", f) for f in features]
        if labels:
            feats = _tr(bot, locale, "features", "Features")
            block.append(f"*{feats}:*")
            for label in labels:
                block.append(f"- {label}")
        items.append(
            discord.ui.Container(
                discord.ui.TextDisplay("\n".join(block)),
                accent_colour=0x2ECC71 if ok else 0xE74C3C,
            )
        )
    return build_view("panel:game:aoe2:providers", *items)
