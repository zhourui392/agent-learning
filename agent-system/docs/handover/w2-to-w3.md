# W2 -> W3 交接说明

## 已冻结接口
- Planner：`Planner.create_plan(request) -> ExecutionPlan`
- Executor：`Executor.execute(plan, request, context, control=None) -> ExecutionResult`
- Replanner：`Replanner.replan_after_failure(plan, failed_step, error) -> ReplanOutcome`
- Recovery：`RecoveryService.find_recovery_point(session_state, step_id=None)`

## W3 接入建议
- 检索增强优先接入 `tool.search` 的 payload 生成逻辑。
- 上下文压缩复用 `ContextManager` 的裁剪策略并增加 token 预算接口。
- 评测样本回放可直接复用 `session_id` 的断点续跑能力。

## 风险与注意事项
- 当前为内存状态存储，进程重启后状态丢失。
- 重规划默认上限为 1 次，复杂场景需按业务扩展。
- 并发执行使用线程池，CPU 密集任务需后续改造。

