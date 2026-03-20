# W11 自动化治理与运营闭环架构

## 概述

W11 在 W1-W10 基础上建立**自动化治理闭环**：流量回放 → A/B 路由 → 混沌注入 → 业务评估 → 门禁决策 → 运营报告。

## 五模块架构

```
┌─────────────────────────────────────────────────────┐
│              RegressionPipeline (编排)                │
│                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ Replay   │→ │ AbRouter │→ │ EvaluationRunner │  │
│  │ Engine   │  │ (W8)     │  │ (W5)             │  │
│  └──────────┘  └──────────┘  └──────────────────┘  │
│       ↓                            ↓                │
│  ┌──────────┐              ┌──────────────────┐    │
│  │ Chaos    │              │ Business         │    │
│  │ Injector │              │ Evaluator        │    │
│  └──────────┘              └──────────────────┘    │
│       ↓                            ↓                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│  │Resilience│  │ Error    │  │ Alert    │         │
│  │ Scorer   │  │ Budget   │  │ Manager  │         │
│  └──────────┘  └──────────┘  └──────────┘         │
│                       ↓                             │
│              ┌──────────────┐                       │
│              │ GateFunction │                       │
│              └──────────────┘                       │
│                       ↓                             │
│              ┌──────────────┐                       │
│              │ WeeklyReport │                       │
│              │ Generator    │                       │
│              └──────────────┘                       │
└─────────────────────────────────────────────────────┘
```

## 模块说明

### Module 1: Traffic Replay Engine (`src/replay/`)

- **TrafficAnonymizer**: 正则链式脱敏（手机、邮箱、身份证、姓名）
- **ReplayEngine**: 捕获、存储、加载、回放流量记录
- **ReplayScheduler**: 通过 TaskQueue 调度回放批次

### Module 2: Chaos Injection Framework (`src/chaos/`)

- **ChaosInjector**: 注入故障（延迟、错误、超时、资源耗尽）
- **ResilienceScorer**: 评分维度 — 恢复速度、错误隔离、级联故障

### Module 3: Business Metrics Evaluator (`src/evaluation/`)

- **BusinessEvaluator**: 技术 + 业务加权复合评分
- **ErrorBudgetTracker**: SLO 错误预算追踪

### Module 4: Regression Pipeline (`src/automation/`)

- **RegressionPipeline**: 编排 replay → ab_route → evaluate → chaos → gate
- **GateFunction**: P1 告警 / 评分 / 预算三重门禁

### Module 5: Ops Report (`src/ops_report/`)

- **TrendAnalyzer**: 连续下降检测回归，连续上升检测改进
- **WeeklyReportGenerator**: 从 ConfigCenter 读取历史，输出 Markdown 周报

## 事件流

```
RegressionPipeline
  ├── publish("regression.started")
  ├── publish("regression.step.replay")
  ├── publish("regression.step.ab_route")
  ├── publish("regression.step.evaluate")
  ├── publish("regression.step.chaos")
  ├── publish("regression.step.gate")
  └── publish("regression.completed")
```

## ConfigCenter Namespace

| Namespace | 消费方 | 说明 |
|-----------|--------|------|
| `replay_policy` | ReplayScheduler | 回放策略（采样率、节流、变体） |
| `chaos_scenarios` | ChaosInjector | 混沌场景定义 |
| `business_eval` | BusinessEvaluator | 评分权重与阈值 |
| `slo_targets` | ErrorBudgetTracker | SLO 目标值 |
| `gate_policy` | GateFunction | 门禁阈值 |
| `regression_results` | Pipeline(写) / Report(读) | 回归运行结果历史 |
