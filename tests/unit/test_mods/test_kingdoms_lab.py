"""laboratoire-v1 (Drasah 05/11) — the 🧪 Laboratoire cockpit.

Drasah's rule: the lab is INDEPENDENT — every render rides the Nilrem
test data, posts in the Labo salon only, and carries NO interactive
component (everything disabled). The multi-selection renders the
player-journey order; the presets are one-click programmes; the
🧾 Chantier du jour preset is the editable per-patch scope.
"""
from __future__ import annotations

import asyncio
import re
from types import SimpleNamespace
from typing import Any

import discord

from kingdoms.mods.kingdoms.kingdom_lab import (
    LAB_PANEL_MARKER,
    LAB_PRESETS,
    LAB_VIEWS,
    KingdomLabCleanButton,
    KingdomLabRefreshButton,
    KingdomLabVersionSelect,
    KingdomLabViewSelect,
    KingdomLabVitrineButton,
    _LabPresetButton,
    build_lab_cockpit,
    deploy_lab_panel,
    neutralize_view,
    register_kingdom_lab_items,
    render_lab_views,
)


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def _walk(children: Any) -> list[Any]:
    out: list[Any] = []
    for child in children or []:
        out.append(child)
        # DynamicItem wrappers expose their inner component as ``.item``.
        inner = getattr(child, "item", None)
        if inner is not None:
            out.append(inner)
        out.extend(_walk(getattr(child, "children", None)))
    return out


def _view_text(view: Any) -> str:
    return "\n".join(
        str(getattr(item, "content", "") or "") for item in _walk(view.children)
    )


class _FakeBot:
    def __init__(self) -> None:
        self._dynamic_items: set[type] = set()

    def add_dynamic_items(self, *items: type) -> None:
        self._dynamic_items.update(items)


class _SendChannel:
    """A mock with the ``.messages`` cache the shared helpers expect."""

    def __init__(self) -> None:
        self.name = "🧪 labo"
        self.messages: list[Any] = []
        self.sent: int = 0

    async def send(self, **kwargs: Any) -> Any:
        self.sent += 1
        view = kwargs.get("view")
        message = SimpleNamespace(
            content="",
            components=list(getattr(view, "children", None) or []),
            layout=None,
            attachments=kwargs.get("files") or [],
            view=kwargs.get("view"),
            pinned=False,
            edits=0,
            deleted=False,
        )
        message.pin = _make_pin(message)
        message.edit = _make_edit(message)
        message.delete = _make_delete(message)
        self.messages.append(message)
        return message


def _make_pin(message: Any) -> Any:
    async def pin() -> None:
        message.pinned = True

    return pin


def _make_edit(message: Any) -> Any:
    async def edit(**kwargs: Any) -> None:
        message.edits += 1
        message.view = kwargs.get("view") or message.view

    return edit


def _make_delete(message: Any) -> Any:
    async def delete(**kwargs: Any) -> None:
        message.deleted = True

    return delete


def test_cockpit_carries_every_control() -> None:
    view = build_lab_cockpit("fr")
    items = _walk(view.children)
    selects = [i for i in items if isinstance(i, discord.ui.Select)]
    multi = [s for s in selects if s.custom_id == "kingdoms:lab:views"]
    assert len(multi) == 1
    assert multi[0].min_values == 1
    assert multi[0].max_values == len(LAB_VIEWS)  # MULTI-selection, no 1-by-1
    versions = [s for s in selects if s.custom_id == "kingdoms:lab:version"]
    assert len(versions) == 1
    assert [o.value for o in versions[0].options] == ["original", "v1"]
    custom_ids = {
        b.custom_id
        for b in items
        if isinstance(b, discord.ui.Button)
    }
    assert custom_ids == {
        "kingdoms:lab:preset:all",
        "kingdoms:lab:preset:lieux",
        "kingdoms:lab:preset:marche",
        "kingdoms:lab:preset:chantier",
        "kingdoms:lab:vitrine",
        "kingdoms:lab:clean",
        "kingdoms:lab:refresh",
    }
    assert LAB_PANEL_MARKER in _view_text(view)


def test_cockpit_top_level_children_are_layout_components() -> None:
    """Live 50035 (Drasah 05/11): Discord rejects a bare interactive item
    at the root of a LayoutView (« In components.N: type must be one of
    (1, 9, 10, 12, 13, 14, 17) ») — the cockpit send failed silently
    (best-effort) and the Labo salon stayed empty. Every top-level
    child must be a layout component; interactive items ride INSIDE an
    ActionRow."""
    view = build_lab_cockpit("fr")
    interactive = (
        discord.ui.Button,
        discord.ui.Select,
        discord.ui.TextInput,
    )
    for child in view.children:
        assert not isinstance(
            child, interactive
        ), f"bare interactive component at the LayoutView root: {type(child).__name__}"
    rows = [c for c in view.children if isinstance(c, discord.ui.ActionRow)]
    selects = [i for i in _walk(view.children) if isinstance(i, discord.ui.Select)]
    assert len(selects) == 2
    for select in selects:
        assert any(select in row._children for row in rows)


