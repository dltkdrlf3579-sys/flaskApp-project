/**
 * 통합 팝업 핸들러 v2.0
 * 모든 게시판에서 일관된 팝업 처리 제공
 * 기존 popup-handler.js를 대체하는 범용 솔루션
 */

class UniversalPopupManager {
    constructor() {
        this.config = {
            popup: {
                width: 1000,
                height: 600,
                options: [
                    'scrollbars=yes',
                    'resizable=yes', 
                    'toolbar=no',
                    'menubar=no',
                    'location=no',
                    'status=no'
                ]
            },
            // 팝업 타입별 설정
            types: {
                popup_person: {
                    endpoint: 'person',
                    windowName: 'personSearch',
                    linkedFields: ['_id', '_dept']
                },
                popup_company: {
                    endpoint: 'company', 
                    windowName: 'companySearch',
                    linkedFields: ['_bizno']
                },
                popup_building: {
                    endpoint: 'building',
                    windowName: 'buildingSearch', 
                    linkedFields: ['_code']
                },
                popup_department: {
                    endpoint: 'department',
                    windowName: 'departmentSearch',
                    linkedFields: ['_code']
                },
                popup_contractor: {
                    endpoint: 'contractor',
                    windowName: 'contractorSearch',
                    linkedFields: ['_id', '_company_name', '_bizno']
                }
            }
        };
        
        this.activePopups = new Map(); // 활성 팝업 추적
        this.initializeCallbacks();
    }

    _popupTypeToTable(popupType) {
        const mapping = {
            popup_person: 'person',
            popup_company: 'company',
            popup_department: 'department',
            popup_building: 'building',
            popup_contractor: 'contractor',
            popup_division: 'division'
        };
        return mapping[popupType] || '';
    }

    /**
     * 통합 팝업 열기
     * @param {string} fieldKey - 필드 키
     * @param {string} popupType - 팝업 타입 (popup_person, popup_company 등)
     */
    openPopup(fieldKey, popupType) {
        const typeConfig = this.config.types[popupType];
        if (!typeConfig) {
            console.error(`Unknown popup type: ${popupType}`);
            alert(`지원하지 않는 팝업 타입: ${popupType}`);
            return;
        }

        const { width, height, options } = this.config.popup;
        const left = (screen.width - width) / 2;
        const top = (screen.height - height) / 2;

        const popupOptions = [
            `width=${width}`,
            `height=${height}`,
            `left=${left}`,
            `top=${top}`,
            ...options
        ].join(',');

        const popupUrl = `/search-popup?type=${typeConfig.endpoint}&field=${fieldKey}`;
        const popup = window.open(popupUrl, typeConfig.windowName, popupOptions);

        if (!popup) {
            console.warn('Popup blocked:', popupUrl);
            const warning = document.querySelector('.popup-block-warning');
            if (warning) {
                warning.style.display = '';
            }
            return;
        }

        // 성공적으로 열림: 차단 경고 숨김
        const warning = document.querySelector('.popup-block-warning');
        if (warning) {
            warning.style.display = 'none';
        }

        // 활성 팝업 추적
        this.activePopups.set(fieldKey, {
            popup: popup,
            type: popupType,
            fieldKey: fieldKey
        });

        popup.focus();

        // 팝업 종료 감지
        this.monitorPopupClose(fieldKey, popup);
    }

    /**
     * 테이블 팝업 열기 (동적 설정 기반)
     * @param {string} fieldKey - 필드 키
     */
    openTablePopup(fieldKey) {
        // 섹션과 컬럼 데이터에서 테이블 설정 찾기
        let fieldConfig = null;
        
        if (typeof sections !== 'undefined' && typeof sectionColumns !== 'undefined') {
            // 섹션별로 컬럼 설정 검색
            sections.forEach(section => {
                const cols = sectionColumns[section.section_key] || [];
                const found = cols.find(col => col.column_key === fieldKey);
                if (found) fieldConfig = found;
            });
        }
        
        if (!fieldConfig || !fieldConfig.input_type_config) {
            console.warn('테이블 설정을 찾을 수 없습니다:', fieldKey);
            return;
        }
        
        const { width, height, options } = this.config.popup;
        const left = (screen.width - width) / 2;
        const top = (screen.height - height) / 2;
        
        const popupOptions = [
            `width=${width}`,
            `height=${height}`,
            `left=${left}`,
            `top=${top}`,
            ...options
        ].join(',');
        
        const tableConfig = JSON.parse(fieldConfig.input_type_config);
        const popupUrl = `/search-popup?type=table&field=${fieldKey}&table=${tableConfig.table_name}&callback=receiveTableSelection`;
        const popup = window.open(popupUrl, 'tableSearch', popupOptions);
        
        if (!popup || popup.closed || typeof popup.closed === 'undefined') {
            console.warn('Popup blocked: table search');
            return;
        }
        
        // 현재 필드 키 저장 (테이블 콜백용)
        window.currentFieldKey = fieldKey;
        
        popup.focus();
    }

