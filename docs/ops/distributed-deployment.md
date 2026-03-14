# 分布式部署指南

## 当前状态

W10 使用 `fakeredis` + `threading` 模拟所有分布式组件，零外部依赖。本文档说明如何切换到真实基础设施。

## 切换到真实 Redis

### 1. 安装依赖

```bash
pip install redis
```

### 2. 替换连接

```python
# Before (fakeredis)
import fakeredis
client = fakeredis.FakeRedis()

# After (real Redis)
import redis
client = redis.Redis(host="redis.example.com", port=6379, db=0)
```

### 3. 涉及模块

| 模块 | 类 | 修改点 |
|------|-----|--------|
| `src/messaging/redis_bus.py` | `RedisMessageBus` | 替换 `fakeredis` 为 `redis` |
| `src/scheduler/redis_queue.py` | `RedisTaskQueue`, `RedisDistributedLock` | 同上 |
| `src/persistence/redis_backend.py` | `RedisSharedMemoryBackend`, `RedisCircuitStateBackend` | 同上 |
| `src/persistence/connection_pool.py` | `RedisConnectionPool` | 使用 `redis.ConnectionPool` |

### 4. 连接池配置建议

```python
pool = redis.ConnectionPool(
    host="redis.example.com",
    port=6379,
    db=0,
    max_connections=20,
    decode_responses=True,
)
client = redis.Redis(connection_pool=pool)
```

## 切换到真实 Prometheus

### 1. 当前实现

`PrometheusMetricsExporter` 已使用 `prometheus_client` 库，无需额外修改代码。

### 2. 暴露 /metrics 端点

```python
from prometheus_client import start_http_server
start_http_server(8000)  # 在 8000 端口暴露 metrics
```

### 3. Prometheus 配置

```yaml
scrape_configs:
  - job_name: 'agent-system'
    static_configs:
      - targets: ['localhost:8000']
```

## 切换到真实 OTLP Collector

### 1. 安装依赖

```bash
pip install opentelemetry-exporter-otlp
```

### 2. 替换 OtlpJsonTraceExporter

将文件写入替换为 HTTP/gRPC 发送：

```python
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

exporter = OTLPSpanExporter(endpoint="http://collector:4317")
```

## 切换到真实消息队列

如需替换为 RabbitMQ/Kafka：

1. 实现 `MessageBus` ABC 的新子类
2. 注入到 `TaskDispatcher` 和其他消费者
3. ABC 契约测试确保行为一致
