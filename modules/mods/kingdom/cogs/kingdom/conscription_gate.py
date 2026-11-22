"""The conscription's season-type gate (hors-saison-v1, Drasah 20/11).

The parcours' VISIBILITY bends to the season the players play — data,
never mode flags:

- **beta** (« on postule directement, sans compte ») : #enregistrement
  is masked ENTIRELY (the account step does not exist — the staff's
  own admin hat still sees it, no role gets a grant), #postuler opens
  to @everyone. ONE beta (Drasah 21/11): the phase flag (Paramètres →
  « Démarrer la beta ») OR the season's « beta » type — either bends
  the parcours;
- **classical / no season** : the declared parcours stands (#enregistrement
  public + masked per account via the Kingdom Enregistré deny,
  #postuler gated by the registered players' allow).

The gate runs AFTER every provisioning/refresh pass (``run_mod_pin_refresh_pass``
calls it) and right after a season launch — the declared ``mod.yaml``
policy is the BASE, this pass is the season's live overlay. Idempotent
by converge-skip: an already-converged guild costs ZERO API call (the
fix-reset-429 lesson — ONE ``edit(overwrites=...)``, never a PATCH per
target), and unknown overwrites (a manual grant) are carried over
untouched.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("kingdom.conscription_gate")

MOD = "kingdom"
SCOPE = "mod/kingdom"
# role keys per conf/mod.yaml (the persisted ids resolve, names renamable)
ROLE_ADMIN = "kingdom_admin"
ROLE_ENREGISTRE = "enregistre"


async def _role_id(bot: Any, guild_id: str, role_key: str) -> int | None:
    roles_service = getattr(bot, "mod_roles_service", None)
    if roles_service is None:
        return None
    try:
        role_id = await roles_service.resolve_role_id(guild_id, MOD, role_key)
    except Exception:  # noqa: BLE001 — a missing role skips, never a raise
        return None
    return int(role_id) if role_id and str(role_id).isdigit() else None


def _key_of(target: Any) -> str:
    """One stable key per overwrite target (role/member id, str passthrough)."""
    if isinstance(target, str):
        return target
    return f"{getattr(target, 'type', getattr(target, '_type', ''))}:{getattr(target, 'id', '')}"


def _ow(**flags: Any) -> Any:
    import discord

    return discord.PermissionOverwrite(**flags)


def _bot_allow(guild: Any) -> tuple[Any, Any] | None:
    me = getattr(guild, "me", None)
    if me is None:
        return None
    return (
        me,
        _ow(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            manage_channels=True,
            manage_messages=True,
        ),
    )


def _register_overwrites(
    guild: Any, *, beta: bool, enregistre_role: Any, camp_denies: dict[Any, Any] | None = None
) -> dict[Any, Any]:
    """#enregistrement : hidden entirely in beta, declared parcours otherwise."""
    overwrites: dict[Any, Any] = {}
    allow = _bot_allow(guild)
    if allow is not None:
        overwrites[allow[0]] = allow[1]
    everyone = getattr(guild, "default_role", None)
    if everyone is not None:
        overwrites[everyone] = _ow(
            view_channel=False if beta else True,
            send_messages=False if not beta else None,
            read_message_history=True if not beta else None,
        )
    if not beta and enregistre_role is not None:
        # the inverse audience (conscription-4-salons): the salon
        # disappears once the account step is passed
        overwrites[enregistre_role] = _ow(view_channel=False)
    # camp holders never needed the account step (conscription-mask 21/11)
    overwrites.update(camp_denies or {})
    return overwrites


