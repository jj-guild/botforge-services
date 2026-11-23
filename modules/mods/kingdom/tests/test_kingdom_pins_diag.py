"""The /kingdom pin diagnosis (epic #412 T1) — one status per panel.

R6 discipline (tests/architecture/test_layering.py): a file under
modules/ OUTSIDE cogs/ may never import discord. These tests reach the
diagnosis module lazily (``_diag()``) and reuse ITS discord namespace
(``_diag().discord.NotFound``), and reach the pin registry through
importlib — no discord import line in this file.
"""

from __future__ import annotations

import asyncio
import importlib
from types import SimpleNamespace

_CLIENT_ID = "42"
_GUILD_ID = "1234"
_CHANNEL_ID = "5678"


class _Resp:
    """A minimal HTTP response for discord exception construction."""

    def __init__(self, status: int = 404) -> None:
        self.status = status
        self.reason = "Not Found"


class _Message:
    def __init__(self, *, pinned: bool = True) -> None:
        self.id = 999
        self.pinned = pinned


class _Channel:
    def __init__(self, *, exc: BaseException | None = None, pinned: bool = True) -> None:
        self._exc = exc
        self._message = _Message(pinned=pinned)

    async def fetch_message(self, message_id: int) -> _Message:
        if self._exc is not None:
            raise self._exc
        return self._message


class _Guild:
    def __init__(self, *, channel: object | None) -> None:
        self._channel = channel

    def get_channel(self, channel_id: int) -> object | None:
        return self._channel


class _Client:
    def __init__(self, *, guild: object | None) -> None:
        self._guild = guild

    def get_guild(self, guild_id: int) -> object | None:
        return self._guild


def _diag():
    from botforge.mods.kingdom.cogs.kingdom import pins_diag

    return pins_diag


def _static_pins():
    return importlib.import_module("botforge.discord.static_pins")


def _spec(
    key: str,
    *,
    scope: str = "mod/kingdom",
    channel_id: str | None = _CHANNEL_ID,
    message_id: str | None = "777",
):
    async def resolve_channel(guild_id: str) -> str | None:
        return channel_id

    async def resolve_message_id(guild_id: str) -> str | None:
        return message_id

    return SimpleNamespace(
        key=key,
        scope=scope,
        resolve_channel=resolve_channel,
        resolve_message_id=resolve_message_id,
    )


def _patch_registry(monkeypatch, specs: list) -> None:
    monkeypatch.setattr(_static_pins(), "registered_static_pins", lambda: list(specs))


def test_the_report_skips_foreign_scopes(monkeypatch) -> None:
    """Only mod/kingdom surfaces ride the diagnosis."""
    diag = _diag()
    _patch_registry(
        monkeypatch,
        [
            _spec("panel:mod:kingdom:home"),
            _spec("panel:mod:other:home", scope="mod/other"),
            _spec("view:home", scope=""),
        ],
    )
    client = _Client(guild=None)
    out = asyncio.run(diag.pins_report(client, _GUILD_ID))
    assert [key for key, _status in out] == ["panel:mod:kingdom:home"]


def test_the_report_rejects_non_numeric_guild_ids(monkeypatch) -> None:
    """A garbage guild id degrades to an empty report, never a raise."""
    diag = _diag()
    _patch_registry(monkeypatch, [_spec("panel:mod:kingdom:home")])
    assert asyncio.run(diag.pins_report(_Client(guild=None), "")) == []
    assert asyncio.run(diag.pins_report(_Client(guild=None), "abc")) == []


def test_the_report_names_the_unprovisioned_channel(monkeypatch) -> None:
    """Step 1 — no stored channel resolution: rerun the Repair."""
    diag = _diag()
    _patch_registry(monkeypatch, [_spec("panel:mod:kingdom:admin:console", channel_id=None)])
    out = asyncio.run(diag.pins_report(_Client(guild=_Guild(channel=None)), _GUILD_ID))
    assert out == [("panel:mod:kingdom:admin:console", "salon non provisionné (résolution absente — refaire un Repair)")]


def test_the_report_names_the_uncached_guild(monkeypatch) -> None:
    """Step 2 — the guild left the bot's cache."""
    diag = _diag()
    _patch_registry(monkeypatch, [_spec("panel:mod:kingdom:admin:console")])
    out = asyncio.run(diag.pins_report(_Client(guild=None), _GUILD_ID))
    assert out == [("panel:mod:kingdom:admin:console", f"serveur {_GUILD_ID} hors cache du bot")]


