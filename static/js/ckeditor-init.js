/**
 * CKEditor 5 초기화 스크립트
 * 네이버 블로그 스타일의 강력한 에디터 기능 제공
 */

// CKEditor 5 글로벌 설정
window.CKEditorConfig = {
    instances: new Map(),
    uploadUrl: '/upload-inline-image',
    
    // 기본 에디터 설정
    defaultConfig: {
        language: 'ko',
        toolbar: {
            items: [
                'heading', '|',
                'bold', 'italic', 'underline', 'strikethrough', '|',
                'fontColor', 'fontBackgroundColor', '|',
                'fontSize', 'fontFamily', '|',
                'alignment', '|',
                'bulletedList', 'numberedList', '|',
                'outdent', 'indent', '|',
                'link', 'imageUpload', 'insertTable', '|',
                'blockQuote', 'codeBlock', '|',
                'undo', 'redo', '|',
                'findAndReplace', 'selectAll', '|',
                'sourceEditing'
            ],
            shouldNotGroupWhenFull: true
        },
        
        // 이미지 설정
        image: {
            toolbar: [
                'imageTextAlternative', 'toggleImageCaption', 'imageStyle:inline',
                'imageStyle:block', 'imageStyle:side', '|',
                'linkImage'
            ],
            upload: {
                types: ['jpeg', 'jpg', 'png', 'gif', 'bmp', 'webp', 'svg']
            },
            resizeOptions: [
                {
                    name: 'resizeImage:original',
                    label: '원본',
                    value: null
                },
                {
                    name: 'resizeImage:50',
                    label: '50%',
                    value: '50'
                },
                {
                    name: 'resizeImage:75',
                    label: '75%',
                    value: '75'
                }
            ]
        },
        
        // 표 설정
        table: {
            contentToolbar: [
                'tableColumn', 'tableRow', 'mergeTableCells',
                'tableProperties', 'tableCellProperties'
            ],
            tableProperties: {
                borderColors: customColors,
                backgroundColors: customColors
            },
            tableCellProperties: {
                borderColors: customColors,
                backgroundColors: customColors
            }
        },
        
        // 폰트 설정
        fontSize: {
            options: [
                9, 10, 11, 12, 13, 14, 15, 16, 18, 20, 22, 24, 26, 28, 36, 48, 72
            ]
        },
        
        fontFamily: {
            options: [
                'default',
                '맑은 고딕, Malgun Gothic, sans-serif',
                '굴림, Gulim, sans-serif',
                '돋움, Dotum, sans-serif',
                '바탕, Batang, serif',
                '궁서, Gungsuh, serif',
                'Arial, Helvetica, sans-serif',
                'Comic Sans MS, cursive',
                'Courier New, Courier, monospace',
                'Georgia, serif',
                'Lucida Sans Unicode, Lucida Grande, sans-serif',
                'Tahoma, Geneva, sans-serif',
                'Times New Roman, Times, serif',
                'Trebuchet MS, Helvetica, sans-serif',
                'Verdana, Geneva, sans-serif'
            ]
        },
        
        // 색상 팔레트
        fontColor: {
            colors: customColors
        },
        
        fontBackgroundColor: {
            colors: customColors
        },
        
        // 링크 설정
        link: {
            decorators: {
                toggleDownloadable: {
                    mode: 'manual',
                    label: '다운로드 가능',
                    attributes: {
                        download: 'file'
                    }
                },
                openInNewTab: {
                    mode: 'manual',
                    label: '새 탭에서 열기',
                    defaultValue: true,
                    attributes: {
                        target: '_blank',
                        rel: 'noopener noreferrer'
                    }
                }
            }
        },
        
        // 기본 스타일
        heading: {
            options: [
                { model: 'paragraph', title: '본문', class: 'ck-heading_paragraph' },
                { model: 'heading1', view: 'h1', title: '제목 1', class: 'ck-heading_heading1' },
                { model: 'heading2', view: 'h2', title: '제목 2', class: 'ck-heading_heading2' },
                { model: 'heading3', view: 'h3', title: '제목 3', class: 'ck-heading_heading3' },
                { model: 'heading4', view: 'h4', title: '제목 4', class: 'ck-heading_heading4' },
                { model: 'heading5', view: 'h5', title: '제목 5', class: 'ck-heading_heading5' }
            ]
        },
        
        // HTML 지원
        htmlSupport: {
            allow: [
                {
                    name: /.*/,
                    attributes: true,
                    classes: true,
                    styles: true
                }
            ]
        },
        
        // 자동 저장 (선택사항)
        autosave: {
            save(editor) {
                return saveData(editor.getData());
            },
            waitingTime: 2000 // 2초
        }
    }
};

