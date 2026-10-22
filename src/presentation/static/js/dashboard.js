/* ── Constants (item 5: sem magic strings espalhadas) ── */
const TYPE = {
  COHOST: 'COHOST_ASSIGNMENT_FAILED',
  CONFIG: 'MEET_SPACE_CONFIG_FAILED',
};

const VIEW = {
  DASHBOARD:      'dashboard',
  REPROCESSADOS:  'reprocessados',
  ENCERRADOS:     'encerrados',
};

/* ── Labels unificados (item 5: 5 objetos → 1) ── */
const LABELS = {
  severity: { info: 'Informação', warning: 'Alerta', error: 'Erro', critical: 'Crítico' },
  status:   { open: 'Aberto', reprocessing: 'Retentativa', resolved: 'Encerrado' },
  type: {
    [TYPE.COHOST]: 'Não foi possível adicionar coorganizador',
    [TYPE.CONFIG]: 'Falha na configuração do Meet',
  },
  action: {
    manual_reprocess: 'Reprocessamento manual',
    resolve:          'Encerramento',
    auto_retry:       'Retentativa automática',
    close:            'Fechamento',
  },
  jobStatus: {
    queued: 'na fila', closed: 'concluído',
    failed: 'falhou',  success: 'sucesso', open: 'aberto',
  },
};

/* ── SVG centralizados ── */
const SVG = {
  dashboard: `<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><rect x="3" y="3" width="8" height="8" rx="1.5"/><rect x="13" y="3" width="8" height="8" rx="1.5"/><rect x="3" y="13" width="8" height="8" rx="1.5"/><rect x="13" y="13" width="8" height="8" rx="1.5"/></svg>`,
  refresh:   `<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 4a8 8 0 0 0-8 8H2l3.5 3.5L9 12H7a5 5 0 1 1 1.34 3.39l-1.42 1.42A8 8 0 1 0 12 4z"/></svg>`,
  check:     `<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path fill-rule="evenodd" d="M12 2a10 10 0 1 0 0 20A10 10 0 0 0 12 2zm4.7 7.7a1 1 0 0 0-1.4-1.4L10 13.58l-1.3-1.3a1 1 0 0 0-1.4 1.42l2 2a1 1 0 0 0 1.4 0l6-6z"/></svg>`,
  cohost:    `<svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M16 11c1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3 1.34 3 3 3zm-8 0c1.66 0 3-1.34 3-3S9.66 5 8 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5z"/></svg>`,
  config:    `<svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M12 15.5a3.5 3.5 0 1 1 0-7 3.5 3.5 0 0 1 0 7zm7.43-2.4c.04-.3.07-.6.07-.9s-.03-.61-.07-.91l1.98-1.55a.48.48 0 0 0 .11-.6l-1.88-3.25a.48.48 0 0 0-.58-.21l-2.33.94a6.8 6.8 0 0 0-1.57-.91l-.35-2.47A.47.47 0 0 0 14.38 3h-3.76a.47.47 0 0 0-.47.4l-.35 2.47c-.56.23-1.09.54-1.57.91l-2.33-.94a.47.47 0 0 0-.58.21L3.44 9.3a.46.46 0 0 0 .11.6l1.98 1.55c-.04.3-.06.6-.06.91s.02.6.06.9L3.55 14.8a.46.46 0 0 0-.11.6l1.88 3.25c.12.21.37.29.58.21l2.33-.94c.48.37 1 .68 1.57.91l.35 2.47c.06.26.29.45.47.45h3.76c.26 0 .47-.19.47-.4l.35-2.47c.56-.23 1.09-.54 1.57-.91l2.33.94c.21.08.46 0 .58-.21l1.88-3.25a.46.46 0 0 0-.11-.6l-1.98-1.55z"/></svg>`,
  arrow:     `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>`,
};

