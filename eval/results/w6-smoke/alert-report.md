# Alert Evaluation

| Rule | Severity | Status | Metric | Actual | Threshold | Route |
|------|----------|--------|--------|--------|-----------|-------|
| low_e2e_success_rate | P1 | ok | e2e_success_rate | 0.8000 | 0.7500 | oncall+owner+war-room |
| high_p95_latency | P2 | ok | p95_latency_ms | 3.2108 | 7.5000 | owner+team-channel |
| tool_execution_failures | P1 | ok | failure_buckets.tool_execution_failed | 0.0000 | 1.0000 | oncall+owner+war-room |
| rate_limited_burst | P2 | ok | failure_buckets.rate_limited | 0.0000 | 5.0000 | owner+team-channel |
| token_cost_spike | P2 | ok | cost.total_tokens | 183.0000 | 240.0000 | owner+team-channel |
