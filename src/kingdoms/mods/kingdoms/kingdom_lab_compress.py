"""Kingdoms mod — lab asset recompression (travaux variant, Drasah 05/11).

The FIRST real « travaux » variant of laboratoire-v2: the assets attached
to the lab renders (lieux illustrations, market banner, crest mosaic) are
recompressed through a pure-stdlib MEDIAN-CUT quantization — 256 palette
colors max, emitted as an indexed PNG (color type 3, per-entry alpha via
tRNS). No new dependency: zlib + struct only, the bot image stays as-is
(the recompression rides ONLY the 🚧 travaux renders — 📜 original keeps
the deployed bytes).

Best-effort by design: any unsupported PNG (interlaced, non-8-bit, …) or
any failure falls back to the ORIGINAL file untouched — the lab never
breaks because the compression declined. Results are cached by content
hash so repeated dispatches are instant.
"""
from __future__ import annotations

import hashlib
import io
import logging
import zlib
from typing import Any

logger = logging.getLogger(__name__)

_PALETTE_SIZE = 256
# Histogram precision BEFORE the median cut (the classic 15-bit trick —
# quantizing the histogram instead of every pixel keeps the cut fast on
# million-pixel art without visible quality loss).
_SHIFT_RGB = 3  # 32 levels per channel
_SHIFT_ALPHA = 4  # 16 alpha levels
_MAX_PIXELS = 12_000_000  # safety net — decline absurdly large images

_cache: dict[str, bytes] = {}

_PNG_SIG = b"\x89PNG\r\n\x1a\n"


def _chunks(data: bytes):
    pos = 8
    size = len(data)
    while pos + 8 <= size:
        length = int.from_bytes(data[pos : pos + 4], "big")
        ctype = data[pos + 4 : pos + 8]
        start = pos + 8
        end = start + length
        if end + 4 > size:
            return
        yield ctype, data[start:end]
        pos = end + 4


