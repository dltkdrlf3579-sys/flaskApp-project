#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 7을 위한 샘플 데이터 생성
"""
import psycopg
import json
import random
import sys
import os

# Windows에서 한글 출력을 위한 인코딩 설정
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

def create_sample_tables():
    """Phase 7 테스트를 위한 샘플 테이블 생성"""
    dsn = 'postgresql://postgres:admin123@localhost:5432/portal_dev'
    
    try:
        conn = psycopg.connect(dsn)
        conn.autocommit = True
        cur = conn.cursor()
        
        # 기존 테이블 정리
        tables_to_drop = [
            'accidents_cache', 'safety_instructions_cache', 
            'follow_sop', 'full_process'
        ]
        
        for table in tables_to_drop:
            cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
            print(f"✅ {table} 기존 테이블 정리")
        
        # 1. accidents_cache 테이블
        cur.execute("""
            CREATE TABLE accidents_cache (
                id SERIAL PRIMARY KEY,
                item_name TEXT,
                custom_data JSONB DEFAULT '{}'::jsonb,
                is_deleted INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ accidents_cache 테이블 생성")
        
        # 2. safety_instructions_cache 테이블
        cur.execute("""
            CREATE TABLE safety_instructions_cache (
                id SERIAL PRIMARY KEY,
                item_name TEXT,
                custom_data JSONB DEFAULT '{}'::jsonb,
                is_deleted INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ safety_instructions_cache 테이블 생성")
        
        # 3. follow_sop 테이블
        cur.execute("""
            CREATE TABLE follow_sop (
                id SERIAL PRIMARY KEY,
                work_req_no TEXT,
                custom_data JSONB DEFAULT '{}'::jsonb,
                is_deleted INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ follow_sop 테이블 생성")
        
        # 4. full_process 테이블
        cur.execute("""
            CREATE TABLE full_process (
                id SERIAL PRIMARY KEY,
                fullprocess_number TEXT,
                custom_data JSONB DEFAULT '{}'::jsonb,
                is_deleted INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ full_process 테이블 생성")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ 테이블 생성 실패: {e}")
        return False

def insert_sample_data():
    """대량 샘플 데이터 삽입"""
    dsn = 'postgresql://postgres:admin123@localhost:5432/portal_dev'
    
    try:
        conn = psycopg.connect(dsn)
        conn.autocommit = True
        cur = conn.cursor()
        
        # 샘플 데이터 템플릿
        workplaces = ['공장A', '공장B', '공장C', '공장D', '사무실', '창고', '연구소']
        accident_types = ['낙하', '충돌', '화재', '누출', '감전', '절단', '화상']
        severities = ['낮음', '중간', '높음', '매우높음']
        departments = ['생산팀', '품질팀', '안전팀', '기술팀', '관리팀']
        
        # 1. accidents_cache 데이터 (5000개)
        print("📦 accidents_cache 데이터 삽입 중...")
        accident_data = []
        for i in range(5000):
            data = {
                'workplace': random.choice(workplaces),
                'accident_type': random.choice(accident_types),
                'severity': random.choice(severities),
                'department': random.choice(departments),
                'date': f'2024-{random.randint(1,12):02d}-{random.randint(1,28):02d}',
                'description': f'사고 설명 {i+1}',
                'reporter': f'담당자{i%100}',
                'status': random.choice(['처리중', '완료', '대기'])
            }
            accident_data.append((f'사고-{i+1:04d}', json.dumps(data, ensure_ascii=False)))
        
        cur.executemany(
            "INSERT INTO accidents_cache (item_name, custom_data) VALUES (%s, %s::jsonb)",
            accident_data
        )
        print(f"✅ accidents_cache: {len(accident_data):,}개 삽입")
        
        # 2. safety_instructions_cache 데이터 (3000개)
        print("📦 safety_instructions_cache 데이터 삽입 중...")
        safety_data = []
        violation_types = ['안전수칙위반', '보호구미착용', '작업절차무시', '위험지역출입']
        inspectors = ['안전담당자A', '안전담당자B', '안전담당자C', '외부검사원']
        
        for i in range(3000):
            data = {
                'workplace': random.choice(workplaces),
                'violation_type': random.choice(violation_types),
                'severity': random.choice(severities),
                'inspector': random.choice(inspectors),
                'date': f'2024-{random.randint(1,12):02d}-{random.randint(1,28):02d}',
                'corrective_action': f'개선조치 {i+1}',
                'due_date': f'2024-{random.randint(6,12):02d}-{random.randint(1,28):02d}'
            }
            safety_data.append((f'안전지시-{i+1:04d}', json.dumps(data, ensure_ascii=False)))
        
        cur.executemany(
            "INSERT INTO safety_instructions_cache (item_name, custom_data) VALUES (%s, %s::jsonb)",
            safety_data
        )
        print(f"✅ safety_instructions_cache: {len(safety_data):,}개 삽입")
        
        # 3. follow_sop 데이터 (2000개)
        print("📦 follow_sop 데이터 삽입 중...")
        sop_data = []
        process_types = ['품질검사', '설비점검', '안전점검', '정기보수', '긴급수리']
        statuses = ['시작', '진행중', '완료', '보류', '취소']
        
        for i in range(2000):
            data = {
                'workplace': random.choice(workplaces),
                'process_type': random.choice(process_types),
                'status': random.choice(statuses),
                'department': random.choice(departments),
                'assigned_to': f'담당자{i%50}',
                'priority': random.choice(['낮음', '보통', '높음', '긴급']),
                'estimated_hours': random.randint(1, 24)
            }
            sop_data.append((f'SOP-{i+1:04d}', json.dumps(data, ensure_ascii=False)))
        
        cur.executemany(
            "INSERT INTO follow_sop (work_req_no, custom_data) VALUES (%s, %s::jsonb)",
            sop_data
        )
        print(f"✅ follow_sop: {len(sop_data):,}개 삽입")
        
        # 4. full_process 데이터 (1500개)
        print("📦 full_process 데이터 삽입 중...")
        process_data = []
        process_names = ['제품조립', '품질검증', '포장작업', '출하준비', '재고관리']
        
        for i in range(1500):
            data = {
                'workplace': random.choice(workplaces),
                'process_name': random.choice(process_names),
                'status': random.choice(statuses),
                'department': random.choice(departments),
                'batch_no': f'BATCH-{i+1:04d}',
                'quantity': random.randint(10, 1000),
                'completion_rate': random.randint(0, 100)
            }
            process_data.append((f'PROC-{i+1:04d}', json.dumps(data, ensure_ascii=False)))
        
        cur.executemany(
            "INSERT INTO full_process (fullprocess_number, custom_data) VALUES (%s, %s::jsonb)",
            process_data
        )
        print(f"✅ full_process: {len(process_data):,}개 삽입")
        
        # 통계 정보 업데이트
        cur.execute("ANALYZE")
        print("✅ 통계 정보 업데이트 완료")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ 데이터 삽입 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_sample_data():
    """샘플 데이터 검증"""
    dsn = 'postgresql://postgres:admin123@localhost:5432/portal_dev'
    
    try:
        conn = psycopg.connect(dsn)
        cur = conn.cursor()
        
        tables = ['accidents_cache', 'safety_instructions_cache', 'follow_sop', 'full_process']
        
        print("\n=== 샘플 데이터 검증 ===")
        for table in tables:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            
            # JSON 키 샘플 조회
            cur.execute(f"""
                SELECT DISTINCT jsonb_object_keys(custom_data) 
                FROM {table} 
                LIMIT 5
            """)
            keys = [row[0] for row in cur.fetchall()]
            
            print(f"📊 {table}: {count:,}개 행, JSON 키: {', '.join(keys)}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ 검증 실패: {e}")
        return False

def main():
    """메인 실행"""
    print("=== Phase 7 샘플 데이터 생성 ===")
    
    # 1. 테이블 생성
    if not create_sample_tables():
        return False
    
    # 2. 샘플 데이터 삽입
    if not insert_sample_data():
        return False
    
    # 3. 데이터 검증
    if not verify_sample_data():
        return False
    
    print("\n🎉 Phase 7 샘플 데이터 생성 완료!")
    print("이제 phase7_performance_optimization.py를 실행할 수 있습니다.")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)