import logging
from datetime import datetime
from typing import Iterable, Optional

from timezone_config import get_korean_time
from db_connection import get_db_connection


def _resolve_existing_table(conn, primary: str, candidates: Optional[Iterable[str]] = None) -> str:
    """Return the first table name that exists on the current backend."""
    names: list[str] = []
    if primary:
        names.append(primary)
    if candidates:
        for name in candidates:
            if name and name not in names:
                names.append(name)

    if not names:
        return primary

    for name in names:
        try:
            cursor = conn.cursor()
            try:
                if getattr(conn, 'is_postgres', False):
                    cursor.execute("SELECT to_regclass(%s)", (name,))
                    row = cursor.fetchone()
                    exists = bool(row and row[0])
                else:
                    cursor.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
                        (name,),
                    )
                    exists = cursor.fetchone() is not None
            finally:
                try:
                    cursor.close()
                except Exception:
                    pass
        except Exception:
            exists = False

        if exists:
            return name

    return primary


def generate_unique_id(prefix, db_path, table_name, id_column, base_datetime=None, counter_digits=4, table_candidates=None):
    """
    접두사 + yyMMdd + N자리 순번 형식의 고유 ID 생성

    Args:
        prefix: ID 접두사 (예: 'FS', 'FP', 'SI')
        db_path: 데이터베이스 경로
        table_name: 테이블명
        id_column: ID 컬럼명
        base_datetime: 기준 시간 (없으면 현재 한국 시간 사용)
        counter_digits: 순번 자릿수 (FS는 4자리, FP는 5자리)

    Returns:
        str: 생성된 고유 ID (예: FS2412010001, FP24120100001)
    """
    if base_datetime:
        # 전달받은 시간 사용 (created_at 기반)
        korean_time = base_datetime
    else:
        # 기본값: 현재 한국 시간
        korean_time = get_korean_time()

    base_id = korean_time.strftime('%y%m%d')  # yyMMdd (날짜만)

    conn = None
    cursor = None
    resolved_table = table_name

    try:
        conn = get_db_connection(db_path, timeout=30.0)
        resolved_table = _resolve_existing_table(conn, table_name, table_candidates)
        cursor = conn.cursor()

        if getattr(conn, 'is_postgres', False):
            cursor.execute("BEGIN")
        else:
            cursor.execute("BEGIN EXCLUSIVE")

        pattern = f"{prefix}{base_id}%"
        cursor.execute(
            f"""
            SELECT {id_column}
            FROM {resolved_table}
            WHERE {id_column} LIKE ?
            ORDER BY {id_column} DESC
            LIMIT 1
            """,
            (pattern,),
        )

        result = cursor.fetchone()

        if result:
            if isinstance(result, dict):
                last_id = result.get(id_column)
                if not last_id and result:
                    try:
                        last_id = next(iter(result.values()))
                    except Exception:
                        last_id = None
            else:
                try:
                    last_id = result[0]
                except Exception:
                    last_id = None
            last_counter = int(str(last_id)[len(prefix) + 6:]) if last_id else 0
            new_counter = last_counter + 1
        else:
            new_counter = 1

        max_counter = 10 ** counter_digits - 1
        if new_counter > max_counter:
            logging.warning(f"Counter overflow for {prefix}{base_id}, resetting to 1")
            new_counter = 1

        unique_id = f"{prefix}{base_id}{new_counter:0{counter_digits}d}"

        conn.commit()
        logging.info(f"고유 ID 생성: {unique_id} (table={resolved_table})")
        return unique_id

    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        logging.error(f"ID 생성 오류: {e}")
        import random
        max_random = 10 ** counter_digits - 1
        fallback_id = f"{prefix}{base_id}{random.randint(1, max_random):0{counter_digits}d}"
        logging.warning(f"폴백 ID 사용: {fallback_id}")
        return fallback_id
    finally:
        try:
            if cursor and hasattr(cursor, 'close'):
                cursor.close()
        except Exception:
            pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def generate_followsop_number(db_path, base_datetime=None):
    """Follow SOP 점검번호 생성 (FSYYMMDDNNNN - 4자리 순번)"""
    return generate_unique_id(
        'FS',
        db_path,
        'follow_sop',
        'work_req_no',
        base_datetime,
        counter_digits=4,
        table_candidates=('follow_sop_cache', 'followsop_cache'),
    )


def generate_fullprocess_number(db_path, base_datetime=None):
    """Full Process 평가번호 생성 (FPYYMMDDNNNNN - 5자리 순번)"""
    return generate_unique_id(
        'FP',
        db_path,
        'full_process',
        'fullprocess_number',
        base_datetime,
        counter_digits=5,
        table_candidates=('full_process_cache', 'fullprocess_cache'),
    )


def generate_safeplace_number(db_path, base_datetime=None):
    """Safe Workplace 점검번호 생성 (SPYYMMDDNNNN - 4자리 순번)

    기본적으로 PostgreSQL을 사용하고, 실패 시 기존 SQLite 로직으로 폴백한다.
    """
    korean_time = base_datetime or get_korean_time()
    base_id = korean_time.strftime('%y%m%d')
    prefix = 'SP'

    try:
        from db_connection import get_db_connection
        conn = get_db_connection()
        table_name = _resolve_existing_table(conn, 'safe_workplace', ('safe_workplace_cache',))
        cursor = conn.cursor()

        pattern = f"{prefix}{base_id}%"
        cursor.execute(
            f"""
            SELECT safeplace_no
            FROM {table_name}
            WHERE safeplace_no LIKE ?
            ORDER BY safeplace_no DESC
            LIMIT 1
            """,
            (pattern,),
        )

        row = cursor.fetchone()
        last_id = None
        if row:
            if isinstance(row, dict):
                last_id = row.get('safeplace_no')
                if not last_id and row:
                    try:
                        last_id = next(iter(row.values()))
                    except Exception:
                        last_id = None
            else:
                try:
                    last_id = row[0]
                except Exception:
                    last_id = None

        if last_id:
            try:
                last_counter = int(str(last_id)[len(prefix) + 6:])
            except ValueError:
                last_counter = 0
            new_counter = last_counter + 1
        else:
            new_counter = 1

        max_counter = 10 ** 4 - 1
        if new_counter > max_counter:
            logging.warning(f"Safe Workplace counter overflow for {prefix}{base_id}, resetting to 1")
            new_counter = 1

        unique_id = f"{prefix}{base_id}{new_counter:04d}"

        cursor.close()
        conn.close()
        logging.info(f"Safe Workplace 고유 ID 생성(PostgreSQL): {unique_id} (table={table_name})")
        return unique_id

    except Exception as e:
        logging.error(f"Safe Workplace ID 생성(PostgreSQL) 실패: {e}")
        raise
