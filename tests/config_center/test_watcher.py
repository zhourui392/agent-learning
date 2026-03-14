"""Tests for config watch/notify mechanism."""

from __future__ import annotations

import pytest

from src.config_center.config_store import ConfigCenter
from src.config_center.models import WatchEvent


@pytest.fixture
def center():
    return ConfigCenter()


class TestWatchNotify:

    def test_watch_fires_on_put(self, center):
        events = []
        center.watch("ns", "k", lambda e: events.append(e))
        center.put("ns", "k", "value")
        assert len(events) == 1
        assert events[0].event_type == "created"
        assert events[0].new_value == "value"

    def test_watch_fires_on_update(self, center):
        center.put("ns", "k", "v1")
        events = []
        center.watch("ns", "k", lambda e: events.append(e))
        center.put("ns", "k", "v2")
        assert len(events) == 1
        assert events[0].event_type == "updated"
        assert events[0].old_value == "v1"
        assert events[0].new_value == "v2"

    def test_watch_fires_on_delete(self, center):
        center.put("ns", "k", "v1")
        events = []
        center.watch("ns", "k", lambda e: events.append(e))
        center.delete("ns", "k")
        assert len(events) == 1
        assert events[0].event_type == "deleted"

    def test_wildcard_watch(self, center):
        events = []
        center.watch("ns", "*", lambda e: events.append(e))
        center.put("ns", "a", 1)
        center.put("ns", "b", 2)
        assert len(events) == 2

    def test_unwatch(self, center):
        events = []
        cb = lambda e: events.append(e)
        center.watch("ns", "k", cb)
        center.put("ns", "k", "v1")
        assert len(events) == 1

        center.unwatch("ns", "k", cb)
        center.put("ns", "k", "v2")
        assert len(events) == 1  # no new event

    def test_version_tracking_in_events(self, center):
        events = []
        center.watch("ns", "k", lambda e: events.append(e))
        center.put("ns", "k", "v1")
        center.put("ns", "k", "v2")

        assert events[0].old_version == 0
        assert events[0].new_version == 1
        assert events[1].old_version == 1
        assert events[1].new_version == 2
