/**
 * Full Process Scoring 외부 쿼리 매핑 JavaScript
 * 백엔드에서 매핑된 외부 데이터를 프론트엔드 scoring input에 적용
 */

/**
 * 외부 scoring 데이터를 해당 input에 적용
 * @param {Array} scoringData - 백엔드에서 매핑된 scoring 데이터
 */
function applyExternalScoring(scoringData) {
    console.log('[SCORING] Applying external scoring data:', scoringData);

    if (!scoringData || !Array.isArray(scoringData)) {
        console.warn('[SCORING] Invalid scoring data provided');
        return;
    }

    let appliedCount = 0;

    scoringData.forEach(columnData => {
        const columnKey = columnData.column_key;
        const items = columnData.items || [];

        console.log(`[SCORING] Processing column_key: ${columnKey}, items: ${items.length}`);

        items.forEach(item => {
            if (item.external_value !== undefined && item.external_value !== null) {
                // data-field와 data-item으로 해당 input 찾기
                const selector = `[data-field="${columnKey}"] [data-item="${item.id}"]`;
                const input = document.querySelector(selector);

                if (input) {
                    // 기존 값과 다른 경우에만 업데이트
                    const currentValue = parseInt(input.value) || 0;
                    const newValue = parseInt(item.external_value) || 0;

                    if (currentValue !== newValue) {
                        input.value = newValue;
                        appliedCount++;

                        // scoring 계산 트리거
                        input.dispatchEvent(new Event('input', { bubbles: true }));

                        console.log(`[SCORING] Applied: ${columnKey}.${item.id} = ${newValue}`);
                    }
                } else {
                    console.warn(`[SCORING] Input not found for: ${columnKey}.${item.id}`);
                }
            }
        });
    });

    console.log(`[SCORING] Total external values applied: ${appliedCount}`);

    // 전체 점수 재계산 트리거
    if (appliedCount > 0) {
        triggerScoreRecalculation();
    }
}

/**
 * 전체 scoring 재계산 트리거
 */
function triggerScoreRecalculation() {
    console.log('[SCORING] Triggering score recalculation');

    // 모든 scoring input에 대해 input 이벤트 발생
    const scoringInputs = document.querySelectorAll('.scoring-input');
    scoringInputs.forEach(input => {
        input.dispatchEvent(new Event('input', { bubbles: true }));
    });

    // 전체 점수 계산 함수가 있다면 호출
    if (typeof recalcScoreFullProcess === 'function') {
        setTimeout(() => {
            recalcScoreFullProcess();
        }, 100);
    }
}

/**
 * 페이지 로드 시 외부 scoring 데이터 자동 적용
 */
function initializeExternalScoring() {
    console.log('[SCORING] Initializing external scoring');

    // 서버에서 전달된 scoring 데이터가 있는지 확인
    if (typeof externalScoringData !== 'undefined' && externalScoringData) {
        console.log('[SCORING] Found external scoring data, applying...');
        applyExternalScoring(externalScoringData);
    } else {
        console.log('[SCORING] No external scoring data found');
    }
}

/**
 * 수동으로 외부 scoring 데이터 로드
 * @param {string} fullprocessNumber - Full Process 번호
 */
function loadExternalScoring(fullprocessNumber) {
    if (!fullprocessNumber) {
        console.warn('[SCORING] No fullprocess number provided');
        return;
    }

    console.log(`[SCORING] Loading external scoring for: ${fullprocessNumber}`);

    // AJAX로 외부 scoring 데이터 요청
    fetch(`/api/full-process/external-scoring/${fullprocessNumber}`)
        .then(response => response.json())
        .then(data => {
            if (data.success && data.scoring_data) {
                console.log('[SCORING] External scoring data loaded successfully');
                applyExternalScoring(data.scoring_data);
            } else {
                console.warn('[SCORING] Failed to load external scoring data:', data.message);
            }
        })
        .catch(error => {
            console.error('[SCORING] Error loading external scoring:', error);
        });
}

/**
 * scoring input 값 변경 시 외부 매핑 상태 표시
 */
function setupExternalScoringIndicators() {
    console.log('[SCORING] Setting up external scoring indicators');

    const scoringInputs = document.querySelectorAll('.scoring-input');

    scoringInputs.forEach(input => {
        // 외부에서 매핑된 값인지 표시하기 위한 클래스 추가
        const parentGroup = input.closest('[data-field]');
        const dataField = parentGroup ? parentGroup.getAttribute('data-field') : null;
        const dataItem = input.getAttribute('data-item');

        if (dataField && dataItem) {
            // 외부 매핑 여부 체크 (config.ini 기반)
            input.addEventListener('focus', function() {
                const tooltip = this.getAttribute('title') || '';
                if (!tooltip.includes('외부 매핑')) {
                    // 외부 매핑 정보가 있다면 툴팁에 표시
                    this.setAttribute('title', `${tooltip}\n(외부 시스템 연동 가능)`.trim());
                }
            });
        }
    });
}

/**
 * 외부 scoring 매핑 상태 디버그 정보 표시
 */
function debugExternalScoringMapping() {
    console.log('=== External Scoring Debug Info ===');

    const scoringGroups = document.querySelectorAll('[data-field]');

    scoringGroups.forEach(group => {
        const columnKey = group.getAttribute('data-field');
        const inputs = group.querySelectorAll('.scoring-input');

        console.log(`Column: ${columnKey}`);
        inputs.forEach(input => {
            const itemId = input.getAttribute('data-item');
            const value = input.value;
            console.log(`  - ${itemId}: ${value}`);
        });
    });

    console.log('================================');
}

// 페이지 로드 완료 시 초기화
document.addEventListener('DOMContentLoaded', function() {
    console.log('[SCORING] DOM loaded, initializing external scoring');

    // 기본 초기화
    initializeExternalScoring();

    // 외부 매핑 표시 설정
    setupExternalScoringIndicators();

    // 디버그 모드에서는 매핑 정보 출력
    if (typeof debugMode !== 'undefined' && debugMode) {
        setTimeout(debugExternalScoringMapping, 1000);
    }
});

// 전역 함수로 노출
window.applyExternalScoring = applyExternalScoring;
window.loadExternalScoring = loadExternalScoring;
window.debugExternalScoringMapping = debugExternalScoringMapping;