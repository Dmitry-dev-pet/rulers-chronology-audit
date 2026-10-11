/* P4: experimental, source-qualified dynasty graph in the existing SPA shell.
   Enabled ONLY by atlasV2=graph and only in the separate preview artifact.
   Dates are year-overlap research candidates, NEVER same-day/effective control.
   No external SDK, code execution, inferred ethnicity or generated geography. */
(() => {
  'use strict';
  if (!document.getElementById('chronology-data')) return;
  const FLAG='graph', MIN=1762, MAX=1800, NS='http://www.w3.org/2000/svg';
  const FILTERS=[
    ['houses','Династии'],
    ['kinship','Брак и родство'],
    ['political_roles','Преемство и регенты'],
    ['personal_union','Личные унии'],
    ['treaty','Договоры'],
    ['institutional','Режимы и органы']
  ];
  const FILTER_KEYS=new Set(FILTERS.map(x=>x[0]));
  const DEFAULTS=new Set(FILTERS.map(x=>x[0]));
  const LABELS={
    marriage:'Брак',parent:'Родство',personal_union:'Личная уния',
    treaty:'Межгосударственный договор',regency:'Регентство',
    co_regency:'Соправительство',succession:'Смена престола',
    imperial_succession:'Выборный императорский титул',
    institutional_change:'Реформа органов',regime_change:'Смена режима',
    sovereign:'Монарх',elector:'Курфюрст',consort:'Консорт',
    heir:'Наследник',dynastic_person:'Династическая фигура',
    co_regent:'Соправитель',regent:'Регент',emperor:'Император СРИ',
    first_consul:'Первый консул',institutional:'Коллегиальный орган',
    documented_house:'Документированный дом',branch_lineage:'Родственная ветвь',
    dynastic_union:'Династический союз'
  };
  const element=(tag,klass,value)=>{
    const n=document.createElement(tag);
    if(klass)n.className=klass;
    if(value!==undefined)n.textContent=String(value);
    return n;
  };
  const svg=(tag,props)=>{
    const n=document.createElementNS(NS,tag);
    Object.entries(props||{}).forEach(([k,v])=>n.setAttribute(k,String(v)));
    return n;
  };
  const replace=(node,...children)=>node.replaceChildren(...children);
  const shorten=(s,max)=>String(s).length>max?String(s).slice(0,max-1)+'…':String(s);
  const escapeOn=event=>event.key==='Enter'||event.key===' ';
  const active=(period,y)=>period.start_year<=y&&y<=period.end_year;
  const relationGroup=r=>r.kind==='personal_union'?'personal_union':
    r.kind==='treaty'?'treaty':r.domain;
  const param=key=>new URL(location.href).searchParams.get(key);
  let data=null,waiting=null,year=1788,filters=new Set(DEFAULTS),selection=null;
  let lastFocus=null,shown=false;

  const overlay=element('div','atlas-v2-layer');
  overlay.hidden=true;
  const dialog=element('section','atlas-v2-dialog');
  dialog.setAttribute('role','dialog');
  dialog.setAttribute('aria-modal','true');
  dialog.setAttribute('aria-labelledby','atlas-v2-heading');
  const header=element('header','atlas-v2-head');
  const headingWrap=element('div','atlas-v2-heading-wrap');
  headingWrap.append(element('span','atlas-v2-eyebrow','ЭКСПЕРИМЕНТ · ИСТОРИЧЕСКИЙ ГРАФ V2'));
  const heading=element('h2','atlas-v2-heading','Династии и политическая власть');
  heading.id='atlas-v2-heading';
  headingWrap.append(heading);
  const close=element('button','atlas-v2-close','Закрыть ×');
  close.type='button';
  close.setAttribute('aria-label','Закрыть экспериментальный граф');
  header.append(headingWrap,close);
  const body=element('div','atlas-v2-body');
  const notice=element('p','atlas-v2-disclaimer',
    'Источниковый пилот 1762–1800, не полная история Европы. Годовые пересечения не доказывают совместную власть в конкретный день. Династия, этничность, юридический титул и фактический контроль различаются.');
  const tools=element('div','atlas-v2-tools');
  const yearRow=element('div','atlas-v2-year-row');
  const backward=element('button','atlas-v2-step','←');
  backward.type='button';
  backward.setAttribute('aria-label','Год назад');
  const currentYear=element('output','atlas-v2-year','1788');
  currentYear.id='atlas-v2-year';
  const forward=element('button','atlas-v2-step','→');
  forward.type='button';
  forward.setAttribute('aria-label','Год вперёд');
  yearRow.append(backward,currentYear,forward);
  const range=element('input','atlas-v2-range');
  range.type='range';range.min=String(MIN);range.max=String(MAX);range.step='1';
  range.setAttribute('aria-label','Исторический год 1762–1800');
  range.id='atlas-v2-year-range';
  const yearEnds=element('div','atlas-v2-year-ends');
  yearEnds.append(element('span',null,String(MIN)),element('span',null,String(MAX)));
  const chips=element('fieldset','atlas-v2-filters');
  chips.append(element('legend',null,'Типы видимых связей'));
  const inputs=new Map();
  for(const [kind,label] of FILTERS){
    const tag=element('label','atlas-v2-filter');
    const input=element('input');
    input.type='checkbox';input.checked=true;input.value=kind;
    input.setAttribute('aria-label',label);
    tag.append(input,element('span',null,label));
    chips.append(tag);inputs.set(kind,input);
    input.addEventListener('change',()=>{
      if(input.checked)filters.add(kind);else filters.delete(kind);
      selection=null;updateURL(false);render();
    });
  }
  tools.append(yearRow,range,yearEnds,chips);
  const status=element('p','atlas-v2-status','Загружаем проверенную структуру графа…');
  status.setAttribute('role','status');status.setAttribute('aria-live','polite');
  const legend=element('div','atlas-v2-legend');
  [
    ['house','Династия'],['person','Личность'],['context','Политический контекст'],
    ['relation','Отношение / событие']
  ].forEach(([kind,label])=>{
    const n=element('span','atlas-v2-legend-item',label);
    n.dataset.legend=kind;legend.append(n);
  });
  const graphScroll=element('div','atlas-v2-graph-scroll');
  graphScroll.setAttribute('role','region');
  graphScroll.setAttribute('aria-label','Интерактивный граф домов, людей и политических контекстов, прокручивается в обе стороны');
  graphScroll.tabIndex=0;
  const relationHeading=element('h3','atlas-v2-subheading','Источниковые связи в выбранном году');
  const relations=element('div','atlas-v2-relations');
  const detail=element('section','atlas-v2-detail');
  detail.setAttribute('aria-label','Подробности и ссылки на исторические источники');
  detail.id='atlas-v2-detail';detail.tabIndex=-1;
  const help=element('p','atlas-v2-help',
    'Линии соединяют дом с человеком и человека с должностью. Пунктир обозначает дополнительные роли; цвет линии — тип отношения, не национальность. На телефоне граф можно прокручивать; все отношения доступны также списком с источниками.');
  body.append(notice,tools,status,legend,graphScroll,help,relationHeading,relations,detail);
  dialog.append(header,body);overlay.append(dialog);document.body.append(overlay);

  const validLink=url=>{
    try{
      const u=new URL(url);
      return u.protocol==='https:'&&!u.username&&!u.password&&
        !/^(drive|docs)\.google\.com$/i.test(u.hostname);
    }catch(_){return false;}
  };
  function addSources(target,ids){
    const wrap=element('div','atlas-v2-source-links');
    const unique=[...new Set(ids||[])];
    if(!unique.length)wrap.append(element('p',null,'Для этой записи ссылки не представлены.'));
    for(const id of unique){
      const item=data?.sources?.[id];
      if(!item||!validLink(item.url))continue;
      const a=element('a','atlas-v2-source',id+' · '+shorten(item.title||id,86)+' ↗');
      a.href=item.url;a.target='_blank';a.rel='noopener noreferrer';
      a.title=item.title||id;
      wrap.append(a);
    }
    target.append(wrap);
  }
  function startOrStop(next,push){
    const url=new URL(location.href);
    if(next){
      url.searchParams.set('atlasV2',FLAG);
      url.searchParams.set('v2Year',String(year));
      const enabled=[...filters].sort();
      if(enabled.length===FILTERS.length)url.searchParams.delete('v2Links');
      else url.searchParams.set('v2Links',enabled.join(',')||'none');
    }else{
      url.searchParams.delete('atlasV2');
      url.searchParams.delete('v2Year');
      url.searchParams.delete('v2Links');
    }
    history[push?'pushState':'replaceState'](null,'',url.pathname+url.search+url.hash);
  }
  const updateURL=push=>startOrStop(true,push);
  const yearFromURL=()=>{
    const v=Number(param('v2Year'));
    return Number.isInteger(v)&&v>=MIN&&v<=MAX?v:1788;
  };
  const linksFromURL=()=>{
    const raw=param('v2Links');
    if(raw===null)return new Set(DEFAULTS);
    if(raw==='none')return new Set();
    const values=raw.split(',').filter(x=>FILTER_KEYS.has(x));
    return new Set(values);
  };
  function adjustYear(y,push){
    const valid=Math.max(MIN,Math.min(MAX,Number(y)||MIN));
    if(valid===year)return;
    year=valid;range.value=String(year);selection=null;
    updateURL(push);render();
  }
  backward.addEventListener('click',()=>adjustYear(year-1,true));
  forward.addEventListener('click',()=>adjustYear(year+1,true));
  range.addEventListener('input',()=>adjustYear(Number(range.value),false));

  function readData(){
    if(waiting)return waiting;
    waiting=fetch('./atlas-v2-graph.json',{cache:'no-cache'}).then(r=>{
      if(!r.ok)throw Error('Пробная проекция недоступна ('+r.status+').');
      return r.json();
    }).then(d=>{
      if(d.schema_version!=='atlas-v2-graph-preview-1'||
         d.historical_truth_verified_by_ci!==false||
         d.scope?.start_year!==MIN||d.scope?.end_year!==MAX||
         !Array.isArray(d.roles)||!Array.isArray(d.relations)||
         !Array.isArray(d.people)||!Array.isArray(d.houses)||
         !Array.isArray(d.contexts)||!d.sources)
         throw Error('Контракт пробной модели не совпадает с интерфейсом.');
      data=d;return d;
    }).catch(err=>{waiting=null;throw err;});
    return waiting;
  }
  function nodeLabel(kind,id){
    if(kind==='house')return data.houses.find(x=>x.id===id)?.name||id;
    if(kind==='person')return data.people.find(x=>x.id===id)?.name||id;
    if(kind==='context')return data.contexts.find(x=>x.id===id)?.name||id;
    if(kind==='institution')return data.institutions.find(x=>x.id===id)?.name||id;
    return id;
  }
  function indexActive(){
    const roleList=data.roles.filter(x=>active(x,year));
    const personRoles=new Map();
    for(const r of roleList){
      if(r.person_id){
        if(!personRoles.has(r.person_id))personRoles.set(r.person_id,[]);
        personRoles.get(r.person_id).push(r);
      }
    }
    const houseLinks=filters.has('houses')
      ?data.affiliations.filter(x=>personRoles.has(x.person_id)):[];
    const relationList=data.relations.filter(r=>{
      if(!active(r,year)||!filters.has(relationGroup(r)))return false;
      return true;
    });
    const personIDs=new Set(houseLinks.map(x=>x.person_id));
    const contextIDs=new Set();
    for(const r of relationList){
      r.people.forEach(p=>personIDs.add(p));
      r.contexts.forEach(c=>contextIDs.add(c));
    }
    const institutionRoles=filters.has('institutional')
      ?roleList.filter(r=>r.institution_id):[];
    const visibleRoles=roleList.filter(r=>r.person_id&&personIDs.has(r.person_id));
    for(const r of [...visibleRoles,...institutionRoles])contextIDs.add(r.context_id);
    const houseIDs=new Set(houseLinks.map(x=>x.house_id));
    return {roleList,personRoles,houseLinks,relationList,
      personIDs,contextIDs,houseIDs,visibleRoles,institutionRoles};
  }

  function mark(kind,id,description,detailIds){
    const options=detailIds||[];
    selection={kind,id,description,sources:options};
    showDetail();
  }
  function showDetail(){
    replace(detail);
    if(!data){detail.append(element('p',null,'Загрузка источников…'));return;}
    const chosen=selection;
    if(!chosen){
      detail.append(element('h3',null,'Выберите узел или связь'));
      detail.append(element('p',null,
        'Нажмите на человека, дом, государство или отношение. Здесь появятся источники и оговорки.'));
      return;
    }
    const title=element('h3',null,chosen.description||nodeLabel(chosen.kind,chosen.id));
    detail.append(title);
    const sources=new Set(chosen.sources||[]);
    if(chosen.kind==='person'){
      const p=data.people.find(x=>x.id===chosen.id);
      detail.append(element('p',null,
        p?.resolution==='linked'?'Личность связана с канонической записью.'
          :'Отдельный исследовательский ID; связь с российским каноном не заявлена.'));
      const roles=data.roles.filter(r=>r.person_id===chosen.id&&active(r,year));
      for(const r of roles){
        detail.append(element('p','atlas-v2-detail-line',
          (LABELS[r.kind]||r.kind)+' · '+r.title+' ('+r.start_year+'–'+r.end_year+')'));
        r.sources.forEach(s=>sources.add(s));
      }
      for(const a of data.affiliations.filter(a=>a.person_id===chosen.id)){
        detail.append(element('p','atlas-v2-detail-line',
          (LABELS[a.kind]||a.kind)+': '+nodeLabel('house',a.house_id)+'. '+a.branch));
        a.sources.forEach(s=>sources.add(s));
      }
    }else if(chosen.kind==='house'){
      const h=data.houses.find(x=>x.id===chosen.id);
      detail.append(element('p',null,h?.note||''));
      h?.sources.forEach(s=>sources.add(s));
      for(const a of data.affiliations.filter(a=>a.house_id===chosen.id)){
        a.sources.forEach(s=>sources.add(s));
      }
    }else if(chosen.kind==='context'){
      const c=data.contexts.find(x=>x.id===chosen.id);
      detail.append(element('p',null,
        'Тип исторического контекста: '+(c?.kind||'не установлен')+
        '. Контекст не обязательно суверенное государство с известными границами.'));
      for(const r of data.roles.filter(r=>r.context_id===chosen.id&&active(r,year))){
        r.sources.forEach(s=>sources.add(s));
      }
    }else if(chosen.kind==='relation'){
      const r=data.relations.find(x=>x.id===chosen.id);
      if(r){
        detail.append(element('p','atlas-v2-detail-line',
          (LABELS[r.kind]||r.kind)+' · '+r.title));
        detail.append(element('p',null,r.note));
        detail.append(element('p','atlas-v2-detail-caveat',
          r.time_kind==='event'
            ?'Однократное событие; это не длительность действия режима или договора.'
            :'Временной интервал отражает источник, а не доказанную непрерывность отношений.'));
        r.sources.forEach(s=>sources.add(s));
      }
    }else if(chosen.kind==='role'){
      const r=data.roles.find(x=>x.id===chosen.id);
      if(r){
        detail.append(element('p','atlas-v2-detail-line',
          (LABELS[r.kind]||r.kind)+' · '+r.title));
        detail.append(element('p',null,r.note));
        r.sources.forEach(s=>sources.add(s));
      }
    }else if(chosen.kind==='affiliation'){
      const a=data.affiliations.find(x=>x.id===chosen.id);
      if(a){
        detail.append(element('p',null,a.branch));
        a.sources.forEach(s=>sources.add(s));
      }
    }
    const disclaimer=element('p','atlas-v2-detail-caveat',
      'Проверка ссылки на источник не подтверждает фактическое господство или национальность.');
    detail.append(disclaimer);
    addSources(detail,[...sources]);
  }
  function choose(kind,id){
    mark(kind,id,nodeLabel(kind,id));
    detail.scrollIntoView({block:'nearest',behavior:'auto'});
  }

  function graphUI(activeSet){
    replace(graphScroll);
    const families=data.houses.filter(h=>activeSet.houseIDs.has(h.id));
    const people=data.people.filter(p=>activeSet.personIDs.has(p.id));
    const contexts=data.contexts.filter(c=>activeSet.contextIDs.has(c.id));
    const institutions=data.institutions.filter(i=>activeSet.institutionRoles.some(r=>r.institution_id===i.id));
    const count=Math.max(families.length,people.length,contexts.length+institutions.length,5);
    const height=Math.max(455,count*70+110);
    const board=svg('svg',{viewBox:'0 0 1460 '+height,width:'1460',height,
      role:'img','aria-label':'Граф выбранного года: дома слева, люди в центре, политические контексты справа'});
    const edges=svg('g',{'class':'atlas-v2-edges'});
    const nodes=svg('g',{'class':'atlas-v2-nodes'});
    board.append(edges,nodes);
    const positions=new Map();
    const register=(collection,x,kind)=>{
      const pad=(height-(collection.length-1)*70)/2;
      for(let i=0;i<collection.length;i++){
        const n=collection[i];positions.set(kind+':'+n.id,{x,y:pad+i*70,node:n,kind});
      }
    };
    register(families,165,'house');
    register(people,710,'person');
    register(contexts,1240,'context');
    register(institutions,1240,'institution');
    const sourceKind=new Map();
    const addEdge=(a,b,kind,id,klass)=>{
      const one=positions.get(a),two=positions.get(b);
      if(!one||!two)return;
      const self=Math.abs(one.x-two.x)<10;
      const d=self
        ?'M '+(one.x+84)+' '+one.y+' C '+(one.x+168)+' '+one.y+', '+(two.x+168)+' '+two.y+', '+(two.x+84)+' '+two.y
        :'M '+(one.x+one.x<two.x?100:0);
      const actual=self?d:('M '+(one.x+(one.x<two.x?100:-100))+' '+one.y+
        ' C '+((one.x+two.x)/2)+' '+one.y+', '+((one.x+two.x)/2)+' '+two.y+
        ', '+(two.x+(one.x<two.x?-100:100))+' '+two.y);
      const path=svg('path',{d:actual,'class':'atlas-v2-edge atlas-v2-edge-'+klass,
        'data-edge-kind':kind});
      edges.append(path);
      if(id){
        const hit=svg('path',{d:actual,'class':'atlas-v2-edge-hit',tabindex:'0',role:'button',
          'aria-label':kind==='role'?'Открыть роль и её источники':'Открыть связь и её источники'});
        hit.dataset.kind=kind;hit.dataset.id=id;
        hit.addEventListener('click',()=>choose(kind,id));
        hit.addEventListener('keydown',e=>{if(escapeOn(e)){e.preventDefault();choose(kind,id);}});
        edges.append(hit);
      }
    };
    for(const a of activeSet.houseLinks){
      addEdge('house:'+a.house_id,'person:'+a.person_id,'affiliation',a.id,
        a.kind==='documented_house'?'house':'lineage');
    }
    for(const r of activeSet.visibleRoles){
      addEdge('person:'+r.person_id,'context:'+r.context_id,'role',r.id,
        ['sovereign','elector'].includes(r.kind)?'ruling':'secondary');
    }
    for(const r of activeSet.institutionRoles){
      addEdge('institution:'+r.institution_id,'context:'+r.context_id,'role',r.id,
        'institutional');
    }
    for(const r of activeSet.relationList){
      if(r.people.length===2){
        addEdge('person:'+r.people[0],'person:'+r.people[1],'relation',r.id,r.kind);
      }else if(r.contexts.length===2){
        addEdge('context:'+r.contexts[0],'context:'+r.contexts[1],
          'relation',r.id,r.kind);
      }
    }
    const kinds=[
      ['house',families,'Дом'],['person',people,'Человек'],
      ['context',contexts,'Контекст'],['institution',institutions,'Орган']
    ];
    for(const [kind,collection] of kinds)for(const item of collection){
      const pos=positions.get(kind+':'+item.id);
      const group=svg('g',{transform:'translate('+pos.x+' '+pos.y+')',
        'class':'atlas-v2-node atlas-v2-node-'+kind,tabindex:'0',role:'button',
        'aria-label':kind+': '+(item.name||item.label||item.id)});
      group.dataset.entityKind=kind;group.dataset.entityId=item.id;
      group.append(svg('rect',{x:-100,y:-24,width:200,height:48,rx:11}));
      const label=svg('text',{x:0,y:4,'text-anchor':'middle'});
      label.textContent=shorten(item.name||item.label||item.id,kind==='context'?22:25);
      group.append(label);
      group.addEventListener('click',()=>choose(kind,item.id));
      group.addEventListener('keydown',e=>{if(escapeOn(e)){e.preventDefault();choose(kind,item.id);}});
      nodes.append(group);
    }
    const header=svg('g',{'class':'atlas-v2-columns'});
    for(const [x,label] of [[165,'ДИНАСТИИ'],[710,'ЛЮДИ'],[1240,'ГОСУДАРСТВА / КОНТЕКСТЫ']]){
      const title=svg('text',{x,y:30,'text-anchor':'middle'});title.textContent=label;
      header.append(title);
    }
    board.append(header);
    graphScroll.append(board);
    graphScroll.scrollLeft=0;graphScroll.scrollTop=0;
    if(!families.length&&!people.length&&!contexts.length){
      graphScroll.append(element('p','atlas-v2-empty',
        'По выбранным фильтрам для этого года нет источниковых связей.'));
    }
    return {families:families.length,people:people.length,contexts:contexts.length,
      institutions:institutions.length,relations:activeSet.relationList.length};
  }

  function render(){
    currentYear.textContent=String(year);
    range.value=String(year);
    backward.disabled=year<=MIN;forward.disabled=year>=MAX;
    for(const [key,node] of inputs)node.checked=filters.has(key);
    if(!data){return;}
    const relevant=indexActive();
    const totals=graphUI(relevant);
    status.textContent=year+' · '+totals.families+' дома · '+totals.people+
      ' человека · '+totals.contexts+' контекстов · '+totals.relations+
      ' связей (по источниковому охвату)';
    replace(relations);
    if(!relevant.relationList.length){
      relations.append(element('p','atlas-v2-empty',
        'Для выбранных типов связей и года документированных событий в пилоте нет.'));
    }
    for(const r of relevant.relationList){
      const item=element('button','atlas-v2-relation');
      item.type='button';item.dataset.relationId=r.id;
      item.append(element('span','atlas-v2-relation-type',LABELS[r.kind]||r.kind));
      item.append(element('strong',null,r.title));
      item.append(element('small',null,
        r.time_kind==='event'?'Событие '+(r.event_year||r.start_year):
          'Источниковое окно '+r.start_year+'–'+r.end_year));
      item.addEventListener('click',()=>choose('relation',r.id));
      relations.append(item);
    }
    showDetail();
  }
  function applyRoute(){
    const wants=param('atlasV2')===FLAG;
    if(!wants){
      if(shown){
        shown=false;overlay.hidden=true;
        document.documentElement.classList.remove('atlas-v2-open');
        if(lastFocus&&lastFocus.isConnected)lastFocus.focus();
        lastFocus=null;
      }
      return;
    }
    if(!shown){
      shown=true;lastFocus=document.activeElement;
      overlay.hidden=false;
      document.documentElement.classList.add('atlas-v2-open');
    }
    year=yearFromURL();filters=linksFromURL();selection=null;
    status.textContent='Загружаем проверенную структуру графа…';
    readData().then(()=>{
      if(!shown)return;
      render();
    }).catch(e=>{
      if(shown){
        status.textContent='Не удалось открыть экспериментальную модель: '+String(e.message||e);
        replace(graphScroll);replace(relations);
        replace(detail,element('p',null,'Основная хронология остаётся доступной.'));
      }
    });
  }
  close.addEventListener('click',()=>{startOrStop(false,true);applyRoute();});
  overlay.addEventListener('click',e=>{
    if(e.target===overlay){startOrStop(false,true);applyRoute();}
  });
  dialog.addEventListener('keydown',e=>{
    if(e.key==='Escape'){e.preventDefault();startOrStop(false,true);applyRoute();return;}
    if(e.key!=='Tab')return;
    const controls=[...dialog.querySelectorAll(
      'button:not([disabled]),input:not([disabled]),a[href],[tabindex="0"]'
    )].filter(x=>x.getClientRects().length>0);
    if(!controls.length)return;
    const first=controls[0],last=controls[controls.length-1];
    if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}
    else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}
  });
  window.addEventListener('popstate',applyRoute);
  window.addEventListener('hashchange',applyRoute);
  applyRoute();
})();