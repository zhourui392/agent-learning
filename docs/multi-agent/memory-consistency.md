# Memory Consistency

## 目标
W7 的共享记忆采用乐观锁和版本号，保证多角色并发写入可控、可追踪。

## 规则
- 每个 key 维护单调递增 `version`。
- 写入方可携带 `expected_version` 做 compare-and-set。
- 版本不匹配时抛出 `VersionConflictError`，由协调器决定重试或人工兜底。
- 可配置 TTL，过期后自动清理。

## 推荐写入顺序
1. Planner 写任务摘要。
2. Executor 写候选结果。
3. Auditor 写审计结论。
4. Coordinator 写最终汇总。

## 可追踪性
- 每次写入都记录 `writer_role`。
- 可通过版本历史查看某个 key 的更新轨迹。