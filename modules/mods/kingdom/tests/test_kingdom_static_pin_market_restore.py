"""static-pin-market-fix + import-restore-fix — the tests (Drasah 23/11).

Merlin's test-env logs (~18:22-18:32) named two dead surfaces:
the Marché static pin crashed inside surface() (a LayoutView passed
where Items are expected) so the pin NEVER landed, and the camp's
restore button ImportError'd on ``save_habitat`` (a service method
imported as a cog symbol) so the wake-up call failed every time.
Both regressions are locked here.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import discord
import pytest


# ---------------------------------------------------------------------------
# 1. The Marché static pin builds — the #381 seam, no hand-rolled wrap.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_market_static_pin_builds_through_the_surface_seam(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The old tail crashed in surface(); the seam closure never raises."""
    import botforge.mods.kingdom.cogs.market as market
    import botforge.mods.kingdom.cogs.panel as panel

    async def _fr(guild_id: str) -> str:
        return "fr"

    monkeypatch.setattr(panel, "_guild_locale", _fr)

    view = await market.build_market_panel("123")
    assert isinstance(view, discord.ui.LayoutView), "the pin wears the seam's LayoutView"

    # the panel carries its title in the tree's TextDisplays and its two
    # entry buttons ride an ActionRow — never naked at the root
    texts: list[str] = []
    custom_ids: list[str] = []
    rows: list[Any] = []

    def _walk(item: Any) -> None:
        text = getattr(item, "content", None)
        if isinstance(text, str):
            texts.append(text)
        if isinstance(item, discord.ui.ActionRow):
            rows.append(item)
        cid = getattr(item, "custom_id", None)
        if cid:
            custom_ids.append(str(cid))
        for child in getattr(item, "children", None) or []:
            _walk(child)

    for child in getattr(view, "children", None) or []:
        _walk(child)

    assert texts, "the pinned title/help ride the view's TextDisplays"
    assert any("market" in str(cid).lower() or "chamber" in str(cid).lower() for cid in custom_ids), (
        "Market + Chamber entry buttons live in the pinned row"
    )


# ---------------------------------------------------------------------------
# 2. The camp's restore button reaches the SERVICE save_habitat.
# ---------------------------------------------------------------------------


class _Response:
    def is_done(self) -> bool:
        return True

    async def defer(self, **kwargs: Any) -> None:
        return None


class _Followup:
    def __init__(self) -> None:
        self.notes: list[str] = []

    async def send(self, content: str, **kwargs: Any) -> None:
        self.notes.append(str(content))


class _Interaction:
    def __init__(self) -> None:
        self.locale = "fr"
        self.response = _Response()
        self.followup = _Followup()
        self.user = Mock(id="42")
        self.client = Mock()
        self.client.get_guild = lambda _gid: object()


class _Realm:
    id = "r-1"
    name = "Aegis"
    slug = "aegis"
    archived_at = 1234
    king_id = "42"


@pytest.mark.asyncio
async def test_the_restore_button_saves_the_habitat_through_the_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ImportError'd cog import is gone — the seam is the service method.

    wake-hub-v1 (Drasah 24/11): the wake re-runs the founder's queue —
    dormant structure, then the hub panel deployed at once, and the
    merged ids saved through the SERVICE seam. The old empty-dict
    save merged nothing: the hub stayed empty until a manual heal.
    """
    import botforge.mods.kingdom.cogs.camp_beta as camp
    import botforge.mods.kingdom.cogs.realms as realms_cog
    import botforge.mods.kingdom.cogs.common as common

    saved: list[tuple[str, dict[str, Any]]] = []

    class _Realms:
        @staticmethod
        async def realm_of_slug(slug: str) -> Any:
            return _Realm() if slug == "aegis" else None

        @staticmethod
        async def restore_realm(realm_id: str) -> Any:
            return _Realm()

        @staticmethod
        async def save_habitat(realm_id: str, ids: dict[str, Any]) -> Any:
            saved.append((realm_id, dict(ids)))
            return _Realm()

    class _Stack:
        realms = _Realms

    monkeypatch.setattr(common, "wiring", lambda: _Stack())
    monkeypatch.setattr(camp, "wiring", lambda: _Stack())

    ensured: list[tuple[Any, Any, bool]] = []
    deployed: list[Any] = []

    async def _fake_ensure(guild: Any, realm: Any, dormant: bool = False) -> dict[str, str]:
        ensured.append((guild, realm, dormant))
        return {"category": "cat-1", "cat_forum": "forum-1"}

    async def _fake_deploy_hub(guild: Any, realm: Any, locale: str = "fr") -> str:
        deployed.append(guild)
        return "hub-msg-1"

    monkeypatch.setattr(realms_cog, "ensure_realm_structure", _fake_ensure)
    monkeypatch.setattr(realms_cog, "deploy_realm_hub", _fake_deploy_hub)

    button = camp.KingdomCampRestoreButton(
        "-yes", "aegis", "99", "Confirmer", discord.ButtonStyle.success
    )
    interaction = _Interaction()
    await button.callback(interaction)

    assert interaction.followup.notes == [
        "♻️ « Aegis » est réveillé — te voilà de nouveau son Roi fondateur."
    ], "the restore reaches success — never the ImportError note"
    assert saved == [
        ("r-1", {"category": "cat-1", "cat_forum": "forum-1", "hub_message": "hub-msg-1"})
    ], "the wake saves the rebuilt ids through the SERVICE seam"
    assert ensured and ensured[0][2] is True, "the structure is ensured dormant"
    assert deployed, "wake-hub-v1: the hub panel is deployed immediately"
