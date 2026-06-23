#!/usr/bin/env python3
"""
메인 테이블 → 캐시 테이블 스키마+데이터 동기화 스크립트 (보드 공통)

목표:
  - 메인 테이블 컬럼을 캐시 테이블에 동일하게 추가(누락분만)
  - 메인 데이터를 캐시에 accident_number/issue_number/work_req_no/fullprocess_number 기준 업서트
  - 캐시에 custom_data, is_deleted 컬럼을 보장(없으면 생성)

사용:
  python tools/SYNC_CACHE_FROM_MAIN.py           # 모든 보드 사고/지시서/FS/FP 동기화
  python tools/SYNC_CACHE_FROM_MAIN.py --board accident
  python tools/SYNC_CACHE_FROM_MAIN.py --dry-run  # 쓰기 없이 시뮬레이션

주의:
  - 캐시를 단일 진실(SOT)로 운영할 경우, 메인은 외부 동기화 소스(읽기 전용)로만 사용.
  - 본 스크립트는 컬럼 삭제는 하지 않음(누락 컬럼만 추가).
"""
import argparse
import json
import sqlite3
from typing import List, Tuple

from db_connection import get_db_connection
from db.upsert import safe_upsert


BOARD_CONFIGS = {
    'accident': {
        'main_table': 'accidents',
        'cache_table': 'accidents_cache',
        'pk': 'accident_number',
    },
    'safety_instruction': {
        'main_table': 'safety_instructions',
        'cache_table': 'safety_instructions_cache',
        'pk': 'issue_number',
    },
    'follow_sop': {
        'main_table': 'follow_sop',
        'cache_table': 'follow_sop_cache',
        'pk': 'work_req_no',
    },
    'full_process': {
        'main_table': 'full_process',
        'cache_table': 'full_process_cache',
        'pk': 'fullprocess_number',
    },
}


def has_table(conn, table: str) -> bool:
    cur = conn.cursor()
    try:
        cur.execute(f"PRAGMA table_info({table})")
        return bool(cur.fetchall())
    except Exception:
        try:
            cur.execute(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = %s",
                (table,)
            )
            return (cur.fetchone() or [0])[0] > 0
        except Exception:
            return False


def get_columns(conn, table: str) -> List[Tuple[str, str]]:
    cur = conn.cursor()
    cols = []
    try:
        # SQLite
        cur.execute(f"PRAGMA table_info({table})")
        for c in cur.fetchall():
            try:
                cols.append((c[1], c[2]))
            except Exception:
                # dict-like
                cols.append((c['name'], c['type']))
    except Exception:
        # Postgres
        try:
            cur.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = %s
                ORDER BY ordinal_position
                """,
                (table,)
            )
            for r in cur.fetchall():
                cols.append((r[0] if not isinstance(r, dict) else r['column_name'],
                             r[1] if not isinstance(r, dict) else r['data_type']))
        except Exception:
            pass
    return cols


def ensure_cache_table(conn, cache_table: str, pk: str):
    cur = conn.cursor()
    # 최소 테이블 생성
    try:
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {cache_table} (
                id INTEGER PRIMARY KEY AUTOINCREMENT
            )
            """
        )
    except Exception:
        pass
    # pk/custom_data/is_deleted 보강
    try:
        cur.execute(f"PRAGMA table_info({cache_table})")
        existing = [c[1] for c in cur.fetchall()]
    except Exception:
        existing = []
    if pk not in existing:
        try:
            cur.execute(f"ALTER TABLE {cache_table} ADD COLUMN {pk} TEXT")
        except Exception:
            pass
    for cn, ct in [('custom_data','TEXT'),('is_deleted','INTEGER')]:
        if cn not in existing:
            try:
                cur.execute(f"ALTER TABLE {cache_table} ADD COLUMN {cn} {ct}")
            except Exception:
                pass
    # 유니크 인덱스
    try:
        cur.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS idx_{cache_table}_{pk} ON {cache_table}({pk})")
    except Exception:
        pass

    # Postgres: id 시퀀스가 뒤처진 경우를 방지하기 위해 MAX(id)+1로 리셋
    try:
        if getattr(conn, 'is_postgres', False):
            # 일부 환경에서 id 컬럼이 없을 수 있으므로 존재 확인
            cur.execute(
                "SELECT COUNT(*) FROM information_schema.columns WHERE table_name = %s AND column_name = 'id'",
                (cache_table,)
            )
            has_id = (cur.fetchone() or [0])[0] > 0
            if has_id:
                cur.execute(
                    """
                    SELECT setval(
                        pg_get_serial_sequence(%s, 'id'),
                        COALESCE((SELECT MAX(id) FROM %s), 0) + 1,
                        false
                    )
                    """,
                    (cache_table, cache_table)
                )
    except Exception:
        # SQLite 또는 시퀀스가 없는 경우 무시
        pass


