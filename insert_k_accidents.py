"""
K사고 샘플 데이터를 직접 DB에 삽입하는 스크립트
IQADB에서 온 것처럼 가짜 K사고 데이터를 생성합니다.
"""

import json
from datetime import datetime, timedelta
from db_connection import get_db_connection

def insert_k_accidents():
    """K사고 샘플 데이터 삽입"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # K사고 샘플 데이터 (IQADB에서 오는 것처럼)
    k_accidents = [
        {
            'accident_number': 'K20250110001',
            'accident_name': '협력사 추락사고',
            'accident_date': '2025-01-10',
            'report_date': '2025-01-10',  # K사고는 report_date 사용
            'workplace': '울산공장',
            'accident_grade': '중대',
            'major_category': '제조업',
            'injury_form': '추락',
            'injury_type': '골절',
            'building': 'A동',
            'floor': '3층',
            'location_category': '생산현장',
            'location_detail': '조립라인 B구역',
            'accident_content': 'IQADB 연계 사고 - 작업 중 3층 발판에서 추락하여 다리 골절',
            'company_name': '안전건설(주)',
            'company_bizno': '123-45-67890',
            'injured_person': '김작업',
            'injured_dept': '생산1팀'
        },
        {
            'accident_number': 'K20250108002',
            'accident_name': '협력사 협착사고',
            'accident_date': '2025-01-08',
            'report_date': '2025-01-08',
            'workplace': '여수공장',
            'accident_grade': '경미',
            'major_category': '건설업',
            'injury_form': '협착',
            'injury_type': '타박상',
            'building': 'B동',
            'floor': '1층',
            'location_category': '창고',
            'location_detail': '자재창고 입구',
            'accident_content': 'IQADB 연계 사고 - 지게차 작업 중 손가락 협착',
            'company_name': '대한물류(주)',
            'company_bizno': '234-56-78901',
            'injured_person': '이안전',
            'injured_dept': '물류팀'
        },
        {
            'accident_number': 'K20250105003',
            'accident_name': '협력사 화재사고',
            'accident_date': '2025-01-05',
            'report_date': '2025-01-05',
            'workplace': '구미공장',
            'accident_grade': '치명',
            'major_category': '제조업',
            'injury_form': '화재',
            'injury_type': '화상',
            'building': 'C동',
            'floor': '2층',
            'location_category': '사무실',
            'location_detail': '전기실',
            'accident_content': 'IQADB 연계 사고 - 전기 합선으로 인한 화재 발생',
            'company_name': '전기공사(주)',
            'company_bizno': '345-67-89012',
            'injured_person': '박전기',
            'injured_dept': '시설팀'
        },
        {
            'accident_number': 'K20250103004',
            'accident_name': '협력사 충돌사고',
            'accident_date': '2025-01-03',
            'report_date': '2025-01-03',
            'workplace': '포항공장',
            'accident_grade': '중대',
            'major_category': '운수업',
            'injury_form': '충돌',
            'injury_type': '찰과상',
            'building': '야외',
            'floor': '지상',
            'location_category': '야외',
            'location_detail': '적재장',
            'accident_content': 'IQADB 연계 사고 - 지게차와 작업자 충돌',
            'company_name': '운송대행(주)',
            'company_bizno': '456-78-90123',
            'injured_person': '최운전',
            'injured_dept': '운송팀'
        }
    ]
    
    print("K사고 샘플 데이터 삽입 시작...")
    
    for accident in k_accidents:
        try:
            # custom_data로 모든 정보 저장
            custom_data = json.dumps(accident, ensure_ascii=False)
            
            # accidents_cache 테이블에 삽입
            cursor.execute("""
                INSERT INTO accidents_cache (
                    accident_number, 
                    accident_name,
                    accident_date,
                    report_date,
                    workplace,
                    accident_grade,
                    custom_data,
                    created_at,
                    is_deleted
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0)
                ON CONFLICT (accident_number) DO UPDATE SET
                    accident_name = EXCLUDED.accident_name,
                    accident_date = EXCLUDED.accident_date,
                    report_date = EXCLUDED.report_date,
                    workplace = EXCLUDED.workplace,
                    accident_grade = EXCLUDED.accident_grade,
                    custom_data = EXCLUDED.custom_data,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                accident['accident_number'],
                accident['accident_name'],
                accident['accident_date'],
                accident['report_date'],
                accident['workplace'],
                accident['accident_grade'],
                custom_data,
                datetime.now().isoformat()
            ))
            
            print(f"[OK] {accident['accident_number']}: {accident['accident_name']} 삽입 완료")
            
        except Exception as e:
            print(f"[ERROR] {accident['accident_number']} 삽입 실패: {e}")
            # 테이블에 report_date 컬럼이 없을 수도 있으므로 다시 시도
            try:
                cursor.execute("""
                    INSERT INTO accidents_cache (
                        accident_number, 
                        accident_name,
                        accident_date,
                        workplace,
                        accident_grade,
                        custom_data,
                        created_at,
                        is_deleted
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, 0)
                    ON CONFLICT (accident_number) DO UPDATE SET
                        accident_name = EXCLUDED.accident_name,
                        accident_date = EXCLUDED.accident_date,
                        workplace = EXCLUDED.workplace,
                        accident_grade = EXCLUDED.accident_grade,
                        custom_data = EXCLUDED.custom_data,
                        updated_at = CURRENT_TIMESTAMP
                """, (
                    accident['accident_number'],
                    accident['accident_name'],
                    accident['accident_date'],
                    accident['workplace'],
                    accident['accident_grade'],
                    custom_data,
                    datetime.now().isoformat()
                ))
                print(f"[OK] {accident['accident_number']}: {accident['accident_name']} 삽입 완료 (report_date 없이)")
            except Exception as e2:
                print(f"[FINAL ERROR] 최종 실패: {e2}")
    
    conn.commit()
    
    # 확인
    cursor.execute("SELECT COUNT(*) FROM accidents_cache WHERE accident_number LIKE %s", ('K%',))
    k_count = cursor.fetchone()[0]
    print(f"\n총 {k_count}개의 K사고가 DB에 있습니다.")
    
    # 샘플 조회
    cursor.execute("""
        SELECT accident_number, accident_name, accident_date, report_date 
        FROM accidents_cache 
        WHERE accident_number LIKE %s
        ORDER BY accident_number DESC 
        LIMIT 5
    """, ('K%',))
    
    print("\n최근 K사고 목록:")
    for row in cursor.fetchall():
        print(f"  - {row[0]}: {row[1]} (사고일: {row[2]}, 보고일: {row[3]})")
    
    conn.close()
    print("\n[COMPLETE] K사고 샘플 데이터 삽입 완료!")

if __name__ == "__main__":
    insert_k_accidents()