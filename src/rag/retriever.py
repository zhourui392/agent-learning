"""
双路召回器：向量召回 + 关键词召回，合并去重后返回。

召回流程：
1. 并行执行向量召回与关键词召回
2. 按合并策略（RRF / 加权分数）融合结果
3. 权限过滤
4. 返回 TopK 结果
"""

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from src.rag.keyword_retriever import KeywordRetriever


class MergeStrategy(Enum):
    """召回结果合并策略"""
    RRF = "rrf"                    # Reciprocal Rank Fusion
    WEIGHTED_SCORE = "weighted"    # 加权分数合并


@dataclass
class RetrievalChunk:
    """检索结果片段"""
    chunk_id: str
    content: str
    score: float
    source_id: str
    source_type: str               # doc / api / db
    access_level: str = "public"   # public / internal / restricted
    metadata: Dict[str, Any] = field(default_factory=dict)
    retrieval_source: str = ""     # vector / keyword / merged


@dataclass
class RetrievalResult:
    """召回结果"""
    query: str
    chunks: List[RetrievalChunk]
    total_candidates: int          # 合并去重前总数
    latency_ms: float
    retrieval_sources: Dict[str, int]  # 各路召回贡献数量


class VectorRetriever:
    """
    向量召回器（基于 Embedding 相似度）

    生产环境对接 FAISS / Milvus / Qdrant，
    当前为内存 mock 实现，用于验证链路。
    """

    def __init__(self, top_k: int = 20):
        self.top_k = top_k
        self._index: List[RetrievalChunk] = []

    def add_documents(self, chunks: List[RetrievalChunk]):
        """将文档片段加入向量索引"""
        self._index.extend(chunks)

    def search(self, query: str, top_k: Optional[int] = None) -> List[RetrievalChunk]:
        """
        向量相似度召回。

        Mock 实现：基于 query 与 content 的字符重叠率模拟相似度。
        生产实现：调用向量数据库的 ANN 搜索接口。
        """
        k = top_k or self.top_k
        query_chars = set(query)

        scored = []
        for chunk in self._index:
            content_chars = set(chunk.content)
            overlap = len(query_chars & content_chars)
            union = len(query_chars | content_chars)
            score = overlap / union if union > 0 else 0.0
            scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, chunk in scored[:k]:
            result = RetrievalChunk(
                chunk_id=chunk.chunk_id,
                content=chunk.content,
                score=score,
                source_id=chunk.source_id,
                source_type=chunk.source_type,
                access_level=chunk.access_level,
                metadata=chunk.metadata,
                retrieval_source="vector",
            )
            results.append(result)

        return results


