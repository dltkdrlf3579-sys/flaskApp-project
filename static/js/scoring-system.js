// 채점 시스템 JavaScript

function decodeHtmlEntities(s) {
    if (typeof s !== 'string') return s;
    return s
        .replace(/&quot;/g, '"')
        .replace(/&#39;/g, "'")
        .replace(/&lt;/g, '<')
        .replace(/&gt;/g, '>')
        .replace(/&amp;/g, '&');
}

function parseJsonDeep(text, fallback = {}) {
    try {
        let t = decodeHtmlEntities(text || '');
        if (!t) return fallback;
        let v = JSON.parse(t);
        if (typeof v === 'string') {
            try { v = JSON.parse(v); } catch (e2) { return fallback; }
        }
        return v;
    } catch (e) {
        return fallback;
    }
}

function initScoringSystem() {
    console.log('🎯 Initializing scoring system...');
    
    // 모든 채점 필드 찾기 (.scoring-field 형태)
    const scoringFields = document.querySelectorAll('.scoring-field');
    console.log(`Found ${scoringFields.length} scoring fields`);
    
    scoringFields.forEach((field, index) => {
        console.log(`Processing field ${index}:`, field.dataset.field);
        
        const config = parseJsonDeep(field.dataset.config, {});
        console.log(`Config for field ${index}:`, config);
        const hiddenInput = field.querySelector('input[type="hidden"]');
        const currentValue = parseJsonDeep(hiddenInput?.value || '{}', {});
        
        // 헤더/토글 UI 보장
        ensureScoringHeader(field);

        const itemsContainer = field.querySelector('.scoring-items');
        
        if (config.items && config.items.length > 0) {
            console.log(`Rendering ${config.items.length} items`);
            // 채점 항목 렌더링
            let html = '<div class="scoring-grid">';
            config.items.forEach(item => {
                const value = currentValue[item.id] || 0;
                html += `
                    <div class="scoring-item">
                        <label>${item.label}</label>
                        <div class="scoring-controls">
                            <button type="button" class="scoring-btn minus" data-item="${item.id}" data-delta="${item.per_unit_delta}">-</button>
                            <input type="number" class="scoring-count" 
                                   data-item="${item.id}" 
                                   data-max="${item.max_count}"
                                   data-delta="${item.per_unit_delta}"
                                   value="${value}" 
                                   min="0" 
                                   max="${item.max_count}">
                            <button type="button" class="scoring-btn plus" data-item="${item.id}" data-delta="${item.per_unit_delta}">+</button>
                            <span class="scoring-points">${value * item.per_unit_delta}점</span>
                        </div>
                    </div>
                `;
            });
            html += '</div>';
            itemsContainer.innerHTML = html;
            
            // 이벤트 리스너 추가
            field.querySelectorAll('.scoring-btn').forEach(btn => {
                btn.addEventListener('click', handleScoringButton);
            });
            
            field.querySelectorAll('.scoring-count').forEach(input => {
                input.addEventListener('change', handleScoringInput);
            });
        } else {
            console.log('No items in config or config is missing');
            // 설정이 없을 때도 기본 UI 표시
            itemsContainer.innerHTML = '<div class="alert alert-info">채점 항목이 설정되지 않았습니다. 관리자 페이지에서 설정해주세요.</div>';
        }
    });
    
    // 총점 계산
    calculateTotalScore();

    // 총점 박스를 관련 채점 그룹 옆으로 재배치 (같은 가족 느낌)
    coLocateScoreTotals();
    // 재배치 후 총점 다시 계산
    calculateScoreTotal();
}

function ensureScoringHeader(fieldEl) {
    let header = fieldEl.querySelector('.scoring-header');
    if (!header) {
        header = document.createElement('div');
        header.className = 'scoring-header';
        header.innerHTML = `
            <button type="button" class="scoring-toggle">채점 편집</button>
            <div class="scoring-summary">
                <span class="summary-total">총점: <b class="score-inline">100</b></span>
                <span class="summary-count critical">중대 0</span>
                <span class="summary-count major">주요 0</span>
                <span class="summary-count minor">경미 0</span>
            </div>
        `;
        fieldEl.insertBefore(header, fieldEl.firstChild);
    }

    const toggleBtn = header.querySelector('.scoring-toggle');
    const itemsEl = fieldEl.querySelector('.scoring-items');
    if (toggleBtn && itemsEl) {
        // 초기 상태: 접힘
        fieldEl.classList.remove('open');
        itemsEl.style.display = 'none';
        toggleBtn.addEventListener('click', () => {
            const open = fieldEl.classList.toggle('open');
            itemsEl.style.display = open ? 'block' : 'none';
            toggleBtn.textContent = open ? '접기' : '채점 편집';
        });
    }
}

function handleScoringButton(e) {
    const btn = e.target;
    const itemId = btn.dataset.item;
    const field = btn.closest('.scoring-field');
    const input = field.querySelector(`input[data-item="${itemId}"]`);
    const max = parseInt(input.dataset.max);
    let value = parseInt(input.value || 0);
    
    if (btn.classList.contains('plus')) {
        value = Math.min(value + 1, max);
    } else {
        value = Math.max(value - 1, 0);
    }
    
    input.value = value;
    updateScoringValue(field, itemId, value);
}

function handleScoringInput(e) {
    const input = e.target;
    const itemId = input.dataset.item;
    const field = input.closest('.scoring-field');
    const max = parseInt(input.dataset.max);
    let value = parseInt(input.value || 0);
    
    value = Math.max(0, Math.min(value, max));
    input.value = value;
    
    updateScoringValue(field, itemId, value);
}

function updateScoringValue(field, itemId, value) {
    const hiddenInput = field.querySelector('input[type="hidden"]');
    const currentValue = parseJsonDeep(hiddenInput.value || '{}', {});
    const input = field.querySelector(`input[data-item="${itemId}"]`);
    const delta = parseFloat(input.dataset.delta);
    const pointsSpan = input.parentElement.querySelector('.scoring-points');
    
    currentValue[itemId] = value;
    hiddenInput.value = JSON.stringify(currentValue);
    
    // 점수 표시 업데이트
    const points = value * delta;
    pointsSpan.textContent = points + '점';
    pointsSpan.className = 'scoring-points ' + (points < 0 ? 'negative' : points > 0 ? 'positive' : '');
    
    // 총점 재계산
    calculateTotalScore();
}

function calculateTotalScore() {
    const scoringFields = document.querySelectorAll('.scoring-field');
    // 그룹별 합산 결과
    const groups = {};

    scoringFields.forEach(field => {
        const config = parseJsonDeep(field.dataset.config, {});

        const groupKey = config.total_key || config.group || 'default';
        if (!groups[groupKey]) {
            const base = (typeof config.base_score === 'number') ? config.base_score : 100;
            groups[groupKey] = {
                base: base,
                total: base,
                critical: 0,
                major: 0,
                minor: 0,
                bonus: 0
            };
        }

        const hiddenInput = field.querySelector('input[type="hidden"]');
        const currentValue = parseJsonDeep(hiddenInput?.value || '{}', {});

        const criteria = config.grade_criteria || {
            critical: { min: -999, max: -10 },
            major: { min: -9, max: -5 },
            minor: { min: -4, max: -1 },
            bonus: { min: 0.1, max: 999 }
        };

        if (Array.isArray(config.items)) {
            config.items.forEach(item => {
                const count = Number(currentValue[item.id] || 0);
                const points = count * Number(item.per_unit_delta || 0);
                groups[groupKey].total += points;

                if (points <= criteria.critical.max && points >= criteria.critical.min) {
                    groups[groupKey].critical += count;
                } else if (points <= criteria.major.max && points >= criteria.major.min) {
                    groups[groupKey].major += count;
                } else if (points <= criteria.minor.max && points >= criteria.minor.min) {
                    groups[groupKey].minor += count;
                } else if (points >= criteria.bonus.min) {
                    groups[groupKey].bonus += count;
                }
            });
        }
    });

    // .scoring-group 형태도 합산 (간단 네모 입력들)
    document.querySelectorAll('.scoring-group').forEach(groupEl => {
        const cfg = parseJsonDeep(groupEl.dataset.config, {});
        const groupKey = groupEl.getAttribute('data-group') || cfg.total_key || cfg.group || 'default';
        if (!groups[groupKey]) {
            const base = (typeof cfg.base_score === 'number') ? cfg.base_score : 100;
            groups[groupKey] = { base, total: base, critical: 0, major: 0, minor: 0, bonus: 0 };
        }
        const criteria = cfg.grade_criteria || {
            critical: { min: -999, max: -10 },
            major: { min: -9, max: -5 },
            minor: { min: -4, max: -1 },
            bonus: { min: 0.1, max: 999 }
        };

        groupEl.querySelectorAll('input.scoring-input').forEach(inp => {
            const count = Number(inp.value || 0);
            const delta = Number(inp.dataset.score || 0);
            const points = count * delta;
            groups[groupKey].total += points;
            if (points <= criteria.critical.max && points >= criteria.critical.min) {
                groups[groupKey].critical += count;
            } else if (points <= criteria.major.max && points >= criteria.major.min) {
                groups[groupKey].major += count;
            } else if (points <= criteria.minor.max && points >= criteria.minor.min) {
                groups[groupKey].minor += count;
            } else if (points >= criteria.bonus.min) {
                groups[groupKey].bonus += count;
            }
        });
    });

    // 상세의 그룹별 총점 박스 업데이트
    document.querySelectorAll('.score-total-field').forEach(box => {
        const key = box.getAttribute('data-total-key') || 'default';
        const g = groups[key] || { total: 100, critical: 0, major: 0, minor: 0, bonus: 0 };
        const scoreValue = box.querySelector('.score-value');
        if (scoreValue) {
            scoreValue.textContent = g.total;
            scoreValue.className = 'score-value ' + (g.total >= 90 ? 'excellent' : g.total >= 70 ? 'good' : g.total >= 50 ? 'fair' : 'poor');
        }
        const hiddenInput = box.querySelector('input[type="hidden"]');
        if (hiddenInput) {
            hiddenInput.value = JSON.stringify({
                total: g.total,
                critical: g.critical,
                major: g.major,
                minor: g.minor,
                bonus: g.bonus
            });
        }
        const criticalEl = box.querySelector('.critical-count');
        const majorEl = box.querySelector('.major-count');
        const minorEl = box.querySelector('.minor-count');
        const bonusEl = box.querySelector('.bonus-count');
        if (criticalEl) criticalEl.textContent = `중대: ${g.critical}`;
        if (majorEl) majorEl.textContent = `주요: ${g.major}`;
        if (minorEl) minorEl.textContent = `경미: ${g.minor}`;
        if (bonusEl) bonusEl.textContent = `가점: ${g.bonus}`;
    });

    // 각 채점 필드 헤더 인라인 요약 업데이트 (자기 그룹 값 적용)
    document.querySelectorAll('.scoring-field').forEach(field => {
        const cfg = parseJsonDeep(field.dataset.config, {});
        const key = cfg.total_key || cfg.group || 'default';
        const g = groups[key] || { total: 100, critical: 0, major: 0, minor: 0 };
        const header = field.querySelector('.scoring-header');
        if (!header) return;
        const scoreInline = header.querySelector('.score-inline');
        const crit = header.querySelector('.summary-count.critical');
        const maj = header.querySelector('.summary-count.major');
        const min = header.querySelector('.summary-count.minor');
        if (scoreInline) scoreInline.textContent = g.total;
        if (crit) crit.textContent = `중대 ${g.critical}`;
        if (maj) maj.textContent = `주요 ${g.major}`;
        if (min) min.textContent = `경미 ${g.minor}`;
    });
}

// 개선된 총점 계산 함수
function calculateScoreTotal() {
    document.querySelectorAll('.score-total-field').forEach(field => {
        // 먼저 include_keys 기반 계산 여부 확인
        const cfg = parseJsonDeep(field.dataset.config || '{}', {});
        const include = Array.isArray(cfg.include_keys) ? cfg.include_keys : [];
        if (include.length > 0) {
            const baseScore = typeof cfg.base_score === 'number' ? cfg.base_score : parseInt(field.dataset.baseScore || '100');
            let total = baseScore;
            include.forEach(key => {
                const group = document.querySelector(`.scoring-group[data-field="${key}"]`);
                if (!group) return;
                const scfg = parseJsonDeep(group.dataset.config || '{}', {});
                const items = Array.isArray(scfg.items) ? scfg.items : [];

                // hidden 대신 직접 scoring-input 값 읽기
                const values = {};
                group.querySelectorAll('input.scoring-input').forEach(inp => {
                    const itemId = inp.dataset.item;
                    if (itemId) {
                        values[itemId] = Number(inp.value || 0);
                    }
                });

                items.forEach(item => {
                    // affects_score가 false면 총점 반영 제외
                    if (typeof item.affects_score === 'boolean' && !item.affects_score) return;
                    const count = Number(values[item.id] || 0);
                    let delta = Number(item.per_unit_delta || 0);
                    if (item.negative === true && delta > 0) delta = -delta;
                    total += count * delta;
                });
            });
            const totalDisplay = field.querySelector('.total-score-display');
            if (totalDisplay) totalDisplay.value = total;
            const hiddenTotal = field.querySelector('input[type="hidden"][data-field]');
            if (hiddenTotal) hiddenTotal.value = JSON.stringify({ total });
            // 가시적인 클론 타일의 표시값도 동기화
            try {
                const key = field.getAttribute('data-field');
                if (key) {
                    document.querySelectorAll(`.score-total-field.score-total-clone[data-field="${key}"] .total-score-display`).forEach(el => {
                        el.value = total;
                    });
                }
            } catch (e) { /* ignore */ }
            return; // include_keys 모드에서는 기존 방식 생략
        }

        // 기존 방식(로컬 박스 내 입력 합산) - 하위호환
        const baseScore = parseInt(field.dataset.baseScore || '100');
        let total = baseScore;
        field.querySelectorAll('.score-item-input.affects-score').forEach(input => {
            const value = parseInt(input.value || '0');
            const isNegative = input.dataset.negative === 'true';
            total += isNegative ? -value : value;
        });
        const totalDisplay = field.querySelector('.total-score-display');
        if (totalDisplay) totalDisplay.value = total;
        const hiddenInput = field.querySelector('input[type="hidden"]');
        if (hiddenInput) hiddenInput.value = JSON.stringify({ total });
        // 클론 타일 동기화
        try {
            const key = field.getAttribute('data-field');
            if (key) {
                document.querySelectorAll(`.score-total-field.score-total-clone[data-field="${key}"] .total-score-display`).forEach(el => {
                    el.value = total;
                });
            }
        } catch (e) { /* ignore */ }
    });
}

// 간단한 총점 계산 함수 추가
function simpleScoreCalculation() {
    console.log('[SIMPLE] 총점 계산 시작');

    // 전체 페이지에서 total-score-display 찾기 (보통 1개)
    const totalDisplays = document.querySelectorAll('.total-score-display');
    console.log('[SIMPLE] total-score-display 개수:', totalDisplays.length);

    totalDisplays.forEach(totalDisplay => {
        console.log('[SIMPLE] 총점 필드 ID:', totalDisplay.id);

        // 설정 파싱 - include_keys 확인
        const config = parseJsonDeep(totalDisplay.dataset.config || '{}', {});
        const includeKeys = config.include_keys || [];
        console.log('[SIMPLE] include_keys:', includeKeys);

        // 기본점수 가져오기
        let baseScore = parseInt(config.base_score || totalDisplay.dataset.baseScore || totalDisplay.getAttribute('data-base-score') || '100');
        let total = baseScore;
        console.log('[SIMPLE] 기본점수:', baseScore);

        if (includeKeys.length > 0) {
            // include_keys가 있으면 해당 그룹만 계산
            console.log('[SIMPLE] include_keys 모드 - 특정 그룹만 계산:', includeKeys);

            includeKeys.forEach(key => {
                const group = document.querySelector(`.scoring-group[data-field="${key}"]`);
                if (!group) {
                    console.log(`[SIMPLE] Group ${key} not found`);
                    return;
                }

                console.log(`[SIMPLE] Group ${key} 계산 중...`);
                const inputs = group.querySelectorAll('.scoring-input');
                inputs.forEach(input => {
                    // 빈 값은 0으로 계산하되, null과 0을 구분
                    const rawValue = input.value.trim();
                    const value = rawValue === '' ? 0 : parseInt(rawValue || 0);
                    const score = parseInt(input.dataset.score || 0);
                    const points = value * score;
                    total += points;
                    if (value > 0) {
                        console.log(`[SIMPLE]   ${key}.${input.dataset.item}: ${value} × ${score} = ${points}`);
                    }
                });
            });
        } else {
            // include_keys가 없으면 모든 scoring-group 계산 (기존 방식)
            console.log('[SIMPLE] include_keys 없음 - 모든 그룹 계산');

            const allGroups = document.querySelectorAll('.scoring-group');
            console.log('[SIMPLE] 전체 scoring-group 개수:', allGroups.length);

            allGroups.forEach((group, idx) => {
                console.log(`[SIMPLE] Group ${idx} (${group.dataset.field}) 계산 중...`);

                const inputs = group.querySelectorAll('.scoring-input');
                inputs.forEach(input => {
                    // 빈 값은 0으로 계산하되, null과 0을 구분
                    const rawValue = input.value.trim();
                    const value = rawValue === '' ? 0 : parseInt(rawValue || 0);
                    const score = parseInt(input.dataset.score || 0);
                    const points = value * score;
                    total += points;
                    if (value > 0) {
                        console.log(`[SIMPLE]   ${group.dataset.field}.${input.dataset.item}: ${value} × ${score} = ${points}`);
                    }
                });
            });
        }

        console.log('[SIMPLE] 최종 총점:', total);
        totalDisplay.value = total;

        // hidden input도 업데이트 (있으면)
        const hiddenInput = document.getElementById(totalDisplay.id.replace('_display', ''));
        if (hiddenInput) {
            hiddenInput.value = total;
            console.log('[SIMPLE] hidden input도 업데이트:', hiddenInput.id);
        }
    });
}

// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', function() {
    initScoringSystem();

    // scoring-group 입력 변화 → hidden JSON 갱신 + 합산
    document.querySelectorAll('.scoring-group').forEach(groupEl => {
        const hidden = groupEl.querySelector('input[type="hidden"][data-field]');
        const state = parseJsonDeep(hidden?.value || '{}', {});

        const updateHidden = () => {
            const obj = {};
            groupEl.querySelectorAll('input.scoring-input').forEach(inp => {
                const id = inp.dataset.item;
                // 빈 값은 null로 처리, 값이 있으면 0 이상으로 정규화
                const rawValue = inp.value.trim();
                if (rawValue === '') {
                    if (id) obj[id] = null;  // 빈 값은 null로 저장
                } else {
                    const v = Math.max(0, parseInt(rawValue, 10));
                    if (id) obj[id] = v;
                    // 입력값 정규화 (빈 값이 아닌 경우만)
                    if (inp.value != v) inp.value = v;
                }
            });
            if (hidden) {  // hidden이 있을 때만 업데이트
                hidden.value = JSON.stringify(obj);
            }
        };

        // 초기화 1회
        if (hidden) {
            updateHidden();
        }

        groupEl.addEventListener('input', (e) => {
            console.log('[EVENT] input 이벤트 발생:', e.target.className, e.target.dataset.item);
            if (e.target && e.target.classList && e.target.classList.contains('scoring-input')) {
                console.log('[EVENT] scoring-input 변경 감지!');
                if (hidden) {
                    updateHidden();
                }
                // 기존 복잡한 함수 대신 간단한 함수 호출
                simpleScoreCalculation();
                // calculateTotalScore();
                // calculateScoreTotal(); // include_keys 기반 총점도 갱신
            }
        });
    });

    // 총점 필드 이벤트 리스너 추가
    document.querySelectorAll('.score-total-field').forEach(field => {
        field.addEventListener('input', (e) => {
            if (e.target && e.target.classList.contains('score-item-input')) {
                calculateScoreTotal();
            }
        });
    });

    // 초기 총점 계산 - 간단한 함수로
    simpleScoreCalculation();
    // calculateScoreTotal();

    // 총점 타일 라벨을 항상 외부 라벨(컬럼명)과 동기화하고, 외부 라벨은 숨김 처리
    syncScoreTotalLabels();
});

