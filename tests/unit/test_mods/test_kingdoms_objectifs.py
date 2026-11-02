"""Tests for the objectifs patch series (Drasah 02/11).

objectif-possede-v1: a goal set on something ALREADY held is
reformulated live (defend priority / marriage wish) and NEVER announces.

objectif-annonces-v1: a goal realized LATER is auto-erased, announced
in Discussions with the 🎯 Redéfinir shortcut, and the ONE pinned recap
follows every save (edited in place, unpinned when empty).

seigneurie-coexist-v1: the 🛡️ Seigneurie roster never closes the
ephemeral parent sheet it was opened from.
"""

from __future__ import annotations

from types import SimpleNamespace

from tests.mocks.discord_mock import (
    MockCategoryChannel,
    MockGuild,
    MockTextChannel,
)

from kingdoms.mods.kingdoms import kingdom_lieux as lieux
from kingdoms.mods.kingdoms.kingdom_persistent import _seigneurie_closes_previous


class FakeKingdomsService:
    """Records every save (the wiring fake of the kingdoms service)."""

    def __init__(self) -> None:
        self.saved: list[object] = []

    async def save_kingdom(self, kingdom: object) -> None:
        self.saved.append(kingdom)


class FakeTerritoriesService:
    """A static territory catalog (the wiring fake)."""

    def __init__(self, *territories: SimpleNamespace) -> None:
        self._territories = list(territories)

    async def territories(self) -> list[SimpleNamespace]:
        return list(self._territories)


def _territory(map_key: str, owner: str) -> SimpleNamespace:
    return SimpleNamespace(map_key=map_key, owner_kingdom_id=owner)


def _kingdom(
    *,
    objectives: dict[str, object] | None = None,
    civilizations: list[str] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id="k-nilrem",
        name="Nilrem",
        civilizations=list(civilizations or []),
        council_objectives=dict(objectives or {}),
    )


def _wiring(
    territories: list[SimpleNamespace] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        kingdoms_service=FakeKingdomsService(),
        territories_service=FakeTerritoriesService(*(territories or [])),
    )


# ---------------------------------------------------------------------------
# objectif-possede-v1 — the LIVE reformulation of an already-held target.
# ---------------------------------------------------------------------------


async def test_an_owned_map_reads_as_a_defend_priority() -> None:
    """His report: wanting a map the realm already owns is not a
    « sought » map — the sheet says défendre coûte que coûte."""
    kingdom = _kingdom(
        objectives={
            "target_territory": "aquitaine",
            "target_territory_label": "Aquitaine",
        }
    )
    wiring = _wiring([_territory("aquitaine", "k-nilrem")])
    lines = await lieux._objectifs_display_lines("fr", kingdom, wiring)
    assert len(lines) == 1
    assert "défendre coûte que coûte" in lines[0]
    assert "Aquitaine" in lines[0]


async def test_a_held_alliance_reads_as_a_marriage_wish() -> None:
    """An alliance already obtained by the realm becomes a marriage
    wish with the kingdom — never a « sought » alliance."""
    kingdom = _kingdom(
        objectives={
            "target_alliance": "bretons",
            "target_alliance_label": "Bretons",
        },
        civilizations=["bretons"],
    )
    lines = await lieux._objectifs_display_lines("fr", kingdom, None)
    assert len(lines) == 1
    assert "Mariage souhaité" in lines[0]
    assert "Bretons" in lines[0]


async def test_a_foreign_map_stays_a_sought_territory() -> None:
    """A map owned by ANOTHER kingdom keeps the classic wording — the
    reformulation only fires on the realm's OWN holdings."""
    kingdom = _kingdom(
        objectives={
            "target_territory": "aquitaine",
            "target_territory_label": "Aquitaine",
        }
    )
    wiring = _wiring([_territory("aquitaine", "k-astolfo")])
    lines = await lieux._objectifs_display_lines("fr", kingdom, wiring)
    assert len(lines) == 1
    assert "défendre" not in lines[0]


async def test_the_save_stamps_whether_the_target_was_already_owned() -> None:
    """The at-save flags distinguish « already possessed at definition »
    (reformulated, never announced) from « acquired later » (announced
    and erased)."""
    kingdom = _kingdom(civilizations=["bretons"])
    wiring = _wiring([_territory("aquitaine", "k-nilrem")])
    staged = {
        "target_territory": "aquitaine",
        "target_territory_label": "Aquitaine",
        "target_alliance": "bretons",
        "target_alliance_label": "Bretons",
    }
    assert await lieux._save_objectives(wiring, kingdom, staged) is True
    goals = kingdom.council_objectives
    assert goals["target_territory_at_save_owned"] is True
    assert goals["target_alliance_at_save_owned"] is True
    assert wiring.kingdoms_service.saved  # persisted
    # a map owned by nobody else at save time: the flag is False.
    kingdom2 = _kingdom()
    wiring2 = _wiring([_territory("aquitaine", "k-astolfo")])
    assert await lieux._save_objectives(
        wiring2, kingdom2, {"target_territory": "aquitaine"}
    ) is True
    assert kingdom2.council_objectives["target_territory_at_save_owned"] is False


# ---------------------------------------------------------------------------
# objectif-annonces-v1 — achieved goals: announce + auto-erase.
# ---------------------------------------------------------------------------


