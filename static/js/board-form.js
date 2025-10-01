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

        if (input.dataset.fieldType === 'dropdown_multi_hidden') {
          const raw = input.value || '';
          if (!raw) {
            data[fieldKey] = [];
            return;
          }
          try {
            const parsed = JSON.parse(raw);
            data[fieldKey] = Array.isArray(parsed) ? parsed : [];
          } catch (e) {
            data[fieldKey] = [];
          }
          return;
        }

        let value = '';

        if (input.tagName === 'SELECT' && input.multiple) {
          const selected = Array.from(input.selectedOptions || [])
            .map(opt => (opt && typeof opt.value !== 'undefined' ? String(opt.value) : ''))
            .filter(val => val !== '');
          data[fieldKey] = selected;
          return;
        }

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

  const DROPDOWN_MULTI_STYLE_ID = 'dropdownMultiStyles';

  function ensureDropdownStyles() {
    if (document.getElementById(DROPDOWN_MULTI_STYLE_ID)) {
      return;
    }
    const style = document.createElement('style');
    style.id = DROPDOWN_MULTI_STYLE_ID;
    style.textContent = `
      .dropdown-multi-checkboxes {
        border: 1px solid #ced4da;
        border-radius: 6px;
        padding: 8px 10px;
        max-height: 136px;
        overflow-y: auto;
        background-color: #fff;
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }
      .dropdown-multi-option {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 6px 10px;
        border: 1px solid #e9ecef;
        border-radius: 6px;
        background-color: #f8f9fa;
        flex: 0 0 calc(25% - 6px);
        box-sizing: border-box;
        padding-left: 0 !important;
        margin: 0 !important;
      }
      .dropdown-multi-option .form-check-label {
        flex: 1 1 auto;
        margin: 0;
      }
      .dropdown-multi-option .form-check-input {
        margin-top: 0;
        margin-left: 0 !important;
        margin-right: 0.5rem;
        background-repeat: no-repeat !important;
        background-position: center center !important;
        background-size: 12px 12px !important;
        width: 14px !important;
        height: 14px !important;
        min-width: 0 !important;
        min-height: 0 !important;
        padding: 0 !important;
        display: inline-block !important;
        flex: 0 0 auto !important;
        box-sizing: content-box !important;
      }
    `;
    document.head.appendChild(style);
  }

  function parseDropdownHiddenValue(hiddenEl) {
    if (!hiddenEl || !hiddenEl.value) {
      return [];
    }
    try {
      const parsed = JSON.parse(hiddenEl.value);
      return Array.isArray(parsed) ? parsed : [];
    } catch (err) {
      return [];
    }
  }

  function updateDropdownHidden(hiddenEl, codes) {
    if (!hiddenEl) {
      return;
    }
    if (!codes || !codes.length) {
      hiddenEl.value = '';
      return;
    }
    try {
      hiddenEl.value = JSON.stringify(codes);
    } catch (err) {
      hiddenEl.value = '';
    }
  }

  function updateDropdownSummary(summaryEl, labels) {
    if (!summaryEl) {
      return;
    }
    if (!labels || !labels.length) {
      summaryEl.textContent = '-';
      summaryEl.classList.add('text-muted');
      summaryEl.dataset.hasSelection = '0';
    } else {
      summaryEl.textContent = labels.join(', ');
      summaryEl.classList.remove('text-muted');
      summaryEl.dataset.hasSelection = '1';
    }
  }

  function initDropdownGroup(group) {
    if (!group || group.dataset.multiInit === '1') {
      return;
    }

    const container = group.closest('.info-cell') || document;
    const fieldKey = group.dataset.checkboxFor || group.dataset.multiKey;
    ensureDropdownStyles();

    const hidden = container.querySelector(`.dropdown-multi-hidden-value[data-field="${fieldKey}"]`);
    let summary = container.querySelector(`.dropdown-multi-summary[data-summary-for="${fieldKey}"]`);
    if (!summary) {
      summary = document.createElement('div');
      summary.className = 'dropdown-multi-summary text-muted mb-1';
      summary.dataset.summaryFor = fieldKey || '';
      summary.textContent = '-';
      group.parentElement.insertBefore(summary, group);
    }

    const checkboxes = Array.from(group.querySelectorAll('input[type="checkbox"]'));
    const initialCodes = parseDropdownHiddenValue(hidden);
    const selectedCodes = [];
    const selectedLabels = [];

    checkboxes.forEach(cb => {
      const labelText = cb.nextElementSibling ? cb.nextElementSibling.textContent.trim() : '';
      if (initialCodes.length) {
        cb.checked = initialCodes.includes(cb.value);
      }
      if (cb.checked) {
        selectedCodes.push(cb.value);
        if (labelText) {
          selectedLabels.push(labelText);
        }
      }
    });

    if (!initialCodes.length && selectedCodes.length) {
      updateDropdownHidden(hidden, selectedCodes);
    }
    updateDropdownSummary(summary, selectedLabels);

    checkboxes.forEach(cb => {
      cb.addEventListener('change', () => {
        const codes = [];
        const labels = [];
        checkboxes.forEach(box => {
          if (box.checked) {
            codes.push(box.value);
            const text = box.nextElementSibling ? box.nextElementSibling.textContent.trim() : '';
            if (text) {
              labels.push(text);
            }
          }
        });
        updateDropdownHidden(hidden, codes);
        updateDropdownSummary(summary, labels);
      });
    });

    group.dataset.multiInit = '1';
  }

  function initDropdownMultiGroups(root) {
    const scope = root || document;
    const groups = scope.querySelectorAll('.dropdown-multi-checkboxes');
    groups.forEach(initDropdownGroup);
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
    initDropdownMultiGroups,
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = BoardForm;
  }

  global.BoardForm = BoardForm;

  if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', () => {
      try {
        initDropdownMultiGroups();
      } catch (err) {
        console.warn('[board-form] failed to initialize dropdown multi groups', err);
      }
    });
  }
})(typeof window !== 'undefined' ? window : globalThis);
