#!/usr/bin/env python3
"""
detailed_content를 모든 column_config 테이블에서 삭제
- 상세내용은 별도 섹션으로 처리되므로 동적 컬럼에서 제외
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import get_db_connection
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def delete_detailed_content_from_configs():
    """모든 column_config 테이블에서 detailed_content 제거"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 삭제할 테이블 목록
        tables = [
            'change_request_column_config',
            'safety_instruction_column_config',
            'accident_column_config',
            'follow_sop_column_config',
            'full_process_column_config'
        ]
        
        total_deleted = 0
        
        for table in tables:
            try:
                # 먼저 존재 여부 확인
                cursor.execute(f"""
                    SELECT COUNT(*) FROM {table} 
                    WHERE column_key = 'detailed_content'
                """)
                count = cursor.fetchone()[0]
                
                if count > 0:
                    # 삭제 실행
                    cursor.execute(f"""
                        DELETE FROM {table} 
                        WHERE column_key = 'detailed_content'
                    """)
                    
                    logger.info(f"✅ {table}: {count}개 레코드 삭제됨")
                    total_deleted += count
                else:
                    logger.info(f"ℹ️ {table}: detailed_content 레코드 없음")
                    
            except Exception as e:
                logger.warning(f"⚠️ {table} 처리 중 오류 (테이블 없음?): {e}")
                continue
        
        if total_deleted > 0:
            conn.commit()
            logger.info(f"\n✨ 총 {total_deleted}개 detailed_content 레코드 삭제 완료!")
        else:
            logger.info("\n✨ 삭제할 detailed_content 레코드가 없습니다.")
            
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ 오류 발생: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("detailed_content 컬럼 설정 삭제 도구")
    print("=" * 60)
    print("\n이 스크립트는 모든 column_config 테이블에서")
    print("detailed_content 레코드를 삭제합니다.")
    print("(상세내용은 별도 섹션으로 처리되므로 중복 제거)\n")
    
    # 자동 실행 모드 (인자가 있으면 자동, 없으면 대화형)
    if len(sys.argv) > 1 and sys.argv[1] == '--auto':
        print("자동 실행 모드...")
        delete_detailed_content_from_configs()
    else:
        response = input("계속하시겠습니까? (y/n): ")
        if response.lower() == 'y':
            delete_detailed_content_from_configs()
        else:
            print("취소되었습니다.")