-- =====================================
-- Follow SOP 관련 테이블 생성
-- =====================================

-- 1. followsop 메인 테이블
CREATE TABLE IF NOT EXISTS followsop (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_req_no TEXT UNIQUE NOT NULL,  -- 고유 번호 (작업요청번호)
    custom_data TEXT,  -- 동적 컬럼 데이터 (JSON)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    updated_by TEXT
);

-- 2. followsop 컬럼 설정 테이블
CREATE TABLE IF NOT EXISTS followsop_column_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    column_key TEXT UNIQUE NOT NULL,
    column_name TEXT NOT NULL,
    column_type TEXT DEFAULT 'text',
    column_order INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    dropdown_options TEXT,
    table_name TEXT,
    table_type TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_required INTEGER DEFAULT 0,
    dropdown_values TEXT,
    tab TEXT,  -- 섹션 키
    is_deleted INTEGER DEFAULT 0,
    column_span INTEGER DEFAULT 1
);

-- 3. followsop 상세 내용 테이블
CREATE TABLE IF NOT EXISTS followsop_details (
    work_req_no TEXT PRIMARY KEY,
    detailed_content TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. followsop 첨부파일 테이블
CREATE TABLE IF NOT EXISTS followsop_attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_req_no TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER,
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    uploaded_by TEXT,
    FOREIGN KEY (work_req_no) REFERENCES followsop(work_req_no)
);

-- 5. followsop 캐시 테이블
CREATE TABLE IF NOT EXISTS followsop_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_req_no TEXT UNIQUE,
    custom_data TEXT,
    sync_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================
-- Full Process 관련 테이블 생성
-- =====================================

-- 1. fullprocess 메인 테이블
CREATE TABLE IF NOT EXISTS fullprocess (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fullprocess_number TEXT UNIQUE NOT NULL,  -- 고유 번호
    custom_data TEXT,  -- 동적 컬럼 데이터 (JSON)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    updated_by TEXT
);

-- 2. fullprocess 컬럼 설정 테이블
CREATE TABLE IF NOT EXISTS fullprocess_column_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    column_key TEXT UNIQUE NOT NULL,
    column_name TEXT NOT NULL,
    column_type TEXT DEFAULT 'text',
    column_order INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    dropdown_options TEXT,
    table_name TEXT,
    table_type TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_required INTEGER DEFAULT 0,
    dropdown_values TEXT,
    tab TEXT,  -- 섹션 키
    is_deleted INTEGER DEFAULT 0,
    column_span INTEGER DEFAULT 1
);

-- 3. fullprocess 상세 내용 테이블
CREATE TABLE IF NOT EXISTS fullprocess_details (
    fullprocess_number TEXT PRIMARY KEY,
    detailed_content TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. fullprocess 첨부파일 테이블
CREATE TABLE IF NOT EXISTS fullprocess_attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fullprocess_number TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER,
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    uploaded_by TEXT,
    FOREIGN KEY (fullprocess_number) REFERENCES fullprocess(fullprocess_number)
);

-- 5. fullprocess 캐시 테이블
CREATE TABLE IF NOT EXISTS fullprocess_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fullprocess_number TEXT UNIQUE,
    custom_data TEXT,
    sync_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================
-- 섹션 설정 초기 데이터 (section_config 테이블)
-- =====================================

-- Follow SOP 섹션 추가
INSERT OR IGNORE INTO section_config (board_type, section_key, section_name, section_order, is_active)
VALUES 
    ('followsop', 'basic', '기본정보', 1, 1),
    ('followsop', 'detail', '상세정보', 2, 1);

-- Full Process 섹션 추가
INSERT OR IGNORE INTO section_config (board_type, section_key, section_name, section_order, is_active)
VALUES 
    ('fullprocess', 'basic', '기본정보', 1, 1),
    ('fullprocess', 'detail', '상세정보', 2, 1);

-- =====================================
-- 인덱스 생성
-- =====================================

-- followsop 인덱스
CREATE INDEX IF NOT EXISTS idx_followsop_work_req_no ON followsop(work_req_no);
CREATE INDEX IF NOT EXISTS idx_followsop_created_at ON followsop(created_at);
CREATE INDEX IF NOT EXISTS idx_followsop_attachments_work_req_no ON followsop_attachments(work_req_no);

-- fullprocess 인덱스
CREATE INDEX IF NOT EXISTS idx_fullprocess_number ON fullprocess(fullprocess_number);
CREATE INDEX IF NOT EXISTS idx_fullprocess_created_at ON fullprocess(created_at);
CREATE INDEX IF NOT EXISTS idx_fullprocess_attachments_number ON fullprocess_attachments(fullprocess_number);