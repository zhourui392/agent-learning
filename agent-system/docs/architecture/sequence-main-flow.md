# 主流程时序

## 请求路径
1. API 接收 AgentRequest。
2. Validator 校验请求契约。
3. Planner 构建结构化计划（带 trace_id 与 plan_version）。
4. Executor 按依赖调度步骤（串并混合）。
5. Gateway 执行工具并返回统一结果封装。
6. 失败步骤按策略触发 Replanner（可选）。
7. State Store 持久化步骤状态、幂等键、快照。
8. API 组装 AgentResponse 并写入审计日志。

## Mermaid 时序图
```mermaid
sequenceDiagram
    participant C as 客户端
    participant A as API
    participant V as Validator
    participant P as Planner
    participant E as Executor
    participant R as Replanner
    participant G as 工具网关
    participant S as 状态存储
    participant L as 审计日志

    C->>A: AgentRequest
    A->>V: validate(request)
    V-->>A: ok
    A->>P: create_plan(request)
    P-->>A: plan(v1, trace_id)
    A->>S: init_session
    A->>E: execute(plan)
    loop each ready step
        E->>S: mark RUNNING/WAITING_TOOL
        E->>G: invoke_tool
        G-->>E: tool_result
        E->>S: mark SUCCESS/FAILED + snapshot
        E->>L: record step event
        alt retryable failure and retry exhausted
            E->>R: replan_after_failure
            R-->>E: new_plan(v+1)
            E->>S: upsert replanned steps
        end
    end
    E-->>A: execution result
    A->>V: validate(response)
    A->>L: record final event
    A-->>C: AgentResponse
```
