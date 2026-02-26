# State Machine and Recovery

## Session States
`PENDING -> RUNNING -> WAITING_TOOL -> SUCCESS | FAILED`

## Step-level State Rules
- A step enters `RUNNING` before any tool call.
- A step enters `WAITING_TOOL` during external execution.
- A step moves to `SUCCESS` when a validated tool result is persisted.
- A step moves to `FAILED` when retries are exhausted or error is non-retryable.

## Retry Model
### Retryable examples
- tool_timeout
- transient_network_error
- service_unavailable

### Non-retryable examples
- schema_validation_error
- permission_denied
- invalid_business_input

## Snapshot Strategy
Create snapshots at:
- pre-step execution
- post-step success
- final response build

Snapshot key:
- session_id + step_id + snapshot_index

## Recovery Entry
Recovery API accepts session_id and optional step_id.
- If step_id is provided, recover from exact snapshot.
- Otherwise recover from latest successful snapshot.

## Idempotency
- Write tools require idempotency_key.
- Replayed step with same idempotency_key must not duplicate side effects.
