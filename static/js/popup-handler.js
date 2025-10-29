/**
 * 통합 팝업 핸들러
 * 모든 보드에서 공통으로 사용하는 팝업 처리 함수
 */

function triggerFieldEvents(field) {
    if (!field) {
        return;
    }
    try {
        field.dispatchEvent(new Event('input', { bubbles: true }));
        field.dispatchEvent(new Event('change', { bubbles: true }));
    } catch (err) {
        console.warn('triggerFieldEvents failed', err);
    }
}

function applyFieldValue(field, value, options) {
    if (!field) {
        return;
    }

    const opts = Object.assign(
        {
            readonly: true,
            background: '#f3f4f6',
        },
        options || {}
    );

    field.value = value == null ? '' : value;

    if (opts.readonly) {
        field.setAttribute('readonly', true);
    } else {
        field.removeAttribute('readonly');
    }

    if (typeof opts.background === 'string') {
        field.style.backgroundColor = opts.background;
    }

    triggerFieldEvents(field);
}

// table_group 기반 linked_text 필드 자동 업데이트 함수
function updateLinkedFieldsByTableGroup(mainFieldKey, selectedData, tableGroup) {
    if (!tableGroup) return;

    console.log('updateLinkedFieldsByTableGroup:', mainFieldKey, tableGroup, selectedData);

    // 같은 table_group의 모든 linked_text 필드 찾기
    const linkedFields = document.querySelectorAll(`input[data-table-group="${tableGroup}"]`);
    console.log('Found linked fields:', linkedFields.length);

    // 모든 input 요소 중 table_group 속성이 있는 것들 확인
    const allInputs = document.querySelectorAll('input[data-table-group]');
    console.log('All inputs with data-table-group:', allInputs.length);
    allInputs.forEach(input => {
        console.log('Input:', input.id, 'table-group:', input.getAttribute('data-table-group'), 'class:', input.className);
    });

    linkedFields.forEach(field => {
        const fieldKey = field.getAttribute('data-field');
        const tableType = field.getAttribute('data-table-type');

        // 메인 필드는 제외
        if (fieldKey === mainFieldKey) return;

        let mappedValue;

        if (fieldKey.includes('_company')) {
            mappedValue = selectedData.company_name || selectedData.company || '';
        } else if (fieldKey.includes('_bizno') || fieldKey.includes('_business_number')) {
            mappedValue = selectedData.business_number || selectedData.company_business_number || '';
        } else if (fieldKey.includes('_id')) {
            if (tableType === 'contractor') {
                mappedValue = selectedData.worker_id || selectedData.contractor_id || selectedData.id || '';
            } else if (tableType === 'company') {
                mappedValue = selectedData.company_id || selectedData.id || '';
            } else if (tableType === 'building') {
                mappedValue = selectedData.building_id || selectedData.id || '';
            }
        } else if (fieldKey.includes('_name')) {
            if (tableType === 'contractor') {
                mappedValue = selectedData.worker_name || selectedData.contractor_name || selectedData.name || '';
            } else if (tableType === 'company') {
                mappedValue = selectedData.company_name || selectedData.name || '';
            } else if (tableType === 'building') {
                mappedValue = selectedData.building_name || selectedData.name || '';
            }
        } else if (fieldKey.includes('_dept') || fieldKey.includes('_department')) {
            mappedValue = selectedData.department_name || selectedData.department || '';
        } else if (fieldKey.includes('_division')) {
            mappedValue = selectedData.division_name || selectedData.division || '';
        } else if (fieldKey.includes('_code')) {
            if (tableType === 'building') {
                mappedValue = selectedData.building_code || selectedData.code || '';
            } else if (tableType === 'department') {
                mappedValue = selectedData.dept_code || selectedData.department_code || '';
            } else if (tableType === 'division') {
                mappedValue = selectedData.division_code || selectedData.code || '';
            } else {
                mappedValue = selectedData.code || '';
            }
        } else if (fieldKey.includes('_parent')) {
            if (tableType === 'division') {
                mappedValue = selectedData.parent_division_code || '';
            }
        } else if (fieldKey.includes('_text')) {
            if (fieldKey.includes('사업자번호') || fieldKey.includes('_bizno')) {
                mappedValue = selectedData.business_number || selectedData.company_business_number || '';
            } else if (fieldKey.includes('소속업체') || fieldKey.includes('업체명')) {
                mappedValue = selectedData.company_name || selectedData.company || '';
            } else if (fieldKey.includes('부서') || fieldKey.includes('_dept')) {
                mappedValue = selectedData.department_name || selectedData.department || '';
            } else if (fieldKey.includes('건물') || fieldKey.includes('_building')) {
                mappedValue = selectedData.building_name || selectedData.name || '';
            } else {
                mappedValue = selectedData.name || selectedData.employee_name || selectedData.company_name || selectedData.building_name || '';
            }
        }

        if (typeof mappedValue !== 'undefined') {
            applyFieldValue(field, mappedValue, { background: '#f8f9fa' });
        }
    });

    markContractorCompanyFields(document);
}


