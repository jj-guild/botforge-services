"""hors-saison-v1 + hub-content-v2 + pins-fusion-v1 — the tests (Drasah 20/11).

Three legs, one cadence (the 5-min pass):
- the conscription gate bends #enregistrement/#postuler to the LIVE
  season's type (beta masks the account step entirely; classical
  restores the declared parcours), converge-idempotent;
- the realm hub panel is a components-v2 LayoutView — the deploy NEVER
  sends ``content`` alongside the v2 flag (the 50035 that emptied every
  hub), re-edits in place via ``discord['hub_message']``, and a
  converged hub costs no edit (fingerprint guard);
- the retired pin key's orphan message is swept (unpin+delete+forget),
  while a survivor reusing the same message id is spared the delete.
"""

from __future__ import annotations

from typing import Any

import discord
import pytest


# ---------------------------------------------------------------------------
# The conscription gate — season_type bends the parcours
# ---------------------------------------------------------------------------


class _FakeRole:
    def __init__(self, rid: int) -> None:
        self.id = rid


class _FakeChannel:
    def __init__(self, cid: int) -> None:
        self.id = cid
        self.overwrites: dict[Any, Any] = {}
        self.edits: list[dict[str, Any]] = []

    async def edit(self, **kwargs: Any) -> None:
        self.edits.append(kwargs)
        if "overwrites" in kwargs:
            self.overwrites = dict(kwargs["overwrites"])


class _FakeGuild:
    def __init__(self) -> None:
        self.id = 1
        self.me = _FakeRole(99)
        self.default_role = _FakeRole(0)
        self._roles = {10: _FakeRole(10), 20: _FakeRole(20)}
        self._channels = {100: _FakeChannel(100), 200: _FakeChannel(200)}

    def get_role(self, rid: int) -> _FakeRole | None:
        return self._roles.get(rid)

    def get_channel(self, cid: int) -> _FakeChannel | None:
        return self._channels.get(cid)


class _RolesService:
    async def resolve_role_id(self, guild_id: str, mod: str, role_key: str) -> str | None:
        return {"kingdom_admin": "10", "enregistre": "20"}.get(role_key)


class _GateBot:
    def __init__(self) -> None:
        self.guilds = [guild]
        self.mod_roles_service = _RolesService()
        self.get_guild = lambda gid: guild if int(gid) == guild.id else None  # noqa: E731


guild = _FakeGuild()
bot = _GateBot()

_CHANNEL_IDS = {"register": "100", "apply": "200"}


@pytest.fixture(autouse=True)
def _patch_season_and_store(monkeypatch: pytest.MonkeyPatch) -> None:
    import botforge.discord.ui.panels_provisioning as provisioning

    async def fake_stored(gid: str, scope: str, key: str) -> str | None:
        assert scope == "mod/kingdom"
        return _CHANNEL_IDS.get(key)

    monkeypatch.setattr(provisioning, "stored_channel_id", fake_stored)
    guild._channels[100].edits.clear()
    guild._channels[200].edits.clear()
    guild._channels[100].overwrites = {}
    guild._channels[200].overwrites = {}


async def _run(beta: bool) -> tuple[_FakeChannel, _FakeChannel]:
    from botforge.mods.kingdom.cogs import camp_beta

    original = camp_beta.season_is_beta

    async def fake_is_beta() -> bool:
        return beta

    camp_beta.season_is_beta = fake_is_beta  # the pass re-imports it per call
    from botforge.mods.kingdom.cogs.conscription_gate import run_conscription_gate_pass

    try:
        await run_conscription_gate_pass(bot)
    finally:
        camp_beta.season_is_beta = original
    return guild._channels[100], guild._channels[200]


@pytest.mark.asyncio
async def test_beta_season_masks_register_and_opens_apply() -> None:
    register, apply = await _run(beta=True)
    assert register.edits, "#enregistrement must be re-gated in beta"
    everyone = register.overwrites[guild.default_role]
    assert everyone.view_channel is False, "beta hides #enregistrement entirely"
    assert 20 not in {r.id for r in register.overwrites}, "no player grant on a hidden salon"
    assert apply.edits, "#postuler must be re-gated in beta"
    assert apply.overwrites[guild.default_role].view_channel is True, "beta opens #postuler"
    assert apply.overwrites[guild._roles[10]].view_channel is True, "staff keeps #postuler"


