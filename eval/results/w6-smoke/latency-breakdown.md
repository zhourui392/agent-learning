# Latency Breakdown

- Samples: 5
- Avg Case Latency: 0.77 ms
- P95 Case Latency: 3.21 ms

| Component | Span | Avg Duration (ms) | P95 Duration (ms) | Samples |
|-----------|------|-------------------|-------------------|---------|
| retrieval | retrieve | 0.40 | 1.44 | 4 |
| compression | compress | 0.33 | 1.11 | 4 |
| generation | build_answer | 0.14 | 0.54 | 4 |
| rerank | rerank | 0.03 | 0.05 | 4 |
| gateway | validation | 0.03 | 0.03 | 1 |
