# Roles And Responsibilities

## Roles
- `planner`：拆解目标、生成任务、选择执行顺序，不直接改共享记忆中的最终业务结论。
- `executor`：执行检索、工具调用、数据整理，产出候选结果和证据。
- `auditor`：复核执行结果、识别冲突与风险，必要时要求重做或触发人工介入。
- `coordinator`：维护跨角色状态、汇总回传结果、推动仲裁与收敛。
- `human`：处理高风险冲突、低置信度分歧和越权场景。

## Responsibility Boundaries
- Planner 负责“做什么”，Executor 负责“怎么做”，Auditor 负责“是否可信”。
- Coordinator 负责流程推进，不替代 Auditor 的判断职责。
- Human 只在自动决策不稳定或风险超阈值时介入。

## Inputs / Outputs
- Planner 输入：目标、上下文、共享记忆摘要；输出：`task_request`
- Executor 输入：`task_request`；输出：`task_result`
- Auditor 输入：`task_result`、证据链；输出：`audit_review` 或 `conflict_notice`
- Coordinator 输入：多角色回传；输出：最终汇总结果或人工介入请求

## Human Triggers
- 关键候选结果置信度差值小于 0.1 且结论冲突。
- 审计发现策略、权限或合规风险。
- 共享记忆出现重复版本冲突且无法自动重试收敛。