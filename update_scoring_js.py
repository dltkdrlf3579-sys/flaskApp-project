#!/usr/bin/env python3
"""
Update scoring JavaScript functions for followsop and fullprocess admin pages
"""
import re

def update_js_functions(file_path):
    """Update the JavaScript functions in the HTML file"""
    
    # Read the file  
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find and replace the toggleScoringField function and related functions
    old_pattern = r'function toggleScoringField\(\).*?function rebuildScoringJsonFromBuilder\(\).*?\n        \}'
    
    new_functions = '''function toggleScoringField() {
            const type = document.getElementById('columnType').value;
            const el = document.getElementById('scoringConfigField');
            if (el) {
                el.style.display = (type === 'scoring' || type === 'score_total') ? 'block' : 'none';
                if (type === 'scoring' || type === 'score_total') {
                    updateScoringPreview();
                }
            }
        }

        // 새로운 채점 모달 관련 함수들
        let scoringItems = [];
        let scoringItemCounter = 0;

        function openScoringModal() {
            const ta = document.getElementById('scoringConfig');
            let config = {};
            try {
                config = JSON.parse(ta.value || '{}');
            } catch(e) {
                config = {};
            }

            // 기본 점수 설정
            document.getElementById('scoringBaseScore').value = config.base_score || 100;

            // 채점 항목 로드
            scoringItems = config.items || [];
            renderScoringItems();

            // 등급 기준 로드
            if (config.grade_criteria) {
                document.getElementById('criticalMin').value = config.grade_criteria.critical?.min || -999;
                document.getElementById('criticalMax').value = config.grade_criteria.critical?.max || -10;
                document.getElementById('majorMin').value = config.grade_criteria.major?.min || -9;
                document.getElementById('majorMax').value = config.grade_criteria.major?.max || -5;
                document.getElementById('minorMin').value = config.grade_criteria.minor?.min || -4;
                document.getElementById('minorMax').value = config.grade_criteria.minor?.max || -1;
                document.getElementById('bonusMin').value = config.grade_criteria.bonus?.min || 0.1;
                document.getElementById('bonusMax').value = config.grade_criteria.bonus?.max || 999;
            }

            // 미리보기 업데이트
            updateScoringPreview();

            // 모달 열기
            const modal = new bootstrap.Modal(document.getElementById('scoringConfigModal'));
            modal.show();
        }

        function addScoringItem(item = null) {
            const newItem = item || {
                id: `item_${++scoringItemCounter}`,
                label: '',
                per_unit_delta: -5,
                max_count: 10
            };
            scoringItems.push(newItem);
            renderScoringItems();
        }

        function renderScoringItems() {
            const container = document.getElementById('scoringItemsList');
            container.innerHTML = '';

            scoringItems.forEach((item, index) => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td class="text-center">${index + 1}</td>
                    <td>
                        <input type="text" class="form-control" value="${item.label || ''}" 
                               onchange="updateScoringItem(${index}, 'label', this.value)">
                    </td>
                    <td>
                        <input type="number" class="form-control" value="${item.per_unit_delta || 0}" 
                               step="0.1" onchange="updateScoringItem(${index}, 'per_unit_delta', parseFloat(this.value))">
                    </td>
                    <td>
                        <input type="number" class="form-control" value="${item.max_count || 1}" 
                               min="1" onchange="updateScoringItem(${index}, 'max_count', parseInt(this.value))">
                    </td>
                    <td class="text-center">
                        ${(item.per_unit_delta || 0) * (item.max_count || 1)}
                    </td>
                    <td class="text-center">
                        <button type="button" class="btn btn-sm btn-danger" onclick="removeScoringItem(${index})">
                            <i class="bi bi-trash"></i>
                        </button>
                    </td>
                `;
                container.appendChild(row);
            });

            if (scoringItems.length === 0) {
                container.innerHTML = '<tr><td colspan="6" class="text-center text-muted">채점 항목을 추가해주세요</td></tr>';
            }
        }

        function updateScoringItem(index, field, value) {
            if (scoringItems[index]) {
                scoringItems[index][field] = value;
                renderScoringItems();
                updateScoringPreview();
            }
        }

        function removeScoringItem(index) {
            scoringItems.splice(index, 1);
            renderScoringItems();
            updateScoringPreview();
        }

        function updateScoringPreview() {
            const config = buildScoringConfig();
            
            // 항목 요약
            const itemsSummary = document.getElementById('scoringItemsSummary');
            if (itemsSummary) {
                let html = `<div class="mb-2">기본 점수: <strong>${config.base_score}점</strong></div>`;
                if (config.items.length > 0) {
                    html += '<ul class="mb-0">';
                    config.items.forEach(item => {
                        const total = item.per_unit_delta * item.max_count;
                        const type = item.per_unit_delta < 0 ? 'danger' : 'success';
                        html += `<li>${item.label}: <span class="text-${type}">${item.per_unit_delta}점</span> × ${item.max_count}회 = <strong>${total}점</strong></li>`;
                    });
                    html += '</ul>';
                } else {
                    html += '<p class="text-muted mb-0">채점 항목이 없습니다</p>';
                }
                itemsSummary.innerHTML = html;
            }

            // 등급 기준 요약
            const criteriaSummary = document.getElementById('gradeCriteriaSummary');
            if (criteriaSummary && config.grade_criteria) {
                const gc = config.grade_criteria;
                criteriaSummary.innerHTML = `
                    <div class="row g-2">
                        <div class="col-6">
                            <span class="badge bg-danger">중대</span> ${gc.critical.min} ~ ${gc.critical.max}점
                        </div>
                        <div class="col-6">
                            <span class="badge bg-warning">주요</span> ${gc.major.min} ~ ${gc.major.max}점
                        </div>
                        <div class="col-6">
                            <span class="badge bg-info">경미</span> ${gc.minor.min} ~ ${gc.minor.max}점
                        </div>
                        <div class="col-6">
                            <span class="badge bg-success">가점</span> ${gc.bonus.min} ~ ${gc.bonus.max}점
                        </div>
                    </div>
                `;
            }

            // JSON 미리보기
            const jsonPreview = document.getElementById('scoringJsonPreview');
            if (jsonPreview) {
                jsonPreview.textContent = JSON.stringify(config, null, 2);
            }

            // 메인 화면 레이블 업데이트
            const label = document.getElementById('scoringPreviewLabel');
            if (label) {
                if (config.items.length > 0) {
                    label.innerHTML = `<span class="text-success">✓ ${config.items.length}개 항목 설정됨</span>`;
                } else {
                    label.innerHTML = '<span class="text-muted">설정되지 않음</span>';
                }
            }
        }

        function buildScoringConfig() {
            const type = document.getElementById('columnType').value;
            const baseScore = parseInt(document.getElementById('scoringBaseScore')?.value || '100');
            
            const config = {
                type: type === 'score_total' ? 'score_total' : 'scoring',
                base_score: baseScore,
                items: scoringItems.filter(item => item.label),
                grade_criteria: {
                    critical: {
                        min: parseFloat(document.getElementById('criticalMin')?.value || '-999'),
                        max: parseFloat(document.getElementById('criticalMax')?.value || '-10')
                    },
                    major: {
                        min: parseFloat(document.getElementById('majorMin')?.value || '-9'),
                        max: parseFloat(document.getElementById('majorMax')?.value || '-5')
                    },
                    minor: {
                        min: parseFloat(document.getElementById('minorMin')?.value || '-4'),
                        max: parseFloat(document.getElementById('minorMax')?.value || '-1')
                    },
                    bonus: {
                        min: parseFloat(document.getElementById('bonusMin')?.value || '0.1'),
                        max: parseFloat(document.getElementById('bonusMax')?.value || '999')
                    }
                }
            };
            
            return config;
        }

        function saveScoringConfig() {
            const config = buildScoringConfig();
            document.getElementById('scoringConfig').value = JSON.stringify(config, null, 2);
            updateScoringPreview();
            
            // 모달 닫기
            const modal = bootstrap.Modal.getInstance(document.getElementById('scoringConfigModal'));
            modal.hide();
        }'''
    
    # Try to replace the functions
    content = re.sub(old_pattern, new_functions, content, flags=re.DOTALL)
    
    # Write back the updated content
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Updated JS functions in: {file_path}")

# Update both files
files_to_update = [
    'templates/admin-followsop-columns.html',
    'templates/admin-fullprocess-columns.html'
]

for file_path in files_to_update:
    try:
        update_js_functions(file_path)
    except Exception as e:
        print(f"Error updating {file_path}: {e}")

print("JavaScript functions updated!")