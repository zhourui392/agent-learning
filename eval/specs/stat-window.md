# Statistical Window & Sampling Rules

## 1. Statistical Window

### Run-level window
- Each evaluation run processes all samples in a dataset once.
- Metrics are computed per-run and compared against the stored baseline.

### Aggregation periods
- **Per-commit**: Triggered on every PR/push (CI gate).
- **Nightly**: Full regression suite runs overnight.
- **Weekly**: Long-tail + adversarial sets run weekly.

## 2. Sampling Strategy

### Dataset tiers

| Tier | Dataset | Size | Trigger | Purpose |
|------|---------|------|---------|---------|
| Smoke | `smoke.jsonl` | 5-10 | Every commit | Fast sanity check |
| Regression | `regression.jsonl` | 15-30 | Every PR | Core quality gate |
| Adversarial | `adversarial.jsonl` | 10-20 | Nightly/Weekly | Edge cases & attacks |
| Full | All datasets | All | Release | Complete coverage |

### Sample selection rules
- **Smoke**: 1-2 samples per category, only easy/medium difficulty
- **Regression**: Full rag_v1 dataset + gateway validation samples
- **Adversarial**: Malicious inputs, privilege escalation, parameter pollution, refusal cases

## 3. Sample Labeling Schema

Each sample must include:

```json
{
  "id": "unique_id",
  "category": "factual|procedural|edge_case|multi_source|negative|gateway",
  "query": "...",
  "expected_answer": "...",
  "relevant_source_ids": ["..."],
  "difficulty": "easy|medium|hard",
  "tags": ["smoke", "regression"],
  "expect_error": null
}
```

### Extended fields for gateway samples

```json
{
  "tool_name": "web_search",
  "tool_params": {"query": "..."},
  "caller_role": "public",
  "expect_error": "UNAUTHORIZED"
}
```

## 4. Version Management

- Datasets are versioned by filename or git tag.
- Adding samples: append-only, never modify existing sample IDs.
- Removing samples: move to `datasets/archived/` with reason.
- Baseline must be re-computed when samples are added.

## 5. Statistical Significance

- Minimum sample size per category: 3
- For consistency measurement: 3 repeated runs
- Score differences < 0.05 are considered within noise
- Regression threshold: current < baseline - 0.10