async def test_objectifs_achieved_fires_only_on_goals_acquired_later() -> None:
    """A goal the kingdom did NOT hold at save time and holds NOW
    fires; one stamped already-owned at save time never does (it stays
    a reformulated line, not an achievement)."""
    kingdom = _kingdom(
        objectives={
            "target_territory": "aquitaine",
            "target_territory_label": "Aquitaine",
            "target_territory_at_save_owned": False,
            "target_alliance": "bretons",
            "target_alliance_label": "Bretons",
            "target_alliance_at_save_owned": True,
        },
        civilizations=["bretons"],
    )
    wiring = _wiring([_territory("aquitaine", "k-nilrem")])
    achieved = await lieux.objectifs_achieved(kingdom, wiring)
    # the map was conquered since: fires. The alliance was already
    # held at save: reformulated, never announced.
    assert achieved == [("target_territory", "Aquitaine")]


async def test_erase_objectifs_kinds_clears_and_persists() -> None:
    """The achieved goal is auto-erased (kind + label + at-save flag)
    and the kingdom doc is persisted."""
    kingdom = _kingdom(
        objectives={
            "target_territory": "aquitaine",
            "target_territory_label": "Aquitaine",
            "target_territory_at_save_owned": False,
            "target_alliance": "bretons",
            "target_alliance_label": "Bretons",
        }
    )
    wiring = _wiring([])
    assert await lieux.erase_objectifs_kinds(
        wiring, kingdom, ["target_territory"]
    ) is True
    goals = kingdom.council_objectives
    assert goals["target_territory"] == ""
    assert goals["target_territory_label"] == ""
    assert "target_territory_at_save_owned" not in goals
    assert goals["target_alliance_label"] == "Bretons"  # untouched
    assert wiring.kingdoms_service.saved


# ---------------------------------------------------------------------------
# The Discussions hub: the ONE pinned recap + the achievement announce.
# ---------------------------------------------------------------------------


def _discussions_guild() -> tuple[MockGuild, MockTextChannel]:
    """A guild carrying the Nilrem realm category and its Discussions."""
    guild = MockGuild(name="Test Guild")
    category = MockCategoryChannel(name="🏰 Nilrem", guild=guild)
    guild._channels[category.id] = category
    channel = MockTextChannel(name="💬 discussions", guild=guild, category=category)
    guild._channels[channel.id] = channel
    category.add_channel(channel)
    return guild, channel


async def test_the_pin_is_one_message_edited_in_place() -> None:
    """His spec: a recap pinned in Discussions per kingdom, redefining
    the objective REPLACES the previous pin (never stacks)."""
    guild, channel = _discussions_guild()
    kingdom = _kingdom(
        objectives={
            "target_territory": "aquitaine",
            "target_territory_label": "Aquitaine",
        }
    )
    wiring = _wiring()
    assert await lieux.refresh_objectifs_pin_safe(guild, wiring, kingdom, "fr") is True
    assert len(channel.messages) == 1
    pin = channel.messages[0]
    assert pin.pinned is True
    assert lieux._OBJECTIFS_PIN_MARKER in pin.content
    assert "Aquitaine" in pin.content
    assert kingdom.council_objectives["pin_message_id"] == pin.id
    # a redefinition: SAME message edited, never a second pin.
    kingdom.council_objectives["target_territory_label"] = "Provence"
    assert await lieux.refresh_objectifs_pin_safe(guild, wiring, kingdom, "fr") is True
    assert len(channel.messages) == 1
    assert channel.messages[0] is pin
    assert pin.edited is True
    assert "Provence" in pin.content


async def test_an_empty_goals_sheet_unpins_the_recap() -> None:
    """No goal left: the pinned recap is unpinned (never deleted)."""
    guild, channel = _discussions_guild()
    kingdom = _kingdom(
        objectives={
            "target_territory": "aquitaine",
            "target_territory_label": "Aquitaine",
        }
    )
    wiring = _wiring()
    await lieux.refresh_objectifs_pin_safe(guild, wiring, kingdom, "fr")
    pin = channel.messages[0]
    assert pin.pinned is True
    kingdom.council_objectives["target_territory"] = ""
    kingdom.council_objectives["target_territory_label"] = ""
    assert await lieux.refresh_objectifs_pin_safe(guild, wiring, kingdom, "fr") is True
    assert len(channel.messages) == 1
    assert pin.pinned is False
    assert "Aucun objectif" in pin.content


async def test_the_achievement_announce_carries_the_redefine_button() -> None:
    """His spec: the announce in Discussions offers the 🎯 shortcut to
    redefine the objective directly."""
    guild, channel = _discussions_guild()
    kingdom = _kingdom()
    wiring = _wiring()
    await lieux.announce_objectif_achieved_safe(
        guild,
        wiring,
        kingdom,
        [("target_territory", "Aquitaine")],
        "fr",
    )
    assert len(channel.messages) == 1
    announce = channel.messages[0]
    assert "Objectif atteint" in announce.content
    assert "Aquitaine" in announce.content
    button = announce.view.children[0]
    assert button.custom_id == "kingdoms:lieux:objectif"
    assert button.label == "🎯 Redéfinir un objectif"


# ---------------------------------------------------------------------------
# seigneurie-coexist-v1 — the roster never closes its ephemeral parent.
# ---------------------------------------------------------------------------


def test_seigneurie_keeps_the_parent_sheet_alive() -> None:
    """His report (retour 1): clicking Seigneurie must NOT close the
    window the player was reading (the ephemeral parent sheet)."""
    sheet = (object(), object())  # a 2-tuple sheet (Salle du conseil)
    # parent ephemeral: the sheet survives, a child window still closes.
    assert _seigneurie_closes_previous(None, True) is False
    assert _seigneurie_closes_previous(sheet, True) is False
    assert _seigneurie_closes_previous((*sheet, object()), True) is True
    # a NON-ephemeral parent keeps the legacy single-window rule.
    assert _seigneurie_closes_previous(sheet, False) is True
