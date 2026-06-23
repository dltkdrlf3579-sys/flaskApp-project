#!/usr/bin/env python3
"""
보드별 컬럼 키 일괄 리네임(관리자 컬럼 설정 + 캐시 데이터 custom_data 동시 반영)

사용 예:
  # 안전지시서: 레거시 키를 표준 키로 변경
  python tools/RENAME_KEYS.py --board safety_instruction \
    --map "primary_business_number:primary_company_bizno;subcontractor_business_number:subcontractor_bizno"

  # 매핑을 파일(JSON)로 전달
  python tools/RENAME_KEYS.py --board accident --json mappings.json

동작:
  1) column_config 테이블에서 column_key를 old -> new로 변경(충돌 없을 때)
  2) *_cache.custom_data 안의 키 old -> new로 변경(값 보존, new가 없을 때만 덮어씀)
  3) (옵션) 캐시 테이블의 top-level 컬럼에도 old가 있으면 new로 복사 시도

주의:
  - column_config에 이미 new 키가 존재하면 column_key 변경은 skip (데이터만 정리)
  - 되돌리기 전에 DB 백업 권장
"""
import argparse
import json
import sqlite3
from typing import Dict, List, Tuple

from db_connection import get_db_connection


BOARD_META = {
    'accident': {
        'config': 'accident_column_config',
        'cache':  'accidents_cache',
    },
    'safety_instruction': {
        'config': 'safety_instruction_column_config',
        'cache':  'safety_instructions_cache',
    },
    'follow_sop': {
        'config': 'follow_sop_column_config',
        'cache':  'follow_sop_cache',
    },
    'full_process': {
        'config': 'full_process_column_config',
        'cache':  'full_process_cache',
    },
}


def parse_map_arg(s: str) -> Dict[str, str]:
    m: Dict[str, str] = {}
    if not s:
        return m
    parts = [p.strip() for p in s.split(';') if p.strip()]
    for p in parts:
        if ':' not in p:
            continue
        old, new = p.split(':', 1)
        old = old.strip()
        new = new.strip()
        if old and new and old != new:
            m[old] = new
    return m


def load_json_map(path: str) -> Dict[str, str]:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    # dict 형태 가정 {old:new, ...}
    out: Dict[str, str] = {}
    for k, v in data.items():
        if isinstance(k, str) and isinstance(v, str) and k and v and k != v:
            out[k] = v
    return out


def rename_in_config(conn, table: str, mappings: Dict[str, str]) -> Tuple[int, int]:
    """column_config에서 column_key rename (충돌 없을 때만).
    Returns: (renamed, skipped)
    """
    renamed = skipped = 0
    cur = conn.cursor()
    for old, new in mappings.items():
        try:
            # new가 이미 있으면 skip
            cur.execute(f"SELECT COUNT(*) FROM {table} WHERE LOWER(column_key)=LOWER(?)", (new,))
            if (cur.fetchone() or [0])[0] > 0:
                skipped += 1
                continue
            cur.execute(
                f"UPDATE {table} SET column_key = ?, updated_at = CURRENT_TIMESTAMP WHERE LOWER(column_key)=LOWER(?)",
                (new, old)
            )
            if getattr(cur, 'rowcount', 0) > 0:
                renamed += 1
        except Exception:
            skipped += 1
    return renamed, skipped


def normalize_json(v):
    if not v:
        return {}
    if isinstance(v, dict):
        return v
    if isinstance(v, str):
        try:
            return json.loads(v) if v.strip() else {}
        except Exception:
            return {}
    return {}


def rename_in_cache_custom_data(conn, cache_table: str, mappings: Dict[str, str]) -> int:
    """캐시 테이블 custom_data 키를 old->new로 변경 (new가 없을 때만 복사)"""
    cur = conn.cursor()
    updated_rows = 0
    rows = cur.execute(f"SELECT id, custom_data FROM {cache_table}").fetchall()
    for r in rows:
        rid = r[0] if not isinstance(r, dict) else r['id']
        raw = r[1] if not isinstance(r, dict) else r['custom_data']
        cd = normalize_json(raw)
        changed = False
        for old, new in mappings.items():
            if old in cd and (new not in cd or cd.get(new) in (None, '', [])):
                cd[new] = cd[old]
                del cd[old]
                changed = True
        if changed:
            try:
                cur.execute(
                    f"UPDATE {cache_table} SET custom_data = ? WHERE id = ?",
                    (json.dumps(cd, ensure_ascii=False), rid)
                )
                updated_rows += 1
            except Exception:
                # Postgres용
                cur.execute(
                    f"UPDATE {cache_table} SET custom_data = %s WHERE id = %s",
                    (json.dumps(cd, ensure_ascii=False), rid)
                )
                updated_rows += 1
    return updated_rows


def maybe_copy_top_level(conn, cache_table: str, mappings: Dict[str, str]) -> int:
    """캐시 top-level 컬럼에도 old가 있으면 new로 복사(new가 없을 때만)"""
    cur = conn.cursor()
    try:
        cur.execute(f"PRAGMA table_info({cache_table})")
        cols = [c[1] for c in cur.fetchall()]
    except Exception:
        cols = []
    applied = 0
    for old, new in mappings.items():
        if old in cols and new in cols:
            try:
                cur.execute(
                    f"UPDATE {cache_table} SET {new} = COALESCE({new}, {old}) WHERE ({new} IS NULL OR {new}='') AND {old} IS NOT NULL"
                )
                applied += getattr(cur, 'rowcount', 0) or 0
            except Exception:
                # 타입/DDL 차이로 실패해도 전체 진행에는 영향 없게
                pass
    return applied


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--board', required=True, choices=list(BOARD_META.keys()))
    ap.add_argument('--map', help='old:new;old2:new2 형태')
    ap.add_argument('--json', dest='json_path', help='매핑 JSON 파일 경로')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    mappings: Dict[str, str] = {}
    if args.map:
        mappings.update(parse_map_arg(args.map))
    if args.json_path:
        mappings.update(load_json_map(args.json_path))
    if not mappings:
        print('[ERROR] 매핑이 비어있습니다. --map 또는 --json 사용')
        return

    meta = BOARD_META[args.board]
    config_table = meta['config']
    cache_table = meta['cache']

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print(f"[START] board={args.board} mappings={mappings}")
    # 1) column_config 키 rename
    renamed = skipped = 0
    if not args.dry_run:
        r, s = rename_in_config(conn, config_table, mappings)
        renamed += r; skipped += s
        print(f" - column_config: renamed={renamed}, skipped={skipped}")
    else:
        print(" - column_config: DRY-RUN (skip)")

    # 2) cache custom_data 키 rename
    updated_rows = rename_in_cache_custom_data(conn, cache_table, mappings) if not args.dry_run else 0
    print(f" - cache.custom_data updated_rows={updated_rows}")

    # 3) top-level 컬럼 복사 시도
    moved = maybe_copy_top_level(conn, cache_table, mappings) if not args.dry_run else 0
    if moved:
        print(f" - cache top-level columns copied={moved}")

    if not args.dry_run:
        conn.commit()
    conn.close()
    print("[DONE]")


if __name__ == '__main__':
    main()

