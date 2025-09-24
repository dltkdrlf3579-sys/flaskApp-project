-- 003_seed_sections.sql
-- Phase 4: init_db 해체 작업 3/4
-- 기본 섹션/초기 데이터 시드 (중복 삽입 방지 포함)

INSERT INTO section_config (board_type, section_key, section_name, section_order)
SELECT board_type, section_key, section_name, section_order
FROM (VALUES
    ('safety_instruction', 'basic_info', '기본정보', 1),
    ('safety_instruction', 'violation_info', '위반정보', 2),
    ('safety_instruction', 'additional', '추가기입정보', 3),
    ('accident', 'basic_info', '기본정보', 1),
    ('accident', 'accident_info', '사고정보', 2),
    ('accident', 'location_info', '장소정보', 3),
    ('accident', 'additional', '추가정보', 4),
    ('safe_workplace', 'basic_info', '기본정보', 1),
    ('safe_workplace', 'workplace_info', '작업장정보', 2),
    ('safe_workplace', 'safety_info', '안전정보', 3)
) AS seed(board_type, section_key, section_name, section_order)
WHERE NOT EXISTS (
    SELECT 1 FROM section_config sc
    WHERE sc.board_type = seed.board_type
      AND sc.section_key = seed.section_key
);

INSERT INTO follow_sop_sections (section_key, section_name, section_order, is_active)
SELECT seed.section_key, seed.section_name, seed.section_order, 1
FROM (VALUES
    ('basic_info', '기본정보', 1),
    ('violation_info', '위반정보', 2),
    ('additional', '추가기입정보', 3)
) AS seed(section_key, section_name, section_order)
WHERE NOT EXISTS (
    SELECT 1 FROM follow_sop_sections fs WHERE fs.section_key = seed.section_key
);

INSERT INTO safe_workplace_sections (section_key, section_name, section_order, is_active)
SELECT seed.section_key, seed.section_name, seed.section_order, 1
FROM (VALUES
    ('basic_info', '기본정보', 1),
    ('workplace_info', '작업장정보', 2),
    ('safety_info', '안전정보', 3)
) AS seed(section_key, section_name, section_order)
WHERE NOT EXISTS (
    SELECT 1 FROM safe_workplace_sections sws WHERE sws.section_key = seed.section_key
);

