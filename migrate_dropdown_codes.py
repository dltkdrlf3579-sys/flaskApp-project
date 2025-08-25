import sqlite3
import json
import os
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)

# DB 경로 설정
DB_PATH = os.path.join(os.path.dirname(__file__), 'portal.db')

def migrate_dropdown_codes():
    """구식 JSON 배열 형식의 드롭다운 옵션을 새로운 코드 매핑 테이블로 마이그레이션"""
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # dropdown_code_mapping 테이블이 있는지 확인
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='dropdown_code_mapping'
        """)
        if not cursor.fetchone():
            logging.error("dropdown_code_mapping 테이블이 없습니다. 먼저 테이블을 생성해주세요.")
            return
        
        # JSON 배열로 저장된 드롭다운 컬럼 찾기
        cursor.execute("""
            SELECT id, column_key, dropdown_options 
            FROM accident_column_config 
            WHERE column_type = 'dropdown' 
            AND dropdown_options IS NOT NULL
        """)
        
        columns = cursor.fetchall()
        migrated_count = 0
        
        for col_id, column_key, options_str in columns:
            if not options_str:
                continue
                
            # JSON 배열 문자열인지 확인
            options_str = options_str.strip()
            if options_str.startswith('[') and options_str.endswith(']'):
                try:
                    # JSON 파싱
                    options = json.loads(options_str)
                    
                    if isinstance(options, list) and len(options) > 0:
                        logging.info(f"[{column_key}] 마이그레이션 시작: {options}")
                        
                        # 기존 코드 매핑 삭제
                        cursor.execute("""
                            DELETE FROM dropdown_code_mapping 
                            WHERE column_key = ?
                        """, (column_key,))
                        
                        # 새로운 코드 매핑 추가
                        for i, option in enumerate(options):
                            code = f"{column_key.upper()}_{i+1:03d}"
                            cursor.execute("""
                                INSERT INTO dropdown_code_mapping 
                                (column_key, code, option_value, display_order, is_active)
                                VALUES (?, ?, ?, ?, 1)
                            """, (column_key, code, str(option), i + 1))
                        
                        # accident_column_config의 dropdown_options를 NULL로 업데이트
                        cursor.execute("""
                            UPDATE accident_column_config 
                            SET dropdown_options = NULL 
                            WHERE id = ?
                        """, (col_id,))
                        
                        migrated_count += 1
                        logging.info(f"[{column_key}] {len(options)}개 옵션 마이그레이션 완료")
                        
                except json.JSONDecodeError as e:
                    logging.error(f"[{column_key}] JSON 파싱 실패: {e}")
                except Exception as e:
                    logging.error(f"[{column_key}] 마이그레이션 실패: {e}")
            else:
                # 단일 옵션 값인 경우 처리
                try:
                    # dropdown_code_mapping에 이미 있는지 확인
                    cursor.execute("""
                        SELECT COUNT(*) FROM dropdown_code_mapping 
                        WHERE column_key = ?
                    """, (column_key,))
                    
                    if cursor.fetchone()[0] == 0:
                        # 단일 값을 코드 매핑으로 추가
                        code = f"{column_key.upper()}_001"
                        cursor.execute("""
                            INSERT INTO dropdown_code_mapping 
                            (column_key, code, option_value, display_order, is_active)
                            VALUES (?, ?, ?, 1, 1)
                        """, (column_key, code, options_str))
                        
                        cursor.execute("""
                            UPDATE accident_column_config 
                            SET dropdown_options = NULL 
                            WHERE id = ?
                        """, (col_id,))
                        
                        migrated_count += 1
                        logging.info(f"[{column_key}] 단일 옵션 마이그레이션 완료: {options_str}")
                except Exception as e:
                    logging.error(f"[{column_key}] 단일 옵션 마이그레이션 실패: {e}")
        
        conn.commit()
        
        if migrated_count > 0:
            logging.info(f"\n[SUCCESS] 총 {migrated_count}개 컬럼의 드롭다운 옵션을 마이그레이션했습니다.")
        else:
            logging.info("[INFO] 마이그레이션할 드롭다운 옵션이 없습니다.")
        
        # 마이그레이션 결과 확인
        cursor.execute("""
            SELECT column_key, COUNT(*) as option_count 
            FROM dropdown_code_mapping 
            GROUP BY column_key
        """)
        results = cursor.fetchall()
        
        if results:
            print("\n[현재 드롭다운 코드 매핑 상태]")
            for column_key, count in results:
                print(f"  - {column_key}: {count}개 옵션")
        
    except Exception as e:
        logging.error(f"마이그레이션 중 오류 발생: {e}")
        conn.rollback()
        
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_dropdown_codes()