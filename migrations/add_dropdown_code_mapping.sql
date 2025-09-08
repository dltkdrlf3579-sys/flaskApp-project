-- 드롭다운 옵션 코드 매핑 테이블 생성
-- 코드-값 매핑 방식으로 드롭다운 옵션 관리

CREATE TABLE IF NOT EXISTS dropdown_option_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    column_key TEXT NOT NULL,           -- 어떤 컬럼의 옵션인지 (예: column11, column12)
    option_code TEXT NOT NULL,          -- 저장될 코드값 (예: STS001, STS002)
    option_value TEXT NOT NULL,         -- 화면에 표시될 값 (예: 진행중, 완료)
    display_order INTEGER DEFAULT 0,    -- 표시 순서
    is_active INTEGER DEFAULT 1,        -- 활성화 여부
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,                    -- 생성자 (추후 SSO 연동 시 사번)
    updated_by TEXT,                    -- 수정자 (추후 SSO 연동 시 사번)
    
    -- 복합 유니크 키: 같은 컬럼에서 코드는 중복될 수 없음
    UNIQUE(column_key, option_code)
);

-- 인덱스 생성 (성능 최적화)
CREATE INDEX IF NOT EXISTS idx_dropdown_column_key ON dropdown_option_codes(column_key);
CREATE INDEX IF NOT EXISTS idx_dropdown_active ON dropdown_option_codes(is_active);

-- 기존 데이터 마이그레이션을 위한 임시 테이블
CREATE TABLE IF NOT EXISTS dropdown_migration_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    column_key TEXT,
    old_value TEXT,           -- 기존 JSON 값
    new_codes TEXT,           -- 새로운 코드 매핑 정보
    migration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT              -- 'pending', 'completed', 'failed'
);

-- 샘플 데이터 삽입 (예시)
-- INSERT INTO dropdown_option_codes (column_key, option_code, option_value, display_order) VALUES
-- ('accident_status', 'STS001', '진행중', 1),
-- ('accident_status', 'STS002', '완료', 2),
-- ('accident_status', 'STS003', '취소', 3),
-- ('accident_type', 'TYP001', '추락', 1),
-- ('accident_type', 'TYP002', '충돌', 2),
-- ('accident_type', 'TYP003', '전도', 3);