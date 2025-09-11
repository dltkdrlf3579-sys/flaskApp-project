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
            
            // 전역 변수로 저장
            window[`editor_${elementId}`] = editor;
            window.editorInstance = editor;
            window.RichText = {
                getData: function() {
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
    });
}

// DOM 준비되면 자동 초기화
document.addEventListener('DOMContentLoaded', function() {
    // data-ckeditor="true" 속성이 있는 요소 찾기
    const editorElements = document.querySelectorAll('[data-ckeditor="true"], #detailed-content');
    
    editorElements.forEach(element => {
        if (element.id) {
            initCKEditor(element.id);
        }
    });
});