(() => {
  'use strict';
  const root = document.getElementById('navigator');
  const $ = id => document.getElementById(id);
  const fmt = value => Number(value).toLocaleString('ko-KR');
  const count = value => `${fmt(value)}건`;
  const rate = (value, total) => total ? `${(value * 100 / total).toFixed(1)}%` : '—';
  let data;
  let selectedPartner;
  function el(tag, text, cls) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (cls) node.className = cls;
    return node;
  }
  function empty(target, message = '조회 범위에 해당하는 데이터가 없습니다.') {
    target.replaceChildren(el('p', message, 'nv-empty'));
  }
  function legend() {
    const wrapper = el('div', undefined, 'nv-legend');
    data.statuses.forEach(status => {
      const label = el('span');
      const dot = el('i', undefined, 'nv-dot');
      dot.style.background = status.color;
      label.append(dot, document.createTextNode(status.label));
      wrapper.append(label);
    });
    return wrapper;
  }
  function track(counts, showNumbers = true, widthTotal) {
    const total = Object.values(counts).reduce((sum, n) => sum + n, 0);
    const bar = el('div', undefined, 'nv-track');
    bar.setAttribute('role', 'img');
    bar.setAttribute('aria-label', data.statuses.map(s => `${s.label} ${count(counts[s.key])}`).join(', '));
    data.statuses.forEach(status => {
      const n = counts[status.key];
      if (!n) return;
      const segment = el('span', showNumbers && n / (widthTotal || total) >= 0.08 ? fmt(n) : '', 'nv-segment');
      segment.style.width = `${100 * n / (widthTotal || total)}%`;
      segment.style.background = status.color;
      segment.title = `${status.label} ${count(n)}`;
      bar.append(segment);
    });
    return bar;
  }
  function bars(rows) {
    const wrapper = el('div', undefined, 'nv-bars');
    const max = Math.max(1, ...rows.map(r => r.total));
    rows.forEach(row => {
      const line = el('div', undefined, 'nv-bar-row');
      const name = el('span', row.name, 'nv-bar-name');
      name.title = row.name;
      line.append(name, track(row.counts, true, max), el('span', fmt(row.total), 'nv-bar-total'));
      wrapper.append(line);
    });
    if (!rows.length) empty(wrapper);
    return wrapper;
  }
  function table(headers, rows) {
    const tableNode = el('table', undefined, 'nv-table');
    const head = el('thead');
    const hrow = el('tr');
    headers.forEach(h => { const th = el('th', h); th.scope = 'col'; hrow.append(th); });
    head.append(hrow);
    const body = el('tbody');
    rows.forEach(row => {
      const tr = el('tr');
      row.forEach(value => {
        const cell = el('td');
        if (value instanceof Node) cell.append(value);
        else { cell.textContent = value; cell.title = value; }
        tr.append(cell);
      });
      body.append(tr);
    });
    tableNode.append(head, body);
    return tableNode;
  }
  function siteTable(rows, details = false) {
    const result = table(['사업장', '대상', ...data.statuses.map(s => s.label)],
      rows.map(r => [r.name, fmt(r.total), ...data.statuses.map(s => fmt(r.counts[s.key]))]));
    result.style.minWidth = `${(data.statuses.length + 2) * 62}px`;
    return result;
  }
  function statusBadge(label) {
    const badge = el('span', label, 'nv-badge');
    const status = data.statuses.find(s => s.label === label);
    if (status) {
      badge.style.color = status.color;
      badge.style.background = `${status.color}18`;
    }
    return badge;
  }
  function exceptionTable(rows) {
    return table(['협력사', '사업장', '해당 업무', '확인 내용', '담당', '상태'],
      rows.map(r => [r.partner_name, r.site, r.work_name, r.issue, r.owner_name, statusBadge(r.status)]));
  }
  function openDialog(title, nodes) {
    $('nv-dialog-title').textContent = title;
    $('nv-dialog-body').replaceChildren(...nodes);
    if (!$('nv-dialog').open) $('nv-dialog').showModal();
  }
  function showPartner(partner) {
    selectedPartner = partner;
    const target = $('nv-partner');
    if (!partner) { empty(target, '조회 가능한 협력사가 없습니다.'); return; }
    const heading = el('div', undefined, 'nv-partner-heading');
    heading.append(el('strong', partner.name), el('span', partner.tiers.join(' · '), 'nv-badge'));
    const stats = el('div', undefined, 'nv-partner-stats');
    [['전체 업무', partner.total, null], ...data.statuses.map(s => [s.label, partner.counts[s.key], s.color])].forEach(([label, n, color]) => {
      const box = el('div');
      const value = el('strong', count(n));
      if (color) value.style.color = color;
      box.append(el('small', label), value); stats.append(box);
    });
    const foot = el('div', undefined, 'nv-partner-footer');
    const detail = el('button', '상세 현황 보기 ›', 'nv-link');
    detail.addEventListener('click', () => {
      const rows = Object.entries(partner.work).map(([name, counts]) => ({name, counts, total: Object.values(counts).reduce((a, b) => a + b, 0)}));
      openDialog(`${partner.name} · 업무 현황`, [legend(), bars(rows),
        table(['업무', ...data.statuses.map(s => s.label)], rows.map(r => [r.name, ...data.statuses.map(s => fmt(r.counts[s.key]))]))]);
    });
    foot.append(el('span', `Gate 미완료 ${count(partner.gate_incomplete)}`, partner.gate_incomplete ? 'nv-danger' : ''), detail);
    target.replaceChildren(heading, el('div', partner.sites.join(' · '), 'nv-partner-info'), stats, track(partner.counts, false), foot);
  }
  function render() {
    const summary = data.summary;
    $('nv-time').textContent = `조회 기준 ${data.queried_at}`;
    $('nv-sample').hidden = !data.sample;
    const cards = [
      {label: '관리 대상 협력사', value: `${fmt(summary.partners)}개사`, note: '현재 조회 범위 기준', color: '#2f5fd3'},
      {label: '전체 대상 업무', value: count(summary.total), note: '연계 업무 합계', color: '#2f5fd3'},
      ...data.statuses.map(s => ({label: s.label, value: count(summary.counts[s.key]),
        note: rate(summary.counts[s.key], summary.total), color: s.color, key: s.key})),
      {label: 'Gate 업무 미완료', value: count(data.gate.incomplete), note: '필수 업무 확인 필요', color: '#ef5350'}
    ];
    $('nv-kpis').replaceChildren(...cards.map(card => {
      const article = el('article', undefined, 'nv-card nv-kpi');
      if (card.key) article.dataset.status = card.key;
      const dot = el('span', undefined, 'nv-kpi-dot'); dot.style.background = card.color;
      const body = el('div'); const value = el('strong', card.value); value.style.color = card.color;
      body.append(el('h2', card.label), value, el('small', card.note)); article.append(dot, body);
      return article;
    }));
    $('nv-legend').replaceChildren(...legend().childNodes);
    const rowLimit = window.innerHeight < 800 ? 3 : 4;
    $('nv-work').replaceChildren(bars(data.work.slice(0, rowLimit)));
    if (data.sites.length) $('nv-sites').replaceChildren(siteTable(data.sites.slice(0, window.innerHeight < 800 ? 4 : 5)));
    else empty($('nv-sites'));
    const gateTotal = data.gate.completed + data.gate.incomplete;
    $('nv-gate-total').textContent = count(gateTotal);
    $('nv-gate-completed').textContent = count(data.gate.completed);
    $('nv-gate-incomplete').textContent = count(data.gate.incomplete);
    const angle = gateTotal ? 360 * data.gate.completed / gateTotal : 0;
    $('nv-donut').style.background = gateTotal ? `conic-gradient(#32a56a 0deg ${angle}deg, #ef5350 ${angle}deg 360deg)` : '#e9eef5';
    $('nv-donut').setAttribute('aria-label', `Gate 전체 ${count(gateTotal)}, 완료 ${count(data.gate.completed)}, 미완료 ${count(data.gate.incomplete)}`);
    $('nv-exception-count').textContent = data.exceptions_linked ? `${count(data.exceptions.length)}` : '미연계';
    if (data.exceptions.length) $('nv-exceptions').replaceChildren(exceptionTable(data.exceptions.slice(0, rowLimit)));
    else empty($('nv-exceptions'), data.exceptions_linked ? '비정상 진행 항목이 없습니다.' : '아직 연계되지 않은 항목입니다.');
    showPartner(selectedPartner || data.partners[0]);
    document.querySelector('[data-dialog="work"]').hidden = data.work.length <= rowLimit && data.statuses.length <= 3;
    document.querySelector('[data-dialog="sites"]').hidden = data.sites.length <= (window.innerHeight < 800 ? 4 : 5) && data.statuses.length <= 2;
  }
  document.querySelectorAll('[data-dialog]').forEach(button => button.addEventListener('click', () => {
    if (!data) return;
    const type = button.dataset.dialog;
    if (type === 'work') openDialog('업무별 현황', [legend(), bars(data.work), table(['업무', ...data.statuses.map(s => s.label)], data.work.map(r => [r.name, ...data.statuses.map(s => fmt(r.counts[s.key]))]))]);
    if (type === 'sites') openDialog('사업장별 업무 현황', [siteTable(data.sites, true)]);
    if (type === 'exceptions') openDialog('비정상 진행 현황', [data.exceptions.length ? exceptionTable(data.exceptions) : el('p', data.exceptions_linked ? '비정상 진행 항목이 없습니다.' : '아직 연계되지 않은 항목입니다.', 'nv-empty')]);
  }));
  $('nv-close').addEventListener('click', () => $('nv-dialog').close());
  $('nv-search').addEventListener('submit', event => {
    event.preventDefault();
    if (!data) return;
    const query = $('nv-search-input').value.trim().toLocaleLowerCase();
    const matches = data.partners.filter(p => p.name.toLocaleLowerCase().includes(query));
    if (matches.length === 1) { showPartner(matches[0]); return; }
    const nodes = matches.map(p => {
      const button = el('button', `${p.name} · ${p.sites.join(', ')} · 전체 ${count(p.total)}`, 'nv-result');
      button.addEventListener('click', () => { showPartner(p); $('nv-dialog').close(); });
      return button;
    });
    openDialog('협력사 검색', nodes.length ? nodes : [el('p', '검색 결과가 없습니다.', 'nv-empty')]);
  });
  window.addEventListener('resize', () => { if (data) render(); });
  fetch(root.dataset.api, {cache: 'no-store', credentials: 'same-origin'})
    .then(async response => { const result = await response.json(); if (!response.ok) throw new Error(result.error || '현황을 불러오지 못했습니다.'); return result; })
    .then(result => { data = result; render(); $('nv-message').textContent = ''; })
    .catch(error => { $('nv-message').textContent = error.message; })
    .finally(() => root.setAttribute('aria-busy', 'false'));
})();
