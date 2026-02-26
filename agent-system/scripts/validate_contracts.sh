#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$ROOT_DIR"

echo "[1/2] checking schema JSON files"
python3 - <<"PY"
import json
import os
from pathlib import Path

contracts_root = Path(os.environ["PYTHONPATH"]) / "contracts"
for schema_file in sorted(contracts_root.rglob("*.json")):
    with schema_file.open("r", encoding="utf-8") as fh:
        json.load(fh)
print("schema json parse check passed")
PY

echo "[2/2] running contract tests"
python3 -m unittest tests.contract.test_tool_contracts

echo "contract validation completed"
