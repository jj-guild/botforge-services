"""eject-sas-v1 + fin-saison-v1 (Drasah 21/11).

Le sas est un sas : une ACCEPTATION se corrige dans SA fenêtre (la
préparation) — « 🗑️ Éjecter » défait le geste d'entrée (le royaume
moteur part avec ses seigneurs et son draft, la coquille retombe
dormante, l'habitat se rendort) et le Roi reçoit le motif par MP. La
saison lancée, plus RIEN : la section devient lecture et le moteur
refuse l'id périmé. « 🏁 Terminer la saison » ferme la boucle de test :
archivage + essuyage moteur, chaque royaume engagé repart en sommeil.
"""

from __future__ import annotations

import unittest.mock as mock
from types import SimpleNamespace as NS
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# The fakes (Check-107 lesson: locale + delete_original_response + message.delete)
# ---------------------------------------------------------------------------


class _Resp:
    def __init__(self) -> None:
        self.done = False

    def is_done(self) -> bool:
        return self.done

    async def defer(self, ephemeral: bool = False) -> None:
        self.done = True

    async def send_message(self, content: Any = None, **kwargs: Any) -> None:
        self.done = True


class _Follow:
    def __init__(self) -> None:
        self.sent: list[Any] = []

    async def send(self, content: Any = None, **kwargs: Any) -> Any:
        self.sent.append((content, kwargs))
        return NS(id="f1")


def _interaction(user: str = "7", guild: Any = None) -> Any:
    resp = _Resp()
    follow = _Follow()
    message = NS(id="m1", deleted=False)

    async def _delete() -> None:
        message.deleted = True

    message.delete = _delete
    outer = NS(
        user=NS(id=user, guild_permissions=None),
        locale="fr",
        guild_id="42",
        guild=guild,
        client=NS(
            status_service=NS(bot_admins=(user,)),
            roles_service=None,
            state_service=None,
        ),
        response=resp,
        followup=follow,
        message=message,
        deleted_original=False,
    )

    async def _delete_original() -> None:
        outer.deleted_original = True

    outer.delete_original_response = _delete_original
    return outer


def _realm(slug: str = "blanc", engaged: bool = True) -> Any:
    return NS(
        id=f"r-{slug}",
        slug=slug,
        name=f"Royaume {slug}",
        king_id="77",
        member_ids=["88"],
        engagement=({"season_id": "s1", "kingdom_id": "k1"} if engaged else None),
        join_request=None,
        presentation="",
    )


class _Kingdoms:
    """The engine seam fake — every op RECORDS itself (contract order)."""

    def __init__(self, phase: str) -> None:
        self.phase = phase
        self.deleted: list[str] = []
        self.released: list[str] = []
        self.reset_done = False

    async def current_season(self) -> Any:
        return NS(phase=self.phase, imposed_kingdoms=False) if self.phase else None

    async def kingdoms(self) -> list[Any]:
        return []

    async def delete_kingdom(self, kingdom_id: str) -> Any:
        self.deleted.append(str(kingdom_id))
        return NS(id=kingdom_id, name=f"engine {kingdom_id}")

    async def reset(self) -> None:
        self.reset_done = True


class _Realms:
    def __init__(self) -> None:
        self.released: list[str] = []
        self.habitats: list[str] = []
        self._realms: list[Any] = []

    def adopt(self, realm: Any) -> None:
        self._realms.append(realm)

    async def realms(self) -> list[Any]:
        return list(self._realms)

    async def realm_of_slug(self, slug: str) -> Any:
        return next((r for r in self._realms if r.slug == slug), None)

    async def release_engagement(self, realm_id: str) -> Any:
        realm = next(r for r in self._realms if r.id == realm_id)
        realm.engagement = None
        realm.join_request = None
        self.released.append(str(realm_id))
        return realm

    async def save_habitat(self, realm_id: str, ids: dict[str, Any]) -> Any:
        self.habitats.append(str(realm_id))
        return next((r for r in self._realms if r.id == realm_id), None)


def _stack(phase: str, realms: _Realms | None = None) -> Any:
    return NS(kingdoms=_Kingdoms(phase), realms=realms or _Realms())


def _texts(view: Any) -> str:
    return "\n".join(str(c.content) for c in view.walk_children() if hasattr(c, "content"))


def _ids(view: Any) -> list[str]:
    return [
        str(item.custom_id)
        for item in view.walk_children()
        if getattr(item, "custom_id", None)
    ]


