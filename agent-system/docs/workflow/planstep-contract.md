# PlanStep 协议（W2）

## 目标
定义 Planner 与 Executor 之间的统一任务分解契约，保证任务图可校验、可执行、可追踪。

## PlanStep 字段
- `step_id`：步骤唯一标识，格式建议 `step-{n}` 或 `step-{n}-replan-{k}`。
- `goal`：步骤业务目标，描述“做什么”。
- `tool_id`：执行工具标识，必须存在于 `allowed_tools`。
- `payload`：工具入参，执行前必须通过工具 Schema 校验。
- `depends_on`：依赖步骤 ID 列表，空数组表示无依赖可直接执行。
- `done_criteria`：完成判定，描述“何时算成功”。
- `timeout_seconds`：步骤超时阈值，单位秒，默认 8。
- `allow_rollback`：是否允许失败后进入回退策略。

## 任务图约束
- 无环：依赖图必须是 DAG。
- 最大深度：默认不超过 6，超出判定为不可执行计划。
- 最大并发：默认不超过 4，超出判定为并发风险。

## 计划质量检查
- 可执行性：
  - `tool_id` 非空且在允许列表。
  - `payload` 非空且可通过工具契约校验。
  - 依赖步骤必须存在。
- 可观测性：
  - 每个步骤必须可映射唯一 `step_id`。
  - 每个步骤必须有 `done_criteria`。
- 可回滚性：
  - 写操作步骤必须显式配置 `allow_rollback`。
  - 失败路径需可落入 `rollback_retry` 或 `human_handoff`。

## 风险标记
Planner 必须输出 `risk_flags`：
- `high_cost`：高失败成本（如通知/写操作）。
- `external_dependency`：强依赖外部工具或网络。
- `uncertain_information`：输入存在不确定条件。

## 版本与追踪
- `plan_version`：每次重规划 +1。
- `trace_id`：请求级追踪 ID，贯穿 Planner/Executor/Replanner/Audit。

