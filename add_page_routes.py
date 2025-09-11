# ============= 필요한 imports (exec로 실행될 때 필요) =============
# 이 파일은 app.py에서 exec()로 실행되므로 필요한 imports를 명시적으로 추가
import logging
import sqlite3
from flask import request, render_template, jsonify
from db_connection import get_db_connection
from config.menu import MENU_CONFIG

# ============= Follow SOP 페이지 라우트 =============
@app.route("/follow-sop")
def follow_sop_route():
    """Follow SOP 페이지 라우트"""
    from common_mapping import smart_apply_mappings
    import math
    import sqlite3
    from section_service import SectionConfigService
    
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 섹션 서비스 초기화
    section_service = SectionConfigService('follow_sop', DB_PATH)
    
    # 기본 섹션 확인 및 생성
    cursor.execute("SELECT COUNT(*) FROM follow_sop_sections WHERE section_key = 'basic_info'")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO follow_sop_sections (section_key, section_name, section_order, is_active)
            VALUES ('basic_info', '기본정보', 1, 1)
        """)
        conn.commit()
    
    # 섹션 정보 가져오기
    sections = section_service.get_sections()
    
    # 동적 컬럼 정보 가져오기
    cursor.execute("""
        SELECT * FROM follow_sop_column_config 
        WHERE is_active = 1 AND (is_deleted = 0 OR is_deleted IS NULL)
        ORDER BY column_order
    """)
    dynamic_columns_rows = cursor.fetchall()
    dynamic_columns = [dict(row) for row in dynamic_columns_rows]
    try:
        logging.info(f"[FOLLOW_SOP] dynamic_columns={len(dynamic_columns)} first={[c.get('column_key') for c in dynamic_columns[:5]]}")
    except Exception:
        pass
    
    # 섹션별로 컬럼 분류
    section_columns = {}
    for section in sections:
        section_columns[section['section_key']] = [
            col for col in dynamic_columns if col.get('tab') == section['section_key']
        ]

    # 목록 표시용 컬럼(중복 제거, 불필요 키 제외) + 채점 항목 컬럼 인라인 확장
    excluded_keys = {'detailed_content', 'violation_content', 'work_req_no', 'registered_date', 'created_at'}
    seen_keys = set()
    display_columns = []

    def _expand_scoring_columns(col):
        try:
            import json as _json
            sc = col.get('scoring_config')
            if sc and isinstance(sc, str):
                try: sc = _json.loads(sc)
                except Exception: sc = {}
            if not sc or not isinstance(sc, dict):
                return []
            items = sc.get('items') or []
            out = []
            for it in items:
                item_id = it.get('id')
                label = it.get('label') or item_id
                if not item_id: 
                    continue
                dkey = f"{col.get('column_key')}__{item_id}"
                out.append({
                    'column_key': dkey,
                    'column_name': f"{col.get('column_name', col.get('column_key'))} - {label}",
                    'column_type': 'number',
                    'input_type': 'number_integer',
                    'is_active': 1,
                    'is_deleted': 0,
                    'tab': col.get('tab'),
                    '_virtual': 1,
                    '_source_scoring_key': col.get('column_key'),
                    '_source_item_id': item_id
                })
            return out
        except Exception:
            return []

    for col in dynamic_columns:
        key = col.get('column_key')
        if not key or key in excluded_keys:
            continue
        if col.get('column_type') == 'scoring':
            # 채점 항목을 개별 컬럼으로 확장
            for vcol in _expand_scoring_columns(col):
                vkey = vcol['column_key']
                if vkey in seen_keys:
                    continue
                seen_keys.add(vkey)
                display_columns.append(vcol)
            continue
        if key in seen_keys:
            continue
        seen_keys.add(key)
        display_columns.append(col)
    
    # 페이지네이션 처리
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    # 검색 조건 처리
    search_params = {}
    where_clauses = []
    query_params = []
    
    # 기본 검색 필드들
    company_name = request.args.get('company_name', '').strip()
    business_number = request.args.get('business_number', '').strip()
    
    if company_name:
        search_params['company_name'] = company_name
        # 호환: company_name 또는 company_name_1cha 키 모두 검색 (Postgres JSONB / SQLite JSON)
        if hasattr(conn, 'is_postgres') and conn.is_postgres:
            where_clauses.append("((s.custom_data->>'company_name') ILIKE %s OR (s.custom_data->>'company_name_1cha') ILIKE %s)")
        else:
            where_clauses.append("(JSON_EXTRACT(s.custom_data, '$.company_name') LIKE ? OR JSON_EXTRACT(s.custom_data, '$.company_name_1cha') LIKE ?)")
        query_params.extend([f"%{company_name}%", f"%{company_name}%"])
    
    if business_number:
        search_params['business_number'] = business_number
        # 호환: business_number 또는 company_name_1cha_bizno 키 모두 검색 (Postgres/SQLite 분기)
        if hasattr(conn, 'is_postgres') and conn.is_postgres:
            where_clauses.append("((s.custom_data->>'business_number') ILIKE %s OR (s.custom_data->>'company_name_1cha_bizno') ILIKE %s)")
        else:
            where_clauses.append("(JSON_EXTRACT(s.custom_data, '$.business_number') LIKE ? OR JSON_EXTRACT(s.custom_data, '$.company_name_1cha_bizno') LIKE ?)")
        query_params.extend([f"%{business_number}%", f"%{business_number}%"])
    
    # WHERE 절 구성 (삭제되지 않은 항목만)
    where_clauses.insert(0, "(s.is_deleted = 0 OR s.is_deleted IS NULL)")
    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
    
    # 메인 테이블 고정 사용
    table_name = "follow_sop"
    count_query = f"""
        SELECT COUNT(*) 
        FROM {table_name} s
        WHERE {where_sql}
    """
    
    cursor.execute(count_query, query_params)
    total_count = cursor.fetchone()[0]
    
    # 데이터 조회
    query = f"""
        SELECT s.* 
        FROM {table_name} s
        WHERE {where_sql}
        ORDER BY s.created_at DESC
        LIMIT ? OFFSET ?
    """
    
    query_params.extend([per_page, (page - 1) * per_page])
    cursor.execute(query, query_params)
    
    # 페이지네이션 계산을 위한 offset
    offset = (page - 1) * per_page
    
    items = []
    # 스코어 총점 계산을 위해 구성 수집
    import json as _json
    scoring_cols = [dict(c) for c in dynamic_columns if dict(c).get('column_type') == 'scoring']
    score_total_cols = [dict(c) for c in dynamic_columns if dict(c).get('column_type') == 'score_total']

    for idx, row in enumerate(cursor.fetchall()):
        item = dict(row)
        # custom_data 평탄화 (safety-instruction 방식)
        if item.get('custom_data'):
            try:
                import json
                raw = item.get('custom_data')
                custom_data = raw if isinstance(raw, dict) else (json.loads(raw) if isinstance(raw, str) and raw else {})
            except Exception as e:
                logging.error(f"custom_data 파싱 오류: {e}")
                custom_data = {}
            if isinstance(custom_data, dict):
                item.update(custom_data)

            # 채점 항목을 개별 키로 평탄화: source_scoring_key__item_id = count
            try:
                for dcol in display_columns:
                    if dcol.get('_virtual') == 1:
                        src = dcol.get('_source_scoring_key')
                        iid = dcol.get('_source_item_id')
                        if not src or not iid:
                            continue
                        group_obj = custom_data.get(src)
                        if isinstance(group_obj, str):
                            try:
                                import json as _json
                                group_obj = _json.loads(group_obj)
                            except Exception:
                                group_obj = {}
                        if isinstance(group_obj, dict):
                            item_key = f"{src}__{iid}"
                            item[item_key] = group_obj.get(iid, 0)
            except Exception as _e:
                logging.error(f"scoring flatten error: {_e}")

            # 채점 총점(score_total) 계산: total_key 기준 합산
            try:
                # 미리 파싱된 scoring/score_total configs
                # build map: group -> base_score (from score_total column config)
                for stc in score_total_cols:
                    conf = stc.get('scoring_config')
                    if conf and isinstance(conf, str):
                        try: conf = _json.loads(conf)
                        except Exception: conf = {}
                    total_key = (conf or {}).get('total_key') or 'default'
                    base = (conf or {}).get('base_score', 100)
                    total = base
                    # iterate scoring cols with same total_key
                    for sc_col in scoring_cols:
                        sconf = sc_col.get('scoring_config')
                        if sconf and isinstance(sconf, str):
                            try: sconf = _json.loads(sconf)
                            except Exception: sconf = {}
                        if ((sconf or {}).get('total_key') or 'default') != total_key:
                            continue
                        items_cfg = (sconf or {}).get('items') or []
                        group_obj = custom_data.get(sc_col.get('column_key'), {})
                        if isinstance(group_obj, str):
                            try: group_obj = _json.loads(group_obj)
                            except Exception: group_obj = {}
                        for it in items_cfg:
                            iid = it.get('id')
                            delta = float(it.get('per_unit_delta') or 0)
                            count = 0
                            if isinstance(group_obj, dict) and iid in group_obj:
                                try: count = int(group_obj.get(iid) or 0)
                                except Exception: count = 0
                            total += count * delta
                    # write into item using the score_total column key
                    item[stc.get('column_key')] = total
            except Exception as _e:
                logging.error(f"score_total compute error: {_e}")
        # No 칼럼은 역순 번호로 설정 (총 개수에서 역순)
        item['no'] = total_count - offset - idx
        items.append(item)
    
    try:
        logging.info(f"[FOLLOW_SOP] table={table_name} total_count={total_count} items={len(items)}")
        if items:
            logging.info(f"[FOLLOW_SOP] first_keys={list(items[0].keys())[:10]}")
    except Exception:
        pass
    conn.close()
    
    # 디버깅 로그 추가
    logging.info(f"[DEBUG] Follow SOP - Total items: {len(items)}")
    logging.info(f"[DEBUG] Follow SOP - Table used: {table_name}")
    logging.info(f"[DEBUG] Follow SOP - Total count: {total_count}")
    if items and len(items) > 0:
        logging.info(f"[DEBUG] Follow SOP - First item keys: {list(items[0].keys())[:5]}")
    
    # smart_apply_mappings 적용 (드롭다운 코드를 라벨로 변환)
    if items:
        from common_mapping import smart_apply_mappings
        items = smart_apply_mappings(items, 'follow_sop', dynamic_columns, DB_PATH)
    
    # 섹션 보정은 유지
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM follow_sop_sections WHERE section_key='work_info' AND (is_deleted=0 OR is_deleted IS NULL)")
        if (cursor.fetchone() or [0])[0] == 0:
            cursor.execute("INSERT OR IGNORE INTO follow_sop_sections (section_key, section_name, section_order, is_active, is_deleted) VALUES ('work_info','작업정보',2,1,0)")
            conn.commit()
    except Exception:
        pass
    
    # 페이지네이션 객체 생성 (app.py와 동일한 구조)
    class Pagination:
        def __init__(self, page, per_page, total_count):
            self.page = page
            self.per_page = per_page
            self.total_count = total_count
            self.pages = math.ceil(total_count / per_page) if total_count > 0 else 1
            self.has_prev = page > 1
            self.prev_num = page - 1 if self.has_prev else None
            self.has_next = page < self.pages
            self.next_num = page + 1 if self.has_next else None
            
        def iter_pages(self, window_size=10):
            start = ((self.page - 1) // window_size) * window_size + 1
            end = min(start + window_size - 1, self.pages)
            for num in range(start, end + 1):
                yield num
        
        def get_window_info(self, window_size=10):
            start = ((self.page - 1) // window_size) * window_size + 1
            end = min(start + window_size - 1, self.pages)
            has_prev_window = start > 1
            has_next_window = end < self.pages
            prev_window_start = max(1, start - window_size)
            next_window_start = min(end + 1, self.pages)
            return {
                'start': start,
                'end': end,
                'has_prev_window': has_prev_window,
                'has_next_window': has_next_window,
                'prev_window_start': prev_window_start,
                'next_window_start': next_window_start
            }
    
    pagination = Pagination(page=page, per_page=per_page, total_count=total_count)
    
    return render_template('follow-sop.html',
                         followsops=items,  # Follow SOP 전용 변수명
                         dynamic_columns=dynamic_columns,
                         sections=sections,
                         section_columns=section_columns,
                         display_columns=display_columns,
                         pagination=pagination,
                         search_params=search_params,
                         total_count=total_count,  # 추가
                         menu=MENU_CONFIG)

@app.route("/follow-sop-register")
def follow_sop_register():
    """Follow SOP 등록 페이지"""
    import sqlite3
    from timezone_config import get_korean_time_str, get_korean_time
    logging.info("Follow SOP 등록 페이지 접근")
    
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 섹션 정보 가져오기
    from section_service import SectionConfigService
    section_service = SectionConfigService('follow_sop', DB_PATH)
    
    # 기본 섹션 확인 및 생성
    cursor.execute("SELECT COUNT(*) FROM follow_sop_sections WHERE section_key = 'basic_info'")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO follow_sop_sections (section_key, section_name, section_order, is_active)
            VALUES ('basic_info', '기본정보', 1, 1)
        """)
        conn.commit()
    
    sections = section_service.get_sections()
    
    # 동적 컬럼 설정 가져오기
    cursor.execute("""
        SELECT * FROM follow_sop_column_config 
        WHERE is_active = 1 AND (is_deleted = 0 OR is_deleted IS NULL)
        ORDER BY column_order
    """)
    dynamic_columns_rows = cursor.fetchall()
    dynamic_columns = [dict(row) for row in dynamic_columns_rows]
    try:
        logging.info(f"[FULL_PROCESS] dynamic_columns={len(dynamic_columns)} first={[c.get('column_key') for c in dynamic_columns[:5]]}")
    except Exception:
        pass
    
    # 기본정보 필드 추가 (하드코딩) - 자동 생성값 포함
    from id_generator import generate_followsop_number
    from datetime import datetime
    created_at_dt = get_korean_time()
    created_at = created_at_dt.strftime('%Y-%m-%d %H:%M:%S')
    # created_at 기준으로 번호 생성
    work_req_no = generate_followsop_number(DB_PATH, created_at_dt)
    
    # work_req_no는 column_config에 없으므로 하드코딩
    basic_fields = [
        {'column_key': 'work_req_no', 'column_name': '점검번호', 'column_type': 'text', 
         'is_required': 1, 'is_readonly': 1, 'tab': 'basic_info', 'default_value': work_req_no}
    ]
    
    # created_at이 column_config에 있으면 거기서 가져오고 default_value만 설정
    for col in dynamic_columns:
        if col['column_key'] == 'created_at':
            col['default_value'] = created_at
            break
    
    # basic_info의 dynamic_columns 추가
    basic_info_dynamic = [col for col in dynamic_columns if col.get('tab') == 'basic_info']
    basic_fields.extend(basic_info_dynamic)
    
    # 섹션별로 컬럼 분류
    section_columns = {'basic_info': basic_fields}
    for section in sections:
        if section['section_key'] != 'basic_info':
            section_columns[section['section_key']] = [
                col for col in dynamic_columns if col.get('tab') == section['section_key']
            ]
    
    # 디버깅용 로그
    logging.info(f"Follow SOP Register - sections: {sections}")
    logging.info(f"Follow SOP Register - section_columns: {section_columns}")
    logging.info(f"Follow SOP Register - basic_fields: {basic_fields}")
    
    conn.close()
    
    # 팝업 여부 확인
    is_popup = request.args.get('popup') == '1'
    
    # 현재 날짜 추가 (한국 시간)
    from timezone_config import get_korean_time
    today_date = get_korean_time().strftime('%Y-%m-%d')
    
    return render_template('follow-sop-register.html',
                         dynamic_columns=dynamic_columns,
                         sections=sections,
                         section_columns=section_columns,  # 중요! 이것이 누락되어 있었음
                         today_date=today_date,  # 오늘 날짜 추가
                         is_popup=is_popup,
                         menu=MENU_CONFIG)

