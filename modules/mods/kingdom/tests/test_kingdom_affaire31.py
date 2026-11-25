"""T4a logs-admin (Drasah 25/11) — the admin trail seam, the tests.

The merge: ONE salon 📜 logs carries the timestamped trail AND the
requests (the notices' season entry notice re-routed onto it), every
admin MUTATION logs one line — the navigation stays silent.

- a line is DATA: the emoji rides the KINDS table, the clock rides the
  Paris seam (fmt_paris), the salon is the DECLARED key admin_log
  resolved by its STORED id — never a display name;
- the trail is a COURTESY: a missing guild or salon degrades to False,
  never a raise on the admin flow that fired it.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any


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


def _patched_stored_channel(monkeypatch: Any, channel_id: str) -> None:
    import botforge.discord.ui.panels_provisioning as provisioning

    async def fake_stored(gid: str, scope: str, key: str) -> str:
        assert (scope, key) == ("mod/kingdom", "admin_log"), "the log salon is data"
        return channel_id

    monkeypatch.setattr(provisioning, "stored_channel_id", fake_stored)


async def test_one_line_is_a_stamped_mention_with_the_kind_emoji() -> None:
    """« [stamp] ⚖️ <@42> action » — the three parts, nothing hand-rolled."""
    from botforge.mods.kingdom.cogs.admin_logs import admin_log_line

    line = admin_log_line("decision", "arbitrage Roc", "42", moment=1_800_000_000.0)
    assert line.startswith("["), "the stamp rides the Paris clock seam"
    assert "⚖️ <@42> arbitrage Roc" in line


async def test_an_unknown_kind_falls_back_never_crashes() -> None:
    """A call site that forgets its kind still logs (the decision hue)."""
    from botforge.mods.kingdom.cogs.admin_logs import admin_log_line

    line = admin_log_line("mystery", "whatever", "42", moment=0.0)
    assert "⚖️" in line


async def test_a_missing_guild_degrades_to_false_never_a_raise() -> None:
    """A trail line can never break the admin flow that fired it."""
    from botforge.mods.kingdom.cogs.admin_logs import log_admin_action_safe

    bot = SimpleNamespace(get_guild=lambda _id: None)
    assert await log_admin_action_safe(bot, "123", "season", "start", "42") is False


async def test_the_line_lands_in_the_declared_logs_salon(monkeypatch: Any) -> None:
    """The salon is the stored admin_log id; the line is silent, mention-only."""
    from botforge.mods.kingdom.cogs.admin_logs import log_admin_action_safe

    import discord

    guild = _Guild()
    channel = guild._channels[777]
    _patched_stored_channel(monkeypatch, "777")
    bot = SimpleNamespace(get_guild=lambda _id: guild)
    ok = await log_admin_action_safe(bot, "123", "time", "pause", "42")
    assert ok is True
    assert len(channel.sent) == 1
    payload = channel.sent[0]
    assert "@42" in str(payload["content"]), "the line names the admin"
    assert payload.get("silent") is True, "a trail never wakes the server"
    mentions = payload["allowed_mentions"]
    assert isinstance(mentions, discord.AllowedMentions)
    assert mentions.roles is False and mentions.everyone is False


def test_the_yaml_declares_one_logs_salon_no_demandes() -> None:
    """admin-logs-v2: the requests block is GONE, admin_log renamed logs."""
    import yaml

    data = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "conf" / "mod.yaml").read_text(encoding="utf-8")
    )
    keys = [str(c["key"]) for c in data.get("channels") or []]
    assert "requests" not in keys, "the demandes salon is merged into logs"
    channels = {str(c["key"]): c for c in data.get("channels") or []}
    assert str(channels["admin_log"]["display_name"]) == "📜 logs"


def test_the_season_entry_notice_is_rerouted_onto_the_logs() -> None:
    """The ONE live branch of the old requests salon now lands in logs."""
    from botforge.mods.kingdom.cogs.notices import NOTICES

    assert NOTICES["season_entry_request"]["channel"] == "admin_log"
