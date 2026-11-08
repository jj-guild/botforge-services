"""Unit tests for the native Discord locale seam's guild default.

Rule under test: the guild default locale is the native
``guild.preferred_locale`` when the guild carries one (Community-enabled
guilds expose Server Settings → Language; others report the hard-coded
``en-US``) — and English on any missing or erroneous signal, never an
exception.
"""

from __future__ import annotations

import discord

from kingdoms.discord.locales import guild_locale, guild_locale_by_id, normalize


class _Guild:
    def __init__(self, preferred_locale: object) -> None:
        self.preferred_locale = preferred_locale


class _RaisingGuild:
    @property
    def preferred_locale(self) -> str:
        raise RuntimeError("boom")


def test_normalize_maps_raw_locales_onto_the_catalog() -> None:
    assert normalize("fr") == "fr"
    assert normalize("fr-FR") == "fr"
    assert normalize(discord.Locale.french) == "fr"
    assert normalize("en-US") == "en"


def test_normalize_falls_back_to_english() -> None:
    assert normalize("ja") == "en"
    assert normalize(None) == "en"
    assert normalize("") == "en"


def test_guild_locale_uses_the_native_preferred_locale() -> None:
    assert guild_locale(_Guild("fr")) == "fr"
    assert guild_locale(_Guild(discord.Locale.french)) == "fr"
    assert guild_locale(_Guild("en-US")) == "en"  # non-Community default


def test_guild_locale_falls_back_to_english_on_any_failure() -> None:
    assert guild_locale(None) == "en"
    assert guild_locale(_RaisingGuild()) == "en"
    assert guild_locale(object()) == "en"  # no preferred_locale attribute


class _Bot:
    def get_guild(self, guild_id: int) -> object:
        return _Guild("fr") if guild_id == 1 else None


class _RaisingBot:
    def get_guild(self, guild_id: int) -> object:
        raise RuntimeError("boom")


def test_guild_locale_by_id_resolves_the_live_guild() -> None:
    assert guild_locale_by_id(_Bot(), "1") == "fr"


def test_guild_locale_by_id_falls_back_to_english_on_any_failure() -> None:
    assert guild_locale_by_id(_Bot(), "2") == "en"  # guild not in cache
    assert guild_locale_by_id(_Bot(), "not-a-number") == "en"  # invalid id
    assert guild_locale_by_id(_Bot(), "") == "en"  # empty id
    assert guild_locale_by_id(object(), "1") == "en"  # no get_guild
    assert guild_locale_by_id(_RaisingBot(), "1") == "en"  # read error
