"""libre:match options/slotinfo decoding — the exploit step (#288, T2).

The raw history documents are stored FIRST (T1); this module decodes
the encoded match fields AFTER the fact, without any re-fetch of the
history: the match-details endpoint answers the ``options`` and
``slotinfo`` blobs for an already-known match id, and the game
module's blob decoder (``botforge.aoe2.codecs``) turns them into the
structured fields — game settings, slots/teams, civs, map.

A decode failure is never fatal: the raw blobs stay stored, the
projection fields stay empty, the sync retries on its next pass.
"""

from __future__ import annotations

import base64
import json
import logging
import re
from typing import Any

from botforge.aoe2.codecs import BlobDecodeError, decode_blob

logger = logging.getLogger("botforge.ext_librematch.decode")

BLOB_FIELDS = ("slotinfo", "options")
DECODE_BATCH = 25


def decode_match_payload(raw: dict[str, Any]) -> tuple[str, str]:
    """Decode one raw match payload's blobs into (options_json, slots_json).

    Empty strings when the payload carries no decodable blob — the
    caller keeps the document, the fields simply stay unexploited.
    """
    options: dict[str, Any] = {}
    slots: list[dict[str, Any]] = []
    for field in BLOB_FIELDS:
        blob = raw.get(field)
        if not isinstance(blob, str) or not blob:
            continue
        try:
            decoded = decode_blob(blob)
        except BlobDecodeError as exc:
            logger.warning("undecodable %s blob (match %s): %s", field, raw.get("id"), exc)
            continue
        if field == "options" and isinstance(decoded, dict):
            options = {str(k): v for k, v in decoded.items() if not str(k).startswith("_")}
        elif field == "slotinfo" and isinstance(decoded, list):
            slots = [_normalize_slot(slot, index) for index, slot in enumerate(decoded)]
    options_json = json.dumps(options, sort_keys=True) if options else ""
    slots_json = json.dumps(slots, sort_keys=True) if slots else ""
    return options_json, slots_json



def _slot_position(slot: dict[str, Any], index: int) -> int:
    """Map one slot to its GAME position (1-8, the P-colors).

    ``stationID`` is the LOBBY's station, NOT the player's position:
    the 2026-11-22 4v4 had JeanJack on station 7 while playing the
    FIRST position (blue). The true position rides the slot's
    ``metaData`` \u2014 a double-base64 TLV whose
    ``ScenarioPlayerIndex`` key (0-7) is the game's own player
    index; verify-live trace: station 7 \u2192 index '0' \u2192 P1.
    The station, then the array order, stay the honest fallbacks.
    """
    player_index = _meta_player_index(slot.get("metaData"))
    if player_index is not None and player_index >= 0:
        return player_index + 1
    for key in ("slot_index", "player_index", "stationID"):
        value = slot.get(key)
        if isinstance(value, (int, float)) and int(value) > 0:
            return int(value)
    return index + 1


def _meta_player_index(meta: Any) -> int | None:
    """Extract ``ScenarioPlayerIndex`` (0-7) from a slot's metaData."""
    if not isinstance(meta, str) or not meta:
        return None
    try:
        inner = base64.b64decode(meta).decode("utf-8", "replace")
        payload = inner[1:-1].encode() if inner.startswith('"') and inner.endswith('"') else inner.encode()
        blob = base64.b64decode(payload)
    except Exception:
        return None
    found = re.search(rb"ScenarioPlayerIndex(.{4})([0-9])", blob, re.S)
    if not found:
        return None
    try:
        return int(found.group(2))
    except ValueError:
        return None


def _normalize_slot(slot: Any, index: int) -> dict[str, Any]:
    """Normalize one decoded slot record into the stored projection.

    The LIVE payload keys are dotted (``profileInfo.id``, verified
    2026-11-20) with ``raceID`` carrying the civilization — the older
    nested ``profileInfo`` shape stays accepted for stored documents.
    """
    if not isinstance(slot, dict):
        return {"slot_index": index}
    profile_info = slot.get("profileInfo") or slot.get("profile_info") or {}
    if not isinstance(profile_info, dict):
        profile_info = {}
    profile_id = (
        slot.get("profile_id")
        or slot.get("playerId")
        or slot.get("profileInfo.id")
        or profile_info.get("id")
    )
    civ = (
        slot.get("civ")
        or slot.get("civilization")
        or slot.get("raceID")
        or slot.get("factionID")
        or slot.get("faction_id")
    )
    # a NEGATIVE profile id is no profile: the WE slotinfo answers
    # ``profileInfo.id: -1`` for a COMPUTER seat (match 518232462,
    # verified live 2026-11-24) - the bare truthiness read the AI as
    # a filled human seat
    try:
        pid = int(profile_id or 0)
    except (TypeError, ValueError):
        pid = 0
    profile_id = str(profile_id or "") if pid > 0 else ""
    filled = (
        pid > 0
        or slot.get("filled") is True
        or slot.get("status") == 3
        or slot.get("isReady") == 1
    )
    return {
        "slot_index": _slot_position(slot, index),
        "profile_id": str(profile_id or ""),
        "civ": int(civ) if isinstance(civ, (int, float)) else str(civ or ""),
        "team": int(slot.get("team") or slot.get("teamID") or slot.get("teamid") or 0),
        "filled": filled,
        "slot_kind": _slot_kind(slot, filled),
    }


def _slot_kind(slot: dict[str, Any], filled: bool) -> str:
    """Derive the slot's kind label from the decoded record.

    A status-2 seat WITHOUT a profile that carries a CIV is a
    COMPUTER (verified live 2026-11-24, match 518232462: the AI rides
    ``status: 2, profileInfo.id: -1, raceID: 40`` while the truly
    closed seats answer ``status: 1, raceID: -1``) - the first rule
    read them all as "closed" and the panels never saw an AI.
    """
    if not filled:
        civ = slot.get("raceID", slot.get("factionID", slot.get("civ")))
        try:
            has_civ = int(civ if civ is not None else -1) >= 0
        except (TypeError, ValueError):
            has_civ = bool(civ) and str(civ) not in ("-1", "", "None")
        if slot.get("status") == 2 and has_civ:
            return "ai"
        return str(slot.get("slot_kind") or ("closed" if slot.get("status") == 2 else "open"))
    if slot.get("ai") or slot.get("is_ai") or str(slot.get("name", "")).lower().startswith("ai "):
        return "ai"
    return "human"