function markContractorCompanyFields(context) {
    const scope = context || document;
    const inputs = scope.querySelectorAll('input[data-field][id$="_company"]');
    inputs.forEach(input => {
        const tableType = (input.getAttribute('data-table-type') || input.getAttribute('data-table-group') || '').toLowerCase();
        if (tableType === 'contractor') {
            input.classList.add('linked-field');
            input.readOnly = true;
            input.style.backgroundColor = '#f8f9fa';
            const wrapper = input.closest('.input-group') || input.closest('.popup-input-wrapper');
            if (wrapper) {
                const triggerBtn = wrapper.querySelector('button');
                if (triggerBtn) {
                    triggerBtn.style.display = 'none';
                }
            }
        }
    });
}

// 담당자 검색 팝업 열기
function openPersonSearch(fieldKey) {
    const width = 1000;
    const height = 600;
    const left = (screen.width - width) / 2;
    const top = (screen.height - height) / 2;
    
    const popupOptions = [
        `width=${width}`,
        `height=${height}`,
        `left=${left}`,
        `top=${top}`,
        'scrollbars=yes',
        'resizable=yes',
        'toolbar=no',
        'menubar=no',
        'location=no',
        'status=no'
    ].join(',');
    
    const popupUrl = `/search-popup?type=person&field=${fieldKey}`;
    const popup = window.open(popupUrl, 'personSearch', popupOptions);
    
    if (!popup || popup.closed || typeof popup.closed === 'undefined') {
        console.warn('Popup blocked: person search');
        return;
    }
    
    popup.focus();
}


// 업체 검색 팝업 열기
function openCompanySearch(fieldKey) {
    const width = 1000;
    const height = 600;
    const left = (screen.width - width) / 2;
    const top = (screen.height - height) / 2;
    
    const popupOptions = [
        `width=${width}`,
        `height=${height}`,
        `left=${left}`,
        `top=${top}`,
        'scrollbars=yes',
        'resizable=yes',
        'toolbar=no',
        'menubar=no',
        'location=no',
        'status=no'
    ].join(',');
    
    const popupUrl = `/search-popup?type=company&field=${fieldKey}`;
    const popup = window.open(popupUrl, 'companySearch', popupOptions);
    
    if (!popup || popup.closed || typeof popup.closed === 'undefined') {
        console.warn('Popup blocked: company search');
        return;
    }
    
    popup.focus();
}

// 업체 선택 콜백
window.receiveCompanySelection = function(fieldKey, data) {
    console.log('receiveCompanySelection 호출:', fieldKey, data);

    // 메인 필드 업데이트
    const mainField = document.getElementById(fieldKey);
    if (mainField) {
        applyFieldValue(mainField, data.company_name || '', { background: '#f3f4f6' });

        // table_group 기반 linked 필드 자동 업데이트
        const tableGroup = mainField.getAttribute('data-table-group');
        if (tableGroup) {
            updateLinkedFieldsByTableGroup(fieldKey, data, tableGroup);
        }
    }

    // 기존 방식 유지 (호환성을 위해)
    // 사업자번호 필드 패턴들
    const patterns = [
        {suffix: '_business_number', value: data.business_number || ''},
        {suffix: '_bizno', value: data.business_number || ''}
    ];

    patterns.forEach(pattern => {
        const field = document.getElementById(fieldKey + pattern.suffix);
        if (field && pattern.value !== undefined) {
            applyFieldValue(field, pattern.value, { background: '#f8f9fa' });
        }
    });
};