@app.route("/follow-sop-detail/<work_req_no>")
def follow_sop_detail(work_req_no):
    """Follow SOP 상세정보 페이지"""
    import json
    import sqlite3
    logging.info(f"Follow SOP 상세 정보 조회: {work_req_no}")
    
    # 테이블 존재 여부를 먼저 확인
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 사용 가능한 테이블 확인
    has_cache_table = False
    has_main_table = False
    
    try:
        # 테이블 존재 여부를 information_schema나 PRAGMA로 확인
        if hasattr(conn, 'is_postgres') and conn.is_postgres:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'follow_sop_cache'
                )
            """)
            has_cache_table = cursor.fetchone()[0]
        else:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='follow_sop_cache'")
            has_cache_table = cursor.fetchone() is not None
    except:
        pass
    
    try:
        if hasattr(conn, 'is_postgres') and conn.is_postgres:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'follow_sop'
                )
            """)
            has_main_table = cursor.fetchone()[0]
        else:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='follow_sop'")
            has_main_table = cursor.fetchone() is not None
    except:
        pass
    
    # Follow SOP 정보 조회 (메인 테이블 고정)
    sop_row = None
    try:
        cursor.execute("""
            SELECT * FROM follow_sop
            WHERE work_req_no = ? AND (is_deleted = 0 OR is_deleted IS NULL)
        """, (work_req_no,))
        sop_row = cursor.fetchone()
    except Exception as e:
        logging.error(f"follow_sop 조회 오류: {e}")
    
    if not sop_row:
        conn.close()
        return "Follow SOP를 찾을 수 없습니다.", 404
    
    sop = dict(sop_row)
    
    # details 테이블에서 상세내용 병합 (테이블 존재 확인 후 조회)
    try:
        details_exists = False
        if hasattr(conn, 'is_postgres') and conn.is_postgres:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'followsop_details'
                )
            """)
            details_exists = bool(cursor.fetchone()[0])
        else:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='followsop_details'")
            details_exists = cursor.fetchone() is not None
        if details_exists:
            detail_row = cursor.execute("""
                SELECT detailed_content FROM followsop_details
                WHERE work_req_no = ?
            """, (work_req_no,)).fetchone()
            if detail_row and detail_row['detailed_content']:
                sop['detailed_content'] = detail_row['detailed_content']
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        logging.error(f"followsop_details 조회 오류(롤백): {e}")
    
    # custom_data 평탄화 (safety-instruction 방식)
    custom_data = {}
    if sop.get('custom_data'):
        try:
            raw = sop.get('custom_data')
            custom_data = raw if isinstance(raw, dict) else (json.loads(raw) if isinstance(raw, str) and raw else {})
        except Exception as e:
            logging.error(f"Custom data parsing error: {e}")
            custom_data = {}
        if isinstance(custom_data, dict):
            sop.update(custom_data)
    
    # 섹션별 컬럼 정보 가져오기
    from section_service import SectionConfigService
    section_service = SectionConfigService('follow_sop', DB_PATH)
    sections = section_service.get_sections()
    
    # 동적 컬럼 설정 가져오기
    cursor.execute("""
        SELECT * FROM follow_sop_column_config 
        WHERE is_active = 1 AND (is_deleted = 0 OR is_deleted IS NULL)
        ORDER BY column_order
    """)
    dynamic_columns = [dict(row) for row in cursor.fetchall()]
    
    # 기본정보 필드 추가 (work_req_no만 하드코딩, created_at은 column_config에서 가져옴)
    basic_fields = [
        {'column_key': 'work_req_no', 'column_name': '점검번호', 'column_type': 'text', 
         'is_required': 1, 'is_readonly': 1, 'tab': 'basic_info'}
    ]
    
    # basic_info 섹션의 dynamic_columns 추가 (created_at 포함)
    basic_info_dynamic = [col for col in dynamic_columns if col.get('tab') == 'basic_info']
    basic_fields.extend(basic_info_dynamic)
    
    # 섹션별로 컬럼 분류
    section_columns = {'basic_info': basic_fields}
    for section in sections:
        if section['section_key'] != 'basic_info':
            section_columns[section['section_key']] = [
                col for col in dynamic_columns if col.get('tab') == section['section_key']
            ]
    
    # 디버깅용 로그
    logging.info(f"Follow SOP Detail - sections: {sections}")
    logging.info(f"Follow SOP Detail - section_columns: {section_columns}")
    
    conn.close()
    
    # 팝업 여부 확인
    is_popup = request.args.get('popup') == '1'
    
    # 전역 키(활성 컬럼) 전달
    all_keys = [c.get('column_key') for c in dynamic_columns if c.get('column_key')]
    return render_template('follow-sop-detail.html',
                         sop=sop,
                         custom_data=custom_data,
                         sections=sections,
                         section_columns=section_columns,
                         all_column_keys=all_keys,
                         is_popup=is_popup,
                         menu=MENU_CONFIG)

@app.route('/register-follow-sop', methods=['POST'])
def register_follow_sop():
    """새 Follow SOP 등록"""
    conn = None
    try:
        # safety-instruction과 동일한 방식으로 form data 처리
        import json
        from timezone_config import get_korean_time_str, get_korean_time
        from db.upsert import safe_upsert
        
        data = json.loads(request.form.get('data', '{}'))
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # created_at 기준으로 work_req_no 생성 (FS + yyMMddhhmm + 카운터)
        from id_generator import generate_followsop_number
        created_at_dt = get_korean_time()
        work_req_no = generate_followsop_number(DB_PATH, created_at_dt)
        
    # custom_data 처리
    custom_data = data.get('custom_data', {})
        if isinstance(custom_data, dict):
            import json
            custom_data_json = json.dumps(custom_data, ensure_ascii=False)
        else:
            custom_data_json = custom_data
        
    # Follow SOP 등록 - 메인 테이블로 저장
    upsert_data = {
        'work_req_no': work_req_no,
        'custom_data': custom_data_json,
        'created_at': created_at_dt.strftime('%Y-%m-%d %H:%M:%S'),
        'created_by': session.get('user_id', 'system'),
        'is_deleted': 0
    }
    # 충돌키 지정 (work_req_no)
    safe_upsert(
        conn,
        'follow_sop',
        upsert_data,
        conflict_cols=['work_req_no'],
        update_cols=['custom_data', 'updated_at', 'is_deleted']
    )
        
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

# 이 라우트는 app.py에 더 완전한 버전이 있으므로 백업으로 변경
# @app.route('/update-follow-sop', methods=['POST'])
def update_follow_sop_simple():
    """Follow SOP 수정"""
    conn = None
    try:
        import json
        
        # safety-instruction과 동일한 방식으로 FormData 받기
        work_req_no = request.form.get('work_req_no')
        detailed_content = request.form.get('detailed_content', '')
        custom_data = request.form.get('custom_data', '{}')
        
        if not work_req_no:
            return jsonify({'success': False, 'message': '점검번호가 필요합니다.'}), 400
        
        # JSON 파싱
        try:
            custom_data_dict = json.loads(custom_data) if custom_data != '{}' else {}
        except ValueError:
            return jsonify({"success": False, "message": "잘못된 데이터 형식입니다."}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # custom_data에 detailed_content 포함
        if detailed_content:
            custom_data_dict['detailed_content'] = detailed_content
        
        custom_data_json = json.dumps(custom_data_dict, ensure_ascii=False)
        
        # Follow SOP 업데이트
        cursor.execute("""
            UPDATE follow_sop 
            SET custom_data = ?, updated_by = ?
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
    import sqlite3
    from section_service import SectionConfigService
    
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 섹션 서비스 초기화
    section_service = SectionConfigService('full_process', DB_PATH)
    
    # 기본 섹션 확인 및 생성
    try:
        cursor.execute("SELECT COUNT(*) FROM full_process_sections WHERE section_key = 'basic_info'")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO full_process_sections (section_key, section_name, section_order, is_active)
                VALUES ('basic_info', '기본정보', 1, 1)
            """)
            conn.commit()
    except Exception as e:
        # 테이블이 없거나 컬럼이 없으면 무시
        conn.rollback() if hasattr(conn, 'rollback') else None
        pass
    
    # 섹션 정보 가져오기
    sections = section_service.get_sections()
    
    # 동적 컬럼 정보 가져오기
    cursor.execute("""
        SELECT * FROM full_process_column_config 
        WHERE is_active = 1 AND (is_deleted = 0 OR is_deleted IS NULL)
        ORDER BY column_order
    """)
    dynamic_columns_rows = cursor.fetchall()
    dynamic_columns = [dict(row) for row in dynamic_columns_rows]
    
    # 섹션별로 컬럼 분류
    section_columns = {}
    for section in sections:
        section_columns[section['section_key']] = [
            col for col in dynamic_columns if col.get('tab') == section['section_key']
        ]
    
    # 페이지네이션 처리
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    # 검색 조건 처리
    search_params = {}
    where_clauses = []
    query_params = []
    
    # 기본 검색 필드들
    company_name = request.args.get('company_name', '').strip()
    business_number = request.args.get('business_number', '').strip()
    
    if company_name:
        search_params['company_name'] = company_name
        # 호환: company_name 또는 company_1cha 키 모두 검색 (Postgres/SQLite 분기)
        if hasattr(conn, 'is_postgres') and conn.is_postgres:
            where_clauses.append("((p.custom_data->>'company_name') ILIKE %s OR (p.custom_data->>'company_1cha') ILIKE %s)")
        else:
            where_clauses.append("(JSON_EXTRACT(p.custom_data, '$.company_name') LIKE ? OR JSON_EXTRACT(p.custom_data, '$.company_1cha') LIKE ?)")
        query_params.extend([f"%{company_name}%", f"%{company_name}%"])
    
    if business_number:
        search_params['business_number'] = business_number
        # 호환: business_number 또는 company_1cha_bizno 키 모두 검색 (Postgres/SQLite 분기)
        if hasattr(conn, 'is_postgres') and conn.is_postgres:
            where_clauses.append("((p.custom_data->>'business_number') ILIKE %s OR (p.custom_data->>'company_1cha_bizno') ILIKE %s)")
        else:
            where_clauses.append("(JSON_EXTRACT(p.custom_data, '$.business_number') LIKE ? OR JSON_EXTRACT(p.custom_data, '$.company_1cha_bizno') LIKE ?)")
        query_params.extend([f"%{business_number}%", f"%{business_number}%"])
    
    # WHERE 절 구성 (삭제되지 않은 항목만)
    where_clauses.insert(0, "(p.is_deleted = 0 OR p.is_deleted IS NULL)")
    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
    
    # 캐시 우선 + 비어있으면 메인 테이블 (safety-instruction와 동일 철학)
    use_cache = False
    try:
        if hasattr(conn, 'is_postgres') and conn.is_postgres:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'full_process_cache'
                )
            """)
            exists = bool(cursor.fetchone()[0])
        else:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='full_process_cache'")
            exists = cursor.fetchone() is not None
        if exists:
            cursor.execute("SELECT COUNT(*) FROM full_process_cache")
            use_cache = (cursor.fetchone()[0] > 0)
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        use_cache = False
    table_name = "full_process"
    
    # 전체 건수 조회
    count_query = f"""
        SELECT COUNT(*) 
        FROM {table_name} p
        WHERE {where_sql}
    """
    
    cursor.execute(count_query, query_params)
    total_count = cursor.fetchone()[0]
    
    # 데이터 조회
    query = f"""
        SELECT p.* 
        FROM {table_name} p
        WHERE {where_sql}
        ORDER BY p.created_at DESC
        LIMIT ? OFFSET ?
    """
    
    query_params.extend([per_page, (page - 1) * per_page])
    cursor.execute(query, query_params)
    
    # 페이지네이션 계산을 위한 offset  
    offset = (page - 1) * per_page
    
    items = []
    for idx, row in enumerate(cursor.fetchall()):
        item = dict(row)
        # custom_data 평탄화 (safety-instruction 방식)
        if item.get('custom_data'):
            try:
                import json
                raw = item.get('custom_data')
                custom_data = raw if isinstance(raw, dict) else (json.loads(raw) if isinstance(raw, str) and raw else {})
            except Exception as e:
                logging.error(f"custom_data 파싱 오류: {e}")
                custom_data = {}
            if isinstance(custom_data, dict):
                item.update(custom_data)
        # No 칼럼은 역순 번호로 설정 (총 개수에서 역순)
        item['no'] = total_count - offset - idx
        items.append(item)
    
    try:
        logging.info(f"[FULL_PROCESS] table={table_name} total_count={total_count} items={len(items)}")
        if items:
            logging.info(f"[FULL_PROCESS] first_keys={list(items[0].keys())[:10]}")
    except Exception:
        pass
    conn.close()
    
    # smart_apply_mappings 적용 (드롭다운 코드를 라벨로 변환)
    if items:
        from common_mapping import smart_apply_mappings
        items = smart_apply_mappings(items, 'full_process', dynamic_columns, DB_PATH)
    
    # 섹션 보정은 유지
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM full_process_sections WHERE section_key='process_info' AND (is_deleted=0 OR is_deleted IS NULL)")
        if (cursor.fetchone() or [0])[0] == 0:
            cursor.execute("INSERT OR IGNORE INTO full_process_sections (section_key, section_name, section_order, is_active, is_deleted) VALUES ('process_info','프로세스 정보',2,1,0)")
            conn.commit()
    except Exception:
        pass
    
    # 페이지네이션 객체 생성 (app.py와 동일한 구조)
    class Pagination:
        def __init__(self, page, per_page, total_count):
            self.page = page
            self.per_page = per_page
            self.total_count = total_count
            self.pages = math.ceil(total_count / per_page) if total_count > 0 else 1
            self.has_prev = page > 1
            self.prev_num = page - 1 if self.has_prev else None
            self.has_next = page < self.pages
            self.next_num = page + 1 if self.has_next else None
            
        def iter_pages(self, window_size=10):
            start = ((self.page - 1) // window_size) * window_size + 1
            end = min(start + window_size - 1, self.pages)
            for num in range(start, end + 1):
                yield num
        
        def get_window_info(self, window_size=10):
            start = ((self.page - 1) // window_size) * window_size + 1
            end = min(start + window_size - 1, self.pages)
            has_prev_window = start > 1
            has_next_window = end < self.pages
            prev_window_start = max(1, start - window_size)
            next_window_start = min(end + 1, self.pages)
            return {
                'start': start,
                'end': end,
                'has_prev_window': has_prev_window,
                'has_next_window': has_next_window,
                'prev_window_start': prev_window_start,
                'next_window_start': next_window_start
            }
    
    pagination = Pagination(page=page, per_page=per_page, total_count=total_count)
    
    return render_template('full-process.html',
                         fullprocesses=items,  # Full Process 전용 변수명
                         dynamic_columns=dynamic_columns,
                         sections=sections,
                         section_columns=section_columns,
                         pagination=pagination,
                         search_params=search_params,
                         total_count=total_count,  # 추가
                         menu=MENU_CONFIG)

@app.route("/full-process-register")
def full_process_register():
    """Full Process 등록 페이지"""
    import sqlite3
    from timezone_config import get_korean_time_str, get_korean_time
    logging.info("Full Process 등록 페이지 접근")
    
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 섹션 서비스 초기화
    from section_service import SectionConfigService
    section_service = SectionConfigService('full_process', DB_PATH)
    
    # 기본 섹션 확인 및 생성
    try:
        cursor.execute("SELECT COUNT(*) FROM full_process_sections WHERE section_key = 'basic_info'")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO full_process_sections (section_key, section_name, section_order, is_active)
                VALUES ('basic_info', '기본정보', 1, 1)
            """)
            conn.commit()
    except Exception as e:
        # 테이블이 없거나 컬럼이 없으면 무시
        conn.rollback() if hasattr(conn, 'rollback') else None
        pass
    
    # 섹션 정보 가져오기
    sections = section_service.get_sections()
    
    # 동적 컬럼 설정 가져오기
    cursor.execute("""
        SELECT * FROM full_process_column_config 
        WHERE is_active = 1 AND (is_deleted = 0 OR is_deleted IS NULL)
        ORDER BY column_order
    """)
    dynamic_columns_rows = cursor.fetchall()
    dynamic_columns = [dict(row) for row in dynamic_columns_rows]
    # 드롭다운 코드 매핑 주입 (register)
    try:
        from app import get_dropdown_options_for_display as _get_opts
        for col in dynamic_columns:
            if col.get('column_type') == 'dropdown':
                opts = _get_opts('full_process', col.get('column_key'))
                col['dropdown_options_mapped'] = opts if opts else []
    except Exception:
        pass
    
    # 기본정보 필드 추가 (하드코딩) - 자동 생성값 포함
    from id_generator import generate_fullprocess_number
    from datetime import datetime
    created_at_dt = get_korean_time()
    created_at = created_at_dt.strftime('%Y-%m-%d %H:%M:%S')
    # created_at 기준으로 번호 생성
    fullprocess_number = generate_fullprocess_number(DB_PATH, created_at_dt)
    
    basic_fields = [
        {'column_key': 'fullprocess_number', 'column_name': '평가번호', 'column_type': 'text', 
         'is_required': 1, 'is_readonly': 1, 'tab': 'basic_info', 'default_value': fullprocess_number},
        {'column_key': 'created_at', 'column_name': '등록일', 'column_type': 'datetime', 
         'is_required': 1, 'is_readonly': 1, 'tab': 'basic_info', 'default_value': created_at}
    ]
    
    # 섹션별로 컬럼 분류
    section_columns = {'basic_info': basic_fields}
    for section in sections:
        if section['section_key'] != 'basic_info':
            section_columns[section['section_key']] = [
                col for col in dynamic_columns if col.get('tab') == section['section_key']
            ]
    
    conn.close()
    
    # 팝업 여부 확인
    is_popup = request.args.get('popup') == '1'
    
    # 현재 날짜 추가 (한국 시간)
    from timezone_config import get_korean_time
    today_date = get_korean_time().strftime('%Y-%m-%d')
    
    return render_template('full-process-register.html',
                         dynamic_columns=dynamic_columns,
                         sections=sections,
                         section_columns=section_columns,  # 중요! 이것이 누락되어 있었음
                         today_date=today_date,  # 오늘 날짜 추가
                         is_popup=is_popup,
                         menu=MENU_CONFIG)

@app.route("/full-process-detail/<fullprocess_number>")
def full_process_detail(fullprocess_number):
    """Full Process 상세정보 페이지"""
    import json
    import sqlite3
    logging.info(f"Full Process 상세 정보 조회: {fullprocess_number}")
    
    # 테이블 존재 여부를 먼저 확인
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 사용 가능한 테이블 확인
    has_cache_table = False
    has_main_table = False
    
    try:
        # 테이블 존재 여부를 information_schema나 PRAGMA로 확인
        if hasattr(conn, 'is_postgres') and conn.is_postgres:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'full_process_cache'
                )
            """)
            has_cache_table = cursor.fetchone()[0]
        else:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='full_process_cache'")
            has_cache_table = cursor.fetchone() is not None
    except:
        pass
    
    try:
        if hasattr(conn, 'is_postgres') and conn.is_postgres:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'full_process'
                )
            """)
            has_main_table = cursor.fetchone()[0]
        else:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='full_process'")
            has_main_table = cursor.fetchone() is not None
    except:
        pass
    
    # Full Process 정보 조회
    process_row = None
    
    # 메인 테이블에서만 조회
    try:
        cursor.execute("""
            SELECT * FROM full_process
            WHERE fullprocess_number = ? AND (is_deleted = 0 OR is_deleted IS NULL)
        """, (fullprocess_number,))
        process_row = cursor.fetchone()
    except Exception as e:
        logging.error(f"full_process 조회 오류: {e}")
    
    if not process_row:
        conn.close()
        return "Full Process를 찾을 수 없습니다.", 404
    
    process = dict(process_row)
    
    # details 테이블에서 상세내용 병합 (테이블 존재 확인 후 조회)
    try:
        details_exists = False
        if hasattr(conn, 'is_postgres') and conn.is_postgres:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'fullprocess_details'
                )
            """)
            details_exists = bool(cursor.fetchone()[0])
        else:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='fullprocess_details'")
            details_exists = cursor.fetchone() is not None
        if details_exists:
            detail_row = cursor.execute("""
                SELECT detailed_content FROM fullprocess_details
                WHERE fullprocess_number = ?
            """, (fullprocess_number,)).fetchone()
            if detail_row and detail_row['detailed_content']:
                process['detailed_content'] = detail_row['detailed_content']
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        logging.error(f"fullprocess_details 조회 오류(롤백): {e}")
    
    # custom_data 평탄화 (safety-instruction 방식)
    custom_data = {}
    if process.get('custom_data'):
        try:
            raw = process.get('custom_data')
            custom_data = raw if isinstance(raw, dict) else (json.loads(raw) if isinstance(raw, str) and raw else {})
        except Exception as e:
            logging.error(f"Custom data parsing error: {e}")
            custom_data = {}
        if isinstance(custom_data, dict):
            process.update(custom_data)
    
    # 섹션별 컬럼 정보 가져오기
    from section_service import SectionConfigService
    section_service = SectionConfigService('full_process', DB_PATH)
    sections = section_service.get_sections()
    
    # 동적 컬럼 설정 가져오기
    cursor.execute("""
        SELECT * FROM full_process_column_config 
        WHERE is_active = 1 AND (is_deleted = 0 OR is_deleted IS NULL)
        ORDER BY column_order
    """)
    dynamic_columns = [dict(row) for row in cursor.fetchall()]
    # 드롭다운 코드 매핑 주입 (detail)
    try:
        from app import get_dropdown_options_for_display as _get_opts
        for col in dynamic_columns:
            if col.get('column_type') == 'dropdown':
                opts = _get_opts('full_process', col.get('column_key'))
                col['dropdown_options_mapped'] = opts if opts else []
    except Exception:
        pass
    
    # 기본정보 필드 추가 (하드코딩)
    basic_fields = [
        {'column_key': 'fullprocess_number', 'column_name': '평가번호', 'column_type': 'text', 
         'is_required': 1, 'is_readonly': 1, 'tab': 'basic_info'},
        {'column_key': 'created_at', 'column_name': '등록일', 'column_type': 'datetime', 
         'is_required': 1, 'is_readonly': 1, 'tab': 'basic_info'}
    ]
    
    # 섹션별로 컬럼 분류
    section_columns = {'basic_info': basic_fields}
    for section in sections:
        if section['section_key'] != 'basic_info':
            section_columns[section['section_key']] = [
                col for col in dynamic_columns if col.get('tab') == section['section_key']
            ]
    
    conn.close()
    
    # 팝업 여부 확인
    is_popup = request.args.get('popup') == '1'
    
    # 전역 키(활성 컬럼) 전달
    all_keys = [c.get('column_key') for c in dynamic_columns if c.get('column_key')]
    return render_template('full-process-detail.html',
                         process=process,
                         instruction=process,  # 템플릿 호환용 별칭
                         custom_data=custom_data,
                         sections=sections,
                         section_columns=section_columns,
                         all_column_keys=all_keys,
                         is_popup=is_popup,
                         menu=MENU_CONFIG)

