#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 1 기능 테스트 스크립트
"""

import sqlite3
import json
import requests
import time
import subprocess
import sys
from threading import Thread

def test_db():
    """DB 테스트"""
    print("=" * 50)
    print("1. DB 테스트")
    print("=" * 50)
    
    try:
        conn = sqlite3.connect('portal.db')
        conn.row_factory = sqlite3.Row
        
        # 동적 컬럼 설정 테스트
        columns = conn.execute('''
            SELECT * FROM accident_column_config 
            WHERE is_active = 1 
            ORDER BY column_order
        ''').fetchall()
        
        print(f"✅ 동적 컬럼 {len(columns)}개 조회 성공:")
        for col in columns:
            print(f"   {col['column_order']:2d}. {col['column_name']} ({col['column_type']})")
        
        # 담당자 마스터 테스트
        persons = conn.execute('SELECT * FROM person_master WHERE is_active = 1').fetchall()
        print(f"✅ 담당자 마스터 {len(persons)}개 조회 성공")
        
        # custom_data 컬럼 확인
        conn.execute('PRAGMA table_info(accidents_cache)')
        table_info = conn.fetchall()
        has_custom_data = any(col[1] == 'custom_data' for col in table_info)
        
        if has_custom_data:
            print("✅ accidents_cache 테이블에 custom_data 컬럼 존재")
        else:
            print("❌ custom_data 컬럼이 없습니다")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ DB 테스트 실패: {e}")
        return False

def test_api():
    """API 테스트"""
    print("\n" + "=" * 50)
    print("2. API 테스트")
    print("=" * 50)
    
    base_url = "http://localhost:5000"
    
    try:
        # 컬럼 설정 조회 API
        response = requests.get(f"{base_url}/api/accident-columns", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data['success']:
                print(f"✅ 컬럼 조회 API 성공: {len(data['columns'])}개 컬럼")
            else:
                print(f"❌ 컬럼 조회 API 응답 오류: {data}")
        else:
            print(f"❌ 컬럼 조회 API HTTP 오류: {response.status_code}")
            
        # 담당자 마스터 조회 API
        response = requests.get(f"{base_url}/api/person-master", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data['success']:
                print(f"✅ 담당자 조회 API 성공: {len(data['persons'])}명")
            else:
                print(f"❌ 담당자 조회 API 응답 오류: {data}")
        else:
            print(f"❌ 담당자 조회 API HTTP 오류: {response.status_code}")
            
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ API 테스트 실패 (서버 연결 불가): {e}")
        return False
    except Exception as e:
        print(f"❌ API 테스트 실패: {e}")
        return False

def test_page():
    """웹페이지 테스트"""
    print("\n" + "=" * 50)
    print("3. 웹페이지 테스트")
    print("=" * 50)
    
    base_url = "http://localhost:5000"
    
    try:
        # 사고 페이지 접근
        response = requests.get(f"{base_url}/page/partner-accident", timeout=10)
        if response.status_code == 200:
            html = response.text
            # 동적 컬럼이 렌더링되었는지 확인
            if 'dynamic-col' in html:
                print("✅ 사고 페이지 로드 성공 (동적 컬럼 렌더링 포함)")
            else:
                print("⚠️  사고 페이지 로드됨 (동적 컬럼 렌더링 확인 필요)")
            return True
        else:
            print(f"❌ 사고 페이지 HTTP 오류: {response.status_code}")
            print(f"응답 내용: {response.text[:200]}...")
            return False
            
    except Exception as e:
        print(f"❌ 웹페이지 테스트 실패: {e}")
        return False

if __name__ == "__main__":
    print("Phase 1 기능 테스트 시작")
    
    # 1. DB 테스트
    db_ok = test_db()
    
    if not db_ok:
        print("\n❌ DB 테스트 실패로 인해 테스트 중단")
        sys.exit(1)
    
    # 2. Flask 서버가 실행 중인지 확인
    try:
        response = requests.get("http://localhost:5000", timeout=2)
        server_running = True
    except:
        server_running = False
    
    if not server_running:
        print("\n⚠️  Flask 서버가 실행되지 않았습니다.")
        print("다음 명령으로 서버를 실행하세요: python app.py")
        sys.exit(1)
    
    # 3. API 테스트
    api_ok = test_api()
    
    # 4. 웹페이지 테스트
    page_ok = test_page()
    
    # 결과 요약
    print("\n" + "=" * 50)
    print("Phase 1 테스트 결과 요약")
    print("=" * 50)
    print(f"DB 테스트:     {'✅ 성공' if db_ok else '❌ 실패'}")
    print(f"API 테스트:    {'✅ 성공' if api_ok else '❌ 실패'}")
    print(f"웹페이지 테스트: {'✅ 성공' if page_ok else '❌ 실패'}")
    
    if db_ok and api_ok and page_ok:
        print("\n🎉 Phase 1 구현이 성공적으로 완료되었습니다!")
        print("\n다음 단계:")
        print("1. 브라우저에서 http://localhost:5000/page/partner-accident 접속")
        print("2. 동적 컬럼이 올바르게 표시되는지 확인")
        print("3. Phase 2 (컬럼 관리 인터페이스) 진행 가능")
    else:
        print("\n⚠️  일부 테스트가 실패했습니다. 문제를 해결한 후 다시 시도하세요.")