@pytest.mark.asyncio
async def test_classical_season_restores_the_declared_parcours() -> None:
    register, apply = await _run(beta=False)
    assert register.overwrites[guild.default_role].view_channel is True
    assert (
        register.overwrites[guild._roles[20]].view_channel is False
    ), "the Enregistré deny stands (masked per account)"
    assert register.overwrites[guild.default_role].send_messages is False
    assert apply.overwrites[guild.default_role].view_channel is False, "classical gates #postuler"
    assert apply.overwrites[guild._roles[20]].view_channel is True, "the registered players see it"


@pytest.mark.asyncio
async def test_the_gate_converges_without_a_second_edit() -> None:
    register, apply = await _run(beta=True)
    assert len(register.edits) == 1 and len(apply.edits) == 1
    await _run(beta=True)
    assert len(register.edits) == 1 and len(apply.edits) == 1, "converged = ZERO extra API call"


@pytest.mark.asyncio
async def test_a_switch_of_type_regains_the_edit() -> None:
    await _run(beta=True)
    register, apply = await _run(beta=False)
    assert len(register.edits) == 2, "the season type's change re-gates the salon"


# ---------------------------------------------------------------------------
# hub-content-v2 — the hub panel is a pure LayoutView, healed in place
# ---------------------------------------------------------------------------


class _FakeMessage:
    def __init__(self, mid: int) -> None:
        self.id = mid
        self.author = _FakeRole(99)  # guild.me.id — the history fallback's match
        self.edits: list[dict[str, Any]] = []

    async def edit(self, **kwargs: Any) -> None:
        self.edits.append(kwargs)


class _FakeHubChannel:
    def __init__(self) -> None:
        self.id = 555
        self.name = "🏰 Le royaume"
        self._sent: list[dict[str, Any]] = []
        self._messages: dict[int, _FakeMessage] = {}
        self.next_id = 900

    async def send(self, **kwargs: Any) -> _FakeMessage:
        self._sent.append(kwargs)
        message = _FakeMessage(self.next_id)
        self.next_id += 1
        self._messages[message.id] = message
        return message

    async def fetch_message(self, mid: int) -> _FakeMessage:
        message = self._messages.get(mid)
        if message is None:
            raise discord.NotFound("gone", 404)
        return message

    def history(self, limit: int = 25) -> Any:
        channel = self

        class _Hist:
            def __aiter__(self) -> "_Hist":
                self._iter = iter(list(channel._messages.values())[:limit])
                return self

            async def __anext__(self) -> _FakeMessage:
                try:
                    return next(self._iter)
                except StopIteration:
                    raise StopAsyncIteration from None

        return _Hist()


class _FakeHubCategory:
    def __init__(self, channel: _FakeHubChannel) -> None:
        self.id = 77
        self.name = "🏰 Avelorn"
        self.channels = [channel]


class _FakeHubGuild:
    def __init__(self) -> None:
        self.id = 1
        self.me = _FakeRole(99)
        self.categories = []
        self.default_role = _FakeRole(0)


class _FakeRealm:
    id = "realm-1"
    name = "Avelorn"
    slug = "avelorn"
    engagement = None  # dormant — hors saison
    discord: dict[str, Any] = {}


def _hub() -> tuple[_FakeHubGuild, _FakeHubChannel, _FakeRealm]:
    channel = _FakeHubChannel()
    category = _FakeHubCategory(channel)
    guild_hub = _FakeHubGuild()
    guild_hub.categories = [category]
    return guild_hub, channel, _FakeRealm()


@pytest.mark.asyncio
async def test_the_hub_deploy_never_sends_content_alongside_the_v2_layout() -> None:
    from botforge.mods.kingdom.cogs.realms import deploy_realm_hub

    guild, channel, realm = _hub()
    message_id = await deploy_realm_hub(guild, realm, locale="fr")
    assert message_id and message_id.isdigit(), "the deploy returns the message id"
    assert channel._sent, "the hub panel must land"
    assert "content" not in channel._sent[0], (
        "content + components-v2 = 50035 — the bug that emptied EVERY hub"
    )
    assert isinstance(channel._sent[0]["view"], discord.ui.LayoutView)
    assert channel._sent[0].get("silent") is True


