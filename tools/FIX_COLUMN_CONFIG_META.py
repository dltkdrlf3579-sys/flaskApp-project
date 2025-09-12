#!/usr/bin/env python3
"""
컬럼 설정 메타(tab/input_type/table_group/table_type) 보강 스크립트 (모든 보드)

증상 해결 목적:
 - Admin에서 linked/popup/테이블 컬럼을 다시 수정하려고 할 때, 섹션/입력타입이 비어져서 저장이 안 되는 문제.
 - 원인: column_config의 tab, input_type, table_* 메타가 NULL/빈값이어서 UI 로직이 판단을 못함.

동작:
 - 각 보드의 *_column_config를 조회하여 아래 규칙으로 메타 보강
   1) tab이 NULL/''이면 기본값 'basic_info'
   2) column_type이 popup_*/linked_* 이거나 input_type='table'이면 input_type='table'
   3) table_group은 base key(접미사 제거)로 설정
   4) table_type은 popup_*에서 타입 매핑, linked_*는 접미사로 유추

사용:
  python tools/FIX_COLUMN_CONFIG_META.py
  python tools/FIX_COLUMN_CONFIG_META.py --dry-run
"""
import argparse
import re
import sqlite3
from typing import Dict

from db_connection import get_db_connection


BOARD_TABLES: Dict[str, str] = {
    'accident': 'accident_column_config',
    'safety_instruction': 'safety_instruction_column_config',
    'follow_sop': 'follow_sop_column_config',
    'full_process': 'full_process_column_config',
}

SUFFIXES = ['_id', '_dept', '_bizno', '_code', '_company']

POPUP_MAP = {
    'popup_person': 'person',
    'popup_company': 'company',
    'popup_department': 'department',
    'popup_building': 'building',
    'popup_contractor': 'contractor',
}

def base_key_of(key: str) -> str:
    if not isinstance(key, str):
        return ''
    bk = key
    for suf in SUFFIXES:
        if bk.endswith(suf):
            bk = bk[:-len(suf)]
            break
    return bk

def infer_table_type(col_type: str, key: str) -> str:
    if isinstance(col_type, str) and col_type in POPUP_MAP:
        return POPUP_MAP[col_type]
    # linked_* 류는 접미사로 유추
    if isinstance(key, str):
        if key.endswith('_bizno'):
            return 'company'
        if key.endswith('_dept'):
            return 'person'   # 사람 부서 연계
        if key.endswith('_code'):
            return 'department'
        if key.endswith('_company'):
            return 'contractor'
    return ''

def ensure_columns(cur, table: str, needed):
    try:
        cur.execute(f"PRAGMA table_info({table})")
        cols = [c[1] for c in cur.fetchall()]
    except Exception:
        cols = []
    for name, ddl in needed:
        if name not in cols:
            try:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
            except Exception:
                pass

def fix_board(conn, table: str, dry_run=False) -> int:
    cur = conn.cursor()
    # 필요한 메타 컬럼이 없을 수도 있음 → 보강
    ensure_columns(cur, table, [
        ('tab','TEXT'),('input_type','TEXT'),('table_group','TEXT'),('table_type','TEXT'),('table_name','TEXT'),
        ('column_span','INTEGER'),('is_deleted','INTEGER')
    ])

    rows = cur.execute(f"SELECT * FROM {table}").fetchall()
    updated = 0
    for r in rows:
        row = dict(r)
        cid = row.get('id')
        key = row.get('column_key') or ''
        ctype = (row.get('column_type') or '').strip()
        tab = (row.get('tab') or '').strip() if isinstance(row.get('tab'), str) else row.get('tab')
        itype = (row.get('input_type') or '').strip() if isinstance(row.get('input_type'), str) else row.get('input_type')
        tgroup = (row.get('table_group') or '').strip() if isinstance(row.get('table_group'), str) else row.get('table_group')
        ttype = (row.get('table_type') or '').strip() if isinstance(row.get('table_type'), str) else row.get('table_type')

        will_tab = tab or 'basic_info'
        is_tableish = bool(ctype.startswith('popup_') or ctype.startswith('linked_') or (itype == 'table'))
        will_itype = itype or ('table' if is_tableish else None)
        bk = base_key_of(key)
        will_tgroup = tgroup or (bk if is_tableish else None)
        will_ttype = ttype or (infer_table_type(ctype, key) if is_tableish else None)

        changes = {}
        if will_tab and will_tab != tab:
            changes['tab'] = will_tab
        if will_itype and will_itype != itype:
            changes['input_type'] = will_itype
        if will_tgroup and will_tgroup != tgroup:
            changes['table_group'] = will_tgroup
        if will_ttype and will_ttype != ttype:
            changes['table_type'] = will_ttype

        if not changes:
            continue
        updated += 1
        if dry_run:
            continue
        # 업데이트 실행
        sets = ", ".join([f"{k} = ?" for k in changes.keys()]) + ", updated_at = CURRENT_TIMESTAMP"
        params = list(changes.values()) + [cid]
        cur.execute(f"UPDATE {table} SET {sets} WHERE id = ?", params)

    if not dry_run:
        conn.commit()
    return updated

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--board', default='all', choices=['all'] + list(BOARD_TABLES.keys()))
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    boards = [args.board] if args.board != 'all' else list(BOARD_TABLES.keys())
    total = 0
    for b in boards:
        table = BOARD_TABLES[b]
        cnt = fix_board(conn, table, args.dry_run)
        print(f"[OK] {b}: meta fixed {cnt} rows in {table}")
        total += cnt
    conn.close()
    print(f"[DONE] total fixed: {total}")

if __name__ == '__main__':
    main()

