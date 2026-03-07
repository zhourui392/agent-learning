# Log Schema

## 目标
W6 日志统一采用结构化 JSON 行格式，便于检索、聚合与告警。

## 核心字段
- `timestamp_ms`：日志时间戳。
- `level`：`INFO` / `WARN` / `ERROR`。
- `event_type`：事件类型，如 `retrieval_complete`、`authorization_failed`。
- `component`：所属模块。
- `message`：人类可读摘要。
- `trace_id` / `session_id` / `case_id`：链路关联字段。
- `step_id`：关联到具体 Span。
- `error_code`：结构化错误码。
- `metadata`：扩展字段。

## 事件模型
- planner：规划开始、规划完成、重规划。
- retrieval：召回完成、召回为空、缓存命中。
- tool：校验失败、鉴权失败、工具成功、工具异常。
- response：答案生成完成、拒答、回答质量退化。

## 规范
- 日志必须避免敏感信息明文输出。
- 同一错误必须带 `error_code`。
- 关键成功路径至少输出一条 `INFO`。
- 关键失败路径必须输出 `WARN` 或 `ERROR`。