/* ── Config fields map (item 3: DRY — fetchConfig e submit driven pelo mesmo array) ── */
const CONFIG_FIELDS = [
  { id: 'cfg-schedule',     key: 'schedule',                get: c => (c.schedule || []).join(', '),   set: v => v ? v.split(',').map(s => s.trim()).filter(Boolean) : [] },
  { id: 'cfg-timezone',     key: 'timezone',                get: c => c.timezone || '',                set: v => v.trim() || 'America/Recife' },
  { id: 'cfg-days-ahead',   key: 'days_ahead',              get: c => c.days_ahead ?? 1,               set: v => parseInt(v, 10) || 1 },
  { id: 'cfg-days-behind',  key: 'days_behind',             get: c => c.days_behind ?? 0,              set: v => parseInt(v, 10) || 0 },
  { id: 'cfg-calendar-id',  key: 'calendar_id',             get: c => c.calendar_id || '',             set: v => v.trim() || 'primary' },
  { id: 'cfg-report-email', key: 'report_email_override',   get: c => c.report_email_override || '',   set: v => v.trim() },
  { id: 'cfg-discord',      key: 'discord_webhook_url',     get: c => c.discord_webhook_url || '',     set: v => v.trim() },
  { id: 'cfg-gchat',        key: 'google_chat_webhook_url', get: c => c.google_chat_webhook_url || '', set: v => v.trim() },
  { id: 'cfg-webhook',      key: 'webhook_url',             get: c => c.webhook_url || '',             set: v => v.trim() },
];

/* ── Views ── */
const savedViews = [
  { id: VIEW.DASHBOARD,     label: 'Dashboard',     icon: SVG.dashboard, filters: { status: 'open' } },
  { id: VIEW.REPROCESSADOS, label: 'Reprocessados', icon: SVG.refresh,   filters: { status: 'reprocessing' } },
  { id: VIEW.ENCERRADOS,    label: 'Encerrados',    icon: SVG.check,     filters: { status: 'resolved' } },
];


/* ── Roteamento por hash ── */
const ROUTE_CONFIG = 'ajustes';

const navigate = id => { if (location.hash !== `#${id}`) location.hash = id; };

const currentRoute = () => location.hash.slice(1) || VIEW.DASHBOARD;

/* ── Estado global ── */
let allIncidents = [];
let activeView = VIEW.DASHBOARD;

/* ── DOM refs cacheados ── */
const viewList          = document.getElementById('view-list');
const form              = document.getElementById('filters-form');
const incidentBody      = document.getElementById('incident-body');
const clearFiltersBtn   = document.getElementById('clear-filters');
const activeViewTitle   = document.getElementById('active-view-title');
const resultCount       = document.getElementById('result-count');
const detail            = document.getElementById('detail-overlay');
const detailTitle       = document.getElementById('detail-title');
const detailSubtitle    = document.getElementById('detail-subtitle');
const detailBody        = document.getElementById('detail-body');
const detailClose       = document.getElementById('detail-close');
const confirmModal      = document.getElementById('confirm-modal');
const configPanel       = document.getElementById('config-panel');
const incidentsPanel    = document.getElementById('incidents-panel');
const btnConfig         = document.getElementById('btn-config');
const configForm        = document.getElementById('config-form');
const configFeedback    = document.getElementById('config-feedback');
const sessionSearchEl   = document.getElementById('session-search');
const sessionSeverityEl = document.getElementById('session-severity');
const sessionDateEl     = document.getElementById('session-date');
const sessionBadgeEl    = document.getElementById('session-count-badge');

/* ── Utilidades ── */
const textOrDash = value => {
  const s = value == null ? '' : String(value).trim();
  return s || '-';
};

const createText = (tag, text, className = '') => {
  const el = document.createElement(tag);
  el.textContent = text;
  if (className) el.className = className;
  return el;
};

const formatCount = n => `${n} registro${n === 1 ? '' : 's'}`;

const createButton = (label, className, onClick) => {
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = className;
  if (label) btn.textContent = label;
  if (onClick) btn.addEventListener('click', onClick);
  return btn;
};

const formatDatetime = value => {
  if (!value) return '-';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
};

/* ── Filtros ── */
const normalizeFilters = filters => ({
  severity:    filters.severity   || '',
  status:      filters.status     || '',
  event_id:    filters.event_id   || '',
  tag:         filters.tag        || '',
  tagAny:      filters.tagAny     || [],
  reprocessed: Boolean(filters.reprocessed),
  query:       filters.query      || '',
  date:        filters.date       || '',
});

