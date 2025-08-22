import os
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify
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

@app.route("/<path:url>")
def page_view(url):
    # 협력사 기준정보 페이지 특별 처리
    if url == 'partner-standards':
        return partner_standards()
    
    # 협력사 사고 페이지 특별 처리
    if url == 'partner-accident':
        return partner_accident()
    
    conn = sqlite3.connect(DB_PATH)
    page = conn.execute("SELECT * FROM pages WHERE url = ?", (url,)).fetchone()
    conn.close()
    
    if not page:
        return "Page not found", 404
    
    return render_template("page.html", 
                         page={'url': page[1], 'title': page[2], 'content': page[3]},
                         menu=MENU_CONFIG)

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
    # 확실히 이 함수가 호출되는지 확인
    with open('PARTNER_ACCIDENT_CALLED.txt', 'w') as f:
        f.write('YES! Called at ' + str(datetime.now()))
    
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
    
    # 사고 데이터 조회 (운영 환경 고려)
    import random
    import datetime
    
    # 사고 데이터 조회 - 단순화
    all_accidents = []
    
    
    # 1. 항상 로컬 DB에서 먼저 조회 (등록된 사고)  
    try:
        local_accidents_rows = conn.execute("""
            SELECT * FROM accidents_cache 
            ORDER BY accident_date DESC, accident_number DESC
        """).fetchall()
        
        # 디버그용 - 첫 번째 사고로 테스트 항목 추가
        if len(local_accidents_rows) > 0:
            all_accidents.append({
                'id': 99999,
                'accident_number': f'DEBUG_{len(local_accidents_rows)}',
                'accident_name': f'디버그: {len(local_accidents_rows)}개 로컬 사고',
                'accident_date': '2025-12-31',
                'accident_grade': '테스트',
                'accident_type': '테스트',
                'disaster_type': '테스트',
                'disaster_form': '테스트',
                'workplace': '테스트',
                'building': '테스트',
                'floor': '테스트',
                'detail_location': '테스트',
                'time': '00:00',
                'day_of_week': '월',
                'accident_content': '테스트',
                'responsible_company_1': '테스트',
                'responsible_company_1_business_number': '0000000000',
                'responsible_company_2': None,
                'responsible_company_2_business_number': None,
                'custom_data': '{}'
            })
        
        for row in local_accidents_rows:
            accident = dict(row)
            # ID 확인 및 설정
            if 'id' not in accident:
                accident['id'] = len(all_accidents) + 1000  # 충돌 방지를 위해 1000부터 시작
            # 필수 필드 채우기
            accident['accident_name'] = accident.get('accident_name') or f"사고_{accident['accident_number']}"
            accident['custom_data'] = accident.get('custom_data', '{}')
            all_accidents.append(accident)
    except Exception as e:
        # 오류 발생 시 더미 데이터에 오류 메시지 추가
        all_accidents.append({
            'id': 88888,
            'accident_number': 'ERROR',
            'accident_name': f'오류: {str(e)}',
            'accident_date': '2025-12-31',
            'accident_grade': 'ERROR',
            'custom_data': '{}'
        })
        logging.error(f"로컬 사고 데이터 조회 실패: {e}")
    
    # 디버그: 로컬 사고 로드 후 상태 확인
    with open('AFTER_LOCAL_LOAD.txt', 'w') as f:
        f.write(f'Local accidents loaded: {len(all_accidents)} items\n')
        if all_accidents:
            f.write(f'First accident: {all_accidents[0]}\n')
    
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
        
        # 로컬 사고가 먼저 나오도록 순서 조정
        all_accidents = all_accidents + dummy_accidents
        
        logging.info(f"더미 데이터 50개 추가됨")
    
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
    dynamic_columns = conn.execute("""
        SELECT * FROM accident_column_config 
        WHERE is_active = 1 
        ORDER BY column_order
    """).fetchall()
    
    conn.close()
    
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
    
    logging.info(f"동적 컬럼 {len(dynamic_columns)}개 로드됨")
    for col in dynamic_columns:
        logging.info(f"  - {col['column_name']} ({col['column_type']})")
    
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
        
        detailed_content = request.form.get('detailed_content')
        custom_data = json.loads(request.form.get('custom_data', '{}'))  # 동적 컬럼만
        attachment_data = json.loads(request.form.get('attachment_data', '[]'))
        files = request.files.getlist('files')
        
        logging.info(f"등록 요청 받음 - 상세내용: {detailed_content[:50] if detailed_content else 'None'}")
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
        
        # 1. 기본 사고 정보 등록 (동적 컬럼만 - 기본정보는 시스템에서 자동 처리)
        # 필요한 컬럼들이 없는 경우 추가
        cursor.execute("PRAGMA table_info(accidents_cache)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'accident_number' not in columns:
            cursor.execute("ALTER TABLE accidents_cache ADD COLUMN accident_number TEXT")
        if 'accident_name' not in columns:
            cursor.execute("ALTER TABLE accidents_cache ADD COLUMN accident_name TEXT")
        if 'custom_data' not in columns:
            cursor.execute("ALTER TABLE accidents_cache ADD COLUMN custom_data TEXT")
        
        cursor.execute("""
            INSERT INTO accidents_cache (
                accident_number, 
                accident_name,
                accident_date,
                custom_data,
                business_number
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            accident_number,
            f"사고_{accident_number}",  # 기본 사고명
            today.strftime('%Y-%m-%d'),  # 오늘 날짜
            json.dumps(custom_data),
            "DIRECT-ENTRY"  # 수기입력 표시
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
    return render_template('admin-accident-columns.html')

@app.route("/admin/menu-settings")
def admin_menu_settings():
    """메뉴 설정 페이지"""
    return render_template('admin-menu-settings.html')

@app.route("/admin/permission-settings")
def admin_permission_settings():
    """권한 설정 페이지"""
    return render_template('admin-permission-settings.html')

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
        cursor.execute("SELECT * FROM accident_column_config WHERE id = ?", (column_id,))
        column = cursor.fetchone()
        if not column:
            return jsonify({"success": False, "message": "컬럼을 찾을 수 없습니다."}), 404
        
        # 업데이트할 필드 준비
        update_fields = []
        params = []
        
        if 'column_name' in data:
            update_fields.append("column_name = ?")
            params.append(data['column_name'])
        
        if 'column_type' in data:
            update_fields.append("column_type = ?")
            params.append(data['column_type'])
        
        if 'is_active' in data:
            update_fields.append("is_active = ?")
            params.append(1 if data['is_active'] else 0)
        
        if 'dropdown_options' in data:
            import json
            dropdown_options = json.dumps(data['dropdown_options'], ensure_ascii=False) if data['dropdown_options'] else None
            update_fields.append("dropdown_options = ?")
            params.append(dropdown_options)
        
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

@app.route("/api/accident-columns/<int:column_id>", methods=["DELETE"])
def delete_accident_column(column_id):
    """사고 페이지 동적 컬럼 삭제 (실제로는 비활성화)"""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10.0)  # timeout 추가
        cursor = conn.cursor()
        
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

if __name__ == "__main__":
    print("Flask 앱 시작 중...", flush=True)
    print(f"partner-accident 라우트 등록됨: {'/partner-accident' in [rule.rule for rule in app.url_map.iter_rules()]}", flush=True)
    app.run(host="0.0.0.0", port=5000, debug=True)