def _decode_png(data: bytes) -> tuple[int, int, bytes, int] | None:
    """Decode a PNG into (width, height, RGBA bytes, source bytes-per-pixel).

    Supports 8-bit non-interlaced images (color types 0, 2, 3, 4, 6) —
    enough for the mod's own assets. Returns None for anything else.
    """
    if len(data) < 33 or data[:8] != _PNG_SIG:
        return None
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    depth = data[24]
    color_type = data[25]
    compression = data[26]
    filter_method = data[27]
    interlace = data[28]
    if (
        depth != 8
        or compression != 0
        or filter_method != 0
        or interlace != 0
        or color_type not in (0, 2, 3, 4, 6)
        or width <= 0
        or height <= 0
        or width * height > _MAX_PIXELS
    ):
        return None
    bpp = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
    plte: list[tuple[int, int, int]] = []
    trns: bytes = b""
    idat = bytearray()
    for ctype, chunk in _chunks(data):
        if ctype == b"IDAT":
            idat += chunk
        elif ctype == b"PLTE":
            plte = [
                (chunk[i], chunk[i + 1], chunk[i + 2])
                for i in range(0, len(chunk) - len(chunk) % 3, 3)
            ]
        elif ctype == b"tRNS":
            trns = chunk
        elif ctype == b"IEND":
            break
    if not idat:
        return None
    try:
        raw = zlib.decompress(bytes(idat))
    except zlib.error:
        return None
    row_len = width * bpp
    if len(raw) < (row_len + 1) * height:
        return None
    rows: list[bytearray] = []
    prev = bytearray(row_len)
    pos = 0
    for _ in range(height):
        ftype = raw[pos]
        pos += 1
        row = bytearray(raw[pos : pos + row_len])
        pos += row_len
        if ftype == 1:
            for i in range(bpp, row_len):
                row[i] = (row[i] + row[i - bpp]) & 0xFF
        elif ftype == 2:
            for i in range(row_len):
                row[i] = (row[i] + prev[i]) & 0xFF
        elif ftype == 3:
            for i in range(row_len):
                left = row[i - bpp] if i >= bpp else 0
                row[i] = (row[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif ftype == 4:
            for i in range(row_len):
                left = row[i - bpp] if i >= bpp else 0
                up = prev[i]
                ul = prev[i - bpp] if i >= bpp else 0
                p = left + up - ul
                pa = abs(p - left)
                pb = abs(p - up)
                pc = abs(p - ul)
                pred = left if (pa <= pb and pa <= pc) else (up if pb <= pc else ul)
                row[i] = (row[i] + pred) & 0xFF
        elif ftype != 0:
            return None
        rows.append(row)
        prev = row
    # normalize every supported color type into packed RGBA bytes
    total = width * height
    if color_type == 6:
        out = b"".join(bytes(r) for r in rows)
        return width, height, out, 4
    if color_type == 2:
        out = bytearray(total * 4)
        o = 0
        for row in rows:
            for i in range(0, row_len, 3):
                out[o] = row[i]
                out[o + 1] = row[i + 1]
                out[o + 2] = row[i + 2]
                out[o + 3] = 0xFF
                o += 4
        return width, height, bytes(out), 4
    if color_type == 0:
        out = bytearray(total * 4)
        o = 0
        for row in rows:
            for i in range(row_len):
                out[o] = out[o + 1] = out[o + 2] = row[i]
                out[o + 3] = 0xFF
                o += 4
        return width, height, bytes(out), 4
    if color_type == 4:
        out = bytearray(total * 4)
        o = 0
        for row in rows:
            for i in range(0, row_len, 2):
                out[o] = out[o + 1] = out[o + 2] = row[i]
                out[o + 3] = row[i + 1]
                o += 4
        return width, height, bytes(out), 4
    if color_type == 3:
        if not plte:
            return None
        out = bytearray(total * 4)
        o = 0
        for row in rows:
            for i in range(row_len):
                idx = row[i]
                if idx >= len(plte):
                    return None
                r, g, b = plte[idx]
                out[o], out[o + 1], out[o + 2] = r, g, b
                out[o + 3] = trns[idx] if idx < len(trns) else 0xFF
                o += 4
        return width, height, bytes(out), 4
    return None


def _histogram(rgba: bytes) -> dict[int, list[int]]:
    """Aggregate the pixels into a reduced-color histogram.

    Key layout: (r>>shift)<<15 | (g>>shift)<<10 | (b>>shift)<<5 | a>>shift4
    — each key carries [count, sum_r, sum_g, sum_b, sum_a] (exact sums, so
    the palette means stay precise even on the reduced grid).
    """
    hist: dict[int, list[int]] = {}
    for i in range(0, len(rgba), 4):
        key = (
            ((rgba[i] >> _SHIFT_RGB) << 15)
            | ((rgba[i + 1] >> _SHIFT_RGB) << 10)
            | ((rgba[i + 2] >> _SHIFT_RGB) << 5)
            | (rgba[i + 3] >> _SHIFT_ALPHA)
        )
        entry = hist.get(key)
        if entry is None:
            hist[key] = [1, rgba[i], rgba[i + 1], rgba[i + 2], rgba[i + 3]]
        else:
            entry[0] += 1
            entry[1] += rgba[i]
            entry[2] += rgba[i + 1]
            entry[3] += rgba[i + 2]
            entry[4] += rgba[i + 3]
    return hist


def _bucket_metrics(bucket: list[list[int]]) -> list[int]:
    """[pixel_count, min_r, max_r, min_g, max_g, min_b, max_b, min_a, max_a]."""
    count = 0
    mins = [255, 255, 255, 255]
    maxs = [0, 0, 0, 0]
    for entry in bucket:
        count += entry[0]
        means = (
            entry[1] // entry[0],
            entry[2] // entry[0],
            entry[3] // entry[0],
            entry[4] // entry[0],
        )
        for c in range(4):
            if means[c] < mins[c]:
                mins[c] = means[c]
            if means[c] > maxs[c]:
                maxs[c] = means[c]
    return [count, mins[0], maxs[0], mins[1], maxs[1], mins[2], maxs[2], mins[3], maxs[3]]


def _median_cut(hist: dict[int, list[int]]) -> tuple[list[tuple[int, ...]], dict[int, int]]:
    """Quantize the histogram to ≤256 colors via median cut.

    Returns (palette of (r, g, b, a), key → palette index).
    """
    keys = list(hist.keys())
    buckets: list[list[list[int]]] = [[hist[k] for k in keys]]
    key_to_bucket: dict[int, int] = {k: 0 for k in keys}
    while len(buckets) < _PALETTE_SIZE:
        # split the bucket holding the most pixels (the classic rule)
        best = -1
        best_count = 0
        best_range = 0
        for bi, bucket in enumerate(buckets):
            if len(bucket) < 2:
                continue
            m = _bucket_metrics(bucket)
            rng = max(
                m[2] - m[1],
                m[4] - m[3],
                m[6] - m[5],
                (m[8] - m[7]) // 2,  # alpha carries half the visual weight
            )
            if m[0] > best_count or (m[0] == best_count and rng > best_range):
                best, best_count, best_range = bi, m[0], rng
        if best < 0 or best_count == 0:
            break
        bucket = buckets[best]
        m = _bucket_metrics(bucket)
        ranges = [m[2] - m[1], m[4] - m[3], m[6] - m[5], (m[8] - m[7]) // 2]
        channel = ranges.index(max(ranges))
        bucket.sort(key=lambda e: e[channel + 1] // e[0])
        total = m[0]
        acc = 0
        split = len(bucket) // 2
        for i, entry in enumerate(bucket):
            acc += entry[0]
            if acc * 2 >= total and i + 1 < len(bucket):
                split = i + 1
                break
        left, right = bucket[:split], bucket[split:]
        if not left or not right:
            break
        new_index = len(buckets)
        buckets[best] = left
        buckets.append(right)
        # remap ONLY the keys whose entry physically moved to the new
        # bucket — entry identity (id), not equality (two reduced keys
        # can carry equal [count, sums] lists).
        right_ids = {id(e) for e in right}
        for k, entry in hist.items():
            if key_to_bucket[k] == best and id(entry) in right_ids:
                key_to_bucket[k] = new_index
    palette: list[tuple[int, ...]] = []
    for bucket in buckets:
        count = sum(e[0] for e in bucket)
        palette.append(
            (
                sum(e[1] for e in bucket) // count,
                sum(e[2] for e in bucket) // count,
                sum(e[3] for e in bucket) // count,
                sum(e[4] for e in bucket) // count,
            )
        )
    return palette, key_to_bucket


def _encode_indexed_png(
    width: int, height: int, palette: list[tuple[int, ...]], indices: bytes
) -> bytes:
    """Emit an indexed PNG (color type 3, per-entry alpha via tRNS)."""
    def chunk(ctype: bytes, payload: bytes) -> bytes:
        return (
            len(payload).to_bytes(4, "big")
            + ctype
            + payload
            + zlib.crc32(ctype + payload).to_bytes(4, "big")
        )

    ihdr = (
        width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + b"\x08\x03\x00\x00\x00"  # 8-bit, color type 3, deflate, adaptive, no interlace
    )
    plte = b"".join(bytes((r, g, b)) for (r, g, b, _a) in palette)
    has_alpha = any(a != 0xFF for (_r, _g, _b, a) in palette)
    trns = b"".join(bytes((a,)) for (_r, _g, _b, a) in palette) if has_alpha else b""
    stride = width
    scanlines = bytearray()
    for row in range(height):
        scanlines.append(0)  # filter 0 — palette indices are already smooth
        scanlines += indices[row * stride : row * stride + stride]
    idat = zlib.compress(bytes(scanlines), 9)
    out = bytearray(_PNG_SIG)
    out += chunk(b"IHDR", ihdr)
    out += chunk(b"PLTE", plte)
    if trns:
        out += chunk(b"tRNS", trns)
    out += chunk(b"IDAT", idat)
    out += chunk(b"IEND", b"")
    return bytes(out)


def compress_png_bytes(data: bytes) -> bytes | None:
    """Recompress PNG bytes via median-cut 256 — None on decline/failure.

    Declines (returns None) when the input is not a supported PNG or when
    the recompressed output would not be strictly smaller.
    """
    if not data or data[:8] != _PNG_SIG:
        return None
    digest = hashlib.md5(data).hexdigest()  # noqa: S324 — cache key, not security
    cached = _cache.get(digest)
    if cached is not None:
        return cached
    try:
        decoded = _decode_png(data)
        if decoded is None:
            return None
        width, height, rgba, _bpp = decoded
        hist = _histogram(rgba)
        palette, key_to_bucket = _median_cut(hist)
        # map every pixel through its histogram key (fast dict path)
        shift = _SHIFT_RGB
        ashift = _SHIFT_ALPHA
        indices = bytearray(width * height)
        pos = 0
        for i in range(0, len(rgba), 4):
            key = (
                ((rgba[i] >> shift) << 15)
                | ((rgba[i + 1] >> shift) << 10)
                | ((rgba[i + 2] >> shift) << 5)
                | (rgba[i + 3] >> ashift)
            )
            indices[pos] = key_to_bucket[key]
            pos += 1
        out = _encode_indexed_png(width, height, palette, bytes(indices))
        if len(out) >= len(data):
            return None
        _cache[digest] = out
        return out
    except Exception:
        logger.warning("KINGDOM LAB: travaux png compression failed", exc_info=True)
        return None


def compressed_size(path) -> int | None:
    """Cached compressed size of an on-disk PNG (None if declined)."""
    try:
        from pathlib import Path

        data = Path(path).read_bytes()
    except Exception:
        return None
    out = compress_png_bytes(data)
    return len(out) if out is not None else None


def compress_discord_file(file: Any) -> Any:
    """Return a discord.File carrying the RECOMPRESSED bytes of ``file``.

    Falls back to the original file (bytes untouched) on any decline —
    the lab render never breaks because the compression declined.
    """
    try:
        fp = getattr(file, "fp", None)
        if fp is None:
            return file
        try:
            fp.seek(0)
        except Exception:
            return file
        data = fp.read()
        compressed = compress_png_bytes(data)
        if compressed is None:
            fp.seek(0)
            return file
        import discord

        return discord.File(
            io.BytesIO(compressed),
            filename=getattr(file, "filename", "asset.png"),
            spoiler=getattr(file, "spoiler", False),
        )
    except Exception:
        logger.warning("KINGDOM LAB: travaux file compression failed", exc_info=True)
        return file
