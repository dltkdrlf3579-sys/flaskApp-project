#!/usr/bin/env python3
"""
Force-reset safety_instruction_column_config to a clean, working set.

What it does:
  1) Backs up current safety_instruction_column_config to a timestamped table
  2) Deletes all rows from safety_instruction_column_config
  3) Inserts a curated set of columns with correct keys, labels, types, tabs

Usage (run from project root):
  python tools/RESET_SI_COLUMNS.py

Idempotent enough to run again — each run creates a new backup.
"""
import time
from db_connection import get_db_connection


def backup(cur):
    ts = time.strftime('%Y%m%d_%H%M%S')
    backup_table = f"safety_instruction_column_config_backup_{ts}"
    cur.execute(f"CREATE TABLE {backup_table} AS SELECT * FROM safety_instruction_column_config")
    return backup_table


def ensure_table(conn):
    cur = conn.cursor()
    try:
        cur.execute(
            """
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
            """
        )
    except Exception:
        pass


def reset_columns(conn):
    """Wipe and insert curated columns (keys must match data/custom_data)."""
    # Define columns: key, name, type, tab
    # Types: text | date | dropdown | textarea | number | popup_person | popup_company | popup_department | linked | linked_dept
    cols = []

    order = 0
    def add(key, name, ctype='text', tab='basic_info'):
        nonlocal order
        order += 1
        cols.append({
            'column_key': key,
            'column_name': name,
            'column_type': ctype,
            'column_order': order,
            'tab': tab,
            'is_active': 1,
            'is_deleted': 0,
        })

    # Basic info
    add('issue_number', '발부번호', 'text', 'basic_info')
    add('created_at', '등록일', 'date', 'basic_info')

    # Issuer (person)
    add('issuer', '발행인(이름)', 'popup_person', 'basic_info')
    add('issuer_id', '발행인 ID', 'linked', 'basic_info')
    add('issuer_dept', '발행부서', 'linked_dept', 'basic_info')
    add('issuer_incharge_dept', '징계 발의부서', 'popup_department', 'basic_info')

    # Classification / employment
    add('classification', '분류', 'dropdown', 'basic_info')
    add('employment_type', '고용형태', 'dropdown', 'basic_info')

    # Companies
    add('primary_company', '1차사명', 'popup_company', 'basic_info')
    add('primary_company_bizno', '1차사명 사업자번호', 'linked', 'basic_info')
    add('secondary_company', '하도사명', 'popup_company', 'basic_info')
    add('secondary_company_bizno', '하도사명 사업자번호', 'linked', 'basic_info')

    # Disciplined person (contractor/worker)
    add('disciplined_person', '징계대상자 성함', 'popup_contractor', 'basic_info')
    add('disciplined_person_id', 'PCMS ID', 'linked', 'basic_info')
    add('disciplined_person_company', '징계대상자 소속업체', 'linked', 'basic_info')
    add('disciplined_person_bizno', '소속업체 사업자번호', 'linked', 'basic_info')

    # Other basics
    add('birth', '생년월일', 'date', 'basic_info')
    add('GBM', 'GBM', 'text', 'basic_info')
    add('business_division', '사업부', 'text', 'basic_info')
    add('team', '팀', 'text', 'basic_info')
    add('dept', '소속부서', 'text', 'basic_info')

    # Violation info
    add('violation_date', '위반일자', 'date', 'violation_info')
    add('discipline_date', '징계일자', 'date', 'violation_info')
    add('discipline_type', '징계유형', 'dropdown', 'violation_info')
    add('accident_number', '사고번호', 'text', 'violation_info')
    add('accident_type', '사고유형', 'dropdown', 'violation_info')
    add('accident_grade', '사고등급', 'dropdown', 'violation_info')
    add('violation_grade', '환경안전수칙 위반등급', 'dropdown', 'violation_info')
    add('violation_type', '위반유형', 'dropdown', 'violation_info')
    add('violation_content', '위반내용', 'textarea', 'violation_info')
    add('access_ban_start_date', '출입정지 시작일', 'date', 'violation_info')
    add('access_ban_end_date', '출입정지 종료일', 'date', 'violation_info')
    add('period', '기간', 'text', 'violation_info')
    add('work_grade', '작업등급', 'dropdown', 'violation_info')
    add('penalty_points', '감점', 'number', 'violation_info')

    cur = conn.cursor()
    # Wipe
    cur.execute("DELETE FROM safety_instruction_column_config")

    # Insert
    for c in cols:
        cur.execute(
            """
            INSERT INTO safety_instruction_column_config
                (column_key, column_name, column_type, column_order, is_active, is_deleted, tab, updated_at)
            VALUES (?, ?, ?, ?, 1, 0, ?, CURRENT_TIMESTAMP)
            """,
            (
                c['column_key'], c['column_name'], c['column_type'], c['column_order'], c['tab']
            )
        )

    conn.commit()
    return len(cols)


def main():
    conn = get_db_connection()
    ensure_table(conn)
    cur = conn.cursor()
    bkt = backup(cur)
    conn.commit()
    print(f"Backup created: {bkt}")
    count = reset_columns(conn)
    conn.close()
    print(f"Inserted {count} safety_instruction columns.")
    print("Done. Restart server and verify UI (list/detail/register).")


if __name__ == '__main__':
    main()

