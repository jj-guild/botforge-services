"""Affaire 49 « retour-testeurs-v1 » (Drasah 27/11, GO explicite) : le patch
des retours terrain de supasaymon et Drasah.

* le bouton 🛡️ Seigneurie de la Salle du conseil ne crash plus (il passait
  une locale en string à ``realm_strings`` qui attend l'interaction —
  le defer était déjà consommé, le joueur voyait « L'application n'a pas
  répondu ») ;
* le pin 📜 Scriptorium portera l'illustration de la référence dès que
  l'asset sera uploadé sur la branche (le patch complet — clé
  ``scriptorium_artwork`` + MediaGallery — est prêt, il attend le PNG) ;
* le message de meeting porte la bannière Civ-VS-Civ (la mosaïque
  blasons de la référence, peinte depuis les civs finales de chaque camp) ;
* le bouton 📜 « Voir la draft » acquitte le clic AVANT de construire la
  fiche (fast-ack : l'horloge de 3 secondes appartient au defer, la
  fenêtre suit en followup).
"""


from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import discord
import pytest


class _Response:
    """The interaction response recorder — defer first is the contract."""

    def __init__(self) -> None:
        self.done = False
        self.deferred: list[bool] = []
        self.order: list[str] = []

    def is_done(self) -> bool:
        return self.done

    async def defer(self, ephemeral: bool = False) -> None:
        self.done = True
        self.deferred.append(ephemeral)
        self.order.append("defer")

    async def send_message(self, content: str, ephemeral: bool = False) -> None:
        self.order.append("send")


def _interaction(user_id: str = "123") -> Any:
    return SimpleNamespace(
        locale="fr",
        user=SimpleNamespace(id=user_id),
        response=_Response(),
    )


# ---------------------------------------------------------------------------
# 1. The Seigneurie button — the crash the testers saw
# ---------------------------------------------------------------------------


class _RealmsService:
    def __init__(self, realm: Any) -> None:
        self._realm = realm

    async def realm_of_member(self, user_id: str) -> Any:
        return self._realm


def _fake_stack(realm: Any) -> Any:
    return SimpleNamespace(realms=_RealmsService(realm))


@pytest.mark.asyncio
async def test_the_seigneurie_button_survives_its_click(monkeypatch: pytest.MonkeyPatch) -> None:
    """The callback speaks to realm_strings with the INTERACTION, not a locale."""
    import botforge.mods.kingdom.cogs.lieux as lieux_module
    import botforge.mods.kingdom.cogs.realms as realms_module

    interaction = _interaction()
    realm = SimpleNamespace(name="AEGIS", slug="aegis")
    monkeypatch.setattr(lieux_module, "wiring", lambda: _fake_stack(realm))
    opened: dict[str, Any] = {}

    async def _fake_window(target: Any, content: str | None = None, **kwargs: Any) -> None:
        opened["is_done"] = target.response.is_done()
        target.response.order.append("window")

    async def _fake_seigneurie(target: Any, shell: Any, strings: dict[str, str]) -> object:
        assert strings, "the realm catalog answered"
        return object()

    monkeypatch.setattr(lieux_module, "open_unique_ephemeral", _fake_window)
    monkeypatch.setattr(realms_module, "seigneurie_window", _fake_seigneurie)

    button = await lieux_module.LieuxSeigneurieButton.from_custom_id(interaction, None, None)
    # The old code passed a bare locale string here — realm_strings called
    # locale_of(str) and every click died AFTER the defer.
    await button.callback(interaction)

    assert interaction.response.order == ["defer", "window"], (
        "the Seigneurie click defers then opens the window — no crash"
    )
    assert opened["is_done"], "the window rides the followup — the ack is already done"


@pytest.mark.asyncio
async def test_the_seigneurie_button_without_a_realm_answers_the_gone_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import botforge.mods.kingdom.cogs.lieux as lieux_module
    import botforge.mods.kingdom.cogs.realms as realms_module

    interaction = _interaction()
    monkeypatch.setattr(lieux_module, "wiring", lambda: _fake_stack(None))
    monkeypatch.setattr(realms_module, "realm_strings", lambda _it: {"realm_gone_note": "pas de royaume"})
    captured: dict[str, Any] = {}

    async def _fake_window(target: Any, content: str | None = None, **kwargs: Any) -> None:
        captured["content"] = content

    monkeypatch.setattr(lieux_module, "open_unique_ephemeral", _fake_window)

    button = await lieux_module.LieuxSeigneurieButton.from_custom_id(interaction, None, None)
    await button.callback(interaction)

    assert "royaume" in str(captured["content"]).lower(), "the gone note answered"


# ---------------------------------------------------------------------------
# 3. The meeting banner — the reference's Civ-VS-Civ mosaic rides the room
# ---------------------------------------------------------------------------


def _attack(pickban: dict[str, Any] | None = None) -> Any:
    return SimpleNamespace(
        id="attack-1",
        map_key="Map X",
        score={},
        pickban=pickban or {},
        attacker_lord_id="111",
        defender_lord_id="222",
        attacker_kingdom_id="k1",
        defender_kingdom_id="k2",
        ai_defender=False,
        lobby_url="",
    )


