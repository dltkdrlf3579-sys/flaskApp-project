/**
 * 통합 팝업 핸들러
 * 모든 보드에서 공통으로 사용하는 팝업 처리 함수
 */

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
        alert('팝업이 차단되었습니다. 브라우저의 팝업 차단을 해제해주세요.');
        return;
    }
    
    popup.focus();
}

// 담당자 선택 콜백
window.receivePersonSelection = function(fieldKey, data) {
    console.log('receivePersonSelection 호출:', fieldKey, data);
    
    // 메인 필드 업데이트
    const mainField = document.getElementById(fieldKey);
    if (mainField) {
        mainField.value = data.employee_name || data.name || '';
    }
    
    // _id 필드 업데이트
    const idField = document.getElementById(fieldKey + '_id');
    if (idField) {
        idField.value = data.employee_id || data.id || '';
        idField.setAttribute('readonly', true);
        idField.style.backgroundColor = '#f8f9fa';
    }
    
    // _dept 필드 업데이트
    const deptField = document.getElementById(fieldKey + '_dept');
    if (deptField && (data.department_name || data.department)) {
        deptField.value = data.department_name || data.department || '';
        deptField.setAttribute('readonly', true);
        deptField.style.backgroundColor = '#f8f9fa';
    }
};

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
        alert('팝업이 차단되었습니다. 브라우저의 팝업 차단을 해제해주세요.');
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
        mainField.value = data.company_name || '';
    }
    
    // _bizno 필드 업데이트 (통일된 접미사)
    const biznoField = document.getElementById(fieldKey + '_bizno');
    if (biznoField) {
        biznoField.value = data.business_number || '';
        biznoField.setAttribute('readonly', true);
        biznoField.style.backgroundColor = '#f8f9fa';
    }
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
        alert('팝업이 차단되었습니다. 브라우저의 팝업 차단을 해제해주세요.');
        return;
    }
    
    popup.focus();
}

// 건물 선택 콜백
window.receiveBuildingSelection = function(fieldKey, data) {
    console.log('receiveBuildingSelection 호출:', fieldKey, data);
    
    // 메인 필드 업데이트
    const mainField = document.getElementById(fieldKey);
    if (mainField) {
        mainField.value = data.building_name || '';
    }
    
    // _code 필드 업데이트
    const codeField = document.getElementById(fieldKey + '_code');
    if (codeField) {
        codeField.value = data.building_code || '';
        codeField.setAttribute('readonly', true);
        codeField.style.backgroundColor = '#f8f9fa';
    }
};

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
        alert('팝업이 차단되었습니다. 브라우저의 팝업 차단을 해제해주세요.');
        return;
    }
    
    popup.focus();
}

// 부서 선택 콜백
window.receiveDepartmentSelection = function(fieldKey, data) {
    console.log('receiveDepartmentSelection 호출:', fieldKey, data);
    
    // 메인 필드 업데이트
    const mainField = document.getElementById(fieldKey);
    if (mainField) {
        mainField.value = data.dept_name || data.department_name || '';
    }
    
    // _code 필드 업데이트
    const codeField = document.getElementById(fieldKey + '_code');
    if (codeField) {
        codeField.value = data.dept_code || data.department_code || '';
        codeField.setAttribute('readonly', true);
        codeField.style.backgroundColor = '#f8f9fa';
    }
};

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
        alert('팝업이 차단되었습니다. 브라우저의 팝업 차단을 해제해주세요.');
        return;
    }
    
    popup.focus();
}

// 협력사 근로자 선택 콜백
window.receiveContractorSelection = function(fieldKey, data) {
    console.log('receiveContractorSelection 호출:', fieldKey, data);
    
    // 메인 필드 업데이트
    const mainField = document.getElementById(fieldKey);
    if (mainField) {
        mainField.value = data.worker_name || data.contractor_name || data.name || '';
    }
    
    // _id 필드 업데이트
    const idField = document.getElementById(fieldKey + '_id');
    if (idField) {
        idField.value = data.worker_id || data.contractor_id || data.id || '';
        idField.setAttribute('readonly', true);
        idField.style.backgroundColor = '#f8f9fa';
    }
    
    // _company_name 필드 업데이트 (소속업체)
    const companyField = document.getElementById(fieldKey + '_company_name');
    if (companyField) {
        companyField.value = data.company_name || data.company || '';
        companyField.setAttribute('readonly', true);
        companyField.style.backgroundColor = '#f8f9fa';
    }
    
    // _bizno 필드 업데이트 (통일된 접미사)
    const biznoField = document.getElementById(fieldKey + '_bizno');
    if (biznoField) {
        biznoField.value = data.business_number || '';
        biznoField.setAttribute('readonly', true);
        biznoField.style.backgroundColor = '#f8f9fa';
    }
};

console.log('✅ Popup handler loaded');