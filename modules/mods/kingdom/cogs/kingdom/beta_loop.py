"""levier-bêta-v1 (Drasah 22-23/11, Check 140) — the BETA TEST LOOP.

Drasah's decision (22/11, « DECISIONS » #4/#5): a beta season ends BY
ITSELF (the engine's ``end`` slot → ``_apply_season_end`` → verdict +
rewards, phase ``ended``) — and the season that just ended RESTARTS A
FRESH BETA IMMÉDIATEMENT (the continuous test loop). The loop stops
ONLY at the admin's « 🏁 Terminer la saison » (the SAME button ends a
classic and a beta — that gesture resets and the pass below sees
nothing left to relaunch). A classic end never relaunches anything.

The pass rides the platform's own 5-minute tick (``phases.py`` — the
attack refresher loop), best-effort at every level: a broken step is a
log line, never a raise. Extensibility (#369): the relaunch is DATA
(the beta it re-arms is the ended season's own ``beta_name``), never a
hardcoded preset.

The full engine chain mirrors the manual departures exactly (the SAME
seams, no bespoke shortcuts):
1. every shell engaged in the ended season is RELEASED (the season it
   points at is about to be archived — a stale binding would bar the
   re-entry, the release_engagement contract);
2. ``launch()`` archives + wipes + seeds the fresh ``setup`` season
   (Gaïa always);
3. ``_arm_compressed_beta`` re-arms the compressed weekend on the FRESH
   season (the ended season's own beta format);
4. the parcours flag rises per guild (ONE beta — the gate bends);
5. ``start_season()`` reveals and starts;
6. every released shell is RE-SEATED (its kingdom re-created approved,
   Roi + members enrolled, shell re-bound, habitat re-woken) — the
   loop replays the admission's own engine chain (``add_kingdom`` +
   ``enroll_king_awaiting_kingdom`` + ``claim_kingdom`` + ``enroll`` +
   ``engage``), so the SAME seats play the next beta with nobody
   re-postulating by hand;
7. the sas CLOSES (the departure's own rule), the content and the
   conscription gate re-run, the live pins re-render, the Géopolitique
   salon learns it (best-effort).

Idempotence is intrinsic: detection only matches a phase ``ended``
BETA season, and a successful ``launch()`` pivots the phase away — a
crash before the pivot retries cleanly, a crash after it is a setup
season the pass ignores.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("kingdom.beta_loop")

_MOD = "kingdom"


def _state_cache(bot: Any) -> Any | None:
    """The mod's state door, degraded to None (a missing service never bends)."""
    from botforge.core.services.mod_storage import ModStateCache

    state_service = getattr(bot, "state_service", None)
    return ModStateCache(state_service, _MOD) if state_service is not None else None


async def _set_beta_flag(bot: Any, guild_id: str, value: bool) -> None:
    """Raise/lower the parcours flag for one guild (best-effort)."""
    from botforge.core.services.beta import enter_beta, exit_beta

    cache = _state_cache(bot)
    if cache is None:
        return
    if value:
        await enter_beta(cache, str(guild_id), _MOD)
    else:
        await exit_beta(cache, str(guild_id), _MOD)


async def season_running(stack: Any | None) -> bool:
    """Whether a season LIVES (setup or started) — the lever's lock.

    levier-bêta-v1 (Drasah 22/11): the parcours lever is FROZEN while
    anything lives. An ``ended`` season does NOT count (its verdict is
    rendered, it is already history) — the lever may flip between two
    betas of the loop, and « Terminer » may end it for good.
    """
    if stack is None or getattr(stack, "kingdoms", None) is None:
        return False
    try:
        season = await stack.kingdoms.current_season()
    except Exception:  # noqa: BLE001 — an unreadable season never locks
        logger.warning("kingdom: the lever's season read failed", exc_info=True)
        return False
    if season is None or bool(getattr(season, "finished", False)):
        return False
    return str(getattr(season, "phase", "")) in ("setup", "started")


