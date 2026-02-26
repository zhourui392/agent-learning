# Agent System W1 Baseline

This directory contains a runnable W1 architecture baseline for a production-oriented agent backend.

## What is Included
- Boundary, context, state machine, and sequence architecture docs.
- ADR records for boundary, store strategy, and tool contract governance.
- Contract-first gateway with JSON Schema validation.
- Planner + Executor + in-memory store + snapshot recovery skeleton.
- Local mock tools and end-to-end replay command.

## Directory Highlights
- `docs/architecture/`: boundary/context/state/sequence docs.
- `docs/adr/`: key architecture decisions.
- `contracts/`: request/response and tool schemas.
- `src/`: runtime modules.
- `tests/`: contract and integration tests.
- `scripts/`: schema validation and session replay scripts.

## Run Locally
```bash
cd agent-system
./scripts/validate_contracts.sh
./scripts/replay_session.sh
python3 -m unittest discover -s tests
```

## Main Flow
`request -> validate -> plan -> execute -> snapshot -> response -> audit`

## Current Scope
- W1 baseline for local development and review.
- In-memory state store (non-durable by design).
