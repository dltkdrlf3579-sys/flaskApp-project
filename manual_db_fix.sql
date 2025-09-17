-- Full Process custom_data 수동 변환 스크립트
-- 평면 데이터를 JSON 구조로 변환

-- 1. 먼저 현재 데이터 확인
SELECT
    fullprocess_number,
    custom_data::jsonb ? 'scre223_item_1' as has_flat_scre223,
    custom_data::jsonb ? 'test224_item_1' as has_flat_test224,
    custom_data::jsonb ? 'test225_item_1' as has_flat_test225,
    custom_data::jsonb ? 'tbm_helmet_check' as has_flat_tbm,
    custom_data::jsonb ? 'safety_procedure_follow' as has_flat_safety,
    custom_data::jsonb ? 'quality_standard_comply' as has_flat_quality,
    jsonb_pretty(custom_data::jsonb) as current_data
FROM full_process
WHERE custom_data IS NOT NULL
LIMIT 5;

-- 2. 변환이 필요한 레코드 찾기
SELECT
    fullprocess_number,
    jsonb_object_keys(custom_data::jsonb) as keys
FROM full_process
WHERE custom_data IS NOT NULL
    AND (
        custom_data::jsonb ? 'scre223_item_1' OR
        custom_data::jsonb ? 'scre223_item_2' OR
        custom_data::jsonb ? 'scre223_item_3' OR
        custom_data::jsonb ? 'test224_item_1' OR
        custom_data::jsonb ? 'test224_item_2' OR
        custom_data::jsonb ? 'test225_item_1' OR
        custom_data::jsonb ? 'test225_item_2' OR
        custom_data::jsonb ? 'test225_item_3' OR
        custom_data::jsonb ? 'test225_item_4' OR
        custom_data::jsonb ? 'tbm_helmet_check' OR
        custom_data::jsonb ? 'tbm_safety_brief' OR
        custom_data::jsonb ? 'tbm_ppe_status' OR
        custom_data::jsonb ? 'tbm_hazard_id' OR
        custom_data::jsonb ? 'safety_procedure_follow' OR
        custom_data::jsonb ? 'safety_barrier_check' OR
        custom_data::jsonb ? 'safety_emergency_prep' OR
        custom_data::jsonb ? 'quality_standard_comply' OR
        custom_data::jsonb ? 'quality_doc_complete' OR
        custom_data::jsonb ? 'quality_test_result'
    );

-- 3. 실제 변환 (주의: 이 쿼리는 데이터를 변경합니다!)
-- 먼저 SELECT로 확인 후 UPDATE 실행하세요

