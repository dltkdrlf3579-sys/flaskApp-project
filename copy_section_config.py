#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""section_config 데이터 복사"""
import sqlite3
from db_connection import get_db_connection

sqlite_conn = sqlite3.connect('portal.db')
sqlite_conn.row_factory = sqlite3.Row
pg_conn = get_db_connection()

cursor = sqlite_conn.cursor()
cursor.execute("SELECT * FROM section_config")
rows = cursor.fetchall()

pg_cursor = pg_conn.cursor()

for row in rows:
    data = dict(row)
    pg_cursor.execute("""
        INSERT INTO section_config 
        (board_type, section_key, section_name, section_order, is_active, is_deleted)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (board_type, section_key) DO UPDATE SET
        section_name = EXCLUDED.section_name,
        section_order = EXCLUDED.section_order,
        is_active = EXCLUDED.is_active,
        is_deleted = EXCLUDED.is_deleted
    """, (
        data['board_type'],
        data['section_key'],
        data['section_name'],
        data.get('section_order', 0),
        int(data.get('is_active', 1)),
        int(data.get('is_deleted', 0))
    ))

pg_conn.commit()
print(f"Copied {len(rows)} section_config rows")

sqlite_conn.close()
pg_conn.close()