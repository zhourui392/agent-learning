# 分布式基础设施层架构

## 概述

W10 在 W9 持久化抽象层基础上引入三个新基础设施模块，将 Agent 系统从单进程骨架升级为可横向扩展的分布式架构。所有组件使用 `fakeredis` + `threading` 模拟，零外部基础设施依赖。

## 架构图

```
┌─────────────────────────────────────────────────────┐
│                  Application Layer                   │
│   Dispatcher / Evaluator / DemoFlow                 │
├────────┬────────────┬──────────────┬────────────────┤
│ Message│  Task      │ Observability│  Persistence   │
│ Bus    │  Queue     │ Exporters    │  Redis Backend │
├────────┼────────────┼──────────────┼────────────────┤
│ ABC    │ ABC        │ ABC          │ ABC            │
│        │ + Lock ABC │              │ (W9 interfaces)│
├────────┼────────────┼──────────────┼────────────────┤
│InMemory│InMemory    │InMemory      │InMemory (W9)   │
│Redis   │Redis       │Prometheus    │SQLite   (W9)   │
│(fake)  │(fake)      │JSON/OTLP     │Redis    (W10)  │
└────────┴────────────┴──────────────┴────────────────┘
```

## 模块说明

### 1. 消息总线 (`src/messaging/`)

| 文件 | 职责 |
|------|------|
| `interfaces.py` | `Message` 数据模型, `MessageBus` ABC |
| `in_memory_bus.py` | threading 实现, 同步回调 |
| `redis_bus.py` | fakeredis pub/sub, 后台线程监听 |

**核心契约**:
- `publish(topic, payload)` → 发布消息
- `subscribe(topic, handler)` → 订阅主题
- `request(topic, payload, timeout)` → 同步请求-回复
- `reply(original, payload)` → 回复请求

**与 Dispatcher 集成**: `TaskDispatcher` 可选注入 `MessageBus`，enqueue 时发布 `task.assigned.{role}`，complete 时发布 `task.completed`。

### 2. 分布式调度 (`src/scheduler/`)

| 文件 | 职责 |
|------|------|
| `interfaces.py` | `TaskItem`, `TaskQueue` ABC, `DistributedLock` ABC |
| `in_memory_queue.py` | deque + Condition 实现 |
| `redis_queue.py` | RPUSH/LPOP + SET NX EX 实现 |

**TaskQueue 契约**:
- `enqueue/dequeue` → FIFO 入队出队
- `ack/nack` → 确认/拒绝（超重试进死信）
- `peek_dead_letter` → 查看死信队列

**DistributedLock 契约**:
- `acquire(lock_name, holder_id, timeout, ttl)` → 加锁
- `release(lock_name, holder_id)` → 解锁（持有者校验）
- TTL 自动过期兜底

### 3. 可观测性导出 (`src/observability/exporters/`)

| 文件 | 职责 |
|------|------|
| `interfaces.py` | `MetricsExporter`, `LogExporter`, `TraceExporter` ABC |
| `in_memory_metrics.py` | counter/gauge/histogram + snapshot |
| `prometheus_exporter.py` | prometheus_client 封装 |
| `json_log_exporter.py` | JSONL 文件写入 |
| `otlp_trace_exporter.py` | OTLP-compatible JSON 格式 |

**与现有组件集成**: `Tracer` 和 `StructuredLogger` 可选注入 exporter，自动转发 span 和 log。

### 4. 持久化 Redis 后端 (`src/persistence/`)

| 文件 | 职责 |
|------|------|
| `redis_backend.py` | `RedisSharedMemoryBackend`, `RedisCircuitStateBackend` |
| `connection_pool.py` | `ConnectionPool` ABC + Redis/SQLite 池 |
| `compression.py` | JSON + zlib 可选压缩 |

## InMemory vs Redis 对比

| 维度 | InMemory | Redis (fakeredis) |
|------|----------|-------------------|
| 延迟 | 纳秒级 | 微秒级（模拟） |
| 持久化 | 无 | 进程内模拟 |
| 分布式 | 单进程 | 模拟跨连接 pub/sub |
| 适用场景 | 单元测试、开发 | 集成测试、架构验证 |
| 真实切换 | N/A | 替换为 redis-py |

## 设计约束

1. **向后兼容**: 所有注入点 `Optional`，默认 `None` 保持原行为
2. **DDD 分层**: 新模块属 Infrastructure 层，ABC 属 Domain 端口
3. **双实现**: 每个抽象 InMemory + Redis 双实现，参数化契约测试
4. **线程安全**: InMemory 实现统一使用 `threading.Lock`/`Condition`
