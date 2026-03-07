# Dashboard Guide

## 看板目标
为研发与运维提供统一视图，独立完成成功率、延迟、成本、错误率排查。

## 推荐维度
- 场景：`smoke` / `regression` / `adversarial`
- 租户：`tenant`
- 工具：`tool_name`
- 模块：`component`
- 模型版本：`model_version`

## 核心看板
- E2E Success Rate
- P95 Latency
- Failure Buckets
- Total Tokens

## 排查路径
1. 从成功率或错误率异常入口进入。
2. 下钻到具体 `trace_id` 或 `error_code`。
3. 结合 `latency-breakdown` 与 `error-topn` 做根因判断。