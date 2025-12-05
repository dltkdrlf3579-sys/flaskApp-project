#!/usr/bin/env python3
"""
PostgreSQL partners_cache 테이블에 더미데이터 삽입 스크립트
기존 구조를 해치지 않고 안전하게 더미데이터만 추가
"""

from db_connection import get_db_connection
import random

def insert_dummy_partners():
    """partners_cache 테이블에 더미데이터 삽입"""
    
    # PostgreSQL 연결 (config.ini 설정 사용)
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 테이블 존재 확인
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'partners_cache'
            )
        """)
        if not cursor.fetchone()[0]:
            print("partners_cache 테이블이 없습니다. 생성합니다...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS partners_cache (
                    business_number TEXT PRIMARY KEY,
                    company_name TEXT NOT NULL,
                    partner_class TEXT,
                    business_type_major TEXT,
                    business_type_minor TEXT,
                    hazard_work_flag TEXT,
                    representative TEXT,
                    address TEXT,
                    permanent_workers INTEGER,
                    average_age INTEGER,
                    annual_revenue BIGINT,
                    transaction_count INTEGER,
                    is_deleted INTEGER DEFAULT 0,
                    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            print("테이블 생성 완료!")
        
        # 기존 데이터 확인
        cursor.execute("SELECT COUNT(*) FROM partners_cache")
        existing_count = cursor.fetchone()[0]
        print(f"기존 데이터: {existing_count}개")
        
        if existing_count > 0:
            response = input("이미 데이터가 있습니다. 삭제하고 새로 넣을까요? (y/n): ")
            if response.lower() == 'y':
                cursor.execute("DELETE FROM partners_cache")
                conn.commit()
                print("기존 데이터 삭제 완료")
            else:
                print("작업 취소")
                return
        
        # 더미데이터 생성
        companies = [
            ('1008193810', '삼성전자(주)', 'A', '제조업', '전자제품', 'Y', '이재용', '서울시 서초구', 150, 35, 500000000000, 85),
            ('1018121395', 'LG전자(주)', 'A', '제조업', '전자제품', 'Y', '조주완', '서울시 영등포구', 120, 33, 300000000000, 72),
            ('1028136062', '현대자동차(주)', 'A', '제조업', '자동차', 'Y', '정의선', '서울시 서초구', 200, 38, 400000000000, 93),
            ('1038130379', 'SK하이닉스(주)', 'A', '제조업', '반도체', 'Y', '곽노정', '경기도 이천시', 100, 32, 250000000000, 67),
            ('1048115695', 'POSCO홀딩스(주)', 'B', '제조업', '철강', 'Y', '장인화', '경북 포항시', 80, 40, 200000000000, 54),
            ('2018146987', '네이버(주)', 'A', '서비스업', 'IT플랫폼', 'N', '최수연', '경기도 성남시', 50, 30, 100000000000, 41),
            ('2028154321', '카카오(주)', 'A', '서비스업', 'IT플랫폼', 'N', '홍은택', '제주도 제주시', 45, 29, 80000000000, 38),
            ('3018167890', '쿠팡(주)', 'B', '유통업', '이커머스', 'N', '강한승', '서울시 송파구', 60, 31, 120000000000, 62),
            ('3028175432', '배달의민족', 'B', '서비스업', '배달플랫폼', 'N', '김봉진', '서울시 송파구', 30, 28, 50000000000, 29),
            ('4018189876', '토스', 'C', '금융업', '핀테크', 'N', '이승건', '서울시 강남구', 25, 27, 30000000000, 18),
            ('4028197654', '당근마켓', 'C', '서비스업', '중고거래', 'N', '김재현', '서울시 서초구', 15, 26, 10000000000, 12),
            ('5018201234', '마켓컬리', 'C', '유통업', '신선식품', 'N', '김슬아', '서울시 강남구', 20, 30, 15000000000, 24),
            ('5028215678', '무신사', 'B', '유통업', '패션', 'N', '조만호', '서울시 성동구', 18, 28, 20000000000, 31),
            ('6018229012', '야놀자', 'B', '서비스업', '숙박예약', 'N', '이수진', '서울시 강남구', 22, 29, 25000000000, 27),
            ('6028237890', '직방', 'C', '서비스업', '부동산', 'N', '안성우', '서울시 서초구', 12, 31, 8000000000, 9),
            ('7018245678', 'GS건설', 'A', '건설업', '종합건설', 'Y', '허명수', '서울시 종로구', 70, 36, 150000000000, 45),
            ('7028253456', '대우건설', 'A', '건설업', '종합건설', 'Y', '백정완', '서울시 중구', 65, 37, 140000000000, 42),
            ('8018261234', '한화건설', 'B', '건설업', '토목건축', 'Y', '최광호', '서울시 중구', 55, 35, 100000000000, 33),
            ('8028269012', 'DL이앤씨', 'B', '건설업', '플랜트', 'Y', '마창민', '서울시 종로구', 48, 34, 90000000000, 28),
            ('9018276789', '롯데건설', 'B', '건설업', '주택건설', 'Y', '하석주', '서울시 서초구', 52, 35, 95000000000, 36),
        ]
        
        print("\n더미데이터 삽입 시작...")
        for i, data in enumerate(companies, 1):
            cursor.execute("""
                INSERT INTO partners_cache (
                    business_number, company_name, partner_class,
                    business_type_major, business_type_minor, hazard_work_flag,
                    representative, address, permanent_workers,
                    average_age, annual_revenue, transaction_count,
                    is_deleted, synced_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, CURRENT_TIMESTAMP)
            """, data)
            print(f"  [{i:2d}] {data[1]} 추가됨")
        
        conn.commit()
        print(f"\n✅ 총 {len(companies)}개 더미데이터가 추가되었습니다!")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    print("=== PostgreSQL partners_cache 더미데이터 삽입 ===")
    print("config.ini 설정: db_backend = postgres")
    insert_dummy_partners()
    print("\n완료! 브라우저에서 /partner-standards 페이지를 확인하세요.")