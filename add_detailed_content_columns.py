#!/usr/bin/env python3
"""
detailed_content 컬럼을 모든 테이블에 추가하는 스크립트
"""

import logging
from db_connection import get_db_connection

logging.basicConfig(level=logging.INFO)

def add_detailed_content_columns():
    """모든 필요한 테이블에 detailed_content 컬럼 추가"""
    conn = None
    try:
        conn = get_db_connection('flask-portal.db')
        cursor = conn.cursor()

        tables_to_update = [
            'follow_sop',
            'full_process',
            'safety_instructions',
            'accidents',
            'partner_standards'
        ]

        for table in tables_to_update:
            try:
                # 컬럼이 이미 존재하는지 확인
                cursor.execute(f"""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = '{table}'
                    AND column_name = 'detailed_content'
                """)

                if cursor.fetchone():
                    logging.info(f"✅ {table} 테이블에 detailed_content 컬럼이 이미 존재합니다")
                else:
                    # 컬럼 추가
                    cursor.execute(f"""
                        ALTER TABLE {table}
                        ADD COLUMN detailed_content TEXT
                    """)
                    logging.info(f"✅ {table} 테이블에 detailed_content 컬럼을 추가했습니다")

            except Exception as e:
                logging.warning(f"⚠️ {table} 테이블 처리 중 오류: {e}")
                # PostgreSQL이 아닌 경우 다른 방법 시도
                try:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN detailed_content TEXT")
                    logging.info(f"✅ {table} 테이블에 detailed_content 컬럼을 추가했습니다 (fallback)")
                except:
                    logging.info(f"ℹ️ {table} 테이블에 detailed_content 컬럼이 이미 존재하거나 테이블이 없습니다")

        conn.commit()
        logging.info("✅ 모든 테이블 업데이트 완료")

    except Exception as e:
        logging.error(f"❌ 오류 발생: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    add_detailed_content_columns()