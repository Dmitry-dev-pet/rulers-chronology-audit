/* HPM P3. Static read-only source audit, gated by ?hpm=pilot in v2.html.
   Relation labels are observations, NOT a taxonomy of accession mechanisms.
   Never infer rulers, state borders, ethnic identity, violence or completeness. */
(() => {
  'use strict';
  const FEATURE='pilot', PARAM='hpm';
  const SOURCE_KINDS={
    succession:'Связь преемственности в источнике',
    imperial_succession:'Связь императорской преемственности',
    regime_change:'Источниковая отметка смены режима',
    institutional_change:'Источниковая отметка изменения учреждения'
  };
  const host=document.body;
  if (!host || !location.pathname.endsWith('/v2.html')) return;
  const el=(tag,cls,value)=>{
    const node=document.createElement(tag);
    if(cls)node.className=cls;
    if(value!==undefined)node.textContent=String(value);
    return node;
  };
  const btn=(text,cls,fn)=>{
    const node=el('button',cls,text);
    node.type='button';node.addEventListener('click',fn);
    return node;
  };
  const safeLink=value=>{
    try{
      const url=new URL(value);
      return url.protocol==='https:' && !!url.hostname && !url.username &&
        !url.password && url.port==='' &&
        ![['drive','.google.com'].join(''),['docs','.google.com'].join(''),'localhost'].includes(url.hostname) &&
        !/(?:\.local|\.internal|\.private|\.localhost|\.lan)$/.test(url.hostname) &&
        !/^\d+\.\d+\.\d+\.\d+$/.test(url.hostname);
    }catch(_){return false;}
  };
  const dialog=el('section','hpm-lab');
  dialog.hidden=true;
  dialog.id='hpm-lab';
  dialog.setAttribute('role','dialog');
  dialog.setAttribute('aria-modal','true');
  dialog.setAttribute('aria-label','Лаборатория переходов исторической власти');
  host.append(dialog);
  let data=null,error=null,loading=null,shown=false,lastFocus=null;
  let selected=null,year='all',context='all',linkage='all';
  let priorOverflow='',priorInert=false;
  const background=document.querySelector('main.container');
  const active=()=>new URL(location.href).searchParams.get(PARAM)===FEATURE;
  const param=(url,k,v)=>{if(v==='all')url.searchParams.delete(k);else url.searchParams.set(k,v);};
  const readFilters=()=>{
    const search=new URL(location.href).searchParams;
    const nextYear=search.get('hpmYear')||'all';
    year=nextYear==='all'||/^\d{4}$/.test(nextYear) &&
      Number(nextYear)>=1762 && Number(nextYear)<=1800?nextYear:'all';
    context=search.get('hpmCtx')||'all';
    linkage=['candidate','reviewed_linkage'].includes(search.get('hpmLink'))?
      search.get('hpmLink'):'all';
    if(data){
      const contexts=new Set(data.events.flatMap(x=>x.contexts.map(c=>c.id)));
      if(context!=='all'&&!contexts.has(context))context='all';
    }
  };
  function writeUrl(){
    const u=new URL(location.href);
    u.searchParams.set(PARAM,FEATURE);
    param(u,'hpmYear',year);param(u,'hpmCtx',context);
    param(u,'hpmLink',linkage);
    history.pushState(null,'',u.pathname+u.search+u.hash);
  }
  const sampled=()=>data.events.filter(x=>
    (year==='all'||String(x.event_year)===year) &&
    (context==='all'||x.contexts.some(c=>c.id===context)) &&
    (linkage==='all'||x.review_status===linkage));
  const chosen=(items)=>{
    if(!items.some(x=>x.id===selected))selected=items[0]?.id||null;
    return items.find(x=>x.id===selected)||null;
  };
  function fact(label,value){
    const card=el('div','hpm-fact');
    card.append(el('span','hpm-fact-label',label),el('strong',null,value));
    return card;
  }
  function sourceList(items){
    const outer=el('ul','hpm-sources');
    for(const src of items){
      const row=el('li');
      const label=[src.source_namespace,src.source_native_id].filter(Boolean).join(' / ');
      if(safeLink(src.source_url)){
        const a=el('a',null,(src.source_title||label)+' ↗');
        a.href=src.source_url;a.target='_blank';a.rel='noopener noreferrer';
        row.append(a);
      }else row.append(el('span',null,'Недоступный URL источника'));
      row.append(el('small',null,label+' · '+(src.pinpoint||'точка цитирования не указана')));
      outer.append(row);
    }
    return outer;
  }
  function details(item){
    const panel=el('article','hpm-detail');
    panel.id='hpm-detail';panel.setAttribute('aria-label','Исходные свидетельства');
    if(!item){
      panel.append(el('h3',null,'Записей по фильтрам нет'),
        el('p',null,'В этом ограниченном наборе не найдено источниковых событий. Это не означает отсутствия передачи власти в истории.'));
      return panel;
    }
    panel.append(el('div','hpm-kicker',item.event_year+' · '+SOURCE_KINDS[item.kind]),
      el('h3',null,item.title),
      el('p','hpm-detail-intro',item.note||'Описание не представлено в исходной связи.'));
    const ctx=el('div','hpm-evidence-block');
    ctx.append(el('h4',null,'Пространство и контекст'),
      el('p',null,item.contexts.length?
        item.contexts.map(c=>c.label+' ('+c.kind+')').join(' · '):
        'Для этой связи отдельный политический контекст не закреплён; территориальный вывод невозможен.'));
    panel.append(ctx);
    const claim=el('div','hpm-evidence-block');
    claim.append(el('h4',null,'Источниковое утверждение'),
      el('p',null,item.assertion.statement),
      el('p','hpm-muted',item.assertion.caveat||'Дополнительной оговорки нет.'),
      el('small',null,'Assertion: '+item.assertion.id+' · '+item.assertion.category+
        ' · '+item.assertion.verification));
    claim.append(sourceList(item.sources));panel.append(claim);
    const roles=el('div','hpm-evidence-block');
    roles.append(el('h4',null,'Юридические роли и направления связи'));
    if(item.roles.length===0){
      roles.append(el('p','hpm-muted',
        'Привязка исходящей и входящей ролей пока не исследована на уровне идентификаторов. Преемник не реконструируется автоматически.'));
    } else {
      for(const role of item.roles){
        const entry=el('div','hpm-role');
        entry.append(el('strong',null,
          (role.direction==='outgoing'?'Исходящая роль: ':'Входящая роль: ')+role.actor_label),
          el('p',null,role.title+' · '+role.role_kind+' · '+role.context_label),
          el('small',null,role.role_id+' · '+role.review_dimension),
          el('p','hpm-muted',role.caveat));
        entry.append(sourceList(role.sources));roles.append(entry);
      }
    }
    panel.append(roles);
    const trace=el('div','hpm-evidence-block');
    trace.append(el('h4',null,'Путь к исходной записи'),
      el('p',null,'Кандидат '+item.id+' → relation '+item.relation_id+
        ' → assertion '+item.assertion.id+' → атрибутированные источники.'));
    for(const original of item.raw_observations){
      trace.append(el('small','hpm-raw',
        original.origin+' / '+original.native_id+' · '+original.dataset+
        ' · SHA-256: '+original.raw_sha256));
    }
    panel.append(trace);
    const caution=el('p','hpm-warning',
      'Способ вступления: UNKNOWN. Проверена только связь идентификаторов там, где она указана; характер передачи, насилие и фактический контроль не установлены.');
    panel.append(caution);
    const link=el('a','hpm-graph-link','Открыть исходные связи в графе ↗');
    const u=new URL(location.href);
    for(const p of ['hpm','hpmYear','hpmCtx','hpmLink','atlasV2','v2Links','v2Year'])
      u.searchParams.delete(p);
    u.searchParams.set('atlasV2','graph');
    u.searchParams.set('v2Year',String(item.event_year));
    u.searchParams.set('v2Links',item.kind);
    link.href=u.pathname+u.search+'#/timeline/1762';
    panel.append(link);
    return panel;
  }
  function makeChoice(title,values,actual,fn){
    const label=el('label','hpm-filter-label',title);
    const select=el('select','hpm-filter');
    for(const [v,name] of values){
      const option=el('option',null,name);option.value=v;
      if(v===actual)option.selected=true;
      select.append(option);
    }
    select.addEventListener('change',()=>{
      fn(select.value);selected=null;writeUrl();render();
    });
    label.append(select);return label;
  }
  function render(){
    if(!shown)return;
    dialog.replaceChildren();
    const header=el('header','hpm-header');
    const brand=el('div');
    brand.append(el('div','hpm-kicker','АТЛАС ВЛАСТИ · ИССЛЕДОВАТЕЛЬСКИЙ ПИЛОТ'),
      el('h2',null,'Как менялась власть?'),
      el('p',null,'Время → политический контекст → тип исходной связи → документ. Это не статистика всех европейских правителей.'));
    header.append(brand,btn('Закрыть ×','hpm-close',close));
    dialog.append(header);
    if(!data){
      dialog.append(el('p','hpm-loading',error?
        'Не удалось загрузить исследовательскую выборку: '+error:
        'Загрузка источниковой выборки…'));
      return;
    }
    const events=sampled();
    const N=events.length,unknown=events.filter(x=>x.accession_mechanism==='unknown').length;
    const linked=events.filter(x=>x.review_status==='reviewed_linkage').length;
    const filters=el('div','hpm-filters');
    const years=[['all','Все годы пилота, 1762–1800']];
    for(let y=1762;y<=1800;y++)years.push([String(y),String(y)]);
    const contexts=[['all','Все изученные контексты']];
    const ctxMap=new Map();
    for(const e of data.events)for(const c of e.contexts)ctxMap.set(c.id,c.label);
    for(const [key,name] of [...ctxMap].sort((a,b)=>a[1].localeCompare(b[1],'ru')))
      contexts.push([key,name]);
    filters.append(makeChoice('Год',years,year,v=>year=v),
      makeChoice('Исторический контекст',contexts,context,v=>context=v),
      makeChoice('Степень привязки ролей',[
        ['all','Все кандидаты'],['reviewed_linkage','Есть сверка role ID'],
        ['candidate','Связка ролей ещё не исследована']],linkage,v=>linkage=v));
    dialog.append(filters);
    const summary=el('div','hpm-summary');
    summary.append(fact('Записей в выбранном источниковом срезе',N),
      fact('Role ID сопоставлены',linked+' / '+N),
      fact('Способ вступления неизвестен',unknown+' / '+N));
    dialog.append(summary);
    const warning=el('p','hpm-warning');
    warning.textContent='Наблюдение — источниковое событие-связь (не человек и не полное правление). '+
      'Европа за 1000 лет НЕ исследована целиком. Нулевой результат не доказывает отсутствия исторических событий. '+
      'Классифицированные механизмы: 0 из '+N+'. Доля неизвестных не скрывается.';
    dialog.append(warning);
    const relation=el('div','hpm-kinds');
    relation.append(el('h3',null,'Типы исходных связей · не способы прихода к власти'));
    for(const [kind,label] of Object.entries(SOURCE_KIN)){
      const count=events.filter(x=>x.kind===kind).length;
      const item=el('div','hpm-kind');
      item.append(el('span',null,label),el('strong',null,count+' / '+N));
      const track=el('div','hpm-bar');
      const fill=el('div','hpm-bar-fill');
      fill.style.width=N?String(count/N*100)+'%':'0%';
      track.append(fill);item.append(track);relation.append(item);
    }
    dialog.append(relation);
    const work=el('div','hpm-work');
    const column=el('section','hpm-event-list');
    column.setAttribute('aria-label','Источниковые события по годам');
    column.append(el('h3',null,'Время и зафиксированные связи'));
    if(!N)column.append(el('p',null,'Нет событий в исследованном срезе.'));
    const now=chosen(events);
    for(const item of events){
      const caption=item.event_year+' · '+item.title;
      const control=btn(caption,'hpm-event',()=>{
        selected=item.id;render();
        const target=dialog.querySelector('.hpm-detail');
        if(target)target.scrollIntoView({behavior:'auto',block:'nearest'});
      });
      control.dataset.eventId=item.id;
      control.setAttribute('aria-pressed',String(now?.id===item.id));
      const hint=el('small',null,item.contexts.map(c=>c.label).join(' / ')||
        'Контекст не закреплён');
      control.append(hint);
      column.append(control);
    }
    work.append(column,details(now));
    dialog.append(work,
      el('footer','hpm-footer',
        'Публичные источники могут расходиться. Техническая проверка JSON/SQL/CI не подтверждает исторической достоверности. Оригинал плаката и приватный Google Drive сюда не импортируются.'));
  }
  function show(){
    if(shown)return;
    lastFocus=document.activeElement;
    shown=true;priorOverflow=document.body.style.overflow;
    priorInert=!!background?.inert;
    if(background)background.inert=true;
    document.body.style.overflow='hidden';
    dialog.hidden=false;readFilters();render();
    dialog.querySelector('.hpm-close')?.focus({preventScroll:true});
  }
  function hide(){
    if(!shown)return;
    shown=false;dialog.hidden=true;dialog.replaceChildren();
    document.body.style.overflow=priorOverflow;
    if(background)background.inert=priorInert;
    if(lastFocus?.isConnected)lastFocus.focus({preventScroll:true});
  }
  function close(){
    const url=new URL(location.href);
    for(const name of ['hpm','hpmYear','hpmCtx','hpmLink'])
      url.searchParams.delete(name);
    history.pushState(null,'',url.pathname+url.search+url.hash);
    hide();
  }
  function sync(){
    if(!active()){hide();return;}
    readFilters();show();render();
  }
  dialog.addEventListener('keydown',e=>{
    if(e.key==='Escape'){e.preventDefault();close();}
    if(e.key!=='Tab')return;
    const focusable=[...dialog.querySelectorAll('button:not([disabled]),a[href],select')]
      .filter(node=>node.getClientRects().length);
    if(!focusable.length)return;
    const first=focusable[0],last=focusable[focusable.length-1];
    if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}
    if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}
  });
  window.addEventListener('popstate',sync);
  sync();
  if(active()){
    loading=fetch('./hpm-pilot.json',{cache:'no-cache'}).then(r=>{
      if(!r.ok)throw Error('HTTP '+r.status);return r.json();
    }).then(payload=>{
      if(payload.schema_version!=='hpm-pages-p3-v1'||
         payload.historical_truth_verified_by_ci!==false||
         payload.historical_region_wide_inference_supported!==false||
         payload.accession_mechanism_rates!==null||
         payload.counts?.candidate_events!==10||
         !Array.isArray(payload.events)||payload.events.length!==10||
         !payload.events.every(x=>x.accession_mechanism==='unknown' &&
           Array.isArray(x.sources)&&x.sources.length&&Array.isArray(x.roles) &&
           Array.isArray(x.contexts)&&Array.isArray(x.raw_observations)))
        throw Error('Нарушен контракт источникового пилота');
      data=payload;readFilters();render();
    }).catch(e=>{error=e.message;render();});
  }
})();