def test_presets_are_journey_ordered_subsets() -> None:
    for keys in LAB_PRESETS.values():
        assert keys and all(k in LAB_VIEWS for k in keys)
    # the walkthrough presets follow the player-journey order; the
    # editable « chantier » scope keeps its own curated order.
    for name in ("all", "lieux"):
        keys = LAB_PRESETS[name]
        assert list(keys) == [k for k in LAB_VIEWS if k in keys]
    assert LAB_PRESETS["all"] == LAB_VIEWS
    assert LAB_PRESETS["lieux"] == (
        "hub",
        "conseil",
        "remparts",
        "comptes",
        "paroisse",
        "voliere",
    )
    # the per-patch editable scope — currently the comptes-cv2 beta.
    assert "comptes" in LAB_PRESETS["chantier"]


def test_every_label_rebuilds_after_a_restart() -> None:
    interaction = SimpleNamespace(locale="fr")
    for preset in ("all", "lieux", "marche", "chantier"):
        match = re.search(r"(\w+)$", f"kingdoms:lab:preset:{preset}")
        rebuilt = _run(_LabPresetButton.from_custom_id(interaction, None, match))
        assert rebuilt.item.label
        assert rebuilt.item.custom_id == f"kingdoms:lab:preset:{preset}"
    assert (
        _run(
            KingdomLabViewSelect.from_custom_id(interaction, None, re.search("x", "x"))
        ).item.max_values
        == len(LAB_VIEWS)
    )
    assert (
        _run(
            KingdomLabVersionSelect.from_custom_id(
                interaction, None, re.search("x", "x")
            )
        ).item.options[0].value
        == "original"
    )
    assert (
        _run(
            KingdomLabVitrineButton.from_custom_id(
                interaction, None, re.search("x", "x")
            )
        ).item.label
        == "🖼️ Vitrine assets"
    )
    assert (
        _run(
            KingdomLabCleanButton.from_custom_id(interaction, None, re.search("x", "x"))
        ).item.label
        == "🧹 Nettoyer"
    )
    assert (
        _run(
            KingdomLabRefreshButton.from_custom_id(
                interaction, None, re.search("x", "x")
            )
        ).item.label
        == "♻️ Actualiser"
    )


def test_registration_is_restart_proof() -> None:
    bot = _FakeBot()
    register_kingdom_lab_items(bot)
    assert bot._dynamic_items == {
        _LabPresetButton,
        KingdomLabViewSelect,
        KingdomLabVersionSelect,
        KingdomLabVitrineButton,
        KingdomLabCleanButton,
        KingdomLabRefreshButton,
    }


def test_neutralize_disables_everything() -> None:
    view = discord.ui.LayoutView(timeout=None)
    button = discord.ui.Button(label="x", custom_id="kingdoms:market:tech")
    view.add_item(discord.ui.ActionRow(button))
    container = discord.ui.Container()
    container.add_item(discord.ui.TextDisplay("t"))
    inner = discord.ui.ActionRow(
        discord.ui.Button(label="y", custom_id="kingdoms:lieux:conseil")
    )
    container.add_item(inner)
    view.add_item(container)
    select = discord.ui.Select(
        options=[discord.SelectOption(label="A", value="a")], custom_id="kingdoms:x"
    )
    view.add_item(discord.ui.ActionRow(select))
    neutralize_view(view)
    for item in _walk(view.children):
        if isinstance(item, (discord.ui.Button, discord.ui.Select)):
            assert item.disabled is True, item


def _fake_wiring() -> Any:
    return SimpleNamespace(
        kingdoms_service=None,
        territories_service=None,
        economy_service=None,
        attacks_service=None,
    )


def _fake_kingdom() -> Any:
    return SimpleNamespace(
        id="k-nilrem",
        name="Nilrem",
        civilizations=[],
        civilization_acquisitions={},
        tech_points_bank=0,
    )


def test_render_posts_labelled_neutralized_views() -> None:
    channel = _SendChannel()
    rendered, failures = _run(
        render_lab_views(
            channel, "fr", _fake_wiring(), _fake_kingdom(), ["taverne", "nope"]
        )
    )
    assert rendered == 1 and failures == []
    assert channel.sent == 1
    view = channel.messages[0].view
    items = _walk(view.children)
    # the étiquette rides FIRST — the salon reads like a walkthrough.
    assert isinstance(view.children[0], discord.ui.TextDisplay)
    assert str(view.children[0].content).startswith("## 🍺")
    # INDEPENDENCE: every interactive component of the vitrine is inert.
    for item in items:
        if isinstance(item, (discord.ui.Button, discord.ui.Select)):
            assert item.disabled is True, item


def test_render_failure_is_isolated() -> None:
    channel = _SendChannel()
    rendered, failures = _run(
        render_lab_views(
            channel, "fr", _fake_wiring(), _fake_kingdom(), ["comptes"]
        )
    )
    assert isinstance(rendered, int) and isinstance(failures, list)


def test_cockpit_deploys_once_then_edits_in_place() -> None:
    channel = _SendChannel()
    guild = SimpleNamespace(text_channels=[channel])
    assert _run(deploy_lab_panel(guild, "fr")) is True
    assert channel.sent == 1 and channel.messages[0].pinned is True
    assert _run(deploy_lab_panel(guild, "fr")) is True
    assert channel.sent == 1  # edited in place, never duplicated
    assert channel.messages[0].edits == 1
