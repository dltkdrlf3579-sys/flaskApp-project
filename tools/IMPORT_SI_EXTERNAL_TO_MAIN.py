#!/usr/bin/env python3
"""
Import Safety Instructions from external DB directly into main table (safety_instructions).

Why
- In some prod datasets, cache is empty or main has placeholders. This script fills main.custom_data
  with real values from external query, mapping columns to canonical keys.

Config
- Reads query from config.ini (first found):
  [CONTENT_DATA_QUERIES] SAFETY_INSTRUCTIONS_QUERY
  or
  [MASTER_DATA_QUERIES] SAFETY_INSTRUCTIONS_QUERY

Usage
  python tools/IMPORT_SI_EXTERNAL_TO_MAIN.py --dry-run
  python tools/IMPORT_SI_EXTERNAL_TO_MAIN.py --apply

Notes
- Non-destructive upsert: uses issue_number as key, updates custom_data only (and updated_at)
- Accepts both English and Korean column names; applies robust synonym mapping
"""
import argparse
import configparser
import json
from typing import Any, Dict, List

from db_connection import get_db_connection
from db.upsert import safe_upsert

try:
    from database_config import execute_SQL, IQADB_AVAILABLE
except Exception:
    execute_SQL = None
    IQADB_AVAILABLE = False


CANONICAL_KEYS = [
    'issue_number','issuer','issuer_id','issuer_dept','issuer_incharge_dept',
    'classification','employment_type','birth','gbm','business_division','team','dept',
    'primary_company','primary_company_bizno','secondary_company','secondary_company_bizno',
    'violation_date','discipline_date','discipline_type','violation_type',
    'accident_number','accident_type','accident_grade','violation_grade',
    'access_ban_start_date','access_ban_end_date','period','penalty_points','work_grade',
    'detailed_content'
]


def norm(s: Any) -> str:
    return ''.join(str(s or '').strip().lower().replace('_','').split())


def synonym_map() -> Dict[str, str]:
    # Map normalized source key -> canonical key
    syn = {}
    def add(names: List[str], target: str):
        for n in names:
            syn[norm(n)] = target
    add(['issue_number','발부번호'], 'issue_number')
    add(['issuer','발행인','발행인(이름)','발행인이름'], 'issuer')
    add(['issuerid','발행인id','발행인아이디'], 'issuer_id')
    add(['issuerdept','발행부서','issuer_department'], 'issuer_dept')
    add(['issuerinchargedept','징계발의부서'], 'issuer_incharge_dept')
    add(['classification','분류'], 'classification')
    add(['employmenttype','고용형태'], 'employment_type')
    add(['birth','생년월일'], 'birth')
    add(['gbm','GBM'], 'gbm')
    add(['businessdivision','사업부'], 'business_division')
    add(['team','팀','tema'], 'team')
    add(['dept','소속부서','department'], 'dept')
    add(['primarycompany','1차사명'], 'primary_company')
    add(['primarycompanybizno','1차사명사업자번호','primarybusinessnumber','primary_company_business_number'], 'primary_company_bizno')
    add(['secondarycompany','하도사명','subcontractor'], 'secondary_company')
    add(['secondarycompanybizno','하도사명사업자번호','subcontractorbusinessnumber','secondarycompanybusinessnumber','subcontractor_bizno'], 'secondary_company_bizno')
    add(['violationdate','위반일자'], 'violation_date')
    add(['disciplinedate','징계일자'], 'discipline_date')
    add(['disciplinetype','징계유형'], 'discipline_type')
    add(['violationtype','위반유형'], 'violation_type')
    add(['accidentnumber','사고번호'], 'accident_number')
    add(['accidenttype','사고유형'], 'accident_type')
    add(['accidentgrade','사고등급'], 'accident_grade')
    add(['violationgrade','환경안전수칙위반등급','safetyviolationgrade'], 'violation_grade')
    add(['accessbanstartdate','출입정지시작일'], 'access_ban_start_date')
    add(['accessbanenddate','출입정지종료일'], 'access_ban_end_date')
    add(['period','기간'], 'period')
    add(['penaltypoints','감점'], 'penalty_points')
    add(['workgrade','작업등급'], 'work_grade')
    add(['detailedcontent','상세내용','violationcontent'], 'detailed_content')
    return syn


def map_row_to_custom(row: Dict[str, Any]) -> Dict[str, Any]:
    syn = synonym_map()
    out: Dict[str, Any] = {}
    # passthrough: if canonical key exists in row, prefer it
    for k in CANONICAL_KEYS:
        if k in row and row[k] not in (None, ''):
            out[k] = row[k]
    # then apply synonyms
    for src_key, val in row.items():
        if val in (None, ''):
            continue
        nk = syn.get(norm(src_key))
        if nk and nk not in out:
            out[nk] = val
    # light post-fix: convert penalty_points to int if numeric
    try:
        if 'penalty_points' in out and isinstance(out['penalty_points'], str) and out['penalty_points'].strip():
            out['penalty_points'] = int(float(out['penalty_points']))
    except Exception:
        pass
    return out


def main():
    ap = argparse.ArgumentParser(description='Import Safety Instructions from external DB into main')
    ap.add_argument('--apply', action='store_true', help='Apply upsert into safety_instructions')
    args = ap.parse_args()

    cfg = configparser.ConfigParser()
    cfg.read('config.ini', encoding='utf-8')
    query = None
    if cfg.has_option('CONTENT_DATA_QUERIES', 'SAFETY_INSTRUCTIONS_QUERY'):
        query = cfg.get('CONTENT_DATA_QUERIES', 'SAFETY_INSTRUCTIONS_QUERY')
    elif cfg.has_option('MASTER_DATA_QUERIES', 'SAFETY_INSTRUCTIONS_QUERY'):
        query = cfg.get('MASTER_DATA_QUERIES', 'SAFETY_INSTRUCTIONS_QUERY')
    if not query:
        print('[ERROR] SAFETY_INSTRUCTIONS_QUERY not found in config.ini')
        return
    if not (execute_SQL and IQADB_AVAILABLE):
        print('[ERROR] External DB module not available (IQADB). Configure and retry.')
        return

    df = execute_SQL(query)
    try:
        nrows = 0 if df is None else len(df)
    except Exception:
        nrows = 0
    print(f'[INFO] External rows fetched: {nrows}')
    if nrows == 0:
        return

    conn = get_db_connection()
    total = 0
    upserts = 0
    skipped = 0
    for _, r in df.iterrows():
        total += 1
        row = r.to_dict() if hasattr(r, 'to_dict') else dict(r)
        issue_number = (row.get('issue_number') or row.get('발부번호') or '').strip()
        if not issue_number:
            skipped += 1
            continue
        cd = map_row_to_custom(row)
        if not cd:
            skipped += 1
            continue
        if not args.apply:
            # print preview for first few
            if upserts < 5:
                print(f"[DRY] {issue_number} keys: {sorted(cd.keys())[:8]} ...")
            upserts += 1
            continue
        data = {
            'issue_number': issue_number,
            'custom_data': cd,
            'updated_at': None
        }
        safe_upsert(conn, 'safety_instructions', data, conflict_cols=['issue_number'], update_cols=['custom_data','updated_at'])
        upserts += 1

    if args.apply:
        conn.commit()
    conn.close()
    print(f"[DONE] processed={total}, upserts={upserts}, skipped={skipped}, mode={'APPLY' if args.apply else 'DRY'}")


if __name__ == '__main__':
    main()

