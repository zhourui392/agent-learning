# W5 -> W6 Handover

## W5 浜や粯姒傝
- 璇勬祴瑙勮寖锛歚eval/specs/metrics-definition.md`銆乣eval/specs/stat-window.md`
- 鏁版嵁闆嗭細`eval/datasets/smoke.jsonl`銆乣eval/datasets/regression.jsonl`銆乣eval/datasets/adversarial.jsonl`
- 鎵ц涓庢墦鍒嗭細`eval/runner.py`銆乣eval/scorer.py`銆乣eval/diff.py`
- 鍩虹嚎锛歚eval/baseline/w5-baseline.json`
- 鎶ュ憡妯℃澘涓庢晠闅滃垎绫伙細`eval/reports/template.md`銆乣eval/reports/failure-buckets.md`
- CI 闂ㄧ锛歚.github/workflows/eval.yml`銆乣docs/ci/eval-gate.md`
- 澶辫触鍥炴斁锛歚scripts/replay_failed_case.sh`

## 褰撳墠杩愯鏂瑰紡
```bash
python -m unittest discover -s tests/eval
python -m eval.runner --dataset eval/datasets/smoke.jsonl --output-dir eval/results/w5-smoke
python -m eval.diff \
  --baseline eval/baseline/w5-baseline.json \
  --current eval/results/w5-smoke/summary.json \
  --output eval/results/w5-smoke/diff-report.md
scripts/replay_failed_case.sh --archive eval/results/w5-smoke/failed-cases.jsonl --case-id smoke_001
```

## W6 寤鸿浼樺厛椤?- 瑙傛祴鍩嬬偣鏍囧噯鍖栵細缁?Retrieval銆丷erank銆丆ompression銆丟ateway 鍥涙缁熶竴 trace/span 缁撴瀯銆?- 寤惰繜鎷嗚处锛氭妸 `validation`銆乣authorization`銆乣execution`銆乣generation` 鎷嗘垚鐙珛鏃跺欢鎸囨爣銆?- 澶辫触鐢诲儚澧炲己锛氬湪澶辫触褰掓。涓姞鍏ュ彫鍥?TopK銆佸帇缂╀笂涓嬫枃闀垮害銆佸伐鍏峰搷搴旀憳瑕併€?- 鍘嗗彶瓒嬪娍闈㈡澘锛氭寜澶╄仛鍚?`e2e_success_rate`銆乣avg_answer_f1`銆乣p95_latency_ms`銆?- 澶氭暟鎹泦鍩虹嚎锛歐6 鍙皢 `smoke` 鎵╁睍涓?`smoke + regression` 缁勫悎闂ㄧ锛宍adversarial` 鐢ㄤ簬 nightly銆?
## 宸茬煡闄愬埗
- 鍩虹嚎鐩墠鍐荤粨鍦?`smoke` 鏁版嵁闆嗭紝瑕嗙洊闈㈠亸淇濆畧銆?- 澶辫触鍥炴斁渚濊禆 `failed-cases.jsonl` 鏍锋湰蹇収锛屼笉浼氳嚜鍔ㄦ仮澶嶈繍琛屾椂澶栭儴渚濊禆銆?- 寤惰繜闂ㄧ瀵规瀬鐭摼璺緝鏁忔劅锛屽悗缁缓璁紩鍏ユ洿闀挎椂闂寸獥鍙ｇ殑绉诲姩骞冲潎銆?
