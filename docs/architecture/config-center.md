# 配置中心架构

## 概述

W9 配置中心提供命名空间感知的 CRUD、自动版本递增、以及 watch/notify 变更推送机制。支持 5 种配置类型：experiment / alert_rule / tenant_policy / gateway / feature_flag。

## 核心组件

```
┌─────────────┐     watch/notify     ┌──────────────┐
│ ConfigCenter │ ──────────────────> │ ConfigWatcher │
│   (CRUD)     │                     │  (callbacks)  │
└──────┬───────┘                     └──────────────┘
       │
       ▼
┌──────────────┐
│ ConfigBackend │
│    (ABC)      │
├──────────────┤
│InMemory│SQLite│
└──────────────┘
```

## ConfigCenter API

| 方法 | 说明 |
|------|------|
| `put(ns, key, value, config_type, desc)` | 创建/更新，版本自动+1，触发 watch |
| `get(ns, key)` | 读取当前值 |
| `delete(ns, key)` | 删除，触发 watch |
| `list_namespace(ns)` | 列出命名空间内所有条目 |
| `history(ns, key)` | 返回版本历史（从旧到新） |
| `watch(ns, key, callback)` | 订阅变更（key="*" 表示通配） |
| `unwatch(ns, key, callback)` | 取消订阅 |

## Watch 机制

- 精确匹配：`watch("experiments", "exp-1", cb)` 只响应 `exp-1` 的变更
- 通配匹配：`watch("experiments", "*", cb)` 响应该命名空间所有变更
- WatchEvent 包含：old_value、new_value、old_version、new_version、event_type

## 与现有组件集成

### AlertManager

```python
# 从配置中心加载告警规则
mgr = AlertManager.from_config_center(config_center, namespace="alert_rules")
```

### AbRouter

```python
# 从配置中心加载实验配置
configs = AbRouter.from_config_center(config_center, namespace="experiments")
router = AbRouter()
decision = router.route(configs["exp-1"], "user-100")
```

## 配置类型说明

| 类型 | 命名空间建议 | 用途 |
|------|-------------|------|
| experiment | experiments | A/B 实验配置 |
| alert_rule | alert_rules | 告警规则定义 |
| tenant_policy | tenant_policies | 租户策略 |
| gateway | gateway | 网关配置（熔断/限流） |
| feature_flag | feature_flags | 特性开关 |
