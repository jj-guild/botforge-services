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

import json
import logging
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


def _normalize_slot(slot: Any, index: int) -> dict[str, Any]:
    """Normalize one decoded slot record into the stored projection."""
    if not isinstance(slot, dict):
        return {"slot_index": index}
    profile_info = slot.get("profileInfo") or slot.get("profile_info") or {}
    if not isinstance(profile_info, dict):
        profile_info = {}
    profile_id = slot.get("profile_id") or slot.get("playerId") or profile_info.get("id")
    civ = slot.get("civ") or slot.get("civilization") or slot.get("factionID") or slot.get("faction_id")
    filled = bool(profile_id) or slot.get("filled") is True or slot.get("status") == 3
    return {
        "slot_index": int(slot.get("slot_index") or slot.get("stationID") or index),
        "profile_id": str(profile_id or ""),
        "civ": int(civ) if isinstance(civ, (int, float)) else str(civ or ""),
        "team": int(slot.get("team") or slot.get("teamID") or slot.get("teamid") or 0),
        "filled": filled,
        "slot_kind": _slot_kind(slot, filled),
    }


def _slot_kind(slot: dict[str, Any], filled: bool) -> str:
    """Derive the slot's kind label from the decoded record."""
    if not filled:
        return str(slot.get("slot_kind") or ("closed" if slot.get("status") == 2 else "open"))
    if slot.get("ai") or slot.get("is_ai") or str(slot.get("name", "")).lower().startswith("ai "):
        return "ai"
    return "human"
