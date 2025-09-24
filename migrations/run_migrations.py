"""Simple migration runner for Phase 4.

This script executes SQL files located in this directory in ascending order
(001_*.sql, 002_*.sql, ...). Each file is executed within a transaction.
The code assumes PostgreSQL only, using db_connection.get_db_connection().
"""

from __future__ import annotations

import logging
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent

import sys

if str(MIGRATIONS_DIR.parent) not in sys.path:
    sys.path.insert(0, str(MIGRATIONS_DIR.parent))

from db_connection import get_db_connection


def list_migration_files() -> list[Path]:
    files = sorted(
        MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"),
        key=lambda path: path.name,
    )
    return files


def apply_migration(conn, file_path: Path) -> None:
    logging.info("[Migration] applying %s", file_path.name)
    sql = file_path.read_text(encoding="utf-8")
    cursor = conn.cursor()
    try:
        cursor.execute(sql)
    finally:
        try:
            cursor.close()
        except Exception:
            pass


def run_migrations() -> None:
    files = list_migration_files()
    if not files:
        logging.info("[Migration] no SQL files found")
        return

    conn = get_db_connection()
    try:
        for file_path in files:
            logging.info("[Migration] running %s", file_path.name)
            try:
                conn.execute("BEGIN")
                apply_migration(conn, file_path)
                conn.commit()
                logging.info("[Migration] %s applied", file_path.name)
            except Exception as exc:
                conn.rollback()
                logging.error("[Migration] %s failed: %s", file_path.name, exc)
                raise
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_migrations()
