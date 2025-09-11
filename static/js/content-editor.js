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

        // CKEditor 모드일 때는 간섭 금지 (basic 모드만 사용)
        if (editor.getAttribute('data-editor-mode') !== 'basic') {
            console.log('ContentEditor skipped (not basic mode)');
            return;
        }
        
        console.log('✅ Content Editor 초기화');
        
        // 붙여넣기 이벤트 핸들러 (HTML/이미지/표 우선)
        editor.addEventListener('paste', function(e) {
            let handled = false;

            const cd = e.clipboardData || window.clipboardData;
            if (!cd) return;
            
            const html = cd.getData('text/html');
            const text = cd.getData('text/plain');
            const uriList = (cd.getData && cd.getData('text/uri-list')) ? cd.getData('text/uri-list') : '';
            const items = cd.items || [];
            const files = cd.files || [];

            // 1) HTML 우선: Excel/Word 등 리치 HTML을 살려서 붙여넣기 (표/스타일 유지)
            if (html && /<\s*table[\s>]/i.test(html)) {
                console.log('📋 HTML 표 감지 - 원본 스타일 유지 붙여넣기');
                const sanitized = sanitizeHtml(html);
                insertHtmlAtCursor(sanitized);
                handled = true;
                e.preventDefault();
                return;
            }

            // 2) 이미지 (클립보드 파일)
            for (let i = 0; i < items.length; i++) {
                const it = items[i];
                if (it && it.type && it.type.indexOf('image') !== -1) {
                    console.log('🖼️ 이미지 데이터 감지');
                    handleImagePaste(it);
                    handled = true;
                    e.preventDefault();
                    return;
                }
            }
            // 일부 환경은 items가 비어 있고 files에만 담김
            if (files && files.length) {
                for (let f of files) {
                    if (f && f.type && f.type.indexOf('image') !== -1) {
                        handleImageFile(f);
                        handled = true;
                        e.preventDefault();
                        return;
                    }
                }
            }

            // 2-1) URI 리스트로 온 이미지 URL 처리 (일부 브라우저/사이트)
            if (uriList) {
                const first = uriList.split('\n').find(line => line && !line.startsWith('#')) || '';
                if (/^https?:\/\//i.test(first) && /(\.png|\.jpg|\.jpeg|\.gif|\.webp|\.bmp)(\?.*)?$/i.test(first)) {
                    const imgHtml = `<img src="${first}" style="max-width:100%;height:auto;margin:10px 0;border-radius:4px;" />`;
                    insertHtmlAtCursor(imgHtml);
                    handled = true;
                    e.preventDefault();
                    return;
                }
            }

            // 3) 탭/개행 표 → 간이 표로 변환
            if (text && text.includes('\t') && text.includes('\n')) {
                console.log('📊 표 데이터 감지 (텍스트 기반)');
                if (handleTablePaste(text)) return;
            }

            // 4) 일반 HTML (표는 아니지만 굵기/줄바꿈 등 유지)
            if (html) {
                const sanitized = sanitizeHtml(html);
                insertHtmlAtCursor(sanitized);
                handled = true;
                e.preventDefault();
                return;
            }

            // 5) 일반 텍스트
            if (text) {
                console.log('📝 텍스트 데이터 처리');
                document.execCommand('insertText', false, text);
                handled = true;
                e.preventDefault();
            }

            // 아무 케이스에도 매칭되지 않으면 기본 동작 허용 (브라우저 기본 붙여넣기)
            if (!handled) {
                // do nothing (no preventDefault)
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

        // 포커스 유틸
        function focusEditable(el){
            try {
                el.focus();
                const range = document.createRange();
                range.selectNodeContents(el);
                range.collapse(false);
                const sel = window.getSelection();
                sel.removeAllRanges();
                sel.addRange(range);
            } catch (_) {
                // ignore
            }
        }

        // 문서 전역 붙여넣기 폴백 (타겟이 에디터가 아닐 때도 처리)
        document.addEventListener('paste', function(ev){
            if (!editor) return;
            const within = ev.composedPath ? ev.composedPath().includes(editor) : editor.contains(ev.target);
            if (within) return; // 에디터 내부는 개별 핸들러가 처리

            const cd = ev.clipboardData || window.clipboardData;
            if (!cd) return;

            const html = cd.getData('text/html');
            const uriList = cd.getData && cd.getData('text/uri-list') ? cd.getData('text/uri-list') : '';

            // 1) 이미지 URL (uri-list)
            if (uriList) {
                const first = uriList.split('\n').find(line => line && !line.startsWith('#')) || '';
                if (/^https?:\/\//i.test(first) && /(\.png|\.jpg|\.jpeg|\.gif|\.webp|\.bmp)(\?.*)?$/i.test(first)) {
                    focusEditable(editor);
                    insertHtmlAtCursor(`<img src="${first}" style="max-width:100%;height:auto;margin:10px 0;border-radius:4px;" />`);
                    ev.preventDefault();
                    return;
                }
            }
            // 2) HTML에 이미지가 포함된 경우
            if (html && /<\s*img[\s>]/i.test(html)) {
                focusEditable(editor);
                insertHtmlAtCursor(sanitizeHtml(html));
                ev.preventDefault();
                return;
            }
            // 3) 파일/아이템 이미지
            const items = cd.items || [];
            for (let i=0;i<items.length;i++){
                const it = items[i];
                if (it && it.type && it.type.indexOf('image') !== -1){
                    focusEditable(editor);
                    handleImagePaste(it);
                    ev.preventDefault();
                    return;
                }
            }
            const files = cd.files || [];
            for (let f of files){
                if (f && f.type && f.type.indexOf('image') !== -1){
                    focusEditable(editor);
                    handleImageFile(f);
                    ev.preventDefault();
                    return;
                }
            }
            // 나머지는 기본 붙여넣기 허용
        }, true);

        // Ctrl+V 감지 시, 에디터 포커스 보장 (일부 브라우저에서 타겟 미지정으로 무반응 방지)
        document.addEventListener('keydown', function(k){
            try {
                if ((k.ctrlKey || k.metaKey) && (k.key === 'v' || k.key === 'V')) {
                    if (document.activeElement !== editor) {
                        focusEditable(editor);
                    }
                }
            } catch(_){}
        }, true);
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

    // HTML 문자열을 커서 위치에 삽입
    function insertHtmlAtCursor(htmlString) {
        const selection = window.getSelection();
        const range = selection.rangeCount ? selection.getRangeAt(0) : null;
        const temp = document.createElement('div');
        temp.innerHTML = htmlString;
        const frag = document.createDocumentFragment();
        let node;
        while ((node = temp.firstChild)) {
            frag.appendChild(node);
        }
        if (range) {
            range.deleteContents();
            range.insertNode(frag);
        } else {
            const editor = document.getElementById('detailed-content');
            editor.appendChild(frag);
        }
    }

    // 안전한 HTML 정제: 표/스타일/굵기/줄바꿈/이미지(data:) 허용
    function sanitizeHtml(html) {
        try {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            // 위험 태그 제거
            doc.querySelectorAll('script, iframe, object, embed').forEach(n => n.remove());
            // style 태그는 제거, 인라인 스타일만 유지
            doc.querySelectorAll('style').forEach(n => n.remove());

            const allowedTags = new Set(['table','thead','tbody','tr','th','td','colgroup','col',
                'p','br','b','strong','i','u','span','div','ul','ol','li','img']);
            const allowedAttrs = new Set(['style','colspan','rowspan','src','srcset','alt','width','height','align']);

            const walker = doc.createTreeWalker(doc.body, NodeFilter.SHOW_ELEMENT, null);
            const toRemove = [];
            while (walker.nextNode()) {
                const el = walker.currentNode;
                if (!allowedTags.has(el.tagName.toLowerCase())) {
                    toRemove.push(el);
                    continue;
                }
                // 허용 속성만 유지
                [...el.attributes].forEach(attr => {
                    const name = attr.name.toLowerCase();
                    if (!allowedAttrs.has(name)) {
                        el.removeAttribute(attr.name);
                    }
                });
                // 이미지 src 안전 처리: data:image/* 만 허용
                if (el.tagName.toLowerCase() === 'img') {
                    const src = el.getAttribute('src') || '';
                    // 허용: data:, https:, http:, blob:
                    const ok = src.startsWith('data:image/') || src.startsWith('https://') || src.startsWith('http://') || src.startsWith('blob:');
                    if (!ok) {
                        el.remove();
                    }
                    // 크기 스타일 기본값
                    if (!el.style.maxWidth) el.style.maxWidth = '100%';
                    if (!el.style.height) el.style.height = 'auto';
                    el.style.margin = el.style.margin || '10px 0';
                    el.style.borderRadius = el.style.borderRadius || '4px';
                }
            }
            toRemove.forEach(n => n.remove());

            // 엑셀 표 기본 테이블 스타일 보강 (없을 때만)
            doc.querySelectorAll('table').forEach(t => {
                if (!t.style.borderCollapse) t.style.borderCollapse = 'collapse';
                if (!t.style.width) t.style.width = '100%';
                if (!t.style.margin) t.style.margin = '15px 0';
                t.style.border = t.style.border || '1px solid #e1e5e9';
            });
            doc.querySelectorAll('th,td').forEach(c => {
                c.style.border = c.style.border || '1px solid #e1e5e9';
                c.style.padding = c.style.padding || '8px';
                c.style.textAlign = c.style.textAlign || 'left';
            });
            doc.querySelectorAll('tr:nth-child(even)').forEach(r => {
                if (!r.style.backgroundColor) r.style.backgroundColor = '#f8f9fa';
            });

            return (doc.body && doc.body.innerHTML) ? doc.body.innerHTML : html;
        } catch (e) {
            console.warn('sanitizeHtml failed', e);
            return html;
        }
    }
    
    // 전역 함수로 노출 (필요시 외부에서 사용)
    window.ContentEditor = {
        init: initContentEditor,
        handleTablePaste: handleTablePaste,
        handleImagePaste: handleImagePaste,
        insertAtCursor: insertAtCursor,
        insertHtmlAtCursor: insertHtmlAtCursor,
        sanitizeHtml: sanitizeHtml
    };
})();
