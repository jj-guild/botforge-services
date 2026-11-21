"""demande-inscription-saison (Drasah 21/11) — the staff notice, the tests.

The incident: the Roi clicked « S'inscrire à la saison » and the staff
learned NOTHING — the Admission drawer counts the pendings, a counter
never previews itself. The fix rides ONE parametrable notice seam:

- every notice is DATA (kind table + conf/locales fr/en), never a
  hand-rolled send — annonce-ready, the #396 seam can absorb the table;
- the notice lands in the DECLARED salon (requests = 📬 demandes) with
  the declared admin role pinged, roles-only mentions, silent;
- the notice is a COURTESY: a missing salon, an unknown role or a
  refused send can never break the Roi's own flow;
- the join button fires the notice after the Roi's ack (the click is
  already answered whatever happens next).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import discord


class _Channel:
    def __init__(self) -> None:
        self.cid = 777
        self.sent: list[dict[str, Any]] = []

    async def send(self, **kwargs: Any) -> None:
        self.sent.append(dict(kwargs))


class _Guild:
    def __init__(self) -> None:
        self.gid = 123
        self._channels = {777: _Channel()}

    def get_channel(self, cid: int) -> Any:
        return self._channels.get(cid)


class _RolesService:
    async def resolve_role_id(self, guild_id: str, mod: str, role_key: str) -> int:
        return 4242


def _bot(guild: Any | None = None) -> Any:
    return SimpleNamespace(get_guild=lambda _id: guild, mod_roles_service=_RolesService())


def _patched_stored_channel(monkeypatch, channel_id: str) -> None:
    import botforge.discord.ui.panels_provisioning as provisioning

    async def fake_stored(gid: str, scope: str, key: str) -> str:
        assert (scope, key) == ("mod/kingdom", "requests"), "the notice's salon is data"
        return channel_id

    monkeypatch.setattr(provisioning, "stored_channel_id", fake_stored)


async def test_the_notice_lands_in_demandes_with_the_admin_ping(monkeypatch) -> None:
    """fr: text from the catalog, ping of the declared role, roles-only mentions."""
    from botforge.mods.kingdom.cogs.notices import announce_season_entry_request

    guild = _Guild()
    channel = guild._channels[777]
    _patched_stored_channel(monkeypatch, "777")
    realm = SimpleNamespace(name="Roc", king_name="Drasah")
    ok = await announce_season_entry_request(_bot(guild), "123", realm, "fr")
    assert ok is True, "the notice flew"
    assert len(channel.sent) == 1
    payload = channel.sent[0]
    content = str(payload["content"])
    assert content.startswith("<@&4242> "), "the declared kingdom_admin role is pinged"
    assert "Roc" in content and "Drasah" in content, "the notice names the realm and its Roi"
    mentions = payload["allowed_mentions"]
    assert isinstance(mentions, discord.AllowedMentions)
    assert mentions.roles is True and mentions.everyone is False and mentions.users is False
    assert payload.get("silent") is True, "a notice never wakes the whole server"


async def test_the_english_notice_reads_the_en_catalog(monkeypatch) -> None:
    from botforge.mods.kingdom.cogs.notices import announce_season_entry_request

    guild = _Guild()
    channel = guild._channels[777]
    _patched_stored_channel(monkeypatch, "777")
    realm = SimpleNamespace(name="Roc", king_name="Drasah")
    await announce_season_entry_request(_bot(guild), "123", realm, "en")
    content = str(channel.sent[0]["content"])
    assert "asks to enter the season" in content, "the en catalog renders the notice"


async def test_a_missing_salon_degrades_to_a_warning_never_a_raise(monkeypatch) -> None:
    from botforge.mods.kingdom.cogs.notices import post_notice

    _patched_stored_channel(monkeypatch, "")  # no stored salon id
    ok = await post_notice(_bot(_Guild()), "123", "season_entry_request", {}, "fr")
    assert ok is False, "a missing salon skips the notice"


async def test_an_unknown_kind_is_rejected_loudly() -> None:
    from botforge.mods.kingdom.cogs.notices import post_notice

    ok = await post_notice(_bot(None), "123", "not-a-kind", {}, "fr")
    assert ok is False


# -----------------------------------------------------------------------
# The join button — the Roi's ack first, the staff notice after
# -----------------------------------------------------------------------


class _Followup:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def send(self, content: Any = None, **kwargs: Any) -> None:
        self.sent.append({"content": content, **kwargs})


class _Response:
    def __init__(self) -> None:
        self.done = False

    async def defer(self, **kwargs: Any) -> None:
        self.done = True


def _click() -> Any:
    return SimpleNamespace(
        client=SimpleNamespace(),
        user=SimpleNamespace(id="1"),
        guild_id="123",
        locale="fr",
        response=_Response(),
        followup=_Followup(),
    )


async def test_a_successful_season_entry_request_fires_the_staff_notice(monkeypatch) -> None:
    """The join click: Roi acked, request saved, notice announced."""
    import unittest.mock as mock

    import botforge.mods.kingdom.cogs.notices as notices_mod
    import botforge.mods.kingdom.cogs.regie as regie_mod
    from botforge.mods.kingdom.cogs import common
    from botforge.mods.kingdom.cogs import realms as realms_mod

    realm = SimpleNamespace(id="r1", name="Roc", slug="roc", king_id="1", king_name="Drasah")

    class _Realms:
        called = False

        async def realm_of_slug(self, slug: str) -> Any:
            return realm

        async def request_season_entry(self, rid: str, king: str, season: str) -> Any:
            _Realms.called = True
            return realm

    class _Kingdoms:
        async def current_season(self) -> Any:
            return SimpleNamespace(id="s1")

    stack = SimpleNamespace(kingdoms=_Kingdoms(), realms=_Realms())

    notices: list[tuple[Any, ...]] = []

    async def fake_announce(bot: Any, guild_id: str, r: Any, locale: str) -> bool:
        notices.append((bot, guild_id, r, locale))
        return True

    async def regie_open(*args: Any, **kwargs: Any) -> bool:
        return True

    with mock.patch.object(common, "wiring", lambda: stack), \
            mock.patch.object(realms_mod, "wiring", lambda: stack), \
            mock.patch.object(notices_mod, "announce_season_entry_request", fake_announce), \
            mock.patch.object(regie_mod, "regie_open", regie_open):
        button = realms_mod.RealmJoinButton("S'inscrire", "roc")
        interaction = _click()
        await button.callback(interaction)

    assert _Realms.called, "the request was saved"
    assert interaction.followup.sent, "the Roi got his ack page"
    assert notices and notices[0][1] == "123" and notices[0][2] is realm, (
        "the staff notice rides the join success"
    )


async def test_a_refused_request_never_fires_the_notice() -> None:
    """A sas-closed click answers the Roi and posts NOTHING."""
    import unittest.mock as mock

    import botforge.mods.kingdom.cogs.notices as notices_mod
    import botforge.mods.kingdom.cogs.regie as regie_mod
    from botforge.mods.kingdom.cogs import common
    from botforge.mods.kingdom.cogs import realms as realms_mod

    realm = SimpleNamespace(id="r1", slug="roc", king_id="1")

    class _Realms:
        async def realm_of_slug(self, slug: str) -> Any:
            return realm

        async def request_season_entry(self, rid: str, king: str, season: str) -> Any:
            raise AssertionError("a closed sas never registers the realm")

    class _Kingdoms:
        async def current_season(self) -> Any:
            return SimpleNamespace(id="s1")

    stack = SimpleNamespace(kingdoms=_Kingdoms(), realms=_Realms())
    assert stack is not None

    async def regie_open(*args: Any, **kwargs: Any) -> bool:
        return False  # le sas est fermé

    async def fake_announce(*args: Any, **kwargs: Any) -> bool:
        raise AssertionError("a refused request posts no notice")

    with mock.patch.object(common, "wiring", lambda: stack), \
            mock.patch.object(realms_mod, "wiring", lambda: stack), \
            mock.patch.object(notices_mod, "announce_season_entry_request", fake_announce), \
            mock.patch.object(regie_mod, "regie_open", regie_open):
        button = realms_mod.RealmJoinButton("S'inscrire", "roc")
        interaction = _click()
        await button.callback(interaction)

    assert interaction.followup.sent, "the Roi is told the sas is closed"
