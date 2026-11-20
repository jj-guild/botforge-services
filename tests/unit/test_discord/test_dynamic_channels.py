"""The dynamic-channel seam (#408): provision/purge as data, not Discord objects.

Fakes are duck-typed (ADR-0011): a guild exposing default_role, me,
roles, and the create_*_channel recorders is the seam's whole surface.
"""

from __future__ import annotations

import pytest

from botforge.discord.dynamic_channels import DiscordDynamicChannelsPlatform


class _FakeRole:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeChannel:
    def __init__(self, channel_id: int) -> None:
        self.id = channel_id
        self.deleted = False

    async def delete(self) -> None:
        self.deleted = True


class _FakeGuild:
    def __init__(self) -> None:
        self.default_role = _FakeRole("@everyone")
        self.me = _FakeRole("the-bot")
        self.roles = [_FakeRole("Kingdom Lord"), _FakeRole("Kingdom King")]
        self.created_text: list[dict[str, object]] = []
        self.created_voice: list[dict[str, object]] = []
        self._next_id = 100

    async def create_text_channel(self, name, **kwargs):  # type: ignore[no-untyped-def]
        self.created_text.append({"name": name, **kwargs})
        return _FakeChannel(self._next_id + len(self.created_text))

    async def create_voice_channel(self, name, **kwargs):  # type: ignore[no-untyped-def]
        self.created_voice.append({"name": name, **kwargs})
        return _FakeChannel(200 + len(self.created_voice))


class _FakeBot:
    def __init__(self, guild: _FakeGuild) -> None:
        self._guild = guild
        self.channels: dict[int, _FakeChannel] = {}

    def get_guild(self, guild_id: int) -> _FakeGuild | None:
        return self._guild if guild_id == 1 else None

    def get_channel(self, channel_id: int) -> object | None:
        return self.channels.get(channel_id)


def _platform() -> tuple[DiscordDynamicChannelsPlatform, _FakeGuild, _FakeBot]:
    guild = _FakeGuild()
    bot = _FakeBot(guild)
    return (
        DiscordDynamicChannelsPlatform(bot),  # type: ignore[arg-type]
        guild,
        bot,
    )


async def test_create_text_channel_carries_the_declared_shape() -> None:
    platform, guild, bot = _platform()
    bot.channels[55] = _FakeChannel(55)
    await platform.create_channel("1", "salon-alice", category_id="55", position=7)
    recorded = guild.created_text[0]
    assert recorded["name"] == "salon-alice"
    assert recorded["position"] == 7
    assert recorded["category"] is bot.channels[55], "the category rides through by id"


async def test_the_overwrites_translate_data_into_discord_objects() -> None:
    platform, guild, _ = _platform()
    await platform.create_channel(
        "1",
        "salon",
        overwrites={
            "@everyone": {"view_channel": False, "send_messages": False},
            "Kingdom Lord": {"view_channel": True, "read_message_history": True},
            "@me": {"view_channel": True, "manage_messages": True},
        },
    )
    overwrites = guild.created_text[0]["overwrites"]
    assert isinstance(overwrites, dict)
    assert overwrites[guild.default_role].view_channel is False
    lord = next(r for r in guild.roles if r.name == "Kingdom Lord")
    assert overwrites[lord].read_message_history is True
    assert overwrites[guild.me].manage_messages is True


async def test_a_missing_role_is_skipped_never_fatal() -> None:
    platform, guild, _ = _platform()
    await platform.create_channel("1", "salon", overwrites={"Ghost Role": {"view_channel": True}})
    overwrites = guild.created_text[0]["overwrites"]
    assert list(overwrites) == [guild.me], "only the bot allow survives a fully-missed role list"


async def test_kind_voice_provisions_a_voice_channel() -> None:
    platform, guild, _ = _platform()
    await platform.create_channel("1", "room", kind="voice")
    assert guild.created_voice[0]["name"] == "room"
    assert not guild.created_text


async def test_create_channel_always_grants_the_bot_its_own_channel() -> None:
    """@me is added automatically — above all inside a private parent
    category: the bot must keep view AND manage_channels on the room
    it provisions, or the purge fails with 403 (#413)."""
    platform, guild, _ = _platform()
    await platform.create_channel(
        "1", "battle-room", overwrites={"@everyone": {"view_channel": False}}
    )
    overwrites = guild.created_text[0]["overwrites"]
    assert guild.me in overwrites
    me_overwrite = overwrites[guild.me]
    assert me_overwrite.view_channel is True
    assert me_overwrite.manage_channels is True
    assert me_overwrite.send_messages is True
    assert me_overwrite.read_message_history is True


async def test_an_explicit_bot_overwrite_is_normalized_to_the_full_bot_allow() -> None:
    """A caller-supplied @me can never lock the bot out: it is normalized
    to the standard bot allow (view + manage_channels always granted)."""
    platform, guild, _ = _platform()
    await platform.create_channel(
        "1", "room", overwrites={"@me": {"view_channel": False, "manage_channels": False}}
    )
    me_overwrite = guild.created_text[0]["overwrites"][guild.me]
    assert me_overwrite.view_channel is True
    assert me_overwrite.manage_channels is True


async def test_create_channel_raises_when_the_guild_is_unreachable() -> None:
    platform, _, _ = _platform()
    with pytest.raises(RuntimeError):
        await platform.create_channel("404", "salon")


async def test_delete_channel_is_best_effort_on_every_miss() -> None:
    platform, _, bot = _platform()
    live = _FakeChannel(123)
    bot.channels[123] = live
    await platform.delete_channel("123")
    assert live.deleted is True
    # Gone already, malformed id: neither raises, nothing to do.
    await platform.delete_channel("999")
    await platform.delete_channel("")
