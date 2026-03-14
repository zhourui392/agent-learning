"""Tests for ConnectionPool implementations."""

from __future__ import annotations

import unittest

from src.persistence.connection_pool import RedisConnectionPool


class TestRedisConnectionPool(unittest.TestCase):

    def test_get_and_release(self):
        pool = RedisConnectionPool(max_connections=3)
        c1 = pool.get_connection()
        self.assertIsNotNone(c1)
        self.assertEqual(pool.pool_size(), 1)
        pool.release_connection(c1)

    def test_reuses_connections(self):
        pool = RedisConnectionPool(max_connections=2)
        c1 = pool.get_connection()
        pool.release_connection(c1)
        c2 = pool.get_connection()
        self.assertIs(c1, c2)

    def test_creates_up_to_max(self):
        pool = RedisConnectionPool(max_connections=3)
        conns = [pool.get_connection() for _ in range(3)]
        self.assertEqual(pool.pool_size(), 3)
        for c in conns:
            pool.release_connection(c)

    def test_close_all(self):
        pool = RedisConnectionPool(max_connections=3)
        c = pool.get_connection()
        pool.release_connection(c)
        pool.close_all()
        self.assertEqual(pool.pool_size(), 0)


if __name__ == "__main__":
    unittest.main()
