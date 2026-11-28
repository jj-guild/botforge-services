"""Kingdom mod — the 🪶 Volière service (voliere-v2 port, Drasah 14/10/2026).

One volière per kingdom, developed for free from the Âge Féodal. SLOTS
BY AGE (v2, Drasah's live-test rulings): Féodal opens the 1st slot,
Château the 2nd, Impérial the 3rd — each slot takes ONE bird, and a
bird already owned can never be re-taken. ONE action and the WHOLE
bird flies: no other action of that bird is possible until the
action's cooldown elapses (the cooldowns stay SHARED by the whole
kingdom, any lord may act).

- **Corbeau** : voler un ⚙️ à une banque adverse (72h — exécution 1h
  après l'envoi), vérifier une déclaration d'attaque (24h — le Corbeau
  perce TOUJOURS la couverture du contre-espionnage), cibler un
  seigneur (48h — « suivi » : toute déclaration du seigneur part avec
  le délai 24h pendant 24h).
- **Faucon** : piocher un territoire parmi les cartes pas encore
  tirées (96h), sabotage en rencontre compté dans la limite 2 du pick
  & ban (48h), Lâcher de faucon (168h — 24h d'immunité à tout effet
  technologique adverse).
- **Pigeon** : piocher une civilisation (72h), question anonyme (1h),
  MP anonyme à un royaume (1h).

voliere-beta-v1 (Drasah 07/11) : sous une bêta ARMÉE ET DÉMARRÉE, la
volière s'ouvre dès la première heure de la saison avec les TROIS
oiseaux — la porte Féodal et l'échelle des âges sont court-circuitées
toute la vie de la bêta.

voliere-beta-5min (Drasah 28/11) : sous cette MÊME bêta live, TOUS les
délais de la volière se compriment à 5 MINUTES — cooldowns d'action,
délai d'exécution du vol, fenêtre de suivi du Corbeau et fenêtre
d'immunité du Faucon. L'état bêta se relit en LIVE à CHAQUE appel (une
saison normale lancée après une bêta récupère ses heures configurées
toute seule, jamais un drapeau persisté).
"""

from __future__ import annotations

import logging
import random
from datetime import datetime
from typing import Any

from botforge.mods.kingdom import chronicle
from botforge.mods.kingdom.admin_debug import bypass_guard
from botforge.mods.kingdom.beta_weekend import beta_started
from botforge.mods.kingdom.errors import KingdomError
from botforge.mods.kingdom.game_clock import game_now
from botforge.mods.kingdom.models import KingdomModel

logger = logging.getLogger("kingdom.voliere")

FEUDAL_AGE_KEY = "feudal_age"
"""The volière unlocks at the Âge Féodal (voliere-v1)."""

CORBEAU_ACTIONS = ("corbeau_civ", "corbeau_verify", "corbeau_track")
FAUCON_ACTIONS = ("faucon_territory", "faucon_sabotage", "faucon_release")
PIGEON_ACTIONS = ("pigeon_civ", "pigeon_question", "pigeon_dm")
BIRDS = ("corbeau", "faucon", "pigeon")
"""The three volière birds (voliere-v2: one per age slot, no repeats)."""

BETA_COMPRESSED_SECONDS = 5 * 60
"""voliere-beta-5min (Drasah 28/11): every volière delay in a live beta."""


def bird_of(action: str) -> str:
    """Return the bird owning one action (``corbeau_civ`` → corbeau)."""
    return str(action).split("_", 1)[0]


class VoliereError(KingdomError):
    """Base of the volière errors (voliere-v1)."""

    code = "KINGDOM_VOLIERE_ERROR"


class VoliereLockedError(VoliereError):
    """Raised when the season is not yet at the Âge Féodal."""

    code = "KINGDOM_VOLIERE_LOCKED"


class VoliereCooldownError(VoliereError):
    """Raised when the kingdom's shared cooldown is still running."""

    code = "KINGDOM_VOLIERE_COOLDOWN"


class VolierePoolEmptyError(VoliereError):
    """Raised when the draw pool has nothing left (civs or maps)."""

    code = "KINGDOM_VOLIERE_POOL_EMPTY"


class VoliereTargetError(VoliereError):
    """Raised on an invalid action target (attack, lord, civ)."""

    code = "KINGDOM_VOLIERE_TARGET"


class VoliereTheftError(VoliereError):
    """Raised on a corbeau ⚙️ theft rule violation (corbeau-v3)."""

    code = "KINGDOM_VOLIERE_THEFT"


