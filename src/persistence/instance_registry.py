"""Instance registry -- track live instances via heartbeat."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class InstanceInfo:
    """One registered instance."""

    instance_id: str
    hostname: str
    started_at: float
    last_heartbeat: float
    status: str


class InstanceRegistry:
    """Register, heartbeat, and detect expired instances.

    Parameters
    ----------
    conn : sqlite3.Connection
        SQLite connection with schema already initialised.
    heartbeat_ttl : float
        Seconds after last heartbeat before an instance is considered expired.
    """

    def __init__(self, conn: sqlite3.Connection, heartbeat_ttl: float = 30.0) -> None:
        self._conn = conn
        self._heartbeat_ttl = heartbeat_ttl

    def register(self, instance_id: str, hostname: str = "") -> InstanceInfo:
        """Register a new instance (or re-register an existing one)."""
        now = time.time()
        self._conn.execute(
            "INSERT OR REPLACE INTO instances "
            "(instance_id, hostname, started_at, last_heartbeat, status) "
            "VALUES (?, ?, ?, ?, 'alive')",
            (instance_id, hostname, now, now),
        )
        self._conn.commit()
        return InstanceInfo(
            instance_id=instance_id, hostname=hostname,
            started_at=now, last_heartbeat=now, status="alive",
        )

    def heartbeat(self, instance_id: str) -> bool:
        """Update heartbeat timestamp.  Return ``False`` if instance not found."""
        now = time.time()
        cursor = self._conn.execute(
            "UPDATE instances SET last_heartbeat = ?, status = 'alive' WHERE instance_id = ?",
            (now, instance_id),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def get(self, instance_id: str) -> Optional[InstanceInfo]:
        row = self._conn.execute(
            "SELECT instance_id, hostname, started_at, last_heartbeat, status "
            "FROM instances WHERE instance_id = ?",
            (instance_id,),
        ).fetchone()
        return self._row_to_info(row) if row else None

    def list_alive(self) -> List[InstanceInfo]:
        """Return all instances whose last heartbeat is within TTL."""
        cutoff = time.time() - self._heartbeat_ttl
        rows = self._conn.execute(
            "SELECT instance_id, hostname, started_at, last_heartbeat, status "
            "FROM instances WHERE last_heartbeat >= ?",
            (cutoff,),
        ).fetchall()
        return [self._row_to_info(r) for r in rows]

    def detect_expired(self) -> List[InstanceInfo]:
        """Find and mark expired instances.  Return the expired list."""
        cutoff = time.time() - self._heartbeat_ttl
        rows = self._conn.execute(
            "SELECT instance_id, hostname, started_at, last_heartbeat, status "
            "FROM instances WHERE last_heartbeat < ? AND status = 'alive'",
            (cutoff,),
        ).fetchall()

        expired = [self._row_to_info(r) for r in rows]
        if expired:
            ids = [inst.instance_id for inst in expired]
            placeholders = ",".join("?" for _ in ids)
            self._conn.execute(
                f"UPDATE instances SET status = 'expired' WHERE instance_id IN ({placeholders})",
                ids,
            )
            self._conn.commit()
        return expired

    def deregister(self, instance_id: str) -> bool:
        cursor = self._conn.execute("DELETE FROM instances WHERE instance_id = ?", (instance_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    @staticmethod
    def _row_to_info(row) -> InstanceInfo:
        return InstanceInfo(
            instance_id=row[0], hostname=row[1],
            started_at=row[2], last_heartbeat=row[3], status=row[4],
        )
