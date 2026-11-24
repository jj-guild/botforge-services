"""Kingdom mod apply flow (postuler-hybride-v1, Drasah 18/11).

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
    # conscription-4-salons (Drasah 20/11): without a season the pin has
    # ZERO buttons — the ⚔️ camp row only rides a live season, the
    # adaptive-window opener is gone. No dead clickable, no clutter.
    assert _buttons(view) == []


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
    # salon-parcours-v2 (Drasah 18/11): an IMPOSSIBLE action is disabled
    disabled = [bool(b.get("disabled")) for b in _buttons(view)]
    assert disabled == [False, True], "a red button is NOT clickable: no dead click, no timeout"

    # ready: the states flip — account red+disabled, postuler green+enabled
    view = render_apply_branch("ready", strings)
    buttons = _buttons(view)
    styles = [b.get("style") for b in buttons]
    assert styles == [4, 3], "an existing account reds the CTA, the ready POSTULER greens"
    assert [bool(b.get("disabled")) for b in buttons] == [True, False], "only possible actions are clickable"

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


def test_the_register_panel_is_the_parcours_first_door(monkeypatch: Any) -> None:
    """The public « register » salon's poster: ONE CTA (salon-parcours-v2).

    The button is the platform's official profile route — the account is
    the free first tier, and the gated Postuler salon opens through the
    registration role, never through a link from here.
    """
    import botforge.mods.kingdom.cogs.panel as panel_module
    from botforge.mods.kingdom.cogs.apply_flow import PROFILE_ROUTE, build_register_panel

    async def _fr(guild_id: str) -> str:
        return "fr"

    monkeypatch.setattr(panel_module, "_guild_locale", _fr)
    view = asyncio.run(build_register_panel("123"))
    buttons = _buttons(view)
    assert len(buttons) == 1, "the register poster carries ONE call-to-action"
    assert buttons[0].get("custom_id") == PROFILE_ROUTE, "the account route, the platform's own"
    assert not buttons[0].get("disabled"), "the account is always possible here (green + clickable)"
    assert buttons[0].get("style") == 3, "the green create-account CTA"
    texts = " ".join(_texts(view))
    assert "S'ENREGISTRER" in texts, "the register salon's own title"
    assert "postuler" in texts, "the hint names the next door"


def test_the_gate_toggles_the_access_role() -> None:
    """profile.bound grants « Kingdom Enregistré »; the last unbind revokes."""
    from botforge.mods.kingdom.cogs.registration_gate import profile_event_handler

    granted: list[str] = []
    revoked: list[str] = []
    role = NS(id=777)

    class _Member:
        roles: tuple[Any, ...] = ()

        async def add_roles(self, r: Any, reason: str = "") -> None:
            self.roles = tuple(self.roles) + (r,)
            granted.append("grant")

        async def remove_roles(self, r: Any, reason: str = "") -> None:
            self.roles = ()
            revoked.append("revoke")

    class _Bot:
        mod_roles_service = None

        def __init__(self) -> None:
            self.member = _Member()

        def get_guild(self, guild_id: int) -> Any:
            bot = self

            class _Guild:
                def get_role(self, role_id: int) -> Any:
                    return role if role_id == 777 else None

                def get_member(self, user_id: int) -> Any:
                    return bot.member  # ONE member across the events

            return _Guild()

    class _RolesService:
        async def resolve_role_id(self, guild_id: str, mod: str, role_key: str) -> str:
            return "777" if role_key == "enregistre" else ""

    class _RolesBot(_Bot):
        mod_roles_service = _RolesService()

    import botforge.mods.kingdom.cogs.panel as panel_module

    panel_module.remember_bot(_RolesBot())
    asyncio.run(profile_event_handler("profile.bound", {"user_id": "42", "guild_id": "123"}))
    assert granted, "the bind grants the access role"
    assert not revoked

    # the member now holds the granted role → the revoke path fires
    asyncio.run(profile_event_handler("profile.unbound", {"user_id": "42", "guild_id": "123", "remaining": False}))
    assert revoked, "the last unbind revokes the access role"

    # a remaining binding keeps the role (multi-profile)
    revoked.clear()
    asyncio.run(profile_event_handler("profile.unbound", {"user_id": "42", "guild_id": "123", "remaining": True}))
    assert not revoked, "a remaining binding keeps the salon open"


def test_the_gate_falls_back_to_fetch_when_the_member_cache_is_empty() -> None:
    """2026-11-18 live incident: without the members intent get_member is
    None — the grant must not silently skip (fetch_member fallback)."""
    from botforge.mods.kingdom.cogs.registration_gate import profile_event_handler

    granted: list[Any] = []
    role = NS(id=777)

    class _Member:
        roles: tuple[Any, ...] = ()

        async def add_roles(self, r: Any, reason: str = "") -> None:
            self.roles = tuple(self.roles) + (r,)
            granted.append("grant")

    member = _Member()

    class _Guild:
        id = 123

        def get_role(self, role_id: int) -> Any:
            return role if role_id == 777 else None

        def get_member(self, user_id: int) -> Any:
            return None  # the members intent is OFF — the live failure

        async def fetch_member(self, user_id: int) -> Any:
            return member

    class _Bot:
        mod_roles_service = None

        def get_guild(self, guild_id: int) -> Any:
            return _Guild()

    class _RolesService:
        async def resolve_role_id(self, guild_id: str, mod: str, role_key: str) -> str:
            return "777" if role_key == "enregistre" else ""

    _Bot.mod_roles_service = _RolesService()

    import botforge.mods.kingdom.cogs.panel as panel_module

    panel_module.remember_bot(_Bot())
    asyncio.run(profile_event_handler("profile.bound", {"user_id": "42", "guild_id": "123"}))
    assert granted, "the fetch fallback grants the role the cache could not see"


def test_the_gate_boot_heal_regrants_the_declared_registrants() -> None:
    """Accounts bound before the gate existed never fire profile.bound —
    the boot reconcile reads the bindings' guild context (the declared
    truth) and re-grants the access role."""
    from botforge.mods.kingdom.cogs.registration_gate import reconcile_guild_access

    granted: list[Any] = []
    role = NS(id=777)

    class _Member:
        def __init__(self) -> None:
            self.roles: tuple[Any, ...] = ()

        async def add_roles(self, r: Any, reason: str = "") -> None:
            self.roles = tuple(self.roles) + (r,)
            granted.append("grant")

    members: dict[int, _Member] = {}

    class _Guild:
        id = 123

        def get_role(self, role_id: int) -> Any:
            return role if role_id == 777 else None

        def get_member(self, user_id: int) -> Any:
            if user_id not in members:
                members[user_id] = _Member()  # one member per registrant
            return members[user_id]

    class _Registration:
        async def list_guild_registrant_ids(self, guild_id: str) -> list[str]:
            return ["42", "43"] if guild_id == "123" else []

    class _RolesService:
        async def resolve_role_id(self, guild_id: str, mod: str, role_key: str) -> str:
            return "777" if role_key == "enregistre" else ""

    class _Bot:
        mod_roles_service = None
        registration_service = None
        guilds = None

        def get_guild(self, guild_id: int) -> Any:
            return _Guild()

    _Bot.mod_roles_service = _RolesService()
    _Bot.registration_service = _Registration()
    _Bot.guilds = [_Guild()]

    asyncio.run(reconcile_guild_access(_Bot()))
    assert len(granted) == 2, "every declared registrant carries the access role after the boot heal"


def test_the_gate_boot_heal_survives_a_missing_role() -> None:
    """No provisioned role → LOUD skip, no crash, no grant."""
    from botforge.mods.kingdom.cogs.registration_gate import reconcile_guild_access

    class _RolesService:
        async def resolve_role_id(self, guild_id: str, mod: str, role_key: str) -> str:
            return ""

    class _Registration:
        async def list_guild_registrant_ids(self, guild_id: str) -> list[str]:
            return ["42"]

    class _Bot:
        mod_roles_service = None
        registration_service = None
        guilds = None

    _Bot.mod_roles_service = _RolesService()
    _Bot.registration_service = _Registration()
    _Bot.guilds = [NS(id=123)]

    asyncio.run(reconcile_guild_access(_Bot()))  # must not raise


def test_the_postuler_wire_dispatches_fullmatch() -> None:
    """postuler-dead-click-v1 (Drasah 20/11, live regression).

    discord.py dispatches a DynamicItem on ``pattern.fullmatch`` of the
    WIRE custom_id; the Postuler template once lacked its ``:mod`` tail
    so every click silently died. The built id must fullmatch the class
    template — exactly the engine's own dispatch semantics.
    """
    from botforge.mods.kingdom.cogs.apply_flow import KingdomPostulerButton

    button = KingdomPostulerButton("kingdom", "📜 Postuler", active=True)
    match = KingdomPostulerButton.__discord_ui_compiled_template__.fullmatch(
        button.item.custom_id or ""
    )
    assert match is not None, "the wire id must fullmatch the class template"
    assert match["mod"] == "kingdom"


def test_the_conscription_declaration_rides_the_parcours() -> None:
    """conscription-4-salons (Drasah 20/11): the CONSCRIPTION sidebar IS
    the parcours — the declared channel order = the player's steps, and
    the register salon is DENIED to the registered (the step passed)."""
    import yaml
    from pathlib import Path

    from botforge.core.services.mod_definition import ChannelAccessPolicy

    conf = yaml.safe_load(open(Path(__file__).parents[1] / "conf" / "mod.yaml"))
    conscription = [c["key"] for c in conf["channels"] if c.get("group") == "conscription"]
    assert conscription == ["register", "apply", "seigneurerie", "realms"]
    register = next(c for c in conf["channels"] if c["key"] == "register")
    policy = ChannelAccessPolicy.from_dict(register["access"])
    assert policy.deny_view == ("🪙 Kingdom Enregistré",), "registred players lose the salon"
    assert policy.everyone_view is True, "the account door stays public"
    seigneurerie = next(c for c in conf["channels"] if c["key"] == "seigneurerie")
    assert seigneurerie["admin_only"] is True


def test_the_seigneurerie_panel_builds_the_lords_desk(monkeypatch: Any) -> None:
    """The pinned seigneurerie panel: the queue lines + the existing
    assign/remove action seams — the PEOPLE surface, admin-gated salon."""
    import asyncio

    import botforge.mods.kingdom.cogs.panel as panel_module
    from botforge.mods.kingdom.cogs.settings_panel import build_seigneurerie_panel

    async def _fr(guild_id: str) -> str:
        return "fr"

    monkeypatch.setattr(panel_module, "_guild_locale", _fr)

    class _Lord:
        id = "42"
        display_name = "Drasah"
        in_queue = True
        kingdom_id = None
        left = False

    class _Kingdom:
        async def lords(self) -> list:
            return [_Lord()]

    class _Stack:
        kingdoms = _Kingdom()

    import botforge.mods.kingdom.cogs.settings_panel as sp

    monkeypatch.setattr(sp, "wiring", lambda: _Stack())
    view = asyncio.run(build_seigneurerie_panel("1"))
    texts = _texts(view)
    assert any("Seigneurerie" in text for text in texts), "the desk is titled"
    assert any("Drasah" in text for text in texts), "the queued lord is listed"
    labels = [str(b.get("label") or "") for b in _buttons(view)]
    assert any("Affecter" in l for l in labels), "the assign seam rides"
    assert any("Retirer" in l for l in labels), "the remove seam rides"
