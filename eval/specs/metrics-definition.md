# Evaluation Metrics Definition

## 1. End-to-End Metrics

### 1.1 E2E Success Rate
- **Definition**: Percentage of test cases where the full pipeline (retrieve -> validate -> authorize -> execute) produces a correct result.
- **Formula**: `successful_cases / total_cases`
- **Correct criteria**: Answer-F1 >= 0.5 AND no gateway error
- **Unit**: percentage (0-100%)

### 1.2 Step Success Rate
- **Definition**: Per-step pass rate across the pipeline.
- **Steps tracked**: retrieval, rerank, validation, authorization, execution
- **Formula**: `step_passes / step_attempts` per step
- **Unit**: percentage (0-100%)

### 1.3 P95 Latency
- **Definition**: 95th percentile end-to-end latency.
- **Scope**: From query submission to final result delivery.
- **Unit**: milliseconds
- **Breakdown**: retrieval_ms, rerank_ms, gateway_ms, execution_ms

### 1.4 Cost
- **Definition**: Resource consumption per evaluation run.
- **Components**:
  - Token count (input + output)
  - Tool invocation count
  - Retrieval call count
- **Unit**: aggregate per run

## 2. Quality Metrics

### 2.1 Recall@K
- **Definition**: Fraction of relevant documents retrieved in top-K results.
- **Formula**: `|retrieved_top_k ∩ relevant| / |relevant|`
- **K values**: 5, 10
- **Scope**: Retrieval stage only

### 2.2 MRR (Mean Reciprocal Rank)
- **Definition**: Average of reciprocal rank of first relevant result.
- **Formula**: `mean(1 / rank_of_first_relevant)`
- **Unit**: 0.0 - 1.0

### 2.3 Answer-F1
- **Definition**: Token-level F1 between generated answer and expected answer.
- **Tokenization**: word-level split with CJK character support
- **Formula**: `2 * precision * recall / (precision + recall)`
- **Unit**: 0.0 - 1.0

### 2.4 Accuracy
- **Definition**: Exact match or semantic equivalence of the final answer.
- **Evaluation**: F1 >= 0.8 counts as accurate
- **Unit**: percentage (0-100%)

### 2.5 Consistency
- **Definition**: Variance of scores across repeated runs of the same sample.
- **Method**: Run each sample N times (default 3), compute std deviation of F1
- **Threshold**: std < 0.05 is consistent
- **Unit**: standard deviation

### 2.6 Stability
- **Definition**: Percentage of samples whose score does not regress between baseline and current run.
- **Formula**: `non_regressed_samples / total_samples`
- **Regression**: current F1 < baseline F1 - 0.1
- **Unit**: percentage (0-100%)

## 3. Gateway Metrics

### 3.1 Validation Rejection Rate
- **Definition**: Percentage of calls rejected by schema/quota validation.
- **Source**: ToolValidator results
- **Target**: < 5% for well-formed agents

### 3.2 Auth Denial Rate
- **Definition**: Percentage of calls denied by authorization.
- **Source**: ToolAuthorizer denial_log
- **Target**: 0% for authorized callers

### 3.3 Circuit Open Frequency
- **Definition**: Percentage of evaluation time any circuit is in OPEN state.
- **Source**: CircuitBreaker stats
- **Target**: < 1%

### 3.4 Audit Completeness
- **Definition**: Ratio of audit entries to actual tool calls.
- **Source**: AuditLogger entry_count vs runner call count
- **Target**: 100%

## 4. Metric Consumption Format

All metrics are output as JSON for programmatic consumption:

```json
{
  "e2e_success_rate": 0.85,
  "step_success_rates": {"retrieval": 0.95, "validation": 1.0, "auth": 1.0},
  "p95_latency_ms": 120.5,
  "avg_recall_at_5": 0.73,
  "avg_recall_at_10": 0.87,
  "avg_mrr": 0.68,
  "avg_answer_f1": 0.62,
  "accuracy": 0.75,
  "consistency_std": 0.03,
  "stability": 0.92,
  "cost": {"total_tokens": 15000, "tool_calls": 45, "retrieval_calls": 15}
}
```
