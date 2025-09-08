#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
외부 DB 연동 테스트 스크립트
운영 서버에서 실행하여 IQADB 연결 확인
"""

import sys
import os
import configparser
import traceback

# 설정 파일 로드
config = configparser.ConfigParser()
config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
config.read(config_path, encoding='utf-8')

print("=" * 70)
print("외부 DB 연동 테스트")
print("=" * 70)

# 1. 설정 확인
print("\n1. 설정 파일 확인:")
print(f"   config.ini 경로: {config_path}")
print(f"   config.ini 존재: {os.path.exists(config_path)}")

module_path = config.get('DATABASE', 'IQADB_MODULE_PATH', fallback='없음')
print(f"   IQADB_MODULE_PATH: {module_path}")
print(f"   경로 존재: {os.path.exists(module_path)}")

external_enabled = config.getboolean('DATABASE', 'EXTERNAL_DB_ENABLED', fallback=False)
print(f"   EXTERNAL_DB_ENABLED: {external_enabled}")

# 2. IQADB 모듈 로드 시도
print("\n2. IQADB 모듈 로드 시도:")
try:
    sys.path.insert(0, os.path.abspath(module_path))
    print(f"   sys.path에 추가: {module_path}")
    
    # 디렉토리 내용 확인
    if os.path.exists(module_path):
        files = os.listdir(module_path)
        print(f"   디렉토리 내 파일들: {files[:5]}...")  # 처음 5개만
        
        # IQADB_CONNECT310 파일 찾기
        iqadb_files = [f for f in files if 'IQADB' in f.upper()]
        print(f"   IQADB 관련 파일: {iqadb_files}")
    
    from IQADB_CONNECT310 import *
    print("   [성공] IQADB_CONNECT310 모듈 로드 성공!")
    IQADB_AVAILABLE = True
    
except ImportError as e:
    print(f"   [실패] ImportError: {e}")
    IQADB_AVAILABLE = False
except Exception as e:
    print(f"   [실패] 예외 발생: {e}")
    traceback.print_exc()
    IQADB_AVAILABLE = False

if not IQADB_AVAILABLE:
    print("\n[오류] IQADB 모듈을 로드할 수 없습니다!")
    print("해결 방법:")
    print("1. config.ini의 IQADB_MODULE_PATH를 확인하세요")
    print("2. 실제 IQADB 모듈이 설치된 경로를 지정하세요")
    print("3. IQADB_CONNECT310.pyd 또는 .py 파일이 있는지 확인하세요")
    sys.exit(1)

# 3. DB 연결 테스트
print("\n3. DB 연결 테스트:")
try:
    conn = iqadb1()
    print("   [성공] iqadb1() 연결 성공!")
    
    # 간단한 쿼리 테스트
    with conn.cursor() as cur:
        # 테스트 쿼리 (현재 날짜 조회)
        cur.execute("SELECT SYSDATE FROM DUAL")
        result = cur.fetchone()
        print(f"   [성공] 테스트 쿼리 실행: {result}")
    
    conn.close()
    print("   [성공] 연결 종료")
    
except Exception as e:
    print(f"   [실패] DB 연결 오류: {e}")
    traceback.print_exc()
    sys.exit(1)

# 4. 실제 쿼리 테스트
print("\n4. 실제 데이터 조회 테스트:")

# 쿼리 섹션 확인
if config.has_section('MASTER_DATA_QUERIES'):
    print("   [MASTER_DATA_QUERIES] 섹션 발견")
    
    # 각 쿼리 테스트
    queries_to_test = [
        ('PARTNERS_EXTERNAL_QUERY', '협력사'),
        ('ACCIDENTS_EXTERNAL_QUERY', '사고'),
        ('SAFETY_INSTRUCTIONS_EXTERNAL_QUERY', '안전지시서')
    ]
    
    for query_key, name in queries_to_test:
        if config.has_option('MASTER_DATA_QUERIES', query_key):
            print(f"\n   [{name} 데이터]")
            query = config.get('MASTER_DATA_QUERIES', query_key)
            print(f"   쿼리: {query[:100]}...")
            
            try:
                conn = iqadb1()
                with conn.cursor() as cur:
                    cur.execute(query)
                    data = cur.fetchall()
                    print(f"   [성공] {len(data)}개 레코드 조회됨")
                    
                    if data and len(data) > 0:
                        # 첫 번째 레코드의 컬럼 확인
                        col_names = [desc[0] for desc in cur.description]
                        print(f"   컬럼: {col_names[:5]}...")  # 처음 5개 컬럼만
                        print(f"   샘플 데이터: {data[0][:3]}...")  # 첫 레코드의 처음 3개 값
                
                conn.close()
                
            except Exception as e:
                print(f"   [실패] 쿼리 실행 오류: {e}")
        else:
            print(f"   [{name}] 쿼리 설정 없음")
else:
    print("   [오류] MASTER_DATA_QUERIES 섹션이 없습니다!")
    print("   config.ini에 다음 섹션을 추가하세요:")
    print("""
[MASTER_DATA_QUERIES]
PARTNERS_EXTERNAL_QUERY = SELECT * FROM 협력사테이블
ACCIDENTS_EXTERNAL_QUERY = SELECT * FROM 사고테이블
SAFETY_INSTRUCTIONS_EXTERNAL_QUERY = SELECT * FROM 안전지시서테이블
    """)

print("\n" + "=" * 70)
print("테스트 완료")
print("=" * 70)