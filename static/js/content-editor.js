/**
 * Content Editor - 통합 붙여넣기 핸들러
 * 모든 detail/register 페이지의 detailed-content에서 사용
 */

(function() {
    'use strict';
    
    // DOM 준비 시 실행
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initContentEditor);
    } else {
        initContentEditor();
    }
    
    function initContentEditor() {
        const editor = document.getElementById('detailed-content');
        if (!editor) {
            console.log('detailed-content 요소를 찾을 수 없습니다.');
            return;
        }
        
        console.log('✅ Content Editor 초기화');
        
        // 붙여넣기 이벤트 핸들러
        editor.addEventListener('paste', function(e) {
            e.preventDefault();
            
            const clipboardData = e.clipboardData || window.clipboardData;
            
            // 1. 엑셀 표 처리 (우선순위 높음)
            const text = clipboardData.getData('text/plain');
            if (text && text.includes('\t') && text.includes('\n')) {
                console.log('📊 표 데이터 감지');
                if (handleTablePaste(text)) {
                    return;
                }
            }
            
            // 2. 이미지 처리
            const items = clipboardData.items;
            let imageHandled = false;
            for (let i = 0; i < items.length; i++) {
                const item = items[i];
                if (item.type.indexOf('image') !== -1) {
                    console.log('🖼️ 이미지 데이터 감지');
                    handleImagePaste(item);
                    imageHandled = true;
                    break;
                }
            }
            
            // 3. 일반 텍스트 처리
            if (!imageHandled && text) {
                console.log('📝 텍스트 데이터 처리');
                document.execCommand('insertText', false, text);
            }
        });
        
        // 드래그 앤 드롭 지원
        editor.addEventListener('drop', function(e) {
            e.preventDefault();
            const files = e.dataTransfer.files;
            
            for (let file of files) {
                if (file.type.startsWith('image/')) {
                    handleImageFile(file);
                }
            }
        });
        
        editor.addEventListener('dragover', function(e) {
            e.preventDefault();
        });
    }
    
    // 표 붙여넣기 처리
    function handleTablePaste(text) {
        const rows = text.trim().split('\n');
        if (rows.length <= 1) return false;
        
        // 첫 행에 탭이 있는지 확인 (표 형식 검증)
        if (!rows[0].includes('\t')) return false;
        
        const table = document.createElement('table');
        table.style.cssText = 'border-collapse: collapse; width: 100%; margin: 15px 0; border: 1px solid #e1e5e9;';
        
        rows.forEach((row, rowIndex) => {
            const cells = row.split('\t');
            const tr = document.createElement('tr');
            
            cells.forEach(cell => {
                const cellElement = document.createElement(rowIndex === 0 ? 'th' : 'td');
                cellElement.textContent = cell.trim();
                cellElement.style.cssText = 'border: 1px solid #e1e5e9; padding: 8px; text-align: left;';
                
                if (rowIndex === 0) {
                    cellElement.style.backgroundColor = '#f8f9fa';
                    cellElement.style.fontWeight = 'bold';
                }
                
                tr.appendChild(cellElement);
            });
            
            if (rowIndex > 0 && rowIndex % 2 === 0) {
                tr.style.backgroundColor = '#f8f9fa';
            }
            
            table.appendChild(tr);
        });
        
        insertAtCursor(table);
        
        // 표 뒤에 줄바꿈 추가
        const br = document.createElement('br');
        insertAtCursor(br);
        
        return true;
    }
    
    // 이미지 붙여넣기 처리
    function handleImagePaste(item) {
        const blob = item.getAsFile();
        
        // 크기 제한 (5MB)
        if (blob.size > 5 * 1024 * 1024) {
            alert('이미지 크기는 5MB 이하로 제한됩니다.');
            return;
        }
        
        handleImageFile(blob);
    }
    
    // 이미지 파일 처리
    function handleImageFile(file) {
        const reader = new FileReader();
        
        reader.onload = function(e) {
            const img = document.createElement('img');
            img.src = e.target.result;
            img.style.cssText = 'max-width: 100%; height: auto; margin: 10px 0; border-radius: 4px;';
            
            insertAtCursor(img);
            
            // 이미지 뒤에 줄바꿈 추가
            const br = document.createElement('br');
            insertAtCursor(br);
        };
        
        reader.readAsDataURL(file);
    }
    
    // 커서 위치에 요소 삽입
    function insertAtCursor(element) {
        const selection = window.getSelection();
        
        if (selection.rangeCount > 0) {
            const range = selection.getRangeAt(0);
            range.insertNode(element);
            
            // 커서를 삽입한 요소 뒤로 이동
            range.setStartAfter(element);
            range.setEndAfter(element);
            selection.removeAllRanges();
            selection.addRange(range);
        } else {
            // 커서가 없으면 끝에 추가
            const editor = document.getElementById('detailed-content');
            editor.appendChild(element);
        }
    }
    
    // 전역 함수로 노출 (필요시 외부에서 사용)
    window.ContentEditor = {
        init: initContentEditor,
        handleTablePaste: handleTablePaste,
        handleImagePaste: handleImagePaste,
        insertAtCursor: insertAtCursor
    };
})();