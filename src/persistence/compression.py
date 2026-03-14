"""Compressed serialization utilities for persistence values."""

from __future__ import annotations

import json
import zlib
from typing import Any

# First byte marker to distinguish compressed from plain JSON.
_COMPRESSED_MARKER = b"\x01"
_PLAIN_MARKER = b"\x00"


def serialize_compressed(value: Any, threshold: int = 1024) -> bytes:
    """Serialize *value* to JSON bytes, compressing if above *threshold*."""
    raw = json.dumps(value, ensure_ascii=False, default=str).encode("utf-8")
    if len(raw) >= threshold:
        return _COMPRESSED_MARKER + zlib.compress(raw)
    return _PLAIN_MARKER + raw


def deserialize_compressed(data: bytes) -> Any:
    """Deserialize bytes produced by :func:`serialize_compressed`."""
    if not data:
        return None
    marker = data[:1]
    payload = data[1:]
    if marker == _COMPRESSED_MARKER:
        return json.loads(zlib.decompress(payload).decode("utf-8"))
    return json.loads(payload.decode("utf-8"))