def _apply_overwrites(
    guild: Any, *, beta: bool, admin_role: Any, enregistre_role: Any, camp_denies: dict[Any, Any] | None = None
) -> dict[Any, Any]:
    """#postuler : open to everyone in beta, registered-only otherwise."""
    overwrites: dict[Any, Any] = {}
    allow = _bot_allow(guild)
    if allow is not None:
        overwrites[allow[0]] = allow[1]
    everyone = getattr(guild, "default_role", None)
    if everyone is not None:
        overwrites[everyone] = _ow(view_channel=bool(beta), read_message_history=True, send_messages=False)
    if admin_role is not None:
        overwrites[admin_role] = _ow(view_channel=True, read_message_history=True, manage_channels=True)
    if enregistre_role is not None:
        # classical: the registered players' allow (mod.yaml's `view`);
        # beta: harmless (everyone already sees the salon)
        overwrites[enregistre_role] = _ow(view_channel=True, read_message_history=True)
    # conscription-mask (Drasah 21/11, immersion) : a player who created
    # OR joined a realm has finished the parcours — the salons leave
    # his sidebar (the roster is recomputed every pass, both ways heal)
    overwrites.update(camp_denies or {})
    return overwrites


def _converged(channel: Any, overwrites: dict[Any, Any]) -> bool:
    """True when the channel ALREADY carries exactly the wanted grants."""
    current = {_key_of(target): overwrite for target, overwrite in (getattr(channel, "overwrites", {}) or {}).items()}
    wanted = {_key_of(target): overwrite for target, overwrite in overwrites.items()}
    if set(current) != set(wanted):
        return False
    return all(current[key] == overwrite for key, overwrite in wanted.items())


async def _camp_holder_denies(guild: Any) -> dict[Any, Any]:
    """Member-level view denies for every CAMP HOLDER of this guild.

    conscription-mask (Drasah 21/11) : dès qu'un joueur crée OU rejoint
    un royaume, il a fini le parcours — la sidebar ne doit plus le noyer
    d'étapes révolues (#enregistrement, #postuler). The roster is read
    from the persistent realm shells (Roi + members) and recomputed on
    EVERY pass: a player who leaves a realm regains the parcours within
    one cycle (no stale deny can survive the pass).
    """
    from .common import wiring

    ids: set[str] = set()
    stack = wiring()
    realms_service = getattr(stack, "realms", None) if stack is not None else None
    if realms_service is not None:
        try:
            realms = await realms_service.realms() or []
        except Exception:  # noqa: BLE001 — a read miss masks nobody, never a raise
            realms = []
        for realm in realms:
            # ejection-archive-v1 follow-up (Drasah 22/11) : un royaume
            # ARCHIVÉ est hors du jeu — sa coquille attend dans la
            # régie, ses joueurs (Roi compris) récupèrent leur parcours.
            # Tant que la coquille est vivante (dormante ou engagée),
            # le parcours reste terminé pour ses membres.
            if getattr(realm, "archived_at", 0):
                continue
            ids.add(str(getattr(realm, "king_id", "") or ""))
            ids.update(str(m) for m in (getattr(realm, "member_ids", []) or []))
    denies: dict[Any, Any] = {}
    for mid in sorted(ids):
        if not str(mid).isdigit() or not mid:
            continue
        member = getattr(guild, "get_member", lambda _id: None)(int(mid))
        if member is None:
            continue  # a foreign realm's member (or a shadow) — not this guild's turf
        denies[member] = _ow(view_channel=False)
    return denies


def _is_bare_view_deny(overwrite: Any) -> bool:
    """True for a lone ``view_channel=False`` — the gate's deny signature.

    The conscription salons' member turf belongs to the gate (the
    20/11 carry-over rule keeps unknown grants; a BARE view deny is
    ours by construction): each pass recomputes the roster, so the
    carry-over drops the signature first and the wanted set re-adds
    the members who still hold a camp. No ex-member deny can linger.
    """
    return overwrite == _ow(view_channel=False)


