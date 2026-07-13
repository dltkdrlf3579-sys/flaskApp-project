"""
IQADB 스키마 생성 및 테스트 데이터 삽입 스크립트
"""
import psycopg2
from psycopg2 import sql
import sys

def create_and_populate_iqadb():
    """IQADB 스키마와 테이블 생성 및 테스트 데이터 삽입"""

    # 데이터베이스 연결
    try:
        conn = psycopg2.connect(
            host="localhost",
            database="portal_dev",
            user="postgres",
            password="admin123"
        )
        conn.autocommit = False
        cursor = conn.cursor()
        print("[SUCCESS] PostgreSQL connection successful")
    except Exception as e:
        print(f"[ERROR] Database connection failed: {e}")
        sys.exit(1)

    try:
        # 1. 스키마 생성
        print("\n[INFO] Creating IQADB schema...")
        cursor.execute("CREATE SCHEMA IF NOT EXISTS iqadb")
        print("  [SUCCESS] Schema created")

        # 2. 기존 테이블 삭제
        print("\n[INFO] Dropping existing tables...")
        tables_to_drop = [
            'partners', 'accidents', 'buildings', 'departments',
            'contractors', 'employees', 'divisions', 'safety_instructions',
            '"외부_followsop_테이블"', '"외부_fullprocess_테이블"',
            '"외부_partner_change_requests_테이블"', 'safe_workplace'
        ]

        for table in tables_to_drop:
            cursor.execute(f"DROP TABLE IF EXISTS iqadb.{table} CASCADE")
            print(f"  - Dropping {table} table")

        # 3. 테이블 생성 및 데이터 삽입
        print("\n[INFO] Creating tables and inserting data...")

        # Partners 테이블
        cursor.execute("""
            CREATE TABLE iqadb.partners (
                business_number VARCHAR(20) PRIMARY KEY,
                company_name VARCHAR(100) NOT NULL,
                partner_class VARCHAR(50),
                business_type_major VARCHAR(100),
                business_type_minor VARCHAR(100),
                hazard_work_flag BOOLEAN DEFAULT false,
                representative VARCHAR(100),
                address TEXT,
                average_age INTEGER,
                annual_revenue BIGINT,
                transaction_count INTEGER,
                permanent_workers INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            INSERT INTO iqadb.partners VALUES
            ('123-45-67890', '삼성건설(주)', 'A급', '건설업', '토목공사', true, '김철수', '서울시 강남구 테헤란로 123', 38, 5000000000, 150, 250),
            ('234-56-78901', '현대안전기술', 'B급', '서비스업', '안전관리', true, '이영희', '서울시 송파구 올림픽로 456', 42, 3000000000, 80, 120),
            ('345-67-89012', 'LG환경서비스', 'A급', '서비스업', '환경관리', false, '박민수', '경기도 성남시 분당구 판교로 789', 35, 4500000000, 200, 180),
            ('456-78-90123', 'SK에너지솔루션', 'A급', '제조업', '에너지설비', true, '최강현', '울산시 남구 산업로 321', 40, 8000000000, 300, 450),
            ('567-89-01234', '포스코건설', 'A급', '건설업', '플랜트시공', true, '정대표', '포항시 남구 동해안로 654', 39, 7500000000, 250, 380)
        """)
        print("  [SUCCESS] partners table created with 5 records")

        # Accidents 테이블
        cursor.execute("""
            CREATE TABLE iqadb.accidents (
                accident_number VARCHAR(20) PRIMARY KEY,
                accident_name VARCHAR(200),
                workplace VARCHAR(100),
                accident_grade VARCHAR(50),
                major_category VARCHAR(100),
                injury_form VARCHAR(100),
                injury_type VARCHAR(100),
                accident_date DATE,
                day_of_week VARCHAR(20),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                building VARCHAR(100),
                floor VARCHAR(20),
                location_category VARCHAR(100),
                location_detail TEXT
            )
        """)

        cursor.execute("""
            INSERT INTO iqadb.accidents VALUES
            ('ACC-2024-001', '고소작업 중 추락사고', '제1공장', '중대재해', '추락', '골절', '다리골절', '2024-01-15', '월요일', CURRENT_TIMESTAMP, 'A동', '3층', '생산라인', '조립라인 #3'),
            ('ACC-2024-002', '지게차 충돌사고', '물류창고', '경미', '충돌', '타박상', '경미한타박', '2024-01-20', '토요일', CURRENT_TIMESTAMP, 'B동', '1층', '물류구역', '적재구역 B-2'),
            ('ACC-2024-003', '화학물질 누출', '제2공장', '중대재해', '화학사고', '화상', '2도화상', '2024-02-10', '토요일', CURRENT_TIMESTAMP, 'C동', '2층', '화학물질보관소', '탱크 #5'),
            ('ACC-2024-004', '협착사고', '제3공장', '일반재해', '협착', '골절', '손가락골절', '2024-02-25', '일요일', CURRENT_TIMESTAMP, 'D동', '1층', '프레스작업장', '프레스기 #2'),
            ('ACC-2024-005', '감전사고', '전기실', '중대재해', '감전', '화상', '전기화상', '2024-03-05', '화요일', CURRENT_TIMESTAMP, 'E동', '지하1층', '전기실', '배전반 구역')
        """)
        print("  [SUCCESS] accidents table created with 5 records")

        # Buildings 테이블
        cursor.execute("""
            CREATE TABLE iqadb.buildings (
                building_code VARCHAR(20) PRIMARY KEY,
                building_name VARCHAR(100) NOT NULL,
                site VARCHAR(100),
                site_type VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            INSERT INTO iqadb.buildings VALUES
            ('BLD-001', '본관', '본사', '사무동'),
            ('BLD-002', '제1공장', '제1산업단지', '생산시설'),
            ('BLD-003', '제2공장', '제2산업단지', '생산시설'),
            ('BLD-004', '물류센터', '물류단지', '물류시설'),
            ('BLD-005', '연구소', '연구단지', '연구시설')
        """)
        print("  [SUCCESS] buildings table created with 5 records")

        # Departments 테이블
        cursor.execute("""
            CREATE TABLE iqadb.departments (
                dept_code VARCHAR(20) PRIMARY KEY,
                dept_name VARCHAR(100) NOT NULL,
                parent_dept_code VARCHAR(20),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            INSERT INTO iqadb.departments VALUES
            ('DEPT000', '전산팀', NULL),
            ('DEPT001', '경영진', NULL),
            ('DEPT100', '안전관리팀', 'DEPT001'),
            ('DEPT101', '안전관리1파트', 'DEPT100'),
            ('DEPT102', '안전관리2파트', 'DEPT100'),
            ('DEPT200', '생산부', 'DEPT001'),
            ('DEPT201', '생산1팀', 'DEPT200'),
            ('DEPT202', '생산2팀', 'DEPT200'),
            ('DEPT300', '구매팀', 'DEPT001'),
            ('DEPT400', '감사팀', 'DEPT001')
        """)
        print("  [SUCCESS] departments table created with 10 records")

        # Contractors 테이블
        cursor.execute("""
            CREATE TABLE iqadb.contractors (
                worker_id VARCHAR(20) PRIMARY KEY,
                worker_name VARCHAR(100) NOT NULL,
                company_name VARCHAR(100),
                business_number VARCHAR(20),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            INSERT INTO iqadb.contractors VALUES
            ('CTR-001', '김협력', '삼성건설(주)', '123-45-67890'),
            ('CTR-002', '이외주', '현대안전기술', '234-56-78901'),
            ('CTR-003', '박도급', 'LG환경서비스', '345-67-89012'),
            ('CTR-004', '최계약', 'SK에너지솔루션', '456-78-90123'),
            ('CTR-005', '정파견', '포스코건설', '567-89-01234')
        """)
        print("  [SUCCESS] contractors table created with 5 records")

        # Employees 테이블
        cursor.execute("""
            CREATE TABLE iqadb.employees (
                employee_id VARCHAR(20) PRIMARY KEY,
                employee_name VARCHAR(100) NOT NULL,
                department_name VARCHAR(100),
                position VARCHAR(50),
                email VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            INSERT INTO iqadb.employees VALUES
            ('EMP000', '개발슈퍼관리자', '전산팀', '팀장', 'super@company.com'),
            ('EMP001', '김대표', '경영진', '대표이사', 'ceo@company.com'),
            ('EMP100', '박안전', '안전관리팀', '팀장', 'safety.manager@company.com'),
            ('EMP101', '이안전', '안전관리1파트', '대리', 'safety.staff@company.com'),
            ('EMP200', '최생산', '생산부', '과장', 'prod.manager@company.com'),
            ('EMP201', '홍길동', '생산1팀', '사원', 'hong@company.com'),
            ('EMP300', '정협력', '구매팀', '차장', 'vendor@company.com'),
            ('EMP400', '감사원', '감사팀', '부장', 'audit@company.com')
        """)
        print("  [SUCCESS] employees table created with 8 records")

        # Divisions 테이블
        cursor.execute("""
            CREATE TABLE iqadb.divisions (
                division_code VARCHAR(20) PRIMARY KEY,
                division_name VARCHAR(100) NOT NULL,
                parent_division_code VARCHAR(20),
                division_level INTEGER,
                division_manager VARCHAR(100),
                division_location VARCHAR(200),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            INSERT INTO iqadb.divisions VALUES
            ('DIV-001', '서울본부', NULL, 1, '김본부장', '서울시 강남구'),
            ('DIV-002', '경기지부', 'DIV-001', 2, '이지부장', '경기도 성남시'),
            ('DIV-003', '울산공장', NULL, 1, '박공장장', '울산시 남구'),
            ('DIV-004', '포항공장', NULL, 1, '최공장장', '포항시 남구'),
            ('DIV-005', '연구개발센터', 'DIV-001', 2, '정센터장', '대전시 유성구')
        """)
        print("  [SUCCESS] divisions table created with 5 records")

        # Safety Instructions 테이블
        cursor.execute("""
            CREATE TABLE iqadb.safety_instructions (
                issue_number VARCHAR(20) PRIMARY KEY,
                issue_date DATE,
                company_name VARCHAR(100),
                violation_content TEXT,
                corrective_action TEXT,
                department VARCHAR(100),
                responsible_person VARCHAR(100),
                completion_status VARCHAR(50),
                completion_date DATE,
                is_deleted INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            INSERT INTO iqadb.safety_instructions VALUES
            ('SI-2024-001', '2024-01-10', '삼성건설(주)', '안전모 미착용', '안전교육 실시 및 경고조치', '안전관리팀', '박안전', '완료', '2024-01-15', 0),
            ('SI-2024-002', '2024-01-25', '현대안전기술', '작업장 정리정돈 불량', '5S 활동 강화 및 재교육', '생산1팀', '최생산', '진행중', NULL, 0),
            ('SI-2024-003', '2024-02-05', 'LG환경서비스', '화학물질 보관 규정 위반', '보관함 정비 및 표시 개선', '안전관리팀', '이안전', '완료', '2024-02-10', 0),
            ('SI-2024-004', '2024-02-20', 'SK에너지솔루션', '고소작업 안전조치 미흡', '안전난간 설치 및 안전대 지급', '생산2팀', '홍길동', '계획', NULL, 0),
            ('SI-2024-005', '2024-03-01', '포스코건설', '소화기 점검 누락', '소화기 전수점검 및 교체', '안전관리팀', '박안전', '진행중', NULL, 0)
        """)
        print("  [SUCCESS] safety_instructions table created with 5 records")

        # 외부_followsop_테이블
        cursor.execute("""
            CREATE TABLE iqadb."외부_followsop_테이블" (
                sop_id SERIAL PRIMARY KEY,
                sop_number VARCHAR(50),
                sop_title VARCHAR(200),
                department VARCHAR(100),
                process_area VARCHAR(100),
                compliance_rate NUMERIC(5,2),
                last_review_date DATE,
                next_review_date DATE,
                assigned_user_id VARCHAR(20),
                assigned_dept_code VARCHAR(20),
                status VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            INSERT INTO iqadb."외부_followsop_테이블"
            (sop_number, sop_title, department, process_area, compliance_rate, last_review_date, next_review_date, assigned_user_id, assigned_dept_code, status) VALUES
            ('SOP-001', '고소작업 안전 절차', '안전관리팀', '작업안전', 95.5, '2024-01-01', '2024-07-01', 'EMP100', 'DEPT100', '정상'),
            ('SOP-002', '화학물질 취급 절차', '생산1팀', '화학안전', 88.0, '2024-01-15', '2024-07-15', 'EMP201', 'DEPT201', '개선필요'),
            ('SOP-003', '지게차 운전 절차', '물류팀', '운송안전', 92.3, '2023-12-01', '2024-06-01', 'EMP200', 'DEPT200', '정상'),
            ('SOP-004', '전기작업 안전 절차', '전기팀', '전기안전', 97.8, '2024-02-01', '2024-08-01', 'EMP101', 'DEPT101', '우수'),
            ('SOP-005', '비상대응 절차', '안전관리팀', '비상대응', 85.2, '2024-01-20', '2024-07-20', 'EMP100', 'DEPT100', '개선필요')
        """)
        print("  [SUCCESS] followsop table created with 5 records")

        # 외부_fullprocess_테이블
        cursor.execute("""
            CREATE TABLE iqadb."외부_fullprocess_테이블" (
                process_id SERIAL PRIMARY KEY,
                process_number VARCHAR(50),
                process_name VARCHAR(200),
                process_type VARCHAR(100),
                department VARCHAR(100),
                start_date DATE,
                end_date DATE,
                progress_rate NUMERIC(5,2),
                responsible_user_id VARCHAR(20),
                responsible_dept_code VARCHAR(20),
                status VARCHAR(50),
                risk_level VARCHAR(20),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            INSERT INTO iqadb."외부_fullprocess_테이블"
            (process_number, process_name, process_type, department, start_date, end_date, progress_rate, responsible_user_id, responsible_dept_code, status, risk_level) VALUES
            ('FP-2024-001', '신규 생산라인 구축', '설비투자', '생산부', '2024-01-01', '2024-06-30', 45.5, 'EMP200', 'DEPT200', '진행중', '중'),
            ('FP-2024-002', '안전관리시스템 개선', '시스템개선', '안전관리팀', '2024-02-01', '2024-05-31', 78.3, 'EMP100', 'DEPT100', '진행중', '낮음'),
            ('FP-2024-003', '협력사 평가체계 구축', '제도개선', '구매팀', '2024-01-15', '2024-04-15', 92.0, 'EMP300', 'DEPT300', '완료예정', '낮음'),
            ('FP-2024-004', '환경설비 교체', '설비투자', '생산2팀', '2024-03-01', '2024-08-31', 25.5, 'EMP201', 'DEPT202', '진행중', '높음'),
            ('FP-2024-005', '품질관리 프로세스 재정립', '프로세스개선', '품질팀', '2024-02-15', '2024-07-15', 60.0, 'EMP400', 'DEPT400', '진행중', '중')
        """)
        print("  [SUCCESS] fullprocess table created with 5 records")

        # 외부_partner_change_requests_테이블
        cursor.execute("""
            CREATE TABLE iqadb."외부_partner_change_requests_테이블" (
                request_id SERIAL PRIMARY KEY,
                request_number VARCHAR(50),
                business_number VARCHAR(20),
                company_name VARCHAR(100),
                change_type VARCHAR(100),
                change_content TEXT,
                request_date DATE,
                requester VARCHAR(100),
                department VARCHAR(100),
                approval_status VARCHAR(50),
                approval_date DATE,
                approver VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            INSERT INTO iqadb."외부_partner_change_requests_테이블"
            (request_number, business_number, company_name, change_type, change_content, request_date, requester, department, approval_status, approval_date, approver) VALUES
            ('PCR-2024-001', '123-45-67890', '삼성건설(주)', '대표자변경', '대표자 김철수 → 이철수 변경', '2024-01-10', '정협력', '구매팀', '승인', '2024-01-12', '김대표'),
            ('PCR-2024-002', '234-56-78901', '현대안전기술', '주소변경', '본사 이전: 서울 → 경기', '2024-01-25', '정협력', '구매팀', '검토중', NULL, NULL),
            ('PCR-2024-003', '345-67-89012', 'LG환경서비스', '사업분야추가', '폐기물처리업 추가', '2024-02-05', '정협력', '구매팀', '승인', '2024-02-07', '김대표'),
            ('PCR-2024-004', '456-78-90123', 'SK에너지솔루션', '등급변경', 'B급 → A급 상향 요청', '2024-02-20', '정협력', '구매팀', '반려', '2024-02-22', '박안전'),
            ('PCR-2024-005', '567-89-01234', '포스코건설', '계약조건변경', '단가 조정 요청', '2024-03-01', '정협력', '구매팀', '검토중', NULL, NULL)
        """)
        print("  [SUCCESS] partner_change_requests table created with 5 records")

        # Safe Workplace 테이블
        cursor.execute("""
            CREATE TABLE iqadb.safe_workplace (
                inspection_id SERIAL PRIMARY KEY,
                inspection_number VARCHAR(50),
                inspection_date DATE,
                inspection_type VARCHAR(100),
                location VARCHAR(200),
                inspector_id VARCHAR(20),
                inspector_name VARCHAR(100),
                inspection_dept_code VARCHAR(20),
                department VARCHAR(100),
                violation_count INTEGER DEFAULT 0,
                violation_content TEXT,
                corrective_action TEXT,
                risk_level VARCHAR(20),
                completion_status VARCHAR(50),
                completion_date DATE,
                notes TEXT,
                is_deleted INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            INSERT INTO iqadb.safe_workplace
            (inspection_number, inspection_date, inspection_type, location, inspector_id, inspector_name, inspection_dept_code, department, violation_count, violation_content, corrective_action, risk_level, completion_status, completion_date, notes) VALUES
            ('SW-2024-001', '2024-01-10', '정기점검', '제1공장 A동', 'EMP100', '박안전', 'DEPT100', '안전관리팀', 3, '안전모 미착용 2건, 통로 물건적치 1건', '즉시 시정 및 교육실시', '중', '완료', '2024-01-11', '전반적으로 양호함'),
            ('SW-2024-002', '2024-01-20', '특별점검', '물류센터', 'EMP101', '이안전', 'DEPT101', '안전관리1파트', 5, '지게차 속도위반 3건, 적재불량 2건', '경고조치 및 재교육', '높음', '진행중', NULL, '집중관리 필요'),
            ('SW-2024-003', '2024-02-01', '정기점검', '제2공장 B동', 'EMP100', '박안전', 'DEPT100', '안전관리팀', 1, '소화기 위치 부적절', '위치 재조정', '낮음', '완료', '2024-02-02', '개선됨'),
            ('SW-2024-004', '2024-02-15', '수시점검', '연구소', 'EMP101', '이안전', 'DEPT101', '안전관리1파트', 2, '화학물질 라벨링 누락', 'MSDS 부착 및 교육', '중', '진행중', NULL, '화학물질 관리 강화 필요'),
            ('SW-2024-005', '2024-03-01', '정기점검', '제3공장 C동', 'EMP100', '박안전', 'DEPT100', '안전관리팀', 0, '지적사항 없음', '없음', '낮음', '완료', '2024-03-01', '우수사업장'),
            ('SW-2024-006', '2024-03-10', '특별점검', '전 사업장', 'dev_super', '개발슈퍼관리자', 'DEPT000', '전산팀', 4, '시스템 보안 취약점 발견', '보안 패치 적용', '높음', '계획', NULL, '긴급 조치 필요')
        """)
        print("  [SUCCESS] safe_workplace table created with 6 records")

        # 권한 부여
        cursor.execute("GRANT ALL PRIVILEGES ON SCHEMA iqadb TO postgres")
        cursor.execute("GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA iqadb TO postgres")
        cursor.execute("GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA iqadb TO postgres")
        print("\n[INFO] Permissions granted")

        # 데이터 검증
        print("\n[RESULT] Data insertion summary:")
        tables = [
            ('partners', 'iqadb.partners'),
            ('accidents', 'iqadb.accidents'),
            ('buildings', 'iqadb.buildings'),
            ('departments', 'iqadb.departments'),
            ('contractors', 'iqadb.contractors'),
            ('employees', 'iqadb.employees'),
            ('divisions', 'iqadb.divisions'),
            ('safety_instructions', 'iqadb.safety_instructions'),
            ('followsop_external', 'iqadb."외부_followsop_테이블"'),
            ('fullprocess_external', 'iqadb."외부_fullprocess_테이블"'),
            ('partner_change_requests_external', 'iqadb."외부_partner_change_requests_테이블"'),
            ('safe_workplace', 'iqadb.safe_workplace')
        ]

        for display_name, table_name in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"  - {display_name}: {count} records")

        # 커밋
        conn.commit()
        print("\n[SUCCESS] All operations completed successfully!")

    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] Operation failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    create_and_populate_iqadb()