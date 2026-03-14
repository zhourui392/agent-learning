"""Export all config entries from SQLite to a JSON file.

Usage:
    python scripts/export_config.py --db state.db --output config_backup.json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config_center.config_store import ConfigCenter
from src.persistence.schema import SchemaManager
from src.persistence.sqlite_backend import SQLiteConfigBackend


def main() -> None:
    parser = argparse.ArgumentParser(description="Export config to JSON.")
    parser.add_argument("--db", required=True, help="SQLite database path.")
    parser.add_argument("--output", required=True, help="Output JSON file path.")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    SchemaManager(conn).ensure_schema()
    backend = SQLiteConfigBackend(conn)
    center = ConfigCenter(backend=backend)

    entries = center.list_all()
    data = [
        {
            "namespace": e.namespace,
            "key": e.key,
            "value": e.value,
            "version": e.version,
            "config_type": e.config_type,
            "description": e.description,
        }
        for e in entries
    ]

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    conn.close()
    print(f"Exported {len(data)} entries to {args.output}")


if __name__ == "__main__":
    main()
