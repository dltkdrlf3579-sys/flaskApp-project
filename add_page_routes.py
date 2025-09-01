# ============= Follow SOP 페이지 라우트 =============
@app.route("/follow-sop")
def follow_sop_route():
    """Follow SOP 페이지 라우트"""
    from common_mapping import smart_apply_mappings
    import math
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 동적 컬럼 정보 가져오기
    cursor.execute("""
        SELECT * FROM follow_sop_column_config 
        WHERE is_active = 1 AND (is_deleted = 0 OR is_deleted IS NULL)
        ORDER BY column_order
    """)
    dynamic_columns_rows = cursor.fetchall()
    dynamic_columns = [dict(row) for row in dynamic_columns_rows]
    
    # 페이지네이션 처리
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    # 검색 조건 처리
    search_params = {}
    where_clauses = []
    query_params = []
    
    # 기본 검색 필드들
    search_fields = ['company_name', 'business_number']
    for field in search_fields:
        value = request.args.get(field, '').strip()
        if value:
            search_params[field] = value
            where_clauses.append(f"s.{field} LIKE ?")
            query_params.append(f"%{value}%")
    
    # WHERE 절 구성
    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
    
    # 전체 건수 조회
    count_query = f"""
        SELECT COUNT(*) 
        FROM follow_sop s
        WHERE {where_sql}
    """
    
    cursor.execute(count_query, query_params)
    total_count = cursor.fetchone()[0]
    
    # 데이터 조회
    query = f"""
        SELECT s.* 
        FROM follow_sop s
        WHERE {where_sql}
        ORDER BY s.created_at DESC
        LIMIT ? OFFSET ?
    """
    
    query_params.extend([per_page, (page - 1) * per_page])
    cursor.execute(query, query_params)
    
    items = []
    for row in cursor.fetchall():
        item = dict(row)
        # custom_data JSON 파싱
        if item.get('custom_data'):
            try:
                import json
                item['custom_data'] = json.loads(item['custom_data'])
            except:
                item['custom_data'] = {}
        items.append(item)
    
    conn.close()
    
    # 페이지네이션 객체 생성
    class Pagination:
        def __init__(self, page, per_page, total_count):
            self.page = page
            self.per_page = per_page
            self.total_count = total_count
            self.total_pages = math.ceil(total_count / per_page) if per_page > 0 else 0
            
        @property
        def pages(self):
            return list(range(1, self.total_pages + 1))
        
        @property
        def prev_num(self):
            return self.page - 1 if self.page > 1 else None
        
        @property
        def next_num(self):
            return self.page + 1 if self.page < self.total_pages else None
        
        @property
        def has_prev(self):
            return self.page > 1
        
        @property
        def has_next(self):
            return self.page < self.total_pages
        
        def iter_pages(self, left_edge=2, left_current=2, right_current=3, right_edge=2):
            last = 0
            for num in range(1, self.total_pages + 1):
                if num <= left_edge or \
                   (self.page - left_current - 1 < num < self.page + right_current) or \
                   num > self.total_pages - right_edge:
                    if last + 1 != num:
                        yield None
                    yield num
                    last = num
    
    pagination = Pagination(page=page, per_page=per_page, total_count=total_count)
    
    return render_template('follow-sop.html',
                         items=items,
                         dynamic_columns=dynamic_columns,
                         pagination=pagination,
                         search_params=search_params,
                         menu=MENU_CONFIG)

@app.route("/follow-sop-register")
def follow_sop_register():
    """Follow SOP 등록 페이지"""
    logging.info("Follow SOP 등록 페이지 접근")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 섹션 정보 가져오기
    from section_service import SectionConfigService
    section_service = SectionConfigService('follow_sop', DB_PATH)
    sections = section_service.get_sections_with_columns()
    
    conn.close()
    
    # 팝업 여부 확인
    is_popup = request.args.get('popup') == '1'
    
    return render_template('follow-sop-register.html',
                         sections=sections,
                         is_popup=is_popup,
                         menu=MENU_CONFIG)

@app.route("/follow-sop-detail/<work_req_no>")
def follow_sop_detail(work_req_no):
    """Follow SOP 상세정보 페이지"""
    import json
    logging.info(f"Follow SOP 상세 정보 조회: {work_req_no}")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Follow SOP 정보 조회
    cursor.execute("""
        SELECT * FROM follow_sop
        WHERE work_req_no = ?
    """, (work_req_no,))
    
    sop_row = cursor.fetchone()
    if not sop_row:
        conn.close()
        return "Follow SOP를 찾을 수 없습니다.", 404
    
    sop = dict(sop_row)
    
    # custom_data JSON 파싱
    custom_data = {}
    if sop.get('custom_data'):
        try:
            custom_data = json.loads(sop['custom_data'])
        except:
            custom_data = {}
    
    # 섹션별 컬럼 정보 가져오기
    from section_service import SectionConfigService
    section_service = SectionConfigService('follow_sop', DB_PATH)
    sections = section_service.get_sections_with_columns()
    
    conn.close()
    
    # 팝업 여부 확인
    is_popup = request.args.get('popup') == '1'
    
    return render_template('follow-sop-detail.html',
                         sop=sop,
                         custom_data=custom_data,
                         sections=sections,
                         is_popup=is_popup,
                         menu=MENU_CONFIG)

