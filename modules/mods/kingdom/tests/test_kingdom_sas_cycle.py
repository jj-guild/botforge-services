"""sas-cycle-v1 (Drasah 21/11) — le cycle de vie du SAS.

« Le SAS est la VOLONTÉ de l'admin : ouvert manuellement, c'est la
préparation de saison ; fermé automatiquement par 🏁 Terminer la
saison (le SEUL geste automatique du cycle) ; rouvert uniquement à la
main. » Et fermer le SAS VIDE la salle d'attente : chaque candidat est
retiré et son Roi reçoit le MP de prévention (best-effort total, pas
de motif — la fermeture est l'information). Le SAS ouvert devient en
outre un PRÉREQUIS de « ▶️ Lancer la saison ».
"""

from __future__ import annotations

import unittest.mock as mock
from types import SimpleNamespace as NS
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# The fakes (Check-107 lesson: locale + status_service + bot_admins)
# ---------------------------------------------------------------------------


class _Resp:
    def __init__(self) -> None:
        self.done = False
        self.modal: Any = None

    def is_done(self) -> bool:
        return self.done

    async def defer(self, ephemeral: bool = False) -> None:
        self.done = True

    async def send_message(self, content: Any = None, **kwargs: Any) -> None:
        self.done = True

    async def send_modal(self, modal: Any) -> None:
        self.done = True
        self.modal = modal


class _Follow:
    def __init__(self) -> None:
        self.sent: list[Any] = []

    async def send(self, content: Any = None, **kwargs: Any) -> Any:
        self.sent.append((content, kwargs))
        return NS(id="f1")


@pytest.fixture(autouse=True)
def _clean_live_window() -> Any:
    from botforge.discord.ui import ephemeral_windows as ew

    ew._live.clear()
    yield
    ew._live.clear()


def _interaction(user: str = "7") -> Any:
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
        guild=None,
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


class _RealmsService:
    """The realm seam fake — realms() + clear_join_request RECORDS."""

    def __init__(self, realms: list[Any]) -> None:
        self._realms = realms
        self.cleared: list[str] = []

    async def realms(self) -> list[Any]:
        return self._realms

    async def clear_join_request(self, realm_id: str) -> Any:
        self.cleared.append(str(realm_id))
        for realm in self._realms:
            if str(realm.id) == str(realm_id):
                return realm
        return None


def _realm(slug: str, *, pending: bool = False, engaged: bool = False) -> Any:
    return NS(
        id=f"r-{slug}",
        slug=slug,
        name=f"Royaume {slug}",
        king_id="77",
        king_name="R",
        member_ids=["88"],
        presentation="",
        join_request={"season_id": "s1", "requested_at": 0} if pending else None,
        engagement={"season_id": "s1", "kingdom_id": "k1"} if engaged else None,
    )


def _ids(view: Any) -> list[str]:
    return [
        str(item.custom_id) for item in view.walk_children() if getattr(item, "custom_id", None)
    ]


