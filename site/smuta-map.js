/* Smuta place explorer. Geographic orientation, NOT a territorial control map.
   No external tiles, tracking, dependencies, inferred tenure or inferred borders. */
(() => {
  'use strict';
  const panel = document.getElementById('panel-timeline');
  const slider = document.getElementById('atlas-year-range');
  const legacy = panel?.querySelector('.atlas-timeline-workspace');
  const toolbar = panel?.querySelector('.timeline-toolbar');
  if (!panel || !slider || !legacy || !toolbar) return;
  const el = (tag, cls, value) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (value !== undefined) n.textContent = String(value);
    return n;
  };
  const button = (text, cls, action) => {
    const b = el('button', cls, text); b.type = 'button';
    b.addEventListener('click', action); return b;
  };
  const safe = value => {
    try { const u = new URL(value); return u.protocol === 'https:' && !u.username && !u.password &&
      ![['drive','.google.com'].join(''),['docs','.google.com'].join('')].includes(u.hostname);
    } catch (_) { return false; }
  };
  const link = (title, href, external = false) => {
    const a = el('a', null, title);
    if (external ? safe(href) : /^#\/people\/person-[a-z0-9-]+$/.test(href)) a.href = href;
    if (external) { a.target = '_blank'; a.rel = 'noopener noreferrer'; }
    return a;
  };
  const modebar = el('div', 'smuta-modebar');
  const launch = button('Смута · карта и источники', 'smuta-launch', () => enter(1608));
  const leave = button('← Общая шкала', 'smuta-return', () => exit());
  leave.hidden = true;
  const intro = el('span', 'smuta-mode-hint', 'Первый географический раздел · 1598–1613');
  const mobileSwitch = button('Свидетельства', 'smuta-mobile-switch', () => setMobile(!work.classList.contains('show-details')));
  modebar.append(launch, leave, intro, mobileSwitch);
  panel.insertBefore(modebar, toolbar);
  // The existing year slider stays canonical; month is a separately qualified
  // sub-period. A year-only statement is NEVER silently assigned to any month.
  const calendar=el('div','smuta-calendarbar');
  calendar.id='smuta-calendarbar';
  const monthLabel=el('label','smuta-month-label','Месяц');
  const monthSelect=el('select','smuta-month-select');
  monthSelect.id='smuta-month';
  monthLabel.htmlFor=monthSelect.id;
  const monthNames=['Весь год','Январь','Февраль','Март','Апрель','Май','Июнь',
    'Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'];
  for(let i=0;i<monthNames.length;i++){
    const o=el('option',null,monthNames[i]);o.value=String(i);monthSelect.append(o);
  }
  monthLabel.append(monthSelect);
  const monthBack=button('‹','smuta-month-step',()=>stepMonth(-1));
  const monthForward=button('›','smuta-month-step',()=>stepMonth(1));
  monthBack.setAttribute('aria-label','Предыдущий месяц');
  monthForward.setAttribute('aria-label','Следующий месяц');
  const monthCaveat=el('span','smuta-month-caveat',
    'Срез по записанной календарной дате; годовые записи не считаются месячными.');
  calendar.append(monthLabel,monthBack,monthForward,monthCaveat);
  panel.insertBefore(calendar,toolbar);

  const work = el('section', 'smuta-workspace'); work.hidden = true;
  work.id = 'smuta-map-workspace'; work.setAttribute('aria-label','Карта свидетельств о власти в Смуту');
  const mapColumn = el('div','smuta-map-column');
  const tools = el('div','smuta-map-tools');
  const examples = el('div','smuta-examples'); examples.setAttribute('aria-label','Годы для сравнения');
  for (const y of [1598,1608,1610,1612,1613]) {
    const b=button(String(y),'smuta-year',()=>setYear(y)); b.dataset.year=String(y); examples.append(b);
  }
  const viewTools=el('div','smuta-zoom-tools');
  viewTools.append(button('−','smuta-zoom',()=>zoomBy(0.65)),button('+','smuta-zoom',()=>zoomBy(1.55)),button('Все города','smuta-fit',()=>fit()));
  viewTools.children[0].setAttribute('aria-label','Уменьшить карту');
  viewTools.children[1].setAttribute('aria-label','Увеличить карту');
  tools.append(examples,viewTools);
  const plot=el('div','smuta-map'); plot.tabIndex=0;
  plot.setAttribute('role','region'); plot.setAttribute('aria-label','Географическая карта. Стрелки перемещают вид, плюс и минус меняют масштаб.');
  const NS='http://www.w3.org/2000/svg';
  const svg=document.createElementNS(NS,'svg'); svg.setAttribute('aria-hidden','true'); svg.classList.add('smuta-grid');
  const waterSvg=document.createElementNS(NS,'svg'); waterSvg.setAttribute('aria-hidden','true'); waterSvg.classList.add('smuta-water');
  const pins=el('div','smuta-pins');
  const stamp=el('div','smuta-map-stamp'); stamp.append(el('strong',null,'СМУТА'),el('span',null,'Карта свидетельств · 1598–1613'));
  const north=el('span','smuta-north','С ↑'); north.setAttribute('aria-hidden','true');
  plot.append(svg,waterSvg,pins,stamp,north);
  const legend=el('div','smuta-legend'); legend.append(el('span','smuta-key active','● Есть запись в выбранном срезе'),el('span','smuta-key','○ Только географический ориентир'));
  const waterLabel=el('label','smuta-water-toggle');
  const waterCheck=el('input');waterCheck.type='checkbox';waterCheck.checked=true;waterCheck.id='smuta-water-toggle';
  waterLabel.append(waterCheck,document.createTextNode(' Реки'));legend.appendChild(waterLabel);
  const caveat=el('p','smuta-map-caveat','Современные точки и обобщённые линии рек, не границы XVII века, исторические русла или точные адреса событий. Нет проверенного рельефа. Датированная запись не означает непрерывный контроль.');
  const hydroAttribution=el('div','smuta-water-source');
  hydroAttribution.append(document.createTextNode('Водная основа: '));
  mapColumn.append(tools,plot,legend,caveat,hydroAttribution);

  const aside=el('aside','smuta-detail'); aside.setAttribute('aria-label','Места, события и источники');
  const modes=el('div','smuta-compare-modes');
  const evidenceMode=button('Свидетельства по месту','smuta-mode-evidence',()=>setComparison(false,true));
  const compareMode=button('Сравнить центры власти','smuta-mode-compare',()=>setComparison(true,true));
  const matrixModeButton=button('Пробелы исследования','smuta-mode-matrix',()=>setMatrix(true,true));
  modes.append(evidenceMode,compareMode,matrixModeButton);
  const filters=el('div','smuta-filters');
  const cityLabel=el('label',null,'Место'); const city=el('select','smuta-city'); city.id='smuta-city'; cityLabel.htmlFor=city.id; cityLabel.append(city);
  const kindLabel=el('label',null,'Тип свидетельства'); const kind=el('select','smuta-kind'); kind.id='smuta-kind'; kindLabel.htmlFor=kind.id;
  const names=new Map([['all','Все типы'],['practice','Местное управление'],['military','Военное присутствие'],['claim','Притязания'],['law','Правовой статус']]);
  for (const [v,n] of names) { const o=el('option',null,n);o.value=v;kind.append(o); }
  kindLabel.append(kind);
  const allLabel=el('label','smuta-period-label'); const all=el('input'); all.type='checkbox';all.id='smuta-all-period';
  allLabel.append(all,document.createTextNode('Показать весь период 1598–1613'));
  filters.append(cityLabel,kindLabel,allLabel);
  const status=el('p','smuta-status','Загрузка данных…');status.setAttribute('role','status');
  const detail=el('div','smuta-detail-scroll');detail.tabIndex=0;
  const share=button('Скопировать ссылку на этот вид','smuta-share',async()=>{
    try { await navigator.clipboard.writeText(location.href);share.textContent='Ссылка скопирована'; }
    catch (_) { const input=el('input','smuta-share-url');input.readOnly=true;input.value=location.href;share.after(input);input.focus();input.select(); }
  });
  aside.append(modes,filters,status,detail,share); work.append(mapColumn,aside);
  panel.insertBefore(work,legacy);
  const oldFooter=document.querySelector('body > [data-atlas-database]');
  const research=document.getElementById('panel-research');
  if(oldFooter && research)research.append(oldFooter);
  function setMobile(show){work.classList.toggle('show-details',show);mobileSwitch.textContent=show?'← Карта':'Свидетельства';schedule();}
  let data=null, error=null, enabled=false, selected='', category='all', whole=false, comparison=false, matrixMode=false, riversVisible=true, selectedMonth=0;
  let sources=new Map(), events=new Map(), people=new Map(), mapped=new Map();
  let view={lon:40,lat:55.3,zoom:1};
  let frame=0, entering=false;
  const currentYear=()=>Number(slider.value);
  const monthKey=(year,month)=>String(year)+'-'+String(month).padStart(2,'0');
  const exactMonth=(row)=>selectedMonth>0 &&
    row.date.precision!=='year'&&row.date.value.slice(0,7)===monthKey(currentYear(),selectedMonth);
  const matchesSelectedYearMonth=row=>
    Number(row.date.value.slice(0,4))===currentYear()&&
    (selectedMonth===0||exactMonth(row));
  const matchesSelectedPeriod=row=>whole||matchesSelectedYearMonth(row);
  function setMonth(month,push=true){
    if(!Number.isInteger(month)||month<0||month>12)return;
    selectedMonth=month;if(month>0)whole=false;
    if(matrixMode)matrixMode=false;
    writeState(push);schedule();
  }
  function stepMonth(direction){
    let next=selectedMonth===0?(direction<0?12:1):selectedMonth+direction;
    let year=currentYear();
    if(next===0){next=12;year--;}else if(next===13){next=1;year++;}
    if(year<1598||year>1613)return;
    if(year!==currentYear())setYear(year);
    setMonth(next);
  }
  const requestedYear=()=>Number(/^#\/timeline\/(\d{4})$/.exec(location.hash)?.[1]||1608);
  const qs=()=>new URL(location.href).searchParams;
  function writeState(push=false) {
    const u=new URL(location.href);
    if(enabled)u.searchParams.set('map','smuta');else u.searchParams.delete('map');
    for(const [key,val] of [['place',selected],['kind',category==='all'?'':category],['scope',whole?'period':''],['month',!whole&&selectedMonth?String(selectedMonth).padStart(2,'0'):''],
      ['compare',comparison?'1':''],['matrix',matrixMode?'1':''],['rivers',riversVisible?'':'0']]) {
      if(enabled&&val)u.searchParams.set(key,val);else u.searchParams.delete(key);
    }
    const target=u.pathname+u.search+u.hash;
    if(target!==location.pathname+location.search+location.hash)history[push?'pushState':'replaceState'](null,'',target);
  }
  function setYear(y) {
    if(!Number.isInteger(y)||y<1598||y>1613)return;
    slider.value=String(y);slider.dispatchEvent(new Event('input',{bubbles:true}));schedule();
  }
  function enter(year=requestedYear(),replace=false) {
    if(entering)return;entering=true;
    enabled=true;panel.classList.add('smuta-map-active');work.hidden=false;legacy.hidden=true;
    launch.setAttribute('aria-pressed','true');leave.hidden=false;
    if(!/^#\/timeline/.test(location.hash))location.hash='#/timeline/'+year;
    // Use the existing era/year controller. Its microtask sets min/max first.
    const era=panel.querySelector('.era-btn[data-era="troubles"]');
    if(era && era.getAttribute('aria-pressed')!=='true')era.click();
    queueMicrotask(()=>{
      setYear(Math.max(1598,Math.min(1613,year)));writeState(!replace);entering=false;schedule();
    });
  }
  function exit(update=true) {
    enabled=false;panel.classList.remove('smuta-map-active');work.hidden=true;legacy.hidden=false;
    leave.hidden=true;launch.setAttribute('aria-pressed','false');if(update)writeState(true);
    window.dispatchEvent(new Event('resize'));
  }
  function readState() {
    const q=qs();selected=q.get('place')||'';category=names.has(q.get('kind'))?q.get('kind'):'all';whole=q.get('scope')==='period';
    comparison=q.get('compare')==='1';matrixMode=q.get('matrix')==='1';
    if(matrixMode)comparison=false;
    const rawMonth=q.get('month')||'';
    selectedMonth=/^(0?[1-9]|1[0-2])$/.test(rawMonth)?Number(rawMonth):0;
    if(whole)selectedMonth=0;
    riversVisible=q.get('rivers')!=='0';
    if(data&&!data.places.some(p=>p.id===selected)&&selected!=='unlocated')selected='';
    if(q.get('map')==='smuta'&&!panel.hidden) {
      if(!enabled)enter(requestedYear(),true);else schedule();
    }else if(q.get('map')!=='smuta'&&enabled)exit(false);
  }
  function setComparison(flag,push=false){
    comparison=flag;matrixMode=false;
    writeState(push);detail.scrollTop=0;schedule();
  }
  function setMatrix(flag,push=false){
    matrixMode=flag;
    if(flag){comparison=false;selectedMonth=0;whole=false;}
    writeState(push);detail.scrollTop=0;schedule();
  }
  function choosePlace(id,push=true) {
    selected=id;comparison=false;matrixMode=false;city.value=id;writeState(push);detail.scrollTop=0;
    if(window.matchMedia('(max-width: 760px)').matches)setMobile(true);
    schedule();
  }
  city.addEventListener('change',()=>choosePlace(city.value));
  kind.addEventListener('change',()=>{category=kind.value;writeState(true);schedule();});
  all.addEventListener('change',()=>{whole=all.checked;if(whole)selectedMonth=0;writeState(true);schedule();});
  monthSelect.addEventListener('change',()=>setMonth(Number(monthSelect.value)));
  waterCheck.addEventListener('change',()=>{riversVisible=waterCheck.checked;writeState(true);schedule();});
  function records(ignorePlace=false) {
    if(!data)return [];
    return data.evidence.filter(e=>matchesSelectedPeriod(e)&&
      (category==='all'||e.nature===category)&&
      (ignorePlace||!selected||(selected==='unlocated'?!mapped.has(e.id):mapped.get(e.id)===selected)));
  }
  function schedule(){cancelAnimationFrame(frame);frame=requestAnimationFrame(render);}
  function fit(){view={lon:40,lat:55.3,zoom:1};schedule();}
  function zoomBy(factor){view.zoom=Math.max(0.7,Math.min(24,view.zoom*factor));schedule();}
  function dimensions(){const w=plot.clientWidth,h=plot.clientHeight;return {w,h,s:Math.max(1,Math.min(w/6.4,h/6.3))*view.zoom,c:Math.cos(55.3*Math.PI/180)};}
  function project(p,d){return {x:d.w/2+(p.lon-view.lon)*d.c*d.s,y:d.h/2+(view.lat-p.lat)*d.s};}
  function svgNode(tag,attrs,text){const n=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,String(v));if(text!==undefined)n.textContent=text;return n;}
  function drawWater(d) {
    waterSvg.setAttribute('viewBox',`0 0 ${d.w} ${d.h}`);
    waterSvg.replaceChildren();
    if(!riversVisible||!data?.hydrography)return;
    const labeled=new Set(),mainNames=new Set(['Volga','Oka']);
    for(const stream of data.hydrography.rivers){
      const primary=mainNames.has(stream.name);
      let longest=[],bestLength=0;
      for(const path of stream.paths){
        const points=path.map(([lon,lat])=>project({lon,lat},d));
        if(points.length<2)continue;
        const dstr=points.map((p,i)=>(i?'L':'M')+p.x.toFixed(1)+','+p.y.toFixed(1)).join(' ');
        waterSvg.appendChild(svgNode('path',{d:dstr,'data-water':stream.id,
          'data-river':stream.name||'',class:primary?'smuta-river-major':'smuta-river-minor'}));
        const len=points.slice(1).reduce((n,p,i)=>n+Math.hypot(p.x-points[i].x,p.y-points[i].y),0);
        if(len>bestLength){bestLength=len;longest=points;}
      }
      if(primary&&!labeled.has(stream.name)&&bestLength>90&&longest.length>2){
        const pos=longest[Math.floor(longest.length/2)];
        if(pos.x>30&&pos.x<d.w-30&&pos.y>25&&pos.y<d.h-20){
          waterSvg.appendChild(svgNode('text',{class:'smuta-river-label',x:pos.x+5,y:pos.y-7},stream.label_ru||stream.name));
          labeled.add(stream.name);
        }
      }
    }
  }
  function drawMap(){
    if(!data||!enabled||!plot.clientWidth)return;
    const d=dimensions();svg.setAttribute('viewBox',`0 0 ${d.w} ${d.h}`);svg.replaceChildren();pins.replaceChildren();
    drawWater(d);
    const ideal=85/(d.s*d.c);
    const step=[0.1,0.25,0.5,1,2,5,10].find(v=>v>=ideal)||10;
    for(let lon=30;lon<=50;lon+=step){const p=project({lon,lat:view.lat},d);if(p.x<0||p.x>d.w)continue;
      svg.append(svgNode('line',{x1:p.x,y1:0,x2:p.x,y2:d.h}),svgNode('text',{x:p.x+4,y:d.h-8},lon+'° в. д.'));}
    for(let lat=50;lat<=61;lat+=step){const p=project({lon:view.lon,lat},d);if(p.y<0||p.y>d.h)continue;
      svg.append(svgNode('line',{x1:0,y1:p.y,x2:d.w,y2:p.y}),svgNode('text',{x:8,y:p.y-5},lat+'° с. ш.'));}
    const visible=(comparison||matrixMode)?data.evidence.filter(e=>matchesSelectedYearMonth(e)):records(true);
    const counts=new Map(data.places.map(p=>[p.id,visible.filter(r=>p.evidence_ids.includes(r.id)).length]));
    let placed=data.places.map(p=>({...p,...project(p.reference_point,d),members:[p]}));
    // Nearby geographic anchors are clustered, NEVER shifted away from coordinates.
    const a=placed.find(p=>p.id==='moscow'),b=placed.find(p=>p.id==='tushino');
    if(a&&b&&Math.hypot(a.x-b.x,a.y-b.y)<70){placed=placed.filter(p=>!['moscow','tushino'].includes(p.id));placed.push({id:'moscow,tushino',name:'Москва / Тушино',x:(a.x+b.x)/2,y:(a.y+b.y)/2,members:[a,b]});}
    for(const p of placed){if(p.x<12||p.x>d.w-12||p.y<12||p.y>d.h-12)continue;
      const n=p.members.reduce((v,m)=>v+(counts.get(m.id)||0),0),isCluster=p.members.length>1;
      const pin=button('', 'smuta-marker'+(n?' has-evidence':'')+(p.members.some(m=>m.id===selected)?' is-selected':''),()=>{
        if(isCluster){view={lon:(a.reference_point.lon+b.reference_point.lon)/2,lat:(a.reference_point.lat+b.reference_point.lat)/2,zoom:20};schedule();}
        else choosePlace(p.id);
      });
      pin.dataset.place=p.id;pin.dataset.count=String(n);pin.dataset.cluster=String(isCluster);
      pin.style.left=p.x+'px';pin.style.top=p.y+'px';
      pin.setAttribute('aria-label',isCluster?`Разделить точки: ${p.name}`:`${p.name}: ${n} свидетельств`);
      pin.setAttribute('aria-pressed',String(p.members.some(m=>m.id===selected)));
      const dot=el('span','smuta-pin-dot',isCluster?'2':n||'');
      const label=el('span','smuta-pin-label',p.name);if(p.x>d.w-170)label.classList.add('left');
      pin.append(dot,label);
      const kinds=[...new Set(p.members.flatMap(m=>
        visible.filter(e=>m.evidence_ids.includes(e.id)).map(e=>e.nature)))];
      if(kinds.length){
        const chips=el('span','smuta-pin-kinds');
        for(const type of kinds)chips.appendChild(el('span','smuta-kind-dot '+type,'●'));
        pin.appendChild(chips);
      }
      pins.append(pin);
    }
  }
  function cite(node,ids){for(const id of [...new Set(ids)]){const src=sources.get(id);if(src&&safe(src.url)){const a=link(id,src.url,true);a.title=src.title;node.append(a);}}}
  function date(d){const unit={day:'',month:' · месяц',year:' · только год'}[d.precision]||'';return d.value+unit+' · '+({julian:'ст. ст.',gregorian:'н. ст.',unspecified:'календарь не уточнён'}[d.calendar]||'');}
  function renderMatrix(){
    const info=data.research_coverage;
    const heading=el('section','smuta-matrix-intro');
    heading.append(el('h3',null,'Матрица исследовательских пробелов'),
      el('p',null,info.precision_policy),
      el('p','smuta-matrix-stats',info.places.length+' мест × '+info.years.length+' лет · '+
        info.filled_city_years+' ячеек с документами · '+
        info.research_gap_city_years+' без внесённых записей.'));
    detail.append(heading);
    const scroll=el('div','smuta-matrix-scroll');
    scroll.tabIndex=0;scroll.setAttribute('role','region');
    scroll.setAttribute('aria-label','Матрица города и года; прокручивается горизонтально');
    const table=el('table','smuta-matrix');
    const head=el('thead');
    const header=el('tr');
    const th=el('th',null,'Место');th.scope='col';header.append(th);
    for(const year of info.years){const h=el('th',null,year);h.scope='col';header.append(h);}
    head.append(header);table.append(head);
    const tbody=el('tbody');
    for(const place of info.places){
      const tr=el('tr');tr.dataset.place=place.place_id;
      const name=el('th',null,place.name);name.scope='row';tr.append(name);
      for(const cell of place.cells){
        const td=el('td');
        const n=cell.evidence_ids.length;
        const caption=n?String(n):'—';
        const label=place.name+', '+cell.year+': '+(n?
          n+' свидетельств; известные месяцы: '+(cell.known_months.join(', ')||'не установлены')+
            '; записей только с годовой датировкой: '+cell.year_only_ids.length:
          'нет внесённых свидетельств, наличие власти неизвестно');
        const action=button(caption,'smuta-matrix-cell'+(n?' has-evidence':' is-gap'),()=>{
          selectedMonth=0;whole=false;
          setYear(cell.year);
          choosePlace(place.place_id);
          schedule();
        });
        action.dataset.year=String(cell.year);
        action.dataset.place=place.place_id;
        action.dataset.count=String(n);
        action.setAttribute('aria-label',label);
        action.title=label;
        action.setAttribute('aria-current',String(cell.year===currentYear()&&
          place.place_id===selected?'true':'false'));
        td.append(action);tr.append(td);
      }
      tbody.append(tr);
    }
    table.append(tbody);scroll.append(table);detail.append(scroll);
    const note=el('p','smuta-matrix-note',
      'Число в клетке — количество записей, не длительность власти. Пусто — не изучено, а не «не управлял». Нажмите клетку для перехода к городу и году.');
    detail.append(note);
    const unknown=el('div','smuta-matrix-unlocated',info.unlocated_evidence_ids.length+
      ' свидетельство о нескольких городах оставлено без единой точки. Это не потерянная запись.');
    detail.append(unknown);
    status.textContent='Матрица · '+info.filled_city_years+' документированных ячеек, '+
      info.research_gap_city_years+' исследовательских пробелов';
  }
  function renderComparison(){
    const year=currentYear();
    const lead=el('div','smuta-comparison-lead');
    const period=selectedMonth?monthNames[selectedMonth]+' '+year:year+' год';
    lead.append(el('h3',null,'Центры власти · '+period),
      el('p',null,selectedMonth?
        'Юридические сроки ниже пересекают ГОД, но не подтверждают власть именно в выбранном месяце. Местные свидетельства с известным месяцем приведены отдельно. Юлианский и неизвестный календарный стиль не нормализованы между собой.':
        'Показаны только юридические сроки, пересекающие выбранный год, и документированные местные свидетельства именно за этот год. Годовые пересечения не доказывают одновременность, а должность — фактический контроль всей территории.'));
    detail.append(lead);
    const formal=(data.formal_year_overlaps||[]).filter(t=>
      Number(t.start.value.slice(0,4))<=year&&Number(t.end.value.slice(0,4))>=year);
    const legalSection=el('section','smuta-comparison-legal');
    legalSection.append(el('h4',null,'Юридический престол · пересечение с годом'));
    if(!formal.length)legalSection.append(el('p','smuta-comparison-empty','Для этого года нет отдельного подтверждённого срока в исследованной базе.'));
    for(const term of formal){
      const card=el('article','smuta-center legal');
      card.append(el('small',null,term.start.value+' — '+term.end.value+' · '+term.status),
        el('h5',null,term.name),el('p',null,term.description),
        el('p','smuta-limit','Годовой срез не является утверждением, что этот правитель осуществлял власть весь год или над всеми городами.'));
      if(term.verification==='imported_not_rechecked')
        card.append(el('p','smuta-comparison-warning','Срок ещё требует независимой документальной сверки.'));
      const citations=el('div','smuta-citations');cite(citations,term.sources);card.append(citations);
      card.append(link('Открыть биографию','#/people/'+term.person_id));
      legalSection.append(card);
    }
    detail.append(legalSection);
    // A comparison is always time-scoped, even if the separate evidence
    // browser is configured to show the whole 1598–1613 period.
    const present=data.evidence.filter(e=>matchesSelectedYearMonth(e));
    const heading=el('h4',null,'Местное управление, военное присутствие и притязания');
    detail.append(heading);
    if(!present.length)detail.append(el('p','smuta-comparison-empty',
      'За этот год отдельных свидетельств о местах пока нет. Не означает отсутствия политических центров или непрерывности прежней власти.'));
    const groups=new Map();
    for(const e of present){
      if(!groups.has(e.authority))groups.set(e.authority,[]);
      groups.get(e.authority).push(e);
    }
    for(const [actor,observations] of groups){
      const card=el('article','smuta-center');
      card.append(el('h5',null,actor),
        el('p','smuta-comparison-description',observations.length+
          (selectedMonth?' свидетельств с известным месяцем · '+period:' местных свидетельств в '+year+' году.')));
      for(const e of observations){
        const row=el('div','smuta-center-observation');
        row.dataset.nature=e.nature;row.dataset.sourceEvent=e.id;
        row.append(el('small',null,date(e.date)+' · '+names.get(e.nature)),
          el('h6',null,e.place),
          el('p',null,e.statement),
          el('p','smuta-limit',e.limitation));
        const citations=el('div','smuta-citations');cite(citations,e.sources);row.append(citations);
        const placeId=mapped.get(e.id);
        if(placeId)row.append(button('Найти место на карте →','smuta-center-find',()=>choosePlace(placeId)));
        else row.append(el('p','smuta-unlocated','Несколько мест в одном притязании: точная точка не установлена.'));
        card.append(row);
      }
      detail.append(card);
    }
    if(selectedMonth){
      const uncertain=data.evidence.filter(e=>
        Number(e.date.value.slice(0,4))===year&&e.date.precision==='year');
      if(uncertain.length){
        const box=el('section','smuta-month-unknown');
        box.append(el('h4',null,'Месяц не установлен · '+uncertain.length),
          el('p',null,'Эти события известны только с точностью до года. Нельзя приписывать их выбранному месяцу.'));
        for(const e of uncertain){
          const note=el('article','smuta-uncertain-item');
          note.append(el('strong',null,e.place),el('p',null,e.statement));
          const links=el('div','smuta-citations');cite(links,e.sources);note.append(links);
          box.append(note);
        }
        detail.append(box);
      }
    }
    const warning=el('p','smuta-comparison-warning',
      'Ни один из показанных политических центров не получает нарисованную территорию контроля; для неё необходимы отдельные источники по каждому месту и периоду.');
    detail.append(warning);
    status.textContent=period+' · '+formal.length+' годовых юридических записей, '+
      groups.size+' местных центров по '+present.length+' датированным свидетельствам';
  }
  function render(){
    if(!enabled)return;
    for(const b of examples.querySelectorAll('button'))b.setAttribute('aria-pressed',String(Number(b.dataset.year)===currentYear()));
    evidenceMode.setAttribute('aria-pressed',String(!comparison&&!matrixMode));
    compareMode.setAttribute('aria-pressed',String(comparison));
    matrixModeButton.setAttribute('aria-pressed',String(matrixMode));
    aside.classList.toggle('is-comparison',comparison);
    filters.hidden=comparison||matrixMode;waterCheck.checked=riversVisible;
    city.value=selected;kind.value=category;all.checked=whole;
    monthSelect.value=String(selectedMonth);
    monthSelect.disabled=whole;
    monthBack.disabled=currentYear()===1598&&selectedMonth===1;
    monthForward.disabled=currentYear()===1613&&selectedMonth===12;
    monthCaveat.textContent=selectedMonth?
      monthNames[selectedMonth]+' · запись года без месяца не относится к этому срезу; календари не приведены к единому стилю.':
      'Весь '+currentYear()+' год · месяц выбирается только по документу.';
    if(!data){status.textContent=error?'Данные не загрузились: '+error:'Загрузка карты…';return;}
    drawMap();detail.replaceChildren();
    if(matrixMode){renderMatrix();return;}
    if(comparison){renderComparison();return;}
    const shown=records(),year=currentYear(),where=data.places.find(p=>p.id===selected);
    const period=whole?'Весь период 1598–1613':selectedMonth?
      monthNames[selectedMonth]+' '+year:year+' год';
    status.textContent=period+' · '+shown.length+' документированных свидетельств'+(where?' · '+where.name:'');
    if(where){
      const box=el('div','smuta-place-note');box.append(el('h3',null,where.name),el('p',null,where.note));
      box.append(link('Откуда взят географический ориентир',where.coordinate_source.url,true));detail.append(box);
    }
    if(!shown.length){
      const empty=el('div','smuta-empty');empty.append(el('h3',null,'Для этого среза записи нет'),el('p',null,'Это пробел в исследовании, а не отсутствие власти или доказательство неизменного контроля.'));
      const pool=data.evidence.filter(e=>!selected||mapped.get(e.id)===selected);
      for(const y of [...new Set(pool.map(e=>Number(e.date.value.slice(0,4))))].sort())empty.append(button('Перейти к '+y,'smuta-nearest-year',()=>setYear(y)));
      detail.append(empty);
    }
    if(selectedMonth&&!whole){
      const undated=data.evidence.filter(e=>
        Number(e.date.value.slice(0,4))===year&&e.date.precision==='year'&&
        (category==='all'||e.nature===category)&&
        (!selected||(selected==='unlocated'?!mapped.has(e.id):mapped.get(e.id)===selected)));
      if(undated.length){
        const box=el('section','smuta-month-unknown');
        box.append(el('h3',null,'Месяц не установлен · '+undated.length),
          el('p',null,'Ниже сведения только за год. Они не считаются событиями выбранного месяца.'));
        for(const e of undated){
          const card=el('article','smuta-uncertain-item');card.dataset.evidence=e.id;
          card.append(el('strong',null,e.place),el('p',null,e.statement),
            el('p','smuta-limit',e.limitation));
          const refs=el('div','smuta-citations');cite(refs,e.sources);card.append(refs);
          box.append(card);
        }
        detail.append(box);
      }
    }
    for(const e of shown){
      const card=el('article','smuta-evidence');card.dataset.evidence=e.id;card.dataset.kind=e.nature;
      card.append(el('small',null,date(e.date)+' · '+names.get(e.nature)),el('h3',null,e.place),el('strong','smuta-authority',e.authority),el('p',null,e.statement),el('p','smuta-limit',e.limitation));
      if(!mapped.has(e.id))card.append(el('p','smuta-unlocated','Без точки на карте: '+data.unlocated.find(u=>u.evidence_id===e.id)?.reason));
      const refs=el('div','smuta-citations');cite(refs,e.sources);card.append(refs);
      const personIds=[...new Set(e.related_event_ids.map(id=>events.get(id)?.person_id).filter(Boolean))];
      for(const id of personIds)if(people.has(id))card.append(link('Биография: '+people.get(id),'#/people/'+id));
      detail.append(card);
    }
    const chronology=data.events.filter(e=>matchesSelectedPeriod(e));
    const section=el('section','smuta-events');
    section.append(el('h3',null,whole?'События периода':selectedMonth?
        'События за '+period:'События '+year+' года'),
      el('p',null,'Документированные события всего раздела; не каждое локализовано до города.'));
    for(const e of chronology){const card=el('article','smuta-event');card.dataset.event=e.id;
      card.append(el('small',null,date(e.date)),el('h4',null,e.title),el('p',null,e.summary),el('p','smuta-limit',e.caveat));
      const refs=el('div','smuta-citations');cite(refs,e.sources);card.append(refs);
      if(e.person_id&&people.has(e.person_id))card.append(link('Биография: '+people.get(e.person_id),'#/people/'+e.person_id));section.append(card);}
    if(!chronology.length)section.append(el('p',null,'За этот период отдельных датированных событий пока не внесено.'));
    if(selectedMonth&&!whole){
      const other=data.events.filter(e=>Number(e.date.value.slice(0,4))===year&&e.date.precision==='year');
      if(other.length){
        const note=el('div','smuta-year-events');
        note.append(el('h4',null,'События только с годовой датировкой · '+other.length),
          el('p',null,'Не относятся автоматически к выбранному месяцу.'));
        for(const e of other){
          const n=el('article','smuta-year-event');n.append(el('strong',null,e.title),el('p',null,e.caveat));
          const refs=el('div','smuta-citations');cite(refs,e.sources);n.append(refs);note.append(n);
        }
        section.append(note);
      }
    }
    detail.append(section);
  }
  // Native pointer capture: one finger pans, two fingers zoom. Pins remain buttons.
  const pointers=new Map();let gesture=null;
  plot.addEventListener('pointerdown',e=>{
    if(e.target.closest('button')||e.button>0)return;
    pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});plot.setPointerCapture(e.pointerId);
    const v=[...pointers.values()];gesture={view:{...view},start:v.map(p=>({...p})),dims:dimensions()};
  });
  plot.addEventListener('pointermove',e=>{
    if(!pointers.has(e.pointerId)||!gesture)return;pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});const v=[...pointers.values()];
    if(v.length===1&&gesture.start.length===1){view.lon=gesture.view.lon-(v[0].x-gesture.start[0].x)/(gesture.dims.s*gesture.dims.c);view.lat=gesture.view.lat+(v[0].y-gesture.start[0].y)/gesture.dims.s;}
    else if(v.length===2&&gesture.start.length===2){const distance=a=>Math.hypot(a[0].x-a[1].x,a[0].y-a[1].y);view.zoom=Math.max(.7,Math.min(24,gesture.view.zoom*distance(v)/Math.max(1,distance(gesture.start))));}
    schedule();
  });
  const stop=e=>{pointers.delete(e.pointerId);gesture=null;if(plot.hasPointerCapture(e.pointerId))plot.releasePointerCapture(e.pointerId);};
  plot.addEventListener('pointerup',stop);plot.addEventListener('pointercancel',stop);
  plot.addEventListener('wheel',e=>{e.preventDefault();zoomBy(e.deltaY<0?1.15:1/1.15);},{passive:false});
  plot.addEventListener('keydown',e=>{if(e.target!==plot)return;const step=.6/view.zoom;const moves={ArrowLeft:[-step,0],ArrowRight:[step,0],ArrowUp:[0,step],ArrowDown:[0,-step]};
    if(moves[e.key]){e.preventDefault();view.lon+=moves[e.key][0];view.lat+=moves[e.key][1];schedule();}else if(['+','=','-','0'].includes(e.key)){e.preventDefault();if(e.key==='0')fit();else zoomBy(e.key==='-'?.7:1.4);}});
  slider.addEventListener('input',schedule);
  window.addEventListener('hashchange',()=>requestAnimationFrame(readState));
  window.addEventListener('popstate',()=>requestAnimationFrame(readState));
  window.addEventListener('atlas:route',()=>requestAnimationFrame(readState));
  new ResizeObserver(schedule).observe(plot);
  readState();
  fetch('./smuta-map.json',{cache:'no-cache'}).then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json();}).then(d=>{
    if(d.schema_version!==1||d.coordinate_kind!=='modern_reference_only'||
      d.historical_borders_verified!==false||!Array.isArray(d.places)||
      !Array.isArray(d.evidence)||!Array.isArray(d.formal_year_overlaps)||
      d.hydrography?.kind!=='modern_hydrography_reference'||
      d.hydrography?.historical_hydrography_verified!==false||
      !Array.isArray(d.hydrography?.rivers))throw Error('Неверный контракт карты');
    data=d;sources=new Map(d.sources.map(s=>[s.id,s]));events=new Map(d.events.map(e=>[e.id,e]));people=new Map(d.people.map(p=>[p.id,p.name]));
    hydroAttribution.append(link('Natural Earth 1:10m · общественное достояние',d.hydrography.source.url,true));
    city.append(el('option',null,'Все места'));city.options[0].value='';
    for(const p of d.places){const o=el('option',null,p.name);o.value=p.id;city.append(o);p.evidence_ids.forEach(id=>mapped.set(id,p.id));}
    const missing=el('option',null,'Без точной привязки');missing.value='unlocated';city.append(missing);
    readState();if(selected)setMobile(true);schedule();
  }).catch(e=>{error=e.message;schedule();});
})();
