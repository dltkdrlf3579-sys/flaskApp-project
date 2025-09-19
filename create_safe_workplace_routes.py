"""
Safe-workplace routes를 add_page_routes.py에 추가하는 스크립트
"""

# add_page_routes.py 파일 읽기
with open('add_page_routes.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 추가할 safe-workplace 라우트 코드
safe_workplace_routes = '''
# ============= Safe-Workplace 관련 라우트 =============
@app.route("/safe-workplace")
def safe_workplace_route():
    """Safe-Workplace 페이지 라우트"""
    from common_mapping import smart_apply_mappings
    import math
    import sqlite3
    from section_service import SectionConfigService

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 섹션 서비스 초기화
    section_service = SectionConfigService('safe_workplace', DB_PATH)

    # 기본 섹션 확인 및 생성
    cursor.execute("SELECT COUNT(*) FROM safe_workplace_sections WHERE section_key = 'basic_info'")
    if _first(cursor.fetchone(), 0) == 0:
        cursor.execute("""
            INSERT INTO safe_workplace_sections (section_key, section_name, section_order, is_active)
            VALUES ('basic_info', '기본정보', 1, 1)
        """)
        conn.commit()

    # 섹션 정보 가져오기
    sections = section_service.get_sections()

    # 동적 컬럼 정보 가져오기
    cursor.execute("""
        SELECT * FROM safe_workplace_column_config
        WHERE is_active = 1 AND (is_deleted = 0 OR is_deleted IS NULL)
        ORDER BY column_order
    """)
    columns = [dict(row) for row in cursor.fetchall()]

    # 페이징 처리
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    search_term = request.args.get('search', '')
    offset = (page - 1) * per_page

    # 데이터 조회 쿼리 - safe_workplace 테이블 구조에 맞게 수정
    base_query = """
        SELECT sw.*, p.company_name, b.building_name
        FROM safe_workplace sw
        LEFT JOIN partners p ON sw.business_number = p.business_number
        LEFT JOIN buildings b ON sw.building_code = b.building_code
        WHERE 1=1
    """

    count_query = """
        SELECT COUNT(*) FROM safe_workplace sw
        LEFT JOIN partners p ON sw.business_number = p.business_number
        WHERE 1=1
    """

    params = []
    if search_term:
        search_clause = " AND (sw.safe_workplace_number LIKE ? OR p.company_name LIKE ? OR sw.work_name LIKE ?)"
        base_query += search_clause
        count_query += search_clause
        params.extend([f'%{search_term}%'] * 3)

    # 전체 개수 조회
    cursor.execute(count_query, params)
    total_count = cursor.fetchone()[0]

    # 페이징된 데이터 조회
    data_query = base_query + " ORDER BY sw.created_at DESC LIMIT ? OFFSET ?"
    cursor.execute(data_query, params + [per_page, offset])
    items = []
    for row in cursor.fetchall():
        item = dict(row)
        item = smart_apply_mappings(item, 'safe_workplace')
        items.append(item)

    # 페이징 정보 계산
    total_pages = math.ceil(total_count / per_page)

    # 템플릿에서 필요한 변수들
    popup = request.args.get('popup', '')

    conn.close()

    return render_template('safe-workplace.html',
                         items=items,
                         sections=sections,
                         columns=columns,
                         page=page,
                         per_page=per_page,
                         total_pages=total_pages,
                         total_count=total_count,
                         search_term=search_term,
                         popup=popup)

@app.route("/safe-workplace-register", methods=['GET', 'POST'])
def safe_workplace_register():
    """Safe-Workplace 등록 페이지"""
    from common_mapping import smart_apply_mappings
    import sqlite3
    from section_service import SectionConfigService
    from id_generator import generate_safe_workplace_number
    from timezone_config import get_korean_time

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    section_service = SectionConfigService('safe_workplace', DB_PATH)
    sections = section_service.get_sections_with_columns()

    # 동적 컬럼 가져오기
    cursor.execute("""
        SELECT * FROM safe_workplace_column_config
        WHERE is_active = 1 AND (is_deleted = 0 OR is_deleted IS NULL)
        ORDER BY column_order
    """)
    columns = [dict(row) for row in cursor.fetchall()]

    if request.method == 'POST':
        try:
            # 한국 시간으로 생성 시각 설정
            created_at = get_korean_time()

            # 고유 번호 생성
            safe_workplace_number = generate_safe_workplace_number(DB_PATH, created_at)

            # 폼 데이터 수집
            form_data = {
                'safe_workplace_number': safe_workplace_number,
                'created_at': created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'work_name': request.form.get('work_name', ''),
                'work_date': request.form.get('work_date', ''),
                'business_number': request.form.get('business_number', ''),
                'building_code': request.form.get('building_code', ''),
                'worker_count': request.form.get('worker_count', 0),
                'safety_manager': request.form.get('safety_manager', ''),
                'work_type': request.form.get('work_type', ''),
                'risk_assessment': request.form.get('risk_assessment', ''),
                'safety_measures': request.form.get('safety_measures', '')
            }

            # 동적 컬럼 데이터 수집
            for column in columns:
                column_key = column.get('column_key')
                form_data[column_key] = request.form.get(column_key, '')

            # 데이터 삽입
            insert_columns = ', '.join(form_data.keys())
            placeholders = ', '.join(['?' for _ in form_data])
            insert_query = f"INSERT INTO safe_workplace ({insert_columns}) VALUES ({placeholders})"

            cursor.execute(insert_query, list(form_data.values()))
            conn.commit()

            flash(f'안전한 일터 점검 {safe_workplace_number}이(가) 등록되었습니다.', 'success')

            # 팝업 모드 확인
            if request.form.get('popup') == '1':
                conn.close()
                return redirect(url_for('safe_workplace_route', popup='close'))

            conn.close()
            return redirect(url_for('safe_workplace_route'))

        except Exception as e:
            conn.rollback()
            conn.close()
            flash(f'등록 중 오류 발생: {str(e)}', 'error')

    # GET 요청 처리
    # 파트너 목록 조회
    cursor.execute("SELECT business_number, company_name FROM partners ORDER BY company_name")
    partners = [dict(row) for row in cursor.fetchall()]

    # 건물 목록 조회
    cursor.execute("SELECT building_code, building_name FROM buildings ORDER BY building_name")
    buildings = [dict(row) for row in cursor.fetchall()]

    conn.close()

    popup = request.args.get('popup', '')

    return render_template('safe-workplace-register.html',
                         sections=sections,
                         columns=columns,
                         partners=partners,
                         buildings=buildings,
                         popup=popup)

@app.route("/safe-workplace/<safe_workplace_number>")
def safe_workplace_detail(safe_workplace_number):
    """Safe-Workplace 상세 페이지"""
    from common_mapping import smart_apply_mappings
    import sqlite3
    from section_service import SectionConfigService

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 섹션 서비스 초기화
    section_service = SectionConfigService('safe_workplace', DB_PATH)
    sections = section_service.get_sections_with_columns()

    # 동적 컬럼 정보 가져오기
    cursor.execute("""
        SELECT * FROM safe_workplace_column_config
        WHERE is_active = 1 AND (is_deleted = 0 OR is_deleted IS NULL)
        ORDER BY column_order
    """)
    columns = [dict(row) for row in cursor.fetchall()]

    # 데이터 조회
    cursor.execute("""
        SELECT sw.*, p.company_name, b.building_name
        FROM safe_workplace sw
        LEFT JOIN partners p ON sw.business_number = p.business_number
        LEFT JOIN buildings b ON sw.building_code = b.building_code
        WHERE sw.safe_workplace_number = ?
    """, (safe_workplace_number,))

    data = cursor.fetchone()
    conn.close()

    if not data:
        flash('요청한 데이터를 찾을 수 없습니다.', 'error')
        return redirect(url_for('safe_workplace_route'))

    # 데이터 매핑 적용
    data = dict(data)
    data = smart_apply_mappings(data, 'safe_workplace')

    popup = request.args.get('popup', '')

    return render_template('safe-workplace-detail.html',
                         data=data,
                         sections=sections,
                         columns=columns,
                         popup=popup)
'''

# 파일 끝에 추가
with open('add_page_routes.py', 'a', encoding='utf-8') as f:
    f.write('\n' + safe_workplace_routes)

print("Safe-workplace routes successfully added to add_page_routes.py")