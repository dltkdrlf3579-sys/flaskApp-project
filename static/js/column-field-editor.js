(function (window) {
    const defaults = {
        showSection: true,
        showSpan: true,
        showTable: true,
        showListButton: true,
        showNumber: true,
        showScoring: true,
        showActive: true
    };

    let config = { ...defaults };
    let elements = {};

    function memoizeElements() {
        elements = {
            form: document.getElementById('columnForm'),
            columnId: document.getElementById('columnId'),
            columnName: document.getElementById('columnName'),
            columnKey: document.getElementById('columnKey'),
            columnSection: document.getElementById('columnSection'),
            sectionField: document.getElementById('sectionField'),
            typeSelect: document.getElementById('columnType'),
            typeChangeWarning: document.getElementById('typeChangeWarning'),
            spanField: document.getElementById('spanField'),
            optionsField: document.getElementById('optionsField'),
            dropdownOptions: document.getElementById('dropdownOptions'),
            optionPreview: document.getElementById('optionPreview'),
            dropdownMultiToggle: document.getElementById('dropdownMultiToggle'),
            dropdownMultiWrapper: document.getElementById('dropdownMultiToggleWrapper'),
            dropdownMultiHint: document.getElementById('dropdownMultiHint'),
            listConfigField: document.getElementById('listConfigField'),
            listBuilderButton: document.getElementById('openListBuilderBtn'),
            listBuilderHint: document.getElementById('listBuilderHint'),
            numberConfigField: document.getElementById('numberConfigField'),
            numberTypeInteger: document.getElementById('numberTypeInteger'),
            numberTypeFloat: document.getElementById('numberTypeFloat'),
            scoringConfigField: document.getElementById('scoringConfigField'),
            scoringConfig: document.getElementById('scoringConfig'),
            scoringPreviewLabel: document.getElementById('scoringPreviewLabel'),
            tableConfigField: document.getElementById('tableConfigField'),
            tableSelectField: document.getElementById('tableSelectField'),
            tableSelect: document.getElementById('tableSelect'),
            selectedTableDisplay: document.getElementById('selectedTableDisplay'),
            selectedTableConfig: document.getElementById('selectedTableConfig'),
            tableColumnsPreview: document.getElementById('tableColumnsPreview'),
            isActive: document.getElementById('isActive'),
            isActiveWrapper: document.getElementById('isActiveWrapper')
        };
    }

    function ensureElements() {
        if (!elements.form) {
            memoizeElements();
        }
    }

    function display(element, show) {
        if (!element) return;
        element.style.display = show ? '' : 'none';
    }

    function applyContextVisibility() {
        ensureElements();

        if (elements.sectionField) {
            display(elements.sectionField, config.showSection);
            if (elements.columnSection) {
                if (config.showSection) {
                    elements.columnSection.setAttribute('required', 'required');
                } else {
                    elements.columnSection.removeAttribute('required');
                }
            }
        }

        if (elements.spanField) {
            if (!config.showSpan) {
                display(elements.spanField, false);
            }
        }

        if (elements.listConfigField) {
            display(elements.listConfigField, config.showListButton);
            if (!config.showListButton && elements.listBuilderButton) {
                elements.listBuilderButton.disabled = true;
            }
        }

        if (elements.numberConfigField) {
            display(elements.numberConfigField, config.showNumber);
        }

        if (elements.scoringConfigField) {
            display(elements.scoringConfigField, config.showScoring);
        }

        if (elements.tableConfigField) {
            display(elements.tableConfigField, config.showTable);
        }
        if (elements.tableSelectField) {
            display(elements.tableSelectField, false);
        }

        if (elements.isActiveWrapper) {
            display(elements.isActiveWrapper, config.showActive);
        }
    }

    function getType() {
        ensureElements();
        return elements.typeSelect ? elements.typeSelect.value : '';
    }

    function toggleOptionsField() {
        ensureElements();
        const type = getType();
        const isDropdown = type === 'dropdown';
        display(elements.optionsField, isDropdown);
        if (elements.dropdownMultiWrapper) {
            display(elements.dropdownMultiWrapper, isDropdown);
        }
        if (elements.dropdownMultiHint) {
            display(elements.dropdownMultiHint, isDropdown && isDropdownMultiSelected());
        }
    }

    function toggleTableField() {
        ensureElements();
        if (!config.showTable) {
            display(elements.tableConfigField, false);
            return;
        }
        const type = getType();
        display(elements.tableConfigField, type === 'table');
    }

    function toggleSpanField() {
        ensureElements();
        if (!config.showSpan || !elements.spanField) {
            return;
        }
        const type = getType();
        const isMulti = (type === 'dropdown') && isDropdownMultiSelected();
        const shouldShow = (type === 'text') || (type === 'dropdown' && !isMulti);
        display(elements.spanField, shouldShow);
    }

    function toggleListField() {
        ensureElements();
        if (!config.showListButton) {
            display(elements.listConfigField, false);
            return;
        }
        const type = getType();
        display(elements.listConfigField, type === 'list');
        if (typeof window.updateListBuilderButtonState === 'function') {
            window.updateListBuilderButtonState();
        }
    }

    function toggleNumberField() {
        ensureElements();
        if (!config.showNumber || !elements.numberConfigField) {
            return;
        }
        const type = getType();
        display(elements.numberConfigField, type === 'number');
    }

    function toggleScoringField() {
        ensureElements();
        if (!config.showScoring || !elements.scoringConfigField) {
            return;
        }
        const type = getType();
        if (type === 'scoring' || type === 'score_total') {
            display(elements.scoringConfigField, true);
            if (elements.scoringPreviewLabel) {
                elements.scoringPreviewLabel.textContent = '설정되지 않음';
            }
            if (typeof window.updateScoringPreview === 'function') {
                window.updateScoringPreview();
            }
        } else {
            display(elements.scoringConfigField, false);
        }
    }

    function isDropdownMultiSelected() {
        ensureElements();
        return !!(elements.dropdownMultiToggle && elements.dropdownMultiToggle.checked);
    }

    function handleDropdownMultiToggleChange() {
        ensureElements();
        const type = getType();
        const isMulti = isDropdownMultiSelected();
        if (typeof window.setSpan === 'function') {
            if (isMulti) {
                window.setSpan(8, { remember: true });
            } else if (type === 'dropdown') {
                window.setSpan(2, { remember: true });
            }
        }
        if (elements.dropdownMultiHint) {
            display(elements.dropdownMultiHint, isMulti);
        }
        toggleSpanField();
    }

    function checkTypeChange() {
        ensureElements();
        const typeSelect = elements.typeSelect;
        if (!typeSelect) {
            return;
        }
        const currentType = typeSelect.value;
        if (currentType === 'dropdown') {
            if (isDropdownMultiSelected()) {
                if (typeof window.setSpan === 'function') {
                    window.setSpan(8, { remember: true });
                }
            } else if (typeof window.setSpan === 'function') {
                window.setSpan(2, { remember: true });
            }
        }

        const originalType = typeSelect.dataset.originalType;
        if (!elements.typeChangeWarning) {
            return;
        }
        if (window.editingId && originalType && originalType !== currentType) {
            display(elements.typeChangeWarning, true);
        } else {
            display(elements.typeChangeWarning, false);
        }
    }

    function handleTypeChange() {
        toggleOptionsField();
        toggleTableField();
        toggleSpanField();
        toggleListField();
        toggleNumberField();
        toggleScoringField();
        checkTypeChange();
    }

    function resetForm() {
        ensureElements();
        if (elements.form) {
            elements.form.reset();
        }
        if (elements.dropdownOptions) {
            elements.dropdownOptions.value = '[]';
        }
        if (elements.selectedTableConfig) {
            elements.selectedTableConfig.value = '';
        }
        if (elements.selectedTableDisplay) {
            elements.selectedTableDisplay.value = '';
        }
        if (elements.tableColumnsPreview) {
            elements.tableColumnsPreview.innerHTML = '';
            display(elements.tableColumnsPreview, false);
        }
        if (elements.numberTypeInteger) {
            elements.numberTypeInteger.checked = true;
        }
        if (elements.numberTypeFloat) {
            elements.numberTypeFloat.checked = false;
        }
        if (elements.scoringConfig) {
            elements.scoringConfig.value = '';
        }
        if (elements.scoringPreviewLabel) {
            elements.scoringPreviewLabel.textContent = '설정되지 않음';
        }
        if (elements.dropdownMultiToggle) {
            elements.dropdownMultiToggle.checked = false;
        }
        handleTypeChange();
    }

    function fillForm(data = {}) {
        ensureElements();
        if (elements.columnId) {
            elements.columnId.value = data.id != null ? data.id : '';
        }
        if (elements.columnName) {
            elements.columnName.value = data.column_name || data.label || '';
        }
        if (elements.columnKey) {
            elements.columnKey.value = data.column_key || data.key || '';
        }
        if (elements.typeSelect) {
            elements.typeSelect.value = data.column_type || data.type || '';
            elements.typeSelect.dataset.originalType = data.original_type || data.column_type || data.type || '';
        }
        if (elements.dropdownOptions) {
            if (Array.isArray(data.dropdown_options)) {
                elements.dropdownOptions.value = JSON.stringify(data.dropdown_options);
            } else if (typeof data.dropdown_options === 'string') {
                elements.dropdownOptions.value = data.dropdown_options;
            } else {
                elements.dropdownOptions.value = '[]';
            }
        }
        if (elements.dropdownMultiToggle) {
            elements.dropdownMultiToggle.checked = !!data.dropdown_multi;
        }
        if (elements.columnSection && data.tab) {
            elements.columnSection.value = data.tab;
        }
        if (elements.isActive && data.is_active != null) {
            elements.isActive.checked = !!data.is_active;
        }
        if (elements.selectedTableDisplay) {
            elements.selectedTableDisplay.value = data.table_display || '';
        }
        if (elements.selectedTableConfig) {
            elements.selectedTableConfig.value = data.table_config || '';
        }
        if (elements.tableColumnsPreview) {
            if (data.table_preview) {
                elements.tableColumnsPreview.innerHTML = data.table_preview;
                display(elements.tableColumnsPreview, true);
            } else {
                elements.tableColumnsPreview.innerHTML = '';
                display(elements.tableColumnsPreview, false);
            }
        }
        const numberType = data.number_type || (data.metadata && data.metadata.numberType) || 'integer';
        if (elements.numberTypeInteger && elements.numberTypeFloat) {
            if (numberType === 'float') {
                elements.numberTypeFloat.checked = true;
                elements.numberTypeInteger.checked = false;
            } else {
                elements.numberTypeInteger.checked = true;
                elements.numberTypeFloat.checked = false;
            }
        }
        if (elements.scoringConfig) {
            elements.scoringConfig.value = data.scoring_config || '';
        }
        if (elements.scoringPreviewLabel && data.scoring_preview) {
            elements.scoringPreviewLabel.textContent = data.scoring_preview;
        }
        handleTypeChange();
    }

    function collectFormData(options = {}) {
        ensureElements();
        const data = {};
        if (elements.columnId && elements.columnId.value) {
            data.id = elements.columnId.value;
        }
        if (elements.columnName) {
            data.column_name = elements.columnName.value.trim();
        }
        if (elements.columnKey) {
            data.column_key = elements.columnKey.value.trim();
        }
        data.column_type = getType();
        if (elements.columnSection) {
            data.tab = elements.columnSection.value;
        }
        if (elements.isActive) {
            data.is_active = elements.isActive.checked;
        }
        if (elements.dropdownOptions) {
            const raw = elements.dropdownOptions.value || '[]';
            try {
                const parsed = JSON.parse(raw);
                if (Array.isArray(parsed)) {
                    data.dropdown_options = parsed;
                }
            } catch (err) {
                data.dropdown_options = [];
            }
        }
        if (elements.dropdownMultiToggle) {
            data.dropdown_multi = !!elements.dropdownMultiToggle.checked;
        }
        if (elements.selectedTableConfig) {
            data.table_config = elements.selectedTableConfig.value.trim();
        }
        if (elements.selectedTableDisplay) {
            data.table_display = elements.selectedTableDisplay.value.trim();
        }
        if (elements.numberTypeInteger && elements.numberTypeFloat) {
            data.number_type = elements.numberTypeFloat.checked ? 'float' : 'integer';
        }
        if (elements.scoringConfig) {
            data.scoring_config = elements.scoringConfig.value;
        }
        return data;
    }

    function init(options = {}) {
        config = { ...defaults, ...options };
        memoizeElements();
        applyContextVisibility();
        if (elements.typeSelect && !elements.typeSelect.dataset.columnFieldEditorBound) {
            elements.typeSelect.addEventListener('change', handleTypeChange);
            elements.typeSelect.dataset.columnFieldEditorBound = '1';
        }
        if (elements.dropdownMultiToggle && !elements.dropdownMultiToggle.dataset.columnFieldEditorBound) {
            elements.dropdownMultiToggle.addEventListener('change', handleDropdownMultiToggleChange);
            elements.dropdownMultiToggle.dataset.columnFieldEditorBound = '1';
        }
        handleTypeChange();
    }

    const ColumnFieldEditor = {
        init,
        setConfig: (options) => {
            config = { ...defaults, ...options };
            applyContextVisibility();
            handleTypeChange();
        },
        applyContextVisibility,
        handleTypeChange,
        toggleOptionsField,
        toggleTableField,
        toggleSpanField,
        toggleListField,
        toggleNumberField,
        toggleScoringField,
        handleDropdownMultiToggleChange,
        isDropdownMultiSelected,
        checkTypeChange,
        resetForm,
        fillForm,
        collectFormData,
        refreshElements: memoizeElements
    };

    window.ColumnFieldEditor = ColumnFieldEditor;
    window.toggleOptionsField = toggleOptionsField;
    window.toggleTableField = toggleTableField;
    window.toggleSpanField = toggleSpanField;
    window.toggleListField = toggleListField;
    window.toggleNumberField = toggleNumberField;
    window.toggleScoringField = toggleScoringField;
    window.handleDropdownMultiToggleChange = handleDropdownMultiToggleChange;
    window.isDropdownMultiSelected = isDropdownMultiSelected;
    window.checkTypeChange = checkTypeChange;
})(window);
