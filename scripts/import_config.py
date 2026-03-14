"""Import config entries from a JSON file into SQLite.

Usage:
    python scripts/import_config.py --db state.db --input config_backup.json
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
    parser = argparse.ArgumentParser(description="Import config from JSON.")
    parser.add_argument("--db", required=True, help="SQLite database path.")
    parser.add_argument("--input", required=True, help="Input JSON file path.")
    args = parser.parse_args()

    input_path = Path(args.input)
    data = json.loads(input_path.read_text(encoding="utf-8"))

    conn = sqlite3.connect(args.db)
    SchemaManager(conn).ensure_schema()
    backend = SQLiteConfigBackend(conn)
    center = ConfigCenter(backend=backend)

    imported = 0
    for item in data:
        center.put(
            namespace=item["namespace"],
            key=item["key"],
            value=item["value"],
            config_type=item.get("config_type", "feature_flag"),
            description=item.get("description", ""),
        )
        imported += 1
        print(f"  put  {item['namespace']}/{item['key']}")

    conn.close()
    print(f"\nImported {imported} entries into {args.db}")


if __name__ == "__main__":
    main()