// 총점(.score-total-field)을 해당 scoring-group의 그리드 옆으로 옮기는 함수
function coLocateScoreTotals() {
    try {
        // Temporarily disabled to stabilize layout; relies on template-only rendering
        return;
        // 이전에 만들어진 표시용 클론들을 정리하여 중복 방지
        document.querySelectorAll('.score-total-field.score-total-clone').forEach(el => {
            try { el.remove(); } catch(e) { /* ignore */ }
        });
        document.querySelectorAll('.score-total-field').forEach(totalField => {
            const cfg = parseJsonDeep(totalField.dataset.config || '{}', {});
            const include = Array.isArray(cfg.include_keys) ? cfg.include_keys : [];

            // 1) 우선 include_keys[0] 기준으로 타겟 찾기
            let targetGroup = null;
            if (include.length > 0) {
                const firstKey = include[0];
                targetGroup = document.querySelector(`.scoring-group[data-field="${firstKey}"]`);
            }

            // 2) include_keys가 없거나 타겟을 못 찾은 경우, total_key 매칭으로 찾기
            if (!targetGroup) {
                const groupKey = cfg.total_key || cfg.group || 'default';
                const groups = Array.from(document.querySelectorAll('.scoring-group'));
                for (const g of groups) {
                    const gcfg = parseJsonDeep(g.dataset.config || '{}', {});
                    const gkey = gcfg.total_key || gcfg.group || 'default';
                    if (gkey === groupKey) { targetGroup = g; break; }
                }
            }

            // 3) 그래도 없으면, 가장 가까운 scoring-group 선택 (아랫줄/오른쪽 우선)
            if (!targetGroup) {
                const allGroups = Array.from(document.querySelectorAll('.scoring-group'));
                if (allGroups.length > 0) {
                    const tfRect = totalField.getBoundingClientRect();
                    let best = null;
                    let bestScore = Infinity;
                    allGroups.forEach(g => {
                        const r = g.getBoundingClientRect();
                        const dy = r.top - tfRect.top; // 아래쪽이 양수, 위쪽이 음수
                        const dx = r.left - tfRect.left; // 오른쪽이 양수
                        // 우선순위: 아래쪽(또는 같은 줄) 우선, 그다음 오른쪽 우선
                        const priY = (dy >= -2) ? 0 : 1; // 위쪽이면 페널티
                        const priX = (dx >= -2) ? 0 : 1; // 왼쪽이면 페널티
                        const dist = Math.hypot(dy, dx);
                        const score = priY * 100000 + priX * 1000 + dist; // 큰 가중치로 우선순위 부여
                        if (score < bestScore) { bestScore = score; best = g; }
                    });
                    targetGroup = best || allGroups[0];
                }
            }
            if (!targetGroup) return; // 끝까지 못 찾으면 이동 포기

            // 이미 스코어링 그룹 내부에 있더라도, 왼쪽 첫 칸으로 재배치하여 위치 보정

            // 보장: 대상 그룹 안에 .scoring-columns가 있어야 함
            let grid = targetGroup.classList && targetGroup.classList.contains('scoring-columns')
                ? targetGroup
                : targetGroup.querySelector('.scoring-columns');
            if (!grid) {
                // 기존 그룹 자체가 그리드가 아닐 때만 새로 생성
                grid = document.createElement('div');
                grid.className = 'scoring-columns';
                targetGroup.appendChild(grid);
            }

            // 총점 원본 컨테이너(.info-cell 내의 실제 타일)를 정확히 식별
            const fieldKey = totalField.getAttribute('data-field');
            const sourceTotalContainer = document.querySelector(`.info-cell .score-total-field[data-field="${fieldKey}"]:not(.score-total-clone)`);
            const sourceInfoCell = sourceTotalContainer ? sourceTotalContainer.closest('.info-cell') : null;
            // 원본 라벨 텍스트 확보 (info-cell > label 또는 타일 내부 라벨)
            let outerLabelText = null;
            if (sourceInfoCell) {
                const direct = sourceInfoCell.querySelector(':scope > label');
                const any = sourceInfoCell.querySelector('label');
                const labelNode = direct || any || null;
                if (labelNode && labelNode.textContent) {
                    outerLabelText = labelNode.textContent.trim();
                }
                if (!outerLabelText) {
                    const inner = sourceTotalContainer ? sourceTotalContainer.querySelector('label') : null;
                    if (inner && inner.textContent) outerLabelText = inner.textContent.trim();
                }
                // 원본 info-cell id를 부여하고 참조 저장 (이후 정확히 이 셀만 숨김)
                if (!sourceInfoCell.id) {
                    const fid = fieldKey || Math.random().toString(36).slice(2);
                    sourceInfoCell.id = `scoretotal-src-${fid}`;
                }
                totalField.setAttribute('data-source-info-id', sourceInfoCell.id);
            }

            // 이미 클론이 있는지 확인 (중복 추가 방지)
            let clone = grid.querySelector(`.score-total-field.score-total-clone[data-field="${fieldKey}"]`);
            if (!clone) {
                // 총점 컨테이너를 .sc-col 형태로 보장
                let totalContainer = totalField.closest('.sc-col');
                if (!totalContainer) {
                    const wrap = document.createElement('div');
                    wrap.className = 'sc-col';
                    totalField.parentNode.insertBefore(wrap, totalField);
                    wrap.appendChild(totalField);
                    totalContainer = wrap;
                }
                clone = totalContainer.cloneNode(true);
                try {
                    // 클론에서는 hidden input 제거 (저장 값 중복 방지)
                    clone.querySelectorAll('input[type="hidden"][data-field]').forEach(h => h.remove());
                    // 라벨 텍스트를 원본 컬럼명으로 동기화
                    const inner = clone.querySelector('label');
                    if (inner && outerLabelText && outerLabelText.length > 0) {
                        inner.textContent = outerLabelText;
                    }
                    // 식별용 클래스 추가
                    clone.classList.add('score-total-clone');
                } catch (e) { /* ignore */ }

                // 왼쪽에 먼저 붙이기(첫 타일 위치)
                if (grid.firstChild) {
                    grid.insertBefore(clone, grid.firstChild);
                } else {
                    grid.appendChild(clone);
                }
            } else {
                // 기존 클론의 라벨만 동기화
                try {
                    const inner = clone.querySelector('label');
                    if (inner && outerLabelText && outerLabelText.length > 0) {
                        inner.textContent = outerLabelText;
                    }
                } catch (e) { /* ignore */ }
            }

            // 원본 필드에도 소스 라벨 저장 (동기화용)
            if (outerLabelText && outerLabelText.length > 0) {
                totalField.setAttribute('data-source-label', outerLabelText);
            }

            // 원본 총점 셀은 레이아웃을 밀어내므로 숨김 처리
            if (sourceInfoCell && sourceInfoCell.style) {
                sourceInfoCell.style.display = 'none';
            }
        });
        // 이동 후 라벨 동기화 재실행
        syncScoreTotalLabels();
    } catch (e) {
        console.warn('coLocateScoreTotals error:', e);
    }
}

