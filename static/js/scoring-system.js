// 채점 시스템 JavaScript
function initScoringSystem() {
    console.log('🎯 Initializing scoring system...');
    
    // 모든 채점 필드 찾기
    const scoringFields = document.querySelectorAll('.scoring-field');
    console.log(`Found ${scoringFields.length} scoring fields`);
    
    scoringFields.forEach((field, index) => {
        console.log(`Processing field ${index}:`, field.dataset.field);
        
        let config = {};
        try {
            // HTML entity decode if needed
            let configStr = field.dataset.config || '{}';
            configStr = configStr.replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');
            config = JSON.parse(configStr);
            console.log(`Config for field ${index}:`, config);
        } catch (e) {
            console.error(`Failed to parse config for field ${index}:`, e, field.dataset.config);
            config = {};
        }
        const hiddenInput = field.querySelector('input[type="hidden"]');
        let currentValue = {};
        try {
            let valueStr = hiddenInput.value || '{}';
            valueStr = valueStr.replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');
            currentValue = JSON.parse(valueStr);
        } catch (e) {
            console.error('Failed to parse current value:', e);
            currentValue = {};
        }
        
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
    const currentValue = JSON.parse(hiddenInput.value || '{}');
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
    const totalField = document.querySelector('.score-total-field');
    
    if (!totalField) return;
    
    let totalScore = 100; // 기본 점수
    let criticalCount = 0;
    let majorCount = 0;
    let minorCount = 0;
    let bonusCount = 0;
    
    scoringFields.forEach(field => {
        const config = JSON.parse(field.dataset.config || '{}');
        const hiddenInput = field.querySelector('input[type="hidden"]');
        const currentValue = JSON.parse(hiddenInput.value || '{}');
        
        // 등급 기준 가져오기
        const criteria = config.grade_criteria || {
            critical: { min: -999, max: -10 },
            major: { min: -9, max: -5 },
            minor: { min: -4, max: -1 },
            bonus: { min: 0.1, max: 999 }
        };
        
        if (config.items) {
            config.items.forEach(item => {
                const count = currentValue[item.id] || 0;
                const points = count * item.per_unit_delta;
                totalScore += points;
                
                // 등급별 카운트
                if (points <= criteria.critical.max && points >= criteria.critical.min) {
                    criticalCount += count;
                } else if (points <= criteria.major.max && points >= criteria.major.min) {
                    majorCount += count;
                } else if (points <= criteria.minor.max && points >= criteria.minor.min) {
                    minorCount += count;
                } else if (points >= criteria.bonus.min) {
                    bonusCount += count;
                }
            });
        }
    });
    
    // 총점 표시 업데이트
    const scoreValue = totalField.querySelector('.score-value');
    const hiddenInput = totalField.querySelector('input[type="hidden"]');
    
    scoreValue.textContent = totalScore;
    scoreValue.className = 'score-value ' + (totalScore >= 90 ? 'excellent' : totalScore >= 70 ? 'good' : totalScore >= 50 ? 'fair' : 'poor');
    
    hiddenInput.value = JSON.stringify({
        total: totalScore,
        critical: criticalCount,
        major: majorCount,
        minor: minorCount,
        bonus: bonusCount
    });
    
    // 등급별 카운트 업데이트
    const criticalEl = totalField.querySelector('.critical-count');
    const majorEl = totalField.querySelector('.major-count');
    const minorEl = totalField.querySelector('.minor-count');
    const bonusEl = totalField.querySelector('.bonus-count');
    
    if (criticalEl) criticalEl.textContent = `중대: ${criticalCount}`;
    if (majorEl) majorEl.textContent = `주요: ${majorCount}`;
    if (minorEl) minorEl.textContent = `경미: ${minorCount}`;
    if (bonusEl) bonusEl.textContent = `가점: ${bonusCount}`;
}

// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', function() {
    initScoringSystem();
});