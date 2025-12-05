/**
 * 관리자 컬럼 관리 공통 모듈
 * 모든 보드의 admin columns 페이지에서 사용
 */

// 전역 변수
let columns = [];
let pendingColumns = [];
let editingId = null;

// API 엔드포인트 설정 (페이지에서 설정해야 함)
let API_ENDPOINT = '';

/**
 * 컬럼 목록 로드
 * 모든 컬럼을 로드 (비활성 포함)
 */
function loadColumns() {
    if (!API_ENDPOINT) {
        console.error('API_ENDPOINT가 설정되지 않았습니다.');
        return;
    }
    
    fetch(API_ENDPOINT)
        .then(response => response.json())
        .then(data => {
            // 모든 컬럼을 표시 (비활성 포함)
            const allData = data;
            
            // 원본 저장
            columns = allData;
            // 작업용 복사본 생성 (플래그 초기화)
            pendingColumns = allData.map(col => {
                // 테이블 정보 복원 (DB에 저장된 경우)
                const column = {
                    ...col,
                    _isNew: false,
                    _modified: false,
                    _toDelete: false
                };
                
                // 메타데이터에서 테이블 정보 복원
                if (col.table_group) column._tableGroup = col.table_group;
                if (col.table_type) column._tableType = col.table_type;
                if (col.table_name) column._tableName = col.table_name;
                
                return column;
            });
            
            console.log('로드된 전체 컬럼:', pendingColumns.length, '개');
            console.log('활성 컬럼:', pendingColumns.filter(c => c.is_active).length, '개');
            console.log('비활성 컬럼:', pendingColumns.filter(c => !c.is_active).length, '개');
            
            renderColumns();
            updatePreview();
        })
        .catch(error => {
            console.error('컬럼 로드 오류:', error);
        });
}

/**
 * 컬럼 렌더링
 * renderColumns 함수는 각 페이지에서 구현
 */

/**
 * 활성/비활성 토글
 */
function toggleActive(id, isActive) {
    const index = pendingColumns.findIndex(c => String(c.id) === String(id));
    if (index !== -1 && !pendingColumns[index]._toDelete) {
        pendingColumns[index].is_active = isActive;
        if (!pendingColumns[index]._isNew) {
            pendingColumns[index]._modified = true;
        }
        // 비활성화는 삭제가 아님을 명확히 함
        console.log(`컬럼 ${id} ${isActive ? '활성화' : '비활성화'} 처리`);
        renderColumns();
        updatePreview();
    }
}

/**
 * 컬럼 카드 HTML 생성 (공통 스타일)
 */
function createColumnCard(column, index) {
    // 삭제된 컬럼은 표시하지 않음
    if (column._deleted) return '';
    
    // 상태 클래스 결정
    const inactiveClass = !column.is_active ? 'inactive-column' : '';
    const deletedClass = column._toDelete ? 'to-delete' : '';
    
    // 상태 배지 결정
    let statusBadge = '';
    if (!column._toDelete) {
        if (column._isNew) {
            statusBadge = '<span class="badge bg-success ms-2">추가</span>';
        } else if (column._modified) {
            statusBadge = '<span class="badge bg-warning ms-2">변경</span>';
        }
    }
    
    // 비활성 배지
    const inactiveBadge = !column.is_active ? '<span class="badge bg-secondary ms-2">비활성</span>' : '';
    
    // 삭제 예정 배지
    const deleteBadge = column._toDelete ? '<span class="badge bg-danger ms-2">삭제예정</span>' : '';
    
    return {
        className: `column-card d-flex align-items-center ${inactiveClass} ${deletedClass}`,
        dataId: column.id,
        statusBadge: statusBadge,
        inactiveBadge: inactiveBadge,
        deleteBadge: deleteBadge
    };
}

/**
 * 공통 CSS 스타일
 */
const commonStyles = `
    .inactive-column {
        opacity: 0.6;
        background: #f5f5f5;
    }
    
    .inactive-column .column-name {
        text-decoration: line-through;
        color: #999;
    }
    
    .to-delete {
        background: #ffe8e8 !important;
        border: 2px dashed #d32f2f;
    }
    
    .toggle-active {
        cursor: pointer;
    }
`;

/**
 * 초기화 시 공통 스타일 추가
 */
function initCommonStyles() {
    if (!document.getElementById('admin-columns-common-styles')) {
        const style = document.createElement('style');
        style.id = 'admin-columns-common-styles';
        style.textContent = commonStyles;
        document.head.appendChild(style);
    }
}

// 페이지 로드 시 초기화
if (typeof window !== 'undefined') {
    window.addEventListener('DOMContentLoaded', initCommonStyles);
}