def add_missing_columns(conn, cache_table: str, main_cols: List[Tuple[str, str]]):
    # 캐시에 없는 메인 컬럼 추가(유형은 보수적으로 TEXT)
    cur = conn.cursor()
    try:
        cur.execute(f"PRAGMA table_info({cache_table})")
        cache_cols = [c[1] for c in cur.fetchall()]
    except Exception:
        cache_cols = []
    for name, _dtype in main_cols:
        if name and name not in cache_cols:
            try:
                cur.execute(f"ALTER TABLE {cache_table} ADD COLUMN {name} TEXT")
            except Exception:
                pass


def normalize_json(v):
    if v is None:
        return {}
    if isinstance(v, dict):
        return v
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return {}
        try:
            return json.loads(s)
        except Exception:
            return {}
    return {}


def sync_board(conn, key: str, dry_run=False):
    cfg = BOARD_CONFIGS[key]
    main, cache, pk = cfg['main_table'], cfg['cache_table'], cfg['pk']
    if not has_table(conn, main):
        print(f"[SKIP] {key}: main '{main}' 없음")
        return
    ensure_cache_table(conn, cache, pk)
    main_cols = get_columns(conn, main)
    add_missing_columns(conn, cache, main_cols)

    # 소스 데이터 로딩(삭제 제외 시도)
    cur = conn.cursor()
    where_notdel = '1=1'
    try:
        cur.execute(f"PRAGMA table_info({main})")
        names = [c[1] for c in cur.fetchall()]
        if 'is_deleted' in names:
            # SQLite식 조건
            where_notdel = "(is_deleted = 0 OR is_deleted IS NULL)"
    except Exception:
        # Postgres 조건: is_deleted::int = 0 같은 변환은 compat가 처리
        where_notdel = '1=1'

    rows = conn.execute(f"SELECT * FROM {main} WHERE {where_notdel}").fetchall()
    migrated = updated = skipped = 0

    for r in rows:
        row = dict(r)
        pk_val = row.get(pk)
        if not pk_val:
            skipped += 1
            continue

        # 캐시에 쓸 데이터 구성(메인 컬럼 그대로)
        data = {}
        for name, _ in main_cols:
            if name in row:
                val = row.get(name)
                # 날짜타입은 문자열화(호환용)
                if name.endswith('_date') or name.endswith('_at'):
                    try:
                        val = str(val) if val is not None else None
                    except Exception:
                        pass
                data[name] = val

        # custom_data 병합: 기존 cache의 custom_data 유지 + 메인 custom_data 잔여 병합
        # 캐시에 이미 있으면 가져오기
        exist = conn.execute(
            f"SELECT custom_data FROM {cache} WHERE {pk} = ?",
            (pk_val,)
        ).fetchone()
        existing_cd = normalize_json(exist[0] if exist else {})
        source_cd = normalize_json(row.get('custom_data'))
        merged_cd = {}
        merged_cd.update(source_cd)
        merged_cd.update(existing_cd)  # 캐시 쪽 우선 유지
        data['custom_data'] = merged_cd

        # is_deleted 반영(없으면 0)
        data['is_deleted'] = int(row.get('is_deleted', 0) or 0)

        if dry_run:
            updated += 1 if exist else migrated + 1
            continue
        try:
            safe_upsert(conn, cache, data, conflict_cols=[pk])
            if exist:
                updated += 1
            else:
                migrated += 1
        except Exception as e:
            print(f"[WARN] {key} 업서트 실패: {pk_val}: {e}")
            skipped += 1

    if not dry_run:
        conn.commit()
    print(f"[OK] {key}: migrated={migrated}, updated={updated}, skipped={skipped}, total={len(rows)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--board', default='all', choices=['all'] + list(BOARD_CONFIGS.keys()))
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    if args.board == 'all':
        for k in BOARD_CONFIGS.keys():
            sync_board(conn, k, args.dry_run)
    else:
        sync_board(conn, args.board, args.dry_run)
    conn.close()


if __name__ == '__main__':
    main()
