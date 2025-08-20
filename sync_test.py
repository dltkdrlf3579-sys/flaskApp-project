#!/usr/bin/env python3
"""
PostgreSQL 연동 및 동기화 테스트 스크립트
배포 후 데이터베이스 연결을 확인할 때 사용하세요.
"""

import sys
import logging
from database_config import db_config, partner_manager

def test_database_connection():
    """데이터베이스 연결 테스트"""
    print("=" * 60)
    print("📊 Flask Portal 데이터베이스 연결 테스트")
    print("=" * 60)
    
    # 설정 정보 출력
    print(f"🔧 외부 DB 활성화: {db_config.external_db_enabled}")
    if db_config.external_db_enabled:
        print(f"🔗 PostgreSQL 호스트: {db_config.pg_host}:{db_config.pg_port}")
        print(f"📁 데이터베이스: {db_config.pg_database}")
        print(f"👤 사용자: {db_config.pg_user}")
        print(f"📋 테이블: {db_config.pg_schema}.{db_config.pg_table}")
    
    print(f"💾 로컬 DB 경로: {db_config.local_db_path}")
    print()
    
    # PostgreSQL 연결 테스트
    if db_config.external_db_enabled:
        print("🔍 PostgreSQL 연결 테스트 중...")
        pg_conn = db_config.get_postgresql_connection()
        
        if pg_conn:
            try:
                cursor = pg_conn.cursor()
                cursor.execute("SELECT version();")
                version = cursor.fetchone()[0]
                print(f"✅ PostgreSQL 연결 성공")
                print(f"   버전: {version.split(',')[0]}")
                
                # 테이블 존재 확인
                cursor.execute(f"""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = %s AND table_name = %s
                    );
                """, (db_config.pg_schema, db_config.pg_table))
                
                table_exists = cursor.fetchone()[0]
                if table_exists:
                    cursor.execute(f"SELECT COUNT(*) FROM {db_config.pg_schema}.{db_config.pg_table}")
                    count = cursor.fetchone()[0]
                    print(f"✅ 테이블 '{db_config.pg_table}' 존재 - {count}개 레코드")
                else:
                    print(f"❌ 테이블 '{db_config.pg_schema}.{db_config.pg_table}'이 존재하지 않습니다")
                
                pg_conn.close()
                
            except Exception as e:
                print(f"❌ PostgreSQL 쿼리 실행 실패: {e}")
                pg_conn.close()
                return False
        else:
            print(f"❌ PostgreSQL 연결 실패")
            return False
    else:
        print("⚠️  외부 DB가 비활성화되어 있습니다 (샘플 데이터 모드)")
    
    # SQLite 연결 테스트
    print("\n🔍 SQLite 연결 테스트 중...")
    try:
        sqlite_conn = db_config.get_sqlite_connection()
        cursor = sqlite_conn.cursor()
        
        # 테이블 확인
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"✅ SQLite 연결 성공")
        print(f"   테이블: {', '.join(tables)}")
        
        # 각 테이블 레코드 수 확인
        for table in ['partners_cache', 'partner_details', 'partner_attachments']:
            if table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"   {table}: {count}개 레코드")
        
        sqlite_conn.close()
        
    except Exception as e:
        print(f"❌ SQLite 연결 실패: {e}")
        return False
    
    return True

def test_data_sync():
    """데이터 동기화 테스트"""
    print("\n" + "=" * 60)
    print("🔄 데이터 동기화 테스트")
    print("=" * 60)
    
    if not db_config.external_db_enabled:
        print("⚠️  외부 DB가 비활성화되어 있어 동기화를 건너뜁니다")
        return True
    
    print("🔍 동기화 필요 여부 확인 중...")
    should_sync = partner_manager.should_sync()
    print(f"   동기화 필요: {'예' if should_sync else '아니오'}")
    
    print("🔄 데이터 동기화 실행 중...")
    try:
        result = partner_manager.sync_partners_from_postgresql()
        if result:
            print("✅ 데이터 동기화 성공")
            
            # 동기화된 데이터 확인
            conn = db_config.get_sqlite_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM partners_cache")
            count = cursor.fetchone()[0]
            print(f"   동기화된 협력사 수: {count}개")
            
            if count > 0:
                cursor.execute("SELECT business_number, company_name FROM partners_cache LIMIT 3")
                samples = cursor.fetchall()
                print("   샘플 데이터:")
                for biz_num, company in samples:
                    print(f"     {biz_num} - {company}")
            
            conn.close()
            return True
        else:
            print("❌ 데이터 동기화 실패")
            return False
            
    except Exception as e:
        print(f"❌ 동기화 중 오류 발생: {e}")
        return False

def test_partner_operations():
    """협력사 데이터 조회 테스트"""
    print("\n" + "=" * 60)
    print("👥 협력사 데이터 조회 테스트")
    print("=" * 60)
    
    try:
        # 전체 협력사 수 확인
        partners, total_count = partner_manager.get_all_partners(page=1, per_page=5)
        print(f"✅ 협력사 목록 조회 성공")
        print(f"   총 협력사 수: {total_count}개")
        print(f"   조회된 샘플: {len(partners)}개")
        
        if len(partners) > 0:
            # 첫 번째 협력사 상세 조회
            first_partner = partners[0]
            business_number = first_partner['business_number']
            print(f"\n🔍 상세 정보 테스트: {business_number}")
            
            detail = partner_manager.get_partner_by_business_number(business_number)
            if detail:
                print(f"✅ 상세 정보 조회 성공")
                print(f"   회사명: {detail['company_name']}")
                print(f"   대표자: {detail.get('representative', 'N/A')}")
                print(f"   상세내용: {detail.get('detailed_content', '없음')}")
            else:
                print(f"❌ 상세 정보 조회 실패")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ 협력사 데이터 조회 실패: {e}")
        return False

def main():
    """메인 테스트 실행"""
    print("🚀 Flask Portal 배포 테스트 시작\n")
    
    # 로깅 설정
    logging.basicConfig(level=logging.INFO)
    
    results = []
    
    # 1. 데이터베이스 연결 테스트
    results.append(test_database_connection())
    
    # 2. 데이터 동기화 테스트
    results.append(test_data_sync())
    
    # 3. 협력사 데이터 조회 테스트  
    results.append(test_partner_operations())
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("📋 테스트 결과 요약")
    print("=" * 60)
    
    test_names = ["데이터베이스 연결", "데이터 동기화", "협력사 조회"]
    for i, (name, result) in enumerate(zip(test_names, results)):
        status = "✅ 성공" if result else "❌ 실패"
        print(f"{i+1}. {name}: {status}")
    
    all_passed = all(results)
    print(f"\n{'🎉 모든 테스트 통과!' if all_passed else '⚠️  일부 테스트 실패'}")
    
    if not all_passed:
        print("\n💡 문제 해결 방법:")
        print("1. config.ini 파일의 설정 확인")
        print("2. PostgreSQL 서버 연결 상태 확인")
        print("3. 네트워크 방화벽 설정 확인")
        print("4. 데이터베이스 권한 확인")
        print("5. app.log 파일에서 상세 오류 확인")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())