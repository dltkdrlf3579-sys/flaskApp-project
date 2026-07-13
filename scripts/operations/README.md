# Operational Scripts

These scripts are not part of the Flask request runtime. Run them manually only when their operation is explicitly required.

- `force_sync.py`: force-runs master and content synchronization.
- `run_daily_sync.py`: performs the normal daily master synchronization check once.

Both scripts resolve the project root themselves and can be launched from any working directory.
