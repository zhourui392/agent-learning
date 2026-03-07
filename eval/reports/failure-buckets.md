# Failure Buckets

## 鐩殑
W5 璇勬祴缁熶竴浣跨敤 `summary.json.failure_buckets` 姹囨€诲け璐ュ師鍥狅紝骞舵妸澶辫触鏍锋湰鍐欏叆 `failed-cases.jsonl`锛屼緵鍥炴斁鍜屽畾浣嶄娇鐢ㄣ€?
## Buckets
- `quality_regression`锛氱瓟妗?F1 鏈揪鍒板噯纭巼闃堝€硷紝閫氬父鍑虹幇鍦?RAG 鍙洖姝ｇ‘浣嗗洖绛旇繃闀裤€佽繃娉涙垨鎽樿涓嶅噯銆?- `missing_required_field`锛氬伐鍏峰弬鏁扮己灏戝繀濉瓧娈碉紝琚?Validator 鎷︽埅銆?- `unauthorized`锛氳皟鐢ㄦ柟瑙掕壊銆佺鎴锋垨鏁忔劅宸ュ叿纭涓嶆弧瓒宠姹傘€?- `rate_limited`锛氳Е鍙戦檺娴侀厤棰濄€?- `circuit_open`锛氱啍鏂櫒澶勪簬鎵撳紑鐘舵€侊紝鎷掔粷鏂拌姹傘€?- `tool_execution_failed`锛氶€氳繃娌荤悊妫€鏌ュ悗锛屽伐鍏锋墽琛岄樁娈垫姏閿欍€?- `invalid_tool_name`锛氭牱鏈０鏄庣殑宸ュ叿涓嶅瓨鍦ㄤ簬娉ㄥ唽涓績銆?
## 褰掓。鏂囦欢
`failed-cases.jsonl` 姣忚涓€涓け璐ヨ褰曪紝鍖呭惈浠ヤ笅瀛楁锛?- `case_id`锛氳瘎娴嬫牱鏈?ID銆?- `trace_id`锛氳瘎娴嬮摼璺?ID锛岀敤浜庡叧鑱斿璁℃棩蹇楀拰鍥炴斁銆?- `session_id`锛氳瘎娴嬩細璇?ID銆?- `error_code`锛氬け璐ュ垎绫荤紪鐮侊紱RAG 璐ㄩ噺澶辫触鏃跺彲鑳戒负绌恒€?- `answer_f1`锛氬綋鍓嶇瓟妗堝緱鍒嗐€?- `latency_ms`锛氭湰娆℃牱鏈欢杩熴€?- `step_outcomes`锛氭楠ょ骇鎵ц缁撴灉銆?- `sample`锛氬畬鏁存牱鏈揩鐓э紝渚?`scripts/replay_failed_case.sh` 鐩存帴閲嶆斁銆?
## 浣跨敤寤鸿
- 鍏堢湅 `failure_buckets` 鍒ゆ柇澶辫触闈㈠悜璐ㄩ噺銆佹不鐞嗚繕鏄€ц兘銆?- 鍐嶆寜 `case_id` 鎴?`trace_id` 鍥炴斁鍗曚釜澶辫触鏍锋湰锛岄伩鍏嶇洿鎺ラ噸璺戞暣鍖呮暟鎹€?- 瀵?`quality_regression` 浼樺厛妫€鏌ュ彫鍥炴枃妗ｃ€佸帇缂╃粨鏋滃拰鏈€缁堝洖绛旀瀯閫犻€昏緫銆?