const currentFilters = () => ({
  severity: document.getElementById('severity-filter').value,
  status:   document.getElementById('status-filter').value,
  event_id: document.getElementById('event-filter').value.trim(),
  date:     (document.getElementById('date-filter').value || '').trim(),
});

const setFilters = filters => {
  const f = normalizeFilters(filters);
  document.getElementById('severity-filter').value = f.severity;
  document.getElementById('status-filter').value   = f.status;
  document.getElementById('event-filter').value    = f.event_id;
};

const tagsOf = item => ((item.metadata || {}).tags || []).map(t => String(t).toLowerCase());

const matchesFilters = (item, filters) => {
  const tags = tagsOf(item);
  if (filters.severity && item.severity !== filters.severity) return false;
  if (filters.status   && item.status   !== filters.status)   return false;
  if (filters.event_id) {
    const haystack = (item.metadata?.title || item.event_id || '').toLowerCase();
    if (!haystack.includes(filters.event_id.toLowerCase())) return false;
  }
  if (filters.tag      && !tags.includes(filters.tag.toLowerCase())) return false;
  if (filters.tagAny?.length && !filters.tagAny.some(t => tags.includes(String(t).toLowerCase()))) return false;
  if (filters.reprocessed) {
    const jobs = (item.metadata || {}).reprocess_jobs || [];
    if (!Array.isArray(jobs) || !jobs.length) return false;
  }
  if (filters.date) {
    const ds = formatDatetime(item.first_seen || item.last_seen);
    if (!ds.includes(filters.date)) return false;
  }
  return true;
};

const classFor = (value, kind) => {
  const allowed = new Set(['severity-info','severity-warning','severity-error','severity-critical','status-open','status-reprocessing','status-resolved']);
  const cls = `${kind}-${value}`;
  return allowed.has(cls) ? cls : '';
};

const createBadge = (value, kind) => {
  const el = document.createElement('span');
  el.className = `badge ${classFor(value, kind)}`.trim();
  el.textContent = LABELS[kind]?.[value] || textOrDash(value);
  return el;
};

const filtersForActiveView = () => normalizeFilters(savedViews.find(v => v.id === activeView)?.filters || {});
const mergedFilters        = () => ({ ...filtersForActiveView(), ...currentFilters() });
const countForView         = view => allIncidents.filter(i => matchesFilters(i, normalizeFilters(view.filters))).length;

/* ── Nav ── */
const clearNavActive = () => document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));

const renderNav = () => {
  viewList.replaceChildren();
  const configVisible = configPanel && !configPanel.hidden;
  savedViews.forEach(view => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = view.id === activeView && !configVisible ? 'nav-item active' : 'nav-item';
    btn.addEventListener('click', () => {
      if (configPanel && !configPanel.hidden) {
        configPanel.hidden = true;
        incidentsPanel.hidden = false;
      }
      clearNavActive();
      btnConfig.classList.remove('active');
      activeView = view.id;
      setFilters(view.filters);
      navigate(view.id);
      renderAll();
    });
    const icon = document.createElement('span');
    icon.className = 'nav-icon';
    icon.innerHTML = view.icon;
    btn.appendChild(icon);
    btn.appendChild(createText('span', view.label));
    btn.appendChild(createText('span', String(countForView(view)), 'view-count'));
    viewList.appendChild(btn);
  });
};

/* ── Dashboard renders ── */

let _stats = { total_processed: 0, total_success: 0, automation_pct: 0, by_day: {}, by_type: {} };

const renderSummary = filtered => {
  document.getElementById('meetings-count').textContent = _stats.total_processed || '-';
  document.getElementById('open-count').textContent    = filtered.filter(i => i.status === 'open').length;
  document.getElementById('warning-count').textContent = filtered.filter(i => i.severity === 'warning').length;
  document.getElementById('error-count').textContent   = filtered.filter(i => i.severity === 'error' || i.severity === 'critical').length;
  const pct = _stats.automation_pct ?? 0;
  document.getElementById('automation-score').textContent = `${pct}%`;
  const bar = document.getElementById('automation-bar');
  if (bar) bar.style.width = `${pct}%`;
  const total = _stats.total_processed ?? 0;
  const success = _stats.total_success ?? 0;
  document.getElementById('automation-sub').textContent =
    total ? `${success} de ${total} reuniões configuradas com sucesso.` : 'Nenhuma reunião processada ainda.';
};

