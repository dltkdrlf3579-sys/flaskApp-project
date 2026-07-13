#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
각 admin 페이지의 섹션 삭제 기능 상세 비교 분석
"""
import sys
import io
import os
import re

# UTF-8 encoding 설정
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from database_config import get_db_connection

def analyze_table_structures():
    """각 테이블의 구조 분석"""
    conn = get_db_connection()
    cursor = conn.cursor()

    print("=" * 80)
    print("📊 테이블 구조 분석")
    print("=" * 80)

    tables = [
        'follow_sop_sections',
        'full_process_sections',
        'accident_sections',
        'safety_instruction_sections'
    ]

    for table in tables:
        print(f"\n### {table} ###")

        # 테이블 존재 확인
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
        """, (table,))

        columns = cursor.fetchall()

        if columns:
            has_id = False
            primary_key = None

            for col_name, data_type, nullable in columns:
                if col_name == 'id':
                    has_id = True
                print(f"  - {col_name}: {data_type} {'(NULL 가능)' if nullable == 'YES' else ''}")

            # Primary Key 확인
            cursor.execute("""
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                WHERE tc.table_name = %s
                    AND tc.constraint_type = 'PRIMARY KEY'
            """, (table,))

            pk_columns = cursor.fetchall()
            if pk_columns:
                primary_key = ', '.join([pk[0] for pk in pk_columns])
                print(f"  🔑 PRIMARY KEY: {primary_key}")

            print(f"  ✅ ID 컬럼 존재: {'예' if has_id else '❌ 아니오'}")
        else:
            print("  ❌ 테이블이 존재하지 않습니다")

    cursor.close()
    conn.close()

def analyze_template_differences():
    """템플릿별 JavaScript 삭제 로직 비교"""
    print("\n" + "=" * 80)
    print("🔍 템플릿별 deleteSection 함수 차이점 분석")
    print("=" * 80)

    templates = {
        'follow-sop': 'templates/admin-follow-sop-columns.html',
        'full-process': 'templates/admin-full-process-columns.html',
        'accident': 'templates/admin-accident-columns.html',
        'safety-instruction': 'templates/admin-safety-instruction-columns.html'
    }

    for board_type, template_path in templates.items():
        print(f"\n### {board_type} ###")

        if not os.path.exists(template_path):
            print(f"  ❌ 파일 없음: {template_path}")
            continue

        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # deleteSection 함수 분석
        delete_func = re.search(r'function deleteSection\((.*?)\)', content)
        if delete_func:
            params = delete_func.group(1)
            print(f"  📝 파라미터: {params}")

        # sectionsToDelete 배열 사용 확인
        if 'sectionsToDelete.push' in content:
            print(f"  ✅ sectionsToDelete 배열 사용")

        # API 엔드포인트 확인
        api_pattern = r'fetch\(`/api/(.*?)/\$\{.*?\}`'
        api_matches = re.findall(api_pattern, content)
        if api_matches:
            print(f"  🌐 API 엔드포인트: /api/{api_matches[0]}/")

        # 삭제 시 ID vs section_key 사용 확인
        if 'sections.find(s => s.id === sectionId)' in content:
            print(f"  🔍 섹션 찾기: ID 기반 (s.id === sectionId)")

        # parseInt 사용 확인
        if 'parseInt(sectionId' in content:
            print(f"  🔢 ID 변환: parseInt 사용")

        # 기본 섹션 보호 로직
        protected = re.findall(r"section\.section_key === '(\w+)'", content)
        if protected:
            print(f"  🛡️ 보호된 섹션: {', '.join(set(protected))}")
        else:
            print(f"  ⚠️ 보호된 섹션 없음")

