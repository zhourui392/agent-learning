# W7 -> W8 Handover

## W7 已交付
- 多角色职责与 SLA：`docs/multi-agent/roles-and-responsibilities.md`、`docs/multi-agent/sla.md`
- 消息契约：`contracts/multi-agent-message.schema.json`
- 协议校验：`src/multi_agent/protocol_validator.py`
- 分派与回传：`src/multi_agent/dispatcher.py`、`src/multi_agent/callback_handler.py`
- 仲裁与记忆：`src/multi_agent/arbitrator.py`、`src/multi_agent/shared_memory.py`
- Demo：`demo/multi_agent_case_1.md`、`demo/multi_agent_case_2.md`
- 评审：`docs/review/review-notes-w7.md`

## 当前边界
- 当前实现为进程内、内存态多 Agent 骨架。
- 协议版本为 `1.x`，兼容策略以 validator 为准。
- 未接入真实外部消息总线、任务队列与持久化共享记忆。

## W8 建议重点
- 把多 Agent 骨架接入发布、灰度、回滚与运行治理。
- 将共享记忆迁移到持久化存储。
- 把 Demo 变成可自动化回放的真实业务链路。