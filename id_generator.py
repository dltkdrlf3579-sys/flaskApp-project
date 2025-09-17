import sqlite3
import logging
from datetime import datetime
from timezone_config import get_korean_time

def generate_unique_id(prefix, db_path, table_name, id_column, base_datetime=None, counter_digits=4):
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

    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    cursor = conn.cursor()

    try:
        # 트랜잭션으로 안전하게 처리
        cursor.execute("BEGIN EXCLUSIVE")

        # 같은 날짜의 기존 ID들 검색
        pattern = f"{prefix}{base_id}%"
        cursor.execute(f"""
            SELECT {id_column} FROM {table_name}
            WHERE {id_column} LIKE ?
            ORDER BY {id_column} DESC
            LIMIT 1
        """, (pattern,))

        result = cursor.fetchone()

        if result:
            # 마지막 순번 추출하여 +1
            last_id = result[0]
            last_counter = int(last_id[len(prefix) + 6:])  # 접두사 + 6자리 날짜 제외
            new_counter = last_counter + 1
        else:
            # 첫 번째 ID
            new_counter = 1

        # 지정된 자릿수로 포맷
        max_counter = 10 ** counter_digits - 1  # 4자리면 9999, 5자리면 99999
        if new_counter > max_counter:
            # 최대값 초과시 다음 날짜로 롤오버 (실제로는 거의 발생 안함)
            logging.warning(f"Counter overflow for {prefix}{base_id}, resetting to 1")
            new_counter = 1

        unique_id = f"{prefix}{base_id}{new_counter:0{counter_digits}d}"

        cursor.execute("COMMIT")
        logging.info(f"고유 ID 생성: {unique_id}")
        return unique_id

    except Exception as e:
        cursor.execute("ROLLBACK")
        logging.error(f"ID 생성 오류: {e}")
        # 폴백: 날짜 + 랜덤
        import random
        max_random = 10 ** counter_digits - 1
        fallback_id = f"{prefix}{base_id}{random.randint(1, max_random):0{counter_digits}d}"
        logging.warning(f"폴백 ID 사용: {fallback_id}")
        return fallback_id
    finally:
        conn.close()

def generate_followsop_number(db_path, base_datetime=None):
    """Follow SOP 점검번호 생성 (FSYYMMDDNNNN - 4자리 순번)"""
    return generate_unique_id('FS', db_path, 'follow_sop', 'work_req_no', base_datetime, counter_digits=4)

def generate_fullprocess_number(db_path, base_datetime=None):
    """Full Process 평가번호 생성 (FPYYMMDDNNNNN - 5자리 순번)"""
    return generate_unique_id('FP', db_path, 'full_process', 'fullprocess_number', base_datetime, counter_digits=5)