const renderLegend = incidents => {
  const legend = document.getElementById('category-legend');
  legend.replaceChildren();
  const rows = [
    ['Coorganizador',    incidents.filter(i => i.type === TYPE.COHOST).length,                                          '#0d7661'],
    ['Configuração Meet',incidents.filter(i => i.type === TYPE.CONFIG).length,                                          '#8bbfb0'],
    ['Outros',           incidents.filter(i => ![TYPE.COHOST, TYPE.CONFIG].includes(i.type)).length,                    '#dce6dd'],
  ];
  const total = Math.max(1, incidents.length);
  rows.forEach(([label, value, color]) => {
    const row = document.createElement('div');
    row.className = 'legend-row';
    const swatch = document.createElement('span');
    swatch.className = 'swatch';
    swatch.style.background = color;
    row.appendChild(swatch);
    row.appendChild(createText('span', label));
    row.appendChild(createText('span', String(value)));
    row.appendChild(createText('span', `${Math.round((value / total) * 100)}%`));
    legend.appendChild(row);
  });
};

const renderBars = () => {
  const bars = document.getElementById('bars');
  bars.replaceChildren();
  const days   = ['Dom','Seg','Ter','Qua','Qui','Sex','Sáb'];
  const counts = days.map((_, idx) => _stats.by_day?.[String(idx)] || 0);
  const max = Math.max(1, ...counts);
  days.forEach((day, idx) => {
    const col = document.createElement('div');
    col.className = 'bar-col';
    const bar = document.createElement('div');
    bar.className = 'bar';
    bar.style.height = `${Math.max(18, (counts[idx] / max) * 205)}px`;
    col.appendChild(bar);
    col.appendChild(createText('span', day));
    bars.appendChild(col);
  });
};

const renderTags = (cell, metadata = {}) => {
  const tags = Array.isArray(metadata.tags) ? metadata.tags : [];
  if (!tags.length) { cell.appendChild(createText('span', 'Sem tags')); return; }
  const list = document.createElement('div');
  list.className = 'tag-list';
  tags.forEach(tag => list.appendChild(createText('span', textOrDash(tag), 'tag')));
  cell.appendChild(list);
};

/* ── Table row factory (item 1: extraído de renderTable) ── */
const createTableRow = item => {
  const row = document.createElement('tr');
  row.addEventListener('click', () => showDetail(item));

  const dateCell = document.createElement('td');
  dateCell.className = 'td-date';
  dateCell.appendChild(createText('span', formatDatetime(item.first_seen || item.last_seen)));
  row.appendChild(dateCell);

  const eventCell = document.createElement('td');
  eventCell.appendChild(createText('span', textOrDash(item.metadata?.title || item.event_id)));
  row.appendChild(eventCell);

  const typeCell = document.createElement('td');
  typeCell.appendChild(createText('span', LABELS.type[item.type] || item.type));
  row.appendChild(typeCell);

  const sevCell = document.createElement('td');
  sevCell.appendChild(createBadge(item.severity, 'severity'));
  row.appendChild(sevCell);

  const sumCell = document.createElement('td');
  sumCell.className = 'summary-cell';
  sumCell.appendChild(createText('span', textOrDash(item.summary)));
  row.appendChild(sumCell);

  const actionsCell = document.createElement('td');
  const actions = document.createElement('div');
  actions.className = 'actions';
  if (activeView === VIEW.DASHBOARD) {
    const retry = createButton('Reprocessar', 'btn-search', e => { e.stopPropagation(); postAction(item.id, 'reprocess', retry); });
    const close = createButton('Encerrar', 'button secondary', e => { e.stopPropagation(); postAction(item.id, 'close', close); });
    actions.appendChild(retry);
    actions.appendChild(close);
  } else if (activeView === VIEW.ENCERRADOS) {
    const reopen = createButton('Devolver ao Dashboard', 'button secondary', e => { e.stopPropagation(); _doAction(item.id, 'reopen', reopen); });
    actions.appendChild(reopen);
  }
  actionsCell.appendChild(actions);
  row.appendChild(actionsCell);

  return row;
};

