# W2 评审记录

## 保留项
- Planner/Executor/Replanner API 已固定：`create_plan`、`execute`、`replan_after_failure`。
- 状态机已与执行引擎联动，支持步骤级快照与续跑。
- 幂等键规则统一为 `request_id + step_id + plan_version`。

## 修复项
- 后续需补充更细粒度并发调度公平性策略。
- 需增加跨进程持久化状态存储（W3/W4）。

## 延后项
- 分布式执行器与跨节点取消信号。
- 更细的成本预算控制（按工具类型配额）。

## W3 输入项
- 检索链路接入点：`Planner` 生成的 `tool.search` 步骤。
- 上下文预算接口：`ContextManager.trim_for_tool`。
- 恢复接口：`RecoveryService.find_recovery_point`。

