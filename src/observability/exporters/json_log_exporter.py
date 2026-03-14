"""JSON Lines log exporter -- writes structured log entries to JSONL files."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, List

from src.observability.exporters.interfaces import LogExporter


class JsonFileLogExporter(LogExporter):
    """Append log entries as JSONL to a file.

    Parameters
    ----------
    output_path:
        Path to the JSONL output file.  Created on first ``export`` call.
    max_buffer:
        Number of entries to buffer before auto-flushing.
    """

    def __init__(self, output_path: str, max_buffer: int = 100) -> None:
        self._path = Path(output_path)
        self._max_buffer = max_buffer
        self._buffer: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def export(self, entries: List[Dict[str, Any]]) -> int:
        with self._lock:
            self._buffer.extend(entries)
            if len(self._buffer) >= self._max_buffer:
                self._flush_locked()
        return len(entries)

    def flush(self) -> None:
        with self._lock:
            self._flush_locked()

    def _flush_locked(self) -> None:
        if not self._buffer:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as fh:
            for entry in self._buffer:
                json.dump(entry, fh, ensure_ascii=False, default=str)
                fh.write("\n")
        self._buffer.clear()