def _is_member_view_deny(guild: Any, target: Any, overwrite: Any) -> bool:
    """A MEMBER's view deny — the gate's own turf, dirty or not.

    drain-coquilles-v1 (Drasah 22/11, Check 135) : l'incident Blanc —
    un deny membre avec d'autres réglages en plus (posé à la main ou
    par une vielle version) survécu à la passe pour toujours, le
    joueur restait masqué sans royaume. La passe droppe maintenant
    TOUT deny membre qui bloque la vue (nu ou sale) : le masque est
    SON territoire, un grant admin ne ressemble jamais à ça. Les
    cibles de RÔLE et le bot ne se touchent jamais (l'invariant
    «unknown overwrites untouched» tient pour le reste).
    """
    if target is getattr(guild, "me", None):
        return False
    if getattr(overwrite, "view_channel", None) is not False:
        return False
    target_id = getattr(target, "id", None)
    if target_id is None or not str(target_id).isdigit():
        return False
    member = getattr(guild, "get_member", lambda _i: None)(int(target_id))
    return member is not None


async def run_conscription_gate_pass(bot: Any, guild_id: str = "") -> int:
    """Bend the register/apply salons to the live beta (ONE beta, 21/11)."""
    from botforge.discord.ui.panels_provisioning import stored_channel_id

    guilds = (
        [bot.get_guild(int(guild_id))]
        if str(guild_id).isdigit()
        else list(getattr(bot, "guilds", []) or [])
    )
    touched = 0
    for guild in guilds:
        if guild is None:
            continue
        gid = str(getattr(guild, "id", ""))
        # ONE beta (Drasah 21/11): the phase flag (Paramètres → Démarrer
        # la beta) OR the season's compressed type — either bends the
        # parcours; the read is PER GUILD (the phase flag is guild state).
        # registration-switch-v1 (22/11): the régie's « Compte requis »
        # OFF bends it the same way (on postule directement, tout saison)
        from .regie import registration_required

        beta = not await registration_required(bot, gid)
        admin_id = await _role_id(bot, gid, ROLE_ADMIN)
        enregistre_id = await _role_id(bot, gid, ROLE_ENREGISTRE)
        admin_role = guild.get_role(admin_id) if admin_id else None
        enregistre_role = guild.get_role(enregistre_id) if enregistre_id else None
        camp_denies = await _camp_holder_denies(guild)
        for key, overwrites in (
            (
                "register",
                _register_overwrites(
                    guild, beta=beta, enregistre_role=enregistre_role, camp_denies=camp_denies
                ),
            ),
            (
                "apply",
                _apply_overwrites(
                    guild,
                    beta=beta,
                    admin_role=admin_role,
                    enregistre_role=enregistre_role,
                    camp_denies=camp_denies,
                ),
            ),
        ):
            channel_id = await stored_channel_id(gid, SCOPE, key)
            if not channel_id or not str(channel_id).isdigit():
                continue
            channel = guild.get_channel(int(channel_id))
            if channel is None or not hasattr(channel, "edit"):
                continue
            # carry over every target the gate does not manage (a manual
            # grant, a future seam — untouched, never dropped); a BARE
            # view deny is the gate's own member turf (_is_bare_view_deny
            # says why) — dropped first, re-added only for the live camp
            # roster, so no ex-member deny can linger on the salons
            wanted_keys = {_key_of(k) for k in overwrites}
            for target, overwrite in dict(getattr(channel, "overwrites", {}) or {}).items():
                if _key_of(target) in wanted_keys:
                    continue
                if _is_member_view_deny(guild, target, overwrite):
                    continue  # the gate recomputes the member denies from the roster
                overwrites[target] = overwrite
            if _converged(channel, overwrites):
                continue
            try:
                await channel.edit(
                    overwrites=overwrites,
                    reason="botforge: the conscription rides the season's type",
                )
                touched += 1
            except Exception:  # noqa: BLE001 — one salon never blocks the pass
                logger.warning(
                    "kingdom: conscription gate failed (%s, guild %s)", key, gid, exc_info=True
                )
    return touched


__all__ = ["run_conscription_gate_pass"]
