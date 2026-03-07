# W6 Incident Drill

- Dataset: `smoke.jsonl`
- Trigger: automated drill from latest observability artifacts

## Active Alerts

- No active alerts

## Latency Hotspots

- `retrieval.retrieve` avg=0.40ms p95=1.44ms
- `compression.compress` avg=0.33ms p95=1.11ms
- `generation.build_answer` avg=0.14ms p95=0.54ms
- `rerank.rerank` avg=0.03ms p95=0.05ms
- `gateway.validation` avg=0.03ms p95=0.03ms

## Suggested Actions

- Check dashboard snapshot for current blast radius.
- Follow on-call escalation runbook for firing alerts.
- Replay failed cases when failure buckets are non-empty.