// 건물 검색 팝업 열기
function openBuildingSearch(fieldKey) {
    const width = 1000;
    const height = 600;
    const left = (screen.width - width) / 2;
    const top = (screen.height - height) / 2;
    
    const popupOptions = [
        `width=${width}`,
        `height=${height}`,
        `left=${left}`,
        `top=${top}`,
        'scrollbars=yes',
        'resizable=yes',
        'toolbar=no',
        'menubar=no',
        'location=no',
        'status=no'
    ].join(',');
    
    const popupUrl = `/search-popup?type=building&field=${fieldKey}`;
    const popup = window.open(popupUrl, 'buildingSearch', popupOptions);
    
    if (!popup || popup.closed || typeof popup.closed === 'undefined') {
        console.warn('Popup blocked: building search');
        return;
    }
    
    popup.focus();
}


// 부서 검색 팝업 열기
function openDepartmentSearch(fieldKey) {
    const width = 1000;
    const height = 600;
    const left = (screen.width - width) / 2;
    const top = (screen.height - height) / 2;
    
    const popupOptions = [
        `width=${width}`,
        `height=${height}`,
        `left=${left}`,
        `top=${top}`,
        'scrollbars=yes',
        'resizable=yes',
        'toolbar=no',
        'menubar=no',
        'location=no',
        'status=no'
    ].join(',');
    
    const popupUrl = `/search-popup?type=department&field=${fieldKey}`;
    const popup = window.open(popupUrl, 'departmentSearch', popupOptions);
    
    if (!popup || popup.closed || typeof popup.closed === 'undefined') {
        console.warn('Popup blocked: department search');
        return;
    }
    
    popup.focus();
}


// 협력사 근로자 검색 팝업 열기
function openContractorSearch(fieldKey) {
    const width = 1000;
    const height = 600;
    const left = (screen.width - width) / 2;
    const top = (screen.height - height) / 2;
    
    const popupOptions = [
        `width=${width}`,
        `height=${height}`,
        `left=${left}`,
        `top=${top}`,
        'scrollbars=yes',
        'resizable=yes',
        'toolbar=no',
        'menubar=no',
        'location=no',
        'status=no'
    ].join(',');
    
    const popupUrl = `/search-popup?type=contractor&field=${fieldKey}`;
    const popup = window.open(popupUrl, 'contractorSearch', popupOptions);
    
    if (!popup || popup.closed || typeof popup.closed === 'undefined') {
        console.warn('Popup blocked: contractor search');
        return;
    }
    
    popup.focus();
}

// ======================================
// 통합 팝업 선택 콜백 함수들 - 완전 통합 버전
// ======================================

// 테이블 선택 콜백
window.receiveTableSelection = function(fieldKey, data) {

    // follow-sop-detail.html의 특이형태 지원
    if (arguments.length === 1 && typeof fieldKey === 'object') {
        data = fieldKey;
        fieldKey = window.currentFieldKey;
    }

    const mainField = document.getElementById(fieldKey);
    if (mainField) {
        applyFieldValue(mainField, data.display_value || data.name || data.display_name || '', { background: '#f3f4f6' });
    }

    const idField = document.getElementById(fieldKey + '_id');
    if (idField) {
        applyFieldValue(idField, data.id || '', { background: '#f3f4f6' });
    }
};

// 담당자 선택 콜백
window.receivePersonSelection = function(fieldKey, data) {

    const mainField = document.getElementById(fieldKey);
    if (mainField) {
        applyFieldValue(mainField, data.employee_name || data.name || '', { background: '#f3f4f6' });

        // table_group 기반 linked 필드 자동 업데이트
        const tableGroup = mainField.getAttribute('data-table-group');
        if (tableGroup) {
            updateLinkedFieldsByTableGroup(fieldKey, data, tableGroup);
        }
    }

    const patterns = [
        {suffix: '_id', value: data.employee_id || data.id || ''},
        {suffix: '_dept', value: data.department_name || data.department || ''}
    ];

    patterns.forEach(pattern => {
        const field = document.getElementById(fieldKey + pattern.suffix);
        if (field && pattern.value !== undefined) {
            applyFieldValue(field, pattern.value, { background: '#f8f9fa' });
        }
    });
};


