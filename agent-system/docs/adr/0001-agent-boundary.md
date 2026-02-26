# ADR 0001: Single-Agent First Boundary Strategy

- Status: Accepted
- Date: 2026-02-26

## Context
The project needs a production-capable baseline quickly. Multi-agent design is planned, but early expansion without governance can increase coordination and observability complexity.

## Decision
Adopt a single-agent-first strategy for W1:
- One planner/executor flow in the same runtime process.
- Strict separation of decision, execution, and audit concerns in code structure.
- Multi-agent interfaces are defined but not fully deployed in W1.

## Rationale
- Reduces moving parts while building schema governance, replay, and recovery.
- Enables deterministic test coverage for failure and retry paths.
- Creates stable contracts for future multi-agent migration.

## Consequences
### Positive
- Faster path to a replayable end-to-end flow.
- Lower integration overhead in early weeks.

### Negative
- Limited horizontal autonomy in W1.
- Additional refactor needed when introducing distributed coordinators.

## Follow-up
- Revisit this ADR in W7 when enabling planner/executor/auditor as independent roles.
