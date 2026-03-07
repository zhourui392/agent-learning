"""
重排器：对召回结果按多维特征重新排序。

重排特征：
1. 相关性分数（来自召回阶段）
2. 时效性（文档新鲜度）
3. 来源可信度（数据源权威程度）

输出带可解释评分字段的排序结果。
"""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.rag.retriever import RetrievalChunk


@dataclass
class RerankScore:
    """可解释的重排评分"""
    relevance_score: float       # 相关性分数 [0, 1]
    freshness_score: float       # 时效性分数 [0, 1]
    authority_score: float       # 来源可信度 [0, 1]
    final_score: float           # 加权最终分数
    explanation: str             # 评分解释


@dataclass
class RerankResult:
    """重排后的单条结果"""
    chunk: RetrievalChunk
    rerank_score: RerankScore
    original_rank: int
    new_rank: int


@dataclass
class RerankOutput:
    """重排输出"""
    results: List[RerankResult]
    latency_ms: float
    config: Dict[str, Any]


@dataclass
class RerankConfig:
    """重排特征权重配置"""
    relevance_weight: float = 0.5
    freshness_weight: float = 0.3
    authority_weight: float = 0.2
    freshness_decay_days: int = 90    # 时效性衰减天数
    top_n: int = 10                    # 重排后保留的 TopN

    # 来源可信度映射
    source_authority: Dict[str, float] = field(default_factory=lambda: {
        "doc": 0.9,          # 官方文档
        "db": 0.8,           # 数据库
        "api": 0.7,          # API 数据
        "user_generated": 0.5,  # 用户生成内容
        "unknown": 0.3,      # 未知来源
    })

    def validate(self):
        """校验权重之和为 1"""
        total = self.relevance_weight + self.freshness_weight + self.authority_weight
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"权重之和必须为 1.0，当前为 {total:.4f}"
            )


class Reranker:
    """
    多特征重排器

    对召回结果执行三维评分：
    - 相关性：归一化原始召回分数
    - 时效性：基于文档更新时间的衰减函数
    - 来源可信度：按数据源类型映射权威分数

    最终分数 = w_rel * relevance + w_fresh * freshness + w_auth * authority
    """

    def __init__(self, config: Optional[RerankConfig] = None):
        self.config = config or RerankConfig()
        self.config.validate()

    def rerank(
        self,
        chunks: List[RetrievalChunk],
        top_n: Optional[int] = None,
    ) -> RerankOutput:
        """
        对召回结果重排。

        Args:
            chunks: 召回阶段返回的片段列表
            top_n: 保留 TopN，默认使用配置值

        Returns:
            RerankOutput 包含排序后的结果与可解释评分
        """
        start_time = time.time()
        n = top_n or self.config.top_n

        if not chunks:
            return RerankOutput(results=[], latency_ms=0.0, config=self._config_dict())

        # 1. 归一化相关性分数
        max_score = max(c.score for c in chunks) or 1.0

        # 2. 计算每个 chunk 的多维分数
        scored_results = []
        for idx, chunk in enumerate(chunks):
            relevance = chunk.score / max_score
            freshness = self._calc_freshness(chunk)
            authority = self._calc_authority(chunk)

            final = (
                self.config.relevance_weight * relevance
                + self.config.freshness_weight * freshness
                + self.config.authority_weight * authority
            )

            explanation = (
                f"relevance={relevance:.3f}(w={self.config.relevance_weight}), "
                f"freshness={freshness:.3f}(w={self.config.freshness_weight}), "
                f"authority={authority:.3f}(w={self.config.authority_weight})"
            )

            scored_results.append(RerankResult(
                chunk=chunk,
                rerank_score=RerankScore(
                    relevance_score=relevance,
                    freshness_score=freshness,
                    authority_score=authority,
                    final_score=final,
                    explanation=explanation,
                ),
                original_rank=idx + 1,
                new_rank=0,  # 排序后填充
            ))

        # 3. 按最终分数排序
        scored_results.sort(key=lambda x: x.rerank_score.final_score, reverse=True)

        # 4. 填充新排名并截取 TopN
        for new_rank, result in enumerate(scored_results):
            result.new_rank = new_rank + 1

        final_results = scored_results[:n]
        latency_ms = (time.time() - start_time) * 1000

        return RerankOutput(
            results=final_results,
            latency_ms=latency_ms,
            config=self._config_dict(),
        )

    def _calc_freshness(self, chunk: RetrievalChunk) -> float:
        """
        时效性评分：基于 updated_at 的指数衰减。

        score = exp(-age_days / decay_days)

        - 今天更新的文档得分接近 1.0
        - decay_days 天前的文档得分约 0.37
        - 无时间信息的文档得分 0.5（中性）
        """
        import math

        updated_at = chunk.metadata.get("updated_at")
        if not updated_at:
            return 0.5

        if isinstance(updated_at, (int, float)):
            age_seconds = time.time() - updated_at
        else:
            return 0.5

        age_days = max(age_seconds / 86400.0, 0)
        return math.exp(-age_days / self.config.freshness_decay_days)

    def _calc_authority(self, chunk: RetrievalChunk) -> float:
        """来源可信度：按 source_type 查表映射"""
        return self.config.source_authority.get(
            chunk.source_type,
            self.config.source_authority.get("unknown", 0.3),
        )

    def _config_dict(self) -> Dict[str, Any]:
        return {
            "relevance_weight": self.config.relevance_weight,
            "freshness_weight": self.config.freshness_weight,
            "authority_weight": self.config.authority_weight,
            "freshness_decay_days": self.config.freshness_decay_days,
            "top_n": self.config.top_n,
        }