// 건물 선택 콜백
window.receiveBuildingSelection = function(fieldKey, data) {

    const mainField = document.getElementById(fieldKey);
    if (mainField) {
        applyFieldValue(mainField, data.building_name || '', { background: '#f3f4f6' });

        // table_group 기반 linked 필드 자동 업데이트
        const tableGroup = mainField.getAttribute('data-table-group');
        if (tableGroup) {
            updateLinkedFieldsByTableGroup(fieldKey, data, tableGroup);
        }
    }

    const codeField = document.getElementById(fieldKey + '_code');
    if (codeField) {
        applyFieldValue(codeField, data.building_code || '', { background: '#f3f4f6' });
    }
};

// 부서 선택 콜백
window.receiveDepartmentSelection = function(fieldKey, data) {

    const mainField = document.getElementById(fieldKey);
    if (mainField) {
        applyFieldValue(mainField, data.dept_name || data.department_name || '', { background: '#f3f4f6' });

        // table_group 기반 linked 필드 자동 업데이트
        const tableGroup = mainField.getAttribute('data-table-group');
        if (tableGroup) {
            updateLinkedFieldsByTableGroup(fieldKey, data, tableGroup);
        }
    }

    // 기존 방식 유지 (호환성을 위해)
    // _code 필드 업데이트
    const codeField = document.getElementById(fieldKey + '_code');
    if (codeField) {
        applyFieldValue(codeField, data.dept_code || data.department_code || '', { background: '#f3f4f6' });
    }
};

// 사업부 검색 팝업 열기
function openDivisionSearch(fieldKey) {
    const width = 1000;
    const height = 600;
    const left = (screen.width - width) / 2;
    const top = (screen.height - height) / 2;

    const popupOptions = [
        `width=${width}`,
        `height=${height}`,
        `left=${left}`,
        `top=${top}`,
        'scrollbars=yes',
        'resizable=yes'
    ].join(',');

    const popupUrl = `/search-popup?type=division&field=${fieldKey}`;
    const popup = window.open(popupUrl, 'divisionSearch', popupOptions);

    if (!popup || popup.closed) {
        console.warn('Popup blocked: division search');
        return;
    }

    popup.focus();
}

// 사업부 선택 콜백
window.receiveDivisionSelection = function(fieldKey, data) {
    console.log('Division selected:', fieldKey, data);

    const mainField = document.getElementById(fieldKey) ||
                      document.querySelector(`[data-field="${fieldKey}"]`);

    if (mainField) {
        applyFieldValue(mainField, data.division_name || '', { background: '#f3f4f6' });

        const tableGroup = mainField.getAttribute('data-table-group');
        if (tableGroup) {
            updateLinkedFieldsByTableGroup(fieldKey, data, tableGroup);
        }
    }

    // 사업부코드 필드 업데이트
    const codeField = document.getElementById(fieldKey + '_code') ||
                      document.querySelector(`[data-field="${fieldKey}_code"]`);
    if (codeField) {
        applyFieldValue(codeField, data.division_code || '', { background: '#f3f4f6' });
    }

    // 상위사업부 필드 업데이트
    const parentField = document.getElementById(fieldKey + '_parent') ||
                        document.querySelector(`[data-field="${fieldKey}_parent"]`);
    if (parentField) {
        applyFieldValue(parentField, data.parent_division_code || '', { background: '#f3f4f6' });
    }
};

// 협력사 근로자 선택 콜백
window.receiveContractorSelection = function(fieldKey, data) {
    // 1. 메인 필드 업데이트
    const mainField = document.getElementById(fieldKey);
    if (mainField) {
        applyFieldValue(mainField, data.worker_name || data.contractor_name || data.name || '', { background: '#f3f4f6' });
    }

    // 2. 모든 가능한 linked 필드 패턴 처리
    const patterns = [
        // ID 필드들
        {suffix: '_id', value: data.worker_id || data.contractor_id || data.id || ''},

        // 업체명 필드들 (실제 사용되는 패턴들)
        {suffix: '_company', value: data.company_name || data.company || ''},
        {suffix: '_company_name', value: data.company_name || data.company || ''},

        // 사업자번호 필드들 (실제 사용되는 패턴들)
        {suffix: '_bizno', value: data.business_number || ''},
        {suffix: '_business_number', value: data.business_number || ''}
    ];

    patterns.forEach(pattern => {
        const field = document.getElementById(fieldKey + pattern.suffix);
        if (field && pattern.value !== undefined) {
            applyFieldValue(field, pattern.value, { background: '#f8f9fa' });
        }
    });

};