// 색상 팔레트 정의
const customColors = [
    {
        color: 'hsl(0, 0%, 0%)',
        label: '검정'
    },
    {
        color: 'hsl(0, 0%, 30%)',
        label: '진한 회색'
    },
    {
        color: 'hsl(0, 0%, 60%)',
        label: '회색'
    },
    {
        color: 'hsl(0, 0%, 90%)',
        label: '연한 회색'
    },
    {
        color: 'hsl(0, 0%, 100%)',
        label: '흰색',
        hasBorder: true
    },
    {
        color: 'hsl(0, 75%, 60%)',
        label: '빨강'
    },
    {
        color: 'hsl(30, 75%, 60%)',
        label: '주황'
    },
    {
        color: 'hsl(60, 75%, 60%)',
        label: '노랑'
    },
    {
        color: 'hsl(90, 75%, 60%)',
        label: '연두'
    },
    {
        color: 'hsl(120, 75%, 60%)',
        label: '초록'
    },
    {
        color: 'hsl(150, 75%, 60%)',
        label: '청록'
    },
    {
        color: 'hsl(180, 75%, 60%)',
        label: '시안'
    },
    {
        color: 'hsl(210, 75%, 60%)',
        label: '파랑'
    },
    {
        color: 'hsl(240, 75%, 60%)',
        label: '남색'
    },
    {
        color: 'hsl(270, 75%, 60%)',
        label: '보라'
    }
];

// Custom Upload Adapter
class CustomUploadAdapter {
    constructor(loader) {
        this.loader = loader;
        this.uploadUrl = window.CKEditorConfig.uploadUrl;
    }
    
    upload() {
        return this.loader.file
            .then(file => new Promise((resolve, reject) => {
                this._initRequest();
                this._initListeners(resolve, reject, file);
                this._sendRequest(file);
            }));
    }
    
    abort() {
        if (this.xhr) {
            this.xhr.abort();
        }
    }
    
    _initRequest() {
        const xhr = this.xhr = new XMLHttpRequest();
        xhr.open('POST', this.uploadUrl, true);
        xhr.responseType = 'json';
    }
    
    _initListeners(resolve, reject, file) {
        const xhr = this.xhr;
        const loader = this.loader;
        const genericErrorText = `${file.name} 업로드 실패`;
        
        xhr.addEventListener('error', () => reject(genericErrorText));
        xhr.addEventListener('abort', () => reject());
        xhr.addEventListener('load', () => {
            const response = xhr.response;
            
            if (!response || response.error) {
                return reject(response && response.error ? response.error.message : genericErrorText);
            }
            
            resolve({
                default: response.url
            });
        });
        
        if (xhr.upload) {
            xhr.upload.addEventListener('progress', evt => {
                if (evt.lengthComputable) {
                    loader.uploadTotal = evt.total;
                    loader.uploaded = evt.loaded;
                }
            });
        }
    }
    
    _sendRequest(file) {
        const data = new FormData();
        data.append('upload', file);
        this.xhr.send(data);
    }
}

// Upload Adapter 플러그인
function CustomUploadAdapterPlugin(editor) {
    editor.plugins.get('FileRepository').createUploadAdapter = (loader) => {
        return new CustomUploadAdapter(loader);
    };
}

// CKEditor 초기화 함수
window.initCKEditor = function(elementId, customConfig = {}) {
    const element = document.querySelector(`#${elementId}`);
    if (!element) {
        console.error(`Element with ID '${elementId}' not found`);
        return Promise.reject(new Error(`Element not found: ${elementId}`));
    }
    
    // 기존 인스턴스가 있으면 제거
    if (window.CKEditorConfig.instances.has(elementId)) {
        const oldInstance = window.CKEditorConfig.instances.get(elementId);
        oldInstance.destroy();
        window.CKEditorConfig.instances.delete(elementId);
    }
    
    // 설정 병합
    const config = {
        ...window.CKEditorConfig.defaultConfig,
        ...customConfig,
        extraPlugins: [CustomUploadAdapterPlugin]
    };
    
    // 초기 데이터 처리
    let initialData = '';
    if (element.tagName === 'TEXTAREA') {
        initialData = element.value || '';
    } else {
        // data-content 속성 확인
        const dataContent = element.getAttribute('data-content');
        if (dataContent) {
            try {
                initialData = JSON.parse(dataContent);
            } catch (e) {
                initialData = dataContent;
            }
        } else {
            initialData = element.innerHTML || '';
        }
    }
    
    // CKEditor 생성
    return ClassicEditor
        .create(element, config)
        .then(editor => {
            // 인스턴스 저장
            window.CKEditorConfig.instances.set(elementId, editor);
            
            // 초기 데이터 설정
            if (initialData) {
                editor.setData(initialData);
            }
            
            // 클립보드 이벤트 처리 (이미지, 엑셀 표 등)
            editor.editing.view.document.on('clipboardInput', (evt, data) => {
                const dataTransfer = data.dataTransfer;
                
                // 엑셀/워드 표 처리
                const htmlData = dataTransfer.getData('text/html');
                if (htmlData && htmlData.includes('</table>')) {
                    // 표 스타일 개선
                    const improvedHtml = improveTableStyles(htmlData);
                    data.content = editor.data.processor.toView(improvedHtml);
                }
                
                // 이미지 처리는 CKEditor가 자동으로 처리 (CustomUploadAdapter 사용)
            });
            
            // 에디터 높이 조정
            editor.editing.view.change(writer => {
                writer.setStyle('min-height', '400px', editor.editing.view.document.getRoot());
            });
            
            // 전역 객체에 노출
            window[`editor_${elementId}`] = editor;
            
            console.log(`✅ CKEditor initialized for #${elementId}`);
            return editor;
        })
        .catch(error => {
            console.error('CKEditor initialization failed:', error);
            throw error;
        });
};