def _both_dashboards(locale: str) -> None:
    from botforge.mods.kingdom.cogs.common import mod_catalog

    keys = (
        "realm_eject_button",
        "eject_window_title",
        "eject_window_hint",
        "eject_reason_players",
        "eject_reason_rules",
        "eject_reason_other",
        "eject_other_modal_title",
        "eject_closed_note",
        "eject_done",
        "eject_dm",
    )
    s = mod_catalog().section("kingdom.validation", locale)
    for k in keys:
        assert s.get(k), (locale, k)


# ---------------------------------------------------------------------------
# eject-sas-v1
# ---------------------------------------------------------------------------


def test_the_eject_button_is_a_restart_proof_dynamic_item() -> None:
    """The eject rides a stable custom id, registry-ready."""
    from botforge.mods.kingdom.cogs.validation import ValidationEjectButton

    assert ValidationEjectButton("blanc", "🗑️ Éjecter").custom_id == "kingdom:valid:eject:blanc"
    _both_dashboards("fr")
    _both_dashboards("en")


def test_the_eject_window_offers_the_reasons_and_the_free_field() -> None:
    """The motif window: two presets + ✏️ Autre, one declared surface."""
    from botforge.mods.kingdom.cogs.common import mod_catalog
    from botforge.mods.kingdom.cogs.validation import _eject_window

    strings = dict(mod_catalog().section("kingdom.validation", "fr"))
    view = _eject_window(strings, "fr", _realm())
    ids = _ids(view)
    assert "kingdom:valid:eject-go:blanc:players" in ids
    assert "kingdom:valid:eject-go:blanc:rules" in ids
    assert "kingdom:valid:eject-other:blanc" in ids
    assert "Royaume blanc" in _texts(view)
    # the window NEVER opens an ejection by itself: no eject-yes shortcut
    assert not [i for i in ids if i.startswith("kingdom:valid:eject:")]
    assert not [i for i in ids if "confirm" in i]


@pytest.mark.asyncio
async def test_the_eject_undoes_the_acceptation_and_dms_the_king() -> None:
    """The full undo: engine kingdom deleted, shell released, king DM'd."""
    from botforge.mods.kingdom.cogs import common, validation

    realms = _Realms()
    realms.adopt(_realm())
    stack = _stack("setup", realms)
    interaction = _interaction(guild=None)
    strings = dict(common.mod_catalog().section("kingdom.validation", "fr"))
    dms: list[tuple[str, str]] = []

    async def _dm(bot: Any, user_id: str, content: str, view: Any = None) -> Any:
        dms.append((user_id, content))

    with mock.patch.object(validation, "wiring", lambda: stack), \
            mock.patch.object(common, "wiring", lambda: stack), \
            mock.patch.object(common, "dm_user_safe", _dm), \
            mock.patch.object(validation, "_refresh_pins", mock.AsyncMock()), \
            mock.patch.object(validation, "mod_catalog", common.mod_catalog), \
            mock.patch.object(validation, "_guild_locale", mock.AsyncMock(return_value="fr")):
        note = await validation._eject_season_entry(
            interaction, (await realms.realms())[0],
            "Nombre de joueurs insuffisant", strings, "fr",
        )
    # the engine kingdom is deleted (the undo of add_kingdom)
    assert stack.kingdoms.deleted == ["k1"]
    # the shell is released — the realm can re-request the entry
    assert realms.released == ["r-blanc"]
    assert "blanc" in note
    # the King learns WHY, by DM
    assert dms and dms[0][0] == "77"
    assert "Nombre de joueurs insuffisant" in dms[0][1]


@pytest.mark.asyncio
async def test_the_eject_is_a_sas_window_gesture_only() -> None:
    """Season launched or gone: the sas is CLOSED, the engine refuses."""
    from botforge.mods.kingdom.cogs import common, validation

    strings = dict(common.mod_catalog().section("kingdom.validation", "fr"))
    for phase in ("started", ""):
        realms = _Realms()
        realms.adopt(_realm())
        stack = _stack(phase, realms)
        interaction = _interaction()
        with mock.patch.object(validation, "wiring", lambda: stack), \
                mock.patch.object(common, "wiring", lambda: stack):
            note = await validation._eject_season_entry(
                interaction, (await realms.realms())[0], "motif", strings, "fr"
            )
        assert "saison est lancée" in str(note)
        # NOTHING moved: no engine delete, no shell release
        assert stack.kingdoms.deleted == []
        assert realms.released == []


