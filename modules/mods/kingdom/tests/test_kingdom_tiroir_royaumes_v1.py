"""tiroir-royaumes-v1 (Drasah 23/11, Check 142) — the 40-cap regression.

The live incident: « 👥 Joueurs & royaumes » answered NOTHING. The cause
(proven by local reproduction): the régie drawer crossed Discord's HARD
limit of 40 components per message (``ValueError`` inside ``surface()``,
AFTER the fast-ack — hence the total silence, not the sas). Drasah cut
the drawer in two: RÉGIE = parcours lever + season switches, ROYAUMES =
compact paginated lines (4 per page, one shared page counter) + the
players' gestures. These tests pin the cap NEVER comes back.
"""

from __future__ import annotations

import re
from types import SimpleNamespace as NS

import discord


def _ids(view: object) -> list[str]:
    return [
        str(item.custom_id)
        for item in view.walk_children()  # type: ignore[attr-defined]
        if getattr(item, "custom_id", None)
    ]


def _children(view: object) -> int:
    return len(list(view.walk_children()))  # type: ignore[attr-defined]


def test_the_page_button_template_is_anchored_and_unique() -> None:
    """The ◀️/▶️ pagination rides its OWN template — no collision."""
    from botforge.mods.kingdom.cogs.settings_panel import (
        KingdomRegieParcoursButton,
        KingdomRegieResetPlayersButton,
        KingdomRoyaumesPageButton,
        KingdomSettingsNavButton,
    )

    page_pattern = re.compile(KingdomRoyaumesPageButton.__discord_ui_compiled_template__.pattern)
    m = page_pattern.fullmatch("kingdom:console-royaumes:page:3:123456789")
    assert m is not None and m.group("page") == "3" and m.group("guild_id") == "123456789"
    # the neighbour templates must NOT eat the pagination's ids
    for cls in (
        KingdomRegieParcoursButton,
        KingdomRegieResetPlayersButton,
        KingdomSettingsNavButton,
    ):
        other = re.compile(cls.__discord_ui_compiled_template__.pattern)  # type: ignore[attr-defined]
        assert other.fullmatch("kingdom:console-royaumes:page:3:123456789") is None


def test_the_royaumes_drawer_never_crosses_the_40_cap() -> None:
    """50 dormant shells + 12 archived: NO ValueError, page 0 under 40."""
    from botforge.mods.kingdom.cogs.settings_panel import (
        _royaumes_drawer,
        settings_strings,
    )

    strings = settings_strings("fr")
    dormant = [
        NS(id=f"realm:d{i:03d}", name=f"D{i:03d}", member_ids=[1, 2, 3], king_name=f"K{i}")
        for i in range(50)
    ]
    archived = [
        NS(id=f"realm:a{i:03d}", name=f"A{i:03d}", member_ids=[], king_name=f"AK{i}",
           archived_at=1)
        for i in range(12)
    ]
    view = _royaumes_drawer(strings, guild_id="7", dormant=dormant, archived=archived, page=0)
    assert _children(view) <= 40, "the 40-cap incident must NEVER come back"
    ids = _ids(view)
    # page 0 shows the FIRST page only — shell #50 must be absent
    assert f"kingdom:console-regie:purge:realm:d049:7" not in ids
    assert "kingdom:console-regie:purge:realm:d000:7" in ids
    # shared page counter: the LAST dormant page is served too
    # (50 dormantes / 3 par page = 17 pages, la #16 porte la #50)
    last = _royaumes_drawer(strings, guild_id="7", dormant=dormant, archived=archived, page=16)
    last_ids = _ids(last)
    assert "kingdom:console-regie:purge:realm:d049:7" in last_ids
    assert "kingdom:console-regie:purge:realm:d000:7" not in last_ids
    assert _children(last) <= 40

    # the pagination buttons ride the restart-proof template
    assert "kingdom:console-royaumes:page:1:7" in ids  # next from page 0
    assert "kingdom:console-royaumes:page:15:7" in last_ids  # prev from page 16


def test_the_slim_regie_stays_under_40_whatever_the_state() -> None:
    """The régie drawer is MINCE — the cap cannot bite it anymore."""
    from botforge.mods.kingdom.cogs.settings_panel import (
        _regie_drawer,
        settings_strings,
    )

    strings = settings_strings("fr")
    for kwargs in (
        {},
        {"season_live": False},
        {"season_running": True, "parcours_beta": True},
        {"season_live": False, "season_running": False, "parcours_beta": True},
    ):
        view = _regie_drawer(strings, **kwargs)  # type: ignore[arg-type]
        assert _children(view) <= 40, f"the regie drawer grew fat: {kwargs}"


def test_the_royaumes_line_shows_the_king_and_the_members() -> None:
    """The compact line: name, King, member count (the King counts)."""
    from botforge.mods.kingdom.cogs.settings_panel import (
        _royaume_line,
        _royaumes_drawer,
        settings_strings,
    )

    strings = settings_strings("fr")
    realm = NS(id="realm:aegis", name="AEGIS", member_ids=[11, 22], king_name="Blanc")
    line = _royaume_line(strings, realm)
    assert "AEGIS" in line and "Blanc" in line and "3" in line  # 2 lords + the King

    view = _royaumes_drawer(strings, guild_id="7", dormant=[realm], archived=[], page=0)
    texts = [
        str(child.content)
        for child in view.walk_children()  # type: ignore[attr-defined]
        if type(child).__name__ == "TextDisplay"
    ]
    assert any("AEGIS" in t for t in texts), "the compact line lists the realm"


def test_the_page_button_rebuilds_the_drawer() -> None:
    """The ◀️/▶️ rebuilds the ROYAUMES drawer page by page."""
    from botforge.mods.kingdom.cogs.settings_panel import KingdomRoyaumesPageButton

    button = KingdomRoyaumesPageButton(2, "7", "▶️", True)
    assert isinstance(button.item, discord.ui.Button)
    assert button.page == 2 and button.guild_id == "7"
    assert button.item.custom_id == "kingdom:console-royaumes:page:2:7"
    # a disabled edge button never leads anywhere odd
    first = KingdomRoyaumesPageButton(0, "7", "◀️", False)
    assert first.item.disabled is True
