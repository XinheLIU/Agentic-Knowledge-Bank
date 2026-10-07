/* AI Knowledge Base UI — canonical-store frontend (ticket 12)
 *
 * Talks only to the canonical SQLite store API (/api/articles, /api/stats,
 * /api/filters, /api/sources → Horizon config). Legacy fields/controls
 * (audience/category filters, JSON file import, edit/delete batch actions)
 * are intentionally removed; enrichment artifacts and localization badges
 * are the new first-class concepts.
 */

const API_BASE = '';

const state = {
  currentView: 'articles',
  filters: { source_type: '', tag: '', profile: '', status: '', q: '', from_date: '', to_date: '' },
  sort: 'score',
  page: 1,
  limit: 20,
  totalPages: 1,
  selectedIds: new Set(),
  filterOptions: null,
  stats: null,
  sources: null,
  horizonDir: null,
  drawerOpen: false,
  focusIndex: -1
};

/* API */
async function api(path, opts = {}) {
  const res = await fetch(API_BASE + path, opts);
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try { msg = (await res.json()).error || msg; } catch { /* keep default */ }
    throw new Error(msg);
  }
  return res.json();
}

function fetchArticles() {
  const qs = new URLSearchParams();
  qs.set('page', state.page);
  qs.set('limit', state.limit);
  qs.set('sort', state.sort);
  for (const [key, value] of Object.entries(state.filters)) {
    if (value) qs.set(key, value);
  }
  return api(`/api/articles?${qs}`);
}

function exportArticles(ids) {
  return api('/api/articles/export', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ids })
  });
}

function fetchFilters() { return api('/api/filters'); }
function fetchStats() { return api('/api/stats'); }
function fetchSources() { return api('/api/sources'); }
function patchSource(slug, data) {
  return api(`/api/sources/${encodeURIComponent(slug)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
}

/* View Switching */
function switchView(view) {
  state.currentView = view;
  document.getElementById('tab-articles').classList.toggle('active', view === 'articles');
  document.getElementById('tab-sources').classList.toggle('active', view === 'sources');
  document.getElementById('articles-list').style.display = view === 'articles' ? 'block' : 'none';
  document.getElementById('pagination').style.display = view === 'articles' ? 'flex' : 'none';
  document.getElementById('sources-list').style.display = view === 'sources' ? 'block' : 'none';
  document.getElementById('filters-group').style.display = view === 'articles' ? 'block' : 'none';
  if (view === 'sources') loadSources();
}

/* Sources view (Horizon source governance) */
function renderSourcesView() {
  const container = document.getElementById('sources-list');
  container.innerHTML = '';
  if (state.horizonDir) {
    const dir = document.createElement('div');
    dir.className = 'sources-dir';
    dir.textContent = `Horizon 配置: ${state.horizonDir}`;
    container.appendChild(dir);
  }
  if (!state.sources || state.sources.length === 0) {
    container.insertAdjacentHTML('beforeend',
      '<div class="placeholder">暂无来源数据</div>');
    return;
  }
  const table = document.createElement('table');
  table.className = 'sources-table';
  table.innerHTML = `
    <thead>
      <tr>
        <th>Slug</th>
        <th>名称</th>
        <th>类型</th>
        <th>分类</th>
        <th>近7天</th>
        <th>启用</th>
      </tr>
    </thead>
    <tbody></tbody>
  `;
  const tbody = table.querySelector('tbody');
  for (const src of state.sources) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${escapeHtml(src.slug)}</td>
      <td>${escapeHtml(src.name || src.slug)}</td>
      <td>${escapeHtml(src.source_type)}</td>
      <td>${escapeHtml(src.category || '')}</td>
      <td>${src.last_7d_count}</td>
      <td><input type="checkbox" class="source-toggle" ${src.enabled ? 'checked' : ''} data-slug="${escapeHtml(src.slug)}"></td>
    `;
    tbody.appendChild(tr);
  }
  container.appendChild(table);
  document.querySelectorAll('.source-toggle').forEach(cb => {
    cb.addEventListener('change', async (e) => {
      const slug = e.target.dataset.slug;
      const enabled = e.target.checked;
      try {
        const payload = await patchSource(slug, { enabled });
        state.sources = payload.sources;
        state.horizonDir = payload.horizon_dir || state.horizonDir;
        renderSourcesView();
      } catch (err) {
        console.error('Patch failed:', err);
        alert('更新失败: ' + err.message);
        e.target.checked = !enabled; // revert on validation failure
      }
    });
  });
}

