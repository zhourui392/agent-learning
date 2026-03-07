"""
压缩器：对重排后的检索结果执行裁剪、去重与预算分配。

功能：
1. 内容去重：基于内容相似度去除冗余片段
2. 低价值剔除：移除信息密度低的片段
3. 预算裁剪：在 token 预算内选择最优片段集
4. 上下文组装：将片段按逻辑顺序组装为 prompt 片段
"""

import hashlib
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from src.rag.context_budget import ContextBudgetManager
from src.rag.reranker import RerankResult


@dataclass
class CompressedChunk:
    """压缩后的片段"""
    chunk_id: str
    content: str
    token_count: int
    source_id: str
    final_score: float
    kept_reason: str               # 保留原因
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CompressionResult:
    """压缩输出"""
    chunks: List[CompressedChunk]
    total_tokens: int
    budget_limit: int
    dropped_count: int             # 被剔除的片段数
    dropped_reasons: Dict[str, int]  # 剔除原因统计
    latency_ms: float


class Compressor:
    """
    检索结果压缩器

    处理流程：
    1. 去重（基于内容 SimHash 或精确匹配）
    2. 低价值过滤（短文本、纯标点、信息密度低）
    3. 预算裁剪（贪心选择分数最高的片段直到预算耗尽）
    4. 组装输出
    """

    def __init__(
        self,
        budget_manager: Optional[ContextBudgetManager] = None,
        dedup_threshold: float = 0.85,
        min_content_length: int = 20,
        min_info_density: float = 0.3,
    ):
        self.budget_manager = budget_manager or ContextBudgetManager()
        self.dedup_threshold = dedup_threshold
        self.min_content_length = min_content_length
        self.min_info_density = min_info_density

    def compress(
        self,
        rerank_results: List[RerankResult],
        budget_override: Optional[int] = None,
    ) -> CompressionResult:
        """
        对重排结果执行压缩。

        Args:
            rerank_results: 重排后的结果列表（已按分数降序）
            budget_override: 覆盖默认 token 预算

        Returns:
            CompressionResult 压缩后的最终片段集
        """
        start_time = time.time()
        budget = budget_override or self.budget_manager.get_retrieval_budget()
        dropped_reasons: Dict[str, int] = {}

        # 1. 去重
        deduped, dup_count = self._deduplicate(rerank_results)
        if dup_count > 0:
            dropped_reasons["duplicate"] = dup_count

        # 2. 低价值过滤
        filtered = []
        for result in deduped:
            reason = self._check_low_value(result.chunk.content)
            if reason:
                dropped_reasons[reason] = dropped_reasons.get(reason, 0) + 1
            else:
                filtered.append(result)

        # 3. 预算裁剪（贪心）
        selected: List[CompressedChunk] = []
        used_tokens = 0

        for result in filtered:
            token_count = self._estimate_tokens(result.chunk.content)
            if used_tokens + token_count > budget:
                dropped_reasons["over_budget"] = dropped_reasons.get("over_budget", 0) + 1
                continue

            selected.append(CompressedChunk(
                chunk_id=result.chunk.chunk_id,
                content=result.chunk.content,
                token_count=token_count,
                source_id=result.chunk.source_id,
                final_score=result.rerank_score.final_score,
                kept_reason=f"rank={result.new_rank}, score={result.rerank_score.final_score:.3f}",
                metadata=result.chunk.metadata,
            ))
            used_tokens += token_count

        # 更新预算消耗
        self.budget_manager.record_usage("retrieval_context", used_tokens)

        total_input = len(rerank_results)
        dropped_count = total_input - len(selected)
        latency_ms = (time.time() - start_time) * 1000

        return CompressionResult(
            chunks=selected,
            total_tokens=used_tokens,
            budget_limit=budget,
            dropped_count=dropped_count,
            dropped_reasons=dropped_reasons,
            latency_ms=latency_ms,
        )

    def _deduplicate(self, results: List[RerankResult]) -> tuple:
        """
        基于内容指纹去重。

        使用内容 MD5 精确去重 + 简易 Jaccard 近似去重。
        保留分数更高的片段。
        """
        seen_hashes: Set[str] = set()
        seen_token_sets: List[set] = []
        deduped = []
        dup_count = 0

        for result in results:
            content = result.chunk.content.strip()
            content_hash = hashlib.md5(content.encode()).hexdigest()

            # 精确去重
            if content_hash in seen_hashes:
                dup_count += 1
                continue

            # 近似去重（Jaccard 相似度）
            token_set = set(content.lower().split())
            is_near_dup = False
            for existing in seen_token_sets:
                intersection = len(token_set & existing)
                union = len(token_set | existing)
                if union > 0 and intersection / union >= self.dedup_threshold:
                    is_near_dup = True
                    break

            if is_near_dup:
                dup_count += 1
                continue

            seen_hashes.add(content_hash)
            seen_token_sets.append(token_set)
            deduped.append(result)

        return deduped, dup_count

    def _check_low_value(self, content: str) -> Optional[str]:
        """
        检查是否为低价值内容。

        Returns:
            剔除原因字符串，None 表示保留
        """
        content = content.strip()

        # 过短
        if len(content) < self.min_content_length:
            return "too_short"

        # 信息密度低（非字母数字字符占比过高）
        alnum_count = sum(1 for c in content if c.isalnum() or '\u4e00' <= c <= '\u9fff')
        total = len(content)
        if total > 0 and alnum_count / total < self.min_info_density:
            return "low_info_density"

        return None

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """
        估算 token 数。

        简易规则：英文按空格分词约 1 token/word，中文约 1.5 token/字。
        生产环境应使用 tiktoken 精确计算。
        """
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        words = len(text.split())
        return int(chinese_chars * 1.5 + words * 1.3)

    def assemble_context(self, chunks: List[CompressedChunk]) -> str:
        """
        将压缩后的片段组装为 LLM 可用的上下文文本。

        格式：
        [来源: {source_id}]
        {content}
        ---
        """
        parts = []
        for chunk in chunks:
            parts.append(f"[来源: {chunk.source_id}]\n{chunk.content}")
        return "\n---\n".join(parts)
