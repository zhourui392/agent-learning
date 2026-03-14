# 分布式故障演练

## 演练场景

### 场景 1：消息总线不可用

**触发方式**: 调用 `bus.close()` 模拟总线宕机

**预期行为**:
- `TaskDispatcher` 仍正常工作（bus 仅用于事件通知，核心调度不依赖）
- 日志记录 bus 发布失败
- 新消息不会被路由

**恢复步骤**:
1. 重建 `MessageBus` 实例
2. 重新注入到 `TaskDispatcher`
3. 重新订阅所有 handler

**验证**: `test_dispatcher_without_bus_still_works` 覆盖此场景

---

### 场景 2：任务队列积压

**触发方式**: 持续 enqueue 但不 dequeue

**预期行为**:
- `queue_length()` 持续增长
- 可通过 MetricsExporter 监控 `tasks_enqueued` vs `tasks_processed` 差值
- 超时任务触发 nack → 重试 → 死信

**恢复步骤**:
1. 扩展 Worker 数量（增加 dequeue 线程）
2. 检查死信队列 `peek_dead_letter()`
3. 调整 `max_retries` 和 `processing_timeout`

---

### 场景 3：分布式锁泄漏

**触发方式**: acquire 后不 release（模拟 Worker 崩溃）

**预期行为**:
- 锁在 TTL 到期后自动释放
- 其他 Worker 在 TTL 后可获取锁
- `is_locked()` 在 TTL 后返回 `False`

**恢复步骤**:
1. 等待 TTL 自动释放（兜底机制）
2. 检查锁持有者日志
3. 调整 TTL 值（建议 2-5 倍于预期处理时间）

**验证**: `test_ttl_expiry` 覆盖此场景

---

### 场景 4：Redis 后端故障切回 InMemory

**触发方式**: Redis 连接异常

**预期行为**:
- 持久化操作失败
- 系统应能切换到 InMemory 后端继续运行（降级）

**恢复步骤**:
1. 检测 Redis 连接状态
2. 实例化 `InMemorySharedMemoryBackend` 替换
3. Redis 恢复后重新注入并同步数据

**注意**: 当前实现未自动切换，需在应用层封装降级逻辑
