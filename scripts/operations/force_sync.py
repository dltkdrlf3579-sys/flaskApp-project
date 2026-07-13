#!/usr/bin/env python3
"""
Force-run all master/content synchronizations using the app's adapters.

Prereqs:
- config.ini [DATABASE] db_backend=postgres and valid postgres_dsn
- IQADB_CONNECT310 available if external master/content queries are enabled

Run from any directory:
    python scripts/operations/force_sync.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from database_config import maybe_daily_sync_master, maybe_one_time_sync_content
except Exception as e:
    print(f"ERROR: failed to import sync functions from database_config: {e}")
    sys.exit(1)


def main():
    print("=== FORCED MASTER + CONTENT SYNC START ===")
    try:
        maybe_daily_sync_master(force=True)
    except Exception as e:
        print(f"ERROR during master sync: {e}")

    try:
        maybe_one_time_sync_content(force=True)
    except Exception as e:
        print(f"ERROR during content sync: {e}")

    print("=== SYNC COMPLETE (check logs above) ===")


if __name__ == '__main__':
    main()