console.log('✅ Popup handler loaded');

markContractorCompanyFields(document);

// 페이지 로드 후 초기화 (디버깅 코드 제거됨)
window.openTableSearch = function openTableSearch(fieldKey) {
    const input = document.getElementById(fieldKey);
    if (!input) {
        alert('필드를 찾을 수 없습니다.');
        return;
    }
    const tableGroup = input.getAttribute('data-table-group') || input.getAttribute('data-table-type');
    window.currentTableSearchField = fieldKey;
    window.currentTableSearchGroup = tableGroup;
    const modal = document.getElementById('table-search-modal');
    if (!modal) {
        alert('검색 모달이 초기화되지 않았습니다.');
        return;
    }
    modal.style.display = 'block';
    document.getElementById('table-search-query').value = '';
    document.getElementById('table-search-results').innerHTML = '';
    document.getElementById('table-search-query').focus();
}

function closeTableSearch() {
    const modal = document.getElementById('table-search-modal');
    if (modal) {
        modal.style.display = 'none';
    }
    window.currentTableSearchField = null;
    window.currentTableSearchGroup = null;
}

async function performTableSearch() {
    const query = document.getElementById('table-search-query').value.trim();
    if (!query) {
        alert('검색어를 입력하세요.');
        return;
    }
    const tableGroup = window.currentTableSearchGroup;
    if (!tableGroup) {
        alert('검색 그룹이 지정되지 않았습니다.');
        return;
    }
    const modal = document.getElementById('table-search-modal');
    const resultsContainer = document.getElementById('table-search-results');
    resultsContainer.innerHTML = '<p>검색 중...</p>';
    try {
        const response = await fetch(`/api/table-search?group=${encodeURIComponent(tableGroup)}&q=${encodeURIComponent(query)}`);
        if (!response.ok) {
            throw new Error(`검색 API 오류 (${response.status})`);
        }
        const data = await response.json();
        if (!Array.isArray(data) || data.length === 0) {
            resultsContainer.innerHTML = '<p>검색 결과가 없습니다.</p>';
            return;
        }
        resultsContainer.innerHTML = '';
        data.forEach(row => {
            const item = document.createElement('button');
            item.type = 'button';
            item.className = 'table-search-item';
            const label = row.display_name || row.name || row.title || row.code || JSON.stringify(row);
            item.textContent = label;
            item.onclick = () => selectTableSearchResult(row);
            resultsContainer.appendChild(item);
        });
    } catch (error) {
        console.error('Table search error:', error);
        resultsContainer.innerHTML = `<p>검색 중 오류가 발생했습니다: ${error.message}</p>`;
    }
}

function selectTableSearchResult(selectedData) {
    const fieldKey = window.currentTableSearchField;
    if (!fieldKey) {
        closeTableSearch();
        return;
    }
    const tableGroup = window.currentTableSearchGroup;
    const input = document.getElementById(fieldKey);
    if (input) {
        const label = selectedData.display_name || selectedData.name || selectedData.title || selectedData.code || JSON.stringify(selectedData);
        input.value = label;
    }
    const hidden = document.getElementById(`${fieldKey}_id`);
    if (hidden) {
        hidden.value = selectedData.id || selectedData.code || selectedData.uid || '';
    }
    const details = {};
    Object.keys(selectedData || {}).forEach(key => {
        if (key !== 'display_name') {
            details[key] = selectedData[key];
        }
    });
    updateLinkedFieldsByTableGroup(fieldKey, details, tableGroup);
    markContractorCompanyFields(document);
    closeTableSearch();
}

window.performTableSearch = performTableSearch;
window.closeTableSearch = closeTableSearch;
window.selectTableSearchResult = selectTableSearchResult;
