# 重排特征说明（Rerank Features）

## 概述

重排层对召回结果执行多维度评分，产出可解释的排序结果。每条结果附带三维分数与最终加权分。

---

## 1. 特征定义

### 1.1 相关性（Relevance）

- 来源：召回阶段的原始分数（向量相似度 / BM25 分数）
- 处理：对召回批次内的分数做 min-max 归一化到 [0, 1]
- 权重：默认 0.5

### 1.2 时效性（Freshness）

- 来源：chunk 元数据中的 `updated_at` 字段
- 处理：指数衰减函数 `score = exp(-age_days / decay_days)`
  - `decay_days` 默认 90 天
  - 当天更新的文档得分接近 1.0
  - 90 天前的文档得分约 0.37
  - 无时间信息的文档得中性分 0.5
- 权重：默认 0.3

### 1.3 来源可信度（Authority）

- 来源：chunk 的 `source_type` 字段
- 处理：查表映射
  - `doc`（官方文档）→ 0.9
  - `db`（数据库）→ 0.8
  - `api`（API 数据）→ 0.7
  - `user_generated`（用户内容）→ 0.5
  - `unknown`（未知来源）→ 0.3
- 权重：默认 0.2

---

## 2. 最终得分计算

```
final_score = w_relevance * relevance + w_freshness * freshness + w_authority * authority
```

约束：`w_relevance + w_freshness + w_authority = 1.0`

---

## 3. 可解释输出

每条重排结果包含 `RerankScore` 字段：

```json
{
  "relevance_score": 0.85,
  "freshness_score": 0.92,
  "authority_score": 0.90,
  "final_score": 0.883,
  "explanation": "relevance=0.850(w=0.5), freshness=0.920(w=0.3), authority=0.900(w=0.2)"
}
```

---

## 4. 权重调优建议

| 场景 | relevance | freshness | authority |
|------|-----------|-----------|-----------|
| 通用问答 | 0.5 | 0.3 | 0.2 |
| 时效敏感（新闻/公告） | 0.3 | 0.5 | 0.2 |
| 合规/政策查询 | 0.4 | 0.2 | 0.4 |
| 数据查询 | 0.6 | 0.1 | 0.3 |

---

## 5. 后续扩展方向

- 引入 Cross-Encoder 模型作为精排特征
- 增加用户反馈信号（点击率/采纳率）
- 增加查询-文档类型匹配特征
- 支持 A/B 实验的权重在线调整