async function loadSources() {
  const container = document.getElementById('sources-list');
  try {
    const payload = await fetchSources();
    state.sources = payload.sources;
    state.horizonDir = payload.horizon_dir;
    renderSourcesView();
  } catch (err) {
    console.error('Load sources failed:', err);
    container.innerHTML = `<div class="placeholder error">加载失败: ${escapeHtml(err.message)}</div>`;
  }
}

/* Filters */
function renderFilters() {
  if (!state.filterOptions) return;
  const { sources, tags, profiles, statuses } = state.filterOptions;
  renderFilterList('source-filters', sources, 'source_type');
  renderFilterList('profile-filters', profiles, 'profile');
  renderFilterList('tag-filters', tags, 'tag');
  renderFilterList('status-filters', statuses, 'status');
}

function renderFilterList(ulId, items, filterKey) {
  const ul = document.getElementById(ulId);
  if (!ul) return;
  ul.innerHTML = '';
  const allLi = document.createElement('li');
  allLi.textContent = '全部';
  allLi.className = state.filters[filterKey] === '' ? 'active' : '';
  allLi.addEventListener('click', () => { state.filters[filterKey] = ''; state.page = 1; loadData(); });
  ul.appendChild(allLi);
  for (const item of items) {
    const li = document.createElement('li');
    li.textContent = item;
    li.className = state.filters[filterKey] === item ? 'active' : '';
    li.addEventListener('click', () => { state.filters[filterKey] = item; state.page = 1; loadData(); });
    ul.appendChild(li);
  }
}

function renderStats() {
  if (!state.stats) return;
  document.getElementById('stat-total').innerHTML = `${state.stats.total} <span>条目</span>`;
  document.getElementById('stat-sources').innerHTML =
    `${Object.keys(state.stats.sources).length} <span>来源类型</span>`;
  document.getElementById('stat-tags').innerHTML = `${Object.keys(state.stats.tags).length} <span>标签</span>`;
  const ver = document.getElementById('kb-version');
  if (ver) ver.textContent = `v${state.stats.version || '?'}`;
}

/* Articles */
function renderArticles(data) {
  const container = document.getElementById('articles-list');
  container.innerHTML = '';
  state.focusIndex = -1;
  if (!data.items || data.items.length === 0) {
    container.innerHTML = '<div class="placeholder">暂无数据</div>';
    renderPagination(data);
    return;
  }
  for (const article of data.items) {
    container.appendChild(createArticleCard(article));
  }
  renderPagination(data);
}

function createArticleCard(article) {
  const div = document.createElement('div');
  div.className = 'article-card' + (state.selectedIds.has(article.id) ? ' selected' : '');
  div.dataset.id = article.id;

  const badges = [];
  if (article.has_zh) badges.push('<span class="lang-badge">中文</span>');
  if (article.has_en) badges.push('<span class="lang-badge">EN</span>');

  div.innerHTML = `
    <div class="article-header">
      <input type="checkbox" class="article-checkbox" ${state.selectedIds.has(article.id) ? 'checked' : ''}>
      <div class="article-title">${escapeHtml(article.title)}</div>
    </div>
    <div class="article-meta">
      <span class="source-badge">${escapeHtml(article.source_type)}</span>
      ${article.score != null ? `<span class="score">★ ${article.score}</span>` : ''}
      ${article.profile ? `<span class="profile-badge">${escapeHtml(article.profile)}</span>` : ''}
      <span class="status-badge status-published">asset</span>
      ${badges.join('')}
      <span>${formatDate(article.updated_at)}</span>
    </div>
    <div class="article-summary">${escapeHtml(article.summary || '')}</div>
    <div class="article-tags">
      ${(article.tags || []).map(t => `<span class="tag" data-tag="${escapeHtml(t)}">${escapeHtml(t)}</span>`).join('')}
    </div>
  `;

  div.querySelector('.article-checkbox').addEventListener('change', (e) => {
    if (e.target.checked) state.selectedIds.add(article.id);
    else state.selectedIds.delete(article.id);
    updateBatchBar();
    div.classList.toggle('selected', e.target.checked);
  });

  div.querySelector('.article-title').addEventListener('click', () => openDrawer(article));

  div.querySelectorAll('.tag').forEach(tagEl => {
    tagEl.addEventListener('click', (e) => {
      e.stopPropagation();
      state.filters.tag = tagEl.dataset.tag;
      state.page = 1;
      loadData();
    });
  });

  return div;
}

