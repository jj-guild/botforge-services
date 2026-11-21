"""hub-rebuild strings (Drasah 21/11) — a click rebuilds the component BEFORE
the callback ever runs.

The incident: a player clicked the hub pin « 🏰 Le Royaume » and every
button answered « le bot n'a pas répondu à temps ». Discord rebuilds a
dynamic item through ``from_custom_id`` and the REALM items read their
labels in the ATTACK catalog (``strings_for`` → kingdom.attack), where
no realm key exists → KeyError before any defer → the click is never
acknowledged → Discord's timeout. The fix: ``from_custom_id`` reads the
REALM catalog (``realm_strings``), the same one the callbacks use.

These tests rebuild EVERY hub item the same way Discord does — any
KeyError here is the bug that produced the timeouts, so every dispatch
must resolve a label in both locales.
"""

from __future__ import annotations

from typing import Any

import pytest


def _interaction(locale: str) -> Any:
    interaction = type("I", (), {})()
    interaction.locale = locale
    interaction.user = type("U", (), {})()
    interaction.user.id = "1"
    return interaction


def _run(coro: Any) -> Any:
    import asyncio

    return asyncio.run(coro)


@pytest.mark.parametrize("locale", ["fr", "en"])
def test_every_hub_item_rebuilds_without_keyerror(locale: str) -> None:
    """Dispatch each hub item exactly as discord.py does on a click.

    The assertion is double: ``from_custom_id`` must not raise (the
    incident was a KeyError) and must carry the realm label (an empty
    label would be the same click swallowed silently).
    """
    from botforge.mods.kingdom.cogs.realms import (
        RealmCrownSelect,
        RealmHomeButton,
        RealmJoinButton,
        RealmNavButton,
        RealmPresentationEditButton,
        RealmQuitButton,
    )
    from botforge.mods.kingdom.cogs.realm_strings import realm_strings

    inter = _interaction(locale)
    strings = realm_strings(locale)

    def label(item: Any) -> str:
        return item.label

    cases: list[tuple[str, Any, dict[str, str], str]] = [
        ("Entrée", RealmHomeButton, {"slug": "aegis"}, strings["realm_enter_button"]),
        ("Nav seigneurie", RealmNavButton, {"view": "seigneurie", "slug": "aegis"}, strings["seigneurie_button"]),
        ("Nav présentation", RealmNavButton, {"view": "presentation", "slug": "aegis"}, strings["presentation_button"]),
        ("Nav saison", RealmNavButton, {"view": "season", "slug": "aegis"}, strings["season_button"]),
        ("Nav palmarès", RealmNavButton, {"view": "palmares", "slug": "aegis"}, strings["palmares_button"]),
        ("Modifier la présentation", RealmPresentationEditButton, {"slug": "aegis"}, strings["presentation_edit_button"]),
        ("S'inscrire à la saison", RealmJoinButton, {"slug": "aegis"}, strings["season_join_button"]),
        ("Quitter le royaume", RealmQuitButton, {"slug": "aegis"}, strings["quit_button"]),
    ]

    for name, cls_, match, expected in cases:
        item = _run(cls_.from_custom_id(inter, None, dict(match))).item
        got = label(item)
        assert got == expected, f"{name} ({locale}): label {got!r} != realm catalog"

    crown = _run(RealmCrownSelect.from_custom_id(inter, None, {"slug": "aegis"})).item
    assert crown.placeholder == strings["seigneurie_crown_placeholder"]
