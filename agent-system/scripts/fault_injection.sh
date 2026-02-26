#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$ROOT_DIR"

RUNS="${RUNS:-30}"

echo "running fault injection with RUNS=${RUNS}"
python3 - <<"PY"
import json
import random
from collections import Counter
from pathlib import Path

from src.api.app import AgentApplication

root = Path(__import__("os").environ["PYTHONPATH"])
app = AgentApplication(project_root=root)

base_request = {
    "request_id": "req-fi",
    "session_id": "sess-fi",
    "user_input": "search architecture baseline",
    "allowed_tools": ["tool.search", "tool.query_db", "tool.notify"],
    "context": {
        "system": {
            "tenant_id": "tenant-demo",
            "environment": "local",
            "policy_version": "v1",
        }
    },
    "metadata": {"recipient": "ops-team", "approval_token": "token-ok"},
}

scenarios = [
    ("ok", "search architecture baseline"),
    ("timeout", "search sleep_short"),
    ("flaky", "search flaky_twice"),
    ("force_fail", "search force_fail"),
    ("notify_deny", "notify handoff"),
]

runs = int(__import__("os").environ.get("RUNS", "30"))
error_counter = Counter()
scenario_counter = Counter()

for index in range(runs):
    scenario_name, user_input = random.choice(scenarios)
    scenario_counter[scenario_name] += 1

    request = json.loads(json.dumps(base_request))
    request["request_id"] = f"req-fi-{index}"
    request["session_id"] = f"sess-fi-{index}"
    request["user_input"] = user_input

    if scenario_name == "notify_deny":
        request["allowed_tools"] = ["tool.notify"]
        request["metadata"].pop("approval_token", None)

    if scenario_name == "timeout":
        request["allowed_tools"] = ["tool.search"]
        request["metadata"]["step_timeout_seconds"] = 1

    response = app.handle_request(request)
    if response["success"]:
        error_counter["SUCCESS"] += 1
    else:
        error_counter[response["error"]["code"]] += 1

print("scenario_count", dict(scenario_counter))
print("result_count", dict(error_counter))
PY
