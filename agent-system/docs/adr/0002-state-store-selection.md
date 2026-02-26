# ADR 0002: In-Memory Store for W1, Pluggable Persistent Store Later

- Status: Accepted
- Date: 2026-02-26

## Context
W1 needs a fast, testable recovery baseline with minimal operational dependencies.

## Decision
- Use an in-memory state store for W1 development and tests.
- Define store and snapshot interfaces to allow Redis/PostgreSQL migration in W2+.

## Rationale
- Simplifies local replay and deterministic tests.
- Avoids early infrastructure lock-in.

## Consequences
- State is not durable across process restarts in W1.
- Production rollout requires persistent backend integration.
