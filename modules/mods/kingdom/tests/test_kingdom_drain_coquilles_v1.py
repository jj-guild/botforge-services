"""drain-coquilles-v1 (Drasah 22/11, Check 135) — the ":" id repair.

The Check 133 autopsy: shell ids carry a ``:`` (``realm:aegis-123``),
so the old templates either TRUNCATED the captured id (ValidationArchive:
clic mort) or did not match at all (KingdomRegieRealmButton: le bouton
ne répondait jamais). The repair rides ANCHORED templates — a real id
must fullmatch with its groups INTACT, a shell must show its purge
button in the régie drawer, and the gate must drop a DIRTY member
deny (the Blanc incident: a hand-made deny survived every pass).
"""

from __future__ import annotations

import re
from types import SimpleNamespace as NS

import pytest


def _ids(view: object) -> list[str]:
    return [
        str(item.custom_id)
        for item in view.walk_children()  # type: ignore[attr-defined]
        if getattr(item, "custom_id", None)
    ]


def _texts(view: object) -> list[str]:
    return [
        child.content
        for child in view.walk_children()  # type: ignore[attr-defined]
        if type(child).__name__ == "TextDisplay"
    ]


def test_regie_realm_button_matches_the_real_colon_ids() -> None:
    """The shell id ``realm:aegis-…`` must match, groups INTACT."""
    from botforge.mods.kingdom.cogs.settings_panel import KingdomRegieRealmButton

    pattern = re.compile(KingdomRegieRealmButton.__discord_ui_compiled_template__.pattern)

    cid = "kingdom:console-regie:purge-yes:realm:aegis-123456789:424857302984091536"
    m = pattern.fullmatch(cid)
    assert m is not None, "the colon id MUST fullmatch (the Check 133 corpse)"
    assert m.group("kind") == "purge-yes"
    assert m.group("realm_id") == "realm:aegis-123456789"
    assert m.group("guild_id") == "424857302984091536"

    # every leg of the kind-routing must survive the same colon id
    for kind in ("restore", "purge", "restore-yes", "restore-no", "purge-no"):
        m2 = pattern.fullmatch(f"kingdom:console-regie:{kind}:realm:huen-7:7")
        assert m2 is not None and m2.group("kind") == kind
        assert m2.group("realm_id") == "realm:huen-7"


def test_validation_archive_button_captures_the_whole_colon_id() -> None:
    """Before: kind matched but captured « realm » TRUNCATED — clic mort."""
    from botforge.mods.kingdom.cogs.validation import ValidationArchiveButton

    pattern = re.compile(ValidationArchiveButton.__discord_ui_compiled_template__.pattern)
    m = pattern.fullmatch("kingdom:valid:arch:realm:aegis-123456789")
    assert m is not None, "the archive button must match a real shell id"
    assert m.group("realm_id") == "realm:aegis-123456789"


def test_the_regie_drawer_shows_the_dormant_shells_and_their_purge() -> None:
    """A dormant shell (a stuck founder) gets its 🗑️ purge in the drawer."""
    from botforge.mods.kingdom.cogs.settings_panel import _regie_drawer, settings_strings

    shell = NS(id="realm:aegis-123", name="AEGIS")
    view = _regie_drawer(settings_strings("fr"), guild_id="7", dormant=[shell])
    ids = _ids(view)
    # the purge card rides the fixed template — restart-proof again
    assert "kingdom:console-regie:purge:realm:aegis-123:7" in ids
    # a dormant shell offers NO restore (only an ARCHIVED one does)
    assert "kingdom:console-regie:restore:realm:aegis-123:7" not in ids
    assert "AEGIS" in "\n".join(_texts(view)), "the shell's name is listed"

    # without dormants the drawer stays EXACTLY the console-v2 one
    plain = _regie_drawer(settings_strings("fr"))
    assert not [i for i in _ids(plain) if "realm:" in i]


# ---------------------------------------------------------------------------
# layoutview-v1 (Check 138) — the SILENT purge click
# ---------------------------------------------------------------------------


class _Resp:
    def __init__(self) -> None:
        self.done = False
        self.deferred = False

    def is_done(self) -> bool:
        return self.done

    async def defer(self, ephemeral: bool = False) -> None:
        self.done = True
        self.deferred = True


class _Follow:
    def __init__(self) -> None:
        self.sent: list[tuple[object, dict]] = []

    async def send(self, content: object = None, **kwargs: object):
        self.sent.append((content, kwargs))

        async def _delete() -> None:
            return None

        return NS(id=f"f{len(self.sent)}", delete=_delete)


