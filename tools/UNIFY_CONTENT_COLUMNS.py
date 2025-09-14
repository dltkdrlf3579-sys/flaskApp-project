#!/usr/bin/env python3
"""
모든 테이블의 content 컬럼명을 detailed_content로 통일

실행 전 백업 필수!
- partner_details.detail_content → detailed_content
- 다른 테이블들은 이미 detailed_content 사용 중

운영환경 실행:
1. 먼저 백업: pg_dump -U postgres -h localhost -d safetydb -t partner_details > partner_details_backup.sql
2. 스크립트 실행: python tools/UNIFY_CONTENT_COLUMNS.py
3. 문제 발생 시 복구: psql -U postgres -h localhost -d safetydb < partner_details_backup.sql
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_connection import get_db_connection
import logging

logging.basicConfig(level=logging.INFO)

def check_column_exists(cursor, table_name, column_name):
    """컬럼 존재 여부 확인"""
    cursor.execute("""
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = %s AND column_name = %s
    """, (table_name.lower(), column_name.lower()))
    return cursor.fetchone() is not None

def unify_content_columns():
    """모든 content 컬럼을 detailed_content로 통일"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 1. 현재 상태 확인
        print("\n=== 1. 현재 컬럼 상태 확인 ===")
        
        tables_to_check = [
            'partner_details',
            'safety_instructions', 
            'accidents',
            'follow_sop',
            'full_process'
        ]
        
        for table in tables_to_check:
            has_detail = check_column_exists(cursor, table, 'detail_content')
            has_detailed = check_column_exists(cursor, table, 'detailed_content')
            
            if has_detail and has_detailed:
                print(f"⚠️  {table}: 두 컬럼 모두 존재 (detail_content, detailed_content)")
            elif has_detail:
                print(f"❌ {table}: detail_content만 존재 (변경 필요)")
            elif has_detailed:
                print(f"✅ {table}: detailed_content 사용 중")
            else:
                print(f"⭕ {table}: content 컬럼 없음")
        
        # 2. partner_details 테이블 처리
        print("\n=== 2. partner_details 테이블 변경 ===")
        
        if check_column_exists(cursor, 'partner_details', 'detail_content'):
            if check_column_exists(cursor, 'partner_details', 'detailed_content'):
                # 두 컬럼 모두 있는 경우
                print("⚠️  detailed_content 컬럼이 이미 존재합니다.")
                
                # detail_content의 데이터를 detailed_content로 복사
                cursor.execute("""
                    UPDATE partner_details 
                    SET detailed_content = detail_content 
                    WHERE detail_content IS NOT NULL 
                    AND (detailed_content IS NULL OR detailed_content = '')
                """)
                updated = cursor.rowcount
                print(f"   - {updated}개 행의 데이터를 detailed_content로 복사")
                
                # detail_content 컬럼 삭제
                cursor.execute("ALTER TABLE partner_details DROP COLUMN detail_content")
                print("   - detail_content 컬럼 삭제 완료")
                
            else:
                # detail_content만 있는 경우 - 이름 변경
                cursor.execute("""
                    ALTER TABLE partner_details 
                    RENAME COLUMN detail_content TO detailed_content
                """)
                print("✅ detail_content → detailed_content 변경 완료")
        
        elif not check_column_exists(cursor, 'partner_details', 'detailed_content'):
            # 둘 다 없는 경우 - 새로 생성
            cursor.execute("""
                ALTER TABLE partner_details 
                ADD COLUMN detailed_content TEXT
            """)
            print("✅ detailed_content 컬럼 새로 생성")
        else:
            print("✅ 이미 detailed_content 사용 중")
        
        # 3. database_config.py의 호환성 코드 확인
        print("\n=== 3. 코드 호환성 확인 ===")
        print("database_config.py의 1256-1262번 라인 호환성 코드를 제거할 수 있습니다.")
        print("모든 테이블이 detailed_content를 사용하므로 더 이상 필요 없습니다.")
        
        # 4. 변경사항 커밋
        conn.commit()
        print("\n✅ 모든 변경사항이 성공적으로 적용되었습니다!")
        
        # 5. 최종 확인
        print("\n=== 4. 최종 상태 확인 ===")
        for table in tables_to_check:
            has_detail = check_column_exists(cursor, table, 'detail_content')
            has_detailed = check_column_exists(cursor, table, 'detailed_content')
            
            if has_detail:
                print(f"❌ {table}: 아직 detail_content 존재 (문제!)")
            elif has_detailed:
                print(f"✅ {table}: detailed_content 사용 중")
            else:
                print(f"⭕ {table}: content 컬럼 없음")
        
    except Exception as e:
        conn.rollback()
        logging.error(f"오류 발생: {e}")
        print(f"\n❌ 오류 발생: {e}")
        print("변경사항이 롤백되었습니다.")
        return False
    
    finally:
        conn.close()
    
    return True

def main():
    print("=" * 60)
    print("Content 컬럼명 통일 스크립트")
    print("=" * 60)
    print("\n⚠️  주의: 운영환경 실행 전 반드시 백업하세요!")
    print("백업 명령: pg_dump -U postgres -h localhost -d safetydb -t partner_details > backup.sql")
    print()
    
    response = input("계속하시겠습니까? (yes/no): ")
    if response.lower() != 'yes':
        print("취소되었습니다.")
        return
    
    if unify_content_columns():
        print("\n" + "=" * 60)
        print("✅ 성공적으로 완료되었습니다!")
        print("\n다음 단계:")
        print("1. database_config.py의 1256-1262번 라인 호환성 코드 제거 가능")
        print("2. 애플리케이션 재시작 후 테스트")
        print("=" * 60)
    else:
        print("\n실패했습니다. 로그를 확인하세요.")

if __name__ == '__main__':
    main()