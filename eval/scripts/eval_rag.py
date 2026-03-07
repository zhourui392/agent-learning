"""
RAG 离线评测脚本

评测指标：
- Recall@K: 召回阶段是否包含期望的 source_id
- MRR (Mean Reciprocal Rank): 首个正确结果的排名倒数
- Answer-F1: 生成答案与期望答案的 token 级 F1
- Latency: 检索链路端到端延迟

用法：
    python -m eval.scripts.eval_rag [--dataset eval/datasets/rag_v1.jsonl] [--output eval/reports/]
"""

import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# 添加项目根目录到 path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.rag.retriever import HybridRetriever, RetrievalChunk, VectorRetriever
from src.rag.keyword_retriever import KeywordRetriever, IndexedChunk
from src.rag.reranker import Reranker, RerankConfig
from src.rag.compressor import Compressor
from src.rag.context_budget import ContextBudgetManager


@dataclass
class EvalSample:
    """评测样本"""
    id: str
    category: str
    query: str
    expected_answer: str
    relevant_source_ids: List[str]
    difficulty: str


@dataclass
class EvalMetrics:
    """单样本评测结果"""
    sample_id: str
    recall_at_5: float
    recall_at_10: float
    mrr: float
    answer_f1: float
    latency_ms: float
    retrieved_source_ids: List[str]
    num_chunks_after_compress: int


@dataclass
class EvalReport:
    """评测报告"""
    dataset_name: str
    total_samples: int
    avg_recall_at_5: float
    avg_recall_at_10: float
    avg_mrr: float
    avg_answer_f1: float
    avg_latency_ms: float
    p95_latency_ms: float
    by_category: Dict[str, Dict[str, float]]
    by_difficulty: Dict[str, Dict[str, float]]
    details: List[EvalMetrics]


def load_dataset(path: str) -> List[EvalSample]:
    """加载 JSONL 格式的评测数据集"""
    samples = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            samples.append(EvalSample(**data))
    return samples


def tokenize_for_f1(text: str) -> List[str]:
    """将文本分词用于 F1 计算"""
    text = text.lower().strip()
    tokens = re.findall(r"[\w\u4e00-\u9fff]+", text)
    return tokens


def compute_f1(predicted: str, expected: str) -> float:
    """计算 token 级 F1 分数"""
    pred_tokens = tokenize_for_f1(predicted)
    exp_tokens = tokenize_for_f1(expected)

    if not pred_tokens or not exp_tokens:
        return 0.0

    pred_set = set(pred_tokens)
    exp_set = set(exp_tokens)

    common = pred_set & exp_set
    if not common:
        return 0.0

    precision = len(common) / len(pred_set)
    recall = len(common) / len(exp_set)
    f1 = 2 * precision * recall / (precision + recall)
    return f1


def compute_recall_at_k(
    retrieved_source_ids: List[str],
    relevant_source_ids: List[str],
    k: int,
) -> float:
    """计算 Recall@K"""
    if not relevant_source_ids:
        return 1.0  # 无期望来源时视为满分

    retrieved_set = set(retrieved_source_ids[:k])
    relevant_set = set(relevant_source_ids)
    return len(retrieved_set & relevant_set) / len(relevant_set)


def compute_mrr(
    retrieved_source_ids: List[str],
    relevant_source_ids: List[str],
) -> float:
    """计算 MRR (Mean Reciprocal Rank)"""
    if not relevant_source_ids:
        return 1.0

    relevant_set = set(relevant_source_ids)
    for rank, source_id in enumerate(retrieved_source_ids):
        if source_id in relevant_set:
            return 1.0 / (rank + 1)
    return 0.0


