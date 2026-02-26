# 智能体系统 W2 Workflow 内核基线

[![CI](https://github.com/zhourui392/agent-learning/actions/workflows/ci.yml/badge.svg)](https://github.com/zhourui392/agent-learning/actions/workflows/ci.yml)

本目录包含一个可运行的 W2 架构基线，用于面向生产的智能体后端 Workflow 内核验证。

## 包含内容
- W1 架构文档：边界、上下文、状态机、主流程时序。
- W2 Workflow 文档：PlanStep 协议、Replanner 策略、幂等与续跑。
- 以契约优先为核心，并集成 JSON Schema 校验的网关。
- 规划器（Planner）+ 执行器（Executor）+ 重规划器（Replanner）骨架实现。
- 内存状态存储 + 快照恢复 + 断点续跑 + 幂等跳过。
- 本地模拟工具、端到端回放与故障注入脚本。

## 目录重点
- `docs/architecture/`：边界/上下文/状态/时序文档。
- `docs/workflow/`：任务分解、重规划、幂等策略。
- `docs/review/`：W2 评审记录。
- `docs/handover/`：W2 -> W3 交接说明。
- `contracts/`：请求/响应、工具 Schema、PlanStep Schema。
- `src/`：运行时代码模块。
- `tests/`：契约测试、单元测试、集成测试。
- `scripts/`：Schema 校验、会话回放、故障注入。

## 本地运行
```bash
cd agent-system
./scripts/validate_contracts.sh
./scripts/replay_session.sh
python3 -m unittest discover -s tests
./scripts/fault_injection.sh
```

## 主流程
流程链路：`request -> validate -> plan -> execute -> replan(optional) -> snapshot -> response -> audit`

## W2 核心能力
- 计划质量校验：无环、最大深度、最大并发、依赖完整性。
- 执行控制：步骤超时、会话超时、并发配额、取消信号。
- 恢复机制：失败重试、重规划、幂等跳过、断点续跑。
- 审计追踪：trace_id、plan_version、step_id 映射、步骤级结果日志。

## 当前范围
- 用于本地开发与评审的 W2 Workflow 基线。
- 内存状态存储（按设计不持久化）。
- 工具调用为 mock（用于故障路径和恢复路径验证）。
