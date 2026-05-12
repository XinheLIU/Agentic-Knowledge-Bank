/* AI Knowledge Base UI - Frontend */

const API_BASE = '';

const state = {
  filters: { source: '', tag: '', category: '', status: '', audience: '', q: '', from_date: '', to_date: '' },
  sort: 'updated_at',
  page: 1,
  limit: 20,
  totalPages: 1,
  selectedIds: new Set(),
  filterOptions: null,
  stats: null,
  drawerOpen: false,
  focusIndex: -1
};

/* API */
async function api(path, opts = {}) {
  const res = await fetch(API_BASE + path, opts);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function fetchArticles() {
  const qs = new URLSearchParams();
  qs.set('page', state.page);
  qs.set('limit', state.limit);
  qs.set('sort', state.sort);
  if (state.filters.source) qs.set('source', state.filters.source);
  if (state.filters.tag) qs.set('tag', state.filters.tag);
  if (state.filters.category) qs.set('category', state.filters.category);
  if (state.filters.status) qs.set('status', state.filters.status);
  if (state.filters.audience) qs.set('audience', state.filters.audience);
  if (state.filters.q) qs.set('q', state.filters.q);
  if (state.filters.from_date) qs.set('from_date', state.filters.from_date);
  if (state.filters.to_date) qs.set('to_date', state.filters.to_date);
  return api(`/api/articles?${qs}`);
}

function patchArticle(id, data) {
  return api(`/api/articles/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
}

function deleteArticle(id) {
  return api(`/api/articles/${id}`, { method: 'DELETE' });
}

function batchAction(action, ids, params = {}) {
  return api('/api/articles/batch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, ids, params })
  });
}

function exportArticles(ids) {
  return api('/api/articles/export', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ids })
  });
}

function importArticles(articles) {
  return api('/api/articles/import', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ articles })
  });
}

function fetchFilters() { return api('/api/filters'); }
function fetchStats() { return api('/api/stats'); }

/* Rendering */
function renderFilters() {
  if (!state.filterOptions) return;
  const { sources, tags, categories, statuses } = state.filterOptions;
  renderFilterList('source-filters', sources, 'source');
  renderFilterList('category-filters', categories, 'category');
  renderFilterList('tag-filters', tags, 'tag');
  renderFilterList('status-filters', statuses, 'status');
  populateSelect('batch-tag-select', tags, '打标签...');
  populateSelect('batch-untag-select', tags, '删标签...');
  populateSelect('batch-cat-select', categories, '改分类...');
  populateSelect('batch-status-select', statuses, '改状态...');
}

function populateSelect(selectId, items, placeholder) {
  const sel = document.getElementById(selectId);
  if (!sel) return;
  sel.innerHTML = `<option value="">${escapeHtml(placeholder)}</option>`;
  for (const item of items) {
    const opt = document.createElement('option');
    opt.value = item;
    opt.textContent = item;
    sel.appendChild(opt);
  }
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
  document.getElementById('stat-sources').innerHTML = `${Object.keys(state.stats.sources).length} <span>来源</span>`;
  document.getElementById('stat-tags').innerHTML = `${Object.keys(state.stats.tags).length} <span>标签</span>`;
}

function renderArticles(data) {
  const container = document.getElementById('articles-list');
  container.innerHTML = '';
  state.focusIndex = -1;
  if (!data.items || data.items.length === 0) {
    container.innerHTML = '<div style="text-align:center;color:#999;padding:40px;">暂无数据</div>';
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
  const categories = article.categories || [];
  const catStr = categories.length > 0 ? categories.join(' | ') : '';

  div.innerHTML = `
    <div class="article-header">
      <input type="checkbox" class="article-checkbox" ${state.selectedIds.has(article.id) ? 'checked' : ''}>
      <div class="article-title">${escapeHtml(article.title)}</div>
    </div>
    <div class="article-meta">
      <span class="source-badge">${escapeHtml(article.source || '')}</span>
      ${article.score != null ? `<span class="score">★ ${article.score}</span>` : ''}
      <span class="status-badge status-${article.status || 'draft'}">${article.status || 'draft'}</span>
      ${catStr ? `<span class="source-badge">${escapeHtml(catStr)}</span>` : ''}
      <span>${formatDate(article.updated_at)}</span>
    </div>
    <div class="article-summary">${escapeHtml(article.summary || '')}</div>
    <div class="article-tags">
      ${(article.tags || []).map(t => `<span class="tag" data-tag="${escapeHtml(t)}">${escapeHtml(t)}</span>`).join('')}
    </div>
    <div class="card-actions">
      <button class="quick-edit" title="编辑标签">🏷</button>
      <button class="quick-cat" title="编辑分类">📂</button>
      <button class="quick-status" title="编辑状态">⚡</button>
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

  div.querySelector('.quick-edit').addEventListener('click', (e) => {
    e.stopPropagation();
    const value = prompt('编辑标签（逗号分隔）:', (article.tags || []).join(', '));
    if (value === null) return;
    const tags = value.split(',').map(s => s.trim()).filter(Boolean);
    patchArticle(article.id, { tags }).then(() => loadData());
  });

  div.querySelector('.quick-cat').addEventListener('click', (e) => {
    e.stopPropagation();
    const value = prompt('编辑分类:', article.category || '');
    if (value === null) return;
    patchArticle(article.id, { category: value.trim() }).then(() => loadData());
  });

  div.querySelector('.quick-status').addEventListener('click', (e) => {
    e.stopPropagation();
    const value = prompt('编辑状态 (draft/review/published/archived):', article.status || 'draft');
    if (value === null) return;
    patchArticle(article.id, { status: value.trim() }).then(() => loadData());
  });

  return div;
}

function renderPagination(data) {
  const container = document.getElementById('pagination');
  container.innerHTML = '';
  state.totalPages = data.pages || 1;
  const prev = document.createElement('button');
  prev.textContent = '上一页';
  prev.disabled = data.page <= 1;
  prev.addEventListener('click', () => { state.page--; loadData(); });
  container.appendChild(prev);
  const info = document.createElement('span');
  info.className = 'page-info';
  info.textContent = `第 ${data.page || 1} / ${data.pages || 1} 页`;
  container.appendChild(info);
  const next = document.createElement('button');
  next.textContent = '下一页';
  next.disabled = data.page >= data.pages;
  next.addEventListener('click', () => { state.page++; loadData(); });
  container.appendChild(next);
}

/* Drawer */
function openDrawer(article) {
  const drawer = document.getElementById('drawer');
  const body = document.getElementById('drawer-body');
  const categories = article.categories || [];
  const catStr = categories.length > 0 ? categories.join(' | ') : '';

  body.innerHTML = `
    <div class="drawer-title">${escapeHtml(article.title)}</div>
    <div class="drawer-meta">
      <span class="source-badge">${escapeHtml(article.source || '')}</span>
      <span class="status-badge status-${article.status || 'draft'}">${article.status || 'draft'}</span>
      ${article.score != null ? `<span class="score">★ ${article.score}</span>` : ''}
      ${catStr ? `<span class="source-badge">${escapeHtml(catStr)}</span>` : ''}
      <span>${formatDate(article.updated_at)}</span>
    </div>
    <div class="drawer-section"><h3>摘要</h3><div class="drawer-summary">${escapeHtml(article.summary || '')}</div></div>
    ${article.key_insight ? `<div class="drawer-section"><h3>核心洞察</h3><div class="drawer-insight">${escapeHtml(article.key_insight)}</div></div>` : ''}
    <div class="drawer-section"><h3>标签</h3><div class="drawer-tags">${(article.tags || []).map(t => `<span class="tag">${escapeHtml(t)}</span>`).join('')}</div></div>
    <div class="drawer-section"><h3>链接</h3><a href="${article.source_url}" target="_blank" class="drawer-link">${escapeHtml(article.source_url || '')}</a></div>
    ${article.author ? `<div class="drawer-section"><h3>作者</h3><div class="drawer-summary">${escapeHtml(article.author)}</div></div>` : ''}
    ${article.published_at ? `<div class="drawer-section"><h3>发布时间</h3><div class="drawer-summary">${formatDate(article.published_at)}</div></div>` : ''}
  `;

  drawer.classList.add('open');
  state.drawerOpen = true;
}

function closeDrawer() {
  document.getElementById('drawer').classList.remove('open');
  state.drawerOpen = false;
}

/* Batch Bar */
function updateBatchBar() {
  const bar = document.getElementById('batch-bar');
  const count = document.getElementById('batch-count');
  if (state.selectedIds.size > 0) {
    bar.classList.add('visible');
    count.textContent = `已选中 ${state.selectedIds.size} 项`;
  } else {
    bar.classList.remove('visible');
  }
}

function clearSelection() {
  state.selectedIds.clear();
  updateBatchBar();
  loadData();
}

async function doExport() {
  const ids = Array.from(state.selectedIds);
  if (!ids.length) { alert('请先选择条目'); return; }
  const data = await exportArticles(ids);
  const blob = new Blob([JSON.stringify(data.articles, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `kb-export-${new Date().toISOString().slice(0,10)}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

async function doImport(file) {
  const text = await file.text();
  let data;
  try { data = JSON.parse(text); } catch { alert('JSON 格式错误'); return; }
  const articles = Array.isArray(data) ? data : (data.articles || []);
  if (!articles.length) { alert('文件中未找到条目'); return; }
  const result = await importArticles(articles);
  alert(`导入完成: ${result.imported} 成功, ${result.skipped} 跳过`);
  loadData();
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
    document.getElementById('articles-list').innerHTML = `<div style="text-align:center;color:#c00;padding:40px;">加载失败: ${escapeHtml(err.message)}</div>`;
  }
}

/* Utilities */
function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
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
      const card = cards[state.focusIndex];
      const cb = card.querySelector('.article-checkbox');
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

/* Event Bindings */
function init() {
  // Theme
  applyTheme();
  document.getElementById('theme-toggle').addEventListener('click', toggleTheme);

  // Date filters
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

  // Search
  document.getElementById('search-input').addEventListener('input', (e) => {
    state.filters.q = e.target.value;
    state.page = 1;
    loadData();
  });

  document.getElementById('sort-select').addEventListener('change', (e) => {
    state.sort = e.target.value;
    loadData();
  });

  // Export / Import
  document.getElementById('export-btn').addEventListener('click', doExport);
  document.getElementById('import-btn').addEventListener('click', () => {
    document.getElementById('import-file').click();
  });
  document.getElementById('import-file').addEventListener('change', (e) => {
    if (e.target.files[0]) doImport(e.target.files[0]);
  });

  // Keyboard shortcuts
  document.addEventListener('keydown', handleKey);

  document.getElementById('refresh-btn').addEventListener('click', () => loadData());
  document.getElementById('drawer-close').addEventListener('click', closeDrawer);

  document.getElementById('batch-clear').addEventListener('click', clearSelection);

  document.getElementById('batch-archive').addEventListener('click', async () => {
    const ids = Array.from(state.selectedIds);
    if (!ids.length) return;
    await batchAction('archive', ids);
    clearSelection();
  });

  document.getElementById('batch-delete').addEventListener('click', async () => {
    const ids = Array.from(state.selectedIds);
    if (!ids.length || !confirm(`确定删除 ${ids.length} 项？`)) return;
    await batchAction('delete', ids);
    clearSelection();
  });

  document.getElementById('batch-tag-select').addEventListener('change', async (e) => {
    const tag = e.target.value;
    if (!tag) return;
    const ids = Array.from(state.selectedIds);
    if (!ids.length) return;
    await batchAction('tag', ids, { tags: [tag] });
    e.target.value = '';
    clearSelection();
  });

  document.getElementById('batch-untag-select').addEventListener('change', async (e) => {
    const tag = e.target.value;
    if (!tag) return;
    const ids = Array.from(state.selectedIds);
    if (!ids.length) return;
    await batchAction('untag', ids, { tags: [tag] });
    e.target.value = '';
    clearSelection();
  });

  document.getElementById('batch-cat-select').addEventListener('change', async (e) => {
    const cat = e.target.value;
    if (!cat) return;
    const ids = Array.from(state.selectedIds);
    if (!ids.length) return;
    await batchAction('category', ids, { category: cat });
    e.target.value = '';
    clearSelection();
  });

  document.getElementById('batch-status-select').addEventListener('change', async (e) => {
    const st = e.target.value;
    if (!st) return;
    const ids = Array.from(state.selectedIds);
    if (!ids.length) return;
    await batchAction('status', ids, { status: st });
    e.target.value = '';
    clearSelection();
  });

  loadData();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
