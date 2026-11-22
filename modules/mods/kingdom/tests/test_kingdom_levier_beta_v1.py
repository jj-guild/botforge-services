"""levier-bêta-v1 (Drasah 22-23/11, Check 140) — the parcours LEVER.

The decisions (consignées « 📌 DÉCISIONS Drasah 22/11 ») :
1. UN SEUL levier Classique ↔ Bêta dans le tiroir Régie — il ABSORBE
   le switch « 📝 Compte requis » (la clé ``registration_required``
   reste la source effective du parcours, le levier la pilote + sync
   le drapeau bêta core).
2. VERROUILLÉ pendant qu'une saison vit (setup OU started ; ended
   ne verrouille plus).
3. Position affichée = effective (parcours bêta OU drapeau levé) —
   le drapeau orphelin devient lisible ET abaissable d'un clic.
4. La boucle bêta relance TOUTE SEULE une saison bêta « ended ».
5. « 🏁 Terminer » accepte aussi phase « ended ».

The regression net mirrors each rule : the template (no double
dispatch with the switches nor the realm buttons), the drawer (the
lever IN, the switch OUT), the callback (locked note / flip + flag),
the 5-min loop pass (relaunch / ignore), and « Terminer ».
"""

from __future__ import annotations

import inspect
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


# ---------------------------------------------------------------------------
# (1) the anchored template — no double dispatch
# ---------------------------------------------------------------------------


def test_the_parcours_lever_template_is_anchored_and_alone() -> None:
    """The lever id fullmatches ITS targets and NOTHING else of the regie."""
    from botforge.mods.kingdom.cogs.settings_panel import (
        KingdomRegieParcoursButton,
        KingdomRegieRealmButton,
        KingdomRegieSwitchButton,
    )

    pattern = re.compile(KingdomRegieParcoursButton.__discord_ui_compiled_template__.pattern)
    assert pattern.fullmatch("kingdom:console-regie:parcours:classic")
    assert pattern.fullmatch("kingdom:console-regie:parcours:beta")
    # the switch namespace stays [a-z_]+ — the lever's ":" escapes it
    switch = re.compile(KingdomRegieSwitchButton.__discord_ui_compiled_template__.pattern)
    assert not switch.fullmatch("kingdom:console-regie:parcours:classic")
    # and the realm template (restore/purge kinds) does not eat it either
    realm = re.compile(KingdomRegieRealmButton.__discord_ui_compiled_template__.pattern)
    assert not realm.fullmatch("kingdom:console-regie:parcours:beta")


def test_the_lever_builds_its_two_positions() -> None:
    """A valid target renders, an alien one refuses at build time."""
    import discord

    from botforge.mods.kingdom.cogs.settings_panel import KingdomRegieParcoursButton

    beta = KingdomRegieParcoursButton("beta", "Bêta", True, False)
    assert beta.target == "beta"
    assert str(beta.item.custom_id) == "kingdom:console-regie:parcours:beta"  # type: ignore[attr-defined]
    with pytest.raises(ValueError):
        KingdomRegieParcoursButton("alien", "??", True, False)  # type: ignore[arg-type]
    _ = discord  # the import proves discord.py loaded for the item


# ---------------------------------------------------------------------------
# (2) the drawer — the lever IN, the switch OUT
# ---------------------------------------------------------------------------


def test_the_regie_drawer_rides_the_lever_and_not_the_switch() -> None:
    """registration_required ne vit PLUS dans la pile — the lever rules."""
    from botforge.mods.kingdom.cogs.settings_panel import _regie_drawer, settings_strings

    strings = settings_strings("fr")
    view = _regie_drawer(strings, season_running=True)
    ids = _ids(view)
    assert "kingdom:console-regie:parcours:classic" in ids
    assert "kingdom:console-regie:parcours:beta" in ids
    assert "kingdom:console-regie:registration_required" not in ids, (
        "the old switch must NOT render anymore (the lever absorbed it)"
    )
    # the lock hint rides the drawer while a season lives
    texts = "\n".join(_texts(view))
    assert str(strings["settings_regie_parcours_label"]) in texts
    assert str(strings["settings_regie_parcours_locked_hint"]) in texts

    # season_free drawer: the lock hint VANISHES (the lever opens)
    free = _regie_drawer(strings, season_running=False)
    assert str(strings["settings_regie_parcours_locked_hint"]) not in "\n".join(_texts(free))


def test_the_lever_positions_follow_the_effective_parcours() -> None:
    """parcours_beta=True marks the BETA side ● and the classic side ○."""
    import discord

    from botforge.mods.kingdom.cogs.settings_panel import _regie_drawer, settings_strings

    view = _regie_drawer(settings_strings("fr"), parcours_beta=True)
    buttons = {
        str(item.custom_id): item
        for item in view.walk_children()  # type: ignore[attr-defined]
        if str(getattr(item, "custom_id", "")).startswith("kingdom:console-regie:parcours:")
    }
    assert len(buttons) == 2
    assert "●" in str(buttons["kingdom:console-regie:parcours:beta"].label)
    assert "○" in str(buttons["kingdom:console-regie:parcours:classic"].label)
    # and the lever rides the semantic styles (active = success)
    assert buttons["kingdom:console-regie:parcours:beta"].style is discord.ButtonStyle.success
    assert buttons["kingdom:console-regie:parcours:classic"].style is discord.ButtonStyle.secondary


