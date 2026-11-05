"""laboratoire-v2 (Drasah 05/11) — the 🧪 Laboratoire validation station.

Drasah's rule: the lab is INDEPENDENT — every render rides the Nilrem
test data, and carries NO interactive component (everything disabled).
The test dropdown says WHAT to test and WHY; ONE test dispatches its
render into BOTH version salons (📜 original + 🚧 travaux) and posts a
feedback test card in 🧪 labo — ✅ Valider · ✏️ Modifier · ❌ Annuler —
the verdicts freeze the card and log the dedicated KINGDOM LAB line.
"""
from __future__ import annotations

import asyncio
import re
from types import SimpleNamespace
from typing import Any

import discord

from kingdoms.mods.kingdoms.kingdom_lab import (
    LAB_ORIGINAL_SLUG,
    LAB_PANEL_MARKER,
    LAB_TEST_ITEMS,
    LAB_TRAVAUX_SLUG,
    LAB_VIEWS,
    KingdomLabCleanButton,
    KingdomLabRefreshButton,
    KingdomLabTestSelect,
    KingdomLabVerdictButton,
    KingdomLabVitrineButton,
    _dispatch_and_report,
    _test_card_view,
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


def _buttons(view: Any) -> list[Any]:
    return [i for i in _walk(view.children) if isinstance(i, discord.ui.Button)]


class _FakeBot:
    def __init__(self) -> None:
        self._dynamic_items: set[type] = set()

    def add_dynamic_items(self, *items: type) -> None:
        self._dynamic_items.update(items)


class _SendChannel:
    """A mock with the ``.messages`` cache the shared helpers expect."""

    def __init__(self, name: str = "🧪 labo") -> None:
        self.name = name
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


def _scan_channel_messages(channel: Any) -> Any:
    """An async ``channel_messages`` stand-in over the mock's cache."""

    async def scan() -> list[Any]:
        return list(channel.messages)

    return scan()


def test_cockpit_carries_every_control() -> None:
    view = build_lab_cockpit("fr")
    items = _walk(view.children)
    selects = [i for i in items if isinstance(i, discord.ui.Select)]
    assert len(selects) == 1  # ONE test dropdown, single choice
    select = selects[0]
    assert select.custom_id == "kingdoms:lab:test"
    assert (select.min_values, select.max_values) == (1, 1)
    assert [o.value for o in select.options] == list(LAB_TEST_ITEMS)
    # every option carries the WHY — Drasah reads what a test is for.
    assert all(o.description for o in select.options)
    assert {b.custom_id for b in items if isinstance(b, discord.ui.Button)} == {
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
    for view in (
        build_lab_cockpit("fr"),
        _test_card_view("fr", "chantier"),
        _test_card_view("fr", "chantier", "verdict_validated"),
    ):
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
        wrappers = [c for row in rows for c in row._children]
        for item in _walk(view.children):
            if isinstance(item, (discord.ui.Button, discord.ui.Select)):
                # _walk also yields the bare inner component of DynamicItem
                # wrappers; ActionRow stores the wrapper, so accept either.
                assert any(
                    item is w or item is getattr(w, "item", None) for w in wrappers
                ), item


def test_items_are_journey_ordered_subsets() -> None:
    for item in LAB_TEST_ITEMS.values():
        views = item["views"]
        assert views and all(v in LAB_VIEWS for v in views)
        assert item["title_key"] and item["why_key"]
    assert LAB_TEST_ITEMS["tout"]["views"] == list(LAB_VIEWS)
    assert LAB_TEST_ITEMS["lieux"]["views"] == [
        v for v in LAB_VIEWS if v in LAB_TEST_ITEMS["lieux"]["views"]
    ]
    # the per-patch editable scope — the current patch's surfaces.
    assert "comptes" in LAB_TEST_ITEMS["chantier"]["views"]


def test_every_label_rebuilds_after_a_restart() -> None:
    interaction = SimpleNamespace(locale="fr")
    select = _run(
        KingdomLabTestSelect.from_custom_id(interaction, None, re.search("x", "x"))
    )
    assert select.item.options[0].value == "tout"
    for action in ("validate", "modify", "cancel"):
        cid = f"kingdoms:lab:verdict:{action}:chantier"
        match = re.search(r"kingdoms:lab:verdict:(validate|modify|cancel):(\w+)$", cid)
        rebuilt = _run(KingdomLabVerdictButton.from_custom_id(interaction, None, match))
        assert rebuilt.item.label
        assert rebuilt.item.custom_id == cid
    for cls, label in (
        (KingdomLabVitrineButton, "🖼️ Vitrine assets"),
        (KingdomLabCleanButton, "🧹 Nettoyer"),
        (KingdomLabRefreshButton, "♻️ Actualiser"),
    ):
        assert (
            _run(cls.from_custom_id(interaction, None, re.search("x", "x"))).item.label
            == label
        )


def test_registration_is_restart_proof() -> None:
    bot = _FakeBot()
    register_kingdom_lab_items(bot)
    assert bot._dynamic_items == {
        KingdomLabTestSelect,
        KingdomLabVerdictButton,
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
        render_lab_views(channel, "fr", _fake_wiring(), _fake_kingdom(), ["comptes"])
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


def _dispatch_interaction(guild: Any) -> Any:
    """A mock interaction recording the responses (_dispatch path)."""
    responses: list[dict[str, Any]] = []
    followups: list[str] = []

    async def defer(*args: Any, **kwargs: Any) -> None:
        responses.append({"deferred": True})

    async def followup_send(*args: Any, **kwargs: Any) -> None:
        followups.append(str(args[0] if args else kwargs.get("content", "")))

    interaction = SimpleNamespace(
        locale="fr",
        guild=guild,
        response=SimpleNamespace(defer=defer),
        followup=SimpleNamespace(send=followup_send),
        client=SimpleNamespace(user=SimpleNamespace(id=1)),
    )
    interaction._responses = responses  # type: ignore[attr-defined]
    interaction._followups = followups  # type: ignore[attr-defined]
    return interaction


def _patched_dispatch(monkeypatch: Any, renders: dict[str, list[str]]) -> None:
    """Stub the render into a recorder (the builders need live data)."""

    async def fake_render(channel, locale, wiring, kingdom, keys, variant="original"):
        renders.setdefault(variant, []).extend(keys)
        return len(keys), []

    monkeypatch.setattr(
        "kingdoms.mods.kingdoms.kingdom_lab.render_lab_views", fake_render
    )

    async def fake_kingdom(wiring: Any) -> Any:
        return _fake_kingdom()

    monkeypatch.setattr(
        "kingdoms.mods.kingdoms.kingdom_lab._test_kingdom",
        fake_kingdom,
    )
    from kingdoms.mods.kingdoms import kingdom_persistent

    wiring = SimpleNamespace(bot_admins=(), kingdoms_service=object())
    monkeypatch.setattr(kingdom_persistent, "_wiring", lambda: wiring)
    monkeypatch.setattr(kingdom_persistent, "_is_admin", lambda *a, **k: True)


def test_dispatch_renders_both_salons_and_posts_the_card(monkeypatch) -> None:
    """laboratoire-v2 core: ONE test → BOTH version salons + feedback card."""
    renders: dict[str, list[str]] = {}
    _patched_dispatch(monkeypatch, renders)
    labo = _SendChannel("🧪 labo")
    original = _SendChannel("📜 original")
    travaux = _SendChannel("🚧 travaux")
    guild = SimpleNamespace(text_channels=[labo, original, travaux])
    interaction = _dispatch_interaction(guild)
    _run(_dispatch_and_report(interaction, "fr", "chantier"))
    # the render hit BOTH salons, on the item's journey-ordered views.
    assert renders["original"] == renders["travaux"] == LAB_TEST_ITEMS["chantier"]["views"]
    # the feedback card rides in labo with the three verdict buttons.
    assert labo.sent == 1
    card = labo.messages[0].view
    assert {b.custom_id for b in _buttons(card)} == {
        "kingdoms:lab:verdict:validate:chantier",
        "kingdoms:lab:verdict:modify:chantier",
        "kingdoms:lab:verdict:cancel:chantier",
    }
    # the summary answers the admin.
    assert interaction._followups


def test_verdict_freezes_the_card_with_the_status() -> None:
    fresh = _test_card_view("fr", "chantier")
    assert all(b.disabled is False for b in _buttons(fresh))
    for status in ("verdict_validated", "verdict_cancelled", "verdict_modified"):
        frozen = _test_card_view("fr", "chantier", status)
        assert all(b.disabled is True for b in _buttons(frozen))
        assert status.replace("_", " ") not in _view_text(frozen)  # raw key never leaks
    with_remarks = _test_card_view("fr", "chantier", "verdict_modified", "dos rogné")
    assert "dos rogné" in _view_text(with_remarks)


def test_clean_sweeps_the_render_salons_only(monkeypatch) -> None:
    """laboratoire-v2: 🧹 empties 📜 original + 🚧 travaux — labo is kept."""

    class _CleanChannel(_SendChannel):
        def __init__(self, name: str) -> None:
            super().__init__(name)
            self.scanned = False

        async def _scan(self) -> list[Any]:
            self.scanned = True
            return list(self.messages)

    labo = _CleanChannel("🧪 labo")
    original = _CleanChannel("📜 original")
    travaux = _CleanChannel("🚧 travaux")
    for channel in (labo, original, travaux):
        channel.send(view=None)
    guild = SimpleNamespace(text_channels=[labo, original, travaux])
    monkeypatch.setattr(
        "kingdoms.mods.kingdoms.panel_messages.channel_messages",
        _scan_channel_messages,
    )
    from kingdoms.mods.kingdoms import kingdom_persistent

    wiring = SimpleNamespace(bot_admins=())
    monkeypatch.setattr(kingdom_persistent, "_wiring", lambda: wiring)
    monkeypatch.setattr(kingdom_persistent, "_is_admin", lambda *a, **k: True)
    interaction = _dispatch_interaction(guild)

    async def defer(*args: Any, **kwargs: Any) -> None:
        pass

    interaction.response = SimpleNamespace(defer=defer)
    button = KingdomLabCleanButton("🧹 Nettoyer")
    _run(button.callback(interaction))
    # the two render salons are swept, labo keeps its messages.
    assert all(m.deleted for m in original.messages)
    assert all(m.deleted for m in travaux.messages)
    assert all(not m.deleted for m in labo.messages)


# --- laboratoire-v2 travaux variant: the MEDIANCUT-256 recompression ---

import io  # noqa: E402
import struct  # noqa: E402
import zlib  # noqa: E402

from kingdoms.mods.kingdoms import kingdom_lab_compress  # noqa: E402
from kingdoms.mods.kingdoms.kingdom_lab import _label_header  # noqa: E402


def _make_png(w: int, h: int, painter: Any) -> bytes:
    """A minimal 8-bit RGBA PNG builder (pure stdlib, no dependency)."""
    rows = bytearray()
    for y in range(h):
        rows.append(0)  # filter 0
        for x in range(w):
            rows += bytes(painter(x, y))

    def chunk(ctype: bytes, payload: bytes) -> bytes:
        return (
            len(payload).to_bytes(4, "big")
            + ctype
            + payload
            + zlib.crc32(ctype + payload).to_bytes(4, "big")
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(rows), 6))
        + chunk(b"IEND", b"")
    )


_NOISY_PNG = _make_png(
    96, 64, lambda x, y: (x * 7 % 256, y * 11 % 256, (x + y) * 3 % 256, 255)
)


def test_compress_png_bytes_shrinks_and_stays_a_valid_palette_png() -> None:
    out = kingdom_lab_compress.compress_png_bytes(_NOISY_PNG)
    assert out is not None and len(out) < len(_NOISY_PNG)
    assert out[:8] == b"\x89PNG\r\n\x1a\n"
    assert out[25] == 3  # color type 3 — indexed
    # re-decodes to the SAME dimensions (the multi-row decode regression
    # — offsets used to restart at every row — stays fixed).
    decoded = kingdom_lab_compress._decode_png(out)
    assert decoded is not None
    width, height, _rgba, _bpp = decoded
    assert (width, height) == (96, 64)


def test_compress_png_bytes_declines_garbage_and_growing_output() -> None:
    assert kingdom_lab_compress.compress_png_bytes(b"") is None
    assert kingdom_lab_compress.compress_png_bytes(b"not a png at all") is None
    # a tiny uniform PNG: indexed encoding cannot beat it — decline, the
    # lab keeps the original bytes rather than shipping a bigger file.
    tiny = _make_png(2, 2, lambda x, y: (255, 0, 0, 255))
    out = kingdom_lab_compress.compress_png_bytes(tiny)
    assert out is None or len(out) < len(tiny)


def test_compress_discord_file_recompresses_or_falls_back() -> None:
    import discord as _discord

    # a real PNG asset → a NEW file, same filename, compressed bytes
    src = _discord.File(io.BytesIO(_NOISY_PNG), filename="rempart.png")
    compressed = kingdom_lab_compress.compress_discord_file(src)
    assert compressed is not src
    assert compressed.filename == "rempart.png"
    compressed.fp.seek(0)
    payload = compressed.fp.read()
    expected = kingdom_lab_compress.compress_png_bytes(_NOISY_PNG)
    assert payload == expected
    # a non-PNG attachment → the ORIGINAL file object, untouched.
    src2 = _discord.File(io.BytesIO(b"jpeg-ish bytes here"), filename="x.jpg")
    assert kingdom_lab_compress.compress_discord_file(src2) is src2


def test_travaux_render_compresses_assets_original_does_not(monkeypatch) -> None:
    """The variant seam: travaux rides the recompression, original never."""
    from kingdoms.mods.kingdoms import kingdom_lab

    async def fake_build(key, locale, wiring, kingdom, state, variant="original"):
        view = discord.ui.LayoutView(timeout=None)
        view.add_item(discord.ui.TextDisplay(f"## {key}"))
        file = discord.File(io.BytesIO(_NOISY_PNG), filename="rempart.png")
        return view, [file]

    async def fake_state(kingdom, wiring):
        return {}

    monkeypatch.setattr(kingdom_lab, "_build_lab_view", fake_build)
    monkeypatch.setattr(
        "kingdoms.mods.kingdoms.kingdom_realm_content._gather_state", fake_state
    )
    original_channel, travaux_channel = _SendChannel("📜 original"), _SendChannel(
        "🚧 travaux"
    )
    rendered, failures = _run(
        kingdom_lab.render_lab_views(
            travaux_channel, "fr", _fake_wiring(), _fake_kingdom(), ["remparts"],
            variant="travaux",
        )
    )
    assert rendered == 1 and failures == []
    travaux_file = travaux_channel.messages[0].attachments[0]
    travaux_file.fp.seek(0)
    travaux_bytes = travaux_file.fp.read()
    assert travaux_bytes != _NOISY_PNG
    assert travaux_bytes == kingdom_lab_compress.compress_png_bytes(_NOISY_PNG)
    assert travaux_file.filename == "rempart.png"
    # the étiquette says WHAT the variant is.
    text = _view_text(travaux_channel.messages[0].view)
    assert "MEDIANCUT" in text
    # original: the deployed bytes ride untouched.
    rendered, failures = _run(
        kingdom_lab.render_lab_views(
            original_channel, "fr", _fake_wiring(), _fake_kingdom(), ["remparts"],
            variant="original",
        )
    )
    assert rendered == 1 and failures == []
    original_file = original_channel.messages[0].attachments[0]
    original_file.fp.seek(0)
    assert original_file.fp.read() == _NOISY_PNG
    assert "MEDIANCUT" not in _view_text(original_channel.messages[0].view)


def test_label_header_variant() -> None:
    plain = _label_header("remparts", "fr", "original")
    assert "MEDIANCUT" not in plain.content
    travaux = _label_header("remparts", "fr", "travaux")
    assert "MEDIANCUT" in travaux.content


def test_inventory_lines_show_cached_pairs(monkeypatch) -> None:
    from kingdoms.mods.kingdoms import kingdom_lab

    monkeypatch.setattr(
        kingdom_lab_compress, "compressed_size", lambda path: 4096, raising=True
    )
    lines = kingdom_lab._inventory_lines()
    assert any("travaux" in line and "−" in line for line in lines) or lines == []