const renderTable = incidents => {
  incidentBody.replaceChildren();
  resultCount.textContent   = formatCount(incidents.length);
  activeViewTitle.textContent = 'Ocorrências abertas';
  if (!incidents.length) {
    const row  = document.createElement('tr');
    const cell = document.createElement('td');
    cell.className = 'empty'; cell.colSpan = 6;
    cell.textContent = 'Nenhuma ocorrência encontrada para este filtro.';
    row.appendChild(cell);
    incidentBody.appendChild(row);
    return;
  }
  incidents.forEach(item => incidentBody.appendChild(createTableRow(item)));
};

/* ── Incident card factories (item 1: extraídos de renderCardViewGrid) ── */
const createCardTopBar = item => {
  const topBar = document.createElement('div');
  topBar.className = 'ic-top-bar';
  const typeIcon = document.createElement('div');
  typeIcon.className = `ic-type-icon${item.status === 'open' ? ' info-icon' : ' ok-icon'}`;
  typeIcon.innerHTML = item.type === TYPE.COHOST ? SVG.cohost : SVG.config;
  topBar.appendChild(typeIcon);
  topBar.appendChild(createBadge(item.severity, 'severity'));
  return topBar;
};

const createCardFooter = (item, isReprocessed) => {
  const footer   = document.createElement('div');
  footer.className = 'ic-card-footer';
  const footLeft = document.createElement('div');
  footLeft.appendChild(createText('div', isReprocessed ? 'Última tentativa' : 'Encerrado em', 'ic-foot-label'));
  const t         = isReprocessed ? item.last_seen : (item.resolved_at || item.last_seen);
  const footValue = createText('div', formatDatetime(t || item.first_seen), 'ic-foot-value');
  if (isReprocessed && item.retries > 0) {
    footValue.appendChild(createText('span', `· ${item.retries}×`, 'ic-retry-count'));
  }
  footLeft.appendChild(footValue);
  footer.appendChild(footLeft);
  const arrowBtn = createButton(null, 'ic-arrow-btn', e => { e.stopPropagation(); showDetail(item); });
  arrowBtn.innerHTML = SVG.arrow;
  footer.appendChild(arrowBtn);

  const reopen = createButton('Devolver', 'button secondary', e => { e.stopPropagation(); _doAction(item.id, 'reopen', reopen); });
  footer.appendChild(reopen);
  return footer;
};

const createIncidentCard = (item, isReprocessed) => {
  const card = document.createElement('article');
  card.className = `incident-card ${item.status}`;
  card.addEventListener('click', () => showDetail(item));
  card.appendChild(createCardTopBar(item));
  const title = createText('div', textOrDash(item.metadata?.title || item.event_id), 'ic-card-title');
  title.title = textOrDash(item.metadata?.title || item.event_id);
  card.appendChild(title);
  card.appendChild(createText('div', LABELS.type[item.type] || item.type || '-', 'ic-card-subtitle'));
  if (item.summary) card.appendChild(createText('div', item.summary, 'ic-card-desc'));
  const tags = tagsOf(item);
  if (tags.length) {
    const tagWrap = document.createElement('div');
    tagWrap.className = 'tag-list ic-card-tags';
    tags.slice(0, 3).forEach(t => tagWrap.appendChild(createText('span', t, 'tag')));
    card.appendChild(tagWrap);
  }
  card.appendChild(createCardFooter(item, isReprocessed));
  return card;
};

/* ── Session view ── */
const renderCardViewGrid = incidents => {
  const grid = document.getElementById('session-card-grid');
  const isReprocessed = activeView === VIEW.REPROCESSADOS;
  grid.replaceChildren();
  if (!incidents.length) {
    const empty = document.createElement('div');
    empty.className = 'session-empty';
    empty.textContent = 'Nenhuma ocorrência encontrada.';
    grid.appendChild(empty);
    return;
  }
  incidents.forEach(item => grid.appendChild(createIncidentCard(item, isReprocessed)));
};