-- 3-1. 변환될 내용 미리보기
WITH transformed AS (
    SELECT
        fullprocess_number,
        custom_data::jsonb as original,
        -- 기존 데이터에서 scoring 필드 제외한 것들
        (custom_data::jsonb - ARRAY[
            'scre223_item_1', 'scre223_item_2', 'scre223_item_3',
            'test224_item_1', 'test224_item_2',
            'test225_item_1', 'test225_item_2', 'test225_item_3', 'test225_item_4',
            'tbm_helmet_check', 'tbm_safety_brief', 'tbm_ppe_status', 'tbm_hazard_id',
            'safety_procedure_follow', 'safety_barrier_check', 'safety_emergency_prep',
            'quality_standard_comply', 'quality_doc_complete', 'quality_test_result'
        ]) ||
        -- scre223 섹션 생성
        CASE
            WHEN custom_data::jsonb ?| ARRAY['scre223_item_1', 'scre223_item_2', 'scre223_item_3']
            THEN jsonb_build_object('scre223',
                jsonb_build_object(
                    'item_1', custom_data::jsonb->'scre223_item_1',
                    'item_2', custom_data::jsonb->'scre223_item_2',
                    'item_3', custom_data::jsonb->'scre223_item_3'
                )::text
            )
            ELSE '{}'::jsonb
        END ||
        -- test224 섹션 생성
        CASE
            WHEN custom_data::jsonb ?| ARRAY['test224_item_1', 'test224_item_2']
            THEN jsonb_build_object('test224',
                jsonb_build_object(
                    'item_1', custom_data::jsonb->'test224_item_1',
                    'item_2', custom_data::jsonb->'test224_item_2'
                )::text
            )
            ELSE '{}'::jsonb
        END ||
        -- test225 섹션 생성
        CASE
            WHEN custom_data::jsonb ?| ARRAY['test225_item_1', 'test225_item_2', 'test225_item_3', 'test225_item_4']
            THEN jsonb_build_object('test225',
                jsonb_build_object(
                    'item_1', custom_data::jsonb->'test225_item_1',
                    'item_2', custom_data::jsonb->'test225_item_2',
                    'item_3', custom_data::jsonb->'test225_item_3',
                    'item_4', custom_data::jsonb->'test225_item_4'
                )::text
            )
            ELSE '{}'::jsonb
        END ||
        -- tbm 섹션 생성
        CASE
            WHEN custom_data::jsonb ?| ARRAY['tbm_helmet_check', 'tbm_safety_brief', 'tbm_ppe_status', 'tbm_hazard_id']
            THEN jsonb_build_object('tbm',
                jsonb_build_object(
                    'item_1', custom_data::jsonb->'tbm_helmet_check',
                    'item_2', custom_data::jsonb->'tbm_safety_brief',
                    'item_3', custom_data::jsonb->'tbm_ppe_status',
                    'item_4', custom_data::jsonb->'tbm_hazard_id'
                )::text
            )
            ELSE '{}'::jsonb
        END ||
        -- safety_check 섹션 생성
        CASE
            WHEN custom_data::jsonb ?| ARRAY['safety_procedure_follow', 'safety_barrier_check', 'safety_emergency_prep']
            THEN jsonb_build_object('safety_check',
                jsonb_build_object(
                    'item_1', custom_data::jsonb->'safety_procedure_follow',
                    'item_2', custom_data::jsonb->'safety_barrier_check',
                    'item_3', custom_data::jsonb->'safety_emergency_prep'
                )::text
            )
            ELSE '{}'::jsonb
        END ||
        -- quality_audit 섹션 생성
        CASE
            WHEN custom_data::jsonb ?| ARRAY['quality_standard_comply', 'quality_doc_complete', 'quality_test_result']
            THEN jsonb_build_object('quality_audit',
                jsonb_build_object(
                    'item_1', custom_data::jsonb->'quality_standard_comply',
                    'item_2', custom_data::jsonb->'quality_doc_complete',
                    'item_3', custom_data::jsonb->'quality_test_result'
                )::text
            )
            ELSE '{}'::jsonb
        END as new_data
    FROM full_process
    WHERE custom_data IS NOT NULL
)
SELECT
    fullprocess_number,
    jsonb_pretty(original) as before,
    jsonb_pretty(new_data) as after
FROM transformed
WHERE original != new_data;  -- 변경이 있는 것만 표시

