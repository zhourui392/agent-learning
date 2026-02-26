#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$ROOT_DIR"

python3 "$ROOT_DIR/src/api/app.py" --request-file "tests/fixtures/sample_request.json"
