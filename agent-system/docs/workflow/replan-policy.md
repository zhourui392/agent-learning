# Replanner 策略（W2）

## 触发条件
- 步骤失败：返回 `success=false`。
- 依赖缺失：就绪队列为空但仍有未完成步骤。
- 上下文漂移：步骤执行时发现关键上下文与计划生成时不一致。

## 策略类型
- `local_replace`：仅替换失败步骤，保留其他步骤。
- `rollback_retry`：从失败点向后重建子图并重试。
- `human_handoff`：不可自动恢复时转人工。

## 策略选择规则
- 可重试错误（`tool_timeout`、`transient_network_error`）优先 `local_replace`。
- 依赖缺失或上下文漂移优先 `rollback_retry`。
- 策略/权限/契约类错误（`permission_denied`、`schema_validation_error`）走 `human_handoff`。

## 步骤 ID 映射
重规划后必须输出 `step_id_mapping`：
- `source_step_id`：原步骤 ID。
- `target_step_id`：新步骤 ID。
- `plan_version`：目标计划版本。

## 轨迹保留
- 历史步骤状态与审计日志不可覆盖。
- 新计划步骤必须可关联到原失败步骤。
- 审计事件需包含 `replan_reason` 与 `replan_strategy`。

