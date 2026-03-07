# W5 Evaluation Report

- Dataset: `{dataset_name}`
- Samples: `{total_samples}`

## Summary

| Metric | Value |
|--------|-------|
| E2E Success Rate | {e2e_success_rate} |
| Avg Answer-F1 | {avg_answer_f1} |
| Accuracy | {accuracy} |
| Avg Latency | {avg_latency_ms} ms |
| P95 Latency | {p95_latency_ms} ms |

## Gateway

| Metric | Value |
|--------|-------|
| Validation Rejection Rate | {validation_rejection_rate} |
| Auth Denial Rate | {auth_denial_rate} |
| Circuit Open Frequency | {circuit_open_frequency} |
| Audit Completeness | {audit_completeness} |

## Cost

| Metric | Value |
|--------|-------|
| Total Tokens | {total_tokens} |
| Tool Calls | {tool_calls} |
| Retrieval Calls | {retrieval_calls} |

## Step Success Rates

| Step | Success Rate |
|------|--------------|
{step_success_rows}

## Failure Buckets

{failure_bucket_rows}