def build_mock_index(retriever: HybridRetriever):
    """
    构建 mock 索引数据，模拟真实知识库。

    生产环境替换为真实索引加载。
    """
    mock_docs = [
        ("doc_refund_policy", "doc", "退款政策规定退款有效期为30天，超过30天不予退款。用户需在购买后30天内提出退款申请。"),
        ("doc_merchant_onboard", "doc", "商户入驻需要提供以下资质：营业执照、食品经营许可证、法人身份证。所有证件需在有效期内。"),
        ("doc_coupon_rules", "doc", "优惠券规则：单张优惠券最大面额为500元。每日领券上限为10张。默认不允许叠加使用，除非活动明确标注支持叠加。"),
        ("doc_verification", "doc", "核销流程说明：核销超时时间为30分钟，超过30分钟未完成核销将自动取消。"),
        ("doc_settlement", "doc", "商户结算提现流程：进入商户端，点击财务管理，选择提现申请，填写金额，提交审核，1到3个工作日到账。"),
        ("doc_complaint", "doc", "用户投诉处理流程：用户提交投诉后，客服48小时内响应，进行调查核实，给出处理方案，用户确认后关闭工单。"),
        ("doc_activity_approval", "doc", "新活动上线审批流程：运营创建活动，主管审批，风控审核，技术确认，灰度发布，全量上线。"),
        ("doc_merchant_freeze", "doc", "商户被冻结后已核销的订单正常结算，冻结期间新订单暂停核销。解冻后恢复正常。"),
        ("doc_system_arch", "doc", "系统架构采用消息队列异步处理，升级期间订单会暂存队列，升级完成后自动补处理。Redis原子扣减保障库存不超发。"),
        ("doc_merchant_rating", "doc", "商户评分低于3分将触发预警，连续两周低于3分将暂停推荐位展示，连续四周将启动商户约谈。"),
        ("doc_merchant_manage", "doc", "商户管理制度包含评分预警、约谈、暂停合作三个等级。评分由用户评价、投诉率、核销成功率综合计算。"),
    ]

    chunks = []
    indexed_chunks = []
    for source_id, source_type, content in mock_docs:
        chunk = RetrievalChunk(
            chunk_id=f"{source_id}_chunk_0",
            content=content,
            score=0.0,
            source_id=source_id,
            source_type=source_type,
            access_level="public",
            metadata={"updated_at": time.time()},
        )
        chunks.append(chunk)

        indexed_chunks.append(IndexedChunk(
            chunk_id=f"{source_id}_chunk_0",
            content=content,
            source_id=source_id,
            source_type=source_type,
            access_level="public",
            metadata={"updated_at": time.time()},
        ))

    retriever.vector_retriever.add_documents(chunks)
    retriever.keyword_retriever.add_documents(indexed_chunks)


def run_evaluation(dataset_path: str, output_dir: str) -> EvalReport:
    """
    执行完整评测流程。

    1. 加载数据集
    2. 构建检索链路（召回 → 重排 → 压缩）
    3. 逐样本执行并计算指标
    4. 生成报告
    """
    samples = load_dataset(dataset_path)

    # 构建检索链路
    retriever = HybridRetriever(final_top_k=10)
    build_mock_index(retriever)
    reranker = Reranker(RerankConfig(top_n=10))
    budget_mgr = ContextBudgetManager(max_total_tokens=4096)
    compressor = Compressor(budget_manager=budget_mgr)

    all_metrics = []
    latencies = []

    for sample in samples:
        start = time.time()

        # 召回
        retrieval_result = retriever.retrieve(sample.query, user_role="public")

        # 重排
        rerank_output = reranker.rerank(retrieval_result.chunks)

        # 压缩
        rerank_results = rerank_output.results
        compression = compressor.compress(rerank_results)

        elapsed_ms = (time.time() - start) * 1000

        # 提取结果来源 ID
        retrieved_ids = [c.chunk.source_id for c in rerank_output.results]

        # 模拟生成答案（取压缩后的拼接内容）
        generated_answer = " ".join(c.content for c in compression.chunks)

        metrics = EvalMetrics(
            sample_id=sample.id,
            recall_at_5=compute_recall_at_k(retrieved_ids, sample.relevant_source_ids, 5),
            recall_at_10=compute_recall_at_k(retrieved_ids, sample.relevant_source_ids, 10),
            mrr=compute_mrr(retrieved_ids, sample.relevant_source_ids),
            answer_f1=compute_f1(generated_answer, sample.expected_answer),
            latency_ms=elapsed_ms,
            retrieved_source_ids=retrieved_ids,
            num_chunks_after_compress=len(compression.chunks),
        )
        all_metrics.append(metrics)
        latencies.append(elapsed_ms)

    # 聚合指标
    n = len(all_metrics)
    avg_recall_5 = sum(m.recall_at_5 for m in all_metrics) / n if n else 0
    avg_recall_10 = sum(m.recall_at_10 for m in all_metrics) / n if n else 0
    avg_mrr = sum(m.mrr for m in all_metrics) / n if n else 0
    avg_f1 = sum(m.answer_f1 for m in all_metrics) / n if n else 0
    avg_lat = sum(latencies) / n if n else 0
    p95_lat = sorted(latencies)[int(n * 0.95)] if n else 0

    # 按 category 聚合
    by_category = _group_metrics(all_metrics, samples, "category")
    by_difficulty = _group_metrics(all_metrics, samples, "difficulty")

    report = EvalReport(
        dataset_name=os.path.basename(dataset_path),
        total_samples=n,
        avg_recall_at_5=avg_recall_5,
        avg_recall_at_10=avg_recall_10,
        avg_mrr=avg_mrr,
        avg_answer_f1=avg_f1,
        avg_latency_ms=avg_lat,
        p95_latency_ms=p95_lat,
        by_category=by_category,
        by_difficulty=by_difficulty,
        details=all_metrics,
    )

    # 输出报告
    _write_report(report, output_dir)

    return report