function renderPagination(data) {
  const container = document.getElementById('pagination');
  container.innerHTML = '';
  state.totalPages = data.pages || 1;
  const prev = document.createElement('button');
  prev.textContent = '上一页';
  prev.disabled = (data.page || 1) <= 1;
  prev.addEventListener('click', () => { state.page--; loadData(); });
  container.appendChild(prev);
  const info = document.createElement('span');
  info.className = 'page-info';
  info.textContent = `第 ${data.page || 1} / ${data.pages || 1} 页`;
  container.appendChild(info);
  const next = document.createElement('button');
  next.textContent = '下一页';
  next.disabled = (data.page || 1) >= (data.pages || 1);
  next.addEventListener('click', () => { state.page++; loadData(); });
  container.appendChild(next);
}

/* Drawer */
function openDrawer(article) {
  const drawer = document.getElementById('drawer');
  const body = document.getElementById('drawer-body');

  const artifacts = article.artifacts || [];
  const artifactHtml = artifacts.map(a => `
    <div class="drawer-section">
      <h3>${escapeHtml(a.title || a.language || 'enrichment')} <span class="lang-badge">${escapeHtml(a.language)}</span></h3>
      ${(a.blocks || []).map(b => `
        <div class="artifact-block ${b.is_primary ? 'primary' : ''}">
          ${b.title ? `<div class="artifact-title">${escapeHtml(b.title)}</div>` : ''}
          <div class="artifact-content">${escapeHtml(b.content || '')}</div>
        </div>
      `).join('')}
    </div>
  `).join('');

  body.innerHTML = `
    <div class="drawer-title">${escapeHtml(article.title)}</div>
    <div class="drawer-meta">
      <span class="source-badge">${escapeHtml(article.source_type)}</span>
      ${article.profile ? `<span class="profile-badge">${escapeHtml(article.profile)}</span>` : ''}
      ${article.score != null ? `<span class="score">★ ${article.score}</span>` : ''}
      <span class="asset-id">${escapeHtml(article.id)}</span>
      <span>${formatDate(article.published_at || article.updated_at)}</span>
    </div>
    <div class="drawer-section"><h3>摘要</h3><div class="drawer-summary">${escapeHtml(article.summary || '')}</div></div>
    ${article.score_reason ? `<div class="drawer-section"><h3>评分理由</h3><div class="drawer-summary">${escapeHtml(article.score_reason)}</div></div>` : ''}
    ${artifactHtml}
    <div class="drawer-section"><h3>标签</h3><div class="drawer-tags">${(article.tags || []).map(t => `<span class="tag">${escapeHtml(t)}</span>`).join('')}</div></div>
    <div class="drawer-section"><h3>链接</h3><a href="${escapeHtml(article.url || '')}" target="_blank" rel="noopener" class="drawer-link">${escapeHtml(article.url || '')}</a></div>
    ${article.author ? `<div class="drawer-section"><h3>作者</h3><div class="drawer-summary">${escapeHtml(article.author)}</div></div>` : ''}
  `;

  drawer.classList.add('open');
  state.drawerOpen = true;
}

function closeDrawer() {
  document.getElementById('drawer').classList.remove('open');
  state.drawerOpen = false;
}

