# ADR 0003: Tool Contract Governance by JSON Schema

- Status: Accepted
- Date: 2026-02-26

## Context
Tool calls are the highest-risk boundary in agent execution. Missing validation causes unstable behavior and poor debuggability.

## Decision
- Every tool request payload must pass JSON Schema validation before execution.
- Every tool response must use a normalized envelope:
  - success
  - data
  - error
  - retryable
- Tool invocation requires policy authorization.

## Rationale
- Enforces deterministic boundaries.
- Enables contract tests and consistent error handling.
- Improves auditability and replay quality.

## Consequences
- All new tools need schema and test fixtures.
- Schema evolution must be versioned and backward compatibility reviewed.
