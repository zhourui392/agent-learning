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

## 运行完整测试
```bash
python3 -m unittest discover -s tests
```

## 运行故障注入
```bash
./scripts/fault_injection.sh
```

## 快速检查
- 确认 `logs/audit.log` 包含 request_id、session_id、step_id、tool_id、result_status。
- 确认工具超时时返回 `tool_timeout` 或 `retry_exhausted`。
- 确认重规划成功时响应包含 `replan_history` 和 `step_id_mapping`。
- 确认幂等键不变时，重复提交不会增加已完成步骤的 attempts。
