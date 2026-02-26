# Main Flow Sequence

## Request Path
1. API receives AgentRequest.
2. Validator checks request contract.
3. Planner builds ordered plan steps.
4. Executor runs tools via gateway.
5. State store persists step status and snapshots.
6. Response assembler returns AgentResponse.
7. Audit logger records final outcome.

## Mermaid
```mermaid
sequenceDiagram
    participant C as Client
    participant A as API
    participant V as Validator
    participant P as Planner
    participant E as Executor
    participant G as Tool Gateway
    participant S as State Store
    participant L as Audit Logger

    C->>A: AgentRequest
    A->>V: validate(request)
    V-->>A: ok
    A->>P: create_plan(request)
    P-->>A: plan
    A->>S: init_session
    A->>E: execute(plan)
    E->>S: mark RUNNING/WAITING_TOOL
    E->>G: invoke_tool
    G-->>E: tool_result
    E->>S: mark step SUCCESS/FAILED
    E->>L: record step event
    E-->>A: execution result
    A->>V: validate(response)
    A->>L: record final event
    A-->>C: AgentResponse
```
