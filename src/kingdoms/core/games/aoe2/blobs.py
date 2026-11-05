"""Transition re-export: the blob decoder lives in the shared codecs util.

The Worlds Edge Link blob decoding (base64 + zlib, slotinfo/options)
is a CODEC, consumed by the provider (ext-librematch) and the game
service alike — shared util, never game-module code (rule R1).
"""

from __future__ import annotations

from kingdoms.core.codecs import (  # noqa: F401
    BlobDecodeError,
    decode_blob,
    decode_options,
    decode_slotinfo,
    decompress_blob,
)
