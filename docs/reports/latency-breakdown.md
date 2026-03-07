# Latency Breakdown Guide

## 用途
使用 `src/observability/latency_analyzer.py` 对 Span 数据做聚合，识别慢步骤、慢工具与慢链路。

## 关键指标
- Case Avg Latency
- Case P95 Latency
- Component Avg Duration
- Component P95 Duration

## 推荐分析顺序
1. 先看整条请求的 `P95 Case Latency`。
2. 再看热点步骤表，定位 `component + span` 组合。
3. 对热点步骤继续拆分等待、执行、重试成本。

## 常见热点
- `retrieval.retrieve`：召回候选过多或索引质量差。
- `gateway.execution`：工具依赖慢或失败重试。
- `generation.build_answer`：上下文过长导致生成变慢。