async def _reseat_one(
    stack: Any,
    realms_service: Any,
    guild: Any,
    realm: Any,
) -> Any | None:
    """Re-seat ONE played shell into the fresh season (the admission chain).

    The engine chain of ``validation._accept_season_entry``, replayed
    silently: kingdom re-created approved, the Roi re-claims the
    throne, the members re-enroll, the shell re-binds — the seats never
    change, only the season under them does.
    """
    from botforge.mods.kingdom.models import LordRole

    season = await stack.kingdoms.current_season()
    if season is None:
        return None
    kingdom = await stack.kingdoms.add_kingdom(str(getattr(realm, "name", "?")))
    king_id = str(getattr(realm, "king_id", ""))
    try:
        await stack.kingdoms.enroll_king_awaiting_kingdom(
            king_id, str(getattr(realm, "king_name", "") or king_id)
        )
        await stack.kingdoms.claim_kingdom(king_id, str(kingdom.id))
    except Exception:  # noqa: BLE001 — the Roi may already ride the season
        logger.warning("kingdom: reseat throne claim degraded (%s)", exc_info=True)
    for member_id in getattr(realm, "member_ids", []) or []:
        try:
            await stack.kingdoms.enroll(
                str(member_id),
                str(member_id),
                LordRole.LORD,
                kingdom_name=str(getattr(realm, "name", "?")),
            )
        except Exception:  # noqa: BLE001 — one member never blocks the loop
            logger.warning("kingdom: reseat member enroll degraded", exc_info=True)
    fresh = await realms_service.engage(str(realm.id), str(season.id), str(kingdom.id))
    # the habitat wakes with the FRESH shell (the stale-object lesson)
    if guild is not None:
        try:
            from .realms import deploy_realm_hub, ensure_realm_structure

            ids = await ensure_realm_structure(guild, fresh, dormant=False)
            hub_message = await deploy_realm_hub(guild, fresh, )
            if hub_message:
                ids["hub_message"] = hub_message
            if ids:
                await realms_service.save_habitat(str(fresh.id), ids)
        except Exception:  # noqa: BLE001 — the loop never stops for a habitat
            logger.warning(
                "kingdom: reseat habitat wake failed (%s)", fresh.id, exc_info=True
            )
    return fresh


async def run_beta_loop_safe(bot: Any) -> str | None:
    """The 5-min pass step: NOTHING anymore (affaire 48, Drasah 27/11).

    La bêta ne relance PLUS toute seule : une saison terminée (le
    verdict tombé, le monde figé) attend le clic admin sur le bouton
    « Boucler » du message d'annonce de fin. La relance vit dans
    :func:`relaunch_beta` (le clic), jamais dans la passe.
    """
    return None


