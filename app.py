import os
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.serving import run_simple
from werkzeug.utils import secure_filename
from config.menu import MENU_CONFIG
from database_config import db_config, partner_manager
import sqlite3
import math

def generate_manual_accident_number(cursor):
    """수기입력 사고번호 자동 생성 (ACCYYMMDD00 형식)"""
    today = datetime.now()
    date_part = today.strftime('%y%m%d')  # 240822
    
    # 오늘 날짜의 마지막 번호 조회
    cursor.execute("""
        SELECT accident_number 
        FROM accidents_cache 
        WHERE accident_number LIKE ?
        ORDER BY accident_number DESC
        LIMIT 1
    """, (f'ACC{date_part}%',))
    
    last = cursor.fetchone()
    if last:
        # ACC24082203 → 04
        seq = int(last[0][-2:]) + 1
    else:
        seq = 1
    
    return f'ACC{date_part}{seq:02d}'

app = Flask(__name__, static_folder='static')

# 설정 파일에서 환경 설정 로드
app.secret_key = db_config.config.get('DEFAULT', 'SECRET_KEY')
app.debug = db_config.config.getboolean('DEFAULT', 'DEBUG')

# Jinja2 필터 추가 (JSON 파싱용)
import json
def from_json_filter(value):
    try:
        return json.loads(value) if value else []
    except:
        return []
app.jinja_env.filters['from_json'] = from_json_filter

DB_PATH = db_config.local_db_path
PASSWORD = db_config.config.get('DEFAULT', 'EDIT_PASSWORD')
UPLOAD_FOLDER = db_config.config.get('DEFAULT', 'UPLOAD_FOLDER')

# 로깅 설정
logging.basicConfig(
    level=getattr(logging, db_config.config.get('LOGGING', 'LOG_LEVEL')),
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(db_config.config.get('LOGGING', 'LOG_FILE')),
        logging.StreamHandler()
    ]
)

# Flask 템플릿 자동 리로드 설정
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

def init_db():
    """기본 설정 초기화 및 데이터 동기화"""
    # 로컬 DB 테이블 초기화 (partner_manager에서 처리)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 페이지 테이블만 여기서 관리
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            title TEXT,
            content TEXT
        )
    ''')
    
    # 메뉴 설정에서 페이지 자동 생성
    for category in MENU_CONFIG:
        for submenu in category['submenu']:
            cursor.execute("SELECT COUNT(*) FROM pages WHERE url = ?", (submenu['url'],))
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    "INSERT INTO pages (url, title, content) VALUES (?, ?, ?)",
                    (submenu['url'], submenu['title'], 
                     f"<h1>{submenu['title']}</h1><p>이 페이지의 내용을 편집하세요.</p>")
                )
    
    conn.commit()
    conn.close()
    
    # 외부 DB 연동이 활성화된 경우 동기화 시도
    if db_config.external_db_enabled:
        sync_success = True
        
        # 1. 협력사 데이터 동기화
        try:
            logging.info("협력사 데이터 동기화 시작...")
            if not partner_manager.sync_partners_from_external_db():
                logging.warning("협력사 데이터 동기화 실패")
                sync_success = False
            else:
                logging.info("협력사 데이터 동기화 완료")
        except Exception as e:
            logging.error(f"협력사 동기화 중 오류: {e}")
            sync_success = False
        
        # 2. 사고 데이터 동기화 (ACCIDENTS_QUERY가 있을 때만)
        try:
            if partner_manager.config.has_option('SQL_QUERIES', 'ACCIDENTS_QUERY'):
                logging.info("사고 데이터 동기화 시작...")
                if partner_manager.sync_accidents_from_external_db():
                    logging.info("사고 데이터 동기화 완료")
                else:
                    logging.warning("사고 데이터 동기화 실패 - 더미 데이터 사용")
            else:
                logging.info("ACCIDENTS_QUERY 미설정 - 사고 데이터는 더미 사용")
        except Exception as e:
            logging.warning(f"사고 동기화 중 오류: {e} - 더미 데이터 사용")
        
        # 동기화 실패 시 샘플 데이터 사용
        if not sync_success:
            logging.info("일부 동기화 실패 - 샘플 데이터로 대체")
            init_sample_data()
    else:
        # 외부 DB가 비활성화된 경우 샘플 데이터 생성
        init_sample_data()

def init_sample_data():
    """외부 DB 없을 때 샘플 데이터 생성"""
    conn = partner_manager.db_config.get_sqlite_connection()
    cursor = conn.cursor()
    
    # 이미 데이터가 있는지 확인
    try:
        cursor.execute("SELECT COUNT(*) FROM partners_cache")
        count = cursor.fetchone()[0]
        
        # permanent_workers 컬럼이 있는지 확인
        cursor.execute("PRAGMA table_info(partners_cache)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # permanent_workers 컬럼이 없으면 기존 데이터에 랜덤값 추가
        if 'permanent_workers' not in columns:
            logging.info("permanent_workers 컬럼이 없어서 기존 데이터에 값을 추가합니다")
            import random
            cursor.execute("SELECT business_number FROM partners_cache")
            existing_partners = cursor.fetchall()
            for partner in existing_partners:
                permanent_workers = random.randint(5, 500)
                cursor.execute("UPDATE partners_cache SET permanent_workers = ? WHERE business_number = ?", 
                             (permanent_workers, partner[0]))
            conn.commit()
            logging.info(f"기존 {len(existing_partners)}개 협력사에 상시근로자 데이터 추가 완료")
        
        # 데이터가 충분히 있으면 종료
        if count > 0:
            conn.close()
            return
    except Exception as e:
        logging.warning(f"데이터 확인 중 오류: {e}")
    
    logging.info("샘플 데이터 생성 중...")
    
    import random
    random.seed(42)  # 고정된 시드
    
    # 샘플 데이터 생성 로직 (기존과 동일)
    base_companies = [
        '삼성전자', 'LG전자', '현대자동차', 'SK하이닉스', 'POSCO홀딩스',
        '네이버', '카카오', '신한금융지주', '한국전력공사', 'KT',
        'LG화학', '현대중공업', '한화솔루션', 'SK텔레콤', '기아',
        '롯데케미칼', 'S-Oil', 'GS칼텍스', '두산에너빌리티', 'HD현대중공업'
    ]
    
    business_types_data = {
        '제조업': ['전자제품', '자동차', '기계', '화학', '섬유', '식품', '의약품', '철강', '플라스틱', '기타제조'],
        '건설업': ['건축공사', '토목공사', '전기공사', '통신공사', '설비공사', '조경공사', '인테리어', '기타건설'],
        'IT업': ['소프트웨어개발', '시스템통합', '데이터베이스', '네트워크', '보안', '게임개발', '웹개발', '모바일앱'],
        '서비스업': ['컨설팅', '교육', '의료', '법률', '회계', '인사', '마케팅', '디자인', '청소', '보안서비스'],
        '운수업': ['육상운송', '해상운송', '항공운송', '물류', '창고', '택배', '렌터카', '기타운송'],
        '유통업': ['도매', '소매', '전자상거래', '백화점', '마트', '편의점', '온라인쇼핑몰', '기타유통'],
        '금융업': ['은행', '증권', '보험', '카드', '리스', '투자', '자산관리', '핀테크'],
        '에너지업': ['전력', '가스', '석유', '신재생에너지', '원자력', '석탄', '기타에너지']
    }
    
    business_types = list(business_types_data.keys())
    certifications = ['ISO 9001', 'ISO 14001', 'ISO 45001', 'KS인증', 'GMP', 'HACCP', '없음']
    safety_ratings = ['A등급', 'B등급', 'C등급', 'D등급']
    products = ['전자부품', '자동차부품', '화학원료', '기계부품', '소프트웨어', '통신장비', '건설자재', '의료기기', '식품', '기타']
    
    # 203개 샘플 데이터 생성
    for i in range(203):
        if i < 20:
            company_name = f"{base_companies[i % len(base_companies)]}(주)"
            business_number = f"{100 + i:03d}81{random.randint(10000, 99999):05d}"
        else:
            company_name = f"협력업체{i-19:03d}(주)"
            business_number = f"{random.randint(100, 999)}81{random.randint(10000, 99999):05d}"
        
        representative = f"대표자{i+1:03d}"
        permanent_workers = random.randint(5, 500)  # 상시근로자 수 (5명~500명)
        partner_class = random.choice(['-', 'A', 'B', 'C'])
        
        business_type_major = random.choice(business_types)
        minor_count = random.randint(1, 2)
        selected_minors = random.sample(business_types_data[business_type_major], min(minor_count, len(business_types_data[business_type_major])))
        business_type_minor = ', '.join(selected_minors)
        
        hazard_work_flag = random.choice(['O', 'X', ''])  # O: 위험작업, X: 비위험작업, '': 미분류
        address = f"서울특별시 {random.choice(['강남구', '서초구', '송파구', '영등포구', '마포구', '종로구', '중구', '용산구'])} 샘플로{random.randint(1, 999)}"
        average_age = random.randint(25, 55)  # 평균 연령
        annual_revenue = random.randint(1, 1000) * 100000000  # 연매출 (억원 단위)
        transaction_count = random.randint(1, 50)  # 거래 차수
        
        cursor.execute('''
            INSERT INTO partners_cache (
                business_number, company_name, partner_class, business_type_major, 
                business_type_minor, hazard_work_flag, representative, address,
                average_age, annual_revenue, transaction_count, permanent_workers
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            business_number, company_name, partner_class, business_type_major,
            business_type_minor, hazard_work_flag, representative, address,
            average_age, annual_revenue, transaction_count, permanent_workers
        ))
        
        # 일부 협력사에 실제 존재하는 샘플 첨부파일 추가
        if i < 5:  # 처음 5개 협력사에만 추가
            # uploads 폴더에 실제 존재하는 파일들 사용
            real_files = [
                ('sample_for_you_1755663410.xlsx', 'uploads/sample_for_you_1755663410.xlsx', '샘플 엑셀 파일'),
                ('[Quick Guide] DS사업장 내방신청 v.03_1755666638.pdf', 'uploads/[Quick Guide] DS사업장 내방신청 v.03_1755666638.pdf', 'DS사업장 가이드'),
                ('[Quick Guide] 상생협력포털(PCMS) 회원가입 v.02_1755674307.pdf', 'uploads/[Quick Guide] 상생협력포털(PCMS) 회원가입 v.02_1755674307.pdf', 'PCMS 가입 가이드')
            ]
            
            # 하나의 실제 파일만 추가 (확실히 다운로드되도록)
            file_info = real_files[i % len(real_files)]
            file_path = os.path.join(os.getcwd(), file_info[1])
            
            # 파일이 실제로 존재하는지 확인
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                cursor.execute('''
                    INSERT INTO partner_attachments (
                        business_number, file_name, file_path, file_size, description
                    ) VALUES (?, ?, ?, ?, ?)
                ''', (
                    business_number,
                    file_info[0],
                    file_path,  # 전체 경로로 저장
                    file_size,
                    file_info[2]
                ))
    
    conn.commit()
    conn.close()
    logging.info("샘플 데이터 생성 완료")

@app.before_request
def before_request():
    init_db()

@app.route("/")
def index():
    # 대시보드 설정 가져오기 (단순화)
    dashboard_config = {
        'url': db_config.config.get('DASHBOARD', 'DASHBOARD_URL', 
                                   fallback='https://your-dashboard.com'),
        'enabled': db_config.config.getboolean('DASHBOARD', 'DASHBOARD_ENABLED', 
                                              fallback=True)
    }
    return render_template("index.html", menu=MENU_CONFIG, dashboard_config=dashboard_config)

# 개별 라우트들을 catch-all 라우트보다 먼저 정의
@app.route("/partner-standards")
def partner_standards_route():
    """협력사 기준정보 페이지 라우트"""
    return partner_standards()

@app.route("/partner-accident")
def partner_accident_route():
    """협력사 사고 페이지 라우트"""
    return partner_accident()

