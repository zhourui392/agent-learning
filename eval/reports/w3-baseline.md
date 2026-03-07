# W3 基线报告

## 基线版本

- 日期: 2026-03-06
- 数据集: eval/datasets/rag_v1.jsonl（15 样本）
- 链路: HybridRetriever(RRF) -> Reranker(3-feature) -> Compressor(budget=2000)

## 冻结指标

| 指标 | 基线值 | 说明 |
|------|--------|------|
| Recall@5 | 1.0000 | Mock 索引规模小，全命中 |
| Recall@10 | 1.0000 | 同上 |
| MRR | 1.0000 | 首个相关结果均排在第1位 |
| Answer-F1 | 0.0575 | 仅拼接原始 chunk，未经 LLM 生成 |
| Avg Latency | 0.3ms | 内存索引，无网络开销 |
| P95 Latency | 1.5ms | 同上 |

## 已知局限

1. **索引规模偏小**：当前仅 11 条 mock 文档，召回指标虚高。生产环境需接入真实知识库后重新评测。
2. **Answer-F1 偏低**：当前未接入 LLM 生成答案，仅拼接检索内容。W4 接入工具调用后可改善。
3. **向量召回为 Mock**：使用字符重叠模拟相似度，需替换为真实 Embedding 模型。
4. **中文分词为简易实现**：关键词召回使用正则分词，生产需接入 jieba 或自定义分析器。

## Top 问题样本分析

| 样本 ID | 问题 | 原因 | 改进方向 |
|---------|------|------|----------|
| fact_001 | F1=0.00 | 期望答案短（"退款有效期为30天"），检索内容冗余 | 压缩层需更精确的片段裁剪 |
| edge_001 | F1=0.00 | 需跨两个 source 综合，但未做 chunk 拼接优化 | 增加跨源聚合逻辑 |
| neg_001 | F1=0.00 | 拒答类样本，检索结果无意义 | 需在 pipeline 前置安全过滤 |
| multi_002 | F1=0.00 | 答案涉及技术细节（Redis原子扣减），chunk 内容覆盖不完整 | 增加 chunk 粒度或上下文窗口 |

## 改进计划

1. **短期（W4）**：
   - 接入 LLM 生成答案，提升 Answer-F1
   - 增加安全过滤前置节点
   - 替换 Mock 向量召回为真实 Embedding

2. **中期（W5-W6）**：
   - 扩大评测样本集（目标 100+）
   - 接入真实知识库，重新评测召回指标
   - 引入 Cross-Encoder 精排

3. **长期**：
   - A/B 实验框架
   - 在线评测与用户反馈闭环

## 复现方式

```bash
cd agent-learning
python -m eval.scripts.eval_rag --dataset eval/datasets/rag_v1.jsonl --output eval/reports/
```