@pytest.mark.asyncio
async def test_the_meeting_banner_paints_from_the_final_civs() -> None:
    """Known-unknown civs degrade to the default crest — the banner always goes out."""
    from botforge.mods.kingdom.cogs.battle import meeting_banner_file

    pickban = {
        "attacker_picks": ["unknown_attacker"],
        "defender_picks": ["unknown_defender"],
    }
    banner = await meeting_banner_file(_attack(pickban))
    assert isinstance(banner, discord.File), "a composite banner came back"
    assert banner.filename == "vs_meeting.png"


@pytest.mark.asyncio
async def test_the_meeting_banner_survives_an_undrafted_meeting() -> None:
    from botforge.mods.kingdom.cogs.battle import meeting_banner_file

    banner = await meeting_banner_file(_attack())
    assert isinstance(banner, discord.File), "no picks yet — the default crest banner"


@pytest.mark.asyncio
async def test_the_meeting_message_wears_the_banner(monkeypatch: pytest.MonkeyPatch) -> None:
    """The banner rides the MEETING message (the scoreboard post), as an attachment."""
    import botforge.mods.kingdom.cogs.battle as battle_module
    from botforge.mods.kingdom.cogs.common import strings_by_locale

    class _Attacks:
        async def record_meeting_message(self, *args: Any) -> None:
            pass

        async def record_ping_message(self, *args: Any) -> None:
            pass

    class _Message:
        id = 777

    class _Salon:
        id = 999

        async def send(self, *args: Any, **kwargs: Any) -> Any:
            sent.append((args, kwargs))
            return _Message()

    sent: list[tuple[tuple, dict]] = []
    stack = SimpleNamespace(attacks=_Attacks(), kingdoms=None)
    guild = SimpleNamespace()

    async def _fake_lord_name(kingdoms: Any, lord_id: str | None) -> str:
        return "Lord"

    monkeypatch.setattr(battle_module, "lord_name", _fake_lord_name)
    monkeypatch.setattr(battle_module, "attack_salon", lambda _g, _a: _Salon())

    await battle_module.post_meeting_message(guild, stack, _attack(), strings_by_locale("fr"))

    assert sent, "the meeting message went out"
    _, kwargs = sent[0]
    files = kwargs.get("files") or []
    assert len(files) == 1 and isinstance(files[0], discord.File), (
        "the meeting post carries exactly the Civ-VS-Civ banner"
    )


# ---------------------------------------------------------------------------
# 4. The draft button — ack FIRST, build behind the defer
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_draft_button_acks_before_it_builds(monkeypatch: pytest.MonkeyPatch) -> None:
    """« L'application n'a pas répondu » — the defer owns the 3s clock now."""
    import botforge.mods.kingdom.cogs.battle as battle_module

    interaction = _interaction()
    stack = SimpleNamespace()
    opened: dict[str, Any] = {}

    async def _fake_open(target: Any, content: str | None = None, **kwargs: Any) -> None:
        opened["is_done"] = target.response.is_done()
        opened["order"] = list(target.response.order)

    async def _fake_by_id(st: Any, aid: str) -> Any:
        return _attack()

    async def _fake_embed(st: Any, at: Any, s: dict[str, str]) -> object:
        return object()

    monkeypatch.setattr(battle_module, "wiring", lambda: stack)
    monkeypatch.setattr(battle_module, "attack_by_id", _fake_by_id)
    monkeypatch.setattr(battle_module, "draft_sheet_embed", _fake_embed)
    monkeypatch.setattr(battle_module, "open_unique_ephemeral", _fake_open)

    button = battle_module.DraftViewButton("attack-1", "📜 Voir la draft")
    await button.callback(interaction)

    assert interaction.response.deferred == [True], "the click is acked ephemeral, first"
    assert opened["is_done"], "the window rides the followup — the ack is already done"
    assert opened["order"] == ["defer"], "nothing answers before the defer"


@pytest.mark.asyncio
async def test_the_draft_button_without_a_service_still_acks(monkeypatch: pytest.MonkeyPatch) -> None:
    """A dead stack answers the note — through the followup, never silent."""
    import botforge.mods.kingdom.cogs.battle as battle_module

    interaction = _interaction()
    captured: dict[str, Any] = {}

    async def _fake_open(target: Any, content: str | None = None, **kwargs: Any) -> None:
        captured["content"] = content
        captured["is_done"] = target.response.is_done()

    monkeypatch.setattr(battle_module, "wiring", lambda: None)
    monkeypatch.setattr(battle_module, "open_unique_ephemeral", _fake_open)

    button = battle_module.DraftViewButton("", "📜 Voir la draft")
    await button.callback(interaction)

    assert interaction.response.done, "the ack happened — Discord never times the click out"
    assert captured["is_done"], "the no-service note rides the followup"
    assert captured["content"], "the note is answered"