class VoliereService:
    """The volière domain logic — cooldowns, draws and effects."""

    def __init__(
        self,
        store: Any,
        config: Any,
        kingdoms: Any,
        territories: Any,
        attacks: Any,
    ) -> None:
        self._store = store
        self._config = config
        self._kingdoms = kingdoms
        self._territories = territories
        self._attacks = attacks
        self._rng = random.Random()  # noqa: S311 - game draw, not crypto

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    @property
    def settings(self) -> Any:
        """The volière settings (cooldowns in hours)."""
        return self._config.voliere

    async def _require_kingdom(self, kingdom_id: str) -> KingdomModel:
        kingdoms = await self._kingdoms.kingdoms()
        kingdom = next((k for k in kingdoms if str(k.id) == str(kingdom_id)), None)
        if kingdom is None or getattr(kingdom, "is_gaia", False):
            raise VoliereTargetError("the kingdom does not exist")
        return kingdom

    async def _save(self, kingdom: KingdomModel) -> None:
        await self._store.upsert_kingdom(kingdom.to_mongo())

    async def _beta_armed(self, now: datetime) -> bool:
        """Whether the LIVE season runs an armed, started beta.

        voliere-beta-5min: the compression reads the live state at
        EVERY call — a normal season launched after a beta recovers
        the configured hours by itself.
        """
        season = await self._kingdoms.current_season()
        if season is None:
            return False
        try:
            return bool(beta_started(season, now))
        except Exception:  # noqa: BLE001
            logger.warning("kingdom volière: beta state read failed", exc_info=True)
            return False

    def _cooldown_seconds(self, action: str, beta: bool) -> int:
        """The action's bird cooldown in SECONDS (5 min in a live beta)."""
        if beta:
            return int(BETA_COMPRESSED_SECONDS)
        return int(getattr(self.settings, f"{action}_cooldown_hours")) * 3600

    def _ready_at(self, kingdom: KingdomModel, bird: str) -> int:
        """Return the unix timestamp the BIRD lands at (v2: whole bird)."""
        return int((kingdom.voliere_cooldowns or {}).get(bird, 0) or 0)

    async def cooldown_ready_at(self, kingdom_id: str, action: str) -> int:
        """Return the unix timestamp the action's bird lands at (admin/view)."""
        kingdom = await self._require_kingdom(kingdom_id)
        return self._ready_at(kingdom, bird_of(action))

    def _check_cooldown(self, kingdom: KingdomModel, action: str, now: datetime) -> None:
        ready_at = self._ready_at(kingdom, bird_of(action))
        if ready_at > int(now.timestamp()) and not bypass_guard(
            f"voliere cooldown {bird_of(action)} of {kingdom.name} (ready in "
            f"{ready_at - int(now.timestamp())}s)"
        ):
            raise VoliereCooldownError(
                "the bird is still flying — no other action until it lands"
            )

    async def _spend(self, kingdom: KingdomModel, action: str, now: datetime) -> None:
        """Fly the WHOLE bird for the action's cooldown (voliere-v2)."""
        self._check_cooldown(kingdom, action, now)
        beta = await self._beta_armed(now)
        cooldowns = dict(kingdom.voliere_cooldowns or {})
        cooldowns[bird_of(action)] = int(now.timestamp()) + self._cooldown_seconds(
            action, beta
        )
        kingdom.voliere_cooldowns = cooldowns
        await self._save(kingdom)

    def _require_bird(self, kingdom: KingdomModel, action: str) -> None:
        """Refuse the action when its bird is not in the volière (v2 slots)."""
        bird = bird_of(action)
        if bird not in (kingdom.voliere_slots or []) and not bypass_guard(
            f"voliere slot {bird} of {kingdom.name}"
        ):
            raise VoliereLockedError(
                f"the {bird} is not in the kingdom's volière (slot to choose)"
            )

    async def _require_feudal(self, now: datetime) -> None:
        """Refuse every volière action before the Âge Féodal."""
        season = await self._kingdoms.current_season()
        if season is None:
            if not bypass_guard("voliere feudal gate (no season)"):
                raise VoliereLockedError("no season is running")
            return
        # voliere-beta-v1 (Drasah 07/11): under an ARMED, STARTED beta the
        # volière opens at the season's very first hour — the Féodal gate
        # is bypassed so every bird flow is testable at once. A beta armed
        # but still ahead of T0 keeps the normal gate: the compressed life
        # applies at T0, exactly like the preset (beta-weekend-v2).
        if await self._beta_armed(now):
            return
        age_keys = [age.key for age in self._config.ages]
        if FEUDAL_AGE_KEY not in age_keys:
            if not bypass_guard("voliere feudal gate (no Âge Féodal declared)"):
                raise VoliereLockedError("the season declares no Âge Féodal")
            return
        if age_keys.index(str(season.current_age_key)) < age_keys.index(FEUDAL_AGE_KEY):
            if not bypass_guard(f"voliere feudal gate (age {season.current_age_key})"):
                raise VoliereLockedError("the season is not yet at the Âge Féodal")

    # ------------------------------------------------------------------
    # Slots by age (voliere-v2, Drasah's live-test rulings)
    # ------------------------------------------------------------------

    def _age_index(self, age_key: str) -> int:
        """Return the age's position in the configured ladder (-1 unknown)."""
        age_keys = [age.key for age in self._config.ages]
        return age_keys.index(age_key) if age_key in age_keys else -1

    def slot_capacity(self, age_key: str) -> int:
        """Return the open slot count at one age (0 before the Féodal).

        Féodal = 1 slot, Château = 2, Impérial = 3 (v2): each age switch
        opens ONE new slot — never more birds than the ladder allows.
        """
        start = self._age_index(FEUDAL_AGE_KEY)
        if start < 0:
            return 0
        return max(0, min(len(BIRDS), self._age_index(age_key) - start + 1))

    async def _capacity_for(self, season: Any, now: datetime) -> int:
        """The open slot count at the season's age — ALL THREE birds in beta.

        voliere-beta-v1 (Drasah 07/11): a STARTED beta opens every slot
        from the season's start (the three birds at once, before any age
        switch); a normal season follows the age ladder untouched. The
        bypass reads the LIVE beta state (never a persisted flag).
        """
        if await self._beta_armed(now):
            return len(BIRDS)
        return self.slot_capacity(str(season.current_age_key))

    async def slot_state(self, kingdom_id: str) -> dict[str, Any]:
        """Return the volière slot snapshot (capacity, chosen, open, birds)."""
        season = await self._kingdoms.current_season()
        if season is None:
            raise VoliereLockedError("no season is running")
        kingdom = await self._require_kingdom(kingdom_id)
        capacity = await self._capacity_for(season, game_now())
        chosen = [str(bird) for bird in (kingdom.voliere_slots or [])]
        age_keys = [age.key for age in self._config.ages]
        next_age = ""
        if capacity < len(BIRDS):
            next_index = self._age_index(FEUDAL_AGE_KEY) + capacity
            if 0 <= next_index < len(age_keys):
                next_age = str(age_keys[next_index])
        return {
            "capacity": capacity,
            "chosen": chosen,
            "open": max(0, capacity - len(chosen)),
            "available": [bird for bird in BIRDS if bird not in chosen],
            "age": str(season.current_age_key),
            "locked": capacity == 0,
            "next_age": next_age,
            "cooldowns": {bird: self._ready_at(kingdom, bird) for bird in BIRDS},
        }

    async def choose_bird(self, kingdom_id: str, bird: str, *, now: datetime) -> str:
        """Fill one open slot with a bird (v2: never an owned bird twice).

        The slot count follows the age (Féodal 1, Château 2, Impérial 3);
        the choice order belongs to the players.
        """
        await self._require_feudal(now)
        kingdom = await self._require_kingdom(kingdom_id)
        season = await self._kingdoms.current_season()
        if season is None:  # pragma: no cover — _require_feudal guarantees one
            raise VoliereLockedError("no season is running")
        chosen = [str(entry) for entry in (kingdom.voliere_slots or [])]
        capacity = await self._capacity_for(season, now)
        if len(chosen) >= capacity:
            raise VoliereLockedError("no volière slot is open at this age")
        if bird not in BIRDS:
            raise VoliereTargetError("unknown bird")
        if bird in chosen:
            raise VoliereTargetError("the bird is already in the volière")
        chosen.append(bird)
        kingdom.voliere_slots = chosen
        await self._save(kingdom)
        logger.info("kingdom volière: %s chose the bird %s", kingdom_id, bird)
        return bird

    async def spend_action(self, kingdom_id: str, action: str, *, now: datetime) -> None:
        """Gate then fly one panel-side action's bird (v2: question, MP).

        The Pigeon's question and anonymous MP live in the panel (modals),
        but they must obey the SAME gates as every service action: Âge
        Féodal, bird in a slot, and the whole-bird cooldown.
        """
        await self._require_feudal(now)
        kingdom = await self._require_kingdom(kingdom_id)
        self._require_bird(kingdom, action)
        await self._spend(kingdom, action, now)

    # ------------------------------------------------------------------
    # Draws (Corbeau civ, Faucon territory, Pigeon civ)
    # ------------------------------------------------------------------

    async def _married_civs(self) -> set[str]:
        lords = await self._kingdoms.lords()
        return {
            str(lord.married_civilization)
            for lord in lords
            if lord.married_civilization is not None and not lord.left
        }

    async def pick_civilization(self, kingdom_id: str, action: str, *, now: datetime) -> str:
        """Draw one NEW civilization for the kingdom (Drasah's ruling).

        The draw covers the WHOLE catalog except the kingdom's hand and
        the married civilizations (exclusivité D74 conservée).
        """
        await self._require_feudal(now)
        kingdom = await self._require_kingdom(kingdom_id)
        self._require_bird(kingdom, action)
        await self._spend(kingdom, action, now)
        hand = {str(civ) for civ in kingdom.civilizations}
        married = await self._married_civs()
        pool = [
            civ.key
            for civ in self._config.civilizations
            if civ.key not in hand and civ.key not in married
        ]
        if not pool:
            raise VolierePoolEmptyError("no civilization is drawable")
        drawn = self._rng.choice(pool)
        civilizations = list(kingdom.civilizations)
        civilizations.append(drawn)
        kingdom.civilizations = civilizations
        await self._save(kingdom)
        logger.info("kingdom volière: %s drew the civilization %s", kingdom_id, drawn)
        return drawn

    async def pick_territory(self, kingdom_id: str, *, now: datetime) -> str:
        """Draw one not-yet-in-game map as a NEW territory for the kingdom."""
        await self._require_feudal(now)
        kingdom = await self._require_kingdom(kingdom_id)
        self._require_bird(kingdom, "faucon_territory")
        await self._spend(kingdom, "faucon_territory", now)
        territories = await self._territories.territories()
        drawn_keys = {str(territory.map_key) for territory in territories}
        pool = [entry.key for entry in self._config.maps if entry.key not in drawn_keys]
        if not pool:
            raise VolierePoolEmptyError("no map is drawable")
        map_key = self._rng.choice(pool)
        await self._territories.draw_map_for(kingdom_id, map_key)
        logger.info("kingdom volière: %s drew the territory %s", kingdom_id, map_key)
        return map_key

    # ------------------------------------------------------------------
    # Corbeau
    # ------------------------------------------------------------------

    async def verify_attack(self, kingdom_id: str, attack_id: str, *, now: datetime) -> str:
        """Reveal the REAL attacker of one attack against the kingdom.

        The Corbeau ALWAYS pierces the contre-espionnage cover (Drasah's
        arbitration): the returned name is the true attacker, cover or
        not. Returns the attacker's display name (corbeau-v3: the full
        inspection — name, lord, map and the attacker's 3 civilizations —
        lives in :meth:`inspect_attack`; this stays the str seam).
        """
        inspection = await self.inspect_attack(kingdom_id, attack_id, now=now)
        logger.info("kingdom volière: %s verified the attack %s", kingdom_id, attack_id)
        return str(inspection["attacker_name"])

    async def inspect_attack(
        self, kingdom_id: str, attack_id: str, *, now: datetime
    ) -> dict[str, Any]:
        """Inspect one attack against the kingdom (corbeau-v3 asymmetry).

        Drasah's inversion (15/10): the ATTACKER reveals their 3
        civilizations FIRST — the defender then sets their own picks
        AFTER the verification, with the attacker's hand known. The
        cover is always pierced (Drasah's arbitration).
        """
        await self._require_feudal(now)
        kingdom = await self._require_kingdom(kingdom_id)
        self._require_bird(kingdom, "corbeau_verify")
        await self._spend(kingdom, "corbeau_verify", now)
        attack = next(
            (a for a in await self._attacks.attacks() if str(a.id) == str(attack_id)),
            None,
        )
        if attack is None or str(attack.defender_kingdom_id) != str(kingdom_id):
            raise VoliereTargetError("the attack does not target the kingdom")
        lords = await self._kingdoms.lords()
        attacker = next(
            (lord for lord in lords if str(lord.id) == str(attack.attacker_lord_id)),
            None,
        )
        attacker_kingdom = next(
            (
                k
                for k in await self._kingdoms.kingdoms()
                if str(k.id) == str(attack.attacker_kingdom_id)
            ),
            None,
        )
        name = str(attacker.display_name) if attacker is not None else str(attack.attacker_lord_id)
        return {
            "attacker_name": name,
            "attacker_lord_id": str(attack.attacker_lord_id),
            "map_key": str(attack.map_key),
            "attacker_civs": [
                str(civ) for civ in (attacker_kingdom.civilizations if attacker_kingdom else [])
            ],
        }

    async def track_lord(self, kingdom_id: str, target_lord_id: str, *, now: datetime) -> int:
        """Mark one lord « suivi » — delayed attack declarations.

        The tracking window follows the config (24h) — FIVE MINUTES
        under an armed, started beta (voliere-beta-5min, Drasah 28/11).
        """
        await self._require_feudal(now)
        kingdom = await self._require_kingdom(kingdom_id)
        self._require_bird(kingdom, "corbeau_track")
        await self._spend(kingdom, "corbeau_track", now)
        lords = await self._kingdoms.lords()
        target = next((lord for lord in lords if str(lord.id) == str(target_lord_id)), None)
        if (
            target is None
            or target.left
            or str(target.kingdom_id) == str(kingdom_id)
        ):
            raise VoliereTargetError("the target is not a trackable lord")
        window = (
            int(BETA_COMPRESSED_SECONDS)
            if await self._beta_armed(now)
            else int(self.settings.corbeau_track_window_hours) * 3600
        )
        until = int(now.timestamp()) + window
        tracking = [
            entry
            for entry in (kingdom.corbeau_tracking or [])
            if str(entry.get("lord_id")) != str(target_lord_id)
        ]
        tracking.append({"lord_id": str(target_lord_id), "until": until})
        kingdom.corbeau_tracking = tracking
        await self._save(kingdom)
        logger.info("kingdom volière: %s tracks the lord %s", kingdom_id, target_lord_id)
        return until

    # ------------------------------------------------------------------
    # Corbeau — vol de points technologiques (corbeau-v3, Drasah 15/10)
    # ------------------------------------------------------------------

    THEFT_ACTIVE_STATES = ("pending", "awaiting_continue", "continuing")

    async def send_corbeau_theft(
        self,
        kingdom_id: str,
        target_kingdom_id: str,
        lord_id: str,
        *,
        now: datetime,
    ) -> dict[str, Any]:
        """Send the Corbeau to steal ⚙️ from a target kingdom's bank.

        The action executes ``corbeau_theft_delay_hours`` AFTER the send
        (FIVE MINUTES under an armed, started beta — voliere-beta-5min):
        nothing is stolen yet — the alarm, the contest window and the
        thief's « Continuer ? » prompt all open at execution. ONE theft
        at a time per kingdom; the whole-bird cooldown flies at the send.
        """
        await self._require_feudal(now)
        kingdom = await self._require_kingdom(kingdom_id)
        self._require_bird(kingdom, "corbeau_civ")
        if str(kingdom_id) == str(target_kingdom_id):
            raise VoliereTargetError("a kingdom cannot steal from itself")
        target = await self._require_kingdom(target_kingdom_id)
        active = kingdom.corbeau_theft
        if active is not None and str(active.get("state")) in self.THEFT_ACTIVE_STATES:
            raise VoliereTheftError("a corbeau theft is already running for this kingdom")
        await self._spend(kingdom, "corbeau_civ", now)
        delay = (
            int(BETA_COMPRESSED_SECONDS)
            if await self._beta_armed(now)
            else int(self.settings.corbeau_theft_delay_hours) * 3600
        )
        execute_at = int(now.timestamp()) + delay
        theft = {
            "id": f"theft-{kingdom_id}-{execute_at}",
            "thief_kingdom_id": str(kingdom_id),
            "thief_lord_id": str(lord_id),
            "target_kingdom_id": str(target_kingdom_id),
            "target_kingdom_name": str(target.name),
            "execute_at": execute_at,
            "contest_until": 0,
            "state": "pending",
            "stolen": 0,
        }
        kingdom.corbeau_theft = theft
        await self._save(kingdom)
        await self._record_theft_milestone(
            str(lord_id), chronicle.KIND_CORBEAU_THEFT, now, target=str(target.name)
        )
        logger.info(
            "kingdom volière: %s sent the corbeau to steal from %s (executes %s)",
            kingdom_id,
            target_kingdom_id,
            execute_at,
        )
        return dict(theft)

    async def resolve_due_thefts(self, *, now: datetime) -> list[dict[str, Any]]:
        """Advance every due theft (events-loop tick, idempotent per tick).

        - a ``pending`` theft past ``execute_at`` steals the 1st ⚙️ from
          the target bank (ALL that remains when the bank holds less
          than 2 — a bank at 0 settles the theft with nothing and NO
          continue prompt), opens the contest window and the thief's
          « Continuer ? » prompt — the returned list carries the thefts
          the loop must ALARM about;
        - an ``awaiting_continue`` window past ``contest_until`` settles
          the thief's safe 1st ⚙️ (no answer = auto-repart, Drasah);
        - a ``continuing`` window past ``contest_until`` settles BOTH ⚙️.
        """
        executed: list[dict[str, Any]] = []
        timestamp = int(now.timestamp())
        contest_seconds = int(self.settings.corbeau_theft_contest_minutes) * 60
        for kingdom in await self._kingdoms.kingdoms():
            theft = kingdom.corbeau_theft
            if theft is None:
                continue
            state = str(theft.get("state"))
            if state == "pending" and int(theft.get("execute_at", 0) or 0) <= timestamp:
                target = await self._require_kingdom(str(theft.get("target_kingdom_id")))
                stolen = self._transfer_bank_point(kingdom, target, 1)
                theft = dict(theft)
                theft["stolen"] = stolen
                if stolen > 0:
                    theft["state"] = "awaiting_continue"
                    theft["contest_until"] = timestamp + contest_seconds
                    executed.append(dict(theft))
                else:
                    theft["state"] = "settled_first"
                kingdom.corbeau_theft = theft
                await self._save_both(kingdom, target)
                await self._record_theft_milestone(
                    str(theft.get("thief_lord_id")),
                    chronicle.KIND_CORBEAU_THEFT,
                    now,
                    target=str(theft.get("target_kingdom_name")),
                    state=theft["state"],
                    points=str(stolen),
                )
            elif state == "awaiting_continue" and int(
                theft.get("contest_until", 0) or 0
            ) <= timestamp:
                theft = dict(theft)
                theft["state"] = "settled_first"
                kingdom.corbeau_theft = theft
                await self._save(kingdom)
                await self._record_theft_milestone(
                    str(theft.get("thief_lord_id")),
                    chronicle.KIND_CORBEAU_THEFT_STOP,
                    now,
                    target=str(theft.get("target_kingdom_name")),
                    points=str(theft.get("stolen", 0)),
                )
            elif state == "continuing" and int(
                theft.get("contest_until", 0) or 0
            ) <= timestamp:
                # The 2nd ⚙️ was ALREADY stolen at the CONTINUER click —
                # the window closing without a contest just settles BOTH.
                theft = dict(theft)
                theft["state"] = "settled_both"
                kingdom.corbeau_theft = theft
                await self._save(kingdom)
                await self._record_theft_milestone(
                    str(theft.get("thief_lord_id")),
                    chronicle.KIND_CORBEAU_THEFT,
                    now,
                    target=str(theft.get("target_kingdom_name")),
                    state="settled_both",
                    points=str(theft["stolen"]),
                )
        return executed

    async def continue_theft(
        self, theft_id: str, kingdom_id: str, go_on: bool, *, now: datetime
    ) -> dict[str, Any]:
        """Answer the thief's « Souhaitez-vous continuer ? » prompt.

        STOP → the thief keeps the 1st ⚙️ SAFE (nothing to contest
        anymore). CONTINUER → the Corbeau goes for the 2nd ⚙️: RISKY —
        a contest inside the window kills the Corbeau and refunds
        EVERYTHING (even the 1st ⚙️); no contest and the thief leaves
        with BOTH (settled at the window's close).
        """
        kingdom = await self._require_kingdom(kingdom_id)
        theft = self._require_theft(kingdom, theft_id, states=("awaiting_continue",))
        timestamp = int(now.timestamp())
        if int(theft.get("contest_until", 0) or 0) <= timestamp:
            raise VoliereTheftError("the contest window is already closed")
        theft = dict(theft)
        if not go_on:
            theft["state"] = "settled_first"
            kingdom.corbeau_theft = theft
            await self._save(kingdom)
            await self._record_theft_milestone(
                str(theft.get("thief_lord_id")),
                chronicle.KIND_CORBEAU_THEFT_STOP,
                now,
                target=str(theft.get("target_kingdom_name")),
                points=str(theft.get("stolen", 0)),
            )
            return dict(theft)
        target = await self._require_kingdom(str(theft.get("target_kingdom_id")))
        theft["stolen"] = int(theft.get("stolen", 0)) + self._transfer_bank_point(
            kingdom, target, 1
        )
        theft["state"] = "continuing"
        kingdom.corbeau_theft = theft
        await self._save_both(kingdom, target)
        await self._record_theft_milestone(
            str(theft.get("thief_lord_id")),
            chronicle.KIND_CORBEAU_THEFT,
            now,
            target=str(theft.get("target_kingdom_name")),
            state="continuing",
            points=str(theft["stolen"]),
        )
        return dict(theft)

    async def contest_theft(self, theft_id: str, kingdom_id: str, *, now: datetime) -> dict[str, Any]:
        """CONTEST a theft from the robbed kingdom (the contest window).

        Success = the Corbeau DIES, EVERYTHING is refunded to the
        robbed bank (even the 1st ⚙️) and the thief kingdom loses its
        Corbeau SLOT (buyable again at the next Âge, voliere-v2 rule).
        """
        kingdom = await self._require_kingdom(kingdom_id)
        kingdoms = await self._kingdoms.kingdoms()
        thief_kingdom = next(
            (
                k
                for k in kingdoms
                if k.corbeau_theft is not None
                and str(k.corbeau_theft.get("id")) == theft_id
            ),
            None,
        )
        if thief_kingdom is None:
            raise VoliereTheftError("no such corbeau theft")
        theft = self._require_theft(
            thief_kingdom, theft_id, states=("awaiting_continue", "continuing")
        )
        if str(theft.get("target_kingdom_id")) != str(kingdom_id):
            raise VoliereTargetError("only the robbed kingdom can contest")
        timestamp = int(now.timestamp())
        if int(theft.get("contest_until", 0) or 0) <= timestamp:
            raise VoliereTheftError("the contest window is already closed")
        stolen = int(theft.get("stolen", 0))
        if stolen > 0:
            thief_kingdom.tech_points_bank = max(0, int(thief_kingdom.tech_points_bank) - stolen)
        thief_kingdom.voliere_slots = [
            bird for bird in thief_kingdom.voliere_slots if bird != "corbeau"
        ]
        dead = dict(thief_kingdom.corbeau_theft or {})
        dead["state"] = "dead"
        thief_kingdom.corbeau_theft = dead
        await self._save(thief_kingdom)
        await self._record_theft_milestone(
            str(dead.get("thief_lord_id")),
            chronicle.KIND_CORBEAU_THEFT_DEAD,
            now,
            target=str(dead.get("target_kingdom_name")),
            points="0",
        )
        kingdom.tech_points_bank = int(kingdom.tech_points_bank) + stolen
        await self._save(kingdom)
        logger.info(
            "kingdom volière: %s contested the theft %s — corbeau dead, %s ⚙️ refunded",
            kingdom_id,
            theft_id,
            stolen,
        )
        result = dict(theft)
        result["state"] = "dead"
        result["refunded"] = stolen
        result["thief_kingdom_name"] = thief_kingdom.name
        return result

    def _require_theft(
        self, kingdom: KingdomModel, theft_id: str, *, states: tuple[str, ...]
    ) -> dict[str, Any]:
        """Return the kingdom's active theft, state-checked."""
        theft = kingdom.corbeau_theft
        if theft is None or str(theft.get("id")) != theft_id:
            raise VoliereTheftError("no such corbeau theft for this kingdom")
        if str(theft.get("state")) not in states:
            raise VoliereTheftError("the theft is not in a contestable/prompted state")
        return dict(theft)

    def _transfer_bank_point(
        self, thief: KingdomModel, target: KingdomModel, amount: int
    ) -> int:
        """Move ⚙️ from the target bank to the thief bank (ALL that remains).

        Returns the amount ACTUALLY moved (a bank below the requested
        amount gives what remains — Drasah: « le Corbeau vole ce qui
        reste »). The caller saves the two sides (:meth:`_save_both`).
        """
        moved = min(max(0, int(amount)), int(target.tech_points_bank))
        if moved > 0:
            target.tech_points_bank = int(target.tech_points_bank) - moved
            thief.tech_points_bank = int(thief.tech_points_bank) + moved
        return moved

    async def _save_both(self, thief: KingdomModel, target: KingdomModel) -> None:
        """Persist a bank transfer's two sides."""
        await self._save(thief)
        await self._save(target)

    async def _record_theft_milestone(
        self, lord_id: str, kind: str, now: datetime, **params: str
    ) -> None:
        """Chronicle one theft milestone on the THIEF lord (best-effort)."""
        lords = await self._kingdoms.lords()
        lord = next((item for item in lords if str(item.id) == str(lord_id)), None)
        if lord is None:
            return
        await chronicle.record(lord, kind, now=now, store=self._store, **params)

    # ------------------------------------------------------------------
    # Faucon
    # ------------------------------------------------------------------

    async def release_faucon(self, kingdom_id: str, *, now: datetime) -> int:
        """Open the Lâcher de faucon — immune to adverse technologies.

        The immunity window follows the config (24h) — FIVE MINUTES
        under an armed, started beta (voliere-beta-5min, Drasah 28/11).
        """
        await self._require_feudal(now)
        kingdom = await self._require_kingdom(kingdom_id)
        self._require_bird(kingdom, "faucon_release")
        await self._spend(kingdom, "faucon_release", now)
        window = (
            int(BETA_COMPRESSED_SECONDS)
            if await self._beta_armed(now)
            else int(self.settings.faucon_release_window_hours) * 3600
        )
        until = int(now.timestamp()) + window
        kingdom.faucon_release_until = until
        await self._save(kingdom)
        logger.info("kingdom volière: %s released the faucon", kingdom_id)
        return until

    async def faucon_sabotage(
        self, kingdom_id: str, attack_id: str, civ_key: str, *, now: datetime
    ) -> None:
        """Place a Faucon sabotage on an ongoing attack (pick & ban phase).

        Same effect as a pick & ban sabotage — it counts in the
        adversary-side 2-limit (no 3rd sabotage, Drasah's ruling).
        """
        await self._require_feudal(now)
        kingdom = await self._require_kingdom(kingdom_id)
        self._require_bird(kingdom, "faucon_sabotage")
        await self._spend(kingdom, "faucon_sabotage", now)
        attack = next(
            (a for a in await self._attacks.attacks() if str(a.id) == str(attack_id)),
            None,
        )
        if attack is None:
            raise VoliereTargetError("the attack does not exist")
        if str(kingdom_id) not in (
            str(attack.attacker_kingdom_id),
            str(attack.defender_kingdom_id),
        ):
            raise VoliereTargetError("the kingdom is not part of the attack")
        pickban = dict(attack.pickban or {})
        # Drasah 18/10 v3: the Faucon also strikes from the battle room
        # (phase Sabotage du vocal) — the meeting state is a valid window.
        in_draft = bool(pickban.get("sent")) and not bool(pickban.get("resolved_pickban"))
        in_room = str(getattr(attack, "state", "")) == "meeting"
        # Drasah 18/10 v4: the post-draft SabotagePhase (DMs, before the
        # battle room) is a valid Faucon window too.
        in_sabotage = bool(pickban.get("resolved_pickban")) and not bool(
            pickban.get("room_revealed")
        )
        if not in_draft and not in_room and not in_sabotage:
            if not bool(pickban.get("sent")):
                raise VoliereTargetError("the pick & ban phase is not running")
            raise VoliereTargetError("the pick & ban phase is over")
        side = "attacker" if str(kingdom_id) == str(attack.attacker_kingdom_id) else "defender"
        sabotages = list(pickban.get(f"{side}_sabotages") or [])
        if len(sabotages) >= 2:
            raise VoliereTargetError("the sabotage limit (2) is already reached")
        if civ_key not in sabotages:
            sabotages.append(civ_key)
        pickban[f"{side}_sabotages"] = sabotages
        attack.pickban = pickban
        await self._store.upsert_attack(attack.to_mongo())
        logger.info(
            "kingdom volière: %s sabotaged %s on the attack %s",
            kingdom_id,
            civ_key,
            attack_id,
        )

    # ------------------------------------------------------------------
    # Effect queries (attacks.py / economy.py hooks)
    # ------------------------------------------------------------------

    async def is_lord_tracked(self, lord_id: str, now: datetime) -> bool:
        """Whether any kingdom currently « suit » this lord."""
        kingdoms = await self._kingdoms.kingdoms()
        timestamp = int(now.timestamp())
        for kingdom in kingdoms:
            for entry in kingdom.corbeau_tracking or []:
                if (
                    str(entry.get("lord_id")) == str(lord_id)
                    and int(entry.get("until", 0) or 0) > timestamp
                ):
                    return True
        return False

    async def has_faucon_release(self, kingdom_id: str, now: datetime) -> bool:
        """Whether the kingdom runs an active Lâcher de faucon."""
        kingdoms = await self._kingdoms.kingdoms()
        kingdom = next((k for k in kingdoms if str(k.id) == str(kingdom_id)), None)
        if kingdom is None:
            return False
        until = int(getattr(kingdom, "faucon_release_until", 0) or 0)
        return until > int(now.timestamp())


__all__ = [
    "BETA_COMPRESSED_SECONDS",
    "BIRDS",
    "CORBEAU_ACTIONS",
    "FAUCON_ACTIONS",
    "FEUDAL_AGE_KEY",
    "PIGEON_ACTIONS",
    "VoliereCooldownError",
    "VoliereError",
    "VoliereLockedError",
    "VolierePoolEmptyError",
    "VoliereService",
    "VoliereTargetError",
    "VoliereTheftError",
    "bird_of",
]
