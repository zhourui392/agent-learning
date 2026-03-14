"""Unified state tracker -- single view of all persistent subsystems."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional


@dataclass
class SystemStateSnapshot:
    """Counts across all persistent subsystems."""

    shared_memory_keys: int
    circuit_breakers: int
    config_entries: int
    active_sessions: int
    registered_instances: int
    alive_instances: int


class StateTracker:
    """Query aggregated counts from a single SQLite database.

    Parameters
    ----------
    conn : sqlite3.Connection
        Must have schema already initialised.
    heartbeat_ttl : float
        Seconds threshold for considering an instance alive.
    """

    def __init__(self, conn: sqlite3.Connection, heartbeat_ttl: float = 30.0) -> None:
        self._conn = conn
        self._heartbeat_ttl = heartbeat_ttl

    def snapshot(self) -> SystemStateSnapshot:
        """Return current counts for every subsystem."""
        import time

        cutoff = time.time() - self._heartbeat_ttl

        return SystemStateSnapshot(
            shared_memory_keys=self._count("shared_memory"),
            circuit_breakers=self._count("circuit_state"),
            config_entries=self._count("config_entries"),
            active_sessions=self._count_where("sessions", "state IN ('running', 'pending')"),
            registered_instances=self._count("instances"),
            alive_instances=self._count_where("instances", f"last_heartbeat >= {cutoff}"),
        )

    def _count(self, table: str) -> int:
        row = self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        return row[0] if row else 0

    def _count_where(self, table: str, condition: str) -> int:
        row = self._conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {condition}").fetchone()
        return row[0] if row else 0