def _group_metrics(
    metrics: List[EvalMetrics],
    samples: List[EvalSample],
    group_by: str,
) -> Dict[str, Dict[str, float]]:
    """按指定字段分组聚合指标"""
    sample_map = {s.id: s for s in samples}
    groups: Dict[str, List[EvalMetrics]] = {}

    for m in metrics:
        sample = sample_map.get(m.sample_id)
        if not sample:
            continue
        key = getattr(sample, group_by, "unknown")
        groups.setdefault(key, []).append(m)

    result = {}
    for key, group in groups.items():
        n = len(group)
        result[key] = {
            "count": n,
            "avg_recall_at_5": sum(m.recall_at_5 for m in group) / n,
            "avg_recall_at_10": sum(m.recall_at_10 for m in group) / n,
            "avg_mrr": sum(m.mrr for m in group) / n,
            "avg_answer_f1": sum(m.answer_f1 for m in group) / n,
            "avg_latency_ms": sum(m.latency_ms for m in group) / n,
        }

    return result


def _write_report(report: EvalReport, output_dir: str):
    """将报告写入 Markdown 文件"""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "eval-report.md")

    lines = [
        "# RAG 评测报告",
        "",
        f"- 数据集: {report.dataset_name}",
        f"- 样本数: {report.total_samples}",
        "",
        "## 总体指标",
        "",
        "| 指标 | 值 |",
        "|------|-----|",
        f"| Recall@5 | {report.avg_recall_at_5:.4f} |",
        f"| Recall@10 | {report.avg_recall_at_10:.4f} |",
        f"| MRR | {report.avg_mrr:.4f} |",
        f"| Answer-F1 | {report.avg_answer_f1:.4f} |",
        f"| Avg Latency | {report.avg_latency_ms:.1f}ms |",
        f"| P95 Latency | {report.p95_latency_ms:.1f}ms |",
        "",
        "## 按类别",
        "",
        "| 类别 | 样本数 | Recall@5 | MRR | F1 |",
        "|------|--------|----------|-----|-----|",
    ]

    for cat, vals in report.by_category.items():
        lines.append(
            f"| {cat} | {vals['count']:.0f} | {vals['avg_recall_at_5']:.4f} | "
            f"{vals['avg_mrr']:.4f} | {vals['avg_answer_f1']:.4f} |"
        )

    lines.extend([
        "",
        "## 按难度",
        "",
        "| 难度 | 样本数 | Recall@5 | MRR | F1 |",
        "|------|--------|----------|-----|-----|",
    ])

    for diff, vals in report.by_difficulty.items():
        lines.append(
            f"| {diff} | {vals['count']:.0f} | {vals['avg_recall_at_5']:.4f} | "
            f"{vals['avg_mrr']:.4f} | {vals['avg_answer_f1']:.4f} |"
        )

    lines.extend([
        "",
        "## 样本明细",
        "",
        "| ID | Recall@5 | MRR | F1 | Latency(ms) |",
        "|----|----------|-----|-----|-------------|",
    ])

    for m in report.details:
        lines.append(
            f"| {m.sample_id} | {m.recall_at_5:.2f} | {m.mrr:.2f} | "
            f"{m.answer_f1:.2f} | {m.latency_ms:.1f} |"
        )

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Report written to {path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="RAG Evaluation Script")
    parser.add_argument(
        "--dataset",
        default=str(PROJECT_ROOT / "eval" / "datasets" / "rag_v1.jsonl"),
        help="Path to evaluation dataset (JSONL)",
    )
    parser.add_argument(
        "--output",
        default=str(PROJECT_ROOT / "eval" / "reports"),
        help="Output directory for reports",
    )
    args = parser.parse_args()

    report = run_evaluation(args.dataset, args.output)
    print(f"\nTotal samples: {report.total_samples}")
    print(f"Avg Recall@5: {report.avg_recall_at_5:.4f}")
    print(f"Avg Recall@10: {report.avg_recall_at_10:.4f}")
    print(f"Avg MRR: {report.avg_mrr:.4f}")
    print(f"Avg Answer-F1: {report.avg_answer_f1:.4f}")
    print(f"Avg Latency: {report.avg_latency_ms:.1f}ms")
