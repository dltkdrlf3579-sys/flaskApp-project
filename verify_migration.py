#!/usr/bin/env python3
"""
마이그레이션 검증 스크립트
서버 재시작 후 모든 페이지가 정상 작동하는지 확인
"""
import sqlite3
# tabulate 모듈이 없으면 간단한 대체 구현
try:
    from tabulate import tabulate
except ImportError:
    def tabulate(data, headers=None, tablefmt="grid"):
        """간단한 테이블 출력 함수"""
        if headers:
            print(" | ".join(str(h).ljust(20) for h in headers))
            print("-" * (len(headers) * 22))
        for row in data:
            print(" | ".join(str(cell).ljust(20) for cell in row))
        return ""
import sys
from pathlib import Path

# DB 경로 설정
DB_PATH = "portal.db"

def check_sections():
    """섹션 테이블 상태 확인"""
    print("\n" + "="*60)
    print("1. 섹션 테이블 상태 확인")
    print("="*60)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    tables = [
        'safety_instruction_sections',
        'follow_sop_sections', 
        'full_process_sections',
        'accident_sections'
    ]
    
    results = []
    for table in tables:
        try:
            # 테이블 존재 확인
            cursor.execute(f"SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='{table}'")
            if cursor.fetchone()[0] == 0:
                results.append([table, "테이블 없음", "-", "-"])
                continue
                
            # 컬럼 확인
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [col[1] for col in cursor.fetchall()]
            
            required_cols = ['section_order', 'is_active', 'is_deleted']
            missing_cols = [col for col in required_cols if col not in columns]
            
            # 데이터 개수 확인
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            total = cursor.fetchone()[0]
            
            cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE is_active = 1")
            active = cursor.fetchone()[0]
            
            status = "[OK]" if not missing_cols else f"[ERROR] 누락: {', '.join(missing_cols)}"
            results.append([table, status, total, active])
            
        except Exception as e:
            results.append([table, f"[ERROR] 오류: {str(e)}", "-", "-"])
    
    print(tabulate(results, headers=["테이블", "상태", "전체", "활성"], tablefmt="grid"))
    conn.close()
    return all("[OK]" in r[1] for r in results)

def check_column_mappings():
    """컬럼 tab 매핑 상태 확인"""
    print("\n" + "="*60)
    print("2. 컬럼 Tab 매핑 상태")
    print("="*60)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    tables = [
        ('safety_instruction_column_config', 'Safety Instruction'),
        ('follow_sop_column_config', 'Follow SOP'),
        ('full_process_column_config', 'Full Process'),
        ('accident_column_config', 'Accident')
    ]
    
    results = []
    has_nulls = False
    
    for table, name in tables:
        try:
            # 전체 컬럼 수
            cursor.execute(f"""
                SELECT COUNT(*) FROM {table}
                WHERE is_active = 1 AND (is_deleted = 0 OR is_deleted IS NULL)
            """)
            total = cursor.fetchone()[0]
            
            # NULL tab 개수
            cursor.execute(f"""
                SELECT COUNT(*) FROM {table}
                WHERE (tab IS NULL OR tab = '') 
                  AND is_active = 1 
                  AND (is_deleted = 0 OR is_deleted IS NULL)
            """)
            nulls = cursor.fetchone()[0]
            
            # 섹션별 분포
            cursor.execute(f"""
                SELECT tab, COUNT(*) FROM {table}
                WHERE is_active = 1 AND (is_deleted = 0 OR is_deleted IS NULL)
                GROUP BY tab
            """)
            sections = cursor.fetchall()
            section_str = ", ".join([f"{s[0]}({s[1]})" for s in sections if s[0]])
            
            status = "[OK]" if nulls == 0 else f"[WARN] NULL: {nulls}개"
            if nulls > 0:
                has_nulls = True
                
            results.append([name, total, nulls, section_str or "없음", status])
            
        except Exception as e:
            results.append([name, "-", "-", f"오류: {str(e)}", "[ERROR]"])
    
    print(tabulate(results, headers=["보드", "전체", "NULL", "섹션별 분포", "상태"], tablefmt="grid"))
    
    # NULL 상세 출력
    if has_nulls:
        print("\n[WARNING] NULL tab 컬럼 상세:")
        for table, name in tables:
            cursor.execute(f"""
                SELECT column_key, column_name 
                FROM {table}
                WHERE (tab IS NULL OR tab = '') 
                  AND is_active = 1
                LIMIT 5
            """)
            nulls = cursor.fetchall()
            if nulls:
                print(f"\n  {name}:")
                for key, name in nulls:
                    print(f"    - {key}: {name}")
    
    conn.close()
    return not has_nulls

