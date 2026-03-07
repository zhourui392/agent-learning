# Eval Gate

## 鐩爣
- 鍦?PR 鍜?`main` 鎺ㄩ€佹椂鎵ц W5 璇勬祴闂ㄧ銆?- 鐢?`eval/baseline/w5-baseline.json` 瀵规瘮褰撳墠 `smoke` 鏁版嵁闆嗙粨鏋溿€?- 澶辫触鏃朵繚鐣欐姤鍛娿€佸樊寮傜粨鏋滃拰澶辫触鏍锋湰褰掓。锛屼究浜庢湰鍦板洖鏀俱€?
## 娴佹按绾挎楠?1. 鎵ц `tests/eval`锛岀‘璁よ瘎鍒嗗櫒銆丷unner銆丏iff 閫昏緫鍙敤銆?2. 鎵ц `python -m eval.runner --dataset eval/datasets/smoke.jsonl --output-dir eval/results/ci-smoke`銆?3. 鎵ц `python -m eval.diff --baseline eval/baseline/w5-baseline.json --current eval/results/ci-smoke/summary.json`銆?4. 鑻ュ嚭鐜板洖褰掞紝`eval.diff` 杩斿洖闈為浂閫€鍑虹爜骞堕樆濉炲悎骞躲€?5. 鏃犺鎴愬姛鎴栧け璐ワ紝閮戒笂浼犱互涓嬩骇鐗╋細
   - `eval/results/ci-smoke/summary.json`
   - `eval/results/ci-smoke/report.md`
   - `eval/results/ci-smoke/diff-report.md`
   - `eval/results/ci-smoke/failed-cases.jsonl`

## 榛樿闂ㄧ闃堝€?- `e2e_success_rate` 涓嬮檷瓒呰繃 `5%` 鏃堕樆濉炪€?- `avg_answer_f1` 涓嬮檷瓒呰繃 `0.05` 鏃堕樆濉炪€?- `accuracy` 涓嬮檷瓒呰繃 `0.05` 鏃堕樆濉炪€?- `p95_latency_ms` 瓒呰繃鍩虹嚎 `1.2x` 鏃堕樆濉炪€?- `cost.total_tokens` 瓒呰繃鍩虹嚎 `1.2x` 鏃堕樆濉炪€?
## 鏈湴鎵ц
```bash
python -m unittest discover -s tests/eval
python -m eval.runner --dataset eval/datasets/smoke.jsonl --output-dir eval/results/local-smoke
python -m eval.diff \
  --baseline eval/baseline/w5-baseline.json \
  --current eval/results/local-smoke/summary.json \
  --output eval/results/local-smoke/diff-report.md
```

## 鍥炴斁澶辫触鏍锋湰
- 浣跨敤 `scripts/replay_failed_case.sh --case-id <case_id>` 鍥炴斁鎸囧畾澶辫触鏍锋湰銆?- 涔熷彲浣跨敤 `scripts/replay_failed_case.sh --trace-id <trace_id>` 鎸夐摼璺拷婧€?
