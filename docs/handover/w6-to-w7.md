# W6 -> W7 Handover

## W6 已交付
- Trace 模型：`docs/observability/trace-model.md`
- 日志模型：`docs/observability/log-schema.md`
- 埋点代码：`src/observability/tracer.py`、`src/observability/logger.py`
- 错误归因：`src/observability/error_bucket.py`
- 慢链路分析：`src/observability/latency_analyzer.py`
- 看板配置：`observability/dashboard.json`
- 告警与值班：`docs/observability/alert-rules.md`、`docs/runbook/oncall-escalation.md`

## 当前接入范围
- `eval.runner` 已接入 RAG 与 Gateway 主链路埋点。
- 运行评测会输出 `traces.jsonl`、`logs.jsonl`、`error-topn.md`、`latency-breakdown.md`。

## W7 建议重点
- 将 Trace/Log 接入多 Agent 协作链路。
- 为 Span 增加跨代理父子关系。
- 增加异常恢复与协作冲突观测。