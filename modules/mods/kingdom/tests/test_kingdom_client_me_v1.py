"""client-me-v1 + draft-sheet-cv2 (Drasah 28/11).

The live incident of 27-28/11: the bot's server role held every right
yet the mod behaved as if it had none — no @me entry on the vocal it
had just created, a silent heal, « no Manage Channels » probes. The
root cause: every self-permission decision reads ``guild.me`` (the
member cache) and silently no-ops when it comes back None. This patch
resolves the client member robustly (cache first, FETCH fallback),
verifies the @me allow at the channel's BIRTH, and sends the draft
sheet as Components V2 blocks (Discord forbids embeds on a CV2
message — the 50035 the live click hit).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from botforge.discord.dynamic_channels import (
    DiscordDynamicChannelsPlatform,
    resolve_client_member,
)


class _Member:
    """A hashable member double (SimpleNamespace is not hashable — the
    overwrites dict uses members as keys)."""

    def __init__(self, uid: int, manage: bool = True) -> None:
        self.id = uid
        self.guild_permissions = SimpleNamespace(manage_channels=manage)


class _Response:
    """The interaction response recorder (the affaire-49 double)."""

    def __init__(self) -> None:
        self.done = False

    def is_done(self) -> bool:
        return self.done

    async def defer(self, ephemeral: bool = False) -> None:
        self.done = True


def _interaction(user_id: str = "123") -> Any:
    return SimpleNamespace(locale="fr", user=SimpleNamespace(id=user_id), response=_Response())


# ---------------------------------------------------------------------------
# resolve_client_member — the robust « who am I » resolution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_prefers_the_cached_member() -> None:
    """A populated cache is the fast path — no fetch, no API call."""
    member = SimpleNamespace(id=42)
    calls: list[int] = []

    async def _fetch(_uid: int) -> Any:
        calls.append(_uid)
        return member

    guild = SimpleNamespace(me=member, fetch_member=_fetch)
    assert await resolve_client_member(guild) is member
    assert calls == []


@pytest.mark.asyncio
async def test_resolve_falls_back_to_the_fetch_when_the_cache_is_empty() -> None:
    """guild.me None (empty member cache) — the client's OWN id still resolves."""
    member = _Member(7)
    calls: list[int] = []

    async def _fetch(uid: int) -> Any:
        calls.append(uid)
        return member

    state = SimpleNamespace(user=SimpleNamespace(id=7))
    guild = SimpleNamespace(me=None, fetch_member=_fetch, _state=state)
    assert await resolve_client_member(guild) is member
    assert calls == [7]


@pytest.mark.asyncio
async def test_resolve_returns_none_on_a_refused_fetch() -> None:
    """A refused fetch is a silent None — never a raise, never a ghost heal."""

    async def _fetch(_uid: int) -> Any:
        raise RuntimeError("unknown member")

    state = SimpleNamespace(user=SimpleNamespace(id=7))
    guild = SimpleNamespace(me=None, fetch_member=_fetch, _state=state)
    assert await resolve_client_member(guild) is None


@pytest.mark.asyncio
async def test_resolve_returns_none_without_a_resolvable_id() -> None:
    """No me, no fetch surface, no state user — None, best effort."""
    guild = SimpleNamespace(me=None)
    assert await resolve_client_member(guild) is None
    state = SimpleNamespace()
    guild2 = SimpleNamespace(me=None, fetch_member=_fetch_none, _state=state)
    assert await resolve_client_member(guild2) is None


async def _fetch_none(_uid: int) -> Any:  # pragma: no cover — never reached
    return None


