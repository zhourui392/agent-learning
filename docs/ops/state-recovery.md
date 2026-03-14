# 状态恢复运维指南

## 概述

W9 的跨实例恢复系统通过 InstanceRegistry + CrossInstanceRecovery 实现宕机后的自动会话恢复。

## 组件

| 组件 | 职责 |
|------|------|
| InstanceRegistry | 实例注册、心跳、过期检测 |
| CrossInstanceRecovery | 扫描孤儿会话、重新分配 |
| StateTracker | 全系统状态单一视图 |

## 恢复流程

```
1. 新实例启动
2. 调用 InstanceRegistry.register() 注册自身
3. 调用 CrossInstanceRecovery.recover()
   3.1 detect_expired() 发现心跳超时的实例
   3.2 查找过期实例的 running/pending 会话
   3.3 将孤儿会话 instance_id 改为当前实例，state 改为 "recovered"
4. 通过 StateTracker.snapshot() 确认恢复结果
```

## 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| heartbeat_ttl | 30.0s | 心跳超时阈值 |

## 操作命令

### 初始化数据库

```bash
python scripts/init_default_config.py --db state.db
```

### 查看系统状态

```python
from src.persistence.state_tracker import StateTracker
tracker = StateTracker(conn)
snap = tracker.snapshot()
print(f"活跃会话: {snap.active_sessions}")
print(f"存活实例: {snap.alive_instances}")
```

### 导出/导入配置

```bash
python scripts/export_config.py --db state.db --output backup.json
python scripts/import_config.py --db state.db --input backup.json
```

## 注意事项

- 生产环境应定期调用 `heartbeat()` （建议间隔 < heartbeat_ttl / 3）
- 恢复后的会话状态为 "recovered"，业务层需根据 payload 决定是否重新执行
- SQLite WAL 模式支持并发读，但写操作仍需串行
