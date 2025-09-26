"""Synchronise system_users and departments_external from master queries.

Run with:  venv\Scripts\python.exe scripts\sync_permission_master_data.py

It executes the SQL configured in [MASTER_DATA_QUERIES]
(employee_query, department_query) and stores the results in
system_users / departments_external.
"""
from __future__ import annotations

import configparser
import logging
from typing import Dict, Iterable, List, Sequence

from db_connection import get_db_connection

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
log = logging.getLogger(__name__)


def load_config() -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    read_files = cfg.read('config.ini', encoding='utf-8')
    if not read_files:
        raise RuntimeError('config.ini not found – run inside project root.')
    return cfg


def execute_query(conn, query: str) -> List[Dict[str, any]]:
    if not query:
        return []
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(query)
        rows = cur.fetchall() or []
        columns: Sequence[str]
        if hasattr(cur, 'description') and cur.description:
            columns = [col[0] for col in cur.description]
        else:
            columns = []
        normalised = []
        for row in rows:
            if isinstance(row, dict):
                lower_dict = {str(k).lower(): row[k] for k in row.keys()}
                normalised.append(lower_dict)
            else:
                item = {}
                for idx, value in enumerate(row):
                    if idx < len(columns):
                        item[columns[idx].lower()] = value
                    else:
                        item[str(idx)] = value
                normalised.append(item)
        return normalised
    except Exception as primary_exc:
        log.warning('Primary DB query failed, attempting external DB: %s', primary_exc)
        try:
            from database_config import execute_SQL  # type: ignore
        except Exception as import_exc:
            log.error('External DB access not available: %s', import_exc)
            raise primary_exc

        try:
            df = execute_SQL(query)
        except Exception as external_exc:
            log.error('External DB query failed: %s', external_exc)
            raise primary_exc

        if df is None:
            raise primary_exc

        normalised = []
        for record in df.to_dict('records'):
            lower_dict = {str(k).lower(): v for k, v in record.items()}
            normalised.append(lower_dict)
        return normalised
    finally:
        if cur:
            cur.close()


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


def upsert_rows(
    conn,
    table: str,
    rows: Iterable[Dict[str, any]],
    mapping: Dict[str, Sequence[str]],
    key_columns: Sequence[str],
    extra_fixed: Dict[str, any] | None = None,
) -> int:
    """Insert rows into table using mapping of target column -> candidate keys."""
    available_columns = set(table_columns(conn, table))
    if not available_columns:
        raise RuntimeError(f"Table '{table}' does not exist or has no columns.")

    cur = conn.cursor()
    inserted = 0
    try:
        for row in rows:
            data: Dict[str, any] = {}
            # Map dynamic values
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

            # Add fixed extras (e.g. is_active=True)
            if extra_fixed:
                for col, value in extra_fixed.items():
                    if col in available_columns:
                        data[col] = value

            # Ensure key columns are present
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


def clear_table(conn, table: str) -> None:
    cur = conn.cursor()
    try:
        cur.execute(f"DELETE FROM {table}")
        conn.commit()
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

    conn = get_db_connection()
    try:
        log.info('Fetching employee data...')
        employee_rows = execute_query(conn, employee_query)
        log.info(' -> %d rows', len(employee_rows))

        log.info('Fetching department data...')
        department_rows = execute_query(conn, department_query)
        log.info(' -> %d rows', len(department_rows))

        # system_users
        log.info('Clearing system_users...')
        clear_table(conn, 'system_users')
        log.info('Populating system_users...')
        inserted_users = upsert_rows(
            conn,
            table='system_users',
        rows=employee_rows,
        mapping={
            'login_id': ('login_id', 'employee_id', 'emp_id', 'loginid'),
            'user_name': ('user_name', 'employee_name', 'name'),
            'dept_id': ('dept_id', 'department_id'),
            'dept_name': ('dept_name', 'department_name')
        },
            key_columns=('login_id',),
            extra_fixed={'is_active': True}
        )
        log.info('system_users upserted %d rows', inserted_users)

        # departments_external
        log.info('Clearing departments_external...')
        clear_table(conn, 'departments_external')
        log.info('Populating departments_external...')
        inserted_depts = upsert_rows(
            conn,
            table='departments_external',
            rows=department_rows,
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