@pytest.mark.asyncio
async def test_the_hub_deploys_again_in_place_not_in_duplicate() -> None:
    from botforge.mods.kingdom.cogs.realms import deploy_realm_hub, _HUB_LAST_RENDER

    guild, channel, realm = _hub()
    first = await deploy_realm_hub(guild, realm, locale="fr")
    realm.discord["hub_message"] = first
    _HUB_LAST_RENDER.clear()
    second = await deploy_realm_hub(guild, realm, locale="fr")
    assert second == first, "an existing hub is re-edited, never duplicated"
    assert len(channel._sent) == 1, "the stored id heals the SAME message"
    message = channel._messages[int(first)]
    assert not message.edits or "view" in message.edits[0], "edits carry the layout only"


@pytest.mark.asyncio
async def test_a_converged_hub_costs_no_edit() -> None:
    from botforge.mods.kingdom.cogs.realms import deploy_realm_hub

    guild, channel, realm = _hub()
    first = await deploy_realm_hub(guild, realm, locale="fr")
    realm.discord["hub_message"] = first
    await deploy_realm_hub(guild, realm, locale="fr")
    assert len(channel._messages[int(first)].edits) == 0, "fingerprint guard: no redundant edit"


# ---------------------------------------------------------------------------
# pins-fusion-v1 — the retired key's orphan is swept, the survivor spared
# ---------------------------------------------------------------------------


class _FakeRegistry:
    def __init__(self) -> None:
        self.store: dict[tuple[str, str], Any] = {}
        self.forgotten: list[str] = []

    async def resolve(self, platform: str, message_key: str, entity_id: str) -> Any:
        return self.store.get((platform, message_key))

    async def forget(self, platform: str, message_key: str, entity_id: str) -> None:
        self.forgotten.append(message_key)
        self.store.pop((platform, message_key), None)


class _RegisteredMessage:
    def __init__(self, channel_id: str, message_id: str) -> None:
        self.channel_id = channel_id
        self.message_id = message_id


class _SweptMessage:
    def __init__(self) -> None:
        self.id = 123
        self.pinned = True
        self.deleted = False
        self.unpinned = False

    async def unpin(self, **kwargs: Any) -> None:
        self.unpinned = True

    async def delete(self, **kwargs: Any) -> None:
        self.deleted = True


class _SweepChannel:
    def __init__(self, message: _SweptMessage) -> None:
        self.id = 400
        self.message = message

    async def fetch_message(self, mid: int) -> _SweptMessage:
        return self.message


class _SweepGuild:
    def __init__(self, channel: _SweepChannel) -> None:
        self.id = 7
        self.categories: list[Any] = []
        self._channel = channel

    def get_channel(self, cid: int) -> "_SweepChannel":
        return self._channel


@pytest.mark.asyncio
async def test_the_orphaned_legacy_pin_is_unpinned_deleted_and_forgotten() -> None:
    from botforge.mods.kingdom.cogs import legacy_pins

    registry = _FakeRegistry()
    registry.store[("discord", "panel:mod:kingdom:candidates")] = _RegisteredMessage("400", "123")
    registry.store[("discord", "panel:mod:kingdom:validation")] = _RegisteredMessage("400", "999")
    message = _SweptMessage()
    channel = _SweepChannel(message)
    sweep_guild = _SweepGuild(channel)

    class _SweepBot:
        guilds = [sweep_guild]
        message_registry = registry

    legacy_pins.reset_swept()
    swept = await legacy_pins.sweep_legacy_pins(_SweepBot())
    assert swept == 1, "the orphaned duplicate retires"
    assert message.unpinned and message.deleted
    assert "panel:mod:kingdom:candidates" in registry.forgotten
    assert "panel:mod:kingdom:validation" not in registry.forgotten, "the survivor stands"


