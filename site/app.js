'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const data = window.TECH_DATA;
  if (!data || !Array.isArray(data.editions) || !Array.isArray(data.discoveries)) {
    $('health-label').textContent = '精选数据暂时无法读取';
    $('empty').hidden = false; $('empty-title').textContent = '请稍后再看';
    $('empty-message').textContent = '不会用原始订阅标题填充尚未完成的精选。'; return;
  }
  const names = {ai:'AI',hardware:'硬件',software:'软件'};
  const editions = data.editions.filter(e => e.status === 'published').sort((a,b) => b.date.localeCompare(a.date));
  const latest = editions[0];
  const state = {collection:'news',edition:latest?.date || '',category:'all',search:'',saved:false,limit:18};
  let bookmarks=new Set(),storageAvailable=true,toastTimer;
  try {const saved=JSON.parse(localStorage.getItem('tech-discovery:saved') || '[]');if(Array.isArray(saved)) bookmarks=new Set(saved.filter(x=>typeof x==='string'));}catch{storageAvailable=false;}
  const create=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;};
  const url=value=>{try{const u=new URL(value);return ['http:','https:'].includes(u.protocol)?u.href:null;}catch{return null;}};
  const date=(value,time=false)=>{if(!value)return '尚无记录';if(!time && /^\d{4}-\d{2}-\d{2}$/.test(value))return value.replaceAll('-','/');const d=new Date(value);if(Number.isNaN(d.valueOf()))return '时间未知';return new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit',...(time?{hour:'2-digit',minute:'2-digit'}:{})}).format(d)+(time?' 北京时间':'');};
  const today=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
  const arrow=()=>{const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 20 20');svg.setAttribute('class','out-arrow');svg.setAttribute('aria-hidden','true');const p=document.createElementNS('http://www.w3.org/2000/svg','path');p.setAttribute('d','M4 16 16 4M5 4h11v11');svg.append(p);return svg;};
  const external=(href,label,cls)=>{const a=create('a',cls,label);a.href=url(href)||'#';a.target='_blank';a.rel='noopener noreferrer';a.append(arrow());return a;};
  const toast=message=>{$('toast').textContent=message;$('toast').classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').classList.remove('show'),2800);};
  function persist(){try{localStorage.setItem('tech-discovery:saved',JSON.stringify([...bookmarks]));storageAvailable=true;}catch{storageAvailable=false;}}
  $('discovery-count').textContent=String(data.discoveries.length);
  $('news-count').textContent=String(latest?.items.length || 0);
  $('health-label').textContent=latest?(latest.date===today?`${date(latest.date)} 精选已发布`:`最新一期：${date(latest.date)}，今日尚未发布新一期`):'精选尚未发布';
  $('health-dot').className='health-dot '+(latest?.date===today?'':'pending');
  $('last-updated').textContent=latest?`本期编辑发布于 ${date(latest.published_at,true)}`:'只展示经过原文核对的中文摘要';
  $('build-time').textContent=`页面生成于 ${date(data.built_at,true)}，不等于新增精选`;
  for(const edition of editions){const option=create('option','',`${date(edition.date)} · ${edition.items.length} 条`);option.value=edition.date;$('edition').append(option);}
  $('edition').value=state.edition;$('edition').disabled=!editions.length;
  const sources=Array.isArray(data.sources)?data.sources:[];
  $('source-summary').textContent=`候选抓取：${sources.filter(s=>s.state==='ok').length} / ${sources.length} 来源最近成功。抓取成功不代表已经完成编辑。`;
  for(const source of sources){const row=create('div','source-row');const info=create('div');info.append(external(source.homepage,source.name),create('small','',`${names[source.category]||source.category} · ${source.kind}`));const status=create('div','source-state '+source.state);status.append(create('span','',source.state==='ok'?'候选抓取成功':source.state==='error'?'抓取异常，保留旧候选':'尚未抓取'),create('small','',`成功时间：${date(source.last_success_at,true)}`));row.append(info,status);$('source-list').append(row);}
  function storyCard(item,index){
    const article=create('article','digest-card');article.id=item.id;
    const number=create('div','story-number',String(index+1).padStart(2,'0'));number.setAttribute('aria-hidden','true');
    const body=create('div','story-body'),top=create('div','story-top');top.append(create('span',`category category-${item.category}`,names[item.category]||'科技'),create('span','story-source',item.source_name));
    body.append(top,create('h3','',item.title_zh));
    for(const [label,text,cls] of [['发生了什么',item.what_zh,'story-block'],['为什么值得看 · 编辑判断',item.why_zh,'story-block story-why']]){const block=create('div',cls);block.append(create('strong','',label),create('p','',text));body.append(block);}
    if(item.caveat_zh)body.append(create('p','story-caveat',`核对说明：${item.caveat_zh}`));
    const bottom=create('div','story-bottom');bottom.append(create('div','story-dates',`原文发布 ${date(item.source_published_at)} · 原文核对 ${date(item.checked_at)}`),external(item.url,item.source_language==='zh'?'阅读中文原文':'阅读英文原文','original-link'));body.append(bottom,create('p','story-original-title',item.original_title));article.append(number,body);return article;
  }
  function discoveryCard(item){
    const card=create('article','card card-discovery'),top=create('div','card-top');top.append(create('span',`category category-${item.category}`,names[item.category]||'其他'));
    const save=create('button','save-card',bookmarks.has(item.id)?'★':'☆');save.type='button';save.setAttribute('aria-label',(bookmarks.has(item.id)?'取消收藏：':'收藏：')+item.title);save.setAttribute('aria-pressed',String(bookmarks.has(item.id)));
    save.addEventListener('click',()=>{const adding=!bookmarks.has(item.id);if(adding)bookmarks.add(item.id);else bookmarks.delete(item.id);persist();render();toast(storageAvailable?(adding?'已收藏，仅保存在当前浏览器':'已取消收藏'):'浏览器不允许保存，收藏仅在本次页面有效');});
    const h3=create('h3');h3.append(external(item.url,item.title));card.append(top,save,h3);
    if(item.note)card.append(create('p','card-note',item.note));if(item.use_case)card.append(create('p','card-use',item.use_case));
    const bottom=create('div','card-bottom'),meta=create('div');meta.append(create('div','card-source',item.source_name||'官方项目'),create('div','card-date',`收录 ${date(item.added_at)} · 核对 ${date(item.verified_at)}`));bottom.append(meta,external(item.url,'查看项目','original-link'));card.append(bottom);return card;
  }
  function render(){
    const discovery=state.collection==='discoveries';
    $('search-wrap').hidden=!discovery;$('discovery-filters').hidden=!discovery;$('edition-wrap').hidden=discovery;
    $('cards').className=discovery?'cards':'cards news-list';$('load-more').hidden=true;$('clear-filters').hidden=true;
    $('section-kicker').textContent=discovery?'TIMELESS FINDS':'THE DAILY EDIT';
    $('collection-title').textContent=discovery?'不一定新，但值得发现':state.edition?`${date(state.edition)} 科技小报`:'这一期，值得看什么';
    if(!discovery){
      const edition=editions.find(e=>e.date===state.edition);
      // Defense in depth: even a malformed static payload cannot create a firehose.
      const items=(edition?.items||[]).filter(i=>i.review_status==='reviewed'&&i.title_zh&&i.what_zh&&i.why_zh&&url(i.url)).slice(0,5);
      $('section-description').textContent=edition?.editor_note||'每天最多五条，先核对原文，再写中文摘要。没有完成编辑的新一期时不会自动补标题。';
      const chars=items.reduce((n,i)=>n+i.what_zh.length+i.why_zh.length,0);
      $('result-count').textContent=items.length?`${items.length} 条精选 · 约 ${Math.max(1,Math.ceil(chars/350))} 分钟`:'本期暂无精选';
      $('sort-note').textContent='中文摘要 · 附原文';$('news-count').textContent=String(items.length);
      $('cards').replaceChildren(...items.map(storyCard));$('empty').hidden=items.length>0;
      $('empty-title').textContent='这期还在等待核对';$('empty-message').textContent='这里只发布选好的中文摘要。自动抓到的原始标题不会直接进入首页；也不会把旧消息标成今天的新消息。';
      $('collection-footnote').textContent='原文日期与本期编辑发布时间分别标注。“为什么值得看”是编辑判断，厂商测试与效果也不代表独立验证。';
      return;
    }
    $('section-description').textContent='值得长期收藏的工具、项目和灵感，与每日新闻分开。';$('sort-note').textContent='按收录时间排列';
    let items=data.discoveries.filter(i=>url(i.url));
    if(state.category!=='all')items=items.filter(i=>i.category===state.category);
    if(state.saved)items=items.filter(i=>bookmarks.has(i.id));
    if(state.search)items=items.filter(i=>[i.title,i.note,i.use_case,i.source_name].filter(Boolean).join(' ').toLocaleLowerCase().includes(state.search));
    items.sort((a,b)=>(b.added_at||'').localeCompare(a.added_at||''));
    $('cards').replaceChildren(...items.slice(0,state.limit).map(discoveryCard));$('result-count').textContent=`${items.length} 条常青发现${state.saved?' · 已收藏':''}`;$('empty').hidden=items.length>0;$('load-more').hidden=items.length<=state.limit;
    const filtered=state.search||state.category!=='all'||state.saved;$('clear-filters').hidden=!filtered;
    $('empty-title').textContent=filtered?'还没有匹配的内容':'好发现，正在等待收录';$('empty-message').textContent=filtered?'试试其他关键词或分类。收藏只保存在当前浏览器。':'不凑数量，遇到值得分享的项目再收录。';
    $('collection-footnote').textContent='常青发现按需收录。核对时间不等于新品发布日期，功能与价格以项目官网为准。';
  }
  document.querySelectorAll('[data-collection]').forEach(button=>button.addEventListener('click',()=>{state.collection=button.dataset.collection;document.querySelectorAll('[data-collection]').forEach(b=>{b.classList.toggle('active',b===button);b.setAttribute('aria-pressed',String(b===button));});render();}));
  document.querySelectorAll('[data-category]').forEach(button=>button.addEventListener('click',()=>{state.category=button.dataset.category;state.limit=18;document.querySelectorAll('[data-category]').forEach(b=>{b.classList.toggle('active',b===button);b.setAttribute('aria-pressed',String(b===button));});render();}));
  $('edition').addEventListener('change',e=>{state.edition=e.target.value;render();});
  $('search').addEventListener('input',e=>{state.search=e.target.value.trim().toLocaleLowerCase();state.limit=18;render();});
  $('saved-toggle').addEventListener('click',()=>{state.saved=!state.saved;$('saved-toggle').classList.toggle('active',state.saved);$('saved-toggle').setAttribute('aria-pressed',String(state.saved));render();});
  $('clear-filters').addEventListener('click',()=>{state.search='';state.category='all';state.saved=false;$('search').value='';$('saved-toggle').classList.remove('active');$('saved-toggle').setAttribute('aria-pressed','false');document.querySelectorAll('[data-category]').forEach(b=>{b.classList.toggle('active',b.dataset.category==='all');b.setAttribute('aria-pressed',String(b.dataset.category==='all'));});render();});
  $('load-more').addEventListener('click',()=>{state.limit+=18;render();});
  $('open-rss').addEventListener('click',()=>{$('rss-dialog').showModal();if(!data.site_url&&location.protocol==='file:')$('rss-help').textContent='本地预览尚无可订阅地址，部署后才能在线订阅。';});
  $('rss-dialog').addEventListener('click',e=>{if(e.target===$('rss-dialog')){const r=e.target.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)e.target.close();}});
  document.querySelectorAll('[data-copy]').forEach(button=>button.addEventListener('click',async()=>{if(!data.site_url&&location.protocol==='file:'){toast('请先部署，再复制订阅地址');return;}const address=new URL(button.dataset.copy,data.site_url||new URL('./',location.href).href).href;try{await navigator.clipboard.writeText(address);button.textContent='已复制';setTimeout(()=>button.textContent='复制地址',1800);}catch{$('rss-help').textContent=`请复制此地址：${address}`;}}));
  render();
})();