# ---------------------------------------------------------------------------
# (3) the callback — locked note / flip + flag + re-render
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

    async def send(self, content: object = None, **kwargs: object):  # type: ignore[no-untyped-def]
        self.sent.append((content, kwargs))
        return NS(id=f"f{len(self.sent)}")

    async def followup_send(self, *a: object, **k: object) -> None:  # pragma: no cover
        return None


def _interaction(resp: _Resp, follow: _Follow) -> NS:  # type: ignore[no-untyped-def]
    return NS(
        locale="fr", guild_id="7", guild=None,
        user=NS(id="7", guild_permissions=None),
        client=NS(),
        response=resp, followup=follow,
    )


@pytest.mark.asyncio
async def test_the_lever_refuses_while_a_season_lives(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Locked: the note arrives, NOTHING flips (rule #2)."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    flipped: list[tuple[str, bool]] = []

    async def _set_switch(bot: object, gid: str, key: str, value: bool) -> None:
        flipped.append((key, value))

    windows: list[dict] = []

    async def _open_unique(interaction: object, content: object = None, **kw: object):
        windows.append({"content": content, **kw})

    async def _guard(interaction: object) -> bool:
        return True

    monkeypatch.setattr(sp, "_panel_guard", _guard)
    monkeypatch.setattr(sp, "wiring", lambda: NS(kingdoms=NS()))
    from botforge.mods.kingdom.cogs import regie as _regie
    monkeypatch.setattr(_regie, "set_switch", _set_switch)
    monkeypatch.setattr(sp, "open_unique_ephemeral", _open_unique)
    saved: dict[str, bool] = {}

    async def _season_running(stack: object) -> bool:
        saved["called"] = True
        return True

    from botforge.mods.kingdom.cogs import beta_loop as _bl
    monkeypatch.setattr(_bl, "season_running", _season_running)

    resp, follow = _Resp(), _Follow()
    btn = sp.KingdomRegieParcoursButton("beta", "Bêta", False, True)
    await btn.callback(_interaction(resp, follow))  # type: ignore[arg-type]

    assert resp.deferred, "fast-ack first (the 3-second clock)"
    assert saved.get("called"), "the lock read ran"
    assert not flipped, "a living season MUST freeze the lever"
    assert windows, "the locked note reaches the admin"
    assert windows[0]["content"], "the note is a real string"


@pytest.mark.asyncio
async def test_the_lever_flips_the_key_the_flag_and_rerenders(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Season-free: set_switch + the flag sync + the drawer opens again."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    flipped: list[tuple[str, bool]] = []
    flags: list[bool] = []
    rendered: list[str] = []

    async def _set_switch(bot: object, gid: str, key: str, value: bool) -> None:
        flipped.append((key, value))

    async def _read_regie(bot: object, gid: str) -> dict:
        return {"registration_required": True}  # classic today

    async def _lower(interaction: object) -> bool:
        flags.append(False)
        return True

    async def _raise(interaction: object) -> bool:
        flags.append(True)
        return True

    async def _pins(interaction: object) -> None:
        return None

    async def _open_unique(interaction: object, content: object = None, **kw: object):
        rendered.append(str(content or "") + str(kw.get("view") and "VIEW"))

    async def _drawer(drawer: str, locale: str, bot: object = None, gid: str = ""):
        rendered.append(drawer)
        return NS(walk_children=lambda: [])

    async def _guard(interaction: object) -> bool:
        return True

    async def _season_running(stack: object) -> bool:
        return False

    async def _pins_refresh(interaction: object) -> None:
        return None

    from botforge.mods.kingdom.cogs import regie as _regie
    monkeypatch.setattr(_regie, "set_switch", _set_switch)
    monkeypatch.setattr(_regie, "read_regie", _read_regie)
    monkeypatch.setattr(sp, "_panel_guard", _guard)
    monkeypatch.setattr(sp, "_lower_beta_flag", _lower)
    monkeypatch.setattr(sp, "_raise_beta_flag", _raise)
    monkeypatch.setattr(sp, "refresh_live_pins_after", _pins_refresh)
    monkeypatch.setattr(sp, "open_unique_ephemeral", _open_unique)
    monkeypatch.setattr(sp, "_build_drawer", _drawer)
    monkeypatch.setattr(sp, "wiring", lambda: NS(kingdoms=NS()))
    from botforge.mods.kingdom.cogs import beta_loop as _bl
    monkeypatch.setattr(_bl, "season_running", _season_running)

    resp, follow = _Resp(), _Follow()
    btn = sp.KingdomRegieParcoursButton("beta", "Bêta", False, False)
    await btn.callback(_interaction(resp, follow))  # type: ignore[arg-type]

    assert resp.deferred, "fast-ack first"
    assert flipped == [("registration_required", False)], (
        "Bêta = postuler direct : the régie key lowers (the source stays)"
    )
    assert flags == [True], "the core beta flag rises with the lever"
    assert "regie" in rendered, "the drawer re-renders after the flip"


# ---------------------------------------------------------------------------
# (4) the 5-min loop pass — relaunch an ENDED beta, ignore the rest
# ---------------------------------------------------------------------------


def _fake_stack(phase: str, beta_name: str | None, finished: bool = False) -> NS:
    launched: list[str] = []

    class _Kingdoms:
        async def current_season(self) -> NS:
            return NS(
                id="season-1", phase=phase, beta_name=beta_name,
                finished=finished,
            )

        async def launch(self, names: object = None) -> NS:
            launched.append("launch")
            return NS(id="season-2", phase="setup", beta_name=beta_name)

        async def start_season(self) -> NS:
            launched.append("start")
            return NS(id="season-2")

    class _Realms:
        def __init__(self) -> None:
            self.released: list[str] = []

        async def realms(self) -> list[NS]:
            return [
                NS(
                    id="realm:aegis-1", name="AEGIS", engagement=NS(),
                    archived_at=0, king_id="10", king_name="Roi",
                    member_ids=["11"],
                )
            ]

        async def release_engagement(self, realm_id: str) -> None:
            self.released.append(realm_id)

        async def engage(self, rid: str, sid: str, kid: str) -> NS:
            return NS(id=rid)

        async def save_habitat(self, rid: str, ids: object) -> None:
            return None

    return NS(kingdoms=_Kingdoms(), realms=_Realms(), launched=launched)


@pytest.mark.asyncio
async def test_the_beta_loop_relanches_an_ended_beta(monkeypatch) -> None:
    """phase ended + beta_name → launch + arm + start, the shells re-seated."""
    from botforge.mods.kingdom.cogs import beta_loop as bl

    stack = _fake_stack("ended", "weekend-compressé")

    async def _arm(s: object) -> None:
        s.launched.append("arm")  # type: ignore[attr-defined]

    from botforge.mods.kingdom.cogs import common as _common, settings_panel as _sp
    monkeypatch.setattr(_common, "wiring", lambda: stack)
    monkeypatch.setattr(_sp, "_arm_compressed_beta", _arm)
    bot = NS(guilds=[NS(id="7")])
    summary = await bl.run_beta_loop_safe(bot)

    assert summary is not None, "the pass RELAUNCHES an ended beta"
    assert "launch" in stack.launched and "start" in stack.launched and "arm" in stack.launched
    assert stack.realms.released == ["realm:aegis-1"], (
        "the played shells are released BEFORE the archive"
    )


@pytest.mark.asyncio
async def test_the_beta_loop_ignores_the_living_and_the_classic(monkeypatch) -> None:
    """ended WITHOUT beta_name, finished, setup, started → NOTHING."""
    from botforge.mods.kingdom.cogs import beta_loop as bl

    bot = NS(guilds=[])
    for season in (
        NS(id="s", phase="ended", beta_name=None, finished=False),  # classic
        NS(id="s", phase="ended", beta_name="w", finished=True),  # already done
        NS(id="s", phase="setup", beta_name="w", finished=False),
        NS(id="s", phase="started", beta_name="w", finished=False),
    ):

        class _Kingdoms:
            async def current_season(self) -> object:
                return season

        from botforge.mods.kingdom.cogs import common as _common
        monkeypatch.setattr(_common, "wiring", lambda: NS(kingdoms=_Kingdoms()))
        assert await bl.run_beta_loop_safe(bot) is None, season.phase
    # and a dead wiring (no service) is a None too, never a raise
    from botforge.mods.kingdom.cogs import common as _common
    monkeypatch.setattr(_common, "wiring", lambda: None)
    assert await bl.run_beta_loop_safe(bot) is None


@pytest.mark.asyncio
async def test_season_running_locks_only_on_living_seasons() -> None:
    """The lever's lock: setup/started lock, ended/None/finished do NOT."""
    from botforge.mods.kingdom.cogs.beta_loop import season_running

    class _S:
        def __init__(self, season: object) -> None:
            self.season = season
            self.kingdoms = NS(current_season=self._read)

        async def _read(self) -> object:
            return self.season

    assert await season_running(_S(NS(phase="setup", finished=False))) is True
    assert await season_running(_S(NS(phase="started", finished=False))) is True
    assert await season_running(_S(NS(phase="ended", finished=False))) is False
    assert await season_running(_S(NS(phase="ended", finished=True))) is False
    assert await season_running(_S(None)) is False
    assert await season_running(None) is False


# ---------------------------------------------------------------------------
# (5) « 🏁 Terminer » — the SAME button ends a beta's own « ended »
# ---------------------------------------------------------------------------


def test_end_season_accepts_started_and_ended() -> None:
    """Before: only « started » was terminable — an auto-ended beta was
    UNTOUCHABLE (the admin had no gesture left). The phases tuple now
    carries BOTH (rule #5, the md5 contract of the started case kept)."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    src = inspect.getsource(sp._end_season)
    assert '"ended"' in src, (
        "« Terminer » MUST accept an auto-ended beta season"
    )
    assert '"started"' in src, "the existing contract stays"
