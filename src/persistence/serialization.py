"""JSON serialization helpers for SQLite value columns."""

from __future__ import annotations

import json
from typing import Any


def serialize(value: Any) -> str:
    """Serialize a Python value to a JSON string for SQLite storage."""
    return json.dumps(value, ensure_ascii=False, default=str)


def deserialize(raw: str) -> Any:
    """Deserialize a JSON string from SQLite back to a Python value."""
    if raw is None:
        return None
    return json.loads(raw)
