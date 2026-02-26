# Agent Boundary Baseline

## Scope
This document defines a production-oriented baseline for single-agent and multi-agent responsibilities.

## Core Scenarios
### Scenario A: High Frequency - Customer FAQ Lookup
- Input: user question, locale, tenant_id.
- Output: concise answer with source snippets.
- Failure path: retrieval timeout or empty recall.
- Human handoff: route to support queue when confidence < 0.6.

### Scenario B: High Complexity - Multi-step Data Analysis
- Input: analysis prompt, metric definitions, time range.
- Output: aggregated result, assumptions, and confidence.
- Failure path: intermediate tool failure or inconsistent data.
- Human handoff: reviewer validates generated SQL and summary.

### Scenario C: High Cost of Failure - Notification Automation
- Input: notification intent, recipients, approval_token.
- Output: send status and audit_id.
- Failure path: permission deny, duplicate send, channel outage.
- Human handoff: manual approval and resend decision.

## Responsibility Boundaries
### Single Agent (Default)
- Owns intent parsing, plan generation, tool invocation, and result synthesis.
- Operates within strict tool policy and contract validation.
- Writes full audit trail for each plan step.

### Multi Agent (Future)
- Planner Agent: decomposes task and dependency graph.
- Executor Agent: performs tool calls and reports structured outcomes.
- Auditor Agent: verifies policy, schema, and risk thresholds.
- Coordinator: resolves conflicts and merges final response.

## Decision / Execution / Audit Separation
- Decision owner: planner role.
- Execution owner: executor role.
- Audit owner: gateway + audit logger.

## Non-functional Targets (W1 Baseline)
- SLO:
  - E2E success rate >= 95% on smoke set.
  - P95 latency <= 8s for single-tool flow.
- Cost ceiling:
  - Average tool calls per request <= 3.
  - Average token budget <= 8k per request.
- Minimum observability:
  - Mandatory fields: request_id, session_id, step_id, tool_id, duration_ms, result_status.

## Risk Controls
- Reject any tool call without schema validation.
- Stop execution on non-retryable errors.
- Require explicit idempotency key for write actions.
