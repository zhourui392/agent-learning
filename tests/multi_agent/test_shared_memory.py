"""Tests for W7 shared memory consistency."""

from __future__ import annotations

import time
import unittest

from src.multi_agent.shared_memory import SharedMemoryStore, VersionConflictError


class SharedMemoryStoreTestCase(unittest.TestCase):
    """Verify versioned shared memory behavior."""

    def test_write_increments_version(self) -> None:
        store = SharedMemoryStore()
        first = store.write("k1", {"v": 1}, writer_role="planner")
        second = store.write("k1", {"v": 2}, writer_role="executor", expected_version=1)

        self.assertEqual(first.version, 1)
        self.assertEqual(second.version, 2)

    def test_write_raises_on_version_conflict(self) -> None:
        store = SharedMemoryStore()
        store.write("k1", {"v": 1}, writer_role="planner")

        with self.assertRaises(VersionConflictError):
            store.write("k1", {"v": 2}, writer_role="executor", expected_version=0)

    def test_cleanup_expired_removes_key(self) -> None:
        store = SharedMemoryStore()
        store.write("k1", {"v": 1}, writer_role="planner", ttl_seconds=0.01)
        time.sleep(0.02)

        removed = store.cleanup_expired()

        self.assertIn("k1", removed)
        self.assertIsNone(store.read("k1"))


if __name__ == "__main__":
    unittest.main()
