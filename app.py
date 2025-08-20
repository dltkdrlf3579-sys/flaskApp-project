import os
import logging
from flask import Flask, render_template, request, jsonify
from werkzeug.serving import run_simple
from config.menu import MENU_CONFIG
from database_config import db_config, partner_manager
import sqlite3
import math

app = Flask(__name__)

# 설정 파일에서 환경 설정 로드
app.secret_key = db_config.config.get('DEFAULT', 'SECRET_KEY')
app.debug = db_config.config.getboolean('DEFAULT', 'DEBUG')

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
        try:
            logging.info("협력사 데이터 동기화 시작...")
            if partner_manager.sync_partners_from_external_db():
                logging.info("협력사 데이터 동기화 완료")
            else:
                logging.warning("협력사 데이터 동기화 실패 - 샘플 데이터 사용")
                init_sample_data()
        except Exception as e:
            logging.warning(f"동기화 중 오류 발생: {e} - 샘플 데이터 사용")
            init_sample_data()
    else:
        # 외부 DB가 비활성화된 경우 샘플 데이터 생성
        init_sample_data()

def init_sample_data():
    """외부 DB 없을 때 샘플 데이터 생성"""
    conn = partner_manager.db_config.get_sqlite_connection()
    cursor = conn.cursor()
    
    # 이미 데이터가 있는지 확인
    cursor.execute("SELECT COUNT(*) FROM partners_cache")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return
    
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
        regular_workers = random.randint(50, 50000)
        business_type_major = random.choice(business_types)
        
        selected_major = random.choice(business_types)
        minor_count = random.randint(1, 3)
        selected_minors = random.sample(business_types_data[selected_major], min(minor_count, len(business_types_data[selected_major])))
        business_type_minor = ', '.join(selected_minors)
        business_type = f"{business_type_major} > {business_type_minor}"
        establishment_date = f"{random.randint(1980, 2020)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
        capital_amount = random.randint(1, 1000) * 100000000
        annual_revenue = random.randint(10, 10000) * 100000000
        main_products = random.choice(products)
        certification = random.choice(certifications)
        safety_rating = random.choice(safety_ratings)
        contact_person = f"담당자{i+1:03d}"
        phone_number = f"02-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}"
        email = f"contact{i+1:03d}@company{i+1:03d}.co.kr"
        
        cursor.execute('''
            INSERT INTO partners_cache (
                business_number, company_name, representative, regular_workers,
                business_type, business_type_major, business_type_minor, establishment_date, 
                capital_amount, annual_revenue, main_products, certification, 
                safety_rating, contact_person, phone_number, email
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            business_number, company_name, representative, regular_workers,
            business_type, business_type_major, business_type_minor, establishment_date,
            capital_amount, annual_revenue, main_products, certification,
            safety_rating, contact_person, phone_number, email
        ))
        
        # 일부 협력사에 샘플 첨부파일 추가
        if i < 10:
            sample_files = [
                ('사업자등록증.pdf', 2.07 * 1024 * 1024, '사업자등록증'),
                ('회사소개서.docx', 192.39 * 1024, '회사소개서'),
                ('인증서.png', 201.46 * 1024, '인증기관')
            ]
            
            num_files = random.randint(1, 3)
            for j in range(num_files):
                file_info = random.choice(sample_files)
                cursor.execute('''
                    INSERT INTO partner_attachments (
                        business_number, file_name, file_path, file_size, description
                    ) VALUES (?, ?, ?, ?, ?)
                ''', (
                    business_number,
                    file_info[0],
                    f'/uploads/{file_info[0]}',
                    int(file_info[1]),
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
    return render_template("index.html", menu=MENU_CONFIG)

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
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    # 검색 조건
    filters = {
        'company_name': request.args.get('company_name', '').strip(),
        'business_number': request.args.get('business_number', '').strip(),
        'accident_date_start': request.args.get('accident_date_start', '').strip(),
        'accident_date_end': request.args.get('accident_date_end', '').strip()
    }
    
    # 더미 데이터 생성
    import random
    import datetime
    
    # 더미 사고 데이터
    dummy_accidents = []
    for i in range(50):  # 50개 더미 데이터
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
            'accident_content': f'사고내용{i+1}',
            'responsible_company_1': f'협력사{(i % 20) + 1}',
            'responsible_company_1_business_number': f'{1000000000 + i * 11111}',
            'responsible_company_2': f'협력사{(i % 15) + 1}' if i % 3 == 0 else None,
            'responsible_company_2_business_number': f'{2000000000 + i * 22222}' if i % 3 == 0 else None,
            'column1': f'컬럼1-{i+1}',
            'column2': f'컬럼2-{i+1}',
            'column3': f'컬럼3-{i+1}',
            'column4': f'컬럼4-{i+1}',
            'column5': f'컬럼5-{i+1}',
            'column6': f'컬럼6-{i+1}',
            'column7': f'컬럼7-{i+1}',
            'column8': f'컬럼8-{i+1}',
            'column9': f'컬럼9-{i+1}',
            'column10': f'컬럼10-{i+1}',
        })
    
    # 검색 필터링 적용
    filtered_accidents = dummy_accidents
    
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
    
    return render_template('partner-accident.html',
                         accidents=accidents,
                         total_count=total_count,
                         pagination=pagination,
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
                         is_popup=is_popup)

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
    
    # 해당 ID의 사고 찾기
    accident = None
    for acc in dummy_accidents:
        if acc['id'] == accident_id:
            accident = acc
            break
    
    if not accident:
        logging.warning(f"사고를 찾을 수 없습니다: {accident_id}")
        return "사고 정보를 찾을 수 없습니다.", 404
    
    # 저장된 상세내용이 있는지 확인
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
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
    
    conn.close()
    
    # 딕셔너리를 객체처럼 사용할 수 있도록 변환
    class DictAsAttr:
        def __init__(self, d):
            for k, v in d.items():
                setattr(self, k, v)
    
    accident = DictAsAttr(accident)
    
    logging.info(f"사고 {accident_id} ({accident.accident_name}) 상세 페이지 로드")
    
    # 팝업 모드인지 확인
    is_popup = request.args.get('popup') == '1'
    
    return render_template('accident-detail.html', 
                         accident=accident,
                         attachments=attachments,
                         menu=MENU_CONFIG, 
                         is_popup=is_popup)

@app.route("/verify-password", methods=["POST"])
def verify_password():
    """비밀번호 검증"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data received"}), 400
            
        password = data.get('password')
        if not password:
            return jsonify({"success": False, "message": "Password not provided"}), 400
        
        # config.ini에서 비밀번호 읽기
        admin_password = db_config.config.get('DEFAULT', 'EDIT_PASSWORD')
        
        if password == admin_password:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "message": "비밀번호가 올바르지 않습니다."})
    except Exception as e:
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
        deleted_attachments = json.loads(request.form.get('deleted_attachments', '[]'))
        attachment_data = json.loads(request.form.get('attachment_data', '[]'))
        files = request.files.getlist('files')
        
        print(f"Accident Number: {accident_number}")
        print(f"Files count: {len(files)}")
        print(f"Attachment data: {attachment_data}")
        
        # 사고 존재 여부 확인 (사고번호 형식 검증)
        if not accident_number or not accident_number.startswith('K'):
            from flask import jsonify
            return jsonify({"success": False, "message": "사고를 찾을 수 없습니다."})
        
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
    """첨부파일 다운로드"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    attachment = conn.execute(
        "SELECT * FROM partner_attachments WHERE id = ?", 
        (attachment_id,)
    ).fetchone()
    conn.close()
    
    if not attachment:
        return "File not found", 404
    
    from flask import send_file
    import os
    
    # 실제 파일 경로 구성 (uploads 폴더 기준)
    actual_file_path = os.path.join(os.getcwd(), 'uploads', attachment['file_name'])
    
    try:
        return send_file(
            actual_file_path,
            as_attachment=True,
            download_name=attachment['file_name']
        )
    except FileNotFoundError:
        return "File not found on disk", 404

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)