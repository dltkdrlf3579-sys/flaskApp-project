#!/usr/bin/env python3
"""
Initialize missing base tables used by the app (works for SQLite or Postgres).

Uses the CompatConnection so SQL will be converted appropriately.

Run from project root (venv active):
    python INIT_APP_BASE_TABLES.py
"""

import sys
import sqlite3

try:
    from db_connection import get_db_connection
except Exception as e:
    print(f"ERROR: cannot import get_db_connection: {e}")
    sys.exit(1)


DDL = [
    # section_config
    '''
    CREATE TABLE IF NOT EXISTS section_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        board_type TEXT NOT NULL,
        section_key TEXT NOT NULL,
        section_name TEXT NOT NULL,
        section_order INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        is_deleted INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(board_type, section_key)
    )
    ''',

    # partner_standards_column_config (used by UI)
    '''
    CREATE TABLE IF NOT EXISTS partner_standards_column_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        column_key TEXT UNIQUE NOT NULL,
        column_name TEXT NOT NULL,
        column_type TEXT DEFAULT 'text',
        column_order INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        dropdown_options TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''',

    # safety_instruction_column_config (align to other *_column_config)
    '''
    CREATE TABLE IF NOT EXISTS safety_instruction_column_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        column_key TEXT UNIQUE NOT NULL,
        column_name TEXT NOT NULL,
        column_type TEXT DEFAULT 'text',
        column_order INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        is_deleted INTEGER DEFAULT 0,
        dropdown_options TEXT,
        tab TEXT,
        column_span INTEGER DEFAULT 1,
        linked_columns TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''',

    # accident_column_config
    '''
    CREATE TABLE IF NOT EXISTS accident_column_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        column_key TEXT UNIQUE NOT NULL,
        column_name TEXT NOT NULL,
        column_type TEXT DEFAULT 'text',
        column_order INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        is_deleted INTEGER DEFAULT 0,
        dropdown_options TEXT,
        tab TEXT,
        column_span INTEGER DEFAULT 1,
        linked_columns TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''',

    # follow_sop_column_config
    '''
    CREATE TABLE IF NOT EXISTS follow_sop_column_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        column_key TEXT UNIQUE NOT NULL,
        column_name TEXT NOT NULL,
        column_type TEXT DEFAULT 'text',
        column_order INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        is_deleted INTEGER DEFAULT 0,
        dropdown_options TEXT,
        tab TEXT,
        column_span INTEGER DEFAULT 1,
        linked_columns TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''',

    # full_process_column_config
    '''
    CREATE TABLE IF NOT EXISTS full_process_column_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        column_key TEXT UNIQUE NOT NULL,
        column_name TEXT NOT NULL,
        column_type TEXT DEFAULT 'text',
        column_order INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        is_deleted INTEGER DEFAULT 0,
        dropdown_options TEXT,
        tab TEXT,
        column_span INTEGER DEFAULT 1,
        linked_columns TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''',

    # dropdown_option_codes_v2 (used by code mappings)
    '''
    CREATE TABLE IF NOT EXISTS dropdown_option_codes_v2 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        board_type TEXT NOT NULL,
        column_key TEXT NOT NULL,
        option_code TEXT NOT NULL,
        option_value TEXT NOT NULL,
        display_order INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(board_type, column_key, option_code)
    )
    ''',
]


def main():
    conn = get_db_connection()
    cur = conn.cursor()

    for stmt in DDL:
        cur.execute(stmt)

    conn.commit()
    conn.close()
    print("Initialized/verified base tables.")


if __name__ == '__main__':
    main()