class HybridRetriever:
    """
    双路混合召回器

    功能：
    - 并行执行向量召回与关键词召回
    - 按配置的合并策略融合结果
    - 前置权限过滤，确保不返回越权内容
    - 输出带来源标记的合并结果
    """

    def __init__(
        self,
        vector_retriever: Optional[VectorRetriever] = None,
        keyword_retriever: Optional[KeywordRetriever] = None,
        merge_strategy: MergeStrategy = MergeStrategy.RRF,
        vector_weight: float = 0.6,
        keyword_weight: float = 0.4,
        vector_top_k: int = 20,
        keyword_top_k: int = 20,
        final_top_k: int = 10,
        rrf_k: int = 60,
    ):
        self.vector_retriever = vector_retriever or VectorRetriever(top_k=vector_top_k)
        self.keyword_retriever = keyword_retriever or KeywordRetriever(top_k=keyword_top_k)
        self.merge_strategy = merge_strategy
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight
        self.final_top_k = final_top_k
        self.rrf_k = rrf_k
        self._access_checker: Optional[Callable[[str, str], bool]] = None

    def set_access_checker(self, checker: Callable[[str, str], bool]):
        """
        设置权限检查函数。

        checker(user_role, access_level) -> bool
        返回 True 表示允许访问。
        """
        self._access_checker = checker

    def retrieve(
        self,
        query: str,
        user_role: str = "public",
        top_k: Optional[int] = None,
    ) -> RetrievalResult:
        """
        执行双路召回 + 合并 + 权限过滤。

        Args:
            query: 用户查询文本
            user_role: 用户角色，用于权限过滤
            top_k: 最终返回数量，默认使用 self.final_top_k

        Returns:
            RetrievalResult 包含合并后的检索结果
        """
        start_time = time.time()
        k = top_k or self.final_top_k

        # 1. 并行执行双路召回（当前串行，生产环境可用线程池并行化）
        vector_results = self.vector_retriever.search(query)
        keyword_results = self.keyword_retriever.search(query)

        # 2. 合并结果
        if self.merge_strategy == MergeStrategy.RRF:
            merged = self._merge_rrf(vector_results, keyword_results)
        else:
            merged = self._merge_weighted(vector_results, keyword_results)

        total_candidates = len(merged)

        # 3. 权限过滤
        filtered = self._filter_by_access(merged, user_role)

        # 4. 截取 TopK
        final = filtered[:k]

        # 5. 统计各路召回贡献
        sources = {"vector": 0, "keyword": 0, "both": 0}
        for chunk in final:
            src = chunk.retrieval_source
            if src in sources:
                sources[src] += 1

        latency_ms = (time.time() - start_time) * 1000

        return RetrievalResult(
            query=query,
            chunks=final,
            total_candidates=total_candidates,
            latency_ms=latency_ms,
            retrieval_sources=sources,
        )

    def _merge_rrf(
        self,
        vector_results: List[RetrievalChunk],
        keyword_results: List[RetrievalChunk],
    ) -> List[RetrievalChunk]:
        """
        Reciprocal Rank Fusion 合并。

        RRF(d) = sum( 1 / (k + rank_i(d)) )  对每路召回的排名求和。
        k 默认 60，平滑排名差异。
        """
        rrf_scores: Dict[str, float] = {}
        chunk_map: Dict[str, RetrievalChunk] = {}
        source_map: Dict[str, set] = {}

        for rank, chunk in enumerate(vector_results):
            cid = chunk.chunk_id
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (self.rrf_k + rank + 1)
            chunk_map[cid] = chunk
            source_map.setdefault(cid, set()).add("vector")

        for rank, chunk in enumerate(keyword_results):
            cid = chunk.chunk_id
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (self.rrf_k + rank + 1)
            chunk_map[cid] = chunk
            source_map.setdefault(cid, set()).add("keyword")

        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

        results = []
        for cid in sorted_ids:
            chunk = chunk_map[cid]
            sources = source_map[cid]
            retrieval_source = "both" if len(sources) > 1 else sources.pop()
            results.append(RetrievalChunk(
                chunk_id=chunk.chunk_id,
                content=chunk.content,
                score=rrf_scores[cid],
                source_id=chunk.source_id,
                source_type=chunk.source_type,
                access_level=chunk.access_level,
                metadata=chunk.metadata,
                retrieval_source=retrieval_source,
            ))

        return results

    def _merge_weighted(
        self,
        vector_results: List[RetrievalChunk],
        keyword_results: List[RetrievalChunk],
    ) -> List[RetrievalChunk]:
        """加权分数合并：对每路的原始分数按权重加和。"""
        scores: Dict[str, float] = {}
        chunk_map: Dict[str, RetrievalChunk] = {}
        source_map: Dict[str, set] = {}

        for chunk in vector_results:
            cid = chunk.chunk_id
            scores[cid] = scores.get(cid, 0.0) + chunk.score * self.vector_weight
            chunk_map[cid] = chunk
            source_map.setdefault(cid, set()).add("vector")

        for chunk in keyword_results:
            cid = chunk.chunk_id
            scores[cid] = scores.get(cid, 0.0) + chunk.score * self.keyword_weight
            chunk_map[cid] = chunk
            source_map.setdefault(cid, set()).add("keyword")

        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

        results = []
        for cid in sorted_ids:
            chunk = chunk_map[cid]
            sources = source_map[cid]
            retrieval_source = "both" if len(sources) > 1 else sources.pop()
            results.append(RetrievalChunk(
                chunk_id=chunk.chunk_id,
                content=chunk.content,
                score=scores[cid],
                source_id=chunk.source_id,
                source_type=chunk.source_type,
                access_level=chunk.access_level,
                metadata=chunk.metadata,
                retrieval_source=retrieval_source,
            ))

        return results

    def _filter_by_access(
        self, chunks: List[RetrievalChunk], user_role: str
    ) -> List[RetrievalChunk]:
        """
        权限过滤前置检查。

        规则：
        - public 角色只能访问 public 内容
        - internal 角色可访问 public + internal
        - admin 角色可访问全部
        - 自定义 checker 优先级最高
        """
        if self._access_checker:
            return [c for c in chunks if self._access_checker(user_role, c.access_level)]

        access_hierarchy = {
            "public": {"public"},
            "internal": {"public", "internal"},
            "admin": {"public", "internal", "restricted"},
        }
        allowed = access_hierarchy.get(user_role, {"public"})
        return [c for c in chunks if c.access_level in allowed]
