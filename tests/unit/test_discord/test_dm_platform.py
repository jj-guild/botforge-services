"""The DM platform seam (#407): send/edit/delete with opaque view handles.

Fakes are duck-typed (ADR-0011): no real discord objects, only the
surface the seam touches.
"""

from __future__ import annotations

import pytest

from botforge.discord.dm_platform import DiscordDMPlatform


class _FakeUser:
    def __init__(self, user_id: int) -> None:
        self.id = user_id
        self.sent: list[dict[str, object]] = []

    async def send(self, content, view=None):  # type: ignore[no-untyped-def]
        self.sent.append({"content": content, "view": view})
        return _FakeMessage(self, content)


class _FakeMessage:
    def __init__(self, user: _FakeUser, content: str) -> None:
        self._user = user
        self.content = content
        self.edited: list[dict[str, object]] = []
        self.deleted = False
        self.id = 7
        self.channel_id = 42

    async def edit(self, content, view=None):  # type: ignore[no-untyped-def]
        self.content = content
        self.edited.append({"content": content, "view": view})
        return self

    async def delete(self) -> None:
        self.deleted = True


class _FakeDMChannel:
    def __init__(self, message: _FakeMessage | None) -> None:
        self._message = message

    async def fetch_message(self, message_id: int) -> _FakeMessage:
        assert message_id == 7
        if self._message is None:
            raise RuntimeError("message gone")
        return self._message


class _FakeBot:
    """Cache-first lookups, fetch fallbacks — the seam's whole surface."""

    def __init__(self, user: _FakeUser | None = None, message: _FakeMessage | None = None) -> None:
        self.user = user
        self.message = message
        self.fetched_users: list[int] = []
        self.fetched_channels: list[int] = []

    def get_user(self, user_id: int) -> _FakeUser | None:
        return self.user if self.user is not None and self.user.id == user_id else None

    async def fetch_user(self, user_id: int) -> _FakeUser:
        self.fetched_users.append(user_id)
        if self.user is None or self.user.id != user_id:
            raise RuntimeError("unknown user")
        return self.user

    def get_channel(self, channel_id: int) -> _FakeDMChannel | None:
        return _FakeDMChannel(self.message) if channel_id == 42 else None

    async def fetch_channel(self, channel_id: int) -> _FakeDMChannel:
        self.fetched_channels.append(channel_id)
        if channel_id != 42:
            raise RuntimeError("unknown channel")
        return _FakeDMChannel(self.message)


async def test_send_dm_rides_the_view_through() -> None:
    user = _FakeUser(1)
    platform = DiscordDMPlatform(_FakeBot(user=user))  # type: ignore[arg-type]
    view = object()
    message = await platform.send_dm("1", "pick your civ", view)
    assert user.sent == [{"content": "pick your civ", "view": view}]
    assert message.content == "pick your civ", "the sent message rides back"


async def test_send_dm_resolves_through_fetch_when_the_cache_is_cold() -> None:
    user = _FakeUser(5)
    bot = _FakeBot(user=user)
    bot.get_user = lambda _id: None  # type: ignore[method-assign]  # cold cache
    platform = DiscordDMPlatform(bot)  # type: ignore[arg-type]
    await platform.send_dm(5, "hello")
    assert bot.fetched_users == [5], "the cache miss fell back to fetch"
    assert user.sent[0]["content"] == "hello"


async def test_send_dm_raises_when_the_user_is_unreachable() -> None:
    platform = DiscordDMPlatform(_FakeBot())  # type: ignore[arg-type]
    with pytest.raises(RuntimeError):
        await platform.send_dm("404", "hello")


async def test_edit_dm_resolves_a_persisted_ref() -> None:
    message = _FakeMessage(_FakeUser(1), "first")
    platform = DiscordDMPlatform(_FakeBot(message=message))  # type: ignore[arg-type]
    ref = {"channel_id": 42, "message_id": 7}
    view = object()
    await platform.edit_dm(ref, "second", view)
    assert message.edited == [{"content": "second", "view": view}]
    assert platform._bot.fetched_channels == [], "the channel came from the cache"


async def test_edit_dm_raises_when_the_ref_is_unresolvable() -> None:
    platform = DiscordDMPlatform(_FakeBot())  # type: ignore[arg-type]
    with pytest.raises(RuntimeError):
        await platform.edit_dm({"channel_id": 0, "message_id": 0}, "nope")


async def test_delete_dm_is_best_effort_on_every_miss() -> None:
    message = _FakeMessage(_FakeUser(1), "bye")
    platform = DiscordDMPlatform(_FakeBot(message=message))  # type: ignore[arg-type]
    await platform.delete_dm({"channel_id": 42, "message_id": 7})
    assert message.deleted is True
    # A ref pointing at nothing, a channel that vanished: never raises.
    await platform.delete_dm({"channel_id": 0, "message_id": 0})
    await platform.delete_dm({"channel_id": 9, "message_id": 7})
    assert platform._bot.fetched_channels == [9]
