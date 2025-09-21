(function (global) {
  'use strict';

  function getEditorContent(elementId) {
    const element = document.getElementById(elementId);
    if (!elementId) {
      return '';
    }

    const altIds = Array.from(new Set([
      elementId,
      elementId.replace(/-/g, '_'),
      elementId.replace(/_/g, '-'),
    ]));

    const candidates = [];

    candidates.push(() =>
      (global.RichText && typeof global.RichText.getData === 'function')
        ? global.RichText.getData()
        : undefined
    );

    candidates.push(() =>
      (global.editorInstance && typeof global.editorInstance.getData === 'function')
        ? global.editorInstance.getData()
        : undefined
    );

    altIds.forEach((id) => {
      candidates.push(() => {
        const instance = global['editor_' + id];
        return instance && typeof instance.getData === 'function' ? instance.getData() : undefined;
      });
      candidates.push(() => {
        const instance = global['editor' + id];
        return instance && typeof instance.getData === 'function' ? instance.getData() : undefined;
      });
      candidates.push(() => {
        const instance = global['editor-' + id];
        return instance && typeof instance.getData === 'function' ? instance.getData() : undefined;
      });
      candidates.push(() => {
        const instance = global[id + '_editor'];
        return instance && typeof instance.getData === 'function' ? instance.getData() : undefined;
      });
      candidates.push(() => {
        const instance = global.CKEDITOR && global.CKEDITOR.instances && global.CKEDITOR.instances[id];
        return instance && typeof instance.getData === 'function' ? instance.getData() : undefined;
      });
    });

    for (const getter of candidates) {
      try {
        const value = getter();
        if (typeof value === 'string') {
          return value;
        }
      } catch (err) {
        console.debug('[board-form] editor getter failed', err);
      }
    }

    if (element) {
      if (element.tagName === 'DIV') {
        return element.innerHTML || '';
      }
      return element.value || '';
    }

    return '';
  }

  function collectDynamicFields(options) {
    const sections = options && Array.isArray(options.sections) ? options.sections : [];
    const includeDisabled = options && options.includeDisabled;
    const skipReadonly = options && options.skipReadonly;
    const data = {};

    sections.forEach(section => {
      const selector = `[data-section="${section.section_key}"]`;
      const inputs = document.querySelectorAll(selector);

      inputs.forEach(input => {
        if (!input) {
          return;
        }
        const fieldKey = input.dataset.field;
        if (!fieldKey) {
          return;
        }
        if (!includeDisabled && (input.disabled || input.getAttribute('disabled'))) {
          return;
        }
        if (skipReadonly && (input.readOnly || input.getAttribute('readonly'))) {
          return;
        }

        let value = '';

        if (input.tagName === 'SELECT') {
          value = input.value;
        } else if (input.type === 'checkbox') {
          value = input.checked ? '1' : '0';
        } else if (input.tagName === 'TEXTAREA') {
          value = input.value;
        } else if (input.classList.contains('value')) {
          return;
        } else if (input.dataset && input.dataset.listValue) {
          value = input.dataset.listValue;
        } else {
          value = input.value;
        }

        const isListField = input.getAttribute('data-field-type') === 'list'
          || (typeof value === 'string' && value.trim().startsWith('[') && value.trim().endsWith(']'));

        if (isListField && value) {
          try {
            const parsed = JSON.parse(value);
            data[fieldKey] = Array.isArray(parsed) ? parsed : value;
          } catch (e) {
            data[fieldKey] = value;
          }
        } else {
          data[fieldKey] = value;
        }
      });
    });

    return data;
  }

  function groupFieldsBySection(dynamicData, sectionColumns) {
    const grouped = {};
    if (!dynamicData || !sectionColumns) {
      return grouped;
    }

    Object.keys(sectionColumns).forEach(sectionKey => {
      const columns = sectionColumns[sectionKey] || [];
      columns.forEach(col => {
        const key = col.column_key;
        if (!key) {
          return;
        }
        if (!grouped[sectionKey]) {
          grouped[sectionKey] = {};
        }
        if (dynamicData[key] !== undefined) {
          grouped[sectionKey][key] = dynamicData[key];
        }
      });
    });

    return grouped;
  }

  function buildBaseFields(dynamicData, fields) {
    if (!dynamicData || !Array.isArray(fields)) {
      return {};
    }
    const baseFields = {};
    fields.forEach(field => {
      if (dynamicData[field] !== undefined) {
        baseFields[field] = dynamicData[field];
      }
    });
    return baseFields;
  }

  function buildAttachmentMeta(options) {
    const selector = options && options.rowSelector ? options.rowSelector : '#attachments-tbody .table-row';
    const rows = document.querySelectorAll(selector);
    const attachments = [];

    rows.forEach(row => {
      if (!row || row.classList.contains('no-data')) {
        return;
      }
      const descEl = row.querySelector('.attachment-desc, .file-desc-input');
      const rawIsNew = String(row.dataset.isNew || '').toLowerCase();
      const id = row.dataset.id || row.dataset.attachmentId;
      attachments.push({
        id: id ? parseInt(id, 10) : null,
        description: descEl ? (descEl.value ?? descEl.textContent ?? '') : '',
        isNew: rawIsNew === 'true' || rawIsNew === '1' || row.classList.contains('new-file-row'),
      });
    });

    return attachments;
  }

  function appendPendingFiles(formData, pendingFiles) {
    if (!formData || !pendingFiles || !Array.isArray(pendingFiles)) {
      return;
    }
    pendingFiles.forEach(file => {
      if (file) {
        formData.append('files', file);
      }
    });
  }

  function appendDeletedAttachments(formData, deletedAttachments) {
    if (!formData || !deletedAttachments) {
      return;
    }
    try {
      formData.append('deleted_attachments', JSON.stringify(deletedAttachments));
    } catch (err) {
      console.warn('[board-form] failed to serialize deleted attachments', err);
      formData.append('deleted_attachments', '[]');
    }
  }

  function appendSectionGroups(formData, groupedSections) {
    if (!formData || !groupedSections) {
      return;
    }
    Object.keys(groupedSections).forEach(sectionKey => {
      try {
        formData.append(sectionKey, JSON.stringify(groupedSections[sectionKey]));
      } catch (err) {
        console.warn(`[board-form] failed to serialize section ${sectionKey}`, err);
      }
    });
  }

  function appendCustomData(formData, customData) {
    if (!formData) {
      return;
    }
    try {
      formData.append('custom_data', JSON.stringify(customData || {}));
    } catch (err) {
      console.warn('[board-form] failed to serialize custom_data', err);
      formData.append('custom_data', '{}');
    }
  }

  const BoardForm = {
    getEditorContent,
    collectDynamicFields,
    groupFieldsBySection,
    buildBaseFields,
    buildAttachmentMeta,
    appendPendingFiles,
    appendDeletedAttachments,
    appendSectionGroups,
    appendCustomData,
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = BoardForm;
  }

  global.BoardForm = BoardForm;
})(typeof window !== 'undefined' ? window : globalThis);
