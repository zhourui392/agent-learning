# 状态机与恢复

## 会话状态
状态流转：`PENDING -> RUNNING -> WAITING_TOOL -> SUCCESS | FAILED | CANCELED`

## 步骤级状态规则
- 每个步骤在调用工具前进入 `RUNNING`。
- 每个步骤在外部执行期间进入 `WAITING_TOOL`。
- 工具结果成功并落库后，步骤进入 `SUCCESS`。
- 重试耗尽或不可重试错误时，步骤进入 `FAILED`。
- 收到取消信号时，步骤进入 `CANCELED`。

## 重试与重规划模型
### 可重试错误示例
- `tool_timeout`（工具超时）
- `transient_network_error`（瞬时网络错误）
- `service_unavailable`（服务不可用）

### 不可重试错误示例
- `schema_validation_error`（Schema 校验失败）
- `permission_denied`（权限拒绝）
- `invalid_business_input`（业务输入非法）

### 重规划策略
- `local_replace`：替换失败步骤并维护 step_id 映射。
- `rollback_retry`：从失败点向后重建子图。
- `human_handoff`：权限/契约/业务非法错误转人工。

## 快照策略
在以下时机创建快照：
- `pre-step`：步骤执行前。
- `post-success`：步骤成功后。
- `post-failed`：步骤失败后。
- `final-response`：响应构建前。

快照键：
- `session_id + step_id + snapshot_index`

## 恢复入口
恢复入口参数：`session_id` + 可选 `step_id`。
- 指定 `step_id`：从该步骤最近快照恢复。
- 不指定 `step_id`：从最近成功快照后的首个未完成步骤恢复。

## 幂等性
- 步骤级幂等键：`request_id + step_id + plan_version`。
- 同幂等键且步骤已成功时，重复提交不会重复执行。
- 重规划后 plan_version 递增，确保新旧步骤可区分。
