'use strict';
(() => {
  const $ = (id) => document.getElementById(id);
  const data = window.TECH_DATA;
  if (!data || !Array.isArray(data.news) || !Array.isArray(data.discoveries)) {
    $('health-label').textContent = '数据文件无法读取';
    $('empty').hidden = false;
    $('empty-title').textContent = '暂时无法加载内容';
    $('empty-message').textContent = '请刷新页面，或稍后重试。已有 RSS 仍可从页脚访问。';
    return;
  }
  const names = {ai: 'AI', hardware: '硬件', software: '软件'};
  const lookback = Number.isInteger(data.lookback_days) && data.lookback_days > 0 ? data.lookback_days : 14;
  const state = {collection: 'news', category: 'all', search: '', saved: false, period: String(lookback), limit: 18};
  $('period').options[0].value = String(lookback);
  $('period').options[0].textContent = `最近 ${lookback} 天`;
  $('period').value = String(lookback);
  let bookmarks = new Set();
  let storageAvailable = true;
  try { const stored = JSON.parse(localStorage.getItem('tech-discovery:saved') || '[]'); if (Array.isArray(stored)) bookmarks = new Set(stored.filter(x => typeof x === 'string')); }
  catch { storageAvailable = false; }
  const create = (tag, cls, text) => { const node = document.createElement(tag); if (cls) node.className = cls; if (text !== undefined) node.textContent = text; return node; };
  const validURL = (value) => { try { const u = new URL(value); return ['http:', 'https:'].includes(u.protocol) ? u.href : null; } catch { return null; } };
  const date = (value, time = false) => {
    if (!value) return '尚无记录';
    if (!time && /^\d{4}-\d{2}-\d{2}$/.test(value)) return value.replaceAll('-', '/');
    const d = new Date(value);
    if (Number.isNaN(d.valueOf())) return '时间未知';
    return new Intl.DateTimeFormat('zh-CN', {year: 'numeric', month: '2-digit', day: '2-digit', ...(time ? {hour:'2-digit',minute:'2-digit',timeZoneName:'short'} : {})}).format(d);
  };
  let toastTimer;
  const toast = (message) => { $('toast').textContent = message; $('toast').classList.add('show'); clearTimeout(toastTimer); toastTimer = setTimeout(() => $('toast').classList.remove('show'), 2800); };
  const external = (url, label, cls) => { const a = create('a', cls, label.replaceAll('↗', '').trim()); if (label.includes('↗')) { const svg = document.createElementNS('http://www.w3.org/2000/svg','svg'); svg.setAttribute('viewBox','0 0 20 20'); svg.setAttribute('class','out-arrow'); svg.setAttribute('aria-hidden','true'); const path = document.createElementNS('http://www.w3.org/2000/svg','path'); path.setAttribute('d','M4 16 16 4M5 4h11v11'); svg.append(path); a.append(svg); } a.href = validURL(url) || '#'; a.target = '_blank'; a.rel = 'noopener noreferrer'; return a; };
  const agoHours = (value) => value ? (Date.now() - new Date(value).valueOf()) / 3600000 : Infinity;
  const sources = Array.isArray(data.sources) ? data.sources : [];
  const healthy = sources.filter(s => s.state === 'ok').length;
  const failed = sources.filter(s => s.state === 'error').length;
  const neverRun = !data.attempted_at;
  const stale = agoHours(data.attempted_at) > 30;
  $('news-count').textContent = String(data.news.length);
  $('discovery-count').textContent = String(data.discoveries.length);
  $('health-label').textContent = neverRun ? '尚未运行自动抓取' : failed ? `${failed} 个来源抓取异常，保留已有内容` : stale ? '更新较久，可能已暂停' : `${healthy} 个来源最近抓取成功`;
  $('health-dot').className = 'health-dot ' + (neverRun ? 'pending' : failed || stale ? 'error' : '');
  $('last-updated').textContent = data.last_success_at ? `最近成功抓取 ${date(data.last_success_at, true)}` : '当前没有成功抓取记录';
  $('source-summary').textContent = `${healthy} / ${sources.length} 来源最近成功`;
  $('build-time').textContent = `页面生成于 ${date(data.built_at, true)}`;
  for (const source of sources) {
    const row = create('div', 'source-row');
    const info = create('div');
    info.append(external(source.homepage, source.name + ' ↗'));
    info.append(create('small', '', `${names[source.category] || source.category} · ${source.kind}`));
    const status = create('div', 'source-state ' + source.state);
    status.append(create('span', '', source.state === 'ok' ? '抓取成功' : source.state === 'error' ? `异常 · ${source.error || '连接失败'}` : '尚未运行'));
    status.append(create('small', '', `成功时间：${date(source.last_success_at, true)}`));
    if (source.state === 'error') status.append(create('small', '', `保留 ${source.item_count || 0} 条 · 连续失败 ${source.consecutive_failures || 1} 次`));
    row.append(info, status); $('source-list').append(row);
  }
  function persist() {
    try { localStorage.setItem('tech-discovery:saved', JSON.stringify([...bookmarks])); storageAvailable = true; }
    catch { storageAvailable = false; }
  }
  function renderCard(item) {
    const discovery = state.collection === 'discoveries';
    const card = create('article', 'card' + (discovery ? ' card-discovery' : ''));
    const top = create('div', 'card-top');
    top.append(create('span', `category category-${item.category}`, names[item.category] || '其他'));
    const save = create('button', 'save-card', bookmarks.has(item.id) ? '★' : '☆');
    save.type = 'button'; save.setAttribute('aria-label', (bookmarks.has(item.id) ? '取消收藏：' : '收藏：') + item.title); save.setAttribute('aria-pressed', String(bookmarks.has(item.id)));
    save.addEventListener('click', () => {
      const adding = !bookmarks.has(item.id);
      if (adding) bookmarks.add(item.id); else bookmarks.delete(item.id);
      persist();
      if (state.saved && !adding) render();
      else { save.textContent = adding ? '★' : '☆'; save.setAttribute('aria-pressed', String(adding)); save.setAttribute('aria-label', (adding ? '取消收藏：' : '收藏：') + item.title); }
      toast(storageAvailable ? (adding ? '已收藏，仅保存在当前浏览器' : '已取消收藏') : '浏览器不允许保存，收藏仅在本次页面中有效');
    });
    const h3 = create('h3'); h3.append(external(item.url, item.title));
    card.append(top, save, h3);
    if (item.note) card.append(create('p', 'card-note', item.note));
    if (discovery && item.use_case) card.append(create('p', 'card-use', item.use_case));
    const bottom = create('div', 'card-bottom'); const meta = create('div');
    meta.append(create('div', 'card-source', discovery ? (item.source_name || '官方项目') : (item.sources || []).map(s => s.name).join(' / ')));
    meta.append(create('div', 'card-date', discovery ? `收录 ${date(item.added_at)} · 核对 ${date(item.verified_at)}` : item.published_at ? `原文发布 ${date(item.published_at, true)}` : `原文时间未注明 · 首次发现 ${date(item.first_seen_at)}`));
    const link = external(item.url, '↗', 'card-link'); link.setAttribute('aria-label', '查看原文：' + item.title); bottom.append(meta, link); card.append(bottom);
    return card;
  }
  function render() {
    const discovery = state.collection === 'discoveries';
    $('section-kicker').textContent = discovery ? 'TIMELESS FINDS' : 'THE LATEST';
    $('collection-title').textContent = discovery ? '不一定新，但值得发现' : '最近发生了什么';
    $('section-description').textContent = discovery ? '工具、项目和灵感。按收录时间排列，与原始发布日期无关。' : `原文标题，直接回到来源。默认展示最近 ${lookback} 天有明确发布时间的条目。`;
    $('period-wrap').hidden = discovery;
    $('sort-note').textContent = discovery ? '按收录时间排列' : state.period === 'all' ? '发布时间缺失的条目置后' : '按原文发布时间排列';
    $('collection-footnote').textContent = discovery ? '常青发现由人工收录，按需补充，不会由新闻自动冒充。核对日期不等于新品发布日期，功能与价格请以项目官网为准。' : '内容通过 RSS 自动收录，不代表独立核验或推荐。规则去重与分类可能遗漏或误判，请以原文为准。';
    let items = [...data[state.collection]].filter(i => validURL(i.url));
    const allCount = items.length;
    const cutoff = Date.now() - Number(state.period) * 86400000;
    if (!discovery && state.period !== 'all') items = items.filter(i => i.published_at && new Date(i.published_at).valueOf() >= cutoff && new Date(i.published_at).valueOf() <= Date.now() + 86400000);
    if (state.category !== 'all') items = items.filter(i => i.category === state.category);
    if (state.saved) items = items.filter(i => bookmarks.has(i.id));
    if (state.search) items = items.filter(i => [i.title, i.note, i.use_case, i.source_name, ...(i.sources || []).map(s => s.name)].filter(Boolean).join(' ').toLocaleLowerCase().includes(state.search));
    items.sort((a,b) => (discovery ? b.added_at || '' : b.published_at || '').localeCompare(discovery ? a.added_at || '' : a.published_at || ''));
    $('cards').replaceChildren(...items.slice(0, state.limit).map(renderCard));
    $('result-count').textContent = `${items.length} 条${discovery ? '发现' : '动态'}${state.saved ? ' · 已收藏' : ''}`;
    $('empty').hidden = items.length > 0;
    $('load-more').hidden = items.length <= state.limit;
    if (!items.length) {
      const filtered = state.search || state.category !== 'all' || state.saved;
      $('clear-filters').hidden = !filtered;
      $('empty-title').textContent = filtered ? '还没有匹配的内容' : discovery ? '好发现，正在等待收录' : allCount ? '这个时间范围内暂无动态' : '还没有可用的新闻数据';
      $('empty-message').textContent = filtered ? '试试其他关键词或分类。收藏保存在本地，不会跨设备同步。' : discovery ? '这里单独收藏长期有价值的工具与项目，不会用旧新闻填充。' : allCount ? '可切换「全部缓存」查看旧条目与时间未注明的条目，也可查看来源是否抓取异常。' : neverRun ? '当前为本地预览，尚未启动自动抓取。部署并运行更新后，这里会展示真实来源的标题；现在也可以先看看常青发现。' : '本次尚未获得可用的源数据。下方会显示各来源状态；不会生成或补造新闻。';
    }
  }
  document.querySelectorAll('[data-collection]').forEach(button => button.addEventListener('click', () => {
    state.collection = button.dataset.collection; state.limit = 18;
    document.querySelectorAll('[data-collection]').forEach(b => { b.classList.toggle('active', b === button); b.setAttribute('aria-pressed', String(b === button)); }); render();
  }));
  document.querySelectorAll('[data-category]').forEach(button => button.addEventListener('click', () => {
    state.category = button.dataset.category; state.limit = 18;
    document.querySelectorAll('[data-category]').forEach(b => { b.classList.toggle('active', b === button); b.setAttribute('aria-pressed', String(b === button)); }); render();
  }));
  $('search').addEventListener('input', e => { state.search = e.target.value.trim().toLocaleLowerCase(); state.limit = 18; render(); });
  $('period').addEventListener('change', e => { state.period = e.target.value; state.limit = 18; render(); });
  $('saved-toggle').addEventListener('click', () => { state.saved = !state.saved; $('saved-toggle').classList.toggle('active', state.saved); $('saved-toggle').setAttribute('aria-pressed', String(state.saved)); state.limit = 18; render(); });
  $('clear-filters').addEventListener('click', () => { state.search = ''; state.category = 'all'; state.saved = false; $('search').value = ''; $('saved-toggle').classList.remove('active'); $('saved-toggle').setAttribute('aria-pressed', 'false'); document.querySelectorAll('[data-category]').forEach(b => { b.classList.toggle('active', b.dataset.category === 'all'); b.setAttribute('aria-pressed', String(b.dataset.category === 'all')); }); render(); });
  $('load-more').addEventListener('click', () => { state.limit += 18; render(); });
  $('open-rss').addEventListener('click', () => { $('rss-dialog').showModal(); if (!data.site_url && location.protocol === 'file:') $('rss-help').textContent = '当前是本地预览。部署后，本站地址下的 rss.xml 和 discoveries.xml 才能被在线阅读器订阅。'; });
  $('rss-dialog').addEventListener('click', e => { if (e.target === $('rss-dialog')) { const rect = e.target.getBoundingClientRect(); if (e.clientX < rect.left || e.clientX > rect.right || e.clientY < rect.top || e.clientY > rect.bottom) e.target.close(); } });
  document.querySelectorAll('[data-copy]').forEach(button => button.addEventListener('click', async () => {
    if (!data.site_url && location.protocol === 'file:') { toast('本地预览尚无可订阅网址，请先部署'); return; }
    const base = data.site_url || new URL('./', location.href).href;
    const url = new URL(button.dataset.copy, base).href;
    try { await navigator.clipboard.writeText(url); button.textContent = '已复制'; setTimeout(() => button.textContent = '复制地址', 1800); }
    catch { $('rss-help').textContent = `请复制此地址：${url}`; }
  }));
  render();
})();