@app.route('/register-full-process', methods=['POST'])
def register_full_process():
    """새 Full Process 등록"""
    conn = None
    try:
        # safety-instruction과 동일한 방식으로 form data 처리
        import json
        from timezone_config import get_korean_time_str, get_korean_time
        from db.upsert import safe_upsert
        
        data = json.loads(request.form.get('data', '{}'))
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # created_at 기준으로 fullprocess_number 생성 (FP + yyMMddhhmm + 카운터)
        from id_generator import generate_fullprocess_number
        created_at_dt = get_korean_time()
        fullprocess_number = generate_fullprocess_number(DB_PATH, created_at_dt)
        
    # custom_data 처리
    custom_data = data.get('custom_data', {})
        if isinstance(custom_data, dict):
            import json
            custom_data_json = json.dumps(custom_data, ensure_ascii=False)
        else:
            custom_data_json = custom_data
        
    # Full Process 등록 - 메인 테이블 저장
    upsert_data = {
        'fullprocess_number': fullprocess_number,
        'custom_data': custom_data_json,
        'created_at': created_at_dt.strftime('%Y-%m-%d %H:%M:%S'),
        'created_by': session.get('user_id', 'system'),
        'is_deleted': 0
    }
    safe_upsert(
        conn,
        'full_process',
        upsert_data,
        conflict_cols=['fullprocess_number'],
        update_cols=['custom_data', 'updated_at', 'is_deleted']
    )
        
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

# 이 라우트는 app.py에 더 완전한 버전이 있으므로 백업으로 변경
# @app.route('/update-full-process', methods=['POST'])
def update_full_process_simple():
    """Full Process 수정"""
    conn = None
    try:
        import json
        
        # safety-instruction과 동일한 방식으로 FormData 받기
        fullprocess_number = request.form.get('fullprocess_number')
        detailed_content = request.form.get('detailed_content', '')
        custom_data = request.form.get('custom_data', '{}')
        
        if not fullprocess_number:
            return jsonify({'success': False, 'message': 'Process 번호가 필요합니다.'}), 400
        
        # JSON 파싱
        try:
            custom_data_dict = json.loads(custom_data) if custom_data != '{}' else {}
        except ValueError:
            return jsonify({"success": False, "message": "잘못된 데이터 형식입니다."}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # custom_data에 detailed_content 포함
        if detailed_content:
            custom_data_dict['detailed_content'] = detailed_content
        
        custom_data_json = json.dumps(custom_data_dict, ensure_ascii=False)
        
        # Full Process 업데이트
        cursor.execute("""
            UPDATE full_process 
            SET custom_data = ?, updated_by = ?
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
