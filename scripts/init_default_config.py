"""Initialize a SQLite database with default W9 configuration entries.

Usage:
    python scripts/init_default_config.py --db state.db
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config_center.config_store import ConfigCenter
from src.persistence.schema import SchemaManager
from src.persistence.sqlite_backend import SQLiteConfigBackend

_DEFAULT_CONFIGS = [
    # -- alert rules
    {
        "namespace": "alert_rules",
        "key": "low_e2e_success_rate",
        "config_type": "alert_rule",
        "value": {
            "name": "low_e2e_success_rate",
            "severity": "P1",
            "metric": "e2e_success_rate",
            "threshold": 0.75,
            "comparator": "lt",
            "route": "oncall+owner+war-room",
            "description": "E2E success rate drops below SLO.",
        },
    },
    {
        "namespace": "alert_rules",
        "key": "high_p95_latency",
        "config_type": "alert_rule",
        "value": {
            "name": "high_p95_latency",
            "severity": "P2",
            "metric": "p95_latency_ms",
            "threshold": 7.5,
            "comparator": "gt",
            "route": "owner+team-channel",
            "description": "P95 latency exceeds smoke baseline tolerance.",
        },
    },
    # -- feature flags
    {
        "namespace": "feature_flags",
        "key": "enable_multi_agent",
        "config_type": "feature_flag",
        "value": True,
        "description": "Enable multi-agent collaboration pipeline.",
    },
    {
        "namespace": "feature_flags",
        "key": "enable_ab_routing",
        "config_type": "feature_flag",
        "value": True,
        "description": "Enable A/B experiment routing.",
    },
    # -- gateway
    {
        "namespace": "gateway",
        "key": "circuit_breaker_defaults",
        "config_type": "gateway",
        "value": {
            "failure_threshold": 5,
            "recovery_timeout": 30.0,
            "success_threshold": 2,
            "window_size": 60.0,
        },
        "description": "Default circuit breaker configuration.",
    },
    # -- experiment
    {
        "namespace": "experiments",
        "key": "refund-decision-exp",
        "config_type": "experiment",
        "value": {
            "experiment_id": "refund-decision-exp",
            "default_variant": "control",
            "variants": [
                {"name": "control", "percentage": 90.0},
                {"name": "assistant_v2", "percentage": 10.0},
            ],
            "salt": "w8",
            "guardrails": [
                {"metric": "success_rate", "comparator": "lt", "threshold": 0.92},
                {"metric": "latency.p95_ms", "comparator": "gt", "threshold": 2500.0},
            ],
        },
        "description": "Refund decision experiment.",
    },
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize default W9 config.")
    parser.add_argument("--db", required=True, help="Path to SQLite database file.")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    SchemaManager(conn).ensure_schema()

    backend = SQLiteConfigBackend(conn)
    center = ConfigCenter(backend=backend)

    created = 0
    for item in _DEFAULT_CONFIGS:
        existing = center.get(item["namespace"], item["key"])
        if existing is not None:
            print(f"  skip  {item['namespace']}/{item['key']} (already exists v{existing.version})")
            continue
        center.put(
            namespace=item["namespace"],
            key=item["key"],
            value=item["value"],
            config_type=item.get("config_type", "feature_flag"),
            description=item.get("description", ""),
        )
        created += 1
        print(f"  init  {item['namespace']}/{item['key']}")

    conn.close()
    print(f"\nDone. Created {created} entries in {args.db}")


if __name__ == "__main__":
    main()
