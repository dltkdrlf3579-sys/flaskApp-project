from database_config import maybe_daily_sync_master

if __name__ == "__main__":
    print("[SYNC] Starting daily master sync...")
    maybe_daily_sync_master(force=False)
    print("[SYNC] Done.")
