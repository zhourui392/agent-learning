# 本地调试运行手册

## 前置条件
- Python 3.11 及以上版本。

## 校验契约
```bash
./scripts/validate_contracts.sh
```

## 回放示例会话
```bash
./scripts/replay_session.sh
```

## 快速检查
- 确认 `logs/audit.log` 包含 request_id、session_id、step_id、tool_id。
- 确认工具失败时会返回 retryable 标记与错误码。
- 确认幂等键不变时，回放不会重复执行已完成步骤。
