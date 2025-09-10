#!/usr/bin/env python3
"""
모든 게시판의 컬럼 표시 문제 전체 검증
"""
import psycopg
import configparser
import re
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')

def get_pg_connection():
    """PostgreSQL 연결"""
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')
    
    postgres_dsn = config.get('DATABASE', 'postgres_dsn')
    match = re.match(r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', postgres_dsn)
    if not match:
        logging.error(f"잘못된 PostgreSQL DSN: {postgres_dsn}")
        return None
    
    user, password, host, port, database = match.groups()
    
    try:
        conn = psycopg.connect(
            host=host,
            port=int(port),
            dbname=database,
            user=user,
            password=password
        )
        conn.autocommit = True
        return conn
    except Exception as e:
        logging.error(f"PostgreSQL 연결 실패: {e}")
        return None

def check_board_columns(conn, board_name, section_table, column_table):
    """게시판별 컬럼 상태 확인"""
    cursor = conn.cursor()
    
    print(f"\n{'='*60}")
    print(f"[{board_name}]")
    print('='*60)
    
    # 1. 섹션 테이블 확인
    try:
        cursor.execute(f"""
            SELECT section_key, section_name, is_active 
            FROM {section_table}
            ORDER BY section_order
        """)
        sections = cursor.fetchall()
        
        print(f"\n[섹션] ({len(sections)}개):")
        for key, name, active in sections:
            status = "[OK]" if active == 1 else "[X]"
            print(f"  {status} {key}: {name}")
    except Exception as e:
        print(f"[ERROR] 섹션 테이블 오류: {e}")
        sections = []
    
    # 2. 컬럼 설정 확인
    try:
        # 전체 컬럼
        cursor.execute(f"""
            SELECT COUNT(*) FROM {column_table}
            WHERE is_active = 1
        """)
        total_cols = cursor.fetchone()[0]
        
        # NULL tab 컬럼
        cursor.execute(f"""
            SELECT COUNT(*) FROM {column_table}
            WHERE is_active = 1 AND (tab IS NULL OR tab = '')
        """)
        null_tabs = cursor.fetchone()[0]
        
        # 섹션별 컬럼 분포
        cursor.execute(f"""
            SELECT tab, COUNT(*) as cnt
            FROM {column_table}
            WHERE is_active = 1
            GROUP BY tab
            ORDER BY tab
        """)
        tab_dist = cursor.fetchall()
        
        print(f"\n[컬럼 상태]:")
        print(f"  - 전체 활성 컬럼: {total_cols}개")
        print(f"  - NULL tab 컬럼: {null_tabs}개")
        print(f"  - 섹션별 분포:")
        for tab, cnt in tab_dist:
            tab_name = tab if tab else "NULL"
            print(f"    - {tab_name}: {cnt}개")
        
        # NULL tab 컬럼 상세
        if null_tabs > 0:
            cursor.execute(f"""
                SELECT column_key, column_name
                FROM {column_table}
                WHERE is_active = 1 AND (tab IS NULL OR tab = '')
                LIMIT 5
            """)
            null_cols = cursor.fetchall()
            print(f"\n[WARNING] NULL tab 컬럼 예시:")
            for key, name in null_cols:
                print(f"    - {key}: {name}")
                
    except Exception as e:
        print(f"[ERROR] 컬럼 설정 오류: {e}")
    
    # 3. 리스트 페이지 표시 컬럼 확인
    try:
        cursor.execute(f"""
            SELECT column_key, column_name, tab, column_type
            FROM {column_table}
            WHERE is_active = 1 
              AND is_list_display = 1
              AND tab IS NOT NULL
            ORDER BY column_order
            LIMIT 10
        """)
        list_cols = cursor.fetchall()
        
        print(f"\n[리스트 페이지 표시 컬럼] ({len(list_cols)}개):")
        for key, name, tab, col_type in list_cols:
            print(f"    - {key} ({name}) [{tab}] - {col_type}")
            
    except Exception as e:
        print(f"[ERROR] 리스트 표시 컬럼 오류: {e}")
    
    return total_cols, null_tabs

def main():
    """메인 실행"""
    conn = get_pg_connection()
    if not conn:
        return
    
    print("=" * 70)
    print("모든 게시판 컬럼 표시 문제 전체 검증")
    print("=" * 70)
    
    boards = [
        ("환경안전 지시서", "safety_instruction_sections", "safety_instruction_column_config"),
        ("Follow SOP", "follow_sop_sections", "follow_sop_column_config"),
        ("Full Process", "full_process_sections", "full_process_column_config"),
        ("협력사 사고", "accident_sections", "accident_column_config"),
        ("기준정보 변경요청", "change_request_sections", "change_request_column_config")
    ]
    
    summary = []
    for board_name, section_table, column_table in boards:
        try:
            total, nulls = check_board_columns(conn, board_name, section_table, column_table)
            summary.append((board_name, total, nulls))
        except Exception as e:
            print(f"\n[ERROR] {board_name} 검증 실패: {e}")
            summary.append((board_name, 0, 0))
    
    # 요약
    print("\n" + "="*70)
    print("[전체 요약]")
    print("="*70)
    
    for board, total, nulls in summary:
        status = "[OK]" if nulls == 0 and total > 0 else "[WARN]"
        print(f"{status} {board}: {total}개 컬럼 (NULL: {nulls}개)")
    
    # 문제 진단
    print("\n" + "="*70)
    print("[문제 진단 및 해결방안]")
    print("="*70)
    
    problems = []
    for board, total, nulls in summary:
        if nulls > 0:
            problems.append(f"- {board}: NULL tab 컬럼 {nulls}개 → tab 매핑 필요")
        if total < 10:
            problems.append(f"- {board}: 컬럼이 너무 적음 ({total}개) → 데이터 확인 필요")
    
    if problems:
        print("발견된 문제:")
        for p in problems:
            print(p)
    else:
        print("[OK] 모든 게시판이 정상입니다!")
    
    conn.close()

if __name__ == "__main__":
    main()