# ============= 필요한 imports (exec로 실행될 때 필요) =============
# 이 파일은 app.py에서 exec()로 실행되므로 필요한 imports를 명시적으로 추가
import logging
import sqlite3
from flask import request, render_template, jsonify, session
from db_connection import get_db_connection
from column_utils import normalize_column_types

# 공통: fetchone() 결과 첫 번째 값 안전 추출
def _first(row, default=0):
    try:
        if row is None:
            return default
        # sqlite3.Row 또는 tuple/리스트 인덱스 0 시도
        try:
            return row[0]
        except Exception:
            pass
        # dict 계열 대응
        if hasattr(row, 'values'):
            vals = list(row.values())
            return vals[0] if vals else default
        return default
    except Exception:
        return default
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
    if _first(cursor.fetchone(), 0) == 0:
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
    # 컬럼 타입 정규화 - 공통 함수 사용
    dynamic_columns = normalize_column_types(dynamic_columns)
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

    # 목록 표시용 컬럼(채점 항목 확장) + 총점/채점 목록 준비
    display_columns = []
    try:
        import json as _json
        def _expand_scoring_columns(_col):
            sc = _col.get('scoring_config')
            if sc and isinstance(sc, str):
                try: sc = _json.loads(sc)
                except Exception: sc = {}
            items = (sc or {}).get('items') or []
            out = []
            for it in items:
                iid = it.get('id')
                label = it.get('label') or iid
                if not iid:
                    continue
                out.append({
                    'column_key': f"{_col.get('column_key')}__{iid}",
                    'column_name': f"{_col.get('column_name', _col.get('column_key'))} - {label}",
                    'column_type': 'number',
                    'input_type': 'number_integer',
                    'is_active': 1,
                    'is_deleted': 0,
                    'tab': _col.get('tab'),
                    '_virtual': 1,
                    '_source_scoring_key': _col.get('column_key'),
                    '_source_item_id': iid
                })
            return out
        excluded = {'detailed_content', 'violation_content', 'fullprocess_number', 'created_at'}
        for col in dynamic_columns:
            ck = col.get('column_key')
            if not ck or ck in excluded:
                continue
            if col.get('column_type') == 'scoring':
                display_columns.extend(_expand_scoring_columns(col))
            else:
                display_columns.append(col)
        scoring_cols = [dict(c) for c in dynamic_columns if dict(c).get('column_type') == 'scoring']
        score_total_cols = [dict(c) for c in dynamic_columns if dict(c).get('column_type') == 'score_total']
    except Exception as _e:
        scoring_cols, score_total_cols = [], []
        logging.warning(f"[FULL_PROCESS] display_columns/scoring list build failed: {_e}")
    
    # 목록 표시용 컬럼: 채점(JSON) → 개별 가상 컬럼으로 확장
    display_columns = []
    try:
        import json as _json
        def _expand_scoring_columns(col):
            sc = col.get('scoring_config')
            if sc and isinstance(sc, str):
                try: sc = _json.loads(sc)
                except Exception: sc = {}
            items = (sc or {}).get('items') or []
            out = []
            for it in items:
                iid = it.get('id')
                label = it.get('label') or iid
                if not iid:
                    continue
                out.append({
                    'column_key': f"{col.get('column_key')}__{iid}",
                    'column_name': f"{col.get('column_name', col.get('column_key'))} - {label}",
                    'column_type': 'number',
                    'input_type': 'number_integer',
                    'is_active': 1,
                    'is_deleted': 0,
                    'tab': col.get('tab'),
                    '_virtual': 1,
                    '_source_scoring_key': col.get('column_key'),
                    '_source_item_id': iid
                })
            return out
        excluded = {'detailed_content', 'violation_content', 'fullprocess_number', 'created_at'}
        for col in dynamic_columns:
            ck = col.get('column_key')
            if not ck or ck in excluded:
                continue
            if (col.get('column_type') == 'scoring'):
                display_columns.extend(_expand_scoring_columns(col))
            else:
                display_columns.append(col)
    except Exception as _e:
        logging.warning(f"[FULL_PROCESS] build display_columns failed: {_e}")
    # 채점 및 총점 컬럼 목록 준비
    try:
        import json as _json
        scoring_cols = [dict(c) for c in dynamic_columns if dict(c).get('column_type') == 'scoring']
        score_total_cols = [dict(c) for c in dynamic_columns if dict(c).get('column_type') == 'score_total']
    except Exception:
        scoring_cols, score_total_cols = [], []

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
            where_clauses.append("(JSON_EXTRACT(s.custom_data, '$.company_name') LIKE %s OR JSON_EXTRACT(s.custom_data, '$.company_name_1cha') LIKE %s)")
        query_params.extend([f"%{company_name}%", f"%{company_name}%"])
    
    if business_number:
        search_params['business_number'] = business_number
        # 호환: business_number 또는 company_name_1cha_bizno 키 모두 검색 (Postgres/SQLite 분기)
        if hasattr(conn, 'is_postgres') and conn.is_postgres:
            where_clauses.append("((s.custom_data->>'business_number') ILIKE %s OR (s.custom_data->>'company_name_1cha_bizno') ILIKE %s)")
        else:
            where_clauses.append("(JSON_EXTRACT(s.custom_data, '$.business_number') LIKE %s OR JSON_EXTRACT(s.custom_data, '$.company_name_1cha_bizno') LIKE %s)")
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
    total_count = _first(cursor.fetchone(), 0)
    
    # 데이터 조회
    query = f"""
        SELECT s.* 
        FROM {table_name} s
        WHERE {where_sql}
        ORDER BY s.created_at DESC
        LIMIT %s OFFSET %s
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
                # PostgreSQL JSONB는 이미 dict로 반환됨
                if isinstance(raw, dict):
                    custom_data = raw
                else:
                    custom_data = json.loads(raw) if isinstance(raw, str) and raw else {}
            except Exception as e:
                logging.error(f"custom_data 파싱 오류: {e}")
                custom_data = {}
            if isinstance(custom_data, dict):
                item.update(custom_data)
            # 채점 항목 평탄화 (가상 컬럼 채우기)
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
                logging.error(f"[FULL_PROCESS] scoring flatten error: {_e}")
            # 총점 계산 (include_keys 우선)
            try:
                for stc in score_total_cols:
                    conf = stc.get('scoring_config')
                    if conf and isinstance(conf, str):
                        try: conf = _json.loads(conf)
                        except Exception: conf = {}
                    base = (conf or {}).get('base_score', 100)
                    total = base
                    include_keys = (conf or {}).get('include_keys') or []
                    if include_keys:
                        for key in include_keys:
                            sc_col = next((c for c in scoring_cols if c.get('column_key') == key), None)
                            if not sc_col:
                                continue
                            sconf = sc_col.get('scoring_config')
                            if sconf and isinstance(sconf, str):
                                try: sconf = _json.loads(sconf)
                                except Exception: sconf = {}
                            items_cfg = (sconf or {}).get('items') or []
                            group_obj = custom_data.get(key, {}) if isinstance(custom_data, dict) else {}
                            if isinstance(group_obj, str):
                                try: group_obj = _json.loads(group_obj)
                                except Exception: group_obj = {}
                            for it in items_cfg:
                                iid = it.get('id')
                                delta = float(it.get('per_unit_delta') or 0)
                                cnt = 0
                                if isinstance(group_obj, dict) and iid in group_obj:
                                    try: cnt = int(group_obj.get(iid) or 0)
                                    except Exception: cnt = 0
                                total += cnt * delta
                    else:
                        total_key = (conf or {}).get('total_key') or 'default'
                        for sc_col in scoring_cols:
                            sconf = sc_col.get('scoring_config')
                            if sconf and isinstance(sconf, str):
                                try: sconf = _json.loads(sconf)
                                except Exception: sconf = {}
                            if ((sconf or {}).get('total_key') or 'default') != total_key:
                                continue
                            items_cfg = (sconf or {}).get('items') or []
                            group_obj = custom_data.get(sc_col.get('column_key'), {}) if isinstance(custom_data, dict) else {}
                            if isinstance(group_obj, str):
                                try: group_obj = _json.loads(group_obj)
                                except Exception: group_obj = {}
                            for it in items_cfg:
                                iid = it.get('id')
                                delta = float(it.get('per_unit_delta') or 0)
                                cnt = 0
                                if isinstance(group_obj, dict) and iid in group_obj:
                                    try: cnt = int(group_obj.get(iid) or 0)
                                    except Exception: cnt = 0
                                total += cnt * delta
                    item[stc.get('column_key')] = total
            except Exception as _e:
                logging.error(f"[FULL_PROCESS] score_total compute error: {_e}")
            # 채점 항목 평탄화: source__item = count
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
                            item[f"{src}__{iid}"] = group_obj.get(iid, 0)
            except Exception as _e:
                logging.error(f"[FULL_PROCESS] scoring flatten error: {_e}")
        # score_total 계산 (include_keys 우선)
        try:
            for stc in score_total_cols:
                conf = stc.get('scoring_config')
                if conf and isinstance(conf, str):
                    try: conf = _json.loads(conf)
                    except Exception: conf = {}
                base = (conf or {}).get('base_score', 100)
                total = base
                include_keys = (conf or {}).get('include_keys') or []
                if include_keys:
                    for key in include_keys:
                        sc_col = next((c for c in scoring_cols if c.get('column_key') == key), None)
                        if not sc_col:
                            continue
                        sconf = sc_col.get('scoring_config')
                        if sconf and isinstance(sconf, str):
                            try: sconf = _json.loads(sconf)
                            except Exception: sconf = {}
                        items_cfg = (sconf or {}).get('items') or []
                        group_obj = custom_data.get(key, {}) if isinstance(custom_data, dict) else {}
                        if isinstance(group_obj, str):
                            try: group_obj = _json.loads(group_obj)
                            except Exception: group_obj = {}
                        for it in items_cfg:
                            iid = it.get('id')
                            delta = float(it.get('per_unit_delta') or 0)
                            cnt = 0
                            if isinstance(group_obj, dict) and iid in group_obj:
                                try: cnt = int(group_obj.get(iid) or 0)
                                except Exception: cnt = 0
                            total += cnt * delta
                else:
                    # 하위호환: total_key 그룹
                    total_key = (conf or {}).get('total_key') or 'default'
                    for sc_col in scoring_cols:
                        sconf = sc_col.get('scoring_config')
                        if sconf and isinstance(sconf, str):
                            try: sconf = _json.loads(sconf)
                            except Exception: sconf = {}
                        if ((sconf or {}).get('total_key') or 'default') != total_key:
                            continue
                        items_cfg = (sconf or {}).get('items') or []
                        group_obj = custom_data.get(sc_col.get('column_key'), {}) if isinstance(custom_data, dict) else {}
                        if isinstance(group_obj, str):
                            try: group_obj = _json.loads(group_obj)
                            except Exception: group_obj = {}
                        for it in items_cfg:
                            iid = it.get('id')
                            delta = float(it.get('per_unit_delta') or 0)
                            cnt = 0
                            if isinstance(group_obj, dict) and iid in group_obj:
                                try: cnt = int(group_obj.get(iid) or 0)
                                except Exception: cnt = 0
                            total += cnt * delta
                item[stc.get('column_key')] = total
        except Exception as _e:
            logging.error(f"[FULL_PROCESS] score_total compute error: {_e}")

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

            # 채점 총점(score_total) 계산: include_keys 우선, 없으면 total_key 기준 합산
            try:
                # 미리 파싱된 scoring/score_total configs
                # build map: group -> base_score (from score_total column config)
                for stc in score_total_cols:
                    conf = stc.get('scoring_config')
                    if conf and isinstance(conf, str):
                        try: conf = _json.loads(conf)
                        except Exception: conf = {}
                    base = (conf or {}).get('base_score', 100)
                    total = base
                    include_keys = (conf or {}).get('include_keys') or []
                    if include_keys:
                        # 명시된 채점 컬럼 키들만 합산
                        for key in include_keys:
                            sc_col = next((c for c in scoring_cols if c.get('column_key') == key), None)
                            if not sc_col:
                                continue
                            sconf = sc_col.get('scoring_config')
                            if sconf and isinstance(sconf, str):
                                try: sconf = _json.loads(sconf)
                                except Exception: sconf = {}
                            items_cfg = (sconf or {}).get('items') or []
                            group_obj = custom_data.get(key, {})
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
                    else:
                        # total_key 그룹 방식 (하위호환)
                        total_key = (conf or {}).get('total_key') or 'default'
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
        if _first(cursor.fetchone(), 0) == 0:
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
    if _first(cursor.fetchone(), 0) == 0:
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
    # 링크드/팝업 타입 보정
    try:
        all_keys = {c.get('column_key') for c in dynamic_columns if c.get('column_key')}
        suffixes = ['_id','_dept','_department','_department_code','_bizno','_company_bizno','_code','_company']
        def base_key_of(k: str) -> str:
            if not isinstance(k, str):
                return ''
            for s in suffixes:
                if k.endswith(s):
                    return k[:-len(s)]
            return k
        def infer_group(bk: str) -> str:
            if not bk:
                return ''
            variants = [bk, bk+'d']
            if any(((v+'_company_bizno') in all_keys) or ((v+'_bizno') in all_keys) for v in variants):
                return 'company'
            if any(((v+'_dept') in all_keys) or ((v+'_department') in all_keys) or ((v+'_department_code') in all_keys) for v in variants):
                return 'department'
            if any(((v+'_id') in all_keys) for v in variants):
                return 'person'
            if any(((v+'_company') in all_keys) for v in variants):
                return 'contractor'
            return ''
        popup_map = {'person':'popup_person','company':'popup_company','department':'popup_department','contractor':'popup_contractor'}
        for col in dynamic_columns:
            ck = col.get('column_key') or ''
            bk = base_key_of(ck)
            grp = infer_group(bk)
            # dept 관련은 별도 처리 유지
            if ck.endswith(('_dept', '_department', '_department_code')):
                col['column_type'] = 'linked_dept'
                continue
            # 나머지 linked 필드는 determine_linked_type 사용
            if (ck.endswith('_id') or ck.endswith('_bizno') or
                ck.endswith('_company') or ck.endswith('_company_bizno')):
                col['column_type'] = determine_linked_type(col)
                continue
            if grp and ck == bk:
                ct = col.get('column_type')
                if not ct or ct in ('text','popup','table','table_select'):
                    col['column_type'] = popup_map.get(grp, ct)
                col['input_type'] = col.get('input_type') or 'table'
    except Exception as _e:
        logging.warning(f"follow_sop register: normalize types failed: {_e}")

    # 컬럼 타입 정규화 - 공통 함수 사용 (DB의 잘못된 타입도 자동 수정)
    dynamic_columns = normalize_column_types(dynamic_columns)

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
    
    # work_req_no와 created_at을 하드코딩
    basic_fields = [
        {'column_key': 'work_req_no', 'column_name': '점검번호', 'column_type': 'text',
         'is_required': 1, 'is_readonly': 1, 'tab': 'basic_info', 'default_value': work_req_no},
        {'column_key': 'created_at', 'column_name': '등록일', 'column_type': 'datetime',
         'is_required': 1, 'is_readonly': 1, 'tab': 'basic_info', 'default_value': created_at}
    ]

    # basic_info의 dynamic_columns 추가 (work_req_no, created_at 제외)
    basic_info_dynamic = [col for col in dynamic_columns
                         if col.get('tab') == 'basic_info'
                         and col.get('column_key') not in ['work_req_no', 'created_at']]
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
    
    # 드롭다운 옵션 로드
    basic_options = {}
    try:
        from app import get_dropdown_options_for_display as _get_opts
        for col in dynamic_columns:
            if col.get('column_type') == 'dropdown':
                col_key = col.get('column_key')
                if col_key:
                    opts = _get_opts('follow_sop', col_key)
                    if opts:
                        basic_options[col_key] = opts
    except Exception as e:
        logging.error(f"Failed to load dropdown options: {e}")

    # 현재 날짜 추가 (한국 시간)
    from timezone_config import get_korean_time
    today_date = get_korean_time().strftime('%Y-%m-%d')

    return render_template('follow-sop-register.html',
                         dynamic_columns=dynamic_columns,
                         sections=sections,
                         section_columns=section_columns,  # 중요! 이것이 누락되어 있었음
                         basic_options=basic_options,  # 드롭다운 옵션 추가
                         today_date=today_date,  # 오늘 날짜 추가
                         is_popup=is_popup,
                         menu=MENU_CONFIG)

@app.route("/follow-sop-detail/<work_req_no>")
def follow_sop_detail(work_req_no):
    """Follow SOP 상세정보 페이지"""
    import json
    logging.info(f"Follow SOP 상세 정보 조회: {work_req_no}")

    # 테이블 존재 여부를 먼저 확인
    conn = get_db_connection()
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
            has_cache_table = _first(cursor.fetchone(), 0)
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
            has_main_table = _first(cursor.fetchone(), 0)
        else:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='follow_sop'")
            has_main_table = cursor.fetchone() is not None
    except:
        pass
    
    # Follow SOP 정보 조회 - 필요한 모든 컬럼 명시
    sop = {}
    try:
        cursor.execute("""
            SELECT work_req_no, custom_data,
                   created_at, updated_at, is_deleted
            FROM follow_sop
            WHERE work_req_no = %s AND (is_deleted = 0 OR is_deleted IS NULL)
        """, (work_req_no,))
        sop_row = cursor.fetchone()

        if sop_row:
            # 명시한 순서대로 매핑 (컬럼 추가/삭제 시 여기만 수정)
            sop = {
                'work_req_no': sop_row[0],
                'custom_data': sop_row[1],
                'created_at': sop_row[2],
                'updated_at': sop_row[3],
                'is_deleted': sop_row[4],
                'created_by': None,  # follow_sop 테이블에 없음
                'updated_by': None   # follow_sop 테이블에 없음
            }
    except Exception as e:
        logging.error(f"follow_sop 조회 오류: {e}")

    if not sop:
        conn.close()
        return "Follow SOP를 찾을 수 없습니다.", 404
    
    # details 테이블 조회는 custom_data 평탄화 후에 수행 (아래에서 처리)
    
    # custom_data 평탄화 (safety-instruction 방식)
    custom_data = {}
    if sop.get('custom_data'):
        try:
            raw = sop.get('custom_data')
            # PostgreSQL JSONB는 이미 dict로 반환됨
            if isinstance(raw, dict):
                custom_data = raw
            else:
                custom_data = json.loads(raw) if isinstance(raw, str) and raw else {}
        except Exception as e:
            logging.error(f"Custom data parsing error: {e}")
            custom_data = {}
        if isinstance(custom_data, dict):
            sop.update(custom_data)
    
    # follow_sop_details 테이블에서 detailed_content 조회
    try:
        cursor.execute("""
            SELECT detailed_content
            FROM follow_sop_details
            WHERE work_req_no = %s
        """, (work_req_no,))
        detail_row = cursor.fetchone()
        if detail_row and detail_row[0]:
            sop['detailed_content'] = detail_row[0]
            print(f"[FS DETAIL DEBUG] Loaded detailed_content from follow_sop_details: {len(detail_row[0])} chars")
            print(f"[FS DETAIL DEBUG] detailed_content value: {detail_row[0][:100]}")  # 디버깅용
        else:
            sop['detailed_content'] = ''
            print("[FS DETAIL DEBUG] No detailed_content in details table, using empty string")
    except Exception as e:
        print(f"[FS DETAIL DEBUG] Failed to load from follow_sop_details: {e}")
        # 기존 custom_data에서 읽기 (하위 호환성)
        if 'detailed_content' not in sop:
            sop['detailed_content'] = ''

    # 최종 확인
    print(f"[FS DETAIL DEBUG] Final sop.detailed_content: {sop.get('detailed_content', 'NOT SET')[:100]}")
    
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
    # 링크드/팝업 타입 보정
    try:
        all_keys = {c.get('column_key') for c in dynamic_columns if c.get('column_key')}
        suffixes = ['_id','_dept','_department','_department_code','_bizno','_company_bizno','_code','_company']
        def base_key_of(k: str) -> str:
            if not isinstance(k, str):
                return ''
            for s in suffixes:
                if k.endswith(s):
                    return k[:-len(s)]
            return k
        def infer_group(bk: str) -> str:
            if not bk:
                return ''
            variants = [bk, bk+'d']
            if any(((v+'_company_bizno') in all_keys) or ((v+'_bizno') in all_keys) for v in variants):
                return 'company'
            if any(((v+'_dept') in all_keys) or ((v+'_department') in all_keys) or ((v+'_department_code') in all_keys) for v in variants):
                return 'department'
            if any(((v+'_id') in all_keys) for v in variants):
                return 'person'
            if any(((v+'_company') in all_keys) for v in variants):
                return 'contractor'
            return ''
        popup_map = {'person':'popup_person','company':'popup_company','department':'popup_department','contractor':'popup_contractor'}
        for col in dynamic_columns:
            ck = col.get('column_key') or ''
            bk = base_key_of(ck)
            grp = infer_group(bk)
            # dept 관련은 별도 처리 유지
            if ck.endswith(('_dept', '_department', '_department_code')):
                col['column_type'] = 'linked_dept'
                continue
            # 나머지 linked 필드는 determine_linked_type 사용
            if (ck.endswith('_id') or ck.endswith('_bizno') or
                ck.endswith('_company') or ck.endswith('_company_bizno')):
                col['column_type'] = determine_linked_type(col)
                continue
            if grp and ck == bk:
                ct = col.get('column_type')
                if not ct or ct in ('text','popup','table','table_select'):
                    col['column_type'] = popup_map.get(grp, ct)
                col['input_type'] = col.get('input_type') or 'table'
    except Exception as _e:
        logging.warning(f"follow_sop detail: normalize types failed: {_e}")

    # 컬럼 타입 정규화 - 공통 함수 사용 (DB의 잘못된 타입도 자동 수정)
    dynamic_columns = normalize_column_types(dynamic_columns)

    # 기본정보 필드 추가 (work_req_no, created_at 하드코딩)
    basic_fields = [
        {'column_key': 'work_req_no', 'column_name': '점검번호', 'column_type': 'text',
         'is_required': 1, 'is_readonly': 1, 'tab': 'basic_info'},
        {'column_key': 'created_at', 'column_name': '등록일', 'column_type': 'text',
         'is_required': 0, 'is_readonly': 1, 'tab': 'basic_info'}
    ]

    # dynamic_columns에서 work_req_no와 created_at 완전히 제거
    dynamic_columns = [col for col in dynamic_columns
                      if col.get('column_key') not in ['work_req_no', 'created_at']]

    # basic_info 섹션의 dynamic_columns 추가
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

    # 첨부파일 정보 가져오기
    attachments = []
    try:
        from board_services import AttachmentService
        attachment_service = AttachmentService('follow_sop', DB_PATH, conn)
        attachments = attachment_service.list(work_req_no)
        logging.info(f"[DEBUG] Loaded {len(attachments)} attachments for {work_req_no}")
    except Exception as e:
        logging.error(f"첨부파일 조회 오류: {e}")
        attachments = []

    conn.close()

    # 드롭다운 옵션 로드
    basic_options = {}
    try:
        from app import get_dropdown_options_for_display as _get_opts
        for col in dynamic_columns:
            if col.get('column_type') == 'dropdown':
                col_key = col.get('column_key')
                if col_key:
                    opts = _get_opts('follow_sop', col_key)
                    if opts:
                        basic_options[col_key] = opts
    except Exception as e:
        logging.error(f"Failed to load dropdown options: {e}")

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
                         basic_options=basic_options,  # 드롭다운 옵션 추가
                         attachments=attachments,  # 첨부파일 데이터 추가
                         is_popup=is_popup,
                         menu=MENU_CONFIG)

@app.route('/register-follow-sop', methods=['POST'])
def register_follow_sop():
    """새 Follow SOP 등록"""
    conn = None
    try:
        import json
        from timezone_config import get_korean_time_str, get_korean_time
        from db.upsert import safe_upsert
        from section_service import SectionConfigService

        conn = get_db_connection()
        cursor = conn.cursor()

        # 섹션 정보 동적으로 가져오기
        section_service = SectionConfigService('follow_sop', DB_PATH)
        sections = section_service.get_sections()

        # 섹션이 없으면 기본값 사용 (하위 호환성)
        if not sections:
            sections = [
                {'section_key': 'basic_info'},
                {'section_key': 'work_info'},
                {'section_key': 'additional'}
            ]

        # 모든 필드를 모을 딕셔너리
        all_fields = {}

        # 각 섹션별로 데이터 수집
        for section in sections:
            section_key = section['section_key']
            section_data_str = request.form.get(section_key, '{}')
            logging.info(f"[FS REGISTER DEBUG] 섹션 {section_key} raw: {section_data_str[:500]}")
            try:
                section_data = json.loads(section_data_str)
                all_fields.update(section_data)
                logging.info(f"[FS REGISTER] 섹션 {section_key} 데이터: {section_data}")
                # 실제 값 확인
                for k, v in section_data.items():
                    if v and v not in ('', [], None):
                        logging.info(f"  -> {k}: {str(v)[:100]}")
            except Exception as e:
                logging.warning(f"[FS REGISTER] 섹션 {section_key} 파싱 실패: {e}")

        # 하위 호환성: custom_data가 있으면 병합
        custom_data_raw = request.form.get('custom_data', '{}')
        try:
            # PostgreSQL JSONB는 이미 dict로 반환됨
            if isinstance(custom_data_raw, dict):
                custom_data_compat = custom_data_raw
            else:
                custom_data_compat = json.loads(custom_data_raw) if custom_data_raw else {}
            if custom_data_compat:
                all_fields.update(custom_data_compat)
                logging.info(f"[FS REGISTER] custom_data 병합: {custom_data_compat}")
        except Exception:
            pass

        # 최종 custom_data
        custom_data = all_fields

        # created_at 기준으로 work_req_no 생성 (FS + yyMMddhhmm + 카운터)
        from id_generator import generate_followsop_number
        created_at_dt = get_korean_time()
        work_req_no = generate_followsop_number(DB_PATH, created_at_dt)

        # detailed_content 가져오기
        detailed_content = request.form.get('detailed_content', '')
        logging.info(f"[FS REGISTER] detailed_content 길이: {len(detailed_content)}")

        # 첨부파일 데이터 (accident와 동일하게 pyjson 사용)
        attachment_data = pyjson.loads(request.form.get('attachment_data', '[]'))

        files = request.files.getlist('files')
        logging.info(f"[FS REGISTER] 첨부파일 개수: {len(files)}")

        # custom_data를 JSON 문자열로 변환
        if isinstance(custom_data, dict):
            custom_data_json = json.dumps(custom_data, ensure_ascii=False)
        else:
            custom_data_json = custom_data

        # Follow SOP 등록 - 메인 테이블로 저장 (detailed_content 제외)
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

        # Details 테이블 저장 (단일 경로)
        try:
            from db.upsert import safe_upsert as _su
            _su(conn, 'follow_sop_details', {
                'work_req_no': work_req_no,
                'detailed_content': detailed_content,
                'updated_at': None
            })
            logging.info("[FS REGISTER] details 테이블에도 저장 완료")
        except Exception as _e_det:
            logging.warning(f"[FS REGISTER] details upsert warning: {_e_det}")

        # 첨부파일 처리 (Safety-Instruction 방식으로 변경)
        if files:
            # CREATE TABLE 제거 - 테이블은 이미 존재함

            import os
            from werkzeug.utils import secure_filename

            upload_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads', 'follow_sop')
            os.makedirs(upload_folder, exist_ok=True)

            for i, file in enumerate(files):
                if file and file.filename:
                    filename = secure_filename(file.filename)
                    timestamp = get_korean_time().strftime('%Y%m%d_%H%M%S')
                    unique_filename = f"{work_req_no}_{timestamp}_{filename}".replace('-', '_')
                    file_path = os.path.join(upload_folder, unique_filename)

                    file.save(file_path)

                    # 첨부파일 정보 저장
                    description = attachment_data[i]['description'] if i < len(attachment_data) else ''
                    cursor.execute("""
                        INSERT INTO follow_sop_attachments (work_req_no, file_name, file_path, file_size, description)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (work_req_no, filename, file_path, os.path.getsize(file_path), description))
                    logging.info(f"[FS REGISTER] 첨부파일 저장: {filename}")

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
            # PostgreSQL JSONB는 이미 dict로 반환됨
            if isinstance(custom_data, dict):
                custom_data_dict = custom_data
            else:
                custom_data_dict = json.loads(custom_data) if custom_data and custom_data != '{}' else {}
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
            SET custom_data = %s, updated_by = %s
            WHERE work_req_no = %s
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
        if _first(cursor.fetchone(), 0) == 0:
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
    # 링크드/팝업 타입 보정
    try:
        all_keys = {c.get('column_key') for c in dynamic_columns if c.get('column_key')}
        suffixes = ['_id','_dept','_department','_department_code','_bizno','_company_bizno','_code','_company']
        def base_key_of(k: str) -> str:
            if not isinstance(k, str):
                return ''
            for s in suffixes:
                if k.endswith(s):
                    return k[:-len(s)]
            return k
        def infer_group(bk: str) -> str:
            if not bk:
                return ''
            variants = [bk, bk+'d']
            if any(((v+'_company_bizno') in all_keys) or ((v+'_bizno') in all_keys) for v in variants):
                return 'company'
            if any(((v+'_dept') in all_keys) or ((v+'_department') in all_keys) or ((v+'_department_code') in all_keys) for v in variants):
                return 'department'
            if any(((v+'_id') in all_keys) for v in variants):
                return 'person'
            if any(((v+'_company') in all_keys) for v in variants):
                return 'contractor'
            return ''
        popup_map = {'person':'popup_person','company':'popup_company','department':'popup_department','contractor':'popup_contractor'}
        for col in dynamic_columns:
            ck = col.get('column_key') or ''
            bk = base_key_of(ck)
            grp = infer_group(bk)
            # dept 관련은 별도 처리 유지
            if ck.endswith(('_dept', '_department', '_department_code')):
                col['column_type'] = 'linked_dept'
                continue
            # 나머지 linked 필드는 determine_linked_type 사용
            if (ck.endswith('_id') or ck.endswith('_bizno') or
                ck.endswith('_company') or ck.endswith('_company_bizno')):
                col['column_type'] = determine_linked_type(col)
                continue
            if grp and ck == bk:
                ct = col.get('column_type')
                if not ct or ct in ('text','popup','table','table_select'):
                    col['column_type'] = popup_map.get(grp, ct)
                col['input_type'] = col.get('input_type') or 'table'
    except Exception as _e:
        logging.warning(f"full_process register/detail: normalize types failed: {_e}")

    # 컬럼 타입 정규화 - 공통 함수 사용 (DB의 잘못된 타입도 자동 수정)
    dynamic_columns = normalize_column_types(dynamic_columns)

    # 섹션별로 컬럼 분류
    section_columns = {}
    for section in sections:
        section_columns[section['section_key']] = [
            col for col in dynamic_columns if col.get('tab') == section['section_key']
        ]

    # 메인 목록 표시용 컬럼: 채점(JSON) → 개별 가상 컬럼으로 확장 + 총점(그대로)
    display_columns = []
    try:
        import json as _json
        def _expand_scoring_columns(_col):
            sc = _col.get('scoring_config')
            if sc and isinstance(sc, str):
                try: sc = _json.loads(sc)
                except Exception: sc = {}
            items = (sc or {}).get('items') or []
            out = []
            for it in items:
                iid = it.get('id')
                label = it.get('label') or iid
                if not iid:
                    continue
                out.append({
                    'column_key': f"{_col.get('column_key')}__{iid}",
                    'column_name': f"{_col.get('column_name', _col.get('column_key'))} - {label}",
                    'column_type': 'number',
                    'input_type': 'number_integer',
                    'is_active': 1,
                    'is_deleted': 0,
                    'tab': _col.get('tab'),
                    '_virtual': 1,
                    '_source_scoring_key': _col.get('column_key'),
                    '_source_item_id': iid
                })
            return out
        excluded_keys = {'detailed_content', 'violation_content', 'fullprocess_number', 'created_at'}
        for col in dynamic_columns:
            ck = col.get('column_key')
            if not ck or ck in excluded_keys:
                continue
            if col.get('column_type') == 'scoring':
                display_columns.extend(_expand_scoring_columns(col))
            else:
                display_columns.append(col)
        # 채점/총점 목록
        scoring_cols = [dict(c) for c in dynamic_columns if dict(c).get('column_type') == 'scoring']
        score_total_cols = [dict(c) for c in dynamic_columns if dict(c).get('column_type') == 'score_total']
    except Exception as _e:
        scoring_cols, score_total_cols = [], []
        logging.warning(f"[FULL_PROCESS] display_columns build failed: {_e}")
    
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
            where_clauses.append("(JSON_EXTRACT(p.custom_data, '$.company_name') LIKE %s OR JSON_EXTRACT(p.custom_data, '$.company_1cha') LIKE %s)")
        query_params.extend([f"%{company_name}%", f"%{company_name}%"])
    
    if business_number:
        search_params['business_number'] = business_number
        # 호환: business_number 또는 company_1cha_bizno 키 모두 검색 (Postgres/SQLite 분기)
        if hasattr(conn, 'is_postgres') and conn.is_postgres:
            where_clauses.append("((p.custom_data->>'business_number') ILIKE %s OR (p.custom_data->>'company_1cha_bizno') ILIKE %s)")
        else:
            where_clauses.append("(JSON_EXTRACT(p.custom_data, '$.business_number') LIKE %s OR JSON_EXTRACT(p.custom_data, '$.company_1cha_bizno') LIKE %s)")
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
            exists = bool(_first(cursor.fetchone(), 0))
        else:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='full_process_cache'")
            exists = cursor.fetchone() is not None
        if exists:
            cursor.execute("SELECT COUNT(*) FROM full_process_cache")
            use_cache = (_first(cursor.fetchone(), 0) > 0)
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
    total_count = _first(cursor.fetchone(), 0)
    
    # 데이터 조회
    query = f"""
        SELECT p.* 
        FROM {table_name} p
        WHERE {where_sql}
        ORDER BY p.created_at DESC
        LIMIT %s OFFSET %s
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
                # PostgreSQL JSONB는 이미 dict로 반환됨
                if isinstance(raw, dict):
                    custom_data = raw
                else:
                    custom_data = json.loads(raw) if isinstance(raw, str) and raw else {}
            except Exception as e:
                logging.error(f"custom_data 파싱 오류: {e}")
                custom_data = {}
            if isinstance(custom_data, dict):
                item.update(custom_data)
            # 채점 항목을 개별 키로 평탄화
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
                            item[f"{src}__{iid}"] = group_obj.get(iid, 0)
            except Exception as _e:
                logging.error(f"[FULL_PROCESS] scoring flatten error: {_e}")
            # 총점 계산 (include_keys 우선)
            try:
                for stc in score_total_cols:
                    conf = stc.get('scoring_config')
                    if conf and isinstance(conf, str):
                        try: conf = _json.loads(conf)
                        except Exception: conf = {}
                    base = (conf or {}).get('base_score', 100)
                    total = base
                    include_keys = (conf or {}).get('include_keys') or []
                    if include_keys:
                        for key in include_keys:
                            sc_col = next((c for c in scoring_cols if c.get('column_key') == key), None)
                            if not sc_col:
                                continue
                            sconf = sc_col.get('scoring_config')
                            if sconf and isinstance(sconf, str):
                                try: sconf = _json.loads(sconf)
                                except Exception: sconf = {}
                            items_cfg = (sconf or {}).get('items') or []
                            group_obj = custom_data.get(key, {}) if isinstance(custom_data, dict) else {}
                            if isinstance(group_obj, str):
                                try: group_obj = _json.loads(group_obj)
                                except Exception: group_obj = {}
                            for it in items_cfg:
                                iid = it.get('id')
                                delta = float(it.get('per_unit_delta') or 0)
                                cnt = 0
                                if isinstance(group_obj, dict) and iid in group_obj:
                                    try: cnt = int(group_obj.get(iid) or 0)
                                    except Exception: cnt = 0
                                total += cnt * delta
                    else:
                        # 하위호환: total_key 그룹 방식
                        total_key = (conf or {}).get('total_key') or 'default'
                        for sc_col in scoring_cols:
                            sconf = sc_col.get('scoring_config')
                            if sconf and isinstance(sconf, str):
                                try: sconf = _json.loads(sconf)
                                except Exception: sconf = {}
                            if ((sconf or {}).get('total_key') or 'default') != total_key:
                                continue
                            items_cfg = (sconf or {}).get('items') or []
                            group_obj = custom_data.get(sc_col.get('column_key'), {}) if isinstance(custom_data, dict) else {}
                            if isinstance(group_obj, str):
                                try: group_obj = _json.loads(group_obj)
                                except Exception: group_obj = {}
                            for it in items_cfg:
                                iid = it.get('id')
                                delta = float(it.get('per_unit_delta') or 0)
                                cnt = 0
                                if isinstance(group_obj, dict) and iid in group_obj:
                                    try: cnt = int(group_obj.get(iid) or 0)
                                    except Exception: cnt = 0
                                total += cnt * delta
                    item[stc.get('column_key')] = total
            except Exception as _e:
                logging.error(f"[FULL_PROCESS] score_total compute error: {_e}")
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
                         display_columns=display_columns,
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

    # basic_info의 dynamic_columns 추가 (fullprocess_number, created_at 제외)
    basic_info_dynamic = [col for col in dynamic_columns
                         if col.get('tab') == 'basic_info'
                         and col.get('column_key') not in ['fullprocess_number', 'created_at']]
    basic_fields.extend(basic_info_dynamic)

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
    
    # 드롭다운 옵션 로드
    basic_options = {}
    try:
        from app import get_dropdown_options_for_display as _get_opts
        for col in dynamic_columns:
            if col.get('column_type') == 'dropdown':
                col_key = col.get('column_key')
                if col_key:
                    opts = _get_opts('full_process', col_key)
                    if opts:
                        basic_options[col_key] = opts
    except Exception as e:
        logging.error(f"Failed to load dropdown options: {e}")

    # 현재 날짜 추가 (한국 시간)
    from timezone_config import get_korean_time
    today_date = get_korean_time().strftime('%Y-%m-%d')

    return render_template('full-process-register.html',
                         dynamic_columns=dynamic_columns,
                         sections=sections,
                         section_columns=section_columns,  # 중요! 이것이 누락되어 있었음
                         basic_options=basic_options,  # 드롭다운 옵션 추가
                         today_date=today_date,  # 오늘 날짜 추가
                         is_popup=is_popup,
                         menu=MENU_CONFIG)

@app.route("/full-process-detail/<fullprocess_number>")
def full_process_detail(fullprocess_number):
    """Full Process 상세정보 페이지"""
    import json
    logging.info(f"Full Process 상세 정보 조회: {fullprocess_number}")

    # 테이블 존재 여부를 먼저 확인
    conn = get_db_connection()
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
    
    # Full Process 정보 조회 - 필요한 모든 컬럼 명시 (follow-sop 방식)
    process = {}

    try:
        # 테이블의 모든 컬럼 이름 가져오기
        if hasattr(conn, 'is_postgres') and conn.is_postgres:
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'full_process'
                ORDER BY ordinal_position
            """)
            columns = [row[0] for row in cursor.fetchall()]
        else:
            # SQLite는 지원하지 않음 - PostgreSQL만 사용
            columns = []

        # 동적으로 SELECT 쿼리 생성
        select_columns = ', '.join(columns)
        cursor.execute(f"""
            SELECT {select_columns}
            FROM full_process
            WHERE fullprocess_number = %s AND (is_deleted = 0 OR is_deleted IS NULL)
        """, (fullprocess_number,))

        process_row = cursor.fetchone()

        if process_row:
            # 컬럼 이름과 값을 매핑하여 딕셔너리 생성
            process = {columns[i]: process_row[i] for i in range(len(columns))}
            logging.info(f"[DEBUG] Loaded process data with columns: {list(process.keys())}")
    except Exception as e:
        logging.error(f"full_process 조회 오류: {e}")

    if not process:
        conn.close()
        return "Full Process를 찾을 수 없습니다.", 404
    
    # 삭제 - 이 부분은 아래에서 처리함
    
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

    # 섹션별 컬럼 정보 가져오기 (섹션 로드를 먼저 해야 함)
    from section_service import SectionConfigService
    section_service = SectionConfigService('full_process', DB_PATH)
    sections = section_service.get_sections()

    # full_process는 follow_sop와 같이 custom_data에 모든 데이터가 저장됨
    # 별도의 섹션 컬럼이 없으므로 섹션별 데이터 병합은 불필요
    section_data = {}
    logging.info(f"[DEBUG] All data merged from custom_data: {list(custom_data.keys())}")
    
    # full_process_details 테이블에서 detailed_content 조회 (follow_sop와 동일한 방식)
    try:
        cursor.execute("""
            SELECT detailed_content 
            FROM full_process_details 
            WHERE fullprocess_number = %s
        """, (fullprocess_number,))
        detail_row = cursor.fetchone()
        if detail_row and detail_row[0]:
            process['detailed_content'] = detail_row[0]
            logging.info(f"Loaded detailed_content from full_process_details: {len(detail_row[0])} chars")
        else:
            # 기존 custom_data에서 읽기 (하위 호환성)
            if 'detailed_content' not in process:
                process['detailed_content'] = ''
    except Exception as e:
        logging.warning(f"Failed to load from full_process_details: {e}")
        # 기존 custom_data에서 읽기 (하위 호환성)
        if 'detailed_content' not in process:
            process['detailed_content'] = ''
    
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

    # dynamic_columns에서 fullprocess_number와 created_at 완전히 제거
    dynamic_columns = [col for col in dynamic_columns
                      if col.get('column_key') not in ['fullprocess_number', 'created_at']]

    # basic_info 섹션의 dynamic_columns 추가
    basic_info_dynamic = [col for col in dynamic_columns if col.get('tab') == 'basic_info']
    basic_fields.extend(basic_info_dynamic)

    # 섹션별로 컬럼 분류
    section_columns = {'basic_info': basic_fields}
    for section in sections:
        if section['section_key'] != 'basic_info':
            section_columns[section['section_key']] = [
                col for col in dynamic_columns if col.get('tab') == section['section_key']
            ]

    # 드롭다운 옵션 로드
    basic_options = {}
    try:
        from app import get_dropdown_options_for_display as _get_opts
        for col in dynamic_columns:
            if col.get('column_type') == 'dropdown':
                col_key = col.get('column_key')
                if col_key:
                    opts = _get_opts('full_process', col_key)
                    if opts:
                        basic_options[col_key] = opts
    except Exception as e:
        logging.error(f"Failed to load dropdown options: {e}")

    # 첨부파일 정보 가져오기 - AttachmentService 사용 (accident와 동일)
    attachments = []
    try:
        from board_services import AttachmentService
        attachment_service = AttachmentService('full_process', DB_PATH, conn)
        attachments = attachment_service.list(fullprocess_number)
        logging.info(f"[DEBUG] Loaded {len(attachments)} attachments for {fullprocess_number}")
    except Exception as e:
        logging.error(f"첨부파일 조회 오류: {e}")
        attachments = []

    # 팝업 여부 확인
    is_popup = request.args.get('popup') == '1'

    # 전역 키(활성 컬럼) 전달
    all_keys = [c.get('column_key') for c in dynamic_columns if c.get('column_key')]

    # 디버깅: 템플릿에 전달되는 데이터 확인
    logging.info(f"[TEMPLATE DEBUG] process keys: {list(process.keys())}")
    logging.info(f"[TEMPLATE DEBUG] custom_data keys: {list(custom_data.keys())}")
    logging.info(f"[TEMPLATE DEBUG] issue_date in process: {process.get('issue_date')}")
    logging.info(f"[TEMPLATE DEBUG] department in process: {process.get('department')}")
    logging.info(f"[TEMPLATE DEBUG] manager in process: {process.get('manager')}")

    # 외부 scoring 데이터 매핑 적용
    external_scoring_data = None
    try:
        from scoring_external_service import get_scoring_data_for_template
        scoring_template_data = get_scoring_data_for_template(cursor, fullprocess_number)
        external_scoring_data = scoring_template_data.get('scoring_columns', [])
        logging.info(f"[SCORING] External scoring data loaded: {len(external_scoring_data)} columns")
    except Exception as e:
        logging.warning(f"[SCORING] Failed to load external scoring data: {e}")

    # DB 연결 닫기 (AttachmentService 사용 후)
    conn.close()

    return render_template('full-process-detail.html',
                         process=process,
                         instruction=process,  # 템플릿 호환용 별칭
                         custom_data=custom_data,
                         section_data=section_data,  # 섹션별 데이터 추가
                         sections=sections,
                         section_columns=section_columns,
                         all_column_keys=all_keys,
                         basic_options=basic_options,  # 드롭다운 옵션 추가
                         attachments=attachments,  # 첨부파일 데이터 추가
                         external_scoring_data=external_scoring_data,  # 외부 scoring 데이터 추가
                         is_popup=is_popup,
                         menu=MENU_CONFIG)

