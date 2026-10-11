/* Historical authority is multi-dimensional, not a single sovereign/subject tree.
 * All visual claims are sourced, regional and year-qualified.
 * No inferred borders, ethnicities, direct provincial rule or exact days.
 */
(() => {
  'use strict';
  const app=document.getElementById('world-authority-app');
  if(!app)return;
  const ns='http://www.w3.org/2000/svg';
  const DIMENSIONS=[
    ['legal','Юридическая власть'],
    ['practical','Местная фактическая власть'],
    ['institutional','Институты и финансы'],
    ['military','Военные действия'],
    ['diplomatic','Дипломатическая иерархия']
  ];
  const allowed=new Set(DIMENSIONS.map(d=>d[0]));
  const labels={
    person:'Человек',polity:'Политическое образование',
    constitutional_framework:'Имперский правовой порядок',
    imperial_title_context:'Императорская власть',
    collective_institution:'Коллективный орган',
    locality:'Локальное место',fiscal_jurisdiction:'Налоговая юрисдикция'
  };
  const make=(tag,cls,text)=>{
    const n=document.createElement(tag);
    if(cls)n.className=cls;
    if(text!==undefined)n.textContent=String(text);
    return n;
  };
  const svg=(tag,attrs)=>{
    const n=document.createElementNS(ns,tag);
    Object.entries(attrs||{}).forEach(([k,v])=>n.setAttribute(k,String(v)));
    return n;
  };
  const getParam=k=>new URL(location.href).searchParams.get(k);
  const root=make('div','world-auth-content');
  const heading=make('h1',null,'Мировая сеть власти · 1788');
  const intro=make('p','world-auth-intro',
    'Три исследовательских примера: имперский правовой порядок, конкурирующие власти в Индии и дипломатия Цин—Чосон. Это не полная карта мира и не доказательство непрерывного контроля территории.');
  const yearTabs=make('nav','world-auth-year-tabs');
  yearTabs.setAttribute('aria-label','Исторические годы исследовательского атласа');
  const regionTabs=make('div','world-auth-region-tabs');
  regionTabs.setAttribute('role','group');
  regionTabs.setAttribute('aria-label','Выберите исторический регион');
  const controls=make('fieldset','world-auth-filters');
  controls.append(make('legend',null,'Какие виды власти показывать'));
  const status=make('p','world-auth-status','Загружаем данные источников…');
  status.setAttribute('role','status');status.setAttribute('aria-live','polite');
  const regionNote=make('section','world-auth-regional-note');
  const graphScroll=make('div','world-auth-scroll');
  graphScroll.tabIndex=0;graphScroll.setAttribute('role','region');
  graphScroll.setAttribute('aria-label','Сеть отношений с горизонтальной прокруткой');
  const helper=make('p','world-auth-helper',
    'Стрелка обозначает направление конкретного отношения, не всегда «кто кому подчинён». Год 1788 — исследовательский срез, а не дата начала всех полномочий.');
  const relations=make('div','world-auth-relations');
  const detail=make('section','world-auth-detail');
  detail.tabIndex=-1;detail.id='world-auth-detail';
  detail.setAttribute('aria-label','Описание и исторические источники');
  root.append(heading,intro,yearTabs,regionTabs,controls,status,regionNote,
              graphScroll,helper,make('h2',null,'Документированные отношения'),
              relations,detail);
  app.replaceChildren(root);
  const YEARS=[1688,1788,1888];
  const readYear=()=>{
    const raw=Number(getParam('year'));
    return YEARS.includes(raw)?raw:1788;
  };
  let year=readYear(),data=null,region='hre',dimensions=new Set(allowed),
      selected=null,revision=0;
  function params(){
    const wanted=getParam('region');
    region=data.regions.some(x=>x.id===wanted)?wanted:data.regions[0].id;
    const set=getParam('dims');
    dimensions=set===null?new Set(allowed):set==='none'?new Set():
      new Set(set.split(',').filter(x=>allowed.has(x)));
  }
  function updateURL(push){
    const u=new URL(location.href);
    u.searchParams.set('region',region);
    if(year===1788)u.searchParams.delete('year');
    else u.searchParams.set('year',String(year));
    const chosen=[...dimensions].sort();
    if(chosen.length===allowed.size)u.searchParams.delete('dims');
    else u.searchParams.set('dims',chosen.length?chosen.join(','):'none');
    history[push?'pushState':'replaceState'](null,'',u.pathname+u.search+u.hash);
  }
  const validLink=url=>{
    try{
      const x=new URL(url);
      return x.protocol==='https:'&&!x.username&&!x.password&&
        ![['drive','.google.com'].join(''),['docs','.google.com'].join('')].includes(x.hostname);
    }catch(_){return false;}
  };
  function citations(ids){
    const panel=make('div','world-auth-sources');
    for(const id of [...new Set(ids||[])]){
      const ref=data?.sources?.[id];
      if(!ref||!validLink(ref.url))continue;
      const a=make('a','world-auth-source',ref.title+' ↗');
      a.href=ref.url;a.target='_blank';a.rel='noopener noreferrer';
      a.title='Источник '+id+' · справочная проверка не равна исторической экспертизе';
      panel.append(a);
    }
    if(!panel.childNodes.length)panel.append(make('p',null,'Нет ссылок на источники.'));
    return panel;
  }
  function details(kind,id){
    detail.replaceChildren();
    const item=kind==='node'?data.nodes.find(n=>n.id===id):
      kind==='edge'?data.edges.find(e=>e.id===id):null;
    if(!item){
      detail.append(make('h2',null,'Выберите узел или связь'),
        make('p',null,'Нажмите на карточку или стрелку для источников и оговорок.'));
      return;
    }
    detail.append(make('h2',null,item.label));
    if(kind==='node'){
      detail.append(make('p','world-auth-tag',labels[item.kind]||item.kind),
                    make('p',null,item.note));
    }else{
      detail.append(make('p','world-auth-tag',
        DIMENSIONS.find(x=>x[0]===item.dimension)?.[1]||item.dimension),
        make('p',null,item.explanation),
        make('p','world-auth-caution',item.caveat),
        make('p','world-auth-caution',
          item.meaning==='event'
            ?'Разовое событие '+year+' года, а не непрерывное правление.'
            :'Годовой срез, а не датировка начала или конца всех полномочий.'));
      if(item.documented_day){
        detail.append(make('p','world-auth-tag',
          'Точная дата по источнику: '+item.documented_day.value+
          ' · '+item.documented_day.calendar));
      }
    }
    detail.append(citations(item.source_ids));
  }
  function choose(kind,id){
    selected={kind,id};details(kind,id);
    detail.scrollIntoView({block:'nearest',behavior:'auto'});
  }
  const shorten=(v,n)=>String(v).length>n?String(v).slice(0,n-1)+'…':String(v);
  function drawGraph(nodes,edges){
    graphScroll.replaceChildren();
    const left=nodes.filter(n=>n.kind==='person'||n.kind==='collective_institution');
    const right=nodes.filter(n=>!left.includes(n));
    const maxCount=Math.max(left.length,right.length,4);
    const height=Math.max(450,maxCount*84+80);
    const board=svg('svg',{width:1140,height,viewBox:'0 0 1140 '+height,
      role:'img','aria-label':'Связи людей и политических контекстов выбранного региона'});
    const defs=svg('defs');
    for(const [dim] of DIMENSIONS){
      const marker=svg('marker',{id:'world-auth-arrow-'+dim,markerWidth:11,
        markerHeight:11,refX:7,refY:4,orient:'auto',
        markerUnits:'userSpaceOnUse'});
      marker.append(svg('path',{d:'M0 0L8 4L0 8Z',
        'class':'world-auth-arrow-'+dim}));
      defs.append(marker);
    }
    board.append(defs);
    const lines=svg('g',{'class':'world-auth-lines'});
    const boxes=svg('g',{'class':'world-auth-nodes'});
    const headingRow=svg('g',{'class':'world-auth-column-labels'});
    for(const [x,t] of [[225,'ЛЮДИ И ОРГАНЫ'],[820,'ГОСУДАРСТВА И КОНТЕКСТЫ']]){
      const n=svg('text',{x,y:34,'text-anchor':'middle'});
      n.textContent=t;headingRow.append(n);
    }
    board.append(lines,boxes,headingRow);
    const position=new Map();
    const place=(collection,x)=>{
      const y=(height-(collection.length-1)*84)/2;
      collection.forEach((n,i)=>position.set(n.id,{x,y:y+i*84}));
    };
    place(left,225);place(right,820);
    for(const e of edges){
      const a=position.get(e.from),b=position.get(e.to);
      if(!a||!b)continue;
      const same=Math.abs(a.x-b.x)<1;
      const pathText=same?
        'M'+(a.x+113)+' '+a.y+' C'+(a.x+260)+' '+a.y+
        ','+(b.x+260)+' '+b.y+','+(b.x+113)+' '+b.y:
        'M'+(a.x+(a.x<b.x?113:-113))+' '+a.y+
        ' C545 '+a.y+',545 '+b.y+','+
        (b.x+(a.x<b.x?-113:113))+' '+b.y;
      const path=svg('path',{d:pathText,
        'class':'world-auth-edge world-auth-edge-'+e.dimension,
        'marker-end':'url(#world-auth-arrow-'+e.dimension+')'});
      lines.append(path);
      const hit=svg('path',{d:pathText,tabindex:0,role:'button',
        'class':'world-auth-edge-hit',
        'aria-label':e.label+' · открыть обоснование'});
      hit.dataset.edgeId=e.id;
      hit.addEventListener('click',()=>choose('edge',e.id));
      hit.addEventListener('keydown',ev=>{
        if(ev.key==='Enter'||ev.key===' '){
          ev.preventDefault();choose('edge',e.id);
        }
      });
      lines.append(hit);
    }
    for(const n of nodes){
      const p=position.get(n.id);
      const group=svg('g',{transform:'translate('+p.x+','+p.y+')',
        tabindex:0,role:'button',
        'class':'world-auth-node world-auth-node-'+n.kind,
        'aria-label':n.label});
      group.dataset.nodeId=n.id;
      group.append(svg('rect',{x:-113,y:-25,width:226,height:50,rx:11}));
      const title=svg('text',{x:0,y:5,'text-anchor':'middle'});
      title.textContent=shorten(n.label,23);
      group.append(title);
      group.addEventListener('click',()=>choose('node',n.id));
      group.addEventListener('keydown',ev=>{
        if(ev.key==='Enter'||ev.key===' '){
          ev.preventDefault();choose('node',n.id);
        }
      });
      boxes.append(group);
    }
    graphScroll.append(board);graphScroll.scrollLeft=0;
    if(!nodes.length)graphScroll.append(make('p','world-auth-empty',
      'Нет связей для выбранных фильтров. Это не доказательство отсутствия власти.'));
  }
  function render(){
    if(!data)return;
    heading.textContent='Мировая сеть власти · '+year;
    document.title='Мировая сеть власти · '+year+' — исторический атлас';
    intro.textContent='Выборочные политические отношения '+year+
      ' года: юридические должности, административное управление, военные '+
      'события и дипломатия. Это НЕ полная карта мира, границ или фактической власти.';
    helper.textContent='Все связи датированы исследовательским годом '+year+
      '. Пересечение по году не доказывает правление в один день. '+
      'Смена должности и военное вмешательство показаны как разные отношения.';
    yearTabs.replaceChildren();
    for(const value of YEARS){
      const b=make('button','world-auth-year',String(value));
      b.type='button';b.dataset.year=String(value);
      b.setAttribute('aria-current',value===year?'date':'false');
      b.setAttribute('aria-pressed',String(value===year));
      b.addEventListener('click',()=>{
        if(value===year)return;
        year=value;data=null;selected=null;region='';
        updateURL(true);loadYear();
      });
      yearTabs.append(b);
    }
    regionTabs.replaceChildren();
    for(const r of data.regions){
      const b=make('button','world-auth-region',r.label);
      b.type='button';b.dataset.region=r.id;
      b.setAttribute('aria-pressed',String(r.id===region));
      b.addEventListener('click',()=>{
        region=r.id;selected=null;updateURL(true);render();
      });
      regionTabs.append(b);
    }
    for(const label of controls.querySelectorAll('label'))label.remove();
    for(const [dim,title] of DIMENSIONS){
      const wrap=make('label','world-auth-filter');
      const check=make('input');
      check.type='checkbox';check.value=dim;check.checked=dimensions.has(dim);
      check.setAttribute('aria-label',title);
      check.addEventListener('change',()=>{
        if(check.checked)dimensions.add(dim);else dimensions.delete(dim);
        selected=null;updateURL(false);render();
      });
      wrap.append(check,make('span',null,title));controls.append(wrap);
    }
    const r=data.regions.find(x=>x.id===region);
    regionNote.replaceChildren(make('strong',null,r.subtitle),
      make('p',null,r.explanation),make('p','world-auth-caution',r.warning));
    const visible=data.edges.filter(e=>e.region===region&&dimensions.has(e.dimension));
    const ids=new Set(visible.flatMap(e=>[e.from,e.to]));
    const nodes=data.nodes.filter(n=>ids.has(n.id));
    status.textContent=year+' · '+r.label+' · '+nodes.length+' узлов · '+
      visible.length+' отношений · не полный список правителей';
    drawGraph(nodes,visible);
    relations.replaceChildren();
    for(const e of visible){
      const b=make('button','world-auth-relation');b.type='button';
      b.dataset.edgeId=e.id;
      b.append(make('span','world-auth-relation-kind',
          DIMENSIONS.find(x=>x[0]===e.dimension)?.[1]||e.dimension),
        make('strong',null,e.label),
        make('small',null,e.explanation));
      b.addEventListener('click',()=>choose('edge',e.id));
      relations.append(b);
    }
    if(!visible.length)relations.append(make('p','world-auth-empty',
      'Ни одной записи этого вида. Отсутствие в базе не означает отсутствия власти.'));
    if(selected&&(selected.kind==='node'?nodes.some(n=>n.id===selected.id):
                  visible.some(e=>e.id===selected.id))){
      details(selected.kind,selected.id);
    }else details(null,null);
  }
  function accepted(d){
    if(d.schema_version!=='authority-network-web-v1'||d.focus_year!==year||
       d.sample_covers_all_world!==false||
       d.geographic_boundaries_verified!==false||
       d.historical_truth_verified_by_ci!==false||
       !Array.isArray(d.regions)||!Array.isArray(d.nodes)||
       !Array.isArray(d.edges)||!d.sources){
      throw Error('Контракт данных не совпадает');
    }
    data=d;params();render();
  }
  function loadYear(){
    const token=++revision;
    const file=year===1788?'./world-authority-1788.json':
      './world-authority-'+year+'.json';
    status.textContent='Загружаем исторические источники '+year+' года…';
    return fetch(file,{cache:'no-cache'})
      .then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json();})
      .then(result=>{if(token===revision)accepted(result);})
      .catch(error=>{
        if(token===revision)
          status.textContent='Не удалось открыть исследовательскую сеть: '+
            String(error.message||error);
      });
  }
  window.addEventListener('popstate',()=>{
    const target=readYear();
    if(target!==year){
      year=target;data=null;selected=null;loadYear();
    }else if(data){params();render();}
  });
  loadYear();
})();