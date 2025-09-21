(function (global) {
  'use strict';

  if (!global.BoardForm) {
    console.warn('[board-detail] BoardForm helpers are required but missing.');
  }

  const BoardDetail = {
    toggleSection(sectionId, toggleButton) {
      if (!sectionId) {
        return;
      }
      const content = document.getElementById(`${sectionId}-content`);
      if (!content) {
        return;
      }
      const icon = toggleButton || (global.event && global.event.target);
      const isHidden = content.style.display === 'none';
      content.style.display = isHidden ? 'block' : 'none';
      if (icon && icon.querySelector) {
        const iconSpan = icon.querySelector('.collapse-icon');
        if (iconSpan) {
          iconSpan.textContent = isHidden ? '▲' : '▼';
        }
      } else if (icon && icon.nodeType === 1) {
        icon.textContent = isHidden ? '▲' : '▼';
      }
    },

    createUpdater(config) {
      const {
        endpoint,
        idField,
        idValue,
        sections,
        sectionColumns,
        attachmentsSelector = '#attachments-tbody .table-row',
        popupReload = false,
        reloadCurrent = true,
        redirectUrl = null,
        successMessage = '저장되었습니다.',
        failurePrefix = '저장 실패',
        includeDeletedAttachments = false,
        onSuccess,
        onError,
      } = config || {};

      if (!endpoint) {
        throw new Error('[board-detail] endpoint is required to build an updater.');
      }

      return function submitBoardForm() {
        const formData = new FormData();

        if (idField && typeof idValue !== 'undefined' && idValue !== null && idValue !== '') {
          formData.append(idField, idValue);
        }

        if (global.BoardForm && typeof global.BoardForm.getEditorContent === 'function') {
          const detailedContent = global.BoardForm.getEditorContent('detailed-content');
          formData.append('detailed_content', detailedContent);
        }

        if (global.BoardForm && typeof global.BoardForm.collectDynamicFields === 'function') {
          const dynamicData = global.BoardForm.collectDynamicFields({ sections: sections || [] });
          const grouped = global.BoardForm.groupFieldsBySection(dynamicData, sectionColumns || {});
          global.BoardForm.appendSectionGroups(formData, grouped);
          global.BoardForm.appendCustomData(formData, dynamicData);
        }

        if (global.BoardForm && typeof global.BoardForm.appendPendingFiles === 'function') {
          const pending = global.pendingFiles && Array.isArray(global.pendingFiles) ? global.pendingFiles : [];
          global.BoardForm.appendPendingFiles(formData, pending);
        }

        if (includeDeletedAttachments && global.BoardForm && typeof global.BoardForm.appendDeletedAttachments === 'function') {
          const deleted = global.deletedAttachments && Array.isArray(global.deletedAttachments) ? global.deletedAttachments : [];
          global.BoardForm.appendDeletedAttachments(formData, deleted);
        }

        if (global.BoardForm && typeof global.BoardForm.buildAttachmentMeta === 'function') {
          const attachmentMeta = global.BoardForm.buildAttachmentMeta({ rowSelector: attachmentsSelector });
          formData.append('attachment_data', JSON.stringify(attachmentMeta));
        }

        fetch(endpoint, {
          method: 'POST',
          body: formData,
        })
          .then((response) => {
            const contentType = response.headers.get('content-type') || '';
            if (contentType.includes('application/json')) {
              return response.json();
            }
            return response.text().then((text) => ({ success: response.ok, message: text || response.statusText }));
          })
          .then((data) => {
            const isSuccess = data && (data.success === true || typeof data.success === 'undefined');
            if (isSuccess) {
              if (successMessage) {
                alert(successMessage);
              }
              if (typeof onSuccess === 'function') {
                onSuccess(data);
                return;
              }
              if (popupReload && global.opener && !global.opener.closed) {
                try {
                  global.opener.location.reload();
                } catch (err) {
                  console.warn('[board-detail] failed to reload opener window:', err);
                }
              }
              if (reloadCurrent) {
                const url = new URL(global.location.href);
                url.searchParams.set('t', Date.now());
                global.location.href = url.toString();
              } else if (redirectUrl) {
                global.location.href = redirectUrl;
              }
            } else {
              const message = (data && (data.message || data.error || data.detail)) || '알 수 없는 오류';
              alert(`${failurePrefix}: ${message}`);
              if (typeof onError === 'function') {
                onError(data);
              }
            }
          })
          .catch((error) => {
            console.error('[board-detail] update failed:', error);
            alert(`${failurePrefix}: ${error && error.message ? error.message : error}`);
            if (typeof onError === 'function') {
              onError(error);
            }
          });
      };
    },
  };

  BoardDetail.verifyPassword = function ({ boardType, password }) {
    if (!password) {
      return Promise.reject(new Error('비밀번호를 입력해주세요.'));
    }
    const payload = {
      password,
      board_type: boardType || 'default',
    };
    return fetch('/verify-password', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    })
      .then((response) => response.json().catch(() => ({ success: false, message: response.statusText || 'Unknown error' })))
      .then((data) => {
        if (data && data.success) {
          return data;
        }
        const message = (data && (data.message || data.error || data.detail)) || '비밀번호가 올바르지 않습니다.';
        throw new Error(message);
      });
  };

  global.BoardDetail = BoardDetail;
})(window);
