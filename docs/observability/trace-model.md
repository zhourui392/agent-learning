# Trace Model

## 目标
W6 统一使用 Trace / Span 模型串联一次请求中的规划、检索、工具调用、响应生成等关键步骤，确保同一请求可以通过 `trace_id` 完整追踪。

## Trace 字段
- `trace_id`：单次请求全链路唯一标识。
- `session_id`：同一会话或评测样本维度标识。
- `case_id`：样本或业务请求编号，便于回放。
- `tags`：业务标签，如 `dataset_name`、`tenant`、`scenario`。

## Span 字段
- `step_id`：当前步骤唯一标识。
- `parent_step_id`：父步骤 ID，用于表达嵌套关系。
- `component`：所属模块，如 `retrieval`、`gateway`、`generation`。
- `name`：步骤名称，如 `retrieve`、`authorization`、`execution`。
- `started_at_ms` / `ended_at_ms` / `duration_ms`：时延字段。
- `status`：`ok` / `error`。
- `error_code`：失败时的结构化错误码。
- `metadata`：扩展属性，如召回条数、输出 token、工具名。

## 推荐链路
- RAG：`retrieve -> rerank -> compress -> build_answer`
- Gateway：`validation -> authorization -> circuit_check -> rate_limit -> execution`

## 采样要求
- `smoke` 与 `adversarial` 默认全量采样。
- 高吞吐场景允许抽样，但错误链路必须 100% 采集。
- `trace_id` 必须同时出现在日志、Span、失败归档中。