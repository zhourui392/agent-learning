"""W9 integration: config center with SQLite backend."""

from __future__ import annotations

import sqlite3

import pytest

from src.config_center.config_store import ConfigCenter
from src.config_center.models import WatchEvent
from src.observability.alert_manager import AlertManager
from src.persistence.schema import SchemaManager
from src.persistence.sqlite_backend import SQLiteConfigBackend
from src.release.ab_router import AbRouter


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    SchemaManager(c).ensure_schema()
    yield c
    c.close()


class TestConfigCenterWithSQLite:

    def test_put_get_with_sqlite(self, conn):
        backend = SQLiteConfigBackend(conn)
        center = ConfigCenter(backend=backend)
        center.put("flags", "dark_mode", True, config_type="feature_flag")

        got = center.get("flags", "dark_mode")
        assert got is not None
        assert got.value is True
        assert got.version == 1

    def test_watch_with_sqlite(self, conn):
        backend = SQLiteConfigBackend(conn)
        center = ConfigCenter(backend=backend)

        events = []
        center.watch("flags", "dark_mode", lambda e: events.append(e))
        center.put("flags", "dark_mode", True)
        center.put("flags", "dark_mode", False)

        assert len(events) == 2
        assert events[0].event_type == "created"
        assert events[1].event_type == "updated"

    def test_history_with_sqlite(self, conn):
        backend = SQLiteConfigBackend(conn)
        center = ConfigCenter(backend=backend)

        center.put("ns", "k", "v1")
        center.put("ns", "k", "v2")
        center.put("ns", "k", "v3")

        h = center.history("ns", "k")
        assert len(h) == 3
        assert [e.version for e in h] == [1, 2, 3]


class TestAlertManagerFromConfigCenter:

    def test_load_rules_from_config(self, conn):
        backend = SQLiteConfigBackend(conn)
        center = ConfigCenter(backend=backend)

        center.put("alert_rules", "custom_rule", {
            "name": "high_error_rate",
            "severity": "P1",
            "metric": "error_rate",
            "threshold": 0.1,
            "comparator": "gt",
            "route": "oncall",
            "description": "Error rate too high",
        }, config_type="alert_rule")

        mgr = AlertManager.from_config_center(center)
        events = mgr.evaluate({"error_rate": 0.5})

        firing = [e for e in events if e.status == "firing"]
        assert len(firing) == 1
        assert firing[0].name == "high_error_rate"


class TestAbRouterFromConfigCenter:

    def test_load_experiments_from_config(self, conn):
        backend = SQLiteConfigBackend(conn)
        center = ConfigCenter(backend=backend)

        center.put("experiments", "exp-1", {
            "experiment_id": "exp-1",
            "default_variant": "control",
            "variants": [
                {"name": "control", "percentage": 90.0},
                {"name": "treatment", "percentage": 10.0},
            ],
            "guardrails": [
                {"metric": "success_rate", "comparator": "lt", "threshold": 0.9},
            ],
        }, config_type="experiment")

        configs = AbRouter.from_config_center(center)
        assert "exp-1" in configs

        router = AbRouter()
        decision = router.route(configs["exp-1"], "user-100")
        assert decision.experiment_id == "exp-1"