// 총점 타일 내부 라벨을 원래 info-cell 컬럼 라벨과 맞추고, 외부 라벨은 숨김 처리
function syncScoreTotalLabels() {
    document.querySelectorAll('.score-total-field').forEach(totalField => {
        // 내부 라벨에 원본 컬럼명 적용
        const inner = totalField.querySelector('label');
        const sourceLabel = totalField.getAttribute('data-source-label');
        if (inner && sourceLabel) {
            inner.textContent = sourceLabel;
        }
        // 원본 총점 info-cell만 숨김 (다른 칼럼 라벨은 유지)
        const srcId = totalField.getAttribute('data-source-info-id');
        if (srcId) {
            const srcCell = document.getElementById(srcId);
            if (srcCell && srcCell.style) srcCell.style.display = 'none';
        }
    });
}
// ---- hide empty .info-cell (공통) ----
(function () {
  function isEffectivelyEmpty(el) {
    // 1) 자식 요소가 하나도 없고
    if (el.children.length === 0) {
      // 2) 텍스트가 모두 공백이면 비어있다고 판단
      return (el.textContent || '').trim() === '';
    }
    return false;
  }

  function hideEmptyInfoCells() {
    var cells = document.querySelectorAll('.info-cell');
    for (var i = 0; i < cells.length; i++) {
      var el = cells[i];
      if (isEffectivelyEmpty(el)) {
        el.style.display = 'none';
        el.classList.add('ghost-hidden');
      }
    }
  }

  // 최초 실행
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', hideEmptyInfoCells);
  } else {
    hideEmptyInfoCells();
  }

  // 동적 변화에도 반영 (섹션 토글/비동기 렌더 등)
  try {
    var mo = new MutationObserver(function () {
      // 간단히 재실행 (문제 셀 수가 적으니 성능 부담 거의 없음)
      hideEmptyInfoCells();
    });
    mo.observe(document.body, { childList: true, subtree: true });
  } catch (e) {
    // MutationObserver 미지원 환경이면 무시
  }

  // 디버그/수동 호출용
  window.hideEmptyInfoCells = hideEmptyInfoCells;
})();
