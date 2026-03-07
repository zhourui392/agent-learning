#!/usr/bin/env bash
set -euo pipefail

ARCHIVE_PATH="eval/results/w5-smoke/failed-cases.jsonl"
CASE_ID=""
TRACE_ID=""
OUTPUT_DIR=""

resolve_python() {
  if command -v python >/dev/null 2>&1; then
    echo "python"
    return
  fi
  if command -v python3 >/dev/null 2>&1; then
    echo "python3"
    return
  fi
  if command -v python.exe >/dev/null 2>&1; then
    echo "python.exe"
    return
  fi
  echo ""
}

usage() {
  echo "Usage: scripts/replay_failed_case.sh [--archive <path>] (--case-id <id> | --trace-id <id>) [--output-dir <dir>]" >&2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --archive)
      ARCHIVE_PATH="$2"
      shift 2
      ;;
    --case-id)
      CASE_ID="$2"
      shift 2
      ;;
    --trace-id)
      TRACE_ID="$2"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$CASE_ID" && -z "$TRACE_ID" ]]; then
  usage
  exit 1
fi

if [[ ! -f "$ARCHIVE_PATH" ]]; then
  echo "Archive not found: $ARCHIVE_PATH" >&2
  exit 1
fi

REPLAY_KEY="${CASE_ID:-$TRACE_ID}"
OUTPUT_DIR="${OUTPUT_DIR:-eval/results/replay-$REPLAY_KEY}"
PYTHON_BIN="${PYTHON_BIN:-$(resolve_python)}"
TMP_DIR="$(mktemp -d)"
DATASET_PATH="$TMP_DIR/replay.jsonl"
trap 'rm -rf "$TMP_DIR"' EXIT

if [[ -z "$PYTHON_BIN" ]]; then
  echo "Python interpreter not found in PATH" >&2
  exit 1
fi

"$PYTHON_BIN" - "$ARCHIVE_PATH" "$DATASET_PATH" "$CASE_ID" "$TRACE_ID" <<'PY'
import json
import pathlib
import sys

archive_path, dataset_path, case_id, trace_id = sys.argv[1:5]
selected = None
for raw_line in pathlib.Path(archive_path).read_text(encoding="utf-8").splitlines():
    if not raw_line.strip():
        continue
    record = json.loads(raw_line)
    if case_id and record.get("case_id") == case_id:
        selected = record
        break
    if trace_id and record.get("trace_id") == trace_id:
        selected = record
        break
if selected is None:
    raise SystemExit("No matching failed case found in archive")
pathlib.Path(dataset_path).write_text(
    json.dumps(selected["sample"], ensure_ascii=False) + "\n",
    encoding="utf-8",
)
print(json.dumps({
    "case_id": selected.get("case_id"),
    "trace_id": selected.get("trace_id"),
    "dataset_path": dataset_path,
}, ensure_ascii=False))
PY

"$PYTHON_BIN" -m eval.runner --dataset "$DATASET_PATH" --output-dir "$OUTPUT_DIR"
echo "Replay output written to $OUTPUT_DIR"
