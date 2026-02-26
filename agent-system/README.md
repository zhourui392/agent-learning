# 智能体系统 W1 基线

[![CI](https://github.com/zhourui392/agent-learning/actions/workflows/ci.yml/badge.svg)](https://github.com/zhourui392/agent-learning/actions/workflows/ci.yml)

本目录包含一个可运行的 W1 架构基线，用于面向生产的智能体后端。

## 包含内容
- 边界、上下文、状态机和主流程时序等架构文档。
- 边界策略、存储策略、工具契约治理的 ADR 记录。
- 以契约优先为核心，并集成 JSON Schema 校验的网关。
- 规划器（Planner）+ 执行器（Executor）+ 内存状态存储 + 快照恢复的骨架实现。
- 本地模拟工具与端到端回放命令。

## 目录重点
- `docs/architecture/`：边界/上下文/状态/时序文档。
- `docs/adr/`：关键架构决策。
- `contracts/`：请求/响应与工具 Schema。
- `src/`：运行时代码模块。
- `tests/`：契约测试与集成测试。
- `scripts/`：Schema 校验与会话回放脚本。

## 本地运行
```bash
cd agent-system
./scripts/validate_contracts.sh
./scripts/replay_session.sh
python3 -m unittest discover -s tests
```

## 主流程
流程链路：`request -> validate -> plan -> execute -> snapshot -> response -> audit`

## 当前范围
- 用于本地开发与评审的 W1 基线。
- 内存状态存储（按设计不持久化）。
