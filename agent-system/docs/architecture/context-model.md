# 上下文模型

## 分层
- 系统上下文：
  - 关键字段：tenant_id、environment、policy_version。
- 任务上下文：
  - 关键字段：request_id、session_id、user_input、objective。
- 工具上下文：
  - 关键字段：current_tool、validated_payload、retry_budget。
- 会话记忆：
  - 关键字段：completed_steps、intermediate_outputs、snapshots。

## 生命周期
1. 从智能体请求创建上下文。
2. 按工具作用域与 token 预算裁剪上下文。
3. 在步骤边界持久化执行快照。
4. 通过 TTL 过期陈旧会话记忆。
5. 记录日志前清理敏感字段。

## 可追溯规则
每个请求必须保留：
- context_source：每个字段的来源。
- trim_policy：被删除内容及删除原因。
- redact_policy：审计日志前被脱敏的字段策略。

## 脱敏基线
- 脱敏字段：api_key、password、access_token、ssn、phone。
- 保留字段：request_id、session_id、step_id、tool_id。

## Token 预算规则
- 优先保留最近 5 个步骤摘要。
- 先丢弃原始工具 payload。
- 保持策略与身份元数据完整。
