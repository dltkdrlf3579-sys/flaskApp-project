-- 안전한 일터 초기 컬럼 설정
INSERT INTO safe_workplace_column_config (column_key, column_name, column_type, column_order, tab, column_span, is_active)
VALUES
-- 기본정보 섹션
('company_name', '협력사명', 'text', 1, 'basic_info', 2, 1),
('business_number', '사업자번호', 'text', 2, 'basic_info', 2, 1),
('inspector_name', '점검자', 'text', 3, 'basic_info', 2, 1),
('inspection_date', '점검일', 'date', 4, 'basic_info', 2, 1),
('work_location', '작업장소', 'text', 5, 'basic_info', 2, 1),
('work_type', '작업종류', 'dropdown', 6, 'basic_info', 2, 1),
('worker_count', '작업인원', 'text', 7, 'basic_info', 2, 1),
('work_time', '작업시간', 'text', 8, 'basic_info', 2, 1),
('safety_equipment', '안전장비', 'text', 9, 'basic_info', 2, 1),
('hazard_level', '위험도', 'dropdown', 10, 'basic_info', 2, 1),
('safety_score', '안전점수', 'text', 11, 'basic_info', 2, 1),
('improvement_needed', '개선필요사항', 'textarea', 12, 'basic_info', 8, 1),
('remarks', '비고', 'textarea', 13, 'basic_info', 8, 1);

-- 작업종류 드롭다운 옵션 설정
UPDATE safe_workplace_column_config
SET dropdown_options = '[
    {"value": "construction", "label": "건설작업"},
    {"value": "electrical", "label": "전기작업"},
    {"value": "chemical", "label": "화학물질 취급"},
    {"value": "height", "label": "고소작업"},
    {"value": "confined", "label": "밀폐공간작업"}
]'
WHERE column_key = 'work_type';

-- 위험도 드롭다운 옵션 설정
UPDATE safe_workplace_column_config
SET dropdown_options = '[
    {"value": "low", "label": "낮음"},
    {"value": "medium", "label": "보통"},
    {"value": "high", "label": "높음"},
    {"value": "critical", "label": "매우높음"}
]'
WHERE column_key = 'hazard_level';