@app.route('/register-full-process', methods=['POST'])
def register_full_process():
    """새 Full Process 등록"""
    conn = None
    try:
        import json
        from timezone_config import get_korean_time_str, get_korean_time
        from db.upsert import safe_upsert
        from section_service import SectionConfigService

        conn = get_db_connection()
        cursor = conn.cursor()

        # 섹션 정보 동적으로 가져오기
        section_service = SectionConfigService('full_process', DB_PATH)
        sections = section_service.get_sections()

        # 섹션이 없으면 기본값 사용 (하위 호환성)
        if not sections:
            sections = [
                {'section_key': 'basic_info'},
                {'section_key': 'process_info'},
                {'section_key': 'additional'}
            ]

        # 모든 필드를 모을 딕셔너리
        all_fields = {}

        # 각 섹션별로 데이터 수집
        for section in sections:
            section_key = section['section_key']
            section_data_str = request.form.get(section_key, '{}')
            logging.info(f"[FP REGISTER DEBUG] 섹션 {section_key} raw: {section_data_str[:500]}")
            try:
                section_data = json.loads(section_data_str)
                all_fields.update(section_data)
                logging.info(f"[FP REGISTER] 섹션 {section_key} 데이터: {section_data}")
                # 실제 값 확인
                for k, v in section_data.items():
                    if v and v not in ('', [], None):
                        logging.info(f"  -> {k}: {str(v)[:100]}")
            except Exception as e:
                logging.warning(f"[FP REGISTER] 섹션 {section_key} 파싱 실패: {e}")

        # 하위 호환성: custom_data가 있으면 병합
        custom_data_raw = request.form.get('custom_data', '{}')
        try:
            # PostgreSQL JSONB는 이미 dict로 반환됨
            if isinstance(custom_data_raw, dict):
                custom_data_compat = custom_data_raw
            else:
                custom_data_compat = json.loads(custom_data_raw) if custom_data_raw else {}
            if custom_data_compat:
                all_fields.update(custom_data_compat)
                logging.info(f"[FP REGISTER] custom_data 병합: {custom_data_compat}")
        except Exception:
            pass

        # 최종 custom_data
        custom_data = all_fields

        # created_at 기준으로 fullprocess_number 생성 (FP + yyMMddhhmm + 카운터)
        from id_generator import generate_fullprocess_number
        created_at_dt = get_korean_time()
        fullprocess_number = generate_fullprocess_number(DB_PATH, created_at_dt)

        # detailed_content 가져오기
        detailed_content = request.form.get('detailed_content', '')
        logging.info(f"[FP REGISTER] detailed_content 길이: {len(detailed_content)}")

        # 첨부파일 데이터 (accident와 동일하게 pyjson 사용)
        attachment_data = pyjson.loads(request.form.get('attachment_data', '[]'))

        files = request.files.getlist('files')
        logging.info(f"[FP REGISTER] 첨부파일 개수: {len(files)}")

        # custom_data를 JSON 문자열로 변환
        if isinstance(custom_data, dict):
            custom_data_json = json.dumps(custom_data, ensure_ascii=False)
        else:
            custom_data_json = custom_data

        # Full Process 등록 - 메인 테이블 저장 (detailed_content 제외)
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

        # Details 테이블 저장 (단일 경로)
        try:
            from db.upsert import safe_upsert as _su
            _su(conn, 'full_process_details', {
                'fullprocess_number': fullprocess_number,
                'detailed_content': detailed_content,
                'updated_at': None
            }, conflict_cols=['fullprocess_number'], update_cols=['detailed_content', 'updated_at'])
            logging.info("[FP REGISTER] details 테이블에도 저장 완료")
        except Exception as _e_det:
            logging.warning(f"[FP REGISTER] details upsert warning: {_e_det}")

        # 첨부파일 처리 (Safety-Instruction 방식으로 변경)
        if files:
            # CREATE TABLE 제거 - 테이블은 이미 존재함

            import os
            from werkzeug.utils import secure_filename

            upload_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads', 'full_process')
            os.makedirs(upload_folder, exist_ok=True)

            for i, file in enumerate(files):
                if file and file.filename:
                    filename = secure_filename(file.filename)
                    timestamp = get_korean_time().strftime('%Y%m%d_%H%M%S')
                    unique_filename = f"{fullprocess_number}_{timestamp}_{filename}".replace('-', '_')
                    file_path = os.path.join(upload_folder, unique_filename)

                    file.save(file_path)

                    # 첨부파일 정보 저장
                    description = attachment_data[i]['description'] if i < len(attachment_data) else ''
                    cursor.execute("""
                        INSERT INTO full_process_attachments (fullprocess_number, file_name, file_path, file_size, description)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (fullprocess_number, filename, file_path, os.path.getsize(file_path), description))
                    logging.info(f"[FP REGISTER] 첨부파일 저장: {filename}")

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
            # PostgreSQL JSONB는 이미 dict로 반환됨
            if isinstance(custom_data, dict):
                custom_data_dict = custom_data
            else:
                custom_data_dict = json.loads(custom_data) if custom_data and custom_data != '{}' else {}
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
            SET custom_data = %s, updated_by = %s
            WHERE fullprocess_number = %s
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
