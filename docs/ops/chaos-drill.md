# 混沌演练操作手册

## 概述

混沌注入框架支持四种故障类型，用于验证系统在异常条件下的韧性。

## 故障类型

| 类型 | 说明 | 参数 |
|------|------|------|
| `latency` | 注入额外延迟 | `delay_ms`: 延迟毫秒数 |
| `error` | 随机注入错误 | `error_rate`: 错误概率 (0-1) |
| `timeout` | 模拟超时 | `timeout_ms`: 超时毫秒数 |
| `resource_exhaustion` | 模拟资源耗尽 | 无额外参数 |

## 快速开始

```python
from src.chaos import InMemoryChaosInjector, ChaosScenario, ResilienceScorer

# 1. 定义场景
scenarios = [
    ChaosScenario(
        fault_type="latency",
        target_component="rag_retriever",
        parameters={"delay_ms": 200},
        duration_seconds=30.0,
    ),
    ChaosScenario(
        fault_type="error",
        target_component="gateway",
        parameters={"error_rate": 0.3},
    ),
]

# 2. 执行混沌实验
injector = InMemoryChaosInjector()
for scenario in scenarios:
    result = injector.wrap_execution(
        scenario,
        fn=lambda: my_service.handle_request(test_request),
    )
    print(f"{scenario.fault_type}: success={result.success}, "
          f"recovery={result.recovery_time_ms:.1f}ms")

# 3. 评分
scorer = ResilienceScorer(max_recovery_ms=5000.0)
report = scorer.score(injector.collect_results())
print(f"Overall resilience: {report.overall_score:.2f}")
for weakness in report.weaknesses:
    print(f"  Weakness: {weakness}")
```

## 从 ConfigCenter 动态加载

```python
from src.config_center.config_store import ConfigCenter

cc = ConfigCenter()
cc.put("chaos_scenarios", "latency_rag", {
    "fault_type": "latency",
    "target_component": "rag",
    "parameters": {"delay_ms": 100},
    "duration_seconds": 10.0,
})

injector = InMemoryChaosInjector.from_config_center(cc)
```

## 评分维度

| 维度 | 满分条件 | 权重 |
|------|----------|------|
| 恢复速度 | recovery_time_ms / max_recovery_ms < 1 | 1/3 |
| 错误隔离 | 错误未扩散到其他组件 | 1/3 |
| 级联故障 | 无级联失败 | 1/3 |

弱点阈值：单项评分 < 0.7 标记为弱点。

## 在自动化回归中使用

混沌场景可通过 `RegressionRunConfig.chaos_scenarios` 集成到回归管线中，pipeline 自动执行注入、评分并纳入门禁决策。