@pytest.mark.asyncio
async def test_a_reused_message_id_forgives_the_delete() -> None:
    from botforge.mods.kingdom.cogs import legacy_pins

    registry = _FakeRegistry()
    registry.store[("discord", "panel:mod:kingdom:candidates")] = _RegisteredMessage("400", "123")
    registry.store[("discord", "panel:mod:kingdom:validation")] = _RegisteredMessage("400", "123")
    legacy_pins.reset_swept()

    class _SweepBot:
        guilds = []
        message_registry = registry

    swept = await legacy_pins.sweep_legacy_pins(_SweepBot())
    assert swept == 0, "the banner pass already claimed the slot — name-only retirement"


def test_the_localized_refusal_heads_dropped_the_banned_emoji() -> None:
    """🚫 → ❌ everywhere in the validation surfaces (fr + en parity)."""
    from pathlib import Path

    locales = Path(__file__).resolve().parents[1] / "conf" / "locales"
    fr_body = (locales / "fr.yaml").read_text(encoding="utf-8")
    en_body = (locales / "en.yaml").read_text(encoding="utf-8")
    assert "🚫" not in fr_body, "fr.yaml still carries the retired emoji"
    assert "🚫" not in en_body, "en.yaml still carries the retired emoji"
    assert "season_beta_apply_line" in fr_body and "season_beta_apply_line" in en_body


# ---------------------------------------------------------------------------
# ONE beta (Drasah 21/11) — the phase flag bends the parcours too
# ---------------------------------------------------------------------------


class _FakeStateService:
    """A StateService stand-in carrying the phase flag per key."""

    def __init__(self, active: bool) -> None:
        self._active = active

    async def get_state(self, scope: str, key: str) -> dict[str, Any] | None:
        assert scope == "mod:kingdom"
        assert key.startswith("beta:g:")
        return {"active": self._active}


class _PhaseGateBot(_GateBot):
    """The gate bot carrying a state service with the phase flag."""

    def __init__(self, active: bool) -> None:
        super().__init__()
        self.state_service = _FakeStateService(active)


async def _run_phase(active: bool) -> tuple[_FakeChannel, _FakeChannel]:
    """Run the gate with NO season beta, only the phase flag (the toggle)."""
    from botforge.mods.kingdom.cogs import camp_beta

    original = camp_beta.season_is_beta

    async def fake_is_beta() -> bool:
        return False  # the season carries NO beta type (the toggle case)

    camp_beta.season_is_beta = fake_is_beta
    from botforge.mods.kingdom.cogs.conscription_gate import run_conscription_gate_pass

    try:
        await run_conscription_gate_pass(_PhaseGateBot(active))
    finally:
        camp_beta.season_is_beta = original
    return guild._channels[100], guild._channels[200]


@pytest.mark.asyncio
async def test_the_phase_flag_bends_the_parcours_like_a_beta_season() -> None:
    """Paramètres → Démarrer la beta masks #enregistrement and opens
    #postuler — the toggle IS the beta, no season type needed."""
    register, apply = await _run_phase(active=True)
    assert register.edits, "the phase flag must re-gate #enregistrement"
    assert register.overwrites[guild.default_role].view_channel is False
    assert apply.edits, "the phase flag must open #postuler"
    assert apply.overwrites[guild.default_role].view_channel is True


@pytest.mark.asyncio
async def test_the_phase_flag_off_keeps_the_classical_parcours() -> None:
    """Leaving the beta phase straightens the parcours right back."""
    register, apply = await _run_phase(active=False)
    assert register.overwrites[guild.default_role].view_channel is True
    assert apply.overwrites[guild.default_role].view_channel is False


@pytest.mark.asyncio
async def test_a_missing_state_service_degrades_to_the_season_type() -> None:
    """A bot WITHOUT a state service never bends on the flag — the
    season type alone decides (the None-cache contract of the seam)."""
    from botforge.mods.kingdom.cogs import camp_beta

    original = camp_beta.season_is_beta

    async def fake_is_beta() -> bool:
        return False

    camp_beta.season_is_beta = fake_is_beta
    try:
        assert await camp_beta.kingdom_is_beta(bot, "1") is False
        phase_bot = _PhaseGateBot(active=True)
        assert await camp_beta.kingdom_is_beta(phase_bot, "1") is True
    finally:
        camp_beta.season_is_beta = original
