# Alert Rules

## 目标
围绕 SLO 违约、错误激增、成本突增建立 W6 告警规则。

## 规则
- `E2E Success Rate < 0.75` 持续 15 分钟：告警等级 `P1`
- `P95 Latency > baseline 1.5x` 持续 15 分钟：告警等级 `P2`
- `tool_execution_failed` 5 分钟内超过 10 次：告警等级 `P1`
- `rate_limited` 10 分钟内超过 20 次：告警等级 `P2`
- `cost.total_tokens` 日环比超过 30%：告警等级 `P2`

## 路由
- `P1`：On-call + 负责人 + 应急群
- `P2`：负责人 + 工作群
- `P3`：工作群 + 次日排期

## 验证
- 每条规则至少做一次压测或演练验证。
- 告警必须可关联 `trace_id`、`dashboard`、`runbook`。