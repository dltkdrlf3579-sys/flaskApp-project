# Flask Portal Restore Package

This package was generated on 2025-08-20 03:25:20 KST.

## How to run
1. Create venv (optional) and install requirements:
   pip install -r requirements.txt

2. Start the app:
   python app.py

- If `config.ini` exists, the app will use its values. Otherwise, copy `config_template.ini` to `config.ini` and adjust.
- If `portal.db` is missing, the app will auto-create tables and seed sample data on first run.

## Notes
- `uploads/` is included as an empty folder for file uploads.
- Database file `portal.db` is **not** included in this package. It is recreated automatically on first run with sample data.
