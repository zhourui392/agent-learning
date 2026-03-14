"""Tests for ConfigCenter CRUD, versioning, and history."""

from __future__ import annotations

import pytest

from src.config_center.config_store import ConfigCenter


@pytest.fixture
def center():
    return ConfigCenter()


class TestConfigCenterCRUD:

    def test_put_and_get(self, center):
        entry = center.put("experiments", "exp-1", {"variant": "control"}, config_type="experiment")
        assert entry.version == 1
        got = center.get("experiments", "exp-1")
        assert got is not None
        assert got.value == {"variant": "control"}

    def test_put_auto_increments_version(self, center):
        center.put("ns", "k", "v1")
        entry = center.put("ns", "k", "v2")
        assert entry.version == 2

    def test_get_missing_returns_none(self, center):
        assert center.get("ns", "missing") is None

    def test_delete(self, center):
        center.put("ns", "k", "v")
        assert center.delete("ns", "k") is True
        assert center.get("ns", "k") is None

    def test_delete_missing(self, center):
        assert center.delete("ns", "nope") is False

    def test_list_namespace(self, center):
        center.put("ns1", "a", 1)
        center.put("ns1", "b", 2)
        center.put("ns2", "c", 3)
        assert len(center.list_namespace("ns1")) == 2

    def test_list_all(self, center):
        center.put("ns1", "a", 1)
        center.put("ns2", "b", 2)
        assert len(center.list_all()) == 2

    def test_history_ordered(self, center):
        center.put("ns", "k", "v1")
        center.put("ns", "k", "v2")
        center.put("ns", "k", "v3")
        h = center.history("ns", "k")
        assert len(h) == 3
        assert h[0].version == 1
        assert h[2].version == 3

    def test_config_types(self, center):
        for ct in ("experiment", "alert_rule", "tenant_policy", "gateway", "feature_flag"):
            center.put("typed", ct, {"type": ct}, config_type=ct)
        entries = center.list_namespace("typed")
        types = {e.config_type for e in entries}
        assert types == {"experiment", "alert_rule", "tenant_policy", "gateway", "feature_flag"}
