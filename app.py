import os
from flask import Flask, render_template, request, session, redirect, url_for, flash
from werkzeug.serving import run_simple
from config.menu import MENU_CONFIG
import sqlite3
import math

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'default-secret-key-for-dev')

DB_PATH = os.environ.get('DB_PATH', 'portal.db')
PASSWORD = os.environ.get('EDIT_PASSWORD', 'admin123')

def init_db():
    """메뉴 설정의 소메뉴를 DB로 시드 (없을 때만)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            title TEXT,
            content TEXT
        )
    ''')
    
    # 기존 협력사 테이블 삭제 후 새로 생성 (스키마 변경)
    cursor.execute('DROP TABLE IF EXISTS partners')
    cursor.execute('''
        CREATE TABLE partners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            business_number TEXT,
            representative TEXT,
            regular_workers INTEGER,
            business_type TEXT,
            business_type_major TEXT,
            business_type_minor TEXT,
            establishment_date TEXT,
            capital_amount BIGINT,
            annual_revenue BIGINT,
            main_products TEXT,
            certification TEXT,
            safety_rating TEXT,
            contact_person TEXT,
            phone_number TEXT,
            email TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
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
    
    # 협력사 샘플 데이터 생성 (새 테이블이므로 항상 비어있음)
    cursor.execute("SELECT COUNT(*) FROM partners")
    if cursor.fetchone()[0] == 0:
        import random
        
        # 기본 샘플 데이터
        base_companies = [
            '삼성전자', 'LG전자', '현대자동차', 'SK하이닉스', 'POSCO홀딩스',
            '네이버', '카카오', '신한금융지주', '한국전력공사', 'KT',
            'LG화학', '현대중공업', '한화솔루션', 'SK텔레콤', '기아',
            '롯데케미칼', 'S-Oil', 'GS칼텍스', '두산에너빌리티', 'HD현대중공업'
        ]
        
        # 업종 대분류/소분류 정의
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
            if i < 20:  # 처음 20개는 실제 회사명 기반
                company_name = f"{base_companies[i % len(base_companies)]}(주)"
                business_number = f"{100 + i:03d}-81-{random.randint(10000, 99999):05d}"
            else:  # 나머지는 가상 회사명
                company_name = f"협력업체{i-19:03d}(주)"
                business_number = f"{random.randint(100, 999)}-81-{random.randint(10000, 99999):05d}"
            
            representative = f"대표자{i+1:03d}"
            regular_workers = random.randint(50, 50000)
            business_type_major = random.choice(business_types)
            
            # 소분류는 1~3개 랜덤 선택 (콤마로 구분)
            selected_major = random.choice(business_types)
            minor_count = random.randint(1, 3)
            selected_minors = random.sample(business_types_data[selected_major], min(minor_count, len(business_types_data[selected_major])))
            business_type_minor = ', '.join(selected_minors)
            business_type = f"{business_type_major} > {business_type_minor}"
            establishment_date = f"{random.randint(1980, 2020)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
            capital_amount = random.randint(1, 1000) * 100000000  # 1억~1000억
            annual_revenue = random.randint(10, 10000) * 100000000  # 10억~1조
            main_products = random.choice(products)
            certification = random.choice(certifications)
            safety_rating = random.choice(safety_ratings)
            contact_person = f"담당자{i+1:03d}"
            phone_number = f"02-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}"
            email = f"contact{i+1:03d}@company{i+1:03d}.co.kr"
            
            cursor.execute('''
                INSERT INTO partners (
                    company_name, business_number, representative, regular_workers,
                    business_type, business_type_major, business_type_minor, establishment_date, 
                    capital_amount, annual_revenue, main_products, certification, 
                    safety_rating, contact_person, phone_number, email
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                company_name, business_number, representative, regular_workers,
                business_type, business_type_major, business_type_minor, establishment_date,
                capital_amount, annual_revenue, main_products, certification,
                safety_rating, contact_person, phone_number, email
            ))
    
    conn.commit()
    conn.close()

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
    company_name = request.args.get('company_name', '').strip()
    business_number = request.args.get('business_number', '').strip()
    business_type_major = request.args.get('business_type_major', '').strip()
    business_type_minor = request.args.get('business_type_minor', '').strip()
    workers_min = request.args.get('workers_min', type=int)
    workers_max = request.args.get('workers_max', type=int)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # 기본 쿼리
    query = "SELECT * FROM partners WHERE 1=1"
    params = []
    
    # 검색 조건 추가
    if company_name:
        query += " AND company_name LIKE ?"
        params.append(f"%{company_name}%")
    
    if business_number:
        query += " AND business_number LIKE ?"
        params.append(f"%{business_number}%")
    
    if business_type_major:
        query += " AND business_type_major = ?"
        params.append(business_type_major)
    
    if business_type_minor:
        query += " AND business_type_minor LIKE ?"
        params.append(f"%{business_type_minor}%")
    
    if workers_min is not None:
        query += " AND regular_workers >= ?"
        params.append(workers_min)
    
    if workers_max is not None:
        query += " AND regular_workers <= ?"
        params.append(workers_max)
    
    # 전체 개수 조회
    count_query = query.replace("SELECT *", "SELECT COUNT(*)")
    total_count = conn.execute(count_query, params).fetchone()[0]
    
    # 페이지네이션 적용
    query += " ORDER BY company_name LIMIT ? OFFSET ?"
    params.extend([per_page, (page - 1) * per_page])
    
    partners = conn.execute(query, params).fetchall()
    conn.close()
    
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

@app.route("/<path:url>/edit", methods=["GET", "POST"])
def page_edit(url):
    if not session.get('edit_mode'):
        flash("편집 권한이 없습니다.", "error")
        return redirect(url_for('page_view', url=url))
    
    conn = sqlite3.connect(DB_PATH)
    page = conn.execute("SELECT * FROM pages WHERE url = ?", (url,)).fetchone()
    conn.close()
    
    if not page:
        return "Page not found", 404
    
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        
        if not title:
            title = "제목을 입력하세요."
        
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE pages SET title = ?, content = ? WHERE url = ?", 
                    (title, content, url))
        conn.commit()
        conn.close()
        
        flash("저장되었습니다.", "success")
        return redirect(url_for('page_view', url=url))
    
    return render_template("edit.html", 
                         page={'url': page[1], 'title': page[2], 'content': page[3]},
                         menu=MENU_CONFIG)

@app.route("/unlock", methods=["GET", "POST"])
def unlock():
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == PASSWORD:
            session['edit_mode'] = True
            flash("편집모드가 활성화되었습니다.", "success")
            return redirect(url_for('index'))
        else:
            flash("비밀번호가 올바르지 않습니다.", "error")
    
    return render_template("unlock.html", menu=MENU_CONFIG)

@app.route("/lock")
def lock():
    session.pop('edit_mode', None)
    flash("편집모드를 종료했습니다.", "info")
    return redirect(url_for('index'))

@app.route("/partner/<int:partner_id>")
def partner_detail(partner_id):
    """협력사 상세정보 페이지"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    partner = conn.execute("SELECT * FROM partners WHERE id = ?", (partner_id,)).fetchone()
    conn.close()
    
    if not partner:
        return "협력사 정보를 찾을 수 없습니다.", 404
    
    return render_template('partner-detail.html', partner=partner, menu=MENU_CONFIG)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)