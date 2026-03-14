"""Tests for instance registry."""

from __future__ import annotations

import sqlite3
import time

import pytest

from src.persistence.instance_registry import InstanceRegistry
from src.persistence.schema import SchemaManager


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    SchemaManager(c).ensure_schema()
    yield c
    c.close()


class TestInstanceRegistry:

    def test_register_and_get(self, conn):
        reg = InstanceRegistry(conn)
        info = reg.register("inst-1", hostname="host-a")
        assert info.instance_id == "inst-1"
        assert info.status == "alive"

        got = reg.get("inst-1")
        assert got is not None
        assert got.hostname == "host-a"

    def test_heartbeat(self, conn):
        reg = InstanceRegistry(conn)
        reg.register("inst-1")
        before = reg.get("inst-1").last_heartbeat

        time.sleep(0.01)
        assert reg.heartbeat("inst-1") is True
        after = reg.get("inst-1").last_heartbeat
        assert after > before

    def test_heartbeat_missing(self, conn):
        reg = InstanceRegistry(conn)
        assert reg.heartbeat("no-such") is False

    def test_detect_expired(self, conn):
        reg = InstanceRegistry(conn, heartbeat_ttl=0.01)
        reg.register("inst-1")
        time.sleep(0.02)

        expired = reg.detect_expired()
        assert len(expired) == 1
        assert expired[0].instance_id == "inst-1"

        got = reg.get("inst-1")
        assert got.status == "expired"

    def test_list_alive(self, conn):
        reg = InstanceRegistry(conn, heartbeat_ttl=0.01)
        reg.register("inst-1")
        reg.register("inst-2")
        time.sleep(0.02)
        reg.heartbeat("inst-2")

        alive = reg.list_alive()
        assert len(alive) == 1
        assert alive[0].instance_id == "inst-2"

    def test_deregister(self, conn):
        reg = InstanceRegistry(conn)
        reg.register("inst-1")
        assert reg.deregister("inst-1") is True
        assert reg.get("inst-1") is None
