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
