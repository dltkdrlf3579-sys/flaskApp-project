#!/usr/bin/env python3
"""
환경안전 지시서 데이터 마이그레이션 스크립트
PostgreSQL -> SQLite 일회성 마이그레이션
"""
import os
import sys
import sqlite3
import configparser
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

try:
    from IQADB_CONNECT310 import execute_SQL
    IQADB_AVAILABLE = True
    print("✅ IQADB_CONNECT310 모듈 로드 성공")
except ImportError:
    print("❌ IQADB_CONNECT310 모듈을 찾을 수 없습니다.")
    IQADB_AVAILABLE = False
    sys.exit(1)

def migrate_safety_instructions():
    """환경안전 지시서 데이터 마이그레이션 실행"""
    
    # config.ini 읽기
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')
    
    if not config.has_option('SQL_QUERIES', 'SAFETY_INSTRUCTIONS_QUERY'):
        print("❌ config.ini에 SAFETY_INSTRUCTIONS_QUERY가 없습니다.")
        return False
    
    # 쿼리 가져오기
    query = config.get('SQL_QUERIES', 'SAFETY_INSTRUCTIONS_QUERY')
    print(f"📋 실행할 쿼리: {query[:100]}...")
    
    try:
        # PostgreSQL에서 데이터 조회
        print("🔍 PostgreSQL에서 환경안전 지시서 데이터 조회 중...")
        df = execute_SQL(query)
        print(f"📊 조회 완료: {len(df)} 건")
        
        if df.empty:
            print("⚠️  조회된 데이터가 없습니다.")
            return False
        
        # SQLite 연결
        db_path = 'portal.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("🗂️  DataFrame 컬럼 정보:")
        for col in df.columns:
            print(f"  - {col}")
        
        # 기존 데이터 확인
        cursor.execute("SELECT COUNT(*) FROM safety_instructions")
        existing_count = cursor.fetchone()[0]
        print(f"📈 기존 데이터: {existing_count} 건")
        
        if existing_count > 0:
            response = input("⚠️  기존 데이터가 있습니다. 덮어쓰시겠습니까? (y/N): ")
            if response.lower() != 'y':
                print("❌ 마이그레이션 취소됨")
                return False
            
            # 기존 데이터 삭제
            cursor.execute("DELETE FROM safety_instructions")
            print("🗑️  기존 데이터 삭제 완료")
        
        # 데이터 삽입
        print("💾 데이터 삽입 중...")
        success_count = 0
        
        for idx, row in df.iterrows():
            try:
                cursor.execute('''
                    INSERT INTO safety_instructions (
                        issue_number, issuer, issuer_department, classification, employment_type,
                        primary_company, primary_business_number, subcontractor, subcontractor_business_number,
                        disciplined_person, gbm, business_division, team, department,
                        violation_date, discipline_date, discipline_department, discipline_type,
                        accident_type, accident_grade, safety_violation_grade, violation_type,
                        access_ban_start_date, access_ban_end_date, period,
                        work_grade, penalty_points, disciplined_person_id, violation_content, detailed_content,
                        created_at, is_deleted
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 0)
                ''', (
                    row.get('issue_number', ''),
                    row.get('issuer', ''),
                    row.get('issuer_department', ''),
                    row.get('classification', ''),
                    row.get('employment_type', ''),
                    row.get('primary_company', ''),
                    row.get('primary_business_number', ''),
                    row.get('subcontractor', ''),
                    row.get('subcontractor_business_number', ''),
                    row.get('disciplined_person', ''),
                    row.get('gbm', ''),
                    row.get('business_division', ''),
                    row.get('team', ''),
                    row.get('department', ''),
                    row.get('violation_date', ''),
                    row.get('discipline_date', ''),
                    row.get('discipline_department', ''),
                    row.get('discipline_type', ''),
                    row.get('accident_type', ''),
                    row.get('accident_grade', ''),
                    row.get('safety_violation_grade', ''),
                    row.get('violation_type', ''),
                    row.get('access_ban_start_date', ''),
                    row.get('access_ban_end_date', ''),
                    row.get('period', ''),
                    row.get('work_grade', ''),
                    int(row.get('penalty_points', 0)) if row.get('penalty_points') else None,
                    row.get('disciplined_person_id', ''),
                    row.get('violation_content', ''),
                    row.get('detailed_content', '')
                ))
                success_count += 1
                
                if (idx + 1) % 100 == 0:
                    print(f"  📈 {idx + 1}/{len(df)} 처리 중...")
                    
            except Exception as e:
                print(f"⚠️  행 {idx + 1} 삽입 실패: {e}")
                continue
        
        # 커밋
        conn.commit()
        conn.close()
        
        print(f"🎉 마이그레이션 완료!")
        print(f"  - 총 조회: {len(df)} 건")
        print(f"  - 성공 삽입: {success_count} 건")
        print(f"  - 실패: {len(df) - success_count} 건")
        
        return True
        
    except Exception as e:
        print(f"❌ 마이그레이션 실패: {e}")
        return False

if __name__ == "__main__":
    print("🚀 환경안전 지시서 데이터 마이그레이션 시작")
    print("=" * 50)
    
    if migrate_safety_instructions():
        print("✅ 마이그레이션 성공!")
    else:
        print("❌ 마이그레이션 실패!")
    
    print("=" * 50)
    input("Press Enter to exit...")