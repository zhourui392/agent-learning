# 流量回放操作手册

## 概述

流量回放体系支持从评测失败案例中捕获流量，脱敏后重放以验证修复效果。

## 快速开始

```python
from src.replay import InMemoryReplayEngine, ReplayPolicy, ReplayRecord, ReplayResult

# 1. 创建引擎
engine = InMemoryReplayEngine()

# 2. 加载失败案例
count = engine.load_from_jsonl("eval/results/failed-cases.jsonl")

# 3. 定义回放策略
policy = ReplayPolicy(
    throttle_rate=1.0,       # 回放速率倍数
    sample_ratio=0.5,        # 采样比例
    target_variant="control", # 目标实验变体
    max_batch_size=50,        # 单批最大记录数
)

# 4. 执行回放
def my_executor(record: ReplayRecord) -> ReplayResult:
    # 实际调用评测或服务逻辑
    return ReplayResult(record_id=record.case_id, success=True, latency_ms=10.0)

batch = engine.replay(policy, my_executor)
print(f"Replayed {len(batch.results)} records in {batch.total_duration_ms:.1f}ms")
```

## 通过 TaskQueue 调度

```python
from src.replay import ReplayScheduler
from src.scheduler.in_memory_queue import InMemoryTaskQueue
from src.config_center.config_store import ConfigCenter

cc = ConfigCenter()
cc.put("replay_policy", "default", {
    "throttle_rate": 0.5,
    "sample_ratio": 0.3,
    "max_batch_size": 20,
})

scheduler = ReplayScheduler(
    task_queue=InMemoryTaskQueue(),
    config_center=cc,
)
task_id = scheduler.schedule("eval/results/failed-cases.jsonl")
```

## 脱敏规则

默认正则规则：

| 类型 | 模式 | 替换 |
|------|------|------|
| 手机号 | `1[3-9]\d{9}` | `<PHONE>` |
| 邮箱 | RFC-like pattern | `<EMAIL>` |
| 身份证 | `\d{15,18}[Xx]?` | `<ID_CARD>` |
| 中文姓名 | `[\u4e00-\u9fff]{2,4}` | `<NAME>` |

支持自定义规则：

```python
from src.replay import TrafficAnonymizer

anon = TrafficAnonymizer(patterns=[
    (r"\d{4}-\d{4}-\d{4}-\d{4}", "<BANK_CARD>"),
])
```
