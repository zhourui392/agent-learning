# Agent Learning（工程化训练仓库）

[![CI](https://github.com/zhourui392/agent-learning/actions/workflows/ci.yml/badge.svg)](https://github.com/zhourui392/agent-learning/actions/workflows/ci.yml)

本仓库用于按周推进 Agent 工程化落地，目标是从架构基线到可上线治理能力，形成可执行、可评审、可回放的实现路径。

## 当前已完成工作（截至 2026/02/26）

- 已完成 8 周学习路线与分周执行清单文档（W1-W8）。
- 已落地 W1 架构基线与 W2 Workflow 内核（`agent-system/`）。
- 已实现 Planner-Executor-Replanner 主流程与计划版本追踪。
- 已实现步骤级超时、重试、幂等、取消、断点续跑。
- 已接入任务图质量校验（无环、深度、并发上限）。
- 已完成 W2 文档与契约产物（PlanStep 协议、重规划策略、幂等策略）。
- 已补齐测试与脚本：单测、集成测试、Schema 校验、会话回放、故障注入。
- 已接入 GitHub Actions CI：推送与 PR 自动执行契约与集成测试。

## 目录说明

- `plans/总体学习文档.md`：全局目标、里程碑、周指标。
- `plans/每周学习方案.md`：W1-W8 周计划详细安排。
- `plans/W1-执行清单.md` ~ `plans/W8-执行清单.md`：每周可执行清单。
- `agent-system/`：W1-W2 落地代码与文档（可运行）。
  - `agent-system/docs/architecture/`：边界、上下文、状态机、主流程时序。
  - `agent-system/docs/workflow/`：PlanStep、重规划、幂等与续跑说明。
  - `agent-system/docs/review/`：W2 评审记录。
  - `agent-system/docs/handover/`：W2 -> W3 交接文档。
  - `agent-system/contracts/`：请求/响应/工具契约 + PlanStep 契约。
  - `agent-system/src/`：Planner/Executor/Replanner/State/Gateway/API 实现。
  - `agent-system/tests/`：契约测试、单测、集成测试。
  - `agent-system/scripts/`：本地校验、回放、故障注入脚本。

## 本地运行

```bash
cd agent-system
./scripts/validate_contracts.sh
./scripts/replay_session.sh
python3 -m unittest discover -s tests
./scripts/fault_injection.sh
```

## 当前边界与限制

- 当前状态存储为内存实现，重启进程后状态不保留。
- 当前工具为 mock 实现，用于验证 Workflow 内核机制。
- 重规划默认上限为 1 次，复杂场景需按业务扩展。
- 多 Agent 协作能力将在后续周（W7）展开。

## 下一步建议

- 按 W3 清单推进 RAG 工程化（召回、重排、上下文压缩、评测基线）。
- 将状态存储切换到持久化后端（如 Redis/PostgreSQL）。
- 增强重规划策略（多轮重规划、策略可配置化、人工接管闭环）。
