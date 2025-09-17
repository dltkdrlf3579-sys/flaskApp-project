-- 기준정보 변경요청 테이블에 컬럼 추가
-- PostgreSQL용 스크립트

-- 1. 먼저 테이블 구조 확인
SELECT column_name, data_type, character_maximum_length, is_nullable
FROM information_schema.columns
WHERE table_name = 'partner_change_requests'
ORDER BY ordinal_position;

-- 2. other_info 컬럼 추가 (TEXT 타입)
ALTER TABLE partner_change_requests
ADD COLUMN IF NOT EXISTS other_info TEXT;

-- 3. final_check_date 컬럼 추가 (DATE 타입)
ALTER TABLE partner_change_requests
ADD COLUMN IF NOT EXISTS final_check_date DATE;

-- 4. 추가된 컬럼 확인
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'partner_change_requests'
  AND column_name IN ('other_info', 'final_check_date');

-- 5. 샘플 데이터로 테스트 (옵션)
/*
UPDATE partner_change_requests
SET other_info = '테스트 비고 정보',
    final_check_date = '2024-12-17'
WHERE id = (SELECT id FROM partner_change_requests LIMIT 1);
*/

-- 6. 결과 확인
SELECT id, other_info, final_check_date
FROM partner_change_requests
LIMIT 5;