const sessionSearch = () => {
  const q     = sessionSearchEl.value.toLowerCase().trim();
  const sev   = sessionSeverityEl.value;
  const dateQ = sessionDateEl.value.trim();
  const view  = savedViews.find(v => v.id === activeView);
  const base  = allIncidents.filter(i => matchesFilters(i, normalizeFilters(view?.filters || {})));
  const filtered = base.filter(item => {
    if (sev && item.severity !== sev) return false;
    if (q) {
      const hay = [item.event_id, item.summary, LABELS.type[item.type] || item.type].join(' ').toLowerCase();
      if (!hay.includes(q)) return false;
    }
    if (dateQ) {
      const t = activeView === VIEW.REPROCESSADOS ? item.last_seen : (item.resolved_at || item.last_seen || item.first_seen);
      if (!formatDatetime(t).includes(dateQ)) return false;
    }
    return true;
  });
  renderCardViewGrid(filtered);
  sessionBadgeEl.textContent = formatCount(filtered.length);
};

const renderCardView = incidents => {
  const isReprocessed = activeView === VIEW.REPROCESSADOS;
  document.getElementById('session-title').textContent    = isReprocessed ? 'Reprocessados' : 'Encerrados';
  document.getElementById('session-subtitle').textContent = isReprocessed
    ? 'Em retentativa automática ou manual.'
    : 'Encerrados pela equipe ou pelo bot.';
  sessionBadgeEl.textContent = formatCount(incidents.length);
  sessionBadgeEl.className   = 'session-count-badge';
  sessionSearchEl.value   = '';
  sessionSeverityEl.value = '';
  sessionDateEl.value     = '';
  renderCardViewGrid(incidents);
};

/* ── Render geral ── */
const renderAll = () => {
  const filters    = mergedFilters();
  const filtered   = allIncidents.filter(i => matchesFilters(i, filters));
  const isDashboard = activeView === VIEW.DASHBOARD;
  document.getElementById('main-title-row').hidden     = !isDashboard;
  document.getElementById('section-kpis-label').hidden = !isDashboard;
  document.getElementById('section-kpis').hidden       = !isDashboard;
  document.getElementById('section-charts').hidden     = !isDashboard;
  document.getElementById('table-section').hidden      = !isDashboard;
  document.getElementById('session-panel').hidden      = isDashboard;
  renderNav();
  if (isDashboard) {
    renderSummary(filtered);
    renderLegend(filtered);
    renderBars();
    renderTable(filtered);
  } else {
    renderCardView(filtered);
  }
};

/* ── Data loading ── */
async function loadIncidents() {
  const [resInc, resStats] = await Promise.all([
    fetch('/incidents?include_resolved=true'),
    fetch('/stats'),
  ]);
  if (!resInc.ok) throw new Error('Falha ao carregar incidentes');
  const data = await resInc.json();
  allIncidents = Array.isArray(data) ? data : [];
  if (resStats.ok) _stats = await resStats.json();
  renderAll();
}

/* ── Detail modal ── */
const showDetail = item => {
  detail.hidden = false;
  detailTitle.textContent    = textOrDash(item.summary);
  detailSubtitle.textContent = `${LABELS.status[item.status] || item.status} · ${LABELS.severity[item.severity] || item.severity}`;
  detailBody.replaceChildren();
  [
    ['E-mail afetado',    item.user_email],
    ['O que falhou',      LABELS.type[item.type] || item.type],
    ['Tentativas feitas', item.retries],
    ['Última atualização',formatDatetime(item.last_seen)],
  ].forEach(([label, value]) => {
    if (value == null || String(value).trim() === '' || value === '-') return;
    const field = document.createElement('div');
    field.className = 'field';
    field.appendChild(createText('span', label));
    field.appendChild(createText('p', textOrDash(value)));
    detailBody.appendChild(field);
  });

  const meetingTitle = item.metadata?.title || item.event_id;
  if (meetingTitle) {
    const field = document.createElement('div');
    field.className = 'field';
    field.appendChild(createText('span', 'Encontro'));
    const p = document.createElement('p');
    p.textContent = meetingTitle;
    if (item.event_id) {
      const link = document.createElement('a');
      link.href = `https://calendar.google.com/calendar/r/eventedit/${item.event_id}`;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.textContent = 'ver no Calendar';
      link.className = 'muted-text';
      link.style.cssText = 'font-size:0.75rem;display:block;margin-top:2px';
      p.appendChild(link);
    }
    field.appendChild(p);
    detailBody.insertBefore(field, detailBody.firstChild);
  }
  const history = ((item.metadata || {}).attempt_history || [])
    .slice(-4)
    .map(e => `${LABELS.action[e.action] || e.action} · ${LABELS.jobStatus[e.status] || e.status}`)
    .join('\n');
  const field = document.createElement('div');
  field.className = 'field';
  field.appendChild(createText('span', 'O que já foi tentado'));
  field.appendChild(createText('p', history || 'Ainda sem tentativas registradas'));
  detailBody.appendChild(field);

  if (item.type === TYPE.COHOST) {
    const tip = document.createElement('div');
    tip.className = 'detail-tip';
    tip.innerHTML = `<strong>Como resolver:</strong> peça ao organizador do encontro que substitua o e-mail <em>${textOrDash(item.user_email)}</em> por um e-mail Gmail ou Google Workspace no evento do Google Calendar. Após a troca, clique em <strong>Reprocessar</strong>.`;
    detailBody.appendChild(tip);
  }
};