# ---------------------------------------------------------------------------
# The birth check — the @me allow verified on the LIVE channel
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_birth_check_verifies_the_allow(monkeypatch: pytest.MonkeyPatch) -> None:
    """A created channel whose @me allow landed surfaces the ✅ in the logs."""
    import logging

    member = _Member(7)
    created: dict[str, Any] = {}

    channel = SimpleNamespace(
        id=99,
        overwrites_for=lambda _me: SimpleNamespace(manage_channels=True),
    )

    async def _create_voice(name: str, **kwargs: Any) -> Any:
        created["name"] = name
        created["overwrites"] = kwargs.get("overwrites")
        return channel

    async def _fetch(_uid: int) -> Any:
        return member

    guild = SimpleNamespace(
        me=None,
        fetch_member=_fetch,
        _state=SimpleNamespace(user=SimpleNamespace(id=7)),
        create_voice_channel=_create_voice,
    )

    async def _guild(_gid: str) -> Any:
        return guild

    platform = DiscordDynamicChannelsPlatform(SimpleNamespace())
    monkeypatch.setattr(platform, "_guild", _guild)

    records: list[tuple[int, str]] = []

    class _Log(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append((record.levelno, record.getMessage()))

    handler = _Log()
    logger = logging.getLogger("botforge.discord.dynamic_channels")
    logger.addHandler(handler)
    try:
        out = await platform.create_channel("10", "⚔️-test", kind="voice")
    finally:
        logger.removeHandler(handler)

    assert out is channel
    assert created["name"] == "⚔️-test"
    # the @me allow rides the creation overwrites (manage_channels=True)
    assert any(
        getattr(ow, "manage_channels", False) is True for ow in created["overwrites"].values()
    ), "the fetched member carries its allow at creation"
    assert any(lvl == logging.INFO and "birth check ✅" in msg for lvl, msg in records), records


# ---------------------------------------------------------------------------
# The mod's heal consumes the same robust resolution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mod_heal_sees_itself_through_the_fetch() -> None:
    """A bot with an empty member cache still heals its own channel."""
    import botforge.mods.kingdom.cogs.battle as battle_module

    member = _Member(7)
    applied: list[Any] = []

    class _Overwrite:
        def __init__(self) -> None:
            self.manage_channels = False

    class _Channel:
        def permissions_for(self, _me: Any) -> Any:
            return SimpleNamespace(manage_channels=False)

        def overwrites_for(self, _me: Any) -> Any:
            return _Overwrite()

        async def set_permissions(self, target: Any, overwrite: Any = None) -> None:
            applied.append((target, overwrite))

    async def _fetch(_uid: int) -> Any:
        return member

    guild = SimpleNamespace(
        me=None,
        fetch_member=_fetch,
        _state=SimpleNamespace(user=SimpleNamespace(id=7)),
    )
    await battle_module._ensure_bot_self_manage_safe(guild, _Channel())
    assert applied, "the heal wrote the @me allow through the FETCHED member"
    assert applied[0][0] is member
    assert applied[0][1].manage_channels is True


# ---------------------------------------------------------------------------
# draft-sheet-cv2 — the 50035 fix (embeds are forbidden on a CV2 message)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_draft_button_sends_cv2_blocks_never_an_embed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The 📜 window rides a Components V2 view — the embed kwarg is gone."""
    import botforge.mods.kingdom.cogs.battle as battle_module

    interaction = _interaction()
    captured: dict[str, Any] = {}

    async def _capture(target: Any, content: Any = None, **kwargs: Any) -> None:
        captured["content"] = content
        captured["kwargs"] = kwargs

    async def _fake_by_id(_st: Any, _aid: str) -> Any:
        return SimpleNamespace(id="a-1")

    async def _fake_embed(_st: Any, _at: Any, _s: Any) -> Any:
        return SimpleNamespace(
            title="📜 Draft — cenotes",
            description="l'aide de la draft",
            fields=[SimpleNamespace(name="⚔️ attaquant", value="francs")],
        )

    monkeypatch.setattr(battle_module, "wiring", lambda: SimpleNamespace())
    monkeypatch.setattr(battle_module, "attack_by_id", _fake_by_id)
    monkeypatch.setattr(battle_module, "draft_sheet_embed", _fake_embed)
    monkeypatch.setattr(battle_module, "open_unique_ephemeral", _capture)

    button = battle_module.DraftViewButton("attack-1", "📜 Voir la draft")
    await button.callback(interaction)

    assert "embed" not in captured["kwargs"], "an embed would re-trigger the 50035"
    assert captured["kwargs"].get("view") is not None, "the sheet rides a CV2 view"
    assert captured["content"] is None


def test_embed_sheet_blocks_map_the_sheet_content() -> None:
    """title/description/fields map onto CV2 text blocks, duck-typed."""
    import botforge.mods.kingdom.cogs.battle as battle_module

    blocks = battle_module._embed_sheet_blocks(
        SimpleNamespace(
            title="📜 Draft",
            description="aide",
            fields=[SimpleNamespace(name="⚔️ a", value="francs")],
        )
    )
    assert len(blocks) == 3
    texts = [str(getattr(b, "content", "") or "") for b in blocks]
    joined = " ".join(texts)
    assert "📜 Draft" in joined and "aide" in joined and "francs" in joined

    # an unreadable fake still yields ONE block — never an empty view
    assert len(battle_module._embed_sheet_blocks(object())) == 1