// 표 스타일 개선 함수
function improveTableStyles(html) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');
    
    // 모든 표에 스타일 적용
    doc.querySelectorAll('table').forEach(table => {
        if (!table.style.borderCollapse) table.style.borderCollapse = 'collapse';
        if (!table.style.width) table.style.width = '100%';
        if (!table.style.margin) table.style.margin = '15px 0';
        table.style.border = table.style.border || '1px solid #ddd';
    });
    
    // 모든 셀에 스타일 적용
    doc.querySelectorAll('th, td').forEach(cell => {
        cell.style.border = cell.style.border || '1px solid #ddd';
        cell.style.padding = cell.style.padding || '8px';
        cell.style.textAlign = cell.style.textAlign || 'left';
    });
    
    // 헤더 셀 스타일
    doc.querySelectorAll('th').forEach(th => {
        if (!th.style.backgroundColor) th.style.backgroundColor = '#f8f9fa';
        if (!th.style.fontWeight) th.style.fontWeight = 'bold';
    });
    
    // 짝수 행 배경색
    doc.querySelectorAll('tr:nth-child(even)').forEach(row => {
        if (!row.style.backgroundColor) row.style.backgroundColor = '#f8f9fa';
    });
    
    return doc.body.innerHTML;
}

// 데이터 저장 함수 (자동 저장용)
function saveData(data) {
    // 로컬 스토리지에 임시 저장
    const key = `ckeditor_autosave_${window.location.pathname}`;
    localStorage.setItem(key, JSON.stringify({
        data: data,
        timestamp: new Date().toISOString()
    }));
    return Promise.resolve();
}

// 자동 복구 함수
window.restoreAutoSave = function(elementId) {
    const key = `ckeditor_autosave_${window.location.pathname}`;
    const saved = localStorage.getItem(key);
    
    if (saved) {
        try {
            const { data, timestamp } = JSON.parse(saved);
            const age = Date.now() - new Date(timestamp).getTime();
            
            // 24시간 이내의 데이터만 복구
            if (age < 24 * 60 * 60 * 1000) {
                const editor = window.CKEditorConfig.instances.get(elementId);
                if (editor) {
                    editor.setData(data);
                    console.log('✅ 자동 저장된 데이터 복구됨');
                    return true;
                }
            }
        } catch (e) {
            console.error('자동 저장 복구 실패:', e);
        }
    }
    return false;
};

// 전역 유틸리티 함수들
window.CKEditorUtils = {
    // 에디터 데이터 가져오기
    getData: function(elementId) {
        const editor = window.CKEditorConfig.instances.get(elementId);
        return editor ? editor.getData() : '';
    },
    
    // 에디터 데이터 설정
    setData: function(elementId, data) {
        const editor = window.CKEditorConfig.instances.get(elementId);
        if (editor) {
            editor.setData(data);
        }
    },
    
    // 에디터 초기화 상태 확인
    isReady: function(elementId) {
        return window.CKEditorConfig.instances.has(elementId);
    },
    
    // 모든 에디터 인스턴스 제거
    destroyAll: function() {
        window.CKEditorConfig.instances.forEach((editor, id) => {
            editor.destroy();
        });
        window.CKEditorConfig.instances.clear();
    }
};

// DOM 준비 시 자동 초기화
document.addEventListener('DOMContentLoaded', function() {
    // CKEditor 자동 초기화 대상 찾기
    const autoInitElements = document.querySelectorAll('[data-ckeditor="true"], .ckeditor-auto');
    
    autoInitElements.forEach(element => {
        const elementId = element.id || `ckeditor_${Date.now()}`;
        if (!element.id) element.id = elementId;
        
        initCKEditor(elementId)
            .then(editor => {
                // 자동 저장 데이터 복구 시도
                restoreAutoSave(elementId);
            })
            .catch(error => {
                console.error(`Failed to initialize CKEditor for ${elementId}:`, error);
            });
    });
});