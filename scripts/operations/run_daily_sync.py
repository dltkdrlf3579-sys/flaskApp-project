import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database_config import maybe_daily_sync_master

if __name__ == "__main__":
    print("[SYNC] Starting daily master sync...")
    maybe_daily_sync_master(force=False)
    print("[SYNC] Done.")
