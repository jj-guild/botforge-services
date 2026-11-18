"""Kingdoms mod apply flow (postuler-hybride-v1, Drasah 18/11).

The golden Postuler panel pinned in the public « apply » salon, the
3-tier model's pure branch decision (account free / season gated /
kingdom later), the restart-proof single call-to-action, and the
window reusing the platform's engine (SeasonApplyButton, the withdraw
confirm) — the mod owns the shape, the core owns the mechanics.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace as NS
from typing import Any


def _texts(view: Any) -> list[str]:
    out: list[str] = []

    def _walk(item: Any) -> None:
        out.append(item)
        for child in item.get("components", []) or []:
            _walk(child)

    for item in view.to_components():
        _walk(item)
    return [str(i.get("content", "")) for i in out if i.get("type") == 10]


def _buttons(view: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    def _walk(item: Any) -> None:
        out.append(item)
        for child in item.get("components", []) or []:
            _walk(child)

    for item in view.to_components():
        _walk(item)
    return [i for i in out if i.get("type") == 2]


def test_apply_module_import() -> None:
    """The apply flow exposes the panel, the button and the decision."""
    from botforge.mods.kingdom.cogs.apply_flow import (  # noqa: F401
        KingdomApplyOpenButton,
        build_apply_panel,
        decide_apply_branch,
    )


def test_apply_custom_id_is_stable() -> None:
    """The single call-to-action is a restart-proof DynamicItem."""
    from botforge.mods.kingdom.cogs.apply_flow import KingdomApplyOpenButton

    button = KingdomApplyOpenButton("⚔️ Rejoins l'aventure")
    assert "kingdom:apply:open" in str(button.item.to_component_dict())


def test_apply_button_rebuilds_from_the_wire() -> None:
    """from_custom_id rebuilds the locale-aware label."""
    from botforge.mods.kingdom.cogs.apply_flow import KingdomApplyOpenButton

    interaction = NS(locale=None, client=NS(), user=NS(id="42"))
    rebuilt = asyncio.run(
        KingdomApplyOpenButton.from_custom_id(interaction, None, None)  # type: ignore[arg-type]
    )
    label = str(rebuilt.item.to_component_dict().get("label", ""))
    assert label  # the catalog's join_button rendered (fr fallback)


def test_apply_panel_renders_the_golden_poster(monkeypatch: Any) -> None:
    """The pinned panel: the golden title, the tagline, ONE button."""
    import botforge.mods.kingdom.cogs.panel as panel_module
    from botforge.mods.kingdom.cogs.apply_flow import build_apply_panel

    # the platform seam falls back to "en" for a botless guild; the
    # prod guild resolves fr through stored_guild_locale — stub it.
    async def _fr(guild_id: str) -> str:
        return "fr"

    monkeypatch.setattr(panel_module, "_guild_locale", _fr)
    view = asyncio.run(build_apply_panel("123"))
    texts = _texts(view)
    assert any("INSCRIPTION" in text for text in texts)
    assert any("conquête" in text for text in texts)
    buttons = _buttons(view)
    assert len(buttons) == 1  # the single call-to-action, no clutter


def test_the_branch_decision_pins_the_three_tiers() -> None:
    """decide_apply_branch: account first, season gate second, never a dead end."""
    from botforge.mods.kingdom.cogs.apply_flow import decide_apply_branch

    # tier 1: no account → the free account guide, whatever the season
    assert (
        decide_apply_branch(
            account_ok=False, enrollment_wired=True, already=False, season_id="s1", phase="inscriptions"
        )
        == "no_account"
    )
    # unwired engine → the platform button reports it
    assert (
        decide_apply_branch(account_ok=True, enrollment_wired=False, already=False, season_id="", phase="preparation")
        == "unwired"
    )
    # already a candidate (season not started) → the withdraw offer
    assert (
        decide_apply_branch(account_ok=True, enrollment_wired=True, already=True, season_id="s1", phase="inscriptions")
        == "already"
    )
    # account ok but no season → come back soon
    assert (
        decide_apply_branch(account_ok=True, enrollment_wired=True, already=False, season_id="", phase="preparation")
        == "no_season"
    )
    # a closed phase → the phase is named
    assert (
        decide_apply_branch(account_ok=True, enrollment_wired=True, already=False, season_id="s1", phase="ouverte")
        == "closed"
    )
    # the open door: account + inscriptions open → the platform's apply
    assert (
        decide_apply_branch(account_ok=True, enrollment_wired=True, already=False, season_id="s1", phase="inscriptions")
        == "ready"
    )


def test_the_already_branch_still_offers_withdraw_once_started() -> None:
    """An ACCEPTED participant on a started season re-reads as closed."""
    from botforge.mods.kingdom.cogs.apply_flow import decide_apply_branch

    assert (
        decide_apply_branch(account_ok=True, enrollment_wired=True, already=True, season_id="s1", phase="ouverte")
        == "closed"
    )


def _fr_strings() -> Any:
    from botforge.core.services.i18n import MessageCatalog

    return MessageCatalog("modules/mods/kingdom/conf").section("kingdom.apply", "fr")


def test_the_window_shows_the_whole_parcours_at_once() -> None:
    """ONE window: BOTH call-to-actions always visible (Drasah 18/11).

    The state PAINTS them: a missing account greens « Créer mon compte »,
    a ready season greens « Postuler » — and the red ones stay clickable
    (the engines self-guard). No command plumbing, no hidden link.
    """
    from botforge.mods.kingdom.cogs.apply_flow import PROFILE_ROUTE, render_apply_branch

    strings = _fr_strings()
    view = render_apply_branch("no_account", strings)
    buttons = _buttons(view)
    customs = [str(b.get("custom_id", "")) for b in buttons]
    styles = [b.get("style") for b in buttons]
    assert customs == [PROFILE_ROUTE, "kingdom:apply:postuler:kingdom"], (
        "the account route + the postuler shape, always both"
    )
    assert styles[0] == 3, "the missing account paints Créer mon compte GREEN (success)"
    assert styles[1] == 4, "the unready season paints Postuler RED (danger)"
    assert "Bienvenue" in " ".join(_texts(view)), "the welcoming title"
    assert "/register" not in " ".join(_texts(view)), "no command plumbing"

    # ready: the states flip — account red, postuler green
    view = render_apply_branch("ready", strings)
    styles = [b.get("style") for b in _buttons(view)]
    assert styles == [4, 3], "an existing account reds the CTA, the ready POSTULER greens"

    # already: the withdraw confirm still closes the loop
    view = render_apply_branch("already", strings, user_id="42")
    customs = [str(b.get("custom_id", "")) for b in _buttons(view)]
    assert any("withdraw" in c for c in customs), "the already branch keeps the withdraw"


def test_no_locale_mentions_the_command() -> None:
    """The whole catalog is /register-free (the account is a button)."""
    from botforge.core.services.i18n import MessageCatalog

    catalog = MessageCatalog("modules/mods/kingdom/conf")
    for locale in ("fr", "en"):
        flat = str(catalog.section("kingdom.apply", locale))
        assert "/register" not in flat, f"the {locale} apply strings mention no command"



def test_the_panel_carries_the_designers_artwork(monkeypatch: Any) -> None:
    """The poster's head: the artwork gallery ABOVE the title (data-driven)."""
    import json as _json

    import botforge.mods.kingdom.cogs.panel as panel_module
    from botforge.mods.kingdom.cogs.apply_flow import build_apply_panel

    async def _fr(guild_id: str) -> str:
        return "fr"

    monkeypatch.setattr(panel_module, "_guild_locale", _fr)
    view = asyncio.run(build_apply_panel("123"))
    dumped = view.to_components()
    wire = _json.dumps(dumped)
    assert "roi.webp" in wire, "the artwork rides the panel"
    assert "roi.webp" in _json.dumps(dumped[0]), "the illustration heads the panel"
