"""Tests for DistributedLock implementations."""

from __future__ import annotations

import threading
import time
import unittest

from src.scheduler.in_memory_queue import InMemoryDistributedLock

try:
    from src.scheduler.redis_queue import RedisDistributedLock
    HAS_FAKEREDIS = True
except RuntimeError:
    HAS_FAKEREDIS = False


def _create_locks():
    yield "in_memory", InMemoryDistributedLock()
    if HAS_FAKEREDIS:
        yield "redis", RedisDistributedLock()


class TestDistributedLockContract(unittest.TestCase):

    def _run_for_all(self, test_fn):
        for name, lock in _create_locks():
            with self.subTest(backend=name):
                test_fn(lock)

    def test_acquire_release(self):
        def _test(lock):
            self.assertTrue(lock.acquire("res1", holder_id="h1", ttl=5.0))
            self.assertTrue(lock.is_locked("res1"))
            self.assertTrue(lock.release("res1", holder_id="h1"))
            self.assertFalse(lock.is_locked("res1"))
        self._run_for_all(_test)

    def test_holder_mismatch(self):
        def _test(lock):
            lock.acquire("res2", holder_id="owner", ttl=5.0)
            self.assertFalse(lock.release("res2", holder_id="intruder"))
            self.assertTrue(lock.is_locked("res2"))
            lock.release("res2", holder_id="owner")
        self._run_for_all(_test)

    def test_acquire_timeout(self):
        def _test(lock):
            lock.acquire("res3", holder_id="a", ttl=5.0)
            start = time.monotonic()
            self.assertFalse(lock.acquire("res3", holder_id="b", timeout=0.15))
            elapsed = time.monotonic() - start
            self.assertGreaterEqual(elapsed, 0.1)
            lock.release("res3", holder_id="a")
        self._run_for_all(_test)

    def test_ttl_expiry(self):
        def _test(lock):
            lock.acquire("res4", holder_id="a", ttl=0.15)
            time.sleep(0.25)
            self.assertFalse(lock.is_locked("res4"))
        self._run_for_all(_test)

    def test_concurrent_acquire(self):
        def _test(lock):
            winners = []

            def _try_acquire(holder):
                if lock.acquire("contest", holder_id=holder, timeout=0.1, ttl=2.0):
                    winners.append(holder)

            threads = [threading.Thread(target=_try_acquire, args=(f"h{i}",)) for i in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(len(winners), 1)
            lock.release("contest", holder_id=winners[0])
        self._run_for_all(_test)


if __name__ == "__main__":
    unittest.main()
