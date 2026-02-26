# 上下文模型

## 分层
- 系统上下文：
  - 关键字段：tenant_id、environment、policy_version。
- 任务上下文：
  - 关键字段：request_id、session_id、user_input、trace_id、plan_version。
- 工具上下文：
  - 关键字段：current_tool、validated_payload、retry_budget、timeout_seconds。
- 会话记忆：
  - 关键字段：step_summaries、snapshots、step_id_mapping。

## 生命周期
1. 从智能体请求创建上下文。
2. 按工具作用域与 token 预算裁剪上下文。
3. 在步骤边界持久化执行快照。
4. 重规划后维护步骤 ID 映射与 plan_version。
5. 记录日志前清理敏感字段。

## 可追溯规则
每个请求必须保留：
- `source_map`：每个字段的来源。
- `trim_policy`：被删除内容及删除原因。
- `trace_id`：跨 Planner/Executor/Replanner 的追踪主键。
- `plan_version`：计划版本号。

## 脱敏基线
- 脱敏字段：api_key、password、access_token、ssn、phone。
- 保留字段：request_id、session_id、step_id、tool_id、trace_id、plan_version。

## Token 预算规则
- 优先保留最近 5 个步骤摘要。
- 先丢弃原始工具 payload。
- 保持策略与身份元数据完整。
