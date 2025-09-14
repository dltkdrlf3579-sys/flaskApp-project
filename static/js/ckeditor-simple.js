/**
 * CKEditor 5 Simple Integration
 * 네이버 블로그 스타일 에디터 기능
 */

// CKEditor 초기화 함수
window.initCKEditor = function(elementId) {
    const element = document.querySelector(`#${elementId}`);
    if (!element) {
        console.error(`Element #${elementId} not found`);
        return;
    }
    
    // 이미 초기화되었는지 확인
    if (window[`editor_${elementId}`] || element.classList.contains('ck-editor__editable')) {
        console.log(`CKEditor already initialized for #${elementId}`);
        return;
    }
    
    // 기존 내용 가져오기
    let initialContent = '';
    if (element.hasAttribute('data-content')) {
        try {
            initialContent = JSON.parse(element.getAttribute('data-content'));
        } catch(e) {
            initialContent = element.getAttribute('data-content') || '';
        }
    } else if (element.tagName === 'TEXTAREA') {
        initialContent = element.value || '';
    } else {
        initialContent = element.innerHTML || '';
    }
    
    // CKEditor 5 Classic 생성
    // 글로벌 업로드 대기 카운터
    window.__ckeditorPendingUploads = window.__ckeditorPendingUploads || 0;

    ClassicEditor
        .create(element, {
            language: 'ko',
            toolbar: {
                items: [
                    'heading', '|',
                    'bold', 'italic', 'underline', 'strikethrough', '|',
                    'link', 'uploadImage', 'insertTable', '|',
                    'bulletedList', 'numberedList', '|',
                    'outdent', 'indent', '|',
                    'blockQuote', 'undo', 'redo'
                ]
            },
            image: {
                toolbar: ['imageTextAlternative', 'imageStyle:full', 'imageStyle:side']
            },
            table: {
                contentToolbar: ['tableColumn', 'tableRow', 'mergeTableCells']
            },
            // 이미지 업로드 어댑터
            simpleUpload: {
                uploadUrl: '/upload-inline-image',
                headers: {
                    'X-CSRF-TOKEN': document.querySelector('meta[name="csrf-token"]')?.content || ''
                }
            }
        })
        .then(editor => {
            console.log('✅ CKEditor initialized');
            
            // 초기 데이터 설정
            if (initialContent) {
                editor.setData(initialContent);
            }
            
            // 전역 변수로 저장 (여러 방식으로 접근 가능하도록)
            window[`editor_${elementId}`] = editor;
            window.editorInstance = editor;
            
            // detailed-content ID인 경우 추가 전역 변수 설정
            if (elementId === 'detailed-content') {
                window['editor_detailed-content'] = editor;  // 하이픈 포함 버전
            }
            
            window.RichText = {
                hasPendingUploads: function() {
                    return (window.__ckeditorPendingUploads || 0) > 0;
                },
                getData: function() {
                    if ((window.__ckeditorPendingUploads || 0) > 0) {
                        alert('이미지 업로드가 완료될 때까지 기다려 주세요.');
                        throw new Error('Uploads are still in progress');
                    }
                    return editor.getData();
                }
            };
            
            // 클립보드 이벤트 처리 - 이미지 직접 붙여넣기
            editor.editing.view.document.on('paste', (evt, data) => {
                const dataTransfer = data.dataTransfer;
                const files = Array.from(dataTransfer.files);
                
                files.forEach(file => {
                    if (file.type.startsWith('image/')) {
                        uploadImage(file, editor);
                    }
                });
            });
            
            // 드래그 앤 드롭 처리
            editor.editing.view.document.on('drop', (evt, data) => {
                const dataTransfer = data.dataTransfer;
                const files = Array.from(dataTransfer.files);
                
                files.forEach(file => {
                    if (file.type.startsWith('image/')) {
                        uploadImage(file, editor);
                    }
                });
            });
        })
        .catch(error => {
            console.error('CKEditor initialization failed:', error);
        });
};

// 이미지 업로드 함수
function uploadImage(file, editor) {
    window.__ckeditorPendingUploads = (window.__ckeditorPendingUploads || 0) + 1;
    const formData = new FormData();
    formData.append('upload', file);
    
    fetch('/upload-inline-image', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.url) {
            // 에디터에 이미지 삽입
            const viewFragment = editor.data.processor.toView(`<img src="${data.url}" />`);
            const modelFragment = editor.data.toModel(viewFragment);
            editor.model.insertContent(modelFragment);
        } else {
            console.error('Image upload failed:', data.error);
        }
    })
    .catch(error => {
        console.error('Image upload error:', error);
    })
    .finally(() => {
        window.__ckeditorPendingUploads = Math.max(0, (window.__ckeditorPendingUploads || 1) - 1);
    });
}

// DOM 준비되면 자동 초기화
document.addEventListener('DOMContentLoaded', function() {
    // data-ckeditor="true" 속성이 있는 요소만 찾기 (중복 방지)
    const editorElements = document.querySelectorAll('[data-ckeditor="true"]');
    
    // 이미 초기화된 요소 추적
    const initializedElements = new Set();
    
    editorElements.forEach(element => {
        if (element.id && !initializedElements.has(element.id)) {
            initCKEditor(element.id);
            initializedElements.add(element.id);
        }
    });
});