@app.route('/register-follow-sop', methods=['POST'])
def register_follow_sop():
    """새 Follow SOP 등록"""
    conn = None
    try:
        data = request.get_json()
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # work_req_no 생성 (자동 생성 로직 필요)
        import datetime
        now = datetime.datetime.now()
        work_req_no = f"SOP{now.strftime('%Y%m%d%H%M%S')}"
        
        # custom_data 처리
        custom_data = data.get('custom_data', {})
        if isinstance(custom_data, dict):
            import json
            custom_data_json = json.dumps(custom_data, ensure_ascii=False)
        else:
            custom_data_json = custom_data
        
        # Follow SOP 등록
        cursor.execute("""
            INSERT INTO follow_sop (work_req_no, custom_data, created_at, created_by)
            VALUES (?, ?, datetime('now'), ?)
        """, (work_req_no, custom_data_json, session.get('user_id', 'system')))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Follow SOP가 등록되었습니다.',
            'work_req_no': work_req_no
        })
        
    except Exception as e:
        if conn:
            conn.rollback()
        logging.error(f"Follow SOP 등록 중 오류: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/update-follow-sop', methods=['POST'])
def update_follow_sop():
    """Follow SOP 수정"""
    conn = None
    try:
        data = request.get_json()
        work_req_no = data.get('work_req_no')
        
        if not work_req_no:
            return jsonify({'success': False, 'message': '작업요청번호가 필요합니다.'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # custom_data 처리
        custom_data = data.get('custom_data', {})
        if isinstance(custom_data, dict):
            import json
            custom_data_json = json.dumps(custom_data, ensure_ascii=False)
        else:
            custom_data_json = custom_data
        
        # Follow SOP 업데이트
        cursor.execute("""
            UPDATE follow_sop 
            SET custom_data = ?, updated_at = datetime('now'), updated_by = ?
            WHERE work_req_no = ?
        """, (custom_data_json, session.get('user_id', 'system'), work_req_no))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Follow SOP가 수정되었습니다.'
        })
        
    except Exception as e:
        if conn:
            conn.rollback()
        logging.error(f"Follow SOP 수정 중 오류: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if conn:
            conn.close()

# ============= Full Process 페이지 라우트 =============
@app.route("/full-process")
def full_process_route():
    """Full Process 페이지 라우트"""
    from common_mapping import smart_apply_mappings
    import math
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 동적 컬럼 정보 가져오기
    cursor.execute("""
        SELECT * FROM full_process_column_config 
        WHERE is_active = 1 AND (is_deleted = 0 OR is_deleted IS NULL)
        ORDER BY column_order
    """)
    dynamic_columns_rows = cursor.fetchall()
    dynamic_columns = [dict(row) for row in dynamic_columns_rows]
    
    # 페이지네이션 처리
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    # 검색 조건 처리
    search_params = {}
    where_clauses = []
    query_params = []
    
    # 기본 검색 필드들
    search_fields = ['company_name', 'business_number']
    for field in search_fields:
        value = request.args.get(field, '').strip()
        if value:
            search_params[field] = value
            where_clauses.append(f"p.{field} LIKE ?")
            query_params.append(f"%{value}%")
    
    # WHERE 절 구성
    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
    
    # 전체 건수 조회
    count_query = f"""
        SELECT COUNT(*) 
        FROM full_process p
        WHERE {where_sql}
    """
    
    cursor.execute(count_query, query_params)
    total_count = cursor.fetchone()[0]
    
    # 데이터 조회
    query = f"""
        SELECT p.* 
        FROM full_process p
        WHERE {where_sql}
        ORDER BY p.created_at DESC
        LIMIT ? OFFSET ?
    """
    
    query_params.extend([per_page, (page - 1) * per_page])
    cursor.execute(query, query_params)
    
    items = []
    for row in cursor.fetchall():
        item = dict(row)
        # custom_data JSON 파싱
        if item.get('custom_data'):
            try:
                import json
                item['custom_data'] = json.loads(item['custom_data'])
            except:
                item['custom_data'] = {}
        items.append(item)
    
    conn.close()
    
    # 페이지네이션 객체 생성
    class Pagination:
        def __init__(self, page, per_page, total_count):
            self.page = page
            self.per_page = per_page
            self.total_count = total_count
            self.total_pages = math.ceil(total_count / per_page) if per_page > 0 else 0
            
        @property
        def pages(self):
            return list(range(1, self.total_pages + 1))
        
        @property
        def prev_num(self):
            return self.page - 1 if self.page > 1 else None
        
        @property
        def next_num(self):
            return self.page + 1 if self.page < self.total_pages else None
        
        @property
        def has_prev(self):
            return self.page > 1
        
        @property
        def has_next(self):
            return self.page < self.total_pages
        
        def iter_pages(self, left_edge=2, left_current=2, right_current=3, right_edge=2):
            last = 0
            for num in range(1, self.total_pages + 1):
                if num <= left_edge or \
                   (self.page - left_current - 1 < num < self.page + right_current) or \
                   num > self.total_pages - right_edge:
                    if last + 1 != num:
                        yield None
                    yield num
                    last = num
    
    pagination = Pagination(page=page, per_page=per_page, total_count=total_count)
    
    return render_template('full-process.html',
                         items=items,
                         dynamic_columns=dynamic_columns,
                         pagination=pagination,
                         search_params=search_params,
                         menu=MENU_CONFIG)

@app.route("/full-process-register")
def full_process_register():
    """Full Process 등록 페이지"""
    logging.info("Full Process 등록 페이지 접근")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 섹션 정보 가져오기
    from section_service import SectionConfigService
    section_service = SectionConfigService('full_process', DB_PATH)
    sections = section_service.get_sections_with_columns()
    
    conn.close()
    
    # 팝업 여부 확인
    is_popup = request.args.get('popup') == '1'
    
    return render_template('full-process-register.html',
                         sections=sections,
                         is_popup=is_popup,
                         menu=MENU_CONFIG)

@app.route("/full-process-detail/<fullprocess_number>")
def full_process_detail(fullprocess_number):
    """Full Process 상세정보 페이지"""
    import json
    logging.info(f"Full Process 상세 정보 조회: {fullprocess_number}")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Full Process 정보 조회
    cursor.execute("""
        SELECT * FROM full_process
        WHERE fullprocess_number = ?
    """, (fullprocess_number,))
    
    process_row = cursor.fetchone()
    if not process_row:
        conn.close()
        return "Full Process를 찾을 수 없습니다.", 404
    
    process = dict(process_row)
    
    # custom_data JSON 파싱
    custom_data = {}
    if process.get('custom_data'):
        try:
            custom_data = json.loads(process['custom_data'])
        except:
            custom_data = {}
    
    # 섹션별 컬럼 정보 가져오기
    from section_service import SectionConfigService
    section_service = SectionConfigService('full_process', DB_PATH)
    sections = section_service.get_sections_with_columns()
    
    conn.close()
    
    # 팝업 여부 확인
    is_popup = request.args.get('popup') == '1'
    
    return render_template('full-process-detail.html',
                         process=process,
                         custom_data=custom_data,
                         sections=sections,
                         is_popup=is_popup,
                         menu=MENU_CONFIG)

@app.route('/register-full-process', methods=['POST'])
def register_full_process():
    """새 Full Process 등록"""
    conn = None
    try:
        data = request.get_json()
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # fullprocess_number 생성 (자동 생성 로직 필요)
        import datetime
        now = datetime.datetime.now()
        fullprocess_number = f"FP{now.strftime('%Y%m%d%H%M%S')}"
        
        # custom_data 처리
        custom_data = data.get('custom_data', {})
        if isinstance(custom_data, dict):
            import json
            custom_data_json = json.dumps(custom_data, ensure_ascii=False)
        else:
            custom_data_json = custom_data
        
        # Full Process 등록
        cursor.execute("""
            INSERT INTO full_process (fullprocess_number, custom_data, created_at, created_by)
            VALUES (?, ?, datetime('now'), ?)
        """, (fullprocess_number, custom_data_json, session.get('user_id', 'system')))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Full Process가 등록되었습니다.',
            'fullprocess_number': fullprocess_number
        })
        
    except Exception as e:
        if conn:
            conn.rollback()
        logging.error(f"Full Process 등록 중 오류: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/update-full-process', methods=['POST'])
def update_full_process():
    """Full Process 수정"""
    conn = None
    try:
        data = request.get_json()
        fullprocess_number = data.get('fullprocess_number')
        
        if not fullprocess_number:
            return jsonify({'success': False, 'message': 'Process 번호가 필요합니다.'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # custom_data 처리
        custom_data = data.get('custom_data', {})
        if isinstance(custom_data, dict):
            import json
            custom_data_json = json.dumps(custom_data, ensure_ascii=False)
        else:
            custom_data_json = custom_data
        
        # Full Process 업데이트
        cursor.execute("""
            UPDATE full_process 
            SET custom_data = ?, updated_at = datetime('now'), updated_by = ?
            WHERE fullprocess_number = ?
        """, (custom_data_json, session.get('user_id', 'system'), fullprocess_number))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Full Process가 수정되었습니다.'
        })
        
    except Exception as e:
        if conn:
            conn.rollback()
        logging.error(f"Full Process 수정 중 오류: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if conn:
            conn.close()