const closeDetail = () => { detail.hidden = true; };

/* ── Confirm modal ── */
let _pendingId = null, _pendingBtn = null;

const closeModal = () => {
  confirmModal.style.display = 'none';
  if (_pendingBtn) _pendingBtn.disabled = false;
  _pendingId = _pendingBtn = null;
};

const _pollUntilChanged = async (id, originalStatus, originalRetries, button) => {
  const label = button?.textContent;
  if (button) button.textContent = 'Processando…';
  const max = 20;
  for (let i = 0; i < max; i++) {
    await new Promise(r => setTimeout(r, 2000));
    const res = await fetch(`/incidents/${encodeURIComponent(id)}`);
    if (!res.ok) break;
    const inc = await res.json();
    if (inc.status !== originalStatus || inc.retries > originalRetries) break;
  }
  await loadIncidents();
  if (button) { button.textContent = label; button.disabled = false; }
};

const _doAction = async (id, action, button) => {
  if (button) button.disabled = true;
  try {
    const res = await fetch(`/incidents/${encodeURIComponent(id)}/${action}`, { method: 'POST' });
    if (!res.ok) { await loadIncidents(); return; }
    const inc = await res.json();
    if (action === 'reprocess') {
      _pollUntilChanged(id, inc.status, inc.retries ?? 0, button);
      return; // não reabilita o botão aqui — o polling faz isso
    }
    await loadIncidents();
  } finally {
    if (action !== 'reprocess' && button) button.disabled = false;
  }
};

const postAction = (id, action, button) => {
  if (action === 'close') {
    button.disabled = true;
    _pendingId = id; _pendingBtn = button;
    confirmModal.style.display = 'flex';
  } else {
    _doAction(id, action, button);
  }
};

/* ── Config panel ── */
const showConfigPanel = () => {
  incidentsPanel.hidden = true;
  configPanel.hidden    = false;
  clearNavActive();
  btnConfig.classList.add('active');
  navigate(ROUTE_CONFIG);
  fetchConfig();
};

const showFeedback = (msg, ok) => {
  configFeedback.textContent    = msg;
  configFeedback.style.display  = 'block';
  configFeedback.style.background = ok ? '#e5f6ee' : '#fdece9';
  configFeedback.style.color      = ok ? '#167654' : '#b94034';
  setTimeout(() => { configFeedback.style.display = 'none'; }, 4000);
};

/* item 3: fetchConfig driven por CONFIG_FIELDS */
const fetchConfig = async () => {
  try {
    const res = await fetch('/config');
    if (!res.ok) return;
    const cfg = await res.json();
    CONFIG_FIELDS.forEach(({ id, get }) => {
      document.getElementById(id).value = get(cfg);
    });
  } catch { showFeedback('Erro ao carregar ajustes.', false); }
};