def analyze_api_routes():
    """app.py의 API 라우트 분석"""
    print("\n" + "=" * 80)
    print("🌐 API 라우트 분석")
    print("=" * 80)

    if not os.path.exists('app.py'):
        print("❌ app.py 파일을 찾을 수 없습니다")
        return

    with open('app.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # 각 보드별 섹션 삭제 API 찾기
    boards = ['follow-sop', 'full-process', 'accident', 'safety-instruction']

    for board in boards:
        print(f"\n### {board} ###")

        # DELETE 라우트 찾기
        pattern = rf"@app\.route\('/api/{board}-sections/<int:section_id>'.*?methods=\['DELETE'\].*?\)\s*def\s+(\w+)"
        match = re.search(pattern, content, re.DOTALL)

        if match:
            func_name = match.group(1)
            print(f"  ✅ DELETE 라우트 존재: {func_name}")

            # 함수 내용 분석
            func_pattern = rf"def {func_name}.*?(?=\n@app|\nif __name__|$)"
            func_match = re.search(func_pattern, content, re.DOTALL)

            if func_match:
                func_content = func_match.group()

                # SectionConfigService 사용 확인
                if 'SectionConfigService' in func_content:
                    print(f"  📦 SectionConfigService 사용")

                # delete_section 메서드 호출 확인
                if 'delete_section' in func_content:
                    print(f"  🗑️ delete_section 메서드 호출")

                # 테이블 직접 쿼리 확인
                if 'DELETE FROM' in func_content or 'UPDATE' in func_content:
                    print(f"  ⚠️ 직접 SQL 쿼리 사용")
        else:
            print(f"  ❌ DELETE 라우트 없음")

def test_actual_deletion():
    """실제 삭제 동작 테스트"""
    print("\n" + "=" * 80)
    print("🧪 실제 삭제 동작 테스트")
    print("=" * 80)

    conn = get_db_connection()
    cursor = conn.cursor()

    # 각 테이블의 현재 섹션 수 확인
    tables = [
        ('follow_sop_sections', 'follow_sop'),
        ('full_process_sections', 'full_process'),
        ('accident_sections', 'accident'),
        ('safety_instruction_sections', 'safety_instruction')
    ]

    for table, board_type in tables:
        print(f"\n### {table} ###")

        # 현재 섹션 수
        cursor.execute(f"""
            SELECT COUNT(*)
            FROM {table}
            WHERE is_deleted = 0 OR is_deleted IS NULL
        """)
        count = cursor.fetchone()[0]
        print(f"  현재 활성 섹션 수: {count}")

        # ID 컬럼 존재 여부
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = %s AND column_name = 'id'
        """, (table,))

        has_id = cursor.fetchone() is not None

        if has_id:
            print(f"  ✅ ID 컬럼 존재 - 정상적인 삭제 가능")
        else:
            print(f"  ❌ ID 컬럼 없음 - 삭제 시 문제 발생 가능!")

            # section_key를 ID로 사용하는지 확인
            cursor.execute(f"""
                SELECT section_key
                FROM {table}
                LIMIT 5
            """)

            keys = cursor.fetchall()
            print(f"  📝 샘플 section_key: {[k[0] for k in keys[:3]]}")

    cursor.close()
    conn.close()

def suggest_fixes():
    """수정 방안 제안"""
    print("\n" + "=" * 80)
    print("💡 문제 해결 방안")
    print("=" * 80)

    print("""
1. **즉각적인 수정 (Quick Fix)**
   - follow_sop_sections와 full_process_sections에 ID 컬럼 추가
   - 또는 JavaScript에서 section_key 기반 삭제로 변경

2. **장기적인 개선**
   - 모든 섹션 테이블 구조 통일
   - 템플릿 코드 통합 및 재사용
   - API 라우트 표준화

3. **테스트 필요 항목**
   - 각 보드별 섹션 삭제 기능
   - 다중 섹션 삭제
   - 삭제 롤백 기능
""")

if __name__ == "__main__":
    analyze_table_structures()
    analyze_template_differences()
    analyze_api_routes()
    test_actual_deletion()
    suggest_fixes()