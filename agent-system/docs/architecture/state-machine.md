# 状态机与恢复

## 会话状态
状态流转：`PENDING -> RUNNING -> WAITING_TOOL -> SUCCESS | FAILED`

## 步骤级状态规则
- 每个步骤在调用工具前进入 `RUNNING`。
- 每个步骤在外部执行期间进入 `WAITING_TOOL`。
- 当通过校验的工具结果被持久化后，步骤进入 `SUCCESS`。
- 当重试耗尽或错误不可重试时，步骤进入 `FAILED`。

## 重试模型
### 可重试示例
- tool_timeout（工具超时）
- transient_network_error（瞬时网络错误）
- service_unavailable（服务不可用）

### 不可重试示例
- schema_validation_error（Schema 校验失败）
- permission_denied（权限拒绝）
- invalid_business_input（业务输入非法）

## 快照策略
在以下时机创建快照：
- 步骤执行前
- 步骤成功后
- 最终响应构建时

快照键：
- 组成：session_id + step_id + snapshot_index

## 恢复入口
恢复 API 接收 session_id 和可选的 step_id。
- 如果提供 step_id，则从指定快照恢复。
- 否则从最近一次成功快照恢复。

## 幂等性
- 写工具必须携带 idempotency_key。
- 使用相同 idempotency_key 回放同一步骤时，不得重复产生副作用。
