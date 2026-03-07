# Tool Audit Specification

## Audit Entry Schema

Every tool invocation produces audit entries with these fields:

| Field | Type | Description |
|-------|------|-------------|
| event_id | string (UUID) | Unique identifier for this entry |
| event_type | enum | Type of event (see below) |
| timestamp | float | Unix timestamp |
| trace_id | string | Distributed trace correlation ID |
| session_id | string | User/agent session ID |
| caller_id | string | Identity of the invoker |
| tool_name | string | Tool being invoked |
| tool_version | string | Version of the tool |
| params_hash | string | SHA-256 hash of params (first 16 chars) |
| result_summary | string | Brief summary of result |
| latency_ms | float | Execution time in milliseconds |
| error | string | Error message if failed |
| metadata | dict | Additional context |

## Event Types

| Event | Trigger | Alert |
|-------|---------|-------|
| tool_call_start | Call begins | No |
| tool_call_success | Call succeeds | No |
| tool_call_failure | Call fails/errors | Yes |
| tool_call_rejected | Validation rejected | No |
| auth_denied | Authorization failed | Yes |
| circuit_opened | Circuit breaker opened | Yes |
| rate_limited | Rate limit hit | No |
| degraded | Degradation activated | No |

## Query Interface

Entries can be queried by:
- `trace_id` — all events in a single request chain
- `session_id` — all events in a user session
- `tool_name` + optional `event_type` filter

## Parameter Privacy

Raw parameters are NOT stored. Only a SHA-256 hash prefix is recorded to enable:
- Duplicate detection
- Correlation without exposing sensitive data

## Alert System

Critical events trigger registered alert handlers. Default alert events:
- `auth_denied`
- `circuit_opened`
- `tool_call_failure`

Custom alert events can be configured via `set_alert_events()`.

## Retention

Current implementation: in-memory (process-scoped). Production should use:
- Persistent storage (database/log system)
- Retention policy (e.g., 90 days)
- Log rotation
