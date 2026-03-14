# 持久化层架构

## 概述

W9 引入持久化抽象层，将 W1-W8 的所有内存状态迁移到可选的 SQLite 后端。采用 ABC 接口抽象，InMemory 和 SQLite 分别实现，确保向后兼容。

## 架构图

```
┌──────────────────────┐     ┌──────────────────────┐
│  SharedMemoryStore   │     │   CircuitBreaker     │
│  (W7 multi-agent)    │     │   (W4 gateway)       │
└────────┬─────────────┘     └────────┬─────────────┘
         │                            │
         ▼                            ▼
┌──────────────────┐        ┌──────────────────┐
│SharedMemoryBackend│        │CircuitStateBackend│
│      (ABC)        │        │      (ABC)        │
├──────────────────┤        ├──────────────────┤
│ InMemory │ SQLite │        │ InMemory │ SQLite │
└──────────────────┘        └──────────────────┘
                    \          /
                     ▼        ▼
               ┌─────────────────┐
               │   SQLite DB     │
               │  (WAL mode)     │
               │                 │
               │ shared_memory   │
               │ circuit_state   │
               │ config_entries  │
               │ config_history  │
               │ sessions        │
               │ instances       │
               │ schema_version  │
               └─────────────────┘
```

## 4 个后端 ABC

| ABC | 用途 | 主要方法 |
|-----|------|----------|
| `SharedMemoryBackend` | 版本化共享记忆 | get / put / delete / list_all |
| `CircuitStateBackend` | 熔断器状态 | get / put / delete / list_all |
| `ConfigBackend` | 配置条目（含历史） | get / put / delete / list_by_namespace / get_history |
| `SessionStoreBackend` | 会话状态 | get / put / delete / list_by_instance / list_by_state |

## SQLite 设计决策

1. **单库多表** -- 所有组件共享一个 `.db` 文件，零外部依赖
2. **WAL 模式** -- 支持并发读，写不阻塞读
3. **幂等 Schema** -- `SchemaManager.ensure_schema()` 可在每次启动时安全调用
4. **JSON 序列化** -- 复杂值通过 `serialization.py` 存为 JSON TEXT 列
5. **版本追踪** -- `schema_version` 表支持未来迁移

## 向后兼容

所有构造器新增参数默认为 `None`：

```python
# W7 原始用法 -- 仍然有效
store = SharedMemoryStore()

# W9 持久化用法
backend = SQLiteSharedMemoryBackend(conn)
store = SharedMemoryStore(backend=backend)
```

## SchemaManager

- `ensure_schema()` 创建所有表（IF NOT EXISTS）
- 记录 schema 版本到 `schema_version` 表
- 预留 `_migrate()` 方法用于未来版本升级