@app.route("/data-recovery")
def data_recovery():
    """데이터 복구 페이지"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # 삭제된 사고 조회
    deleted_accidents_rows = conn.execute("""
        SELECT * FROM accidents_cache 
        WHERE is_deleted = 1
        ORDER BY accident_date DESC, accident_number DESC
    """).fetchall()
    
    deleted_accidents = [dict(row) for row in deleted_accidents_rows]
    conn.close()
    
    return render_template('data-recovery.html', 
                         deleted_accidents=deleted_accidents,
                         menu=MENU_CONFIG,
                         active_slug='data-recovery')

def partner_standards():
    """협력사 기준정보 페이지"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    # 검색 조건
    filters = {
        'company_name': request.args.get('company_name', '').strip(),
        'business_number': request.args.get('business_number', '').strip(),
        'business_type_major': request.args.get('business_type_major', '').strip(),
        'business_type_minor': request.args.get('business_type_minor', '').strip(),
        'workers_min': request.args.get('workers_min', type=int),
        'workers_max': request.args.get('workers_max', type=int)
    }
    
    # 새로운 데이터 매니저를 통해 협력사 목록 조회
    partners, total_count = partner_manager.get_all_partners(
        page=page, 
        per_page=per_page, 
        filters=filters
    )
    
    # 페이지네이션 정보
    class Pagination:
        def __init__(self, page, per_page, total_count):
            self.page = page
            self.per_page = per_page
            self.total_count = total_count
            self.pages = math.ceil(total_count / per_page)
            self.has_prev = page > 1
            self.prev_num = page - 1 if self.has_prev else None
            self.has_next = page < self.pages
            self.next_num = page + 1 if self.has_next else None
        
        def iter_pages(self, window_size=10):
            # 현재 페이지를 기준으로 10개 페이지 윈도우 생성
            start = ((self.page - 1) // window_size) * window_size + 1
            end = min(start + window_size - 1, self.pages)
            for num in range(start, end + 1):
                yield num
        
        def get_window_info(self, window_size=10):
            # 현재 윈도우의 시작과 끝 페이지
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
    
    pagination = Pagination(page, per_page, total_count)
    
    return render_template('partner-standards.html',
                         partners=partners,
                         total_count=total_count,
                         pagination=pagination,
                         menu=MENU_CONFIG)


def partner_accident():
    """협력사 사고 페이지"""
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    # 검색 조건
    filters = {
        'company_name': request.args.get('company_name', '').strip(),
        'business_number': request.args.get('business_number', '').strip(),
        'accident_date_start': request.args.get('accident_date_start', '').strip(),
        'accident_date_end': request.args.get('accident_date_end', '').strip()
    }
    
    # Phase 1: 동적 컬럼 설정 가져오기
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    dynamic_columns_rows = conn.execute("""
        SELECT * FROM accident_column_config 
        WHERE is_active = 1 
        ORDER BY column_order
    """).fetchall()
    # Row 객체를 dict로 변환
    dynamic_columns = [dict(row) for row in dynamic_columns_rows]
    
    # 드롭다운 컬럼에 대해 코드-값 매핑 정보 추가
    for col in dynamic_columns:
        if col['column_type'] == 'dropdown':
            col['code_mapping'] = get_dropdown_options_for_display(col['column_key'])
    
    # 사고 데이터 조회 (운영 환경 고려)
    import random
    import datetime
    
    # 사고 데이터 조회 - 단순화
    all_accidents = []
    
    
    # 1. 항상 로컬 DB에서 먼저 조회 (등록된 사고)  
    try:
        # accident_datetime 컬럼이 없으면 추가
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(accidents_cache)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'accident_datetime' not in columns:
            cursor.execute("ALTER TABLE accidents_cache ADD COLUMN accident_datetime TEXT")
            # 기존 데이터 업데이트 (날짜와 시간 조합)
            cursor.execute("""
                UPDATE accidents_cache 
                SET accident_datetime = 
                    CASE 
                        WHEN accident_date IS NOT NULL AND accident_time IS NOT NULL 
                        THEN accident_date || ' ' || accident_time
                        WHEN accident_date IS NOT NULL 
                        THEN accident_date || ' 00:00'
                        ELSE datetime('now', 'localtime')
                    END
                WHERE accident_datetime IS NULL
            """)
            conn.commit()
            logging.info("accident_datetime 컬럼 추가 및 기존 데이터 업데이트 완료")
        
        local_accidents_rows = conn.execute("""
            SELECT * FROM accidents_cache 
            WHERE is_deleted = 0 OR is_deleted IS NULL
            ORDER BY 
                CASE 
                    WHEN accident_datetime IS NOT NULL AND accident_datetime != '' 
                    THEN accident_datetime 
                    ELSE COALESCE(accident_date, '1900-01-01') || ' 00:00' 
                END DESC, 
                accident_number DESC
        """).fetchall()
        
        logging.info(f"로컬 DB에서 {len(local_accidents_rows)}개 사고 조회됨")
        
        for row in local_accidents_rows:
            accident = dict(row)
            # ID 확인 및 설정
            if 'id' not in accident or not accident['id']:
                accident['id'] = len(all_accidents) + 1000  # 충돌 방지를 위해 1000부터 시작
            # 필수 필드 채우기
            accident['accident_name'] = accident.get('accident_name') or f"사고_{accident['accident_number']}"
            accident['custom_data'] = accident.get('custom_data', '{}')
            
            # 웹 표시용 필수 필드들 채우기
            accident['accident_grade'] = accident.get('accident_grade') or accident.get('injury_level', '일반')
            accident['accident_type'] = accident.get('accident_type', '기타')
            accident['disaster_type'] = accident.get('disaster_type', '일반사고')
            accident['disaster_form'] = accident.get('disaster_form', '기타')
            accident['workplace'] = accident.get('workplace', '미분류')
            accident['building'] = accident.get('building', '미분류')
            accident['floor'] = accident.get('floor', '미분류')
            accident['detail_location'] = accident.get('detail_location', accident.get('accident_location', '미분류'))
            accident['time'] = accident.get('time', '미분류')
            accident['day_of_week'] = accident.get('day_of_week', '미분류')
            accident['accident_content'] = accident.get('accident_content', accident.get('accident_description', '내용 없음'))
            accident['responsible_company_1'] = accident.get('responsible_company_1', '직접등록')
            accident['responsible_company_1_business_number'] = accident.get('responsible_company_1_business_number', accident.get('business_number', 'DIRECT-ENTRY'))
            accident['responsible_company_2'] = accident.get('responsible_company_2')
            accident['responsible_company_2_business_number'] = accident.get('responsible_company_2_business_number')
            
            all_accidents.append(accident)
        
        logging.info(f"로컬 사고 추가 완료: {len(all_accidents)}개")
    except Exception as e:
        logging.error(f"로컬 사고 데이터 조회 실패: {e}")
        import traceback
        logging.error(traceback.format_exc())
    
    
    # 2. 개발 환경에서는 더미 데이터 추가 (로컬 사고 뒤에)
    if not db_config.external_db_enabled:
        import json
        
        # 더미 데이터를 임시 리스트에 저장
        dummy_accidents = []
        for i in range(50):  # 50개 더미 데이터
            # 사고번호 생성: K + 연월일 + 순서(3자리)
            months = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
            days = [1, 5, 10, 15, 20, 25]
            accident_date_fixed = f'2024-{months[i % 12]:02d}-{days[i % 6]:02d}'
            accident_number = f'K{accident_date_fixed.replace("-", "")}{i+1:03d}'
            
            # 고정된 값들
            grades = ['경미', '중대', '치명']
            types = ['추락', '협착', '절단', '화재']
            disaster_types = ['안전사고', '보건사고']
            disaster_forms = ['낙하', '충돌', '전도']
            days_of_week = ['월', '화', '수', '목', '금', '토', '일']
            
            dummy_accident = {
                'id': i + 1,
                'accident_number': accident_number,
                'accident_name': f'사고사례{i+1:03d}',
                'accident_date': accident_date_fixed,
                'accident_grade': grades[i % 3],
                'accident_type': types[i % 4],
                'disaster_type': disaster_types[i % 2],
                'disaster_form': disaster_forms[i % 3],
                'workplace': f'사업장{(i % 5) + 1}',
                'building': f'건물{(i % 10) + 1}',
                'floor': f'{(i % 20) + 1}층',
                'detail_location': f'상세위치{i+1:03d}',
                'time': f'{9 + (i % 10):02d}:{(i * 5) % 60:02d}',
                'day_of_week': days_of_week[i % 7],
                'accident_content': f'사고내용{i+1}',
                'responsible_company_1': f'협력사{(i % 20) + 1}',
                'responsible_company_1_business_number': f'{1000000000 + i * 11111}',
                'responsible_company_2': f'협력사{(i % 15) + 1}' if i % 3 == 0 else None,
                'responsible_company_2_business_number': f'{2000000000 + i * 22222}' if i % 3 == 0 else None,
            }
            
            # 동적 컬럼 데이터 추가
            custom_data = {}
            for col in dynamic_columns:
                col_key = col['column_key']
                col_type = col['column_type']
                
                if col_type == 'dropdown':
                    options = json.loads(col['dropdown_options']) if col['dropdown_options'] else []
                    custom_data[col_key] = options[i % len(options)] if options else f'{col_key}-값{i+1}'
                elif col_type == 'date':
                    custom_data[col_key] = f'2025-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}'
                elif col_type == 'popup_person':
                    custom_data[col_key] = {'name': f'담당자{i+1}', 'department': f'부서{i % 5 + 1}'}
                elif col_type == 'popup_company':
                    custom_data[col_key] = {'name': f'업체{i+1}', 'business_number': f'{3000000000 + i * 33333}'}
                else:
                    custom_data[col_key] = f'{col["column_name"]}-값{i+1}'
            
            dummy_accident['custom_data'] = json.dumps(custom_data, ensure_ascii=False)
            dummy_accidents.append(dummy_accident)
        
        # 로컬 사고 뒤에 더미 사고 추가
        all_accidents.extend(dummy_accidents)
        
        logging.info(f"더미 데이터 50개 추가됨")
    
    print(f"[DEBUG] 전체 사고 개수: {len(all_accidents)}", flush=True)
    logging.info(f"전체 사고 개수: {len(all_accidents)}")
    
    filtered_accidents = all_accidents
    
    if filters['company_name']:
        filtered_accidents = [a for a in filtered_accidents if filters['company_name'].lower() in a['responsible_company_1'].lower()]
    
    if filters['business_number']:
        filtered_accidents = [a for a in filtered_accidents if filters['business_number'] in str(a['responsible_company_1_business_number'])]
    
    if filters['accident_date_start']:
        filtered_accidents = [a for a in filtered_accidents if a['accident_date'] >= filters['accident_date_start']]
    
    if filters['accident_date_end']:
        filtered_accidents = [a for a in filtered_accidents if a['accident_date'] <= filters['accident_date_end']]
    
    total_count = len(filtered_accidents)
    
    # 페이지네이션
    start = (page - 1) * per_page
    end = start + per_page
    accidents = filtered_accidents[start:end]
    
    
    # 딕셔너리를 객체처럼 사용할 수 있도록 변환
    class DictAsAttr:
        def __init__(self, d):
            for k, v in d.items():
                setattr(self, k, v)
    
    accidents = [DictAsAttr(a) for a in accidents]
    
    # 페이지네이션 정보 (partner_standards와 동일한 클래스 사용)
    class Pagination:
        def __init__(self, page, per_page, total_count):
            self.page = page
            self.per_page = per_page
            self.total_count = total_count
            self.pages = math.ceil(total_count / per_page)
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
    
    pagination = Pagination(page, per_page, total_count)
    
    # DB 연결 닫기
    conn.close()
    
    # 코드를 값으로 변환 (표시용)
    for accident in accidents:
        # DictAsAttr 객체 처리를 위해 hasattr 사용
        if hasattr(accident, 'custom_data') and accident.custom_data:
            try:
                custom_data = json.loads(accident.custom_data)
                for col in dynamic_columns:
                    if col['column_type'] == 'dropdown' and col['column_key'] in custom_data:
                        code = custom_data[col['column_key']]
                        if code:
                            # 코드를 값으로 변환
                            custom_data[col['column_key']] = convert_code_to_value(col['column_key'], code)
                accident.custom_data = json.dumps(custom_data, ensure_ascii=False)
            except Exception as e:
                logging.error(f"코드 변환 오류: {e}")
    
    # 디버깅 로그
    logging.info(f"partner_accident: 전체 {len(all_accidents)}개, 필터링 {total_count}개, 표시 {len(accidents)}개")
    
    return render_template('partner-accident.html',
                         accidents=accidents,
                         total_count=total_count,
                         pagination=pagination,
                         dynamic_columns=dynamic_columns,  # Phase 1: 동적 컬럼 정보 전달
                         menu=MENU_CONFIG)

# 편집 기능 완전 제거 - 심플함을 위해

@app.route("/partner/<business_number>")
@app.route("/partner-detail/<business_number>")
def partner_detail(business_number):
    """협력사 상세정보 페이지"""
    logging.info(f"협력사 상세 정보 조회: {business_number}")
    
    # 새로운 데이터 매니저를 통해 협력사 정보 조회
    partner = partner_manager.get_partner_by_business_number(business_number)
    
    if not partner:
        logging.warning(f"협력사를 찾을 수 없습니다: {business_number}")
        return "협력사 정보를 찾을 수 없습니다.", 404
    
    # 첨부파일 정보 가져오기
    conn = partner_manager.db_config.get_sqlite_connection()
    conn.row_factory = sqlite3.Row
    attachments = conn.execute("""
        SELECT * FROM partner_attachments 
        WHERE business_number = ? 
        ORDER BY upload_date DESC
    """, (business_number,)).fetchall()
    conn.close()
    
    logging.info(f"협력사 {business_number} ({partner['company_name']}) 상세 페이지 로드 - 첨부파일 {len(attachments)}개")
    
    # 팝업 모드인지 확인
    is_popup = request.args.get('popup') == '1'
    
    return render_template('partner-detail.html', 
                         partner=partner, 
                         attachments=attachments,
                         menu=MENU_CONFIG, 
                         is_popup=is_popup,
                         board_type='partner')  # 게시판 타입 전달

@app.route("/accident-detail/<int:accident_id>")
def accident_detail(accident_id):
    """사고 상세정보 페이지"""
    logging.info(f"사고 상세 정보 조회: {accident_id}")
    
    # 더미 데이터에서 해당 사고 찾기 (실제로는 DB에서 조회)
    import random
    
    # 더미 사고 데이터 (partner_accident 함수와 동일한 데이터 생성)
    dummy_accidents = []
    for i in range(50):
        # 사고번호 생성: K + 연월일 + 순서(3자리) - 고정된 값
        months = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
        days = [1, 5, 10, 15, 20, 25]
        accident_date_fixed = f'2024-{months[i % 12]:02d}-{days[i % 6]:02d}'
        accident_number = f'K{accident_date_fixed.replace("-", "")}{i+1:03d}'
        
        # 고정된 값들로 변경
        grades = ['경미', '중대', '치명']
        types = ['추락', '협착', '절단', '화재']
        disaster_types = ['안전사고', '보건사고']
        disaster_forms = ['낙하', '충돌', '전도']
        days_of_week = ['월', '화', '수', '목', '금', '토', '일']
        
        dummy_accidents.append({
            'id': i + 1,
            'accident_number': accident_number,
            'accident_name': f'사고사례{i+1:03d}',
            'accident_date': accident_date_fixed,
            'accident_grade': grades[i % 3],
            'accident_type': types[i % 4],
            'disaster_type': disaster_types[i % 2],
            'disaster_form': disaster_forms[i % 3],
            'workplace': f'사업장{(i % 5) + 1}',
            'building': f'건물{(i % 10) + 1}',
            'floor': f'{(i % 20) + 1}층',
            'detail_location': f'상세위치{i+1:03d}',
            'time': f'{9 + (i % 10):02d}:{(i * 5) % 60:02d}',
            'day_of_week': days_of_week[i % 7],
            'accident_content': f'사고내용{i+1}에 대한 상세 설명입니다.',
            'responsible_company_1': f'협력사{(i % 20) + 1}',
            'responsible_company_1_business_number': f'{1000000000 + i * 11111}',
            'responsible_company_2': f'협력사{(i % 15) + 1}' if i % 3 == 0 else None,
            'responsible_company_2_business_number': f'{2000000000 + i * 22222}' if i % 3 == 0 else None,
        })
    
    # DB에서 실제 사고 데이터 가져오기
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # accidents_cache에서 먼저 찾기
    cursor.execute("""
        SELECT * FROM accidents_cache 
        WHERE id = ? OR accident_number = ?
        LIMIT 1
    """, (accident_id, f'K{accident_id}'))
    
    accident = cursor.fetchone()
    
    # 없으면 더미 데이터에서 찾기
    if not accident:
        for acc in dummy_accidents:
            if acc['id'] == accident_id:
                accident = dict(acc)
                break
    else:
        accident = dict(accident)  # Row를 dict로 변환
    
    if not accident:
        logging.warning(f"사고를 찾을 수 없습니다: {accident_id}")
        conn.close()
        return "사고 정보를 찾을 수 없습니다.", 404
    
    # accident_details 테이블이 존재하는지 먼저 확인
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accident_details (
            accident_number TEXT PRIMARY KEY,
            detailed_content TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # accident_details 테이블에서 상세내용 조회
    cursor.execute("SELECT detailed_content FROM accident_details WHERE accident_number = ?", (accident['accident_number'],))
    detail_row = cursor.fetchone()
    if detail_row:
        accident['detailed_content'] = detail_row['detailed_content']
    else:
        accident['detailed_content'] = ''
    
    # accident_attachments 테이블도 생성
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accident_attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            accident_number TEXT,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 첨부파일 정보 가져오기
    attachments = cursor.execute("""
        SELECT * FROM accident_attachments 
        WHERE accident_number = ? 
        ORDER BY created_at DESC
    """, (accident['accident_number'],)).fetchall()
    
    # Phase 2: 동적 컬럼 설정 가져오기
    dynamic_columns_rows = conn.execute("""
        SELECT * FROM accident_column_config 
        WHERE is_active = 1 
        ORDER BY column_order
    """).fetchall()
    
    # Row 객체를 딕셔너리로 변환
    dynamic_columns = [dict(row) for row in dynamic_columns_rows]
    
    conn.close()
    
    # 드롭다운 컬럼에 대해 코드-값 매핑 적용 (등록 페이지와 동일한 로직)
    for col in dynamic_columns:
        if col['column_type'] == 'dropdown':
            # 코드-값 매핑 방식으로 옵션 가져오기
            code_options = get_dropdown_options_for_display(col['column_key'])
            if code_options:
                # 새로운 방식의 옵션이 있으면 사용
                col['dropdown_options_mapped'] = code_options
                logging.info(f"  - {col['column_name']} ({col['column_key']}): 코드-값 매핑 {len(code_options)}개 옵션")
            else:
                # 기존 JSON 방식 유지 (하위 호환성)
                col['dropdown_options_mapped'] = None
    
    # 딕셔너리를 객체처럼 사용할 수 있도록 변환
    class DictAsAttr:
        def __init__(self, d):
            for k, v in d.items():
                setattr(self, k, v)
    
    # custom_data 파싱
    import json
    custom_data = {}
    if 'custom_data' in accident and accident['custom_data']:
        try:
            custom_data = json.loads(accident['custom_data'])
            logging.info(f"Loaded custom_data: {custom_data}")
        except Exception as e:
            logging.error(f"Error parsing custom_data: {e}")
            custom_data = {}
    
    accident = DictAsAttr(accident)
    
    logging.info(f"사고 {accident_id} ({accident.accident_name}) 상세 페이지 로드")
    
    # 팝업 모드인지 확인
    is_popup = request.args.get('popup') == '1'
    
    return render_template('accident-detail.html', 
                         accident=accident,
                         attachments=attachments,
                         dynamic_columns=dynamic_columns,  # 동적 컬럼 정보
                         custom_data=custom_data,  # 기존 데이터
                         menu=MENU_CONFIG, 
                         is_popup=is_popup,
                         board_type='accident')  # 게시판 타입 전달

def get_dropdown_options_for_display(column_key):
    """드롭다운 옵션을 코드-값 매핑 방식으로 가져오기"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        
        # 활성화된 코드 목록 조회
        codes = conn.execute("""
            SELECT option_code, option_value 
            FROM dropdown_option_codes
            WHERE column_key = ? AND is_active = 1
            ORDER BY display_order
        """, (column_key,)).fetchall()
        
        logging.info(f"[DEBUG] get_dropdown_options_for_display({column_key}): {len(codes) if codes else 0}개 행 조회됨")
        if codes:
            for c in codes:
                logging.info(f"  - {c['option_code']}: {c['option_value']}")
        
        conn.close()
        
        if codes:
            # 🔐 방탄: 만약 '단 1행'이고 그 값이 JSON 배열 문자열이면 바로 분해해서 반환
            if len(codes) == 1:
                v = codes[0]['option_value']
                if isinstance(v, str):
                    s = v.strip()
                    if s.startswith('[') and s.endswith(']'):
                        try:
                            arr = json.loads(s)
                            if isinstance(arr, list):
                                logging.warning(
                                    f"[{column_key}] option_value가 배열 문자열 1건으로 저장되어 있어 런타임 분해 처리합니다. "
                                    f"원본={v} (len={len(arr)})"
                                )
                                return [
                                    {'code': f"{column_key.upper()}_{i+1:03d}", 'value': str(item)}
                                    for i, item in enumerate(arr)
                                ]
                        except Exception as e:
                            logging.error(f"[{column_key}] 배열 문자열 파싱 실패: {e}")
            
            # 정상 케이스
            return [{'code': row['option_code'], 'value': row['option_value']} for row in codes]
        else:
            return None
    except:
        return None

def convert_code_to_value(column_key, code):
    """코드를 표시 값으로 변환"""
    if not code:
        return code
        
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 코드에 해당하는 값 조회 (비활성화된 것도 포함 - 기존 데이터 표시용)
        result = cursor.execute("""
            SELECT option_value 
            FROM dropdown_option_codes
            WHERE column_key = ? AND option_code = ?
        """, (column_key, code)).fetchone()
        
        conn.close()
        
        if result:
            return result[0]
        else:
            # 매핑이 없으면 원본 값 반환 (하위 호환성)
            return code
    except:
        return code

def convert_accident_codes_to_values(accident_data, dynamic_columns):
    """사고 데이터의 코드를 표시 값으로 일괄 변환"""
    if not accident_data or not accident_data.get('custom_data'):
        return accident_data
    
    try:
        custom_data = json.loads(accident_data['custom_data'])
        
        for col in dynamic_columns:
            if col['column_type'] == 'dropdown' and col['column_key'] in custom_data:
                code = custom_data[col['column_key']]
                if code:
                    # 코드를 값으로 변환
                    custom_data[col['column_key']] = convert_code_to_value(col['column_key'], code)
        
        accident_data['custom_data'] = json.dumps(custom_data, ensure_ascii=False)
    except:
        pass
    
    return accident_data

@app.route("/accident-register")
def accident_register():
    """사고 등록 페이지"""
    logging.info("사고 등록 페이지 접근")
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Row 객체로 반환
    
    # 동적 컬럼 설정 가져오기
    dynamic_columns_rows = conn.execute("""
        SELECT * FROM accident_column_config 
        WHERE is_active = 1 
        ORDER BY column_order
    """).fetchall()
    
    # Row 객체를 딕셔너리로 변환
    dynamic_columns = [dict(row) for row in dynamic_columns_rows]
    
    conn.close()
    
    # 드롭다운 컬럼에 대해 코드-값 매핑 적용
    for col in dynamic_columns:
        if col['column_type'] == 'dropdown':
            # 코드-값 매핑 방식으로 옵션 가져오기
            code_options = get_dropdown_options_for_display(col['column_key'])
            if code_options:
                # 새로운 방식의 옵션이 있으면 사용
                col['dropdown_options_mapped'] = code_options
                logging.info(f"  - {col['column_name']} ({col['column_key']}): 코드-값 매핑 {len(code_options)}개 옵션 = {code_options}")
            else:
                # 기존 JSON 방식 유지 (하위 호환성)
                col['dropdown_options_mapped'] = None
                logging.info(f"  - {col['column_name']} ({col['column_key']}): 기존 JSON 방식 사용, dropdown_options = {col.get('dropdown_options')}")
    
    logging.info(f"동적 컬럼 {len(dynamic_columns)}개 로드됨")
    
    # 팝업 모드인지 확인
    is_popup = request.args.get('popup') == '1'
    
    return render_template('accident-register.html',
                         dynamic_columns=dynamic_columns,
                         menu=MENU_CONFIG,
                         is_popup=is_popup)

@app.route("/register-accident", methods=["POST"])
def register_accident():
    """새 사고 등록"""
    conn = None
    try:
        import json
        import datetime
        
        # 기본정보 필드들 받기
        accident_name = request.form.get('accident_name', '')
        accident_date = request.form.get('accident_date', '')
        accident_time = request.form.get('accident_time', '')
        accident_grade = request.form.get('accident_grade', '')
        accident_type = request.form.get('accident_type', '')
        injury_type = request.form.get('injury_type', '')
        injury_form = request.form.get('injury_form', '')
        workplace = request.form.get('workplace', '')
        building = request.form.get('building', '')
        floor = request.form.get('floor', '')
        location_detail = request.form.get('location_detail', '')
        day_of_week = request.form.get('day_of_week', '')
        responsible_company1 = request.form.get('responsible_company1', '')
        responsible_company1_no = request.form.get('responsible_company1_no', '')
        responsible_company2 = request.form.get('responsible_company2', '')
        responsible_company2_no = request.form.get('responsible_company2_no', '')
        
        detailed_content = request.form.get('detailed_content')
        custom_data = json.loads(request.form.get('custom_data', '{}'))  # 동적 컬럼
        attachment_data = json.loads(request.form.get('attachment_data', '[]'))
        files = request.files.getlist('files')
        
        logging.info(f"등록 요청 받음 - 사고명: {accident_name}")
        logging.info(f"사고 날짜: {accident_date}, 시간: {accident_time}")
        logging.info(f"동적 컬럼 데이터: {custom_data}")
        logging.info(f"첨부파일 개수: {len(files)}")
        
        # 새 사고번호 생성 (수기입력: ACCYYMMDD00 형식)
        today = datetime.date.today()
        date_part = today.strftime('%y%m%d')  # YYMMDD 형식
        accident_number_prefix = f"ACC{date_part}"
        
        conn = sqlite3.connect(DB_PATH, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        
        # 오늘 날짜의 마지막 사고번호 찾기
        cursor.execute("""
            SELECT accident_number FROM accidents_cache 
            WHERE accident_number LIKE ? 
            ORDER BY accident_number DESC 
            LIMIT 1
        """, (f"{accident_number_prefix}%",))
        
        last_accident = cursor.fetchone()
        if last_accident:
            # 마지막 번호에서 1 증가 (뒤 2자리)
            last_num = int(last_accident[0][-2:])
            accident_number = f"{accident_number_prefix}{str(last_num + 1).zfill(2)}"
        else:
            accident_number = f"{accident_number_prefix}01"
        
        logging.info(f"새 사고 등록: {accident_number}")
        
        # 1. 기본 사고 정보 등록 (기본정보 + 동적 컬럼)
        # 필요한 컬럼들이 없는 경우 추가
        cursor.execute("PRAGMA table_info(accidents_cache)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # 필수 컬럼들 체크 및 추가
        required_columns = [
            ('accident_number', 'TEXT'),
            ('accident_name', 'TEXT'),
            ('accident_date', 'TEXT'),
            ('accident_time', 'TEXT'),
            ('accident_datetime', 'TEXT'),
            ('accident_grade', 'TEXT'),
            ('accident_type', 'TEXT'),
            ('injury_type', 'TEXT'),
            ('injury_form', 'TEXT'),
            ('workplace', 'TEXT'),
            ('building', 'TEXT'),
            ('floor', 'TEXT'),
            ('location_detail', 'TEXT'),
            ('day_of_week', 'TEXT'),
            ('responsible_company1', 'TEXT'),
            ('responsible_company1_no', 'TEXT'),
            ('responsible_company2', 'TEXT'),
            ('responsible_company2_no', 'TEXT'),
            ('custom_data', 'TEXT')
        ]
        
        for col_name, col_type in required_columns:
            if col_name not in columns:
                cursor.execute(f"ALTER TABLE accidents_cache ADD COLUMN {col_name} {col_type}")
                logging.info(f"컬럼 추가: {col_name}")
        
        # datetime 조합 (정렬용)
        if accident_date and accident_time:
            accident_datetime = f"{accident_date} {accident_time}"
        elif accident_date:
            accident_datetime = f"{accident_date} 00:00"
        else:
            accident_datetime = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        
        cursor.execute("""
            INSERT INTO accidents_cache (
                accident_number, 
                accident_name,
                accident_date,
                accident_time,
                accident_datetime,
                accident_grade,
                accident_type,
                injury_type,
                injury_form,
                workplace,
                building,
                floor,
                location_detail,
                day_of_week,
                responsible_company1,
                responsible_company1_no,
                responsible_company2,
                responsible_company2_no,
                custom_data,
                business_number
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            accident_number,
            accident_name or f"사고_{accident_number}",
            accident_date or today.strftime('%Y-%m-%d'),
            accident_time or '',
            accident_datetime,
            accident_grade or '',
            accident_type or '',
            injury_type or '',
            injury_form or '',
            workplace or '',
            building or '',
            floor or '',
            location_detail or '',
            day_of_week or '',
            responsible_company1 or '',
            responsible_company1_no or '',
            responsible_company2 or '',
            responsible_company2_no or '',
            json.dumps(custom_data),
            responsible_company1_no or "DIRECT-ENTRY"  # 수기입력 표시
        ))
        
        # 2. 상세내용 저장
        if detailed_content:
            cursor.execute("""
                INSERT INTO accident_details (accident_number, detailed_content, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (accident_number, detailed_content))
        
        # 3. 첨부파일 처리
        if files:
            upload_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads', 'accidents')
            os.makedirs(upload_folder, exist_ok=True)
            
            for i, file in enumerate(files):
                if file and file.filename:
                    filename = secure_filename(file.filename)
                    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                    unique_filename = f"{accident_number}_{timestamp}_{filename}"
                    file_path = os.path.join(upload_folder, unique_filename)
                    
                    file.save(file_path)
                    
                    # 첨부파일 정보 저장
                    description = attachment_data[i]['description'] if i < len(attachment_data) else ''
                    cursor.execute("""
                        INSERT INTO accident_attachments (accident_number, file_name, file_path, file_size, description)
                        VALUES (?, ?, ?, ?, ?)
                    """, (accident_number, filename, file_path, os.path.getsize(file_path), description))
        
        conn.commit()
        logging.info(f"사고 {accident_number} 등록 완료")
        
        return jsonify({"success": True, "accident_number": accident_number})
        
    except Exception as e:
        if conn:
            conn.rollback()
        logging.error(f"사고 등록 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)})
    finally:
        if conn:
            conn.close()

@app.route("/verify-password", methods=["POST"])
def verify_password():
    """게시판별 비밀번호 검증"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data received"}), 400
            
        password = data.get('password')
        board_type = data.get('board_type', 'default')  # partner, accident, 또는 default
        
        if not password:
            return jsonify({"success": False, "message": "Password not provided"}), 400
        
        # 게시판 타입별 비밀번호 확인
        correct_password = None
        
        if board_type == 'partner':
            # 협력사 게시판 비밀번호
            correct_password = db_config.config.get('PASSWORDS', 'PARTNER_EDIT_PASSWORD', fallback=None)
        elif board_type == 'accident':
            # 사고 게시판 비밀번호
            correct_password = db_config.config.get('PASSWORDS', 'ACCIDENT_EDIT_PASSWORD', fallback=None)
        else:
            # 기본 비밀번호 (기존 호환성)
            correct_password = db_config.config.get('DEFAULT', 'EDIT_PASSWORD')
        
        # 비밀번호가 설정되지 않은 경우 기본 비밀번호 사용
        if not correct_password:
            correct_password = db_config.config.get('DEFAULT', 'EDIT_PASSWORD')
        
        logging.info(f"비밀번호 검증 요청: board_type={board_type}")
        
        if password == correct_password:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "message": "비밀번호가 올바르지 않습니다."})
    except Exception as e:
        logging.error(f"비밀번호 검증 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/update-partner", methods=["POST"])