@pytest.mark.asyncio
async def test_the_eject_button_refuses_a_gone_realm_quietly() -> None:
    """A clicked id pointing at a vanished realm degrades to the note."""
    from botforge.mods.kingdom.cogs import common, validation

    stack = _stack("setup", _Realms())  # no realm adopted
    interaction = _interaction()
    opened: list[Any] = []
    with mock.patch.object(validation, "wiring", lambda: stack), \
            mock.patch.object(common, "wiring", lambda: stack), \
            mock.patch.object(validation, "_guild_locale", mock.AsyncMock(return_value="fr")), \
            mock.patch.object(validation, "mod_catalog", common.mod_catalog), \
            mock.patch.object(
                validation, "open_unique_ephemeral",
                mock.AsyncMock(side_effect=lambda _i, content=None, **kw: opened.append(content or kw)),
            ):
        button = validation.ValidationEjectButton("blanc", "🗑️ Éjecter")
        await button.callback(interaction)
    assert opened and "n'existe plus" in str(opened[0])


# ---------------------------------------------------------------------------
# fin-saison-v1
# ---------------------------------------------------------------------------


def test_the_end_season_confirm_card_is_the_cycle_card() -> None:
    """« Terminer la saison » asks its confirmation like every cycle op."""
    from botforge.mods.kingdom.cogs.settings_panel import _cycle_confirm_card, settings_strings

    view = _cycle_confirm_card(settings_strings("fr"), "end-season")
    ids = _ids(view)
    assert "kingdom:cycle-confirm:end-season:yes" in ids
    assert "kingdom:cycle-confirm:end-season:no" in ids
    assert "Terminer la saison" in _texts(view)


def test_the_running_cockpit_offers_the_end_of_season() -> None:
    """The running cycle row carries « 🏁 Terminer la saison » (danger)."""
    from botforge.mods.kingdom.cogs.settings_panel import SettingsActionButton

    button = SettingsActionButton(
        "end-season", "🏁 Terminer la saison", __import__("discord").ButtonStyle.danger
    )
    assert button.custom_id == "kingdom:settings:end-season"


@pytest.mark.asyncio
async def test_the_end_season_rewinds_everything_and_archives() -> None:
    """The loop closes: habitats sleep, shells release, the engine wipes."""
    from botforge.mods.kingdom.cogs import common, settings_panel as sp

    realms = _Realms()
    realms.adopt(_realm("blanc"))
    realms.adopt(_realm("noir"))
    stack = _stack("started", realms)
    interaction = _interaction(guild=NS(spec_set=["channels"]))  # habitat best-effort
    slept: list[str] = []

    async def _sleep(guild: Any, realm: Any, **kw: Any) -> dict[str, Any]:
        slept.append(str(realm.id))
        return {}

    with mock.patch.object(sp, "wiring", lambda: stack), \
            mock.patch.object(common, "wiring", lambda: stack), \
            mock.patch.object(sp, "_needs_stack", lambda s: (stack, None)), \
            mock.patch.object(sp, "refresh_live_pins_after", mock.AsyncMock()), \
            mock.patch("botforge.mods.kingdom.cogs.realms.ensure_realm_structure", _sleep), \
            mock.patch("botforge.mods.kingdom.cogs.realms.deploy_realm_hub", mock.AsyncMock(return_value=None)):
        await sp._end_season(interaction, sp.settings_strings("fr"))
    # the engine archived + wiped LAST, after the realms left the season
    assert stack.kingdoms.reset_done is True
    assert set(realms.released) == {"r-blanc", "r-noir"}
    assert set(slept) == {"r-blanc", "r-noir"}
    note = interaction.followup.sent[-1][0]
    assert "{released}" not in str(note)


@pytest.mark.asyncio
async def test_the_end_season_never_fires_on_a_sleeping_zone() -> None:
    """No launched season: the gesture refuses, nothing is touched."""
    from botforge.mods.kingdom.cogs import common, settings_panel as sp

    for phase in ("setup", ""):
        stack = _stack(phase)
        interaction = _interaction()
        with mock.patch.object(sp, "wiring", lambda: stack), \
                mock.patch.object(common, "wiring", lambda: stack), \
                mock.patch.object(sp, "_needs_stack", lambda s: (stack, None)), \
                mock.patch.object(sp, "refresh_live_pins_after", mock.AsyncMock()):
            await sp._end_season(interaction, sp.settings_strings("fr"))
        assert stack.kingdoms.reset_done is False
        assert any("LANÇÉE" in str(c) for c, _ in interaction.followup.sent)
