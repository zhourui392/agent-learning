# W3 -> W4 交接说明

## W3 产出总结

### 代码模块

| 模块 | 路径 | 职责 |
|------|------|------|
| 双路召回器 | `src/rag/retriever.py` | 向量+关键词混合召回，RRF/加权合并，权限过滤 |
| 关键词召回器 | `src/rag/keyword_retriever.py` | BM25 内存实现 |
| 重排器 | `src/rag/reranker.py` | 三维特征评分（相关性/时效性/可信度），可解释输出 |
| 压缩器 | `src/rag/compressor.py` | 去重、低价值过滤、预算裁剪、上下文组装 |
| 上下文预算 | `src/rag/context_budget.py` | Token 配额管理 |
| 多级缓存 | `src/rag/cache.py` | Query/Embedding/Context 三级缓存 + 降级策略 |

### 文档

| 文档 | 路径 |
|------|------|
| 知识源清单 | `docs/rag/knowledge-inventory.md` |
| 索引策略 | `docs/rag/index-policy.md` |
| 重排特征说明 | `docs/rag/rerank-features.md` |
| 降级策略 | `docs/rag/degrade-policy.md` |

### 评测

| 产物 | 路径 |
|------|------|
| 评测数据集 v1 | `eval/datasets/rag_v1.jsonl`（15 样本） |
| 评测脚本 | `eval/scripts/eval_rag.py` |
| 基线报告 | `eval/reports/w3-baseline.md` |
| 评测结果 | `eval/reports/eval-report.md` |

## W4 接入要求（工具调用阶段的检索约束）

### 1. 检索接口约定

W4 的工具调用模块应通过以下接口调用检索链路：

```python
from src.rag.retriever import HybridRetriever

retriever = HybridRetriever(final_top_k=10)
result = retriever.retrieve(query="用户问题", user_role="internal")
# result.chunks -> List[RetrievalChunk]
```

### 2. 上下文预算约束

- 检索上下文默认预算：2000 tokens
- 工具调用前需先通过 `ContextBudgetManager` 分配预算
- 工具返回结果也需纳入 token 预算计算

### 3. 权限传递

- 用户角色需从会话上下文传递到检索层
- `user_role` 支持：public / internal / admin
- 权限过滤在召回层前置执行，不依赖后续环节

### 4. 降级兜底

- 工具调用中的检索应设置超时（建议 3s）
- 超时降级路径已内置于 `DegradePolicy`
- 降级结果需标记 `degraded=True`，LLM 应感知降级状态

### 5. 缓存复用

- W4 可直接复用 `RAGCache` 实例
- 工具调用结果也可缓存（需自行扩展 cache key 前缀）

## 风险与注意事项

1. 当前向量召回为 Mock（字符重叠模拟），需在 W4 或 W5 替换为真实 Embedding。
2. 关键词分词为简易正则，中文场景需接入 jieba。
3. 评测 Answer-F1 偏低，接入 LLM 后预计大幅改善。
4. 缓存为内存实现，进程重启后失效（与 W2 状态存储限制一致）。