    /**
     * 팝업 종료 모니터링
     * @param {string} fieldKey - 필드 키
     * @param {Window} popup - 팝업 윈도우
     */
    monitorPopupClose(fieldKey, popup) {
        const checkClosed = () => {
            if (popup.closed) {
                this.activePopups.delete(fieldKey);
                clearInterval(checkInterval);
            }
        };
        
        const checkInterval = setInterval(checkClosed, 1000);
    }

    /**
     * 전역 콜백 함수들 초기화
     */
    initializeCallbacks() {
        // 담당자 선택 콜백
        window.receivePersonSelection = (fieldKey, data) => {
            this.handleSelection(fieldKey, data, 'popup_person');
        };

        // 업체 선택 콜백
        window.receiveCompanySelection = (fieldKey, data) => {
            this.handleSelection(fieldKey, data, 'popup_company');
        };

        // 건물 선택 콜백
        window.receiveBuildingSelection = (fieldKey, data) => {
            this.handleSelection(fieldKey, data, 'popup_building');
        };

        // 부서 선택 콜백
        window.receiveDepartmentSelection = (fieldKey, data) => {
            this.handleSelection(fieldKey, data, 'popup_department');
        };

        // 협력사 근로자 선택 콜백
        window.receiveContractorSelection = (fieldKey, data) => {
            this.handleSelection(fieldKey, data, 'popup_contractor');
        };

        // 테이블 선택 콜백
        window.receiveTableSelection = (selectedItem) => {
            const fieldKey = window.currentFieldKey;
            if (!fieldKey) return;
            
            const mainField = document.getElementById(fieldKey);
            if (mainField) {
                mainField.value = selectedItem.display_value || selectedItem.name || '';
            }
            
            // _id 필드가 있으면 업데이트
            const idField = document.getElementById(fieldKey + '_id');
            if (idField && selectedItem.id) {
                idField.value = selectedItem.id;
            }
        };
    }

    /**
     * 통합 선택 결과 처리
     * @param {string} fieldKey - 필드 키
     * @param {Object} data - 선택된 데이터
     * @param {string} popupType - 팝업 타입
     */
    handleSelection(fieldKey, data, popupType) {
        console.log(`Selection received for ${popupType}:`, fieldKey, data);
        
        // 메인 필드 업데이트
        const mainField = document.getElementById(fieldKey);
        if (mainField) {
            let mainValue = '';
            
            switch (popupType) {
                case 'popup_person':
                    mainValue = data.employee_name || data.name || '';
                    break;
                case 'popup_company':
                    mainValue = data.company_name || '';
                    break;
                case 'popup_building':
                    mainValue = data.building_name || '';
                    break;
                case 'popup_department':
                    mainValue = data.dept_name || data.department_name || '';
                    break;
                case 'popup_contractor':
                    mainValue = data.worker_name || data.contractor_name || data.name || '';
                    break;
            }
            
            mainField.value = mainValue;
            try {
                mainField.dispatchEvent(new Event('input', { bubbles: true }));
                mainField.dispatchEvent(new Event('change', { bubbles: true }));
            } catch (err) {
                console.warn('Failed to dispatch input event for popup field', fieldKey, err);
            }
        }

        // 연관 필드들 업데이트
        this.updateLinkedFields(fieldKey, data, popupType);
        if (mainField) {
            this.updateLinkedFieldsByGroup(mainField, data, popupType);
        }

        // 활성 팝업 정리
        this.activePopups.delete(fieldKey);
    }

    /**
     * 연관 필드 업데이트
     * @param {string} fieldKey - 메인 필드 키
     * @param {Object} data - 선택된 데이터
     * @param {string} popupType - 팝업 타입
     */
    updateLinkedFields(fieldKey, data, popupType) {
        const typeConfig = this.config.types[popupType];
        if (!typeConfig || !typeConfig.linkedFields) return;
        
        typeConfig.linkedFields.forEach(suffix => {
            const linkedField = document.getElementById(fieldKey + suffix);
            if (!linkedField) return;
            
            let value = '';
            
            // 타입별 연관 필드 매핑
            switch (popupType) {
                case 'popup_person':
                    if (suffix === '_id') value = data.employee_id || data.id || '';
                    if (suffix === '_dept') value = data.department_name || data.department || '';
                    break;
                    
                case 'popup_company':
                    if (suffix === '_bizno') value = data.business_number || '';
                    break;
                    
                case 'popup_building':
                    if (suffix === '_code') value = data.building_code || '';
                    break;
                    
                case 'popup_department':
                    if (suffix === '_code') value = data.dept_code || data.department_code || '';
                    break;
                    
                case 'popup_contractor':
                    if (suffix === '_id') value = data.worker_id || data.contractor_id || data.id || '';
                    if (suffix === '_company_name') value = data.company_name || data.company || '';
                    if (suffix === '_bizno') value = data.business_number || '';
                    break;
            }
            
            linkedField.value = value;
            linkedField.setAttribute('readonly', true);
            linkedField.style.backgroundColor = '#f8f9fa';
            try {
                linkedField.dispatchEvent(new Event('input', { bubbles: true }));
                linkedField.dispatchEvent(new Event('change', { bubbles: true }));
            } catch (err) {
                console.warn('Failed to sync linked popup field', linkedField.id, err);
            }
        });
    }

