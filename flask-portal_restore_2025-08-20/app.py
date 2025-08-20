import os
import logging
from flask import Flask, render_template, request, session, redirect, url_for, flash
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
        if partner_manager.should_sync():
            logging.info("협력사 데이터 동기화 시작...")
            if partner_manager.sync_partners_from_postgresql():
                logging.info("협력사 데이터 동기화 완료")
            else:
                logging.warning("협력사 데이터 동기화 실패")
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

@app.route("/partner/<business_number>")
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
    is_popup = request.args.get('popup') == 'true'
    
    return render_template('partner-detail.html', 
                         partner=partner, 
                         attachments=attachments,
                         menu=MENU_CONFIG, 
                         is_popup=is_popup)

@app.route("/verify-password", methods=["POST"])
def verify_password():
    """비밀번호 검증"""
    try:
        data = request.get_json()
        password = data.get('password')
        
        # config.ini에서 비밀번호 읽기
        admin_password = SETTINGS.get('SECURITY', 'admin_password', fallback='admin123')
        
        if password == admin_password:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "message": "비밀번호가 올바르지 않습니다."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/update-partner", methods=["POST"])
def update_partner():
    """협력사 정보 업데이트"""
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
        
        print(f"Connecting to database: {DB_PATH}")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 협력사 존재 여부 확인
        partner = partner_manager.get_partner_by_business_number(business_number)
        if not partner:
            from flask import jsonify
            return jsonify({"success": False, "message": "협력사를 찾을 수 없습니다."})
        
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
        from flask import jsonify
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
    try:
        return send_file(
            attachment['file_path'],
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