-- 4. 실제 업데이트 (위 SELECT 결과 확인 후 실행)
-- 주의: 이 쿼리는 실제로 데이터를 변경합니다!
/*
UPDATE full_process
SET custom_data = (
    -- 기존 데이터에서 scoring 필드 제외
    (custom_data::jsonb - ARRAY[
        'scre223_item_1', 'scre223_item_2', 'scre223_item_3',
        'test224_item_1', 'test224_item_2',
        'test225_item_1', 'test225_item_2', 'test225_item_3', 'test225_item_4',
        'tbm_helmet_check', 'tbm_safety_brief', 'tbm_ppe_status', 'tbm_hazard_id',
        'safety_procedure_follow', 'safety_barrier_check', 'safety_emergency_prep',
        'quality_standard_comply', 'quality_doc_complete', 'quality_test_result'
    ]) ||
    -- scre223 섹션
    CASE
        WHEN custom_data::jsonb ?| ARRAY['scre223_item_1', 'scre223_item_2', 'scre223_item_3']
        THEN jsonb_build_object('scre223',
            jsonb_build_object(
                'item_1', custom_data::jsonb->'scre223_item_1',
                'item_2', custom_data::jsonb->'scre223_item_2',
                'item_3', custom_data::jsonb->'scre223_item_3'
            )::text
        )
        ELSE '{}'::jsonb
    END ||
    -- test224 섹션
    CASE
        WHEN custom_data::jsonb ?| ARRAY['test224_item_1', 'test224_item_2']
        THEN jsonb_build_object('test224',
            jsonb_build_object(
                'item_1', custom_data::jsonb->'test224_item_1',
                'item_2', custom_data::jsonb->'test224_item_2'
            )::text
        )
        ELSE '{}'::jsonb
    END ||
    -- test225 섹션
    CASE
        WHEN custom_data::jsonb ?| ARRAY['test225_item_1', 'test225_item_2', 'test225_item_3', 'test225_item_4']
        THEN jsonb_build_object('test225',
            jsonb_build_object(
                'item_1', custom_data::jsonb->'test225_item_1',
                'item_2', custom_data::jsonb->'test225_item_2',
                'item_3', custom_data::jsonb->'test225_item_3',
                'item_4', custom_data::jsonb->'test225_item_4'
            )::text
        )
        ELSE '{}'::jsonb
    END ||
    -- tbm 섹션
    CASE
        WHEN custom_data::jsonb ?| ARRAY['tbm_helmet_check', 'tbm_safety_brief', 'tbm_ppe_status', 'tbm_hazard_id']
        THEN jsonb_build_object('tbm',
            jsonb_build_object(
                'item_1', custom_data::jsonb->'tbm_helmet_check',
                'item_2', custom_data::jsonb->'tbm_safety_brief',
                'item_3', custom_data::jsonb->'tbm_ppe_status',
                'item_4', custom_data::jsonb->'tbm_hazard_id'
            )::text
        )
        ELSE '{}'::jsonb
    END ||
    -- safety_check 섹션
    CASE
        WHEN custom_data::jsonb ?| ARRAY['safety_procedure_follow', 'safety_barrier_check', 'safety_emergency_prep']
        THEN jsonb_build_object('safety_check',
            jsonb_build_object(
                'item_1', custom_data::jsonb->'safety_procedure_follow',
                'item_2', custom_data::jsonb->'safety_barrier_check',
                'item_3', custom_data::jsonb->'safety_emergency_prep'
            )::text
        )
        ELSE '{}'::jsonb
    END ||
    -- quality_audit 섹션
    CASE
        WHEN custom_data::jsonb ?| ARRAY['quality_standard_comply', 'quality_doc_complete', 'quality_test_result']
        THEN jsonb_build_object('quality_audit',
            jsonb_build_object(
                'item_1', custom_data::jsonb->'quality_standard_comply',
                'item_2', custom_data::jsonb->'quality_doc_complete',
                'item_3', custom_data::jsonb->'quality_test_result'
            )::text
        )
        ELSE '{}'::jsonb
    END
)::jsonb
WHERE custom_data IS NOT NULL
    AND (
        custom_data::jsonb ? 'scre223_item_1' OR
        custom_data::jsonb ? 'test224_item_1' OR
        custom_data::jsonb ? 'test225_item_1' OR
        custom_data::jsonb ? 'tbm_helmet_check' OR
        custom_data::jsonb ? 'safety_procedure_follow' OR
        custom_data::jsonb ? 'quality_standard_comply'
    );
*/

-- 5. 변환 후 결과 확인
SELECT
    fullprocess_number,
    custom_data::jsonb ? 'scre223' as has_scre223_section,
    custom_data::jsonb ? 'test224' as has_test224_section,
    custom_data::jsonb ? 'test225' as has_test225_section,
    custom_data::jsonb ? 'tbm' as has_tbm_section,
    custom_data::jsonb ? 'safety_check' as has_safety_section,
    custom_data::jsonb ? 'quality_audit' as has_quality_section,
    jsonb_pretty(custom_data::jsonb) as structured_data
FROM full_process
WHERE custom_data IS NOT NULL
LIMIT 5;