"""
기존 사고 데이터를 코드-값 매핑 방식으로 완전 마이그레이션
"""
import sqlite3
import json

def migrate_accident_data():
    """모든 사고 데이터의 드롭다운 값을 코드로 변환"""
    
    conn = sqlite3.connect('portal.db')
    cursor = conn.cursor()
    
    print("=" * 60)
    print("사고 데이터 마이그레이션 시작")
    print("=" * 60)
    
    # 1. 드롭다운 타입의 동적 컬럼 조회
    dropdown_columns = cursor.execute("""
        SELECT column_key, column_name, dropdown_options
        FROM accident_column_config
        WHERE column_type = 'dropdown'
    """).fetchall()
    
    print(f"\n드롭다운 컬럼 {len(dropdown_columns)}개 발견")
    
    # 2. 각 컬럼에 대한 값-코드 매핑 테이블 생성
    value_to_code_map = {}
    
    for col_key, col_name, dropdown_options in dropdown_columns:
        print(f"\n처리중: {col_name} ({col_key})")
        
        # 코드 매핑 조회
        codes = cursor.execute("""
            SELECT option_code, option_value
            FROM dropdown_option_codes
            WHERE column_key = ?
        """, (col_key,)).fetchall()
        
        if codes:
            # 값 -> 코드 매핑 생성
            value_to_code_map[col_key] = {value: code for code, value in codes}
            print(f"  - 코드 매핑 {len(codes)}개 로드됨")
        else:
            # 코드 매핑이 없으면 기존 JSON에서 생성
            if dropdown_options:
                try:
                    options = json.loads(dropdown_options)
                    if isinstance(options, list):
                        print(f"  - 기존 옵션에서 코드 생성 중...")
                        for idx, value in enumerate(options, 1):
                            code = f"{col_key.upper()}_{str(idx).zfill(3)}"
                            
                            # dropdown_option_codes에 삽입
                            cursor.execute("""
                                INSERT OR IGNORE INTO dropdown_option_codes
                                (column_key, option_code, option_value, display_order, is_active)
                                VALUES (?, ?, ?, ?, 1)
                            """, (col_key, code, value, idx))
                            
                            if col_key not in value_to_code_map:
                                value_to_code_map[col_key] = {}
                            value_to_code_map[col_key][value] = code
                        
                        print(f"    새로 생성된 코드: {len(options)}개")
                except Exception as e:
                    print(f"    오류: {e}")
    
    # 3. 모든 사고 데이터 조회
    accidents = cursor.execute("""
        SELECT accident_number, custom_data
        FROM accidents_cache
        WHERE custom_data IS NOT NULL AND custom_data != ''
    """).fetchall()
    
    print(f"\n마이그레이션 대상 사고: {len(accidents)}개")
    
    # 4. 각 사고 데이터 변환
    migrated_count = 0
    error_count = 0
    
    for accident_number, custom_data_str in accidents:
        try:
            custom_data = json.loads(custom_data_str)
            changed = False
            
            # 각 드롭다운 컬럼 확인
            for col_key in value_to_code_map:
                if col_key in custom_data:
                    current_value = custom_data[col_key]
                    
                    # 이미 코드 형식인지 확인 (COLUMN_XXX 패턴)
                    if current_value and not (
                        isinstance(current_value, str) and 
                        current_value.startswith(col_key.upper() + '_')
                    ):
                        # 값을 코드로 변환
                        if current_value in value_to_code_map[col_key]:
                            new_code = value_to_code_map[col_key][current_value]
                            custom_data[col_key] = new_code
                            changed = True
                            print(f"  {accident_number}: {col_key} = '{current_value}' → '{new_code}'")
            
            # 변경사항이 있으면 DB 업데이트
            if changed:
                cursor.execute("""
                    UPDATE accidents_cache
                    SET custom_data = ?
                    WHERE accident_number = ?
                """, (json.dumps(custom_data, ensure_ascii=False), accident_number))
                migrated_count += 1
                
        except Exception as e:
            print(f"  오류 - {accident_number}: {e}")
            error_count += 1
    
    # 5. 커밋
    conn.commit()
    
    print("\n" + "=" * 60)
    print("마이그레이션 완료!")
    print(f"  - 성공: {migrated_count}건")
    print(f"  - 오류: {error_count}건")
    print(f"  - 건너뜀: {len(accidents) - migrated_count - error_count}건")
    print("=" * 60)
    
    # 6. 검증
    print("\n검증 중...")
    
    # 변환된 데이터 샘플 확인
    sample = cursor.execute("""
        SELECT accident_number, custom_data
        FROM accidents_cache
        WHERE custom_data IS NOT NULL
        LIMIT 3
    """).fetchall()
    
    for accident_number, custom_data_str in sample:
        print(f"\n샘플 - {accident_number}:")
        custom_data = json.loads(custom_data_str)
        for col_key in value_to_code_map:
            if col_key in custom_data:
                code = custom_data[col_key]
                if code:
                    # 코드를 값으로 역변환 테스트
                    value_result = cursor.execute("""
                        SELECT option_value
                        FROM dropdown_option_codes
                        WHERE column_key = ? AND option_code = ?
                    """, (col_key, code)).fetchone()
                    
                    if value_result:
                        print(f"  {col_key}: {code} → {value_result[0]}")
    
    conn.close()
    print("\n마이그레이션 스크립트 종료")

if __name__ == "__main__":
    # 자동 실행 (input 제거)
    print("기존 사고 데이터를 코드 방식으로 마이그레이션합니다.")
    migrate_accident_data()