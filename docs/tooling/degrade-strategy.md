# Tool Degradation Strategy

## Overview

When a tool becomes unavailable (circuit open, timeout, error), the system degrades gracefully instead of failing entirely.

## Degradation Paths

### 1. Fallback Tool
Use an alternative tool that provides similar (potentially reduced) functionality.

```python
DegradeStrategy(fallback_tool="search_v1", message="Using legacy search")
```

### 2. Cached Response
Return a previously cached result when the tool is temporarily unavailable.

```python
DegradeStrategy(cached_response={"result": "cached data"}, message="Serving cached result")
```

### 3. Human Handoff
Escalate to human operator when no automated fallback is suitable.

```python
DegradeStrategy(human_handoff=True, message="Requires human intervention")
```

## Circuit Breaker Integration

| Circuit State | Behavior |
|--------------|----------|
| CLOSED | Normal tool invocation |
| OPEN | Reject immediately, apply degrade strategy |
| HALF_OPEN | Allow probe call, degrade on failure |

### State Transitions

```
CLOSED --[failures >= threshold]--> OPEN
OPEN   --[recovery timeout]------> HALF_OPEN
HALF_OPEN --[success threshold]--> CLOSED
HALF_OPEN --[any failure]--------> OPEN
```

Default config: 5 failures to open, 30s recovery, 2 successes to close.

## Rate Limiter

Token bucket algorithm per caller:
- **Burst**: allows short bursts up to bucket capacity
- **Steady**: refills at configured tokens/second
- **Backoff**: exponential backoff on repeated rejections (capped)

## Degradation Priorities

1. Fallback tool (best UX, closest to normal behavior)
2. Cached response (acceptable for read-only operations)
3. Human handoff (last resort, for critical operations)
4. Error with retry guidance (if no strategy registered)
