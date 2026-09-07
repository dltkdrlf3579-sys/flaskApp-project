(() => {
    function openPopup(url, name) {
        const width = Math.min(1400, window.screen.availWidth);
        const height = Math.min(900, window.screen.availHeight);
        const left = Math.max(0, (window.screen.availWidth - width) / 2);
        const top = Math.max(0, (window.screen.availHeight - height) / 2);
        const popup = window.open(url, name, `width=${width},height=${height},left=${left},top=${top},scrollbars=yes,resizable=yes`);
        if (popup) popup.focus();
        else window.location.assign(url);
    }

    const listing = document.querySelector('.training-list');
    if (listing) {
        window.showRegisterModal = () => openPopup(listing.dataset.registerUrl, 'aiTrainingRegister');
        listing.querySelectorAll('[data-training-popup]').forEach(link => {
            link.addEventListener('click', event => {
                event.preventDefault();
                openPopup(link.href, 'aiTrainingDetail');
            });
        });
    }

    const form = document.getElementById('training-form');
    if (!form) return;
    const errorBox = document.getElementById('training-error');
    const fileInput = document.getElementById('training-files');
    const fileBody = document.getElementById('training-file-body');
    const pending = new Map();
    let counter = 0;
    let saving = false;

    function showError(message) {
        errorBox.textContent = message;
        errorBox.hidden = false;
        errorBox.scrollIntoView({block: 'nearest'});
    }

    function updateCount() {
        const count = fileBody.rows.length;
        document.getElementById('training-file-count').textContent = count;
        document.getElementById('training-empty').hidden = count > 0;
    }

    function finish() {
        if (window.opener && !window.opener.closed) {
            window.opener.location.reload();
            window.close();
        } else {
            window.location.assign(form.dataset.listUrl);
        }
    }

    document.getElementById('training-close').addEventListener('click', () => {
        if (saving) return;
        if (window.opener && !window.opener.closed) window.close();
        else window.location.assign(form.dataset.listUrl);
    });

    if (!fileInput) return;
    document.getElementById('training-add').addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', () => {
        errorBox.hidden = true;
        const extensions = new Set(form.dataset.extensions.split(','));
        for (const file of fileInput.files) {
            if (file.size > Number(form.dataset.maxMb) * 1024 * 1024) {
                showError(`파일당 ${form.dataset.maxMb}MB를 초과했습니다: ${file.name}`);
                continue;
            }
            if (!extensions.has(file.name.split('.').pop().toLowerCase())) {
                showError(`허용되지 않은 파일 형식입니다: ${file.name}`);
                continue;
            }
            if ([...pending.values()].some(existing => existing.name === file.name && existing.size === file.size && existing.lastModified === file.lastModified)) continue;
            counter += 1;
            const key = String(counter);
            pending.set(key, file);
            const row = fileBody.insertRow();
            row.dataset.pendingKey = key;
            row.insertCell().textContent = file.name;
            row.insertCell().textContent = `${(file.size / 1024 / 1024).toFixed(2)} MB`;
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'btn btn-outline-danger btn-sm training-remove';
            button.textContent = '삭제';
            row.insertCell().append(button);
        }
        fileInput.value = '';
        updateCount();
    });

    fileBody.addEventListener('click', event => {
        const button = event.target.closest('.training-remove');
        if (!button || saving) return;
        const row = button.closest('tr');
        if (row.dataset.pendingKey) pending.delete(row.dataset.pendingKey);
        row.remove();
        updateCount();
    });

    form.addEventListener('submit', async event => {
        event.preventDefault();
        if (saving) return;
        if (!fileBody.rows.length) {
            showError('첨부파일을 1개 이상 추가해 주세요.');
            return;
        }
        const data = new FormData(form);
        data.set('keep_file_ids', JSON.stringify([...fileBody.querySelectorAll('[data-file-id]')].map(row => Number(row.dataset.fileId))));
        pending.forEach(file => data.append('files', file));
        saving = true;
        errorBox.hidden = true;
        const saveButton = document.getElementById('training-save');
        const label = saveButton.textContent;
        saveButton.textContent = '저장 중...';
        form.querySelectorAll('button, input').forEach(element => { element.disabled = true; });
        try {
            const response = await fetch(form.action, {method: 'POST', body: data});
            const result = await response.json().catch(() => ({message: `서버 응답 오류 (${response.status})`}));
            if (!response.ok || !result.success) throw new Error(result.message || result.error || '저장에 실패했습니다.');
            if (result.warning) window.alert(result.warning);
            finish();
        } catch (error) {
            showError(error.message);
        } finally {
            saving = false;
            saveButton.textContent = label;
            form.querySelectorAll('button, input').forEach(element => { element.disabled = false; });
        }
    });
})();
