import sqlite3
import os

# DB 경로 설정
DB_PATH = os.path.join(os.path.dirname(__file__), 'portal.db')

def init_person_master():
    """person_master 테이블 생성 및 샘플 데이터 추가"""
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # person_master 테이블 생성
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS person_master (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id VARCHAR(20) NOT NULL UNIQUE,
                name VARCHAR(100) NOT NULL,
                department VARCHAR(100),
                company_name VARCHAR(100),
                position VARCHAR(50),
                phone VARCHAR(20),
                email VARCHAR(100),
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 기존 데이터 확인
        existing = cursor.execute("SELECT COUNT(*) FROM person_master").fetchone()[0]
        
        if existing == 0:
            # 샘플 담당자 데이터 추가
            sample_persons = [
                ('E001', '김철수', '안전관리팀', '삼성전자', '팀장', '010-1234-5678', 'kim.cs@samsung.com'),
                ('E002', '이영희', '안전관리팀', '삼성전자', '과장', '010-2345-6789', 'lee.yh@samsung.com'),
                ('E003', '박민수', '시설관리팀', '삼성전자', '대리', '010-3456-7890', 'park.ms@samsung.com'),
                ('E004', '정수진', '품질관리팀', '삼성전자', '사원', '010-4567-8901', 'jung.sj@samsung.com'),
                ('E005', '최동욱', '생산관리팀', '삼성전자', '부장', '010-5678-9012', 'choi.dw@samsung.com'),
                ('E006', '강미나', '환경안전팀', '삼성전자', '차장', '010-6789-0123', 'kang.mn@samsung.com'),
                ('E007', '조성우', '시공관리팀', '협력사A', '팀장', '010-7890-1234', 'jo.sw@partnera.com'),
                ('E008', '윤서연', '품질보증팀', '협력사B', '과장', '010-8901-2345', 'yoon.sy@partnerb.com'),
                ('E009', '임재현', '안전관리팀', '협력사C', '대리', '010-9012-3456', 'lim.jh@partnerc.com'),
                ('E010', '한지민', '시설운영팀', '삼성전자', '사원', '010-0123-4567', 'han.jm@samsung.com'),
                ('E011', '김태준', '건설안전팀', '협력사D', '팀장', '010-1111-2222', 'kim.tj@partnerd.com'),
                ('E012', '이수빈', '품질관리팀', '협력사E', '과장', '010-3333-4444', 'lee.sb@partnere.com'),
                ('E013', '박지훈', '안전보건팀', '삼성전자', '부장', '010-5555-6666', 'park.jh@samsung.com'),
                ('E014', '최예진', '환경관리팀', '삼성전자', '차장', '010-7777-8888', 'choi.yj@samsung.com'),
                ('E015', '정현우', '시공안전팀', '협력사F', '대리', '010-9999-0000', 'jung.hw@partnerf.com')
            ]
            
            cursor.executemany("""
                INSERT INTO person_master 
                (employee_id, name, department, company_name, position, phone, email)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, sample_persons)
            
            print(f"[SUCCESS] person_master table created and {len(sample_persons)} sample data added")
        else:
            print(f"[INFO] person_master table already has {existing} records")
        
        conn.commit()
        
    except Exception as e:
        print(f"[ERROR] Error occurred: {e}")
        conn.rollback()
        
    finally:
        conn.close()

if __name__ == "__main__":
    init_person_master()