/* ── Event listeners ── */
form.addEventListener('submit', e => { e.preventDefault(); renderAll(); });
clearFiltersBtn.addEventListener('click', () => { setFilters({}); renderAll(); });
detailClose.addEventListener('click', closeDetail);
detail.addEventListener('click', e => { if (e.target === detail) closeDetail(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape' && !detail.hidden) closeDetail(); });

sessionSearchEl.addEventListener('input', sessionSearch);
sessionSeverityEl.addEventListener('change', sessionSearch);
sessionDateEl.addEventListener('input', sessionSearch);
document.getElementById('session-clear').addEventListener('click', () => {
  sessionSearchEl.value = ''; sessionSeverityEl.value = ''; sessionDateEl.value = '';
  sessionSearch();
});

document.getElementById('confirm-cancel').addEventListener('click', closeModal);
document.getElementById('confirm-ok').addEventListener('click', async () => {
  confirmModal.style.display = 'none';
  const id = _pendingId, btn = _pendingBtn;
  _pendingId = _pendingBtn = null;
  if (id) await _doAction(id, 'close', btn);
});

btnConfig.addEventListener('click', showConfigPanel);

/* item 3: configForm submit driven por CONFIG_FIELDS */
configForm.addEventListener('submit', async e => {
  e.preventDefault();
  const body = Object.fromEntries(
    CONFIG_FIELDS.map(({ id, key, set }) => [key, set(document.getElementById(id).value)])
  );
  try {
    const res = await fetch('/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    showFeedback(res.ok ? 'Ajustes salvos.' : 'Erro ao salvar.', res.ok);
  } catch { showFeedback('Erro de conexão.', false); }
});

/* ── hashchange — sincroniza view com URL ── */
window.addEventListener('hashchange', () => {
  const route = currentRoute();
  if (route === ROUTE_CONFIG) {
    showConfigPanel();
  } else {
    const view = savedViews.find(v => v.id === route) || savedViews[0];
    if (configPanel && !configPanel.hidden) {
      configPanel.hidden    = true;
      incidentsPanel.hidden = false;
      btnConfig.classList.remove('active');
    }
    activeView = view.id;
    setFilters(view.filters);
    renderAll();
  }
});

/* ── Boot — restaura view do hash ── */
const _bootRoute = currentRoute();
const _bootView  = savedViews.find(v => v.id === _bootRoute);

if (_bootRoute === ROUTE_CONFIG) {
  setFilters(savedViews[0].filters);
} else {
  activeView = (_bootView || savedViews[0]).id;
  setFilters((_bootView || savedViews[0]).filters);
}

loadIncidents()
  .then(() => { if (_bootRoute === ROUTE_CONFIG) showConfigPanel(); })
  .catch(err => {
    incidentBody.replaceChildren();
    const row  = document.createElement('tr');
    const cell = document.createElement('td');
    cell.colSpan = 7; cell.className = 'empty'; cell.textContent = err.message;
    row.appendChild(cell);
    incidentBody.appendChild(row);
  });

/* ── Botão "Rodar bot agora" ── */
const runBtn    = document.getElementById('run-bot-btn');
const runStatus = document.getElementById('run-bot-status');
let _pollTimer  = null;

const _setRunUI = (status, message) => {
  const running = status === 'running';
  runBtn.disabled = running;
  runBtn.textContent = running ? 'Rodando…' : 'Rodar bot agora';
  runStatus.textContent = message || '';
  runStatus.style.color = status === 'error' ? '#b94034' : status === 'done' ? '#167654' : '';
};

const _pollStatus = async () => {
  try {
    const res = await fetch('/run/status');
    const s   = await res.json();
    _setRunUI(s.status, s.message);
    if (s.status === 'running') {
      _pollTimer = setTimeout(_pollStatus, 2000);
    } else {
      if (s.status === 'done') loadIncidents();
    }
  } catch { /* ignora falha de polling */ }
};

runBtn.addEventListener('click', async () => {
  _setRunUI('running', 'Iniciando…');
  try {
    const res = await fetch('/run', { method: 'POST' });
    if (res.status === 409) { _setRunUI('idle', 'Bot já está rodando.'); return; }
    if (!res.ok) { _setRunUI('error', 'Erro ao iniciar o bot.'); return; }
    clearTimeout(_pollTimer);
    _pollTimer = setTimeout(_pollStatus, 1500);
  } catch { _setRunUI('error', 'Erro de conexão.'); }
});
