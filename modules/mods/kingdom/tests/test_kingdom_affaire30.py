"""affaire-30 (Drasah 25/11) — a draft forfeit reaches Géopolitique.

Un forfait de draft n'était annoncé que dans le salon d'attaque, que
la fermeture immédiate supprime une seconde plus tard. Géopolitique
doit rester LA surface de vérité des résolutions : une ligne plate
par forfait, avec le camp forfait et le vainqueur par forfait. Le
« double forfait » est un forfait général : l'attaquant présent
l'emporte (la règle existante) — la ligne Géo porte son royaume.
Périmètre tranché : PAS les no-shows, PAS les annulations.
"""


from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest


class _Channel:
    def __init__(self, name: str) -> None:
        self.name = name
        self.sent: list[str] = []

    async def send(self, content: str) -> None:
        self.sent.append(content)


class _Guild:
    def __init__(self, *names: str) -> None:
        self.text_channels = [_Channel(name) for name in names]


def _bot(*names: str) -> Any:
    return SimpleNamespace(guilds=[_Guild(*names)])


async def _kingdoms_name(_stack: Any, kingdom_id: Any) -> str:
    return str(kingdom_id or "")


@pytest.mark.asyncio
async def test_a_side_forfeit_posts_its_geo_line() -> None:
    """One camp missed the draft: Géo learns WHO forfeited and the winner."""

    from botforge.mods.kingdom.cogs import battle
    from botforge.mods.kingdom.cogs.common import strings_by_locale

    bot = _bot("general", "geopolitique")
    attack = SimpleNamespace(id="a1", map_key="pataugeoire")
    strings = strings_by_locale("fr")
    await battle.announce_forfeit_safe(bot, None, attack, "defender", "Camelot", strings)
    geo = bot.guilds[0].text_channels[1]
    assert geo.sent == ["🏳️ **pataugeoire** : forfait de le défenseur — victoire de **Camelot** par forfait."]


@pytest.mark.asyncio
async def test_the_general_forfeit_posts_the_attacker_takeover() -> None:
    """The « double forfait » is a GENERAL forfeit: the present attacker
    wins — the Géo line carries the winner like the salon note does."""

    from botforge.mods.kingdom.cogs import battle
    from botforge.mods.kingdom.cogs.common import strings_by_locale

    bot = _bot("geopolitique")
    attack = SimpleNamespace(id="a1", map_key="pataugeoire")
    strings = strings_by_locale("fr")
    await battle.announce_forfeit_safe(bot, None, attack, "both", "Kaamelott", strings)
    geo = bot.guilds[0].text_channels[0]
    assert geo.sent == [
        "🏳️ **pataugeoire** : forfait général — aucun camp n'a validé, **Kaamelott** l'emporte par forfait."
    ]


@pytest.mark.asyncio
async def test_a_missing_geo_salon_never_crashes_the_forfeit() -> None:
    """No Géopolitique salon: the resolution proceeds, nothing raises."""

    from botforge.mods.kingdom.cogs import battle
    from botforge.mods.kingdom.cogs.common import strings_by_locale

    bot = _bot("general", "taverne")
    attack = SimpleNamespace(id="a1", map_key="pataugeoire")
    strings = strings_by_locale("fr")
    await battle.announce_forfeit_safe(bot, None, attack, "attacker", "Camelot", strings)
    assert bot.guilds[0].text_channels[0].sent == []


@pytest.mark.asyncio
async def test_the_forfeit_line_is_spoken_in_both_locales() -> None:
    """The two templates exist and format in fr and en."""

    from botforge.mods.kingdom.cogs import battle
    from botforge.mods.kingdom.cogs.common import strings_by_locale

    for locale, who, both in (
        ("fr", "le défenseur", "aucun camp n'a validé"),
        ("en", "the defender", "nobody validated"),
    ):
        strings = strings_by_locale(locale)
        assert who in strings["forfeit_geo_side"].format(map="m", side=who, winner="W")
        assert both in strings["forfeit_geo_both"].format(map="m", winner="W")


@pytest.mark.asyncio
async def test_the_forfeit_resolution_announces_to_geo_before_closing(
    monkeypatch: Any,
) -> None:
    """_run_forfeits_safe calls announce_forfeit_safe BEFORE the closure."""

    closures: list[str] = []
    from botforge.mods.kingdom.cogs import battle, common, phases

    calls: list[tuple[str, str]] = []

    async def _announce(bot: Any, stack: Any, attack: Any, side: str, winner: str, strings: Any) -> None:
        calls.append((attack.map_key, side))

    attack = SimpleNamespace(
        id="a1",
        map_key="pataugeoire",
        ai_defender=False,
        is_over=True,
        winner_kingdom_id="camelot",
        pickban={"forfeit_side": "defender"},
    )

    class _Attacks:
        async def expire_stale(self) -> list[Any]:
            return [attack]

    async def _salon(guild: Any, atk: Any, content: str) -> None:
        return None

    async def _name(_kingdoms: Any, kingdom_id: Any) -> str:
        return "Camelot"

    async def _cleanup(bot: Any, stack: Any, atk: Any) -> int:
        closures.append(str(atk.id))
        return 0

    # The function imports its helpers AT CALL TIME (from .battle /
    # .common) — the patches ride those modules, not the phases one.
    monkeypatch.setattr(battle, "announce_forfeit_safe", _announce)
    monkeypatch.setattr(battle, "cleanup_decided_attack_safe", _cleanup)
    monkeypatch.setattr(common, "attack_salon_send_safe", _salon)
    monkeypatch.setattr(common, "kingdom_name", _name)
    strings = {
        "forfeit_side": "salon:",
        "side_defender": "le défenseur",
        "forfeit_both": "salon:",
    }
    stack = SimpleNamespace(attacks=_Attacks(), kingdoms=None)
    bot = SimpleNamespace(guilds=[])
    played = await phases._run_forfeits_safe(bot, stack, None, strings)
    assert played == 1
    assert calls == [("pataugeoire", "defender")], "the forfeit reaches Géo before the closure"
    assert closures == ["a1"], "the immediate closure still runs AFTER the announce"