/* Export (read-only JSON export stays; import is `kb ingest`/`kb restore`) */
async function doExport() {
  const ids = Array.from(state.selectedIds);
  if (!ids.length) { alert('请先选择条目'); return; }
  const data = await exportArticles(ids);
  const blob = new Blob([JSON.stringify(data.articles, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `kb-export-${new Date().toISOString().slice(0, 10)}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

/* Data Loading */
async function loadData() {
  try {
    const [articles, filters, stats] = await Promise.all([fetchArticles(), fetchFilters(), fetchStats()]);
    state.filterOptions = filters;
    state.stats = stats;
    renderFilters();
    renderStats();
    renderArticles(articles);
  } catch (err) {
    console.error('Load failed:', err);
    document.getElementById('articles-list').innerHTML =
      `<div class="placeholder error">加载失败: ${escapeHtml(err.message)}</div>`;
  }
}

/* Utilities */
function escapeHtml(text) {
  if (text == null) return '';
  const div = document.createElement('div');
  div.textContent = String(text);
  return div.innerHTML;
}

function formatDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', year: 'numeric' });
}

/* Theme */
function applyTheme() {
  const dark = localStorage.getItem('kb-theme') === 'dark';
  document.body.classList.toggle('dark', dark);
  const btn = document.getElementById('theme-toggle');
  if (btn) btn.textContent = dark ? '☀️ 亮色' : '🌙 暗黑';
}

function toggleTheme() {
  const dark = !document.body.classList.contains('dark');
  localStorage.setItem('kb-theme', dark ? 'dark' : 'light');
  applyTheme();
}

/* Keyboard shortcuts */
function handleKey(e) {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || e.target.tagName === 'TEXTAREA') return;
  const cards = document.querySelectorAll('.article-card');

  if (e.key === 'Escape') {
    if (state.drawerOpen) { closeDrawer(); return; }
    if (state.selectedIds.size > 0) { clearSelection(); return; }
  }

  if (e.key === 'j' || e.key === 'J') {
    e.preventDefault();
    if (state.focusIndex < cards.length - 1) {
      state.focusIndex++;
      cards[state.focusIndex].scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  if (e.key === 'k' || e.key === 'K') {
    e.preventDefault();
    if (state.focusIndex > 0) {
      state.focusIndex--;
      cards[state.focusIndex].scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  if (e.key === 'x' || e.key === 'X') {
    if (state.focusIndex >= 0 && state.focusIndex < cards.length) {
      const cb = cards[state.focusIndex].querySelector('.article-checkbox');
      cb.checked = !cb.checked;
      cb.dispatchEvent(new Event('change'));
    }
  }

  if (e.key === 'a' || e.key === 'A') {
    e.preventDefault();
    const allIds = Array.from(document.querySelectorAll('.article-card')).map(c => c.dataset.id);
    allIds.forEach(id => state.selectedIds.add(id));
    updateBatchBar();
    cards.forEach(c => c.classList.add('selected'));
  }
}

function clearSelection() {
  state.selectedIds.clear();
  updateBatchBar();
  loadData();
}

function updateBatchBar() {
  const bar = document.getElementById('batch-bar');
  const count = document.getElementById('batch-count');
  if (!bar || !count) return;
  if (state.selectedIds.size > 0) {
    bar.classList.add('visible');
    count.textContent = `已选中 ${state.selectedIds.size} 项`;
  } else {
    bar.classList.remove('visible');
  }
}

/* Event Bindings */
function init() {
  document.getElementById('tab-articles').addEventListener('click', () => switchView('articles'));
  document.getElementById('tab-sources').addEventListener('click', () => switchView('sources'));

  applyTheme();
  document.getElementById('theme-toggle').addEventListener('click', toggleTheme);

  document.getElementById('date-from').addEventListener('change', (e) => {
    state.filters.from_date = e.target.value;
    state.page = 1;
    loadData();
  });
  document.getElementById('date-to').addEventListener('change', (e) => {
    state.filters.to_date = e.target.value;
    state.page = 1;
    loadData();
  });

  let searchTimer = null;
  document.getElementById('search-input').addEventListener('input', (e) => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      state.filters.q = e.target.value;
      state.page = 1;
      loadData();
    }, 250);
  });

  document.getElementById('sort-select').addEventListener('change', (e) => {
    state.sort = e.target.value;
    loadData();
  });

  document.getElementById('export-btn').addEventListener('click', () => {
    doExport().catch(err => alert('导出失败: ' + err.message));
  });

  document.addEventListener('keydown', handleKey);

  document.getElementById('refresh-btn').addEventListener('click', () => loadData());
  document.getElementById('drawer-close').addEventListener('click', closeDrawer);

  document.getElementById('batch-clear').addEventListener('click', clearSelection);
  document.getElementById('batch-export').addEventListener('click', () => {
    doExport().catch(err => alert('导出失败: ' + err.message));
  });

  loadData();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
