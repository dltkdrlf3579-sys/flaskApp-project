(function (window) {
  'use strict';

  function findColumnByKeyOrId(collection, columnKey, columnId) {
    if (!Array.isArray(collection)) {
      return null;
    }
    if (columnKey != null) {
      const target = collection.find((c) => String(c.column_key) === String(columnKey));
      if (target) {
        return target;
      }
    }
    if (columnId != null) {
      const target = collection.find((c) => String(c.id) === String(columnId));
      if (target) {
        return target;
      }
    }
    return null;
  }

  function normalizeBoardKey(boardKey) {
    return (boardKey || '').replace(/_/g, '-');
  }

  function init(config) {
    if (!config) {
      console.warn('[ListChildSupport] init called without config');
      return;
    }

    const settings = {
      apiBase: config.apiBase || '',
      adminBase: config.adminBase || '',
      boardKey: config.boardKey || '',
      getPendingColumns: () => window.pendingColumns,
      getColumns: () => window.columns,
      getEditingId: () => window.editingId,
      reload: typeof config.reload === 'function' ? config.reload : window.loadColumns
    };

    if (typeof config.getPendingColumns === 'function') {
      settings.getPendingColumns = config.getPendingColumns;
    }
    if (typeof config.getColumns === 'function') {
      settings.getColumns = config.getColumns;
    }
    if (typeof config.getEditingId === 'function') {
      settings.getEditingId = config.getEditingId;
    }
    if (typeof config.reload === 'function') {
      settings.reload = config.reload;
    }

    if (!settings.adminBase) {
      if (settings.boardKey) {
        settings.adminBase = `/admin/${normalizeBoardKey(settings.boardKey)}-columns`;
      } else {
        console.warn('[ListChildSupport] adminBase not provided; list builder may not open correctly');
      }
    }

    function getFormColumnId() {
      const input = document.getElementById('columnId');
      if (input && input.value) {
        return input.value;
      }
      return null;
    }

    function getFormColumnKey() {
      const input = document.getElementById('columnKey');
      if (input && input.value) {
        return input.value.trim();
      }
      return '';
    }

    function resolveCurrentColumn() {
      const pending = settings.getPendingColumns ? settings.getPendingColumns() : window.pendingColumns;
      const existing = settings.getColumns ? settings.getColumns() : window.columns;
      const collections = [];
      if (Array.isArray(pending)) {
        collections.push(pending);
      }
      if (Array.isArray(existing) && existing !== pending) {
        collections.push(existing);
      }

      const fallbackId = getFormColumnId();
      const editingId = settings.getEditingId ? settings.getEditingId() : window.editingId;
      const candidateIds = [];
      if (editingId != null) {
        candidateIds.push(editingId);
      }
      if (fallbackId != null && fallbackId !== '' && !candidateIds.includes(fallbackId)) {
        candidateIds.push(fallbackId);
      }

      // Try resolving by id first
      for (const collection of collections) {
        for (const id of candidateIds) {
          const found = findColumnByKeyOrId(collection, null, id);
          if (found) {
            return found;
          }
        }
      }

      // Try resolving by current column key
      const columnKey = getFormColumnKey();
      if (columnKey) {
        for (const collection of collections) {
          const found = findColumnByKeyOrId(collection, columnKey, null);
          if (found) {
            return found;
          }
        }
      }

      return null;
    }

    function openListChildBuilder() {
      const typeSelect = document.getElementById('columnType');
      if (!typeSelect || typeSelect.value !== 'list') {
        alert('리스트 타입일 때만 자식 컬럼을 편집할 수 있습니다.');
        return;
      }
      const column = resolveCurrentColumn();
      if (!column) {
        alert('컬럼 정보를 찾을 수 없습니다. "전체 변경사항 저장" 후 다시 시도해주세요.');
        return;
      }
      if (column._isNew) {
        alert('컬럼을 먼저 저장한 후에 자식 컬럼을 편집할 수 있습니다. "전체 변경사항 저장"을 눌러주세요.');
        return;
      }
      if (column._toDelete) {
        alert('삭제 예정인 컬럼은 자식 컬럼을 편집할 수 없습니다.');
        return;
      }
      openListChildBuilderForKey(column.column_key);
    }

    function openListChildBuilderForKey(columnKey) {
      if (!settings.adminBase) {
        alert('리스트 편집기 경로가 설정되지 않았습니다.');
        return;
      }
      const url = `${settings.adminBase}/${columnKey}/list-builder`;
      const popupWidth = 1100;
      const popupHeight = 800;
      const popupLeft = Math.max(0, Math.round((window.screen.width - popupWidth) / 2));
      const popupTop = Math.max(0, Math.round((window.screen.height - popupHeight) / 2));
      const popupFeatures = [
        `width=${popupWidth}`,
        `height=${popupHeight}`,
        `left=${popupLeft}`,
        `top=${popupTop}`,
        'resizable=yes',
        'scrollbars=yes',
        'toolbar=no',
        'menubar=no',
        'location=no',
        'status=no',
        'noopener=yes'
      ].join(',');
      const popup = window.open(url, `listChildBuilder_${columnKey}`, popupFeatures);
      if (popup) {
        popup.focus();
      } else {
        console.warn('리스트 컬럼 편집 팝업이 차단되었습니다.');
      }
    }

    function openListChildBuilderFromCard(columnId, columnKey) {
      if (!columnKey) {
        alert('컬럼 정보를 찾을 수 없습니다. 새로고침 후 다시 시도해주세요.');
        return;
      }
      const collections = [];
      const pending = settings.getPendingColumns ? settings.getPendingColumns() : window.pendingColumns;
      const existing = settings.getColumns ? settings.getColumns() : window.columns;
      if (Array.isArray(pending)) {
        collections.push(pending);
      }
      if (Array.isArray(existing) && existing !== pending) {
        collections.push(existing);
      }
      let target = null;
      for (const collection of collections) {
        target = findColumnByKeyOrId(collection, columnKey, columnId);
        if (target) break;
      }
      if (!target) {
        alert('컬럼 정보를 찾을 수 없습니다. 새로고침 후 다시 시도해주세요.');
        return;
      }
      if (target._isNew) {
        alert('자식 컬럼을 편집하려면 먼저 해당 컬럼을 저장해주세요.');
        return;
      }
      if (target._toDelete) {
        alert('삭제 예정인 컬럼은 자식 컬럼을 편집할 수 없습니다.');
        return;
      }
      openListChildBuilderForKey(target.column_key || columnKey);
    }
    function openListChildBuilderForKeyById(columnId) {
      const collection = settings.getPendingColumns ? settings.getPendingColumns() : window.pendingColumns;
      const column = findColumnByKeyOrId(collection, null, columnId);
      if (!column) {
        alert('컬럼 정보를 찾을 수 없습니다. 목록을 새로고침 해주세요.');
        return;
      }
      if (column._isNew) {
        alert('컬럼을 먼저 저장한 후 자식 컬럼을 편집할 수 있습니다. "전체 변경사항 저장"을 눌러주세요.');
        return;
      }
      if (column._toDelete) {
        alert('삭제 예정인 컬럼은 자식 컬럼을 편집할 수 없습니다.');
        return;
      }
      openListChildBuilderForKey(column.column_key);
    }
    function updateListBuilderButtonState() {
      const typeSelect = document.getElementById('columnType');
      const field = document.getElementById('listConfigField');
      const btn = document.getElementById('openListBuilderBtn');
      const hint = document.getElementById('listBuilderHint');
      if (!btn || !hint || !field || !typeSelect) {
        return;
      }
      if (typeSelect.value !== 'list') {
        btn.disabled = true;
        hint.textContent = '리스트 타입을 선택하면 자식 컬럼을 편집할 수 있습니다.';
        return;
      }
      const column = resolveCurrentColumn();
      if (column && column._toDelete) {
        btn.disabled = true;
        hint.textContent = '삭제 예정인 컬럼은 자식 컬럼을 편집할 수 없습니다.';
      } else {
        btn.disabled = false;
        hint.textContent = column && !column._isNew
          ? '새 창에서 자식 컬럼을 편집합니다.'
          : '컬럼을 먼저 저장한 후 자식 컬럼을 편집하세요.';
      }
    }

    window.openListChildBuilder = openListChildBuilder;
    window.openListChildBuilderForKey = openListChildBuilderForKey;
    window.openListChildBuilderFromCard = openListChildBuilderFromCard;
    window.listChildSupportConfig = settings;

    window.updateListBuilderButtonState = updateListBuilderButtonState;

    window.addEventListener('message', function (event) {
      if (!event || !event.data || event.data.type !== 'LIST_CHILD_SCHEMA_SAVED') {
        return;
      }
      if (event.origin && event.origin !== window.location.origin) {
        return;
      }
      const data = event.data;
      const collections = [
        settings.getPendingColumns ? settings.getPendingColumns() : window.pendingColumns,
        settings.getColumns ? settings.getColumns() : window.columns
      ];
      collections.forEach((collection) => {
        const target = findColumnByKeyOrId(collection, data.columnKey, data.columnId);
        if (target) {
          if (data.schema) {
            target.child_schema = data.schema;
          }
          if (data.listItemType) {
            target.list_item_type = data.listItemType;
          }
          if (data.inputType) {
            target.input_type = data.inputType;
          }
          target._child_schema_generated = false;
        }
      });
      if (typeof settings.reload === 'function') {
        try {
          settings.reload();
        } catch (err) {
          console.warn('[ListChildSupport] reload 실패', err);
        }
      }
    });
  }

  window.ListChildSupport = { init };
})(window);
