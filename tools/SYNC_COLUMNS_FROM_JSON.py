#!/usr/bin/env python3
"""
Sync column configurations from JSON files in ./columns into the DB.

Usage:
  python tools/SYNC_COLUMNS_FROM_JSON.py            # sync all boards present in columns/*.json
  python tools/SYNC_COLUMNS_FROM_JSON.py accident   # sync only a specific board

Notes:
- Respects config.ini [DATABASE] settings (uses Postgres when db_backend=postgres)
- Idempotent: marks old rows inactive and upserts JSON-defined columns
"""
import sys
from column_sync_service import ColumnSyncService


def main():
    svc = ColumnSyncService('portal.db', 'columns')
    if len(sys.argv) > 1:
        board = sys.argv[1]
        count = svc.sync_board(board)
        print(f"{board}: {count} columns synced")
    else:
        results = svc.sync_all_boards()
        print("Sync results:", results)


if __name__ == '__main__':
    main()

