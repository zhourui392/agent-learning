# Multi-Agent Protocol

## Overview
W7 采用基于消息协议的多 Agent 协作模型，核心角色包括 `planner`、`executor`、`auditor`、`coordinator` 与 `human`。

## Message Envelope
- `version`：协议版本，当前为 `1.x`
- `header`：消息标识、类型、发送方、接收方、任务 ID
- `payload`：业务数据
- `meta`：trace/session/status/priority/conflict_fields

## Core Message Types
- `task_request`
- `task_result`
- `audit_review`
- `conflict_notice`
- `memory_update`

## Runtime Components
- Validator：校验协议结构与兼容性
- Dispatcher：负责任务分发、超时回收与重试
- Callback Handler：负责结果回传和聚合
- Arbitrator：负责冲突仲裁
- Shared Memory：负责共享状态一致性

## Human Fallback
当结论冲突且自动规则无法稳定收敛时，系统进入 `needs_human`，由人工接管最终裁决。