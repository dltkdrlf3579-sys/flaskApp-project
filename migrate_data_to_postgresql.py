#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
긴급! SQLite → PostgreSQL 데이터 마이그레이션
모든 기존 데이터를 PostgreSQL로 복사
"""
import sqlite3
from db_connection import get_db_connection
from db.upsert import safe_upsert
import json

def migrate_all_data():
    """모든 데이터를 SQLite에서 PostgreSQL로 마이그레이션"""
    
    # SQLite 연결
    sqlite_conn = sqlite3.connect('portal.db')
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cursor = sqlite_conn.cursor()
    
    # PostgreSQL 연결
    pg_conn = get_db_connection()
    pg_cursor = pg_conn.cursor()
    
    migration_results = {}
    
    # 1. partners_cache 마이그레이션
    print("\n=== partners_cache 마이그레이션 시작 ===")
    sqlite_cursor.execute("SELECT * FROM partners_cache")
    partners = sqlite_cursor.fetchall()
    
    success_count = 0
    for partner in partners:
        try:
            data = dict(partner)
            safe_upsert(pg_conn, 'partners_cache', data, 
                       conflict_cols=['business_number'])
            success_count += 1
            if success_count % 10 == 0:
                print(f"  {success_count}개 처리...")
        except Exception as e:
            print(f"  오류: {data.get('business_number')} - {e}")
    
    migration_results['partners_cache'] = success_count
    print(f"✅ partners_cache: {success_count}/{len(partners)}개 완료")
    
    # 2. accidents_cache 마이그레이션
    print("\n=== accidents_cache 마이그레이션 시작 ===")
    sqlite_cursor.execute("SELECT * FROM accidents_cache")
    accidents = sqlite_cursor.fetchall()
    
    success_count = 0
    for accident in accidents:
        try:
            data = dict(accident)
            # custom_data가 문자열이면 JSON으로 파싱
            if 'custom_data' in data and isinstance(data['custom_data'], str):
                try:
                    data['custom_data'] = json.loads(data['custom_data'])
                except:
                    data['custom_data'] = {}
            
            safe_upsert(pg_conn, 'accidents_cache', data,
                       conflict_cols=['id'])
            success_count += 1
        except Exception as e:
            print(f"  오류: {data.get('id')} - {e}")
    
    migration_results['accidents_cache'] = success_count
    print(f"✅ accidents_cache: {success_count}/{len(accidents)}개 완료")
    
    # 3. safety_instructions_cache 마이그레이션
    print("\n=== safety_instructions_cache 마이그레이션 시작 ===")
    sqlite_cursor.execute("SELECT * FROM safety_instructions_cache")
    safety_instructions = sqlite_cursor.fetchall()
    
    success_count = 0
    for instruction in safety_instructions:
        try:
            data = dict(instruction)
            if 'custom_data' in data and isinstance(data['custom_data'], str):
                try:
                    data['custom_data'] = json.loads(data['custom_data'])
                except:
                    data['custom_data'] = {}
            
            safe_upsert(pg_conn, 'safety_instructions_cache', data,
                       conflict_cols=['id'])
            success_count += 1
        except Exception as e:
            print(f"  오류: {data.get('id')} - {e}")
    
    migration_results['safety_instructions_cache'] = success_count
    print(f"✅ safety_instructions_cache: {success_count}/{len(safety_instructions)}개 완료")
    
    # 4. 기타 테이블들
    other_tables = [
        'accident_column_config',
        'partner_details',
        'accident_details',
        'buildings_cache',
        'departments_cache',
        'employees_cache',
        'contractors_cache',
        'dropdown_codes'
    ]
    
    for table in other_tables:
        try:
            sqlite_cursor.execute(f"SELECT * FROM {table}")
            rows = sqlite_cursor.fetchall()
            
            if rows:
                print(f"\n=== {table} 마이그레이션 시작 ===")
                success_count = 0
                for row in rows:
                    try:
                        data = dict(row)
                        # 각 테이블의 PK 찾기
                        if 'id' in data:
                            conflict_cols = ['id']
                        elif 'business_number' in data:
                            conflict_cols = ['business_number']
                        elif 'accident_number' in data:
                            conflict_cols = ['accident_number']
                        else:
                            # PK가 없으면 INSERT만
                            pg_cursor.execute(
                                f"INSERT INTO {table} VALUES ({','.join(['?' for _ in data])})",
                                tuple(data.values())
                            )
                            pg_conn.commit()
                            success_count += 1
                            continue
                        
                        safe_upsert(pg_conn, table, data, conflict_cols=conflict_cols)
                        success_count += 1
                    except Exception as e:
                        print(f"  오류: {e}")
                
                migration_results[table] = success_count
                print(f"✅ {table}: {success_count}/{len(rows)}개 완료")
        except Exception as e:
            print(f"⚠️  {table} 테이블 스킵: {e}")
    
    # 커밋
    pg_conn.commit()
    
    # 결과 요약
    print("\n" + "="*50)
    print("📊 마이그레이션 완료 요약:")
    print("="*50)
    
    total = 0
    for table, count in migration_results.items():
        print(f"  {table}: {count}개")
        total += count
    
    print(f"\n✅ 총 {total}개 레코드 마이그레이션 완료!")
    
    # 연결 종료
    sqlite_conn.close()
    pg_conn.close()
    
    return migration_results

if __name__ == "__main__":
    print("=== SQLite → PostgreSQL 데이터 마이그레이션 ===")
    print("⚠️  기존 SQLite 데이터를 PostgreSQL로 복사합니다.")
    
    migrate_all_data()
    
    print("\n🎉 마이그레이션 완료! Flask 앱을 다시 실행하세요.")