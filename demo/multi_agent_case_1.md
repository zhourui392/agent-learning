# Multi-Agent Case 1

## 场景
标准流程：Planner 下发任务，Executor 收集退款证据，Auditor 复核通过，Coordinator 汇总完成。

## 预期路径
- `task_request` -> `task_result` -> `audit_review`
- 共享记忆写入 `merchant:m-100`
- 最终状态为 `completed`

## 运行逻辑
对应实现见 `src/multi_agent/demo_flow.py` 中的 `run_standard_flow()`。