def test_the_report_names_the_uncached_channel(monkeypatch) -> None:
    """Step 3 — the channel exists but the bot cannot see it."""
    diag = _diag()
    _patch_registry(monkeypatch, [_spec("panel:mod:kingdom:admin:console")])
    out = asyncio.run(diag.pins_report(_Client(guild=_Guild(channel=None)), _GUILD_ID))
    assert out == [("panel:mod:kingdom:admin:console", f"salon <#{_CHANNEL_ID}> hors cache du bot (droits salon cassés ?)")]


def test_the_report_names_the_never_pinned_panel(monkeypatch) -> None:
    """Step 4 — the channel is found but the pin never landed."""
    diag = _diag()
    _patch_registry(monkeypatch, [_spec("panel:mod:kingdom:admin:console", message_id=None)])
    client = _Client(guild=_Guild(channel=_Channel()))
    out = asyncio.run(diag.pins_report(client, _GUILD_ID))
    assert out == [
        (
            "panel:mod:kingdom:admin:console",
            f"jamais épinglé (salon <#{_CHANNEL_ID}> trouvé — l'épinglage n'y est jamais passé)",
        )
    ]


def test_the_report_names_the_deleted_message(monkeypatch) -> None:
    """Step 5 — the pinned message was deleted since the last pass."""
    diag = _diag()
    _patch_registry(monkeypatch, [_spec("panel:mod:kingdom:admin:console")])
    channel = _Channel(exc=diag.discord.NotFound(_Resp()))  # type: ignore[arg-type]
    client = _Client(guild=_Guild(channel=channel))
    out = asyncio.run(diag.pins_report(client, _GUILD_ID))
    assert out == [("panel:mod:kingdom:admin:console", "message 777 supprimé — le prochain passage doit le recréer")]


def test_the_report_names_an_unreadable_message(monkeypatch) -> None:
    """Step 5b — an HTTP error reads as a permissions hint."""
    diag = _diag()
    _patch_registry(monkeypatch, [_spec("panel:mod:kingdom:admin:console")])
    channel = _Channel(exc=diag.discord.HTTPException(_Resp(status=403)))  # type: ignore[arg-type]
    client = _Client(guild=_Guild(channel=channel))
    out = asyncio.run(diag.pins_report(client, _GUILD_ID))
    assert out == [("panel:mod:kingdom:admin:console", "message 777 illisible (HTTP 403 — droits lecture du bot ?)")]


def test_the_report_distinguishes_pinned_from_unpinned(monkeypatch) -> None:
    """The two healthy endings: pinned, and present-but-unpinned."""
    diag = _diag()
    _patch_registry(
        monkeypatch,
        [
            _spec("panel:mod:kingdom:admin:console"),
            _spec("panel:mod:kingdom:apply", message_id="888"),
        ],
    )
    client = _Client(guild=_Guild(channel=_Channel(pinned=False)))
    out = dict(asyncio.run(diag.pins_report(client, _GUILD_ID)))
    assert out == {
        "panel:mod:kingdom:admin:console": f"épinglé dans <#{_CHANNEL_ID}>",
        "panel:mod:kingdom:apply": f"présent dans <#{_CHANNEL_ID}> mais NON épinglé (999)",
    }


def test_the_report_never_raises(monkeypatch) -> None:
    """A broken seam (resolve_channel raising) becomes an error line."""
    diag = _diag()

    async def boom(guild_id: str) -> str | None:
        raise TypeError("seam down")

    spec = SimpleNamespace(
        key="panel:mod:kingdom:admin:console",
        scope="mod/kingdom",
        resolve_channel=boom,
        resolve_message_id=noop_resolver(),
    )
    _patch_registry(monkeypatch, [spec])
    out = asyncio.run(diag.pins_report(_Client(guild=None), _GUILD_ID))
    assert out == [("panel:mod:kingdom:admin:console", "erreur : TypeError")]


def noop_resolver():
    async def resolve_message_id(guild_id: str) -> str | None:
        return None

    return resolve_message_id


def test_admin_pin_lines_format_the_followup(monkeypatch) -> None:
    """The admin followup: a bold title, one bullet per surface."""
    diag = _diag()
    _patch_registry(monkeypatch, [_spec("panel:mod:kingdom:admin:console", channel_id=None)])
    lines = asyncio.run(diag.admin_pin_lines(_Client(guild=None), _GUILD_ID))
    assert lines[0] == "**Panneaux du mod — diagnostic**"
    assert lines[1].startswith("• `panel:mod:kingdom:admin:console` — ")
    assert asyncio.run(diag.admin_pin_lines(_Client(guild=None), "")) == []
