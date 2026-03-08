# Multi-Agent Case 2

## 场景
异常流程：Executor 与 Auditor 对退款结论冲突，进入仲裁。

## 预期路径
- 候选结果冲突
- 同优先级且置信度接近
- 仲裁结果为 `needs_human`

## 运行逻辑
对应实现见 `src/multi_agent/demo_flow.py` 中的 `run_conflict_flow()`。