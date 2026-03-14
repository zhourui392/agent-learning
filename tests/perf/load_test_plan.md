# Load Test Plan

## 目标
- 验证 `W8` 发布链路在目标流量下满足 `docs/ops/sla-slo.md`。
- 识别 CPU、内存、外部依赖和人工接管链路的容量瓶颈。

## 场景
- 峰值流量：模拟日常峰值 `2x` 的 30 分钟压测。
- 长稳压测：以日常均值 `1.2x` 连续运行 6 小时。
- 故障注入：模拟依赖超时、实验止损、回滚、人工接管。

## 观测指标
- `success_rate`
- `latency.p95_ms`
- `timeout_rate`
- `cpu_usage`
- `memory_usage`
- `manual_takeover_rate`

## 通过标准
- 核心 SLO 持续满足。
- 告警可触发、回滚可执行、人工接管链路可用。