# ---------------------------------------------------------------------------
# The launch prerequisite — fermé ⇒ le geste refuse poliment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_launch_refuses_a_closed_sas() -> None:
    """sas-cycle-v1 : SAS fermé ⇒ pas de fourche, la note dit d'ouvrir."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    interaction = _interaction()
    strings = sp.settings_strings("fr")
    with mock.patch("botforge.mods.kingdom.cogs.regie.regie_open", new=mock.AsyncMock(return_value=False)) as reg, \
            mock.patch.object(sp, "open_unique_ephemeral", new=mock.AsyncMock()) as open_win:
        await sp._open_launch(interaction, strings)

    reg.assert_awaited_once()
    open_win.assert_awaited_once()
    kwargs = open_win.await_args.kwargs
    assert kwargs.get("content") == strings["settings_launch_sas_closed"], "the refusal note"
    assert "view" not in kwargs, "no fork card on a closed airlock"


@pytest.mark.asyncio
async def test_the_launch_asks_nothing_when_the_sas_is_open() -> None:
    """lancer-unique-v1 : SAS ouvert ⇒ la saison se prépare TOUT DE SUITE —
    plus de modal, plus de noms imposés, plus de question du sas (le
    levier de la régie possède le sas, « Ajouter un royaume » les injections)."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    interaction = _interaction()
    strings = sp.settings_strings("fr")
    launched: list[object] = []

    class _Kingdoms:
        async def launch(self, imposed: object) -> None:
            launched.append(imposed)

    stack = NS(kingdoms=_Kingdoms())
    tail: list[str] = []
    async def _tail(i: Any, sas_answer: str) -> None:
        tail.append(sas_answer)

    with mock.patch(
        "botforge.mods.kingdom.cogs.regie.regie_open", new=mock.AsyncMock(return_value=True)
    ), mock.patch.object(sp, "_needs_stack", new=lambda s: (stack, None)), \
            mock.patch.object(sp, "_lower_beta_flag", new=mock.AsyncMock(return_value=False)), \
            mock.patch.object(sp, "_finish_launch", new=mock.AsyncMock(side_effect=_tail)), \
            mock.patch.object(sp, "open_unique_ephemeral", new=mock.AsyncMock()) as open_win:
        await sp._open_launch(interaction, strings)

    open_win.assert_not_awaited(), "no question window anymore — the launch asks NOTHING"
    assert interaction.response.modal is None, "the prepare modal is GONE"
    assert launched == [None], "the season prepares, with NO imposed names"
    assert tail == ["open"], "the sas stays open (the régie lever owns it)"
    note = interaction.followup.sent[-1][0]
    assert note == strings["settings_launch_done"]


# ---------------------------------------------------------------------------
# Le vidage — fermer le SAS vide la salle d'attente, les Rois apprennent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_manual_close_drains_the_waiting_room() -> None:
    """Le switch 🎚️ fermé ⇒ candidats retirés + MP au Roi (best-effort)."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    pending = _realm("blanc", pending=True)
    quiet = _realm("noir")  # pas candidat : jamais touché
    service = _RealmsService([pending, quiet])
    stack = NS(realms=service)
    interaction = _interaction()
    strings = sp.settings_strings("fr")

    button = sp.KingdomRegieSwitchButton(
        "season_entry_open", "sas", True, NS(name="success")
    )
    with mock.patch.object(sp, "_panel_guard", new=mock.AsyncMock(return_value=True)), \
            mock.patch("botforge.mods.kingdom.cogs.regie.toggle_switch", new=mock.AsyncMock(return_value=False)), \
            mock.patch.object(sp, "refresh_live_pins_after", new=mock.AsyncMock()), \
            mock.patch.object(sp, "_build_drawer", new=mock.AsyncMock(return_value=NS())), \
            mock.patch.object(sp, "open_unique_ephemeral", new=mock.AsyncMock()), \
            mock.patch.object(sp, "wiring", lambda: stack), \
            mock.patch("botforge.mods.kingdom.cogs.apply_flow._guild_locale", new=mock.AsyncMock(return_value="fr")), \
            mock.patch("botforge.mods.kingdom.cogs.common.dm_user_safe", new=mock.AsyncMock()) as dm:
        await button.callback(interaction)

    assert service.cleared == ["r-blanc"], "the waiting room emptied"
    dm.assert_awaited_once_with(interaction.client, "77", strings["settings_sas_drain_closed_dm"])


@pytest.mark.asyncio
async def test_the_manual_open_never_drains_anything() -> None:
    """Rouvrir n'efface rien — la réouverture est un geste neutre."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    pending = _realm("blanc", pending=True)
    service = _RealmsService([pending])
    stack = NS(realms=service)
    interaction = _interaction()

    button = sp.KingdomRegieSwitchButton(
        "season_entry_open", "sas", False, NS(name="danger")
    )
    with mock.patch.object(sp, "_panel_guard", new=mock.AsyncMock(return_value=True)), \
            mock.patch("botforge.mods.kingdom.cogs.regie.toggle_switch", new=mock.AsyncMock(return_value=True)), \
            mock.patch.object(sp, "refresh_live_pins_after", new=mock.AsyncMock()), \
            mock.patch.object(sp, "_build_drawer", new=mock.AsyncMock(return_value=NS())), \
            mock.patch.object(sp, "open_unique_ephemeral", new=mock.AsyncMock()), \
            mock.patch.object(sp, "wiring", lambda: stack), \
            mock.patch("botforge.mods.kingdom.cogs.common.dm_user_safe", new=mock.AsyncMock()) as dm:
        await button.callback(interaction)

    assert service.cleared == [], "an OPEN keeps the pending request alive"
    dm.assert_not_awaited()