def update_partner():
    """협력사 정보 업데이트"""
    conn = None
    try:
        import json
        
        business_number = request.form.get('business_number')
        detailed_content = request.form.get('detailed_content')
        deleted_attachments = json.loads(request.form.get('deleted_attachments', '[]'))
        attachment_data = json.loads(request.form.get('attachment_data', '[]'))
        files = request.files.getlist('files')
        
        print(f"Business Number: {business_number}")
        print(f"Files count: {len(files)}")
        print(f"Attachment data: {attachment_data}")
        
        # 협력사 존재 여부 확인 (먼저 확인)
        partner = partner_manager.get_partner_by_business_number(business_number)
        if not partner:
            from flask import jsonify
            return jsonify({"success": False, "message": "협력사를 찾을 수 없습니다."})
        
        print(f"Connecting to database: {DB_PATH}")
        conn = sqlite3.connect(DB_PATH, timeout=30.0)  # timeout 추가
        conn.execute("PRAGMA journal_mode=WAL")  # WAL 모드로 변경 (동시성 개선)
        cursor = conn.cursor()
        
        logging.info(f"업데이트 대상 협력사: {business_number}")
        
        # 1. 협력사 상세내용 업데이트 (partner_details 테이블)
        logging.info(f"상세내용 업데이트: {detailed_content[:50]}...")
        cursor.execute("""
            INSERT OR REPLACE INTO partner_details (business_number, detailed_content, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (business_number, detailed_content))
        logging.info("상세내용 업데이트 완료")
        
        # 2. 삭제된 첨부파일 처리
        for attachment_id in deleted_attachments:
            cursor.execute("DELETE FROM partner_attachments WHERE id = ?", (attachment_id,))
        
        # 3. 기존 첨부파일 정보 업데이트
        for attachment in attachment_data:
            if attachment['id'] and not attachment.get('isNew'):
                cursor.execute("""
                    UPDATE partner_attachments 
                    SET description = ? 
                    WHERE id = ?
                """, (attachment['description'], attachment['id']))
        
        # 4. 새 파일 업로드 처리
        import os
        upload_folder = os.path.join(os.getcwd(), 'uploads')
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
            
        # 새 파일들과 새 첨부파일 데이터 매칭
        new_attachments = [a for a in attachment_data if a.get('isNew')]
        print(f"New attachments: {new_attachments}")
        
        for i, file in enumerate(files):
            if file.filename and i < len(new_attachments):
                filename = file.filename
                # 파일명에 타임스탬프 추가하여 중복 방지
                import time
                timestamp = str(int(time.time()))
                name, ext = os.path.splitext(filename)
                unique_filename = f"{name}_{timestamp}{ext}"
                file_path = os.path.join(upload_folder, unique_filename)
                
                print(f"Saving file: {filename} as {unique_filename}")
                file.save(file_path)
                
                attachment_info = new_attachments[i]
                cursor.execute("""
                    INSERT INTO partner_attachments 
                    (business_number, file_name, file_path, file_size, description)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    business_number,
                    filename,  # 원본 파일명으로 저장
                    file_path,
                    os.path.getsize(file_path),
                    attachment_info['description']
                ))
                logging.info(f"첨부파일 추가: {filename} - {attachment_info['description']}")
        
        # 커밋 전 확인
        check_result = cursor.execute("SELECT COUNT(*) FROM partner_attachments WHERE business_number = ?", (business_number,)).fetchone()
        logging.info(f"커밋 전 {business_number} 협력사 첨부파일 개수: {check_result[0]}개")
        
        try:
            conn.commit()
            logging.info("데이터베이스 커밋 성공")
            
            # 커밋 후 다시 확인
            check_result2 = cursor.execute("SELECT COUNT(*) FROM partner_attachments WHERE business_number = ?", (business_number,)).fetchone()
            logging.info(f"커밋 후 {business_number} 협력사 첨부파일 개수: {check_result2[0]}개")
            
            conn.close()
            
            # 새로운 연결로 다시 확인
            logging.info("새 연결로 데이터 지속성 확인...")
            verify_conn = sqlite3.connect(DB_PATH)
            verify_result = verify_conn.execute("SELECT COUNT(*) FROM partner_attachments WHERE business_number = ?", (business_number,)).fetchone()
            logging.info(f"새 연결 확인: {business_number} 협력사 첨부파일 개수: {verify_result[0]}개")
            verify_conn.close()
            
            from flask import jsonify
            return jsonify({"success": True})
        except Exception as commit_error:
            print(f"Commit failed: {commit_error}")
            conn.rollback()
            conn.close()
            from flask import jsonify
            return jsonify({"success": False, "message": f"Commit failed: {str(commit_error)}"})
        
    except Exception as e:
        if conn:
            try:
                conn.rollback()
                conn.close()
            except:
                pass
        from flask import jsonify
        logging.error(f"업데이트 중 오류 발생: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/update-accident", methods=["POST"])