    updateLinkedFieldsByGroup(mainField, selectedData, popupType) {
        if (!mainField) return;
        const tableGroup = mainField.getAttribute('data-table-group');
        if (!tableGroup) return;
        const tableType = mainField.getAttribute('data-table-type') || this._popupTypeToTable(popupType);
        const targetRowIdx = mainField.getAttribute('data-row-index');
        const linkedFields = document.querySelectorAll(`[data-table-group="${tableGroup}"]`);
        linkedFields.forEach(field => {
            if (field === mainField) {
                return;
            }
            const fieldRowIdx = field.getAttribute('data-row-index');
            if (targetRowIdx !== null && fieldRowIdx !== null && targetRowIdx !== fieldRowIdx) {
                return;
            }
            const fieldKey = field.getAttribute('data-field') || field.id || '';
            let value = '';

            if (fieldKey.includes('_company')) {
                value = selectedData.company_name || selectedData.company || '';
            } else if (fieldKey.includes('_bizno') || fieldKey.includes('_business_number')) {
                value = selectedData.business_number || selectedData.company_business_number || '';
            } else if (fieldKey.includes('_dept') || fieldKey.includes('_department')) {
                value = selectedData.department_name || selectedData.department || '';
            } else if (fieldKey.includes('_division')) {
                value = selectedData.division_name || selectedData.division || '';
            } else if (fieldKey.includes('_parent')) {
                value = selectedData.parent_division_code || selectedData.parent || '';
            } else if (fieldKey.includes('_code')) {
                if (tableType === 'building') {
                    value = selectedData.building_code || selectedData.code || '';
                } else if (tableType === 'department') {
                    value = selectedData.dept_code || selectedData.department_code || selectedData.code || '';
                } else if (tableType === 'division') {
                    value = selectedData.division_code || selectedData.code || '';
                } else {
                    value = selectedData.code || '';
                }
            } else if (fieldKey.includes('_id')) {
                if (tableType === 'contractor') {
                    value = selectedData.worker_id || selectedData.contractor_id || selectedData.id || '';
                } else if (tableType === 'company') {
                    value = selectedData.company_id || selectedData.id || '';
                } else if (tableType === 'building') {
                    value = selectedData.building_id || selectedData.id || '';
                } else {
                    value = selectedData.id || '';
                }
            } else if (fieldKey.includes('_name')) {
                value = selectedData.name || selectedData.employee_name || selectedData.contractor_name || selectedData.company_name || selectedData.building_name || '';
            }

            if (value !== undefined && value !== null) {
                field.value = value;
                field.setAttribute('readonly', true);
                field.style.backgroundColor = '#f8f9fa';
                try {
                    field.dispatchEvent(new Event('input', { bubbles: true }));
                    field.dispatchEvent(new Event('change', { bubbles: true }));
                } catch (err) {
                    console.warn('Failed to sync grouped field', field.id, err);
                }
            }
        });
    }

    /**
     * 필드 상태 초기화
     * @param {string} fieldKey - 필드 키
     */
    clearField(fieldKey) {
        const mainField = document.getElementById(fieldKey);
        if (mainField) {
            mainField.value = '';
        }
        
        // 연관 필드들도 초기화
        const possibleSuffixes = ['_id', '_dept', '_code', '_bizno', '_company_name'];
        possibleSuffixes.forEach(suffix => {
            const linkedField = document.getElementById(fieldKey + suffix);
            if (linkedField) {
                linkedField.value = '';
            }
        });
    }
}

// 전역 인스턴스 생성
const popupManager = new UniversalPopupManager();
window.popupManager = popupManager;

// 편의 함수들 (기존 코드 호환성)
function openUniversalPopup(fieldKey, popupType) {
    popupManager.openPopup(fieldKey, popupType);
}

function openPersonSearch(fieldKey) {
    popupManager.openPopup(fieldKey, 'popup_person');
}

function openCompanySearch(fieldKey) {
    popupManager.openPopup(fieldKey, 'popup_company');
}

function openBuildingSearch(fieldKey) {
    popupManager.openPopup(fieldKey, 'popup_building');
}

function openDepartmentSearch(fieldKey) {
    popupManager.openPopup(fieldKey, 'popup_department');
}

function openContractorSearch(fieldKey) {
    popupManager.openPopup(fieldKey, 'popup_contractor');
}

function openTablePopup(fieldKey) {
    popupManager.openTablePopup(fieldKey);
}

// 기존 openPopup 함수 호환성 (테이블 팝업용)
function openPopup(fieldKey) {
    popupManager.openTablePopup(fieldKey);
}

console.log('✅ Universal Popup Handler v2.0 loaded');
