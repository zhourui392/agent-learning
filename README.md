# Agent Learning（工程化训练仓库）

[![CI](https://github.com/zhourui392/agent-learning/actions/workflows/ci.yml/badge.svg)](https://github.com/zhourui392/agent-learning/actions/workflows/ci.yml)

本仓库用于按周推进 Agent 工程化落地，目标是从基础执行框架逐步演进到具备评测、观测、多 Agent 协作与上线治理能力的可交付系统。

当前仓库已经完成 `W1-W10` 的主要产物，覆盖：
- 工作流执行内核
- RAG 检索与上下文压缩
- Gateway 治理与安全控制
- 自动化评测与 CI 门禁
- 可观测性与告警体系
- 多 Agent 协作骨架与 Demo
- 上线治理、灰度、回滚与 Runbook
- 生产化持久化层与统一配置中心
- 分布式消息总线、任务队列、可观测性导出与 Redis 后端

## 当前完成进度（截至 2026-03-14）

### W1：基础执行框架
- 建立基础目录结构与工程骨架
- 形成 Planner / Executor / Replanner 主流程雏形
- 补齐基础文档与执行清单

### W2：Workflow 内核
- 完成 Planner-Executor-Replanner 闭环
- 支持步骤级超时、重试、幂等、取消、断点续跑
- 增加任务图质量校验与计划版本跟踪

### W3：RAG 基础能力
- 建立知识清单与检索基础模块
- 实现混合检索、重排、压缩等核心链路
- 输出 RAG 策略与知识组织相关文档

### W4：Gateway 与治理
- 完成 Tool Registry、Validator、Authorizer
- 实现限流、熔断、审计日志、错误码治理
- 补齐安全与治理相关测试、契约与说明文档

### W5：评测体系
- 建立统一指标口径与统计窗口
- 构建 `smoke` / `regression` / `adversarial` 数据集
- 实现评测 Runner、Scorer、Baseline Diff
- 接入 CI 门禁与失败样本回放能力

### W6：可观测性
- 建立 Trace / Span / 结构化日志模型
- 输出错误分桶、慢链路分析、告警评估、看板快照
- 运行评测时自动生成 `traces.jsonl`、`logs.jsonl`、`alert-report.md` 等产物

### W7：多 Agent 协作
- 定义多角色职责、SLA 与消息协议
- 实现任务分派、回调聚合、冲突仲裁、共享记忆
- 产出标准流程 / 冲突流程 Demo
- 实现单 Agent vs 多 Agent 对比评测

### W8：上线与治理
- 补齐灰度、A/B、回滚、SLA/SLO、告警升级与 Runbook
- 实现稳定分桶与实验止损路由器
- 输出容量评估、预发演练、上线复盘与下一阶段路线图

### W9：生产化状态与配置中心
- 建立持久化抽象层（4 个 Backend ABC + InMemory / SQLite 双实现）
- SQLite 单库多表，WAL 模式，SchemaManager 幂等建表
- 统一配置中心（命名空间、版本自增、watch/notify 变更推送）
- SharedMemoryStore / CircuitBreaker 注入后端，状态可跨实例恢复
- AlertManager / AbRouter 支持从 ConfigCenter 动态加载规则与实验配置
- InstanceRegistry 心跳检测 + CrossInstanceRecovery 孤儿会话恢复
- StateTracker 提供全系统状态单一视图
- 迁移脚本：init_default_config / export_config / import_config

### W10：分布式架构与基础设施接入
- 消息总线抽象（MessageBus ABC + InMemory + Redis 双实现，publish/subscribe/request-reply）
- 分布式任务队列（TaskQueue ABC + DistributedLock ABC，enqueue/dequeue/ack/nack/dead-letter）
- 可观测性导出后端（MetricsExporter + LogExporter + TraceExporter，InMemory/Prometheus/JSON/OTLP 4 实现）
- 持久化 Redis 后端（RedisSharedMemoryBackend + RedisCircuitStateBackend）
- 连接池抽象与压缩序列化工具
- TaskDispatcher 集成 MessageBus 事件广播
- Tracer / StructuredLogger 注入 Exporter 转发
- 端到端管线集成测试与多实例模拟
- 性能基准（消息吞吐、队列吞吐、Redis 读写）

## 仓库结构

- `plans/`：总体学习规划、每周方案与分周执行清单
- `src/`：当前主实现代码
  - `src/gateway/`：工具治理、权限、限流、熔断、审计
  - `src/rag/`：检索、重排、上下文压缩
  - `src/observability/`：Trace、日志、告警、看板、演练
  - `src/multi_agent/`：多 Agent 协议、分派、仲裁、共享记忆、Demo 评测
  - `src/release/`：A/B 路由、实验止损、发布治理辅助模块
  - `src/persistence/`：持久化抽象层、SQLite/Redis 后端、实例注册、状态恢复、连接池
  - `src/config_center/`：统一配置中心、watch/notify、版本管理
  - `src/messaging/`：消息总线抽象、InMemory/Redis 实现
  - `src/scheduler/`：分布式任务队列与锁抽象、InMemory/Redis 实现
  - `src/observability/exporters/`：Metrics/Log/Trace 导出后端
- `contracts/`：协议与契约文件
- `eval/`：评测数据集、评测器、报告模板、结果产物
- `docs/`：交接、评审、可观测性、安全、治理、多 Agent 文档
- `demo/`：多 Agent 业务 Demo 说明
- `tests/`：单元测试与集成测试
- `scripts/`：辅助脚本（失败样本回放、配置初始化/导出/导入）
- `observability/`：看板配置

## 当前重点产物

### 评测相关
- `eval/runner.py`
- `eval/scorer.py`
- `eval/diff.py`
- `eval/baseline/w5-baseline.json`
- `docs/ci/eval-gate.md`

### 可观测性相关
- `src/observability/tracer.py`
- `src/observability/logger.py`
- `src/observability/error_bucket.py`
- `src/observability/latency_analyzer.py`
- `src/observability/alert_manager.py`

### 多 Agent 相关
- `contracts/multi-agent-message.schema.json`
- `src/multi_agent/protocol_validator.py`
- `src/multi_agent/dispatcher.py`
- `src/multi_agent/arbitrator.py`
- `src/multi_agent/shared_memory.py`
- `src/multi_agent/evaluator.py`

### 发布治理相关
- `src/release/ab_router.py`
- `docs/release/gray-release-plan.md`
- `docs/release/rollback-policy.md`
- `docs/release/ab-experiment-spec.md`
- `docs/ops/sla-slo.md`
- `docs/runbook/incident-handling.md`

### 持久化与配置中心（W9）
- `src/persistence/interfaces.py` -- 4 个 Backend ABC
- `src/persistence/sqlite_backend.py` -- SQLite 实现
- `src/persistence/schema.py` -- 幂等 Schema 管理
- `src/persistence/instance_registry.py` -- 实例心跳
- `src/persistence/recovery.py` -- 跨实例恢复
- `src/persistence/state_tracker.py` -- 全局状态视图
- `src/config_center/config_store.py` -- 配置中心
- `docs/architecture/persistence-layer.md`
- `docs/architecture/config-center.md`
- `docs/ops/state-recovery.md`

### 分布式基础设施（W10）
- `src/messaging/interfaces.py` -- MessageBus ABC
- `src/messaging/in_memory_bus.py` / `redis_bus.py` -- 双实现
- `src/scheduler/interfaces.py` -- TaskQueue + DistributedLock ABC
- `src/scheduler/in_memory_queue.py` / `redis_queue.py` -- 双实现
- `src/observability/exporters/` -- Metrics/Log/Trace 导出器
- `src/persistence/redis_backend.py` -- Redis 持久化后端
- `src/persistence/connection_pool.py` -- 连接池
- `docs/architecture/distributed-layer.md`
- `docs/ops/distributed-deployment.md`
- `docs/ops/distributed-drill.md`

## 本地运行

### 1. 运行全部测试

```bash
python -m unittest discover -s tests
```

### 2. 运行 W5/W6 评测

```bash
python -m eval.runner --dataset eval/datasets/smoke.jsonl --output-dir eval/results/local-smoke
python -m eval.diff \
  --baseline eval/baseline/w5-baseline.json \
  --current eval/results/local-smoke/summary.json \
  --output eval/results/local-smoke/diff-report.md
```

### 3. 回放失败样本

```bash
bash scripts/replay_failed_case.sh \
  --archive eval/results/w5-smoke/failed-cases.jsonl \
  --case-id smoke_001
```

### 4. 初始化 W9 配置数据库

```bash
python scripts/init_default_config.py --db state.db
python scripts/export_config.py --db state.db --output config_backup.json
python scripts/import_config.py --db state.db --input config_backup.json
```

### 5. 运行 W7 多 Agent 对比评测

```bash
@'
from src.multi_agent.evaluator import MultiAgentEvaluator
summary = MultiAgentEvaluator().run('eval/results/w7-multi-agent')
print(summary)
'@ | python -
```

## 典型输出产物

### W5/W6 评测输出
- `summary.json`
- `report.md`
- `failed-cases.jsonl`
- `traces.jsonl`
- `logs.jsonl`
- `error-topn.md`
- `latency-breakdown.md`
- `alerts.json`
- `alert-report.md`
- `dashboard-snapshot.json`
- `incident-drill.md`

### W7 多 Agent 输出
- `eval/results/w7-multi-agent/summary.json`
- `eval/results/w7-multi-agent/report.md`
- `eval/results/w7-multi-agent/traces.jsonl`
- `eval/results/w7-multi-agent/logs.jsonl`

### W8 治理输出
- `docs/release/gray-release-plan.md`
- `docs/release/pre-prod-drill.md`
- `docs/reports/w8-capacity-report.md`
- `docs/reports/w8-drill-issues.md`
- `docs/reports/w8-launch-review.md`
- `docs/roadmap/next-phase.md`

## 当前边界与限制

- 分布式组件使用 fakeredis + threading 模拟，尚未接入真实 Redis / RabbitMQ
- 可观测性导出器实现了 Prometheus / OTLP 格式，但尚未对接真实后端
- 评测基线当前以 `smoke` 数据集为主，覆盖面仍可继续扩展
- 多 Agent 协作已支持消息总线通信，但仍为单进程多线程模拟

## 下一步方向

- 进入 `W11`：自动化治理与运营闭环
- 支持自动回放、自动演练与错误预算治理
- 接入真实基础设施（Redis / Prometheus / OTLP Collector）
- 运营控制台与周报自动生成

## 分周索引

- `plans/W1-执行清单.md`
- `plans/W2-执行清单.md`
- `plans/W3-执行清单.md`
- `plans/W4-执行清单.md`
- `plans/W5-执行清单.md`
- `plans/W6-执行清单.md`
- `plans/W7-执行清单.md`
- `plans/W8-执行清单.md`
- `plans/W9-执行清单.md`
- `plans/W10-执行清单.md`
