"""Synchronise system_users and departments_external using MASTER_DATA_QUERIES.

Run with:
    venv\Scripts\python.exe scripts\sync_permission_master_data.py

This fetches employee/dept data from the external IQADB source (execute_SQL)
then upserts into the Postgres tables system_users / departments_external.
"""
from __future__ import annotations

import logging
import configparser
from typing import Dict, Iterable, List, Sequence

from db_connection import get_db_connection
from database_config import execute_SQL  # external DB helper

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
log = logging.getLogger(__name__)


def load_config() -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    read_files = cfg.read('config.ini', encoding='utf-8')
    if not read_files:
        raise RuntimeError('config.ini not found – run inside project root.')
    return cfg


def fetch_external_data(query: str) -> List[Dict[str, any]]:
    if not query:
        return []
    log.info('Running external query (first 100 chars): %s', query[:100])
    df = execute_SQL(query)
    if df is None:
        return []
    rows = df.to_dict('records')
    normalised = []
    for record in rows:
        lower_dict = {str(k).lower(): v for k, v in record.items()}
        normalised.append(lower_dict)
    return normalised


def table_columns(conn, table_name: str) -> List[str]:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT column_name
              FROM information_schema.columns
             WHERE table_schema = 'public' AND table_name = %s
            """,
            (table_name,),
        )
        return [row[0] for row in cur.fetchall()]
    finally:
        cur.close()


def truncate_table(conn, table: str) -> None:
    cur = conn.cursor()
    try:
        cur.execute(f"TRUNCATE {table}")
        conn.commit()
    finally:
        cur.close()


def upsert_rows(
    conn,
    table: str,
    rows: Iterable[Dict[str, any]],
    mapping: Dict[str, Sequence[str]],
    key_columns: Sequence[str],
    extra_fixed: Dict[str, any] | None = None,
) -> int:
    available_columns = set(table_columns(conn, table))
    if not available_columns:
        raise RuntimeError(f"Table '{table}' does not exist or has no columns.")

    cur = conn.cursor()
    inserted = 0
    try:
        for row in rows:
            data: Dict[str, any] = {}
            for target_col, source_keys in mapping.items():
                if target_col not in available_columns:
                    continue
                value = None
                for key in source_keys:
                    key_lower = key.lower()
                    if key_lower in row and row[key_lower] not in (None, ''):
                        value = row[key_lower]
                        break
                data[target_col] = value

            if extra_fixed:
                for col, value in extra_fixed.items():
                    if col in available_columns:
                        data[col] = value

            if not all(data.get(col) not in (None, '') for col in key_columns):
                continue

            columns = [col for col, val in data.items() if val is not None]
            if not columns:
                continue

            values = [data[col] for col in columns]
            placeholders = ','.join(['%s'] * len(columns))
            insert_cols = ','.join(columns)
            update_cols = [col for col in columns if col not in key_columns]
            if update_cols:
                update_clause = ','.join([f"{col} = EXCLUDED.{col}" for col in update_cols])
                sql = (
                    f"INSERT INTO {table} ({insert_cols}) "
                    f"VALUES ({placeholders}) "
                    f"ON CONFLICT ({', '.join(key_columns)}) DO UPDATE SET {update_clause}"
                )
            else:
                sql = (
                    f"INSERT INTO {table} ({insert_cols}) "
                    f"VALUES ({placeholders}) "
                    f"ON CONFLICT ({', '.join(key_columns)}) DO NOTHING"
                )

            cur.execute(sql, values)
            inserted += 1

        conn.commit()
        return inserted
    finally:
        cur.close()


def main() -> None:
    cfg = load_config()

    employee_query = cfg.get('MASTER_DATA_QUERIES', 'employee_query', fallback='').strip()
    department_query = cfg.get('MASTER_DATA_QUERIES', 'department_query', fallback='').strip()

    if not employee_query:
        raise RuntimeError('MASTER_DATA_QUERIES.employee_query 설정이 필요합니다.')
    if not department_query:
        raise RuntimeError('MASTER_DATA_QUERIES.department_query 설정이 필요합니다.')

    employees = fetch_external_data(employee_query)
    departments = fetch_external_data(department_query)

    log.info('Employees fetched: %d', len(employees))
    log.info('Departments fetched: %d', len(departments))

    conn = get_db_connection()
    try:
        # system_users
        log.info('Truncating system_users...')
        truncate_table(conn, 'system_users')
        log.info('Populating system_users...')
        inserted_users = upsert_rows(
            conn,
            table='system_users',
            rows=employees,
            mapping={
                'login_id': ('login_id', 'employee_id', 'loginid'),
                'user_name': ('user_name', 'employee_name', 'name'),
                'dept_id': ('dept_id', 'department_id'),
                'dept_name': ('dept_name', 'department_name')
            },
            key_columns=('login_id',),
            extra_fixed={'is_active': True}
        )
        log.info('system_users upserted %d rows', inserted_users)

        # departments_external
        log.info('Truncating departments_external...')
        truncate_table(conn, 'departments_external')
        log.info('Populating departments_external...')
        inserted_depts = upsert_rows(
            conn,
            table='departments_external',
            rows=departments,
            mapping={
                'dept_id': ('dept_id', 'dept_code'),
                'dept_code': ('dept_code',),
                'dept_name': ('dept_name', 'department_name'),
                'dept_full_path': ('dept_full_path',),
                'parent_dept_code': ('parent_dept_code', 'parent_id'),
                'dept_level': ('dept_level',)
            },
            key_columns=('dept_id',),
            extra_fixed={'is_active': True}
        )
        log.info('departments_external upserted %d rows', inserted_depts)

        log.info('Done.')
    finally:
        conn.close()


if __name__ == '__main__':
    main()