def update_accident():
    """사고 정보 업데이트"""
    conn = None
    try:
        import json
        
        accident_number = request.form.get('accident_number')
        detailed_content = request.form.get('detailed_content')
        custom_data = request.form.get('custom_data', '{}')  # Phase 2: 동적 컬럼 데이터
        deleted_attachments = json.loads(request.form.get('deleted_attachments', '[]'))
        attachment_data = json.loads(request.form.get('attachment_data', '[]'))
        files = request.files.getlist('files')
        
        print(f"Accident Number: {accident_number}")
        print(f"Custom Data received: {custom_data}")  # 디버깅용 추가
        print(f"Files count: {len(files)}")
        print(f"Attachment data: {attachment_data}")
        
        # 사고번호가 없으면 자동 생성 (수기입력용)
        if not accident_number:
            accident_number = generate_manual_accident_number(cursor)
            logging.info(f"자동 생성된 사고번호: {accident_number}")
        
        # 사고 형식 검증 (K로 시작하는 외부시스템 사고 또는 ACC로 시작하는 수기입력 사고)
        if not (accident_number.startswith('K') or accident_number.startswith('ACC')):
            from flask import jsonify
            return jsonify({"success": False, "message": "잘못된 사고번호 형식입니다."})
        
        print(f"Connecting to database: {DB_PATH}")
        conn = sqlite3.connect(DB_PATH, timeout=30.0)  # timeout 추가
        conn.execute("PRAGMA journal_mode=WAL")  # WAL 모드로 변경 (동시성 개선)
        cursor = conn.cursor()
        
        logging.info(f"업데이트 대상 사고: {accident_number}")
        
        # 1. 사고 상세내용 업데이트 (테이블이 없으면 생성)
        logging.info(f"상세내용 업데이트: {detailed_content[:50]}...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accident_details (
                accident_number TEXT PRIMARY KEY,
                detailed_content TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            INSERT OR REPLACE INTO accident_details (accident_number, detailed_content, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (accident_number, detailed_content))
        logging.info("상세내용 업데이트 완료")
        
        # Phase 2: 동적 컬럼 데이터 저장 (accidents_cache 테이블에 custom_data 업데이트)
        # accidents_cache 테이블에 accident_number 컬럼 추가 (없으면)
        cursor.execute("""
            PRAGMA table_info(accidents_cache)
        """)
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'accident_number' not in columns:
            cursor.execute("""
                ALTER TABLE accidents_cache ADD COLUMN accident_number TEXT
            """)
            logging.info("accident_number 컬럼 추가됨")
        
        if 'accident_name' not in columns:
            cursor.execute("""
                ALTER TABLE accidents_cache ADD COLUMN accident_name TEXT
            """)
            logging.info("accident_name 컬럼 추가됨")
        
        # 먼저 해당 사고가 accidents_cache에 있는지 확인
        cursor.execute("SELECT id FROM accidents_cache WHERE accident_number = ?", (accident_number,))
        accident_row = cursor.fetchone()
        
        if accident_row:
            # 기존 레코드 업데이트
            cursor.execute("""
                UPDATE accidents_cache 
                SET custom_data = ?
                WHERE accident_number = ?
            """, (custom_data, accident_number))
            logging.info(f"동적 컬럼 데이터 업데이트 완료: {accident_number}")
        else:
            # 새 레코드 생성 (업체 정보는 선택적)
            # 비공식/직접등록 사고는 'DIRECT-ENTRY'로 표시
            cursor.execute("""
                INSERT INTO accidents_cache (business_number, accident_number, accident_name, custom_data, accident_date)
                VALUES (?, ?, ?, ?, date('now'))
            """, ('DIRECT-ENTRY', accident_number, f"사고_{accident_number}", custom_data))
            logging.info(f"새 사고 레코드 생성 (직접등록) 및 동적 컬럼 데이터 저장: {accident_number}")
        
        # 2. 사고 첨부파일 테이블 생성 (없으면 생성)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accident_attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                accident_number TEXT,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size INTEGER,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 3. 삭제된 첨부파일 처리
        for attachment_id in deleted_attachments:
            cursor.execute("DELETE FROM accident_attachments WHERE id = ?", (attachment_id,))
        
        # 4. 기존 첨부파일 정보 업데이트
        for attachment in attachment_data:
            if attachment['id'] and not attachment.get('isNew'):
                cursor.execute("""
                    UPDATE accident_attachments 
                    SET description = ? 
                    WHERE id = ?
                """, (attachment['description'], attachment['id']))
        
        # 5. 새 파일 업로드 처리
        import os
        upload_folder = os.path.join(os.getcwd(), 'uploads')
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
            
        # 새 파일들과 새 첨부파일 데이터 매칭
        new_attachments = [a for a in attachment_data if a.get('isNew')]
        print(f"New attachments: {new_attachments}")
        
        for i, file in enumerate(files):
            if file.filename and i < len(new_attachments):
                filename = file.filename
                # 파일명에 타임스탬프 추가하여 중복 방지
                import time
                timestamp = str(int(time.time()))
                name, ext = os.path.splitext(filename)
                unique_filename = f"{name}_{timestamp}{ext}"
                file_path = os.path.join(upload_folder, unique_filename)
                
                print(f"Saving file: {filename} as {unique_filename}")
                file.save(file_path)
                
                attachment_info = new_attachments[i]
                cursor.execute("""
                    INSERT INTO accident_attachments 
                    (accident_number, file_name, file_path, file_size, description)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    accident_number,
                    filename,  # 원본 파일명으로 저장
                    file_path,
                    os.path.getsize(file_path),
                    attachment_info['description']
                ))
                logging.info(f"첨부파일 추가: {filename} - {attachment_info['description']}")
        
        # 커밋 전 확인
        check_result = cursor.execute("SELECT COUNT(*) FROM accident_attachments WHERE accident_number = ?", (accident_number,)).fetchone()
        logging.info(f"커밋 전 {accident_number} 사고 첨부파일 개수: {check_result[0]}개")
        
        try:
            conn.commit()
            logging.info("데이터베이스 커밋 성공")
            
            # 커밋 후 다시 확인
            check_result2 = cursor.execute("SELECT COUNT(*) FROM accident_attachments WHERE accident_number = ?", (accident_number,)).fetchone()
            logging.info(f"커밋 후 {accident_number} 사고 첨부파일 개수: {check_result2[0]}개")
            
            conn.close()
            
            # 새로운 연결로 다시 확인
            logging.info("새 연결로 데이터 지속성 확인...")
            verify_conn = sqlite3.connect(DB_PATH)
            verify_result = verify_conn.execute("SELECT COUNT(*) FROM accident_attachments WHERE accident_number = ?", (accident_number,)).fetchone()
            logging.info(f"새 연결 확인: {accident_number} 사고 첨부파일 개수: {verify_result[0]}개")
            verify_conn.close()
            
            from flask import jsonify
            return jsonify({"success": True})
        except Exception as commit_error:
            print(f"Commit failed: {commit_error}")
            conn.rollback()
            conn.close()
            from flask import jsonify
            return jsonify({"success": False, "message": f"Commit failed: {str(commit_error)}"})
        
    except Exception as e:
        if conn:
            try:
                conn.rollback()
                conn.close()
            except:
                pass
        from flask import jsonify
        logging.error(f"사고 업데이트 중 오류 발생: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/download/<int:attachment_id>")
def download_attachment(attachment_id):
    """첨부파일 다운로드 (협력사 및 사고 통합)"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # 먼저 partner_attachments에서 찾기
    attachment = conn.execute(
        "SELECT * FROM partner_attachments WHERE id = ?", 
        (attachment_id,)
    ).fetchone()
    
    # partner_attachments에 없으면 accident_attachments에서 찾기
    if not attachment:
        attachment = conn.execute(
            "SELECT * FROM accident_attachments WHERE id = ?", 
            (attachment_id,)
        ).fetchone()
    
    conn.close()
    
    if not attachment:
        return "File not found", 404
    
    from flask import send_file
    import os
    
    # DB에 저장된 file_path 사용 (실제 저장된 경로)
    stored_file_path = attachment['file_path']
    
    # 절대 경로인지 상대 경로인지 확인
    if os.path.isabs(stored_file_path):
        actual_file_path = stored_file_path
    else:
        # 상대 경로면 현재 디렉토리 기준으로 구성
        actual_file_path = os.path.join(os.getcwd(), stored_file_path.lstrip('/\\'))
    
    logging.info(f"다운로드 요청: ID={attachment_id}, 파일={attachment['file_name']}, 경로={actual_file_path}")
    
    try:
        if os.path.exists(actual_file_path):
            return send_file(
                actual_file_path,
                as_attachment=True,
                download_name=attachment['file_name']
            )
        else:
            logging.error(f"파일을 찾을 수 없습니다: {actual_file_path}")
            return "File not found on disk", 404
    except Exception as e:
        logging.error(f"파일 다운로드 중 오류: {e}")
        return f"Download error: {str(e)}", 500

@app.route("/partner-attachments/<business_number>")
def get_partner_attachments(business_number):
    """협력사 첨부파일 목록 가져오기"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    attachments = conn.execute("""
        SELECT * FROM partner_attachments 
        WHERE business_number = ? 
        ORDER BY upload_date DESC
    """, (business_number,)).fetchall()
    conn.close()
    
    from flask import jsonify
    return jsonify([dict(attachment) for attachment in attachments])

# ===== Phase 1: 동적 컬럼 관리 API =====

@app.route("/api/accident-columns", methods=["GET"])
def get_accident_columns():
    """사고 페이지 동적 컬럼 설정 조회"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        columns = conn.execute("""
            SELECT * FROM accident_column_config 
            ORDER BY column_order
        """).fetchall()
        conn.close()
        
        # 관리 페이지에서는 모든 컬럼 반환 (활성/비활성 모두)
        return jsonify([dict(col) for col in columns])
    except Exception as e:
        logging.error(f"컬럼 조회 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# 이 라우트는 아래에 더 완전한 버전이 있으므로 제거됨

@app.route("/admin/accident-columns")
def admin_accident_columns():
    """사고 컬럼 관리 페이지"""
    return render_template('admin-accident-columns.html', menu=MENU_CONFIG)

@app.route("/admin/accident-columns-v2")
def admin_accident_columns_v2():
    """사고 컬럼 관리 페이지 V2 - 코드 매핑 방식"""
    return render_template('admin-accident-columns-v2.html', menu=MENU_CONFIG)

@app.route("/admin/accident-columns-v3")
def admin_accident_columns_v3():
    """사고 컬럼 관리 페이지 V3 - 완전한 코드 매핑 시스템"""
    return render_template('admin-accident-columns-v3.html', menu=MENU_CONFIG)

@app.route("/admin/accident-columns-enhanced")
def admin_accident_columns_enhanced():
    """사고 컬럼 관리 페이지 Enhanced - Phase 2 고급 기능"""
    return render_template('admin-accident-columns-enhanced.html', menu=MENU_CONFIG)

@app.route("/admin/accident-columns-simplified")
def admin_accident_columns_simplified():
    """사고 컬럼 관리 페이지 Simplified - 간소화 버전"""
    return render_template('admin-accident-columns-simplified.html', menu=MENU_CONFIG)

@app.route("/admin/menu-settings")
def admin_menu_settings():
    """메뉴 설정 페이지"""
    return render_template('admin-menu-settings.html', menu=MENU_CONFIG)

@app.route("/admin/permission-settings")
def admin_permission_settings():
    """권한 설정 페이지"""
    return render_template('admin-permission-settings.html', menu=MENU_CONFIG)

@app.route("/admin/data-management")
def admin_data_management():
    """데이터 관리 페이지"""
    return render_template('admin-data-management.html', menu=MENU_CONFIG)

@app.route("/api/accidents/deleted")
def get_deleted_accidents():
    """삭제된 사고 목록 API"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # 삭제된 사고만 조회
    deleted_accidents_rows = conn.execute("""
        SELECT * FROM accidents_cache 
        WHERE is_deleted = 1
        ORDER BY accident_date DESC, accident_number DESC
    """).fetchall()
    
    deleted_accidents = [dict(row) for row in deleted_accidents_rows]
    conn.close()
    
    return jsonify({"success": True, "accidents": deleted_accidents})

@app.route('/api/accidents/delete', methods=['POST'])
def delete_accidents():
    """선택한 사고들을 소프트 삭제"""
    try:
        data = request.json
        ids = data.get('ids', [])
        
        if not ids:
            return jsonify({"success": False, "message": "삭제할 항목이 없습니다."}), 400
        
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        cursor = conn.cursor()
        
        # 모든 사고 삭제 가능 (ACC, K 모두)
        placeholders = ','.join('?' * len(ids))
        cursor.execute(f"""
            UPDATE accidents_cache 
            SET is_deleted = 1 
            WHERE id IN ({placeholders})
        """, ids)
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        return jsonify({
            "success": True,
            "deleted_count": deleted_count,
            "message": f"{deleted_count}건이 삭제되었습니다."
        })
    except Exception as e:
        logging.error(f"사고 삭제 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/accidents/restore', methods=['POST'])
def restore_accidents():
    """삭제된 사고들을 복구"""
    try:
        data = request.json
        ids = data.get('ids', [])
        
        if not ids:
            return jsonify({"success": False, "message": "복구할 항목이 없습니다."}), 400
        
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        cursor = conn.cursor()
        
        # 선택한 사고들을 복구 (is_deleted = 0)
        placeholders = ','.join('?' * len(ids))
        cursor.execute(f"""
            UPDATE accidents_cache 
            SET is_deleted = 0 
            WHERE id IN ({placeholders})
        """, ids)
        
        restored_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        return jsonify({
            "success": True,
            "restored_count": restored_count,
            "message": f"{restored_count}건이 복구되었습니다."
        })
    except Exception as e:
        logging.error(f"사고 복구 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/accidents/permanent-delete', methods=['POST'])
def permanent_delete_accidents():
    """선택한 사고들을 영구 삭제"""
    try:
        data = request.json
        ids = data.get('ids', [])
        
        if not ids:
            return jsonify({"success": False, "message": "삭제할 항목이 없습니다."}), 400
        
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        cursor = conn.cursor()
        
        # 선택한 사고들을 영구 삭제
        placeholders = ','.join('?' * len(ids))
        cursor.execute(f"""
            DELETE FROM accidents_cache 
            WHERE id IN ({placeholders})
        """, ids)
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        return jsonify({
            "success": True,
            "deleted_count": deleted_count,
            "message": f"{deleted_count}건이 영구 삭제되었습니다."
        })
    except Exception as e:
        logging.error(f"사고 영구 삭제 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/accident-columns", methods=["POST"])
def add_accident_column():
    """사고 페이지 동적 컬럼 추가"""
    try:
        data = request.json
        
        conn = sqlite3.connect(DB_PATH, timeout=10.0)  # timeout 추가
        cursor = conn.cursor()
        
        # 컬럼 키 사용 (사용자가 직접 입력하거나 자동 생성)
        column_key = data.get('column_key')
        if not column_key:
            # 새 컬럼 키 자동 생성
            cursor.execute("SELECT MAX(CAST(SUBSTR(column_key, 7) AS INTEGER)) FROM accident_column_config WHERE column_key LIKE 'column%'")
            max_num = cursor.fetchone()[0] or 10
            column_key = f"column{max_num + 1}"
        
        # 최대 순서 번호 조회
        cursor.execute("SELECT MAX(column_order) FROM accident_column_config")
        max_order = cursor.fetchone()[0] or 0
        
        import json
        dropdown_options = None
        if data.get('column_type') == 'dropdown' and 'dropdown_options' in data:
            dropdown_options = json.dumps(data['dropdown_options'], ensure_ascii=False)
        
        cursor.execute("""
            INSERT INTO accident_column_config 
            (column_key, column_name, column_type, column_order, is_active, dropdown_options)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            column_key,
            data['column_name'],
            data.get('column_type', 'text'),
            max_order + 1,
            data.get('is_active', 1),
            dropdown_options
        ))
        
        # 드롭다운 타입일 경우 자동으로 코드 생성
        if data.get('column_type') == 'dropdown' and dropdown_options:
            try:
                options_list = json.loads(dropdown_options) if isinstance(dropdown_options, str) else dropdown_options
                if isinstance(options_list, list):
                    for idx, value in enumerate(options_list, 1):
                        code = f"{column_key.upper()}_{str(idx).zfill(3)}"
                        cursor.execute("""
                            INSERT OR IGNORE INTO dropdown_option_codes
                            (column_key, option_code, option_value, display_order, is_active)
                            VALUES (?, ?, ?, ?, 1)
                        """, (column_key, code, value, idx))
                    logging.info(f"드롭다운 컬럼 {column_key}에 대한 코드 {len(options_list)}개 자동 생성")
            except Exception as e:
                logging.error(f"드롭다운 코드 자동 생성 실패: {e}")
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "success": True, 
            "message": "컬럼이 추가되었습니다.",
            "column_key": column_key
        })
    except Exception as e:
        logging.error(f"컬럼 추가 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/accident-columns/<int:column_id>", methods=["PUT"])
def update_accident_column(column_id):
    """사고 페이지 동적 컬럼 수정"""
    try:
        data = request.json
        
        conn = sqlite3.connect(DB_PATH, timeout=10.0)  # timeout 추가
        cursor = conn.cursor()
        
        # 현재 컬럼 정보 조회
        cursor.execute("SELECT column_key, column_type FROM accident_column_config WHERE id = ?", (column_id,))
        column_info = cursor.fetchone()
        if not column_info:
            return jsonify({"success": False, "message": "컬럼을 찾을 수 없습니다."}), 404
        
        current_column_key, current_column_type = column_info
        
        # 업데이트할 필드 준비
        update_fields = []
        params = []
        
        if 'column_name' in data:
            update_fields.append("column_name = ?")
            params.append(data['column_name'])
        
        # 타입 변경 처리
        if 'column_type' in data:
            new_type = data['column_type']
            update_fields.append("column_type = ?")
            params.append(new_type)
            
            # 드롭다운에서 다른 타입으로 변경 시 코드 비활성화
            if current_column_type == 'dropdown' and new_type != 'dropdown':
                cursor.execute("""
                    UPDATE dropdown_option_codes 
                    SET is_active = 0 
                    WHERE column_key = ?
                """, (current_column_key,))
                logging.info(f"타입 변경으로 {current_column_key}의 드롭다운 코드 비활성화")
        
        if 'is_active' in data:
            update_fields.append("is_active = ?")
            params.append(1 if data['is_active'] else 0)
        
        if 'dropdown_options' in data:
            import json
            dropdown_options = json.dumps(data['dropdown_options'], ensure_ascii=False) if data['dropdown_options'] else None
            update_fields.append("dropdown_options = ?")
            params.append(dropdown_options)
            
            # 새로운 드롭다운 옵션에 대한 코드 생성
            if data.get('column_type') == 'dropdown' and dropdown_options:
                try:
                    options_list = json.loads(dropdown_options) if isinstance(dropdown_options, str) else data['dropdown_options']
                    if isinstance(options_list, list):
                        # 기존 코드 비활성화
                        cursor.execute("""
                            UPDATE dropdown_option_codes 
                            SET is_active = 0 
                            WHERE column_key = ?
                        """, (current_column_key,))
                        
                        # 새 코드 생성
                        for idx, value in enumerate(options_list, 1):
                            code = f"{current_column_key.upper()}_{str(idx).zfill(3)}"
                            cursor.execute("""
                                INSERT OR REPLACE INTO dropdown_option_codes
                                (column_key, option_code, option_value, display_order, is_active)
                                VALUES (?, ?, ?, ?, 1)
                            """, (current_column_key, code, value, idx))
                        logging.info(f"드롭다운 옵션 업데이트: {current_column_key}에 코드 {len(options_list)}개 재생성")
                except Exception as e:
                    logging.error(f"드롭다운 코드 업데이트 실패: {e}")
        
        if update_fields:
            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            params.append(column_id)
            
            query = f"UPDATE accident_column_config SET {', '.join(update_fields)} WHERE id = ?"
            cursor.execute(query, params)
            conn.commit()
        
        conn.close()
        
        return jsonify({"success": True, "message": "컬럼이 수정되었습니다."})
    except Exception as e:
        logging.error(f"컬럼 수정 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/dropdown-codes/<column_key>", methods=["GET"])
def get_dropdown_codes(column_key):
    """특정 컬럼의 드롭다운 코드 목록 조회"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        codes = conn.execute("""
            SELECT * FROM dropdown_option_codes
            WHERE column_key = ? AND is_active = 1
            ORDER BY display_order
        """, (column_key,)).fetchall()
        conn.close()
        
        # 응답 형식 통일
        return jsonify({
            "success": True,
            "codes": [
                {
                    "code": code['option_code'],
                    "value": code['option_value'],
                    "order": code['display_order']
                } for code in codes
            ]
        })
    except Exception as e:
        logging.error(f"드롭다운 코드 조회 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/dropdown-codes", methods=["POST"])
def save_dropdown_codes():
    """드롭다운 코드 저장/업데이트 (변경 이력 추적 포함)"""
    conn = None
    try:
        data = request.json
        column_key = data.get('column_key')
        codes = data.get('codes', [])
        
        logging.info(f"[dropdown-codes] v3 handler called: column_key={column_key}, codes count={len(codes)}")
        logging.info(f"[dropdown-codes] raw codes: {codes}")
        
        # === 유틸: JSON 배열 문자열인지 판별
        def _looks_like_json_array_text(s):
            return isinstance(s, str) and s.strip().startswith('[') and s.strip().endswith(']')
        
        # === 유틸: 어떤 형태로 와도 재귀적으로 평탄화
        def _deep_flatten_values(value):
            import json
            out = []
            stack = [value]
            while stack:
                v = stack.pop()
                if isinstance(v, list):
                    # 리스트면 항목을 뒤에서 앞으로 스택에
                    for i in range(len(v) - 1, -1, -1):
                        stack.append(v[i])
                elif isinstance(v, str) and _looks_like_json_array_text(v):
                    # 문자열이더라도 [ ... ] 꼴이면 다시 파싱해서 반복
                    try:
                        parsed = json.loads(v)
                        stack.append(parsed)
                    except Exception:
                        sv = v.strip()
                        if sv:
                            out.append(sv)
                else:
                    sv = (str(v)).strip()
                    if sv:
                        out.append(sv)
            return out
        
        # 들어온 codes를 재귀 평탄화해서 완전한 리스트로 만들기
        flattened = []
        for c in codes:  # codes는 [{code: "...", value: "..."} ...] 형태
            vals = _deep_flatten_values(c.get('value'))
            for v in vals:
                flattened.append({'value': v})
        
        # flattened가 비어있으면 빈 값 하나라도 넣기
        if not flattened:
            flattened = [{'value': ''}]
        
        logging.info(f"[dropdown-codes] flattened to {len(flattened)} values: {[f['value'] for f in flattened]}")
        
        # 요청 정보 수집 (감사 로그용)
        ip_address = request.remote_addr
        user_agent = request.headers.get('User-Agent', '')
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 트랜잭션 시작
        cursor.execute("BEGIN TRANSACTION")
        
        # 기존 활성 코드 조회 (변경 전 상태 기록용)
        existing_codes = cursor.execute("""
            SELECT option_code, option_value, display_order 
            FROM dropdown_option_codes
            WHERE column_key = ? AND is_active = 1
        """, (column_key,)).fetchall()
        
        existing_dict = {row[0]: {'value': row[1], 'order': row[2]} for row in existing_codes}
        
        # 기존 코드 비활성화
        cursor.execute("""
            UPDATE dropdown_option_codes 
            SET is_active = 0, updated_at = CURRENT_TIMESTAMP
            WHERE column_key = ?
        """, (column_key,))
        
        # 새 코드 재생성 (순번 부여)
        for idx, item in enumerate(flattened, 1):
            new_code = f"{column_key.upper()}_{str(idx).zfill(3)}"
            option_value = item['value']
            
            # 기존 코드가 있는지 확인
            existing = cursor.execute("""
                SELECT id, option_value, display_order FROM dropdown_option_codes
                WHERE column_key = ? AND option_code = ?
            """, (column_key, new_code)).fetchone()
            
            if existing:
                old_value = existing[1]
                old_order = existing[2]
                
                # 업데이트
                cursor.execute("""
                    UPDATE dropdown_option_codes 
                    SET option_value = ?, display_order = ?, is_active = 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE column_key = ? AND option_code = ?
                """, (option_value, idx, column_key, new_code))
                
                # 변경 이력 기록 (값이나 순서가 변경된 경우만)
                if old_value != option_value or old_order != idx:
                    cursor.execute("""
                        INSERT INTO dropdown_code_audit 
                        (column_key, option_code, action_type, old_value, new_value, 
                         old_order, new_order, ip_address, user_agent)
                        VALUES (?, ?, 'UPDATE', ?, ?, ?, ?, ?, ?)
                    """, (column_key, new_code, old_value, option_value, 
                          old_order, idx, ip_address, user_agent))
            else:
                # 새로 삽입
                cursor.execute("""
                    INSERT OR REPLACE INTO dropdown_option_codes 
                    (column_key, option_code, option_value, display_order, is_active)
                    VALUES (?, ?, ?, ?, 1)
                """, (column_key, new_code, option_value, idx))
                
                # 생성 이력 기록
                cursor.execute("""
                    INSERT INTO dropdown_code_audit 
                    (column_key, option_code, action_type, new_value, new_order, 
                     ip_address, user_agent)
                    VALUES (?, ?, 'CREATE', ?, ?, ?, ?)
                """, (column_key, new_code, option_value, idx, ip_address, user_agent))
        
        # 삭제된 코드 확인 및 기록 (재생성된 코드 기준)
        new_codes = {f"{column_key.upper()}_{str(i+1).zfill(3)}" for i in range(len(flattened))}
        for old_code, old_data in existing_dict.items():
            if old_code not in new_codes:
                cursor.execute("""
                    INSERT INTO dropdown_code_audit 
                    (column_key, option_code, action_type, old_value, old_order, 
                     ip_address, user_agent)
                    VALUES (?, ?, 'DELETE', ?, ?, ?, ?)
                """, (column_key, old_code, old_data['value'], old_data['order'], 
                      ip_address, user_agent))
        
        cursor.execute("COMMIT")
        conn.close()
        
        return jsonify({"success": True, "message": "드롭다운 코드가 저장되었습니다."})
    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        logging.error(f"드롭다운 코드 저장 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/dropdown-codes/<column_key>/history", methods=["GET"])
def get_dropdown_history(column_key):
    """특정 컬럼의 변경 이력 조회"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        
        # 최근 100개 변경 이력 조회
        history = conn.execute("""
            SELECT * FROM dropdown_code_audit
            WHERE column_key = ?
            ORDER BY changed_at DESC
            LIMIT 100
        """, (column_key,)).fetchall()
        
        # 통계 정보 조회
        stats = conn.execute("""
            SELECT * FROM dropdown_code_stats
            WHERE column_key = ?
        """, (column_key,)).fetchone()
        
        conn.close()
        
        return jsonify({
            "history": [dict(row) for row in history],
            "stats": dict(stats) if stats else None
        })
    except Exception as e:
        logging.error(f"변경 이력 조회 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/dropdown-codes/audit-summary", methods=["GET"])
def get_audit_summary():
    """전체 변경 이력 요약"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        
        # 최근 7일간 변경 통계
        recent_changes = conn.execute("""
            SELECT 
                DATE(changed_at) as date,
                COUNT(*) as total_changes,
                COUNT(DISTINCT column_key) as columns_changed
            FROM dropdown_code_audit
            WHERE changed_at >= datetime('now', '-7 days')
            GROUP BY DATE(changed_at)
            ORDER BY date DESC
        """).fetchall()
        
        # 가장 많이 변경된 컬럼 TOP 5
        most_changed = conn.execute("""
            SELECT 
                column_key,
                COUNT(*) as change_count,
                MAX(changed_at) as last_changed
            FROM dropdown_code_audit
            GROUP BY column_key
            ORDER BY change_count DESC
            LIMIT 5
        """).fetchall()
        
        conn.close()
        
        return jsonify({
            "recent_changes": [dict(row) for row in recent_changes],
            "most_changed_columns": [dict(row) for row in most_changed]
        })
    except Exception as e:
        logging.error(f"감사 요약 조회 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/accident-columns/<int:column_id>", methods=["DELETE"])
def delete_accident_column(column_id):
    """사고 페이지 동적 컬럼 삭제 (실제로는 비활성화)"""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10.0)  # timeout 추가
        cursor = conn.cursor()
        
        # 먼저 컬럼 정보 조회
        cursor.execute("SELECT column_key, column_type FROM accident_column_config WHERE id = ?", (column_id,))
        column_info = cursor.fetchone()
        
        if column_info:
            column_key, column_type = column_info
            
            # 드롭다운 타입이면 관련 코드도 비활성화
            if column_type == 'dropdown':
                cursor.execute("""
                    UPDATE dropdown_option_codes 
                    SET is_active = 0 
                    WHERE column_key = ?
                """, (column_key,))
                logging.info(f"드롭다운 컬럼 {column_key}의 코드도 비활성화")
        
        # 컬럼을 실제로 삭제하지 않고 비활성화
        cursor.execute("""
            UPDATE accident_column_config 
            SET is_active = 0, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        """, (column_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "message": "컬럼이 삭제되었습니다."})
    except Exception as e:
        logging.error(f"컬럼 삭제 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/accident-columns/order", methods=["PUT"])
def update_accident_columns_order():
    """사고 페이지 동적 컬럼 순서 변경"""
    try:
        data = request.json  # [{id: 1, column_order: 0}, {id: 2, column_order: 1}, ...]
        
        conn = sqlite3.connect(DB_PATH, timeout=10.0)  # timeout 추가
        cursor = conn.cursor()
        
        for item in data:
            cursor.execute("""
                UPDATE accident_column_config 
                SET column_order = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            """, (item['column_order'], item['id']))
        
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "message": "순서가 변경되었습니다."})
    except Exception as e:
        logging.error(f"컬럼 순서 변경 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/person-master", methods=["GET"])
def get_person_master():
    """담당자 마스터 목록 조회 (팝업용)"""
    try:
        search = request.args.get('search', '')
        
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        
        query = """
            SELECT * FROM person_master 
            WHERE is_active = 1
        """
        params = []
        
        if search:
            query += " AND (name LIKE ? OR department LIKE ? OR company_name LIKE ?)"
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])
        
        query += " ORDER BY name"
        
        persons = conn.execute(query, params).fetchall()
        conn.close()
        
        return jsonify({
            "success": True,
            "persons": [dict(p) for p in persons]
        })
    except Exception as e:
        logging.error(f"담당자 조회 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# Catch-all 라우트는 맨 마지막에 위치 (다른 모든 라우트 다음)
@app.route("/<path:url>")
def page_view(url):
    """일반 페이지 체크 (catch-all 라우트)"""
    conn = sqlite3.connect(DB_PATH)
    page = conn.execute("SELECT * FROM pages WHERE url = ?", (url,)).fetchone()
    conn.close()
    
    if not page:
        return "Page not found", 404
    
    return render_template("page.html", 
                         page={'url': page[1], 'title': page[2], 'content': page[3]},
                         menu=MENU_CONFIG)

@app.route("/api/accident-export")
def export_accidents_excel():
    """사고 데이터 엑셀 다운로드"""
    try:
        import openpyxl
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill
        from datetime import datetime
        import io
        
        # 검색 조건 가져오기
        company_name = request.args.get('company_name', '')
        business_number = request.args.get('business_number', '')
        accident_date_start = request.args.get('accident_date_start', '')
        accident_date_end = request.args.get('accident_date_end', '')
        
        # DB 연결
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        
        # 동적 컬럼 정보 가져오기
        dynamic_columns_rows = conn.execute("""
            SELECT * FROM accident_column_config 
            WHERE is_active = 1 
            ORDER BY column_order
        """).fetchall()
        dynamic_columns = [dict(row) for row in dynamic_columns_rows]
        
        # 사고 데이터 조회 (partner_accident 함수와 동일한 로직)
        query = """
            SELECT * FROM accidents_cache 
            WHERE 1=1
        """
        params = []
        
        if company_name:
            query += " AND (responsible_company1 LIKE ? OR responsible_company2 LIKE ?)"
            params.extend([f'%{company_name}%', f'%{company_name}%'])
        
        if business_number:
            query += " AND (responsible_company1_no LIKE ? OR responsible_company2_no LIKE ?)"
            params.extend([f'%{business_number}%', f'%{business_number}%'])
        
        if accident_date_start:
            query += " AND accident_date >= ?"
            params.append(accident_date_start)
        
        if accident_date_end:
            query += " AND accident_date <= ?"
            params.append(accident_date_end)
        
        query += """
            ORDER BY 
                CASE 
                    WHEN accident_datetime IS NOT NULL AND accident_datetime != '' 
                    THEN accident_datetime 
                    ELSE COALESCE(accident_date, '1900-01-01') || ' 00:00' 
                END DESC, 
                accident_number DESC
        """
        
        accidents = conn.execute(query, params).fetchall()
        
        # 엑셀 워크북 생성
        wb = Workbook()
        ws = wb.active
        ws.title = "사고 현황"
        
        # 헤더 스타일 설정
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        header_align = Alignment(horizontal="center", vertical="center")
        
        # 헤더 작성 (사고번호는 자동 생성되므로 제외)
        headers = [
            '사고명', '재해날짜', '시간', '사고등급', '사고분류',
            '재해유형', '재해형태', '사업장', '건물', '층', '세부위치',
            '요일', '귀책협력사(1차)', '귀책협력사(1차)사업자번호',
            '귀책협력사(2차)', '귀책협력사(2차)사업자번호'
        ]
        
        # 동적 컬럼 헤더 추가
        for col in dynamic_columns:
            headers.append(col['column_name'])
        
        # 헤더 쓰기
        for col_idx, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align
        
        # 데이터 쓰기
        for row_idx, accident_row in enumerate(accidents, 2):
            accident = dict(accident_row)
            
            # 기본 필드 쓰기 (사고번호 제외)
            ws.cell(row=row_idx, column=1, value=accident.get('accident_name', ''))
            ws.cell(row=row_idx, column=2, value=accident.get('accident_date', ''))
            ws.cell(row=row_idx, column=3, value=accident.get('accident_time', ''))
            ws.cell(row=row_idx, column=4, value=accident.get('accident_grade', ''))
            ws.cell(row=row_idx, column=5, value=accident.get('accident_type', ''))
            ws.cell(row=row_idx, column=6, value=accident.get('injury_type', ''))
            ws.cell(row=row_idx, column=7, value=accident.get('injury_form', ''))
            ws.cell(row=row_idx, column=8, value=accident.get('workplace', ''))
            ws.cell(row=row_idx, column=9, value=accident.get('building', ''))
            ws.cell(row=row_idx, column=10, value=accident.get('floor', ''))
            ws.cell(row=row_idx, column=11, value=accident.get('location_detail', ''))
            ws.cell(row=row_idx, column=12, value=accident.get('day_of_week', ''))
            ws.cell(row=row_idx, column=13, value=accident.get('responsible_company1', ''))
            ws.cell(row=row_idx, column=14, value=accident.get('responsible_company1_no', ''))
            ws.cell(row=row_idx, column=15, value=accident.get('responsible_company2', ''))
            ws.cell(row=row_idx, column=16, value=accident.get('responsible_company2_no', ''))
            
            # 동적 컬럼 데이터 쓰기
            import json
            custom_data = {}
            # DictAsAttr 객체 처리를 위해 hasattr 사용
            if hasattr(accident, 'custom_data') and accident.custom_data:
                try:
                    custom_data = json.loads(accident.custom_data)
                except:
                    custom_data = {}
            
            for col_idx, col in enumerate(dynamic_columns, 17):
                value = custom_data.get(col['column_key'], '')
                # popup 타입 데이터 처리
                if isinstance(value, dict):
                    if 'name' in value:
                        value = value['name']
                    else:
                        value = str(value)
                ws.cell(row=row_idx, column=col_idx, value=value)
        
        # 컬럼 너비 자동 조정
        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width
        
        # 파일을 메모리에 저장
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        
        conn.close()
        
        # 파일명 생성
        filename = f"accident_list_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        # 다운로드 응답
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
    
    except Exception as e:
        logging.error(f"엑셀 다운로드 중 오류: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return jsonify({"success": False, "message": str(e)}), 500

# ===== 엑셀 임포트 API =====
@app.route('/api/accident-import', methods=['POST'])
def import_accidents():
    try:
        import openpyxl
        import json
        from datetime import datetime
        import re
        
        # 파일 확인
        if 'file' not in request.files:
            return jsonify({"success": False, "message": "파일이 없습니다."}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({"success": False, "message": "파일이 선택되지 않았습니다."}), 400
            
        if not file.filename.lower().endswith(('.xlsx', '.xls')):
            return jsonify({"success": False, "message": "엑셀 파일만 업로드 가능합니다."}), 400
        
        # 옵션 확인
        skip_duplicates = request.form.get('skip_duplicates') == 'on'
        validate_data = request.form.get('validate_data') == 'on'
        
        # 엑셀 파일 읽기
        wb = openpyxl.load_workbook(file, data_only=True)
        ws = wb.active
        
        # DB 연결
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # accident_columns 테이블 확인 및 생성
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='accident_columns'
        """)
        if not cursor.fetchone():
            # 테이블이 없으면 빈 리스트로 처리
            dynamic_columns = []
            logging.info("accident_columns 테이블이 없어서 동적 컬럼 없이 처리합니다.")
        else:
            # 동적 컬럼 조회
            cursor.execute("""
                SELECT column_key, column_name, column_type, dropdown_options
                FROM accident_columns 
                WHERE is_active = 1 
                ORDER BY column_order
            """)
            dynamic_columns = cursor.fetchall()
        
        # 헤더 매핑 (한글 헤더명 -> DB 컬럼명)
        # 주의: 사고번호는 자동 생성하므로 매핑에서 제외
        header_mapping = {
            '사고명': 'accident_name', 
            '재해날짜': 'accident_date',
            '시간': 'accident_time',
            '사고등급': 'accident_level',
            '사고분류': 'accident_classification',
            '재해유형': 'disaster_type',
            '재해형태': 'disaster_form',
            '사업장': 'workplace',
            '건물': 'building',
            '층': 'floor',
            '세부위치': 'location_detail',
            '요일': 'day_of_week',
            '귀책협력사(1차)': 'responsible_company1',
            '귀책협력사(1차)사업자번호': 'responsible_company1_no',
            '귀책협력사(2차)': 'responsible_company2',
            '귀책협력사(2차)사업자번호': 'responsible_company2_no',
            '처리상태': 'processing_status',
            '조치사항': 'measures',
            '재발방지대책': 'prevention_measures',
            '담당부서': 'department',
            '담당자': 'manager',
            '완료예정일': 'completion_date',
            '원인분석': 'cause_analysis',
            '첨부문서': 'attachment',
            '발생위치': 'occurrence_location'
        }
        
        # 동적 컬럼 매핑 추가
        for col in dynamic_columns:
            header_mapping[col['column_name']] = col['column_key']
        
        # 첫 번째 행에서 헤더 읽기
        headers = []
        for cell in ws[1]:
            headers.append(cell.value if cell.value else '')
        
        success_count = 0
        error_count = 0
        errors = []
        
        # 헤더 정보 로그
        logging.info(f"엑셀 헤더: {headers}")
        logging.info(f"헤더 매핑: {header_mapping}")
        
        # 데이터 행 처리 (2행부터)
        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), 2):
            try:
                # 빈 행 건너뛰기
                if not any(row):
                    continue
                
                logging.info(f"처리 중인 행 {row_idx}: {row}")
                
                # 데이터 매핑
                data = {}
                custom_data = {}
                
                for col_idx, cell_value in enumerate(row):
                    if col_idx >= len(headers):
                        break
                        
                    header = headers[col_idx]
                    if not header or not cell_value:
                        continue
                        
                    # 문자열로 변환
                    str_value = str(cell_value).strip()
                    if not str_value:
                        continue
                    
                    # 헤더 매핑
                    if header in header_mapping:
                        db_column = header_mapping[header]
                        
                        # 기본 컬럼인지 동적 컬럼인지 확인 (accident_number는 자동 생성하므로 제외)
                        if db_column in ['accident_name', 'accident_date', 'accident_time', 
                                       'accident_level', 'accident_classification', 'disaster_type', 'disaster_form',
                                       'workplace', 'building', 'floor', 'location_detail', 'day_of_week',
                                       'responsible_company1', 'responsible_company1_no', 'responsible_company2',
                                       'responsible_company2_no', 'processing_status', 'measures', 
                                       'prevention_measures', 'department', 'manager', 'completion_date',
                                       'cause_analysis', 'attachment', 'occurrence_location']:
                            data[db_column] = str_value
                        else:
                            # 동적 컬럼
                            custom_data[db_column] = str_value
                
                # 사고번호는 항상 자동 생성 (사용자 입력 무시)
                if data.get('accident_date'):
                    # 재해날짜를 기준으로 ACCYYMMDD 형식으로 생성
                    try:
                        accident_date = data['accident_date']
                        if isinstance(accident_date, str):
                            # 날짜 문자열을 파싱
                            for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d']:
                                try:
                                    dt = datetime.strptime(accident_date, fmt)
                                    break
                                except ValueError:
                                    continue
                            else:
                                # 파싱 실패시 현재 날짜 사용
                                dt = datetime.now()
                        else:
                            dt = datetime.now()
                        
                        # ACCYYMMDD 기본 형식으로 생성
                        base_number = dt.strftime('ACC%y%m%d')
                        
                        # 같은 날짜에 이미 있는 사고 수 확인
                        cursor.execute("""
                            SELECT COUNT(*) FROM accidents 
                            WHERE accident_number LIKE ?
                        """, (base_number + '%',))
                        count = cursor.fetchone()[0]
                        
                        # 일련번호 추가 (01, 02, 03...)
                        sequence = str(count + 1).zfill(2)
                        data['accident_number'] = base_number + sequence
                        
                    except Exception as e:
                        # 오류 발생시 기본 자동 생성 방식 사용
                        data['accident_number'] = generate_manual_accident_number(cursor)
                else:
                    # 재해날짜가 없으면 기본 자동 생성 방식 사용
                    data['accident_number'] = generate_manual_accident_number(cursor)
                
                # 중복 확인
                if skip_duplicates and data.get('accident_number'):
                    cursor.execute("SELECT COUNT(*) FROM accidents WHERE accident_number = ?", (data['accident_number'],))
                    if cursor.fetchone()[0] > 0:
                        continue
                
                # 날짜 형식 처리 - 간단화
                if data.get('accident_date'):
                    date_str = str(data['accident_date']).strip()
                    if date_str and date_str != 'None':
                        data['accident_date'] = date_str
                    else:
                        # 날짜가 없으면 오늘 날짜로 설정
                        data['accident_date'] = datetime.now().strftime('%Y-%m-%d')
                
                logging.info(f"매핑된 데이터: {data}")
                logging.info(f"동적 컬럼 데이터: {custom_data}")
                
                # 최소 필수 데이터 확인
                if not data.get('accident_number'):
                    logging.error(f"행 {row_idx}: 사고번호가 생성되지 않음")
                    continue
                
                # DB 저장 - 간단화
                try:
                    # 기본 필드만 먼저 저장
                    insert_sql = """
                        INSERT INTO accidents 
                        (accident_number, accident_name, accident_date, created_at) 
                        VALUES (?, ?, ?, ?)
                    """
                    values = [
                        data['accident_number'],
                        data.get('accident_name', ''),
                        data.get('accident_date', datetime.now().strftime('%Y-%m-%d')),
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    ]
                    
                    logging.info(f"실행할 SQL: {insert_sql}")
                    logging.info(f"SQL 파라미터: {values}")
                    
                    cursor.execute(insert_sql, values)
                    
                except Exception as sql_error:
                    logging.error(f"SQL 실행 오류: {sql_error}")
                    raise sql_error
                
                success_count += 1
                
            except Exception as e:
                error_count += 1
                errors.append(f"행 {row_idx}: {str(e)}")
                continue
        
        conn.commit()
        conn.close()
        
        result = {
            "success": True,
            "success_count": success_count,
            "error_count": error_count
        }
        
        if errors:
            result["errors"] = errors[:10]  # 최대 10개 오류만 반환
            
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"엑셀 임포트 중 오류: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return jsonify({"success": False, "message": str(e)}), 500

# ===== 협력사 엑셀 다운로드 API =====
@app.route('/api/partners/export')
def export_partners_to_excel():
    try:
        import openpyxl
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill
        from datetime import datetime
        import io
        
        # 검색 조건 가져오기
        company_name = request.args.get('company_name', '')
        business_number = request.args.get('business_number', '')
        business_type_major = request.args.get('business_type_major', '')
        business_type_minor = request.args.get('business_type_minor', '')
        workers_min = request.args.get('workers_min', '')
        workers_max = request.args.get('workers_max', '')
        
        # 협력사 데이터 조회 (partner_standards 함수와 동일한 로직)
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 쿼리 구성
            query = "SELECT * FROM partners_cache WHERE 1=1"
            params = []
            
            if company_name:
                query += " AND company_name LIKE ?"
                params.append(f'%{company_name}%')
            
            if business_number:
                query += " AND business_number LIKE ?"
                params.append(f'%{business_number}%')
                
            if business_type_major:
                query += " AND business_type_major = ?"
                params.append(business_type_major)
                
            if business_type_minor:
                query += " AND business_type_minor = ?"
                params.append(business_type_minor)
                
            if workers_min:
                try:
                    min_val = int(workers_min)
                    query += " AND permanent_workers >= ?"
                    params.append(min_val)
                except ValueError:
                    pass
                    
            if workers_max:
                try:
                    max_val = int(workers_max)
                    query += " AND permanent_workers <= ?"
                    params.append(max_val)
                except ValueError:
                    pass
            
            query += " ORDER BY company_name"
            
            partners = cursor.execute(query, params).fetchall()
            
            # 엑셀 워크북 생성
            wb = Workbook()
            ws = wb.active
            ws.title = "협력사 기준정보"
            
            # 헤더 스타일 설정
            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            header_align = Alignment(horizontal="center", vertical="center")
            
            # 헤더 작성
            headers = [
                '협력사명', '사업자번호', 'Class', '업종(대분류)', '업종(소분류)',
                '위험작업여부', '대표자성명', '주소', '평균연령', '매출액', 
                '거래차수', '상시근로자'
            ]
            
            # 헤더 쓰기
            for col_idx, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col_idx, value=header)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_align
            
            # 데이터 쓰기
            for row_idx, partner_row in enumerate(partners, 2):
                partner = dict(partner_row)
                
                ws.cell(row=row_idx, column=1, value=partner.get('company_name', ''))
                ws.cell(row=row_idx, column=2, value=partner.get('business_number', ''))
                ws.cell(row=row_idx, column=3, value=partner.get('partner_class', ''))
                ws.cell(row=row_idx, column=4, value=partner.get('business_type_major', ''))
                ws.cell(row=row_idx, column=5, value=partner.get('business_type_minor', ''))
                
                # 위험작업여부 처리
                hazard_work = partner.get('hazard_work_flag', '')
                hazard_text = '예' if hazard_work == 'O' else '아니오' if hazard_work == 'X' else ''
                ws.cell(row=row_idx, column=6, value=hazard_text)
                
                ws.cell(row=row_idx, column=7, value=partner.get('representative', ''))
                ws.cell(row=row_idx, column=8, value=partner.get('address', ''))
                ws.cell(row=row_idx, column=9, value=partner.get('average_age', ''))
                
                # 매출액 처리 (억원 단위)
                revenue = partner.get('annual_revenue')
                if revenue:
                    revenue_text = f"{revenue // 100000000}억원"
                else:
                    revenue_text = ''
                ws.cell(row=row_idx, column=10, value=revenue_text)
                
                ws.cell(row=row_idx, column=11, value=partner.get('transaction_count', ''))
                
                # 상시근로자 처리
                workers = partner.get('permanent_workers')
                workers_text = f"{workers}명" if workers else ''
                ws.cell(row=row_idx, column=12, value=workers_text)
            
            # 컬럼 너비 자동 조정
            for column in ws.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                ws.column_dimensions[column_letter].width = adjusted_width
            
            # 파일을 메모리에 저장
            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
            
            conn.close()
            
            # 파일명 생성
            filename = f"partners_list_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            
            # 다운로드 응답
            return send_file(
                output,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=filename
            )
            
        except Exception as db_error:
            logging.error(f"협력사 데이터 조회 중 오류: {db_error}")
            # 더미 데이터로 대체
            wb = Workbook()
            ws = wb.active
            ws.title = "협력사 기준정보"
            
            # 헤더만 있는 빈 파일 생성
            headers = [
                '협력사명', '사업자번호', 'Class', '업종(대분류)', '업종(소분류)',
                '위험작업여부', '대표자성명', '주소', '평균연령', '매출액', 
                '거래차수', '상시근로자'
            ]
            
            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            header_align = Alignment(horizontal="center", vertical="center")
            
            for col_idx, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col_idx, value=header)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_align
            
            # 샘플 데이터 1행 추가
            sample_data = [
                '샘플 협력사', '123-45-67890', 'A', '제조업', '전자제품',
                '예', '김대표', '서울시 강남구', '35', '100억원', '5', '50명'
            ]
            for col_idx, value in enumerate(sample_data, 1):
                ws.cell(row=2, column=col_idx, value=value)
            
            # 컬럼 너비 조정
            for column in ws.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 30)
                ws.column_dimensions[column_letter].width = adjusted_width
            
            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
            
            filename = f"partners_list_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            
            return send_file(
                output,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=filename
            )
    
    except Exception as e:
        logging.error(f"협력사 엑셀 다운로드 중 오류: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return jsonify({"success": False, "message": str(e)}), 500

# ===== 협력사 삭제 API =====
@app.route('/api/partners/delete', methods=['POST'])
def delete_partners():
    try:
        data = request.get_json()
        business_numbers = data.get('business_numbers', [])
        
        if not business_numbers:
            return jsonify({"success": False, "message": "삭제할 협력사가 선택되지 않았습니다."}), 400
        
        # DB 연결
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        deleted_count = 0
        
        # 각 협력사를 삭제
        for business_number in business_numbers:
            # 실제 삭제 대신 soft delete 구현 (is_deleted 플래그)
            # 만약 테이블에 is_deleted 컬럼이 없다면 실제 삭제
            try:
                # 먼저 컬럼 존재 확인
                cursor.execute("PRAGMA table_info(partners_cache)")
                columns = [col[1] for col in cursor.fetchall()]
                
                if 'is_deleted' in columns:
                    # Soft delete
                    cursor.execute(
                        "UPDATE partners_cache SET is_deleted = 1 WHERE business_number = ?",
                        (business_number,)
                    )
                else:
                    # Hard delete
                    cursor.execute(
                        "DELETE FROM partners_cache WHERE business_number = ?",
                        (business_number,)
                    )
                
                if cursor.rowcount > 0:
                    deleted_count += 1
                    
            except Exception as e:
                logging.error(f"협력사 {business_number} 삭제 중 오류: {e}")
                continue
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "success": True,
            "deleted_count": deleted_count,
            "message": f"{deleted_count}개의 협력사가 삭제되었습니다."
        })
        
    except Exception as e:
        logging.error(f"협력사 삭제 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.after_request
def add_header(response):
    """응답 헤더 추가 - 캐시 무효화"""
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

if __name__ == "__main__":
    print("Flask 앱 시작 중...", flush=True)
    print(f"partner-accident 라우트 등록됨: {'/partner-accident' in [rule.rule for rule in app.url_map.iter_rules()]}", flush=True)
    app.run(host="0.0.0.0", port=5000, debug=True)