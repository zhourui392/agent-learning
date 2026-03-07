# Error TopN Report Guide

## 用途
使用 `src/observability/error_bucket.py` 将失败样本归为 `model`、`tool`、`data`、`strategy`、`system` 五类，并按优先级和频次输出 TopN 报告。

## 输出列
- `Category`：错误大类。
- `Error Code`：结构化错误码。
- `Priority`：处理优先级，`P1` 最高。
- `Count`：命中次数。
- `Sample IDs`：关联样本。

## 默认映射
- `quality_regression` -> `model`
- `tool_execution_failed` / `invalid_tool_name` -> `tool`
- `missing_required_field` -> `data`
- `unauthorized` -> `strategy`
- `rate_limited` / `circuit_open` -> `system`

## 排查建议
- 先处理 `P1` 系统性故障。
- 再处理高频 `tool` 与 `model` 问题。
- `strategy` 问题通常涉及策略配置或授权口径。