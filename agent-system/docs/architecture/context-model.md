# Context Model

## Layers
- System context:
  - tenant_id, environment, policy_version.
- Task context:
  - request_id, session_id, user_input, objective.
- Tool context:
  - current_tool, validated_payload, retry_budget.
- Session memory:
  - completed steps, intermediate outputs, snapshots.

## Lifecycle
1. Create context from agent request.
2. Trim context based on tool scope and token budget.
3. Persist execution snapshots at step boundaries.
4. Expire stale session memory by TTL.
5. Clean sensitive fields before logging.

## Traceability Rules
Every request must preserve:
- context_source: where each field came from.
- trim_policy: what was removed and why.
- redact_policy: what was masked before audit logging.

## Redaction Baseline
- Redact: api_key, password, access_token, ssn, phone.
- Keep: request_id, session_id, step_id, tool_id.

## Token Budget Rule
- Prefer latest 5 step summaries.
- Drop raw tool payloads first.
- Keep policy and identity metadata intact.
