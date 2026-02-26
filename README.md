# Agent Learning（工程化训练仓库）

[![CI](https://github.com/zhourui392/agent-learning/actions/workflows/ci.yml/badge.svg)](https://github.com/zhourui392/agent-learning/actions/workflows/ci.yml)

本仓库用于按周推进 Agent 工程化落地，目标是从架构基线到可上线治理能力，形成可执行、可评审、可回放的实现路径。

## 当前已完成工作（截至 2026/02/26）

- 已完成 8 周学习路线与分周执行清单文档（W1-W8）。
- 已落地 W1 的可运行工程骨架（`agent-system/`）。
- 已完成 W1 关键架构文档：边界、上下文模型、状态机、主链路时序。
- 已完成 W1 核心 ADR：单 Agent 优先、状态存储策略、工具契约治理。
- 已实现最小主链路：`request -> validate -> plan -> execute -> snapshot -> response -> audit`。
- 已接入契约治理：请求/响应/工具 JSON Schema + 校验器。
- 已补齐测试与脚本：契约测试、集成测试、Schema 校验脚本、回放脚本。
- 已接入 GitHub Actions CI：推送与 PR 自动执行契约与集成测试。

## 目录说明

- `总体学习文档.md`：全局目标、里程碑、周指标。
- `每周学习方案.md`：W1-W8 周计划详细安排。
- `W1-执行清单.md` ~ `W8-执行清单.md`：每周可执行清单。
- `agent-system/`：W1 落地代码与文档（可运行）。
  - `agent-system/docs/`：架构文档与 ADR。
  - `agent-system/contracts/`：请求/响应/工具契约。
  - `agent-system/src/`：Planner/Executor/State/Gateway/API 骨架实现。
  - `agent-system/tests/`：契约测试与集成测试。
  - `agent-system/scripts/`：本地校验与回放脚本。

## 本地运行

```bash
cd agent-system
./scripts/validate_contracts.sh
./scripts/replay_session.sh
PYTHONPATH=. python3 -m unittest discover -s tests
```

## 当前边界与限制

- 当前状态存储为内存实现，重启进程后状态不保留。
- 当前工具为 mock 实现，目标用于验证主流程与治理骨架。
- 多 Agent 协作能力将在后续周（W7）再展开。

## 下一步建议

- 按 W2 清单推进 Workflow 内核：Planner-Executor-Replanner 细化。
- 将状态存储抽象切换到持久化后端（如 Redis/PostgreSQL）。
- 补充失败恢复、重试策略、幂等键在真实工具链中的验证。
