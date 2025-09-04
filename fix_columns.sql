-- Fix broken column names in accident_column_config
UPDATE accident_column_config SET column_name = '귀책담당자(임직원)' WHERE column_key = 'incharge_person';
UPDATE accident_column_config SET column_name = '귀책담당자 ID' WHERE column_key = 'incharge_person_id';
UPDATE accident_column_config SET column_name = '귀책담당자 부서' WHERE column_key = 'incharge_person_dept';
UPDATE accident_column_config SET column_name = '부상자명단' WHERE column_key = 'injured_person';

-- Verify updates
SELECT column_key, column_name FROM accident_column_config WHERE column_key IN ('incharge_person', 'incharge_person_id', 'incharge_person_dept', 'injured_person');