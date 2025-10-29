// Sortable.js 초기화 헬퍼
(function() {
    'use strict';
    
    // Sortable 로드 확인
    function checkSortable() {
        if (typeof Sortable === 'undefined') {
            console.error('❌ Sortable.js가 로드되지 않았습니다.');
            
            // 로컬 파일 재시도
            const script = document.createElement('script');
            script.src = '/static/js/Sortable.min.js';
            script.onload = function() {
                console.log('✅ Sortable.js 로컬 파일 로드 성공');
                initializeSortable();
            };
            script.onerror = function() {
                console.error('❌ Sortable.js 로컬 파일도 로드 실패');
                alert('드래그 기능을 사용할 수 없습니다. 관리자에게 문의하세요.');
            };
            document.head.appendChild(script);
        } else {
            console.log('✅ Sortable.js 로드 완료');
            initializeSortable();
        }
    }
    
    // Sortable 초기화
    function initializeSortable() {
        // 섹션 드래그
        const sectionContainer = document.getElementById('sections-container');
        if (sectionContainer && typeof Sortable !== 'undefined') {
            new Sortable(sectionContainer, {
                animation: 150,
                handle: '.drag-handle',
                ghostClass: 'sortable-ghost',
                onEnd: function(evt) {
                    console.log('섹션 순서 변경:', evt.oldIndex, '→', evt.newIndex);
                    updateSectionOrders();
                }
            });
            console.log('✅ 섹션 드래그 초기화 완료');
        }
        
        // 컬럼 드래그
        document.querySelectorAll('.columns-container').forEach(function(container) {
            if (typeof Sortable !== 'undefined') {
                new Sortable(container, {
                    animation: 150,
                    handle: '.drag-handle',
                    ghostClass: 'sortable-ghost',
                    onEnd: function(evt) {
                        console.log('컬럼 순서 변경:', evt.oldIndex, '→', evt.newIndex);
                        updateColumnOrders();
                    }
                });
            }
        });
        console.log('✅ 컬럼 드래그 초기화 완료');
    }
    
    // DOM 준비 시 실행
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', checkSortable);
    } else {
        checkSortable();
    }
    
    // 전역 함수로 노출 (필요시 재초기화)
    window.reinitializeSortable = initializeSortable;
})();