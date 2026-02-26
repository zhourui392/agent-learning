# Local Debug Runbook

## Prerequisites
- Python 3.11+

## Validate Contracts
```bash
./scripts/validate_contracts.sh
```

## Replay Sample Session
```bash
./scripts/replay_session.sh
```

## Fast Checks
- Verify `logs/audit.log` contains request_id, session_id, step_id, tool_id.
- Verify a failed tool returns retryable flag and error code.
- Verify replay does not rerun completed steps when idempotency key is unchanged.
