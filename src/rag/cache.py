"""
RAG 多级缓存：query 缓存、片段缓存、结果缓存。

缓存层级：
1. Query 缓存：相同 query 直接返回缓存结果（最快路径）
2. 片段缓存：缓存 Embedding 向量，避免重复计算
3. 结果缓存：缓存最终组装好的上下文文本

降级策略：
- 检索超时时回退到最近缓存
- 向量服务不可用时降级为纯关键词检索
"""

import hashlib
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, TypeVar

T = TypeVar("T")


class CacheStatus(Enum):
    HIT = "hit"
    MISS = "miss"
    EXPIRED = "expired"
    DEGRADED = "degraded"


@dataclass
class CacheEntry(Generic[T]):
    """缓存条目"""
    key: str
    value: T
    created_at: float
    ttl_seconds: float
    hit_count: int = 0

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl_seconds


@dataclass
class CacheStats:
    """缓存统计"""
    total_requests: int = 0
    hits: int = 0
    misses: int = 0
    expirations: int = 0
    evictions: int = 0

    @property
    def hit_rate(self) -> float:
        return self.hits / self.total_requests if self.total_requests > 0 else 0.0


class LRUCache(Generic[T]):
    """
    LRU 缓存（Least Recently Used）

    - 固定容量，满时淘汰最久未访问的条目
    - 每条 entry 有独立 TTL
    - 线程安全需调用方保证（生产环境加锁）
    """

    def __init__(self, max_size: int = 1000, default_ttl: float = 300.0):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._store: OrderedDict[str, CacheEntry[T]] = OrderedDict()
        self.stats = CacheStats()

    def get(self, key: str) -> tuple:
        """
        查询缓存。

        Returns:
            (value_or_None, CacheStatus)
        """
        self.stats.total_requests += 1

        if key not in self._store:
            self.stats.misses += 1
            return None, CacheStatus.MISS

        entry = self._store[key]

        if entry.is_expired:
            del self._store[key]
            self.stats.expirations += 1
            return None, CacheStatus.EXPIRED

        # 移到末尾（最近访问）
        self._store.move_to_end(key)
        entry.hit_count += 1
        self.stats.hits += 1
        return entry.value, CacheStatus.HIT

    def put(self, key: str, value: T, ttl: Optional[float] = None):
        """写入缓存"""
        if key in self._store:
            del self._store[key]

        # 淘汰
        while len(self._store) >= self.max_size:
            evicted_key, _ = self._store.popitem(last=False)
            self.stats.evictions += 1

        self._store[key] = CacheEntry(
            key=key,
            value=value,
            created_at=time.time(),
            ttl_seconds=ttl or self.default_ttl,
        )

    def invalidate(self, key: str) -> bool:
        """使指定 key 失效"""
        if key in self._store:
            del self._store[key]
            return True
        return False

    def invalidate_by_prefix(self, prefix: str) -> int:
        """使指定前缀的所有 key 失效"""
        keys_to_remove = [k for k in self._store if k.startswith(prefix)]
        for k in keys_to_remove:
            del self._store[k]
        return len(keys_to_remove)

    def clear(self):
        """清空缓存"""
        self._store.clear()

    @property
    def size(self) -> int:
        return len(self._store)


class RAGCache:
    """
    RAG 多级缓存管理器

    三级缓存：
    - query_cache: query 文本 -> 最终检索结果
    - embedding_cache: chunk_id -> embedding 向量
    - context_cache: query hash -> 组装后的上下文文本
    """

    def __init__(
        self,
        query_cache_size: int = 500,
        query_cache_ttl: float = 300.0,       # 5 分钟
        embedding_cache_size: int = 5000,
        embedding_cache_ttl: float = 3600.0,  # 1 小时
        context_cache_size: int = 200,
        context_cache_ttl: float = 600.0,     # 10 分钟
    ):
        self.query_cache: LRUCache = LRUCache(query_cache_size, query_cache_ttl)
        self.embedding_cache: LRUCache = LRUCache(embedding_cache_size, embedding_cache_ttl)
        self.context_cache: LRUCache = LRUCache(context_cache_size, context_cache_ttl)

    @staticmethod
    def _query_key(query: str, user_role: str = "public") -> str:
        """生成 query 缓存 key（含用户角色，防止越权缓存）"""
        raw = f"{query.strip().lower()}|{user_role}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def get_query_result(self, query: str, user_role: str = "public"):
        """查询 query 缓存"""
        key = self._query_key(query, user_role)
        return self.query_cache.get(key)

    def put_query_result(self, query: str, result: Any, user_role: str = "public"):
        """写入 query 缓存"""
        key = self._query_key(query, user_role)
        self.query_cache.put(key, result)

    def get_embedding(self, chunk_id: str):
        """查询 embedding 缓存"""
        return self.embedding_cache.get(chunk_id)

    def put_embedding(self, chunk_id: str, embedding: List[float]):
        """写入 embedding 缓存"""
        self.embedding_cache.put(chunk_id, embedding)

    def get_context(self, query: str, user_role: str = "public"):
        """查询组装后的上下文缓存"""
        key = f"ctx_{self._query_key(query, user_role)}"
        return self.context_cache.get(key)

    def put_context(self, query: str, context: str, user_role: str = "public"):
        """写入上下文缓存"""
        key = f"ctx_{self._query_key(query, user_role)}"
        self.context_cache.put(key, context)

    def invalidate_source(self, source_id: str):
        """当数据源更新时，清除相关缓存"""
        # query 和 context 缓存全量清除（保守策略）
        self.query_cache.clear()
        self.context_cache.clear()
        # embedding 缓存按前缀清除
        self.embedding_cache.invalidate_by_prefix(source_id)

    def stats_summary(self) -> Dict[str, Any]:
        """缓存统计摘要"""
        return {
            "query_cache": {
                "size": self.query_cache.size,
                "hit_rate": f"{self.query_cache.stats.hit_rate:.2%}",
                "hits": self.query_cache.stats.hits,
                "misses": self.query_cache.stats.misses,
            },
            "embedding_cache": {
                "size": self.embedding_cache.size,
                "hit_rate": f"{self.embedding_cache.stats.hit_rate:.2%}",
            },
            "context_cache": {
                "size": self.context_cache.size,
                "hit_rate": f"{self.context_cache.stats.hit_rate:.2%}",
            },
        }


class DegradePolicy:
    """
    检索降级策略

    降级触发条件：
    1. 检索超时（超过 timeout_ms）
    2. 向量服务不可用
    3. 全部召回路均失败

    降级行为：
    - 优先返回最近缓存结果
    - 无缓存时返回空结果 + 降级标记
    """

    def __init__(
        self,
        timeout_ms: float = 3000.0,
        cache: Optional[RAGCache] = None,
    ):
        self.timeout_ms = timeout_ms
        self.cache = cache or RAGCache()

    def should_degrade(self, elapsed_ms: float, error: Optional[Exception] = None) -> bool:
        """判断是否需要降级"""
        if error is not None:
            return True
        return elapsed_ms > self.timeout_ms

    def get_fallback(self, query: str, user_role: str = "public") -> tuple:
        """
        获取降级结果。

        优先从缓存取，无缓存返回空。

        Returns:
            (result_or_None, is_from_cache: bool)
        """
        # 尝试 query 缓存
        result, status = self.cache.get_query_result(query, user_role)
        if result is not None:
            return result, True

        # 尝试 context 缓存
        context, status = self.cache.get_context(query, user_role)
        if context is not None:
            return context, True

        return None, False
