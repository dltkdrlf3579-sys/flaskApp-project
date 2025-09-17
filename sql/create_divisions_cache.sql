-- Create divisions_cache table for division popup functionality
CREATE TABLE IF NOT EXISTS divisions_cache (
    division_code VARCHAR(50) PRIMARY KEY,
    division_name VARCHAR(255) NOT NULL,
    parent_division_code VARCHAR(50),
    division_level INTEGER DEFAULT 1,
    division_manager VARCHAR(100),
    division_location VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better search performance
CREATE INDEX IF NOT EXISTS idx_divisions_name ON divisions_cache(division_name);
CREATE INDEX IF NOT EXISTS idx_divisions_parent ON divisions_cache(parent_division_code);
CREATE INDEX IF NOT EXISTS idx_divisions_level ON divisions_cache(division_level);

-- Insert sample test data
INSERT INTO divisions_cache (division_code, division_name, parent_division_code, division_level, division_manager, division_location) VALUES
('DIV001', '경영지원본부', NULL, 1, '김철수', '본사 3층'),
('DIV002', '영업본부', NULL, 1, '이영희', '본사 5층'),
('DIV003', '생산본부', NULL, 1, '박민수', '공장 A동'),
('DIV004', '연구개발본부', NULL, 1, '최진우', '연구소 1동'),
('DIV005', '품질관리본부', NULL, 1, '정수진', '공장 B동'),
('DIV001-01', '인사팀', 'DIV001', 2, '홍길동', '본사 3층'),
('DIV001-02', '재무팀', 'DIV001', 2, '김재무', '본사 3층'),
('DIV001-03', '총무팀', 'DIV001', 2, '이총무', '본사 2층'),
('DIV002-01', '국내영업팀', 'DIV002', 2, '박영업', '본사 5층'),
('DIV002-02', '해외영업팀', 'DIV002', 2, '최해외', '본사 5층'),
('DIV003-01', '제1생산팀', 'DIV003', 2, '김생산', '공장 A동'),
('DIV003-02', '제2생산팀', 'DIV003', 2, '이제조', '공장 A동'),
('DIV003-03', '설비관리팀', 'DIV003', 2, '박설비', '공장 C동'),
('DIV004-01', '기초연구팀', 'DIV004', 2, '정연구', '연구소 1동'),
('DIV004-02', '응용개발팀', 'DIV004', 2, '최개발', '연구소 2동'),
('DIV005-01', '품질보증팀', 'DIV005', 2, '김품질', '공장 B동'),
('DIV005-02', '품질검사팀', 'DIV005', 2, '이검사', '공장 B동')
ON CONFLICT (division_code) DO UPDATE SET
    division_name = EXCLUDED.division_name,
    parent_division_code = EXCLUDED.parent_division_code,
    division_level = EXCLUDED.division_level,
    division_manager = EXCLUDED.division_manager,
    division_location = EXCLUDED.division_location,
    updated_at = CURRENT_TIMESTAMP;