@pytest.mark.asyncio
async def test_the_purge_click_opens_its_confirm_card(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Before the Check 138: the card's build crashed a SILENT death.

    The corpse: `discord.ui.LayoutView(discord.ui.Container(...))` —
    discord.py 2.7.1's LayoutView takes NO positional child, so the
    purge card (and the restore DM question) raised TypeError right
    after their fast-acks: the click was swallowed, nothing displayed
    (Drasah's report: only 🗑️ Supprimer was dead, the switches worked).
    """
    import discord

    from botforge.mods.kingdom.cogs import settings_panel as sp

    realm = NS(
        id="realm:aegis-123456789", name="AEGIS",
        engagement=None, join_request=None,
    )

    class _Realms:
        async def realm_by_id(self, realm_id: str) -> object:
            return realm if realm_id == realm.id else None

    monkeypatch.setattr(sp, "wiring", lambda: NS(realms=_Realms(), kingdoms=None))

    async def _guard(interaction: object) -> bool:
        return True

    monkeypatch.setattr(sp, "_panel_guard", _guard)

    resp = _Resp()
    inter = NS(
        locale="fr", guild_id="7", guild=None,
        user=NS(id="7", guild_permissions=None),
        client=NS(), response=resp, followup=_Follow(),
    )

    btn = sp.KingdomRegieRealmButton(
        "purge", realm.id, "7", "Supprimer", discord.ButtonStyle.danger
    )
    await btn.callback(inter)  # type: ignore[arg-type]
    assert resp.deferred, "fast-ack: the click never races the 3-second clock"
    sent = inter.followup.sent  # type: ignore[attr-defined]
    assert sent, "the confirm card ARRIVES (the corpse: total silence)"
    kwargs = sent[-1][1]
    assert kwargs.get("view") is not None, "the card rides a real view"
    ids = _ids(kwargs["view"])
    assert f"kingdom:console-regie:purge-yes:{realm.id}:7" in ids, (
        "the red confirm leg rides the anchored template"
    )


# ---------------------------------------------------------------------------
# purge-card-close-v1 (Check 139) — the card DIES with its own gesture
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_purge_yes_closes_the_confirm_card_into_its_note(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Drasah's live report: after the purge, the red card STAYED open —
    he could click Supprimer on an already-deleted realm again. The fix:
    ``_purge_yes`` routes the success (and failure) note through
    ``open_unique_ephemeral`` (the single-window seam), which closes the
    live confirm card instead of stacking a SECOND ephemeral view.
    """
    import discord

    from botforge.mods.kingdom.cogs import settings_panel as sp

    realm = NS(id="realm:aegis-123456789", name="AEGIS")
    destroyed: list[str] = []
    windows: list[dict] = []

    class _Realms:
        async def destroy_realm(self, realm_id: str) -> object:
            destroyed.append(realm_id)
            return realm

    async def _open_unique(interaction: object, content: str | None = None, **kw: object):
        windows.append({"content": content, **kw})

    async def _pins(interaction: object) -> None:
        return None

    async def _dismantle(client: object, gone: object) -> None:  # noqa: RUF029
        return None

    monkeypatch.setattr(sp, "open_unique_ephemeral", _open_unique)
    monkeypatch.setattr(sp, "refresh_live_pins_after", _pins)
    from botforge.mods.kingdom.cogs import realms as cogs_realms

    monkeypatch.setattr(sp, "wiring", lambda: NS(realms=_Realms(), kingdoms=None))
    monkeypatch.setattr(cogs_realms, "dismantle_realm_category", _dismantle)

    resp = _Resp()
    inter = NS(
        locale="fr", guild_id="7", guild=None,
        user=NS(id="7", guild_permissions=None),
        client=NS(), response=resp, followup=_Follow(),
    )

    btn = sp.KingdomRegieRealmButton(
        "purge-yes", realm.id, "7", "Supprimer", discord.ButtonStyle.danger
    )
    await btn.callback(inter)  # type: ignore[arg-type]
    assert resp.deferred, "fast-ack first: the 3-second clock is the defer's"
    assert destroyed == [realm.id], "the shell is really destroyed"
    assert len(windows) == 1, "ONE window call — the note replaces the card"
    assert "AEGIS" in str(windows[0]["content"]), "the note carries the realm name"
    assert inter.followup.sent == [], "no raw followup view: the card never reopens"


@pytest.mark.asyncio
async def test_the_purge_yes_without_service_still_answers_in_one_window(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The no-service leg ALSO dies into a note — never a silent corpse."""
    import discord

    from botforge.mods.kingdom.cogs import settings_panel as sp

    windows: list[dict] = []

    async def _open_unique(interaction: object, content: str | None = None, **kw: object):
        windows.append({"content": content, **kw})

    monkeypatch.setattr(sp, "open_unique_ephemeral", _open_unique)
    monkeypatch.setattr(sp, "wiring", lambda: NS(realms=None, kingdoms=None))

    inter = NS(
        locale="fr", guild_id="7", guild=None,
        user=NS(id="7", guild_permissions=None),
        client=NS(), response=_Resp(), followup=_Follow(),
    )
    btn = sp.KingdomRegieRealmButton(
        "purge-yes", "realm:x-1", "7", "Supprimer", discord.ButtonStyle.danger
    )
    await btn.callback(inter)  # type: ignore[arg-type]
    assert len(windows) == 1, "a note rides the single-window seam"
    assert inter.followup.sent == [], "nothing stacked on top of the dead card"