# ---------------------------------------------------------------------------
# La fin de saison — ferme le sas, vide la salle, prévient les Rois
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_end_of_season_closes_the_sas_and_drains() -> None:
    """🏁 : switch season_entry_open ⇒ False + vidage + MP saison (neutre)."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    pending = _realm("blanc", pending=True)
    service = _RealmsService([pending])
    stack = NS(
        kingdoms=NS(
            current_season=mock.AsyncMock(return_value=NS(phase="started", started_at=None)),
            reset=mock.AsyncMock(),
        ),
        realms=service,
    )
    interaction = _interaction()
    strings = sp.settings_strings("fr")
    switches: list[tuple[str, bool]] = []

    async def _set_switch(client: Any, guild: str, key: str, value: bool) -> bool:
        switches.append((key, bool(value)))
        return True

    with mock.patch.object(sp, "_needs_stack", lambda s: (stack, None)), \
            mock.patch.object(sp, "refresh_live_pins_after", new=mock.AsyncMock()), \
            mock.patch("botforge.mods.kingdom.cogs.regie.set_switch", _set_switch), \
            mock.patch("botforge.mods.kingdom.cogs.apply_flow._guild_locale", new=mock.AsyncMock(return_value="fr")), \
            mock.patch("botforge.mods.kingdom.cogs.common.dm_user_safe", new=mock.AsyncMock()) as dm:
        await sp._end_season(interaction, strings)

    assert ("season_entry_open", False) in switches, "the season's end closes the airlock"
    assert service.cleared == ["r-blanc"], "the waiting room emptied at the end"
    dm.assert_awaited_once_with(
        interaction.client, "77", strings["settings_sas_drain_season_dm"]
    )


@pytest.mark.asyncio
async def test_the_drain_survives_a_broken_dm_and_engine() -> None:
    """Best-effort TOTAL : MP raté ⇒ le candidat est quand même vidé."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    pending = _realm("blanc", pending=True)
    service = _RealmsService([pending])
    stack = NS(realms=service)
    interaction = _interaction()

    async def _boom(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("DMUnavailable")

    button = sp.KingdomRegieSwitchButton(
        "season_entry_open", "sas", True, NS(name="success")
    )
    with mock.patch.object(sp, "_panel_guard", new=mock.AsyncMock(return_value=True)), \
            mock.patch("botforge.mods.kingdom.cogs.regie.toggle_switch", new=mock.AsyncMock(return_value=False)), \
            mock.patch.object(sp, "refresh_live_pins_after", new=mock.AsyncMock()), \
            mock.patch.object(sp, "_build_drawer", new=mock.AsyncMock(return_value=NS())), \
            mock.patch.object(sp, "open_unique_ephemeral", new=mock.AsyncMock()), \
            mock.patch.object(sp, "wiring", lambda: stack), \
            mock.patch("botforge.mods.kingdom.cogs.apply_flow._guild_locale", new=mock.AsyncMock(return_value="fr")), \
            mock.patch("botforge.mods.kingdom.cogs.common.dm_user_safe", new=_boom):
        await button.callback(interaction)

    assert service.cleared == ["r-blanc"], "a failed DM never blocks the drain"


def test_the_two_dm_notes_and_the_refusal_ship_fr_and_en() -> None:
    """Parité fr/en : le refus de lancement + les DEUX MPS (manuel/fin)."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    keys = (
        "settings_launch_sas_closed",
        "settings_sas_drain_closed_dm",
        "settings_sas_drain_season_dm",
    )
    for loc in ("fr", "en"):
        strings = sp.settings_strings(loc)
        for key in keys:
            assert strings.get(key), f"{loc} missing {key}"
