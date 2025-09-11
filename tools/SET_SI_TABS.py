#!/usr/bin/env python3
"""
Set tab values on safety_instruction_column_config for common keys so that
they render under sections in list/detail/register views.

Only rows with tab IS NULL or '' are updated. Existing tabs are preserved.

Usage:
  python tools/SET_SI_TABS.py
"""
from db_connection import get_db_connection


BASIC = {
    'issue_number','created_at',
    'issuer','issuer_id','issuer_dept','issuer_incharge_dept',
    'classification','employment_type','employement_type',
    'primary_company','primary_company_bizno',
    'secondary_company','secondary_company_bizno',
    'subcontractor','subcontractor_business_number',
    'birth','gbm','business_division','team','dept',
}
VIOLATION = {
    'violation_date','discipline_date','discipline_type','displine_type',
    'accident_number','accident_type','accident_grade',
    'violation_grade','violation_type','violation_content',
    'access_ban_start_date','access_ban_end_date','period','work_grade','penalty_points',
}


def _exec(cur, sql, params):
    try:
        cur.execute(sql, params)
        return True
    except Exception:
        return False


def set_tab(conn, keys, tab_name):
    cur = conn.cursor()
    is_pg = getattr(conn, 'is_postgres', False)
    if not keys:
        return 0
    placeholders = ','.join(['%s']*len(keys)) if is_pg else ','.join(['?']*len(keys))
    sql = (
        f"UPDATE safety_instruction_column_config "
        f"SET tab = {'%s' if is_pg else '?'}, updated_at = CURRENT_TIMESTAMP "
        f"WHERE (tab IS NULL OR tab = '') AND LOWER(column_key) IN ({placeholders})"
    )
    params = [tab_name] + [k.lower() for k in keys]
    cur.execute(sql, tuple(params))
    return cur.rowcount if hasattr(cur, 'rowcount') else 0


def main():
    conn = get_db_connection()
    total_basic = set_tab(conn, BASIC, 'basic_info')
    total_violation = set_tab(conn, VIOLATION, 'violation_info')
    # 나머지 미지정 컬럼은 additional로
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE safety_instruction_column_config "
            "SET tab='additional', updated_at=CURRENT_TIMESTAMP "
            "WHERE (tab IS NULL OR tab='')"
        )
    except Exception:
        pass
    conn.commit(); conn.close()
    print(f"Updated tabs: basic={total_basic}, violation={total_violation}, others->additional")


if __name__ == '__main__':
    main()
