# W5 Evaluation Report

- Dataset: `smoke.jsonl`
- Samples: `5`

## Summary

| Metric | Value |
|--------|-------|
| E2E Success Rate | 80.00% |
| Avg Answer-F1 | 0.7810 |
| Accuracy | 60.00% |
| Avg Latency | 0.36 ms |
| P95 Latency | 1.25 ms |

## Gateway

| Metric | Value |
|--------|-------|
| Validation Rejection Rate | 0.00% |
| Auth Denial Rate | 0.00% |
| Circuit Open Frequency | 0.00% |
| Audit Completeness | 100.00% |

## Cost

| Metric | Value |
|--------|-------|
| Total Tokens | 183 |
| Tool Calls | 1 |
| Retrieval Calls | 4 |

## Step Success Rates

| Step | Success Rate |
|------|--------------|
| authorization | 100.00% |
| compression | 100.00% |
| execution | 100.00% |
| rate_limit | 100.00% |
| rerank | 100.00% |
| retrieval | 100.00% |
| validation | 100.00% |

## Failure Buckets

- `quality_regression`: 1