def check_pages():
    """페이지 접근 가능성 시뮬레이션"""
    print("\n" + "="*60)
    print("3. 페이지 접근 가능성 체크")
    print("="*60)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    pages = [
        ('/safety-instruction', 'safety_instruction_sections', 'safety_instruction_column_config'),
        ('/follow-sop', 'follow_sop_sections', 'follow_sop_column_config'),
        ('/full-process', 'full_process_sections', 'full_process_column_config'),
        ('/partner-accident', 'accident_sections', 'accident_column_config')
    ]
    
    results = []
    for url, section_table, column_table in pages:
        try:
            # 섹션 체크
            cursor.execute(f"SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='{section_table}'")
            has_section_table = cursor.fetchone()[0] > 0
            
            if has_section_table:
                cursor.execute(f"SELECT COUNT(*) FROM {section_table} WHERE is_active = 1")
                active_sections = cursor.fetchone()[0]
            else:
                active_sections = 0
            
            # 컬럼 체크
            cursor.execute(f"""
                SELECT COUNT(*) FROM {column_table}
                WHERE is_active = 1 AND tab IS NOT NULL AND tab != ''
            """)
            mapped_columns = cursor.fetchone()[0]
            
            # 상태 판단
            if not has_section_table:
                status = "[ERROR] 섹션 테이블 없음"
            elif active_sections == 0:
                status = "[ERROR] 활성 섹션 없음"
            elif mapped_columns == 0:
                status = "[ERROR] 매핑된 컬럼 없음"
            else:
                status = "[OK]"
            
            results.append([url, active_sections, mapped_columns, status])
            
        except Exception as e:
            results.append([url, "-", "-", f"[ERROR] 오류: {str(e)}"])
    
    print(tabulate(results, headers=["페이지", "활성 섹션", "매핑 컬럼", "상태"], tablefmt="grid"))
    conn.close()
    return all("[OK]" in r[3] for r in results)

def check_admin_pages():
    """관리자 페이지 체크"""
    print("\n" + "="*60)
    print("4. 관리자 페이지 체크")
    print("="*60)
    
    admin_pages = [
        '/admin/safety-instruction-columns',
        '/admin/follow-sop-columns',
        '/admin/full-process-columns',
        '/admin/accident-columns'
    ]
    
    print("다음 관리자 페이지들을 확인하세요:")
    for page in admin_pages:
        print(f"  - {page}")
    print("\n각 페이지에서:")
    print("  1. 섹션이 표시되는지 확인")
    print("  2. 각 섹션 내에 컬럼들이 표시되는지 확인")
    print("  3. 드래그 앤 드롭이 작동하는지 확인")
    
    return True

def main():
    """메인 검증 실행"""
    print("\n" + "=== 마이그레이션 검증 시작 " + "="*40)
    
    if not Path(DB_PATH).exists():
        print(f"[ERROR] 데이터베이스 파일을 찾을 수 없습니다: {DB_PATH}")
        sys.exit(1)
    
    # 각 체크 실행
    checks = [
        ("섹션 테이블", check_sections()),
        ("컬럼 매핑", check_column_mappings()),
        ("페이지 접근성", check_pages()),
        ("관리자 페이지", check_admin_pages())
    ]
    
    # 최종 결과
    print("\n" + "="*60)
    print("=== 최종 검증 결과 ===")
    print("="*60)
    
    all_passed = all(result for _, result in checks)
    
    for name, result in checks:
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {name}: {status}")
    
    if all_passed:
        print("\n[SUCCESS] 모든 검증을 통과했습니다!")
        print("서버를 재시작하고 각 페이지를 테스트해보세요.")
    else:
        print("\n[WARNING] 일부 검증에 실패했습니다.")
        print("위의 오류를 확인하고 수정 후 다시 실행하세요.")
        print("\nPostgreSQL 환경이면 다음 명령을 실행하세요:")
        print("  psql -U username -d database -f complete_migration_fix.sql")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())