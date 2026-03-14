"""SQLite implementations of persistence backends.

All four backends share a single ``sqlite3.Connection`` and rely on
``SchemaManager.ensure_schema()`` having been called beforehand.
"""

from __future__ import annotations

import sqlite3
from typing import List, Optional

from src.persistence.interfaces import (
    CircuitRecord,
    CircuitStateBackend,
    ConfigBackend,
    ConfigRecord,
    MemoryRecord,
    SessionRecord,
    SessionStoreBackend,
    SharedMemoryBackend,
)
from src.persistence.serialization import deserialize, serialize


# ---------------------------------------------------------------------------
# SharedMemory
# ---------------------------------------------------------------------------

class SQLiteSharedMemoryBackend(SharedMemoryBackend):

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get(self, key: str) -> Optional[MemoryRecord]:
        row = self._conn.execute(
            "SELECT key, value, version, writer_role, updated_at, expires_at "
            "FROM shared_memory WHERE key = ?",
            (key,),
        ).fetchone()
        return self._row_to_record(row) if row else None

    def put(self, record: MemoryRecord) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO shared_memory "
            "(key, value, version, writer_role, updated_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (record.key, serialize(record.value), record.version,
             record.writer_role, record.updated_at, record.expires_at),
        )
        self._conn.commit()

    def delete(self, key: str) -> bool:
        cursor = self._conn.execute("DELETE FROM shared_memory WHERE key = ?", (key,))
        self._conn.commit()
        return cursor.rowcount > 0

    def list_all(self) -> List[MemoryRecord]:
        rows = self._conn.execute(
            "SELECT key, value, version, writer_role, updated_at, expires_at FROM shared_memory"
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def clear(self) -> None:
        self._conn.execute("DELETE FROM shared_memory")
        self._conn.commit()

    @staticmethod
    def _row_to_record(row) -> MemoryRecord:
        return MemoryRecord(
            key=row[0], value=deserialize(row[1]), version=row[2],
            writer_role=row[3], updated_at=row[4], expires_at=row[5],
        )


# ---------------------------------------------------------------------------
# CircuitState
# ---------------------------------------------------------------------------

class SQLiteCircuitStateBackend(CircuitStateBackend):

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get(self, tool_name: str) -> Optional[CircuitRecord]:
        row = self._conn.execute(
            "SELECT tool_name, state, failure_count, success_count, "
            "half_open_successes, last_failure_time, last_state_change, "
            "total_calls, total_failures, total_rejections "
            "FROM circuit_state WHERE tool_name = ?",
            (tool_name,),
        ).fetchone()
        return self._row_to_record(row) if row else None

    def put(self, record: CircuitRecord) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO circuit_state "
            "(tool_name, state, failure_count, success_count, "
            "half_open_successes, last_failure_time, last_state_change, "
            "total_calls, total_failures, total_rejections) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (record.tool_name, record.state, record.failure_count,
             record.success_count, record.half_open_successes,
             record.last_failure_time, record.last_state_change,
             record.total_calls, record.total_failures, record.total_rejections),
        )
        self._conn.commit()

    def delete(self, tool_name: str) -> bool:
        cursor = self._conn.execute("DELETE FROM circuit_state WHERE tool_name = ?", (tool_name,))
        self._conn.commit()
        return cursor.rowcount > 0

    def list_all(self) -> List[CircuitRecord]:
        rows = self._conn.execute(
            "SELECT tool_name, state, failure_count, success_count, "
            "half_open_successes, last_failure_time, last_state_change, "
            "total_calls, total_failures, total_rejections FROM circuit_state"
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def clear(self) -> None:
        self._conn.execute("DELETE FROM circuit_state")
        self._conn.commit()

    @staticmethod
    def _row_to_record(row) -> CircuitRecord:
        return CircuitRecord(
            tool_name=row[0], state=row[1], failure_count=row[2],
            success_count=row[3], half_open_successes=row[4],
            last_failure_time=row[5], last_state_change=row[6],
            total_calls=row[7], total_failures=row[8], total_rejections=row[9],
        )


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class SQLiteConfigBackend(ConfigBackend):

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get(self, namespace: str, key: str) -> Optional[ConfigRecord]:
        row = self._conn.execute(
            "SELECT namespace, key, value, version, config_type, updated_at, description "
            "FROM config_entries WHERE namespace = ? AND key = ?",
            (namespace, key),
        ).fetchone()
        return self._row_to_record(row) if row else None

    def put(self, record: ConfigRecord) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO config_entries "
            "(namespace, key, value, version, config_type, updated_at, description) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (record.namespace, record.key, serialize(record.value),
             record.version, record.config_type, record.updated_at, record.description),
        )
        self._conn.execute(
            "INSERT INTO config_history "
            "(namespace, key, value, version, config_type, updated_at, description) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (record.namespace, record.key, serialize(record.value),
             record.version, record.config_type, record.updated_at, record.description),
        )
        self._conn.commit()

    def delete(self, namespace: str, key: str) -> bool:
        cursor = self._conn.execute(
            "DELETE FROM config_entries WHERE namespace = ? AND key = ?",
            (namespace, key),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def list_by_namespace(self, namespace: str) -> List[ConfigRecord]:
        rows = self._conn.execute(
            "SELECT namespace, key, value, version, config_type, updated_at, description "
            "FROM config_entries WHERE namespace = ?",
            (namespace,),
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def list_all(self) -> List[ConfigRecord]:
        rows = self._conn.execute(
            "SELECT namespace, key, value, version, config_type, updated_at, description "
            "FROM config_entries"
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def get_history(self, namespace: str, key: str) -> List[ConfigRecord]:
        rows = self._conn.execute(
            "SELECT namespace, key, value, version, config_type, updated_at, description "
            "FROM config_history WHERE namespace = ? AND key = ? ORDER BY id ASC",
            (namespace, key),
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def clear(self) -> None:
        self._conn.execute("DELETE FROM config_entries")
        self._conn.execute("DELETE FROM config_history")
        self._conn.commit()

    @staticmethod
    def _row_to_record(row) -> ConfigRecord:
        return ConfigRecord(
            namespace=row[0], key=row[1], value=deserialize(row[2]),
            version=row[3], config_type=row[4], updated_at=row[5],
            description=row[6],
        )


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

class SQLiteSessionStoreBackend(SessionStoreBackend):

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get(self, session_id: str) -> Optional[SessionRecord]:
        row = self._conn.execute(
            "SELECT session_id, instance_id, state, payload, created_at, updated_at, expires_at "
            "FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return self._row_to_record(row) if row else None

    def put(self, record: SessionRecord) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO sessions "
            "(session_id, instance_id, state, payload, created_at, updated_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (record.session_id, record.instance_id, record.state,
             serialize(record.payload), record.created_at, record.updated_at,
             record.expires_at),
        )
        self._conn.commit()

    def delete(self, session_id: str) -> bool:
        cursor = self._conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    def list_all(self) -> List[SessionRecord]:
        rows = self._conn.execute(
            "SELECT session_id, instance_id, state, payload, created_at, updated_at, expires_at "
            "FROM sessions"
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def list_by_instance(self, instance_id: str) -> List[SessionRecord]:
        rows = self._conn.execute(
            "SELECT session_id, instance_id, state, payload, created_at, updated_at, expires_at "
            "FROM sessions WHERE instance_id = ?",
            (instance_id,),
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def list_by_state(self, state: str) -> List[SessionRecord]:
        rows = self._conn.execute(
            "SELECT session_id, instance_id, state, payload, created_at, updated_at, expires_at "
            "FROM sessions WHERE state = ?",
            (state,),
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def clear(self) -> None:
        self._conn.execute("DELETE FROM sessions")
        self._conn.commit()

    @staticmethod
    def _row_to_record(row) -> SessionRecord:
        return SessionRecord(
            session_id=row[0], instance_id=row[1], state=row[2],
            payload=deserialize(row[3]), created_at=row[4],
            updated_at=row[5], expires_at=row[6],
        )