async def relaunch_beta(bot: Any, stack: Any) -> str | None:
    """Relaunch a fresh beta season NOW (the « Boucler » click, affaire 48).

    The former loop's own body: release the played shells, launch the
    fresh season, re-arm the ended season's beta format, reopen the
    game, reseat the shells, refresh the surfaces, announce. Returns
    a one-line summary, None when there was nothing to loop. Never raises.
    """
    season = None
    try:
        season = await stack.kingdoms.current_season()
    except Exception:  # noqa: BLE001
        logger.warning("kingdom: beta relaunch season read failed", exc_info=True)
    if season is not None and str(getattr(season, "phase", "")) != "ended":
        return None  # only a CLOSED season can loop
    if season is not None and not getattr(season, "beta_name", None):
        return None  # a CLASSIC end never relaunches (Drasah's asymmetry)
    ended_id = str(getattr(season, "id", "")) if season is not None else ""
    beta_name = str(getattr(season, "beta_name", "")) if season is not None else ""
    logger.info("kingdom: beta relaunch after %s (%s)", ended_id, beta_name)

    # (1) release the played shells BEFORE the archive — a binding to
    # the dying season ids would bar the re-entry
    realms_service = getattr(stack, "realms", None)
    played: list[Any] = []
    if realms_service is not None:
        try:
            played = [
                realm
                for realm in await realms_service.realms()
                if getattr(realm, "engagement", None)
                and not getattr(realm, "archived_at", 0)
            ]
        except Exception:  # noqa: BLE001
            logger.warning("kingdom: beta loop shells read failed", exc_info=True)
        for realm in played:
            try:
                await realms_service.release_engagement(str(realm.id))
            except Exception:  # noqa: BLE001 — one shell never stops the loop
                logger.warning(
                    "kingdom: beta loop release failed (%s)", realm.id, exc_info=True
                )

    # (2) the fresh season — pivot: after this the pass ignores it
    from .settings_panel import _arm_compressed_beta

    new_season = await stack.kingdoms.launch()
    # (3) the ended season's own beta format, re-armed on the FRESH doc
    await _arm_compressed_beta(stack)
    # (5) the game starts now (the loop's own departure)
    await stack.kingdoms.start_season()

    for guild in list(getattr(bot, "guilds", []) or []):
        gid = str(getattr(guild, "id", ""))
        if not gid:
            continue
        # (4) the parcours flag rises — beta rules apply at once
        try:
            await _set_beta_flag(bot, gid, True)
        except Exception:  # noqa: BLE001 — best-effort, the season stands
            logger.warning("kingdom: beta loop flag raise failed", exc_info=True)
        # the sas closes (every departure's own rule)
        try:
            from .regie import set_switch

            await set_switch(bot, gid, "season_entry_open", False)
        except Exception:  # noqa: BLE001
            logger.warning("kingdom: beta loop sas close failed", exc_info=True)
        # (6) the played shells take their seats back
        if realms_service is not None:
            for realm in played:
                try:
                    await _reseat_one(stack, realms_service, guild, realm)
                except Exception:  # noqa: BLE001 — one shell never stops the loop
                    logger.warning(
                        "kingdom: beta loop reseat failed (%s)",
                        getattr(realm, "id", "?"),
                        exc_info=True,
                    )
        # the mirrors and the feeding (the departure's own tail)
        try:
            from botforge.discord.static_pins import refresh_live_pins

            await refresh_live_pins(bot, gid)
        except Exception:  # noqa: BLE001 — the 5-min surface pass heals
            logger.warning("kingdom: beta loop pins refresh failed", exc_info=True)
        try:
            # territory-reveal-v1 (Drasah 23/11) : la passe de 5 min
            # emmène le tirage + les fiches + Gaïa — elle RÉPARE un
            # départ raté (rien ne reste silencieux en bêta).
            from .realm_content import feed_season_surfaces

            await feed_season_surfaces(bot)
        except Exception:  # noqa: BLE001
            logger.warning("kingdom: beta loop content pass failed", exc_info=True)
        try:
            from .conscription_gate import run_conscription_gate_pass

            await run_conscription_gate_pass(bot, gid)
        except Exception:  # noqa: BLE001
            logger.warning("kingdom: beta loop gate pass failed", exc_info=True)
        # the salon learns it (best-effort, never blocking)
        try:
            from .battle import _geopolitics_channel
            from .common import mod_catalog
            from .panel import _guild_locale

            strings = (
                dict(mod_catalog().section("kingdom.beta_loop", await _guild_locale(gid)))
            )
            channel = _geopolitics_channel(guild)
            if channel is not None:
                await channel.send(
                    str(strings["beta_loop_restarted"]).format(
                        name=beta_name, count=len(played)
                    )
                )
        except Exception:  # noqa: BLE001 — a note never stops the loop
            logger.warning("kingdom: beta loop notice failed", exc_info=True)

    summary = (
        f"beta loop relaunched from {ended_id} ({beta_name}), "
        f"{len(played)} realm(s) re-seated, new season {getattr(new_season, 'id', '?')}"
    )
    logger.info("kingdom: %s", summary)
    return summary


__all__ = ["relaunch_beta", "run_beta_loop_safe", "season_running"]
