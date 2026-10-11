/* Europe 1762–1800: sourced network in two append-only historical layers, no nationality inference.
   Other centuries and the original ?world=1762 sheet remain untouched. */
(() => {
  'use strict';
  if (!document.getElementById('chronology-data')) return;
  const create=(tag,className,text)=>{
    const n=document.createElement(tag);
    if(className)n.className=className;
    if(text!==undefined)n.textContent=String(text);
    return n;
  };
  const ns='http://www.w3.org/2000/svg';
  const svgNode=(tag,attrs,text)=>{
    const n=document.createElementNS(ns,tag);
    for(const [k,v] of Object.entries(attrs||{}))n.setAttribute(k,String(v));
    if(text!==undefined)n.textContent=String(text);
    return n;
  };
  const layer=create('div','dynasty-layer');
  layer.hidden=true;
  const dialog=create('section','dynasty-dialog');
  dialog.setAttribute('role','dialog');
  dialog.setAttribute('aria-modal','true');
  dialog.setAttribute('aria-labelledby','dynasty-title');
  const head=create('header','dynasty-head');
  const headText=create('div','dynasty-head-text');
  headText.append(
    create('span','dynasty-eyebrow','Историческая сеть · 1762–1800'),
    create('h2','dynasty-title','Династические связи Европы')
  );
  headText.querySelector('h2').id='dynasty-title';
  const close=create('button','dynasty-close','Закрыть ×');
  close.type='button';
  close.setAttribute('aria-label','Закрыть династическую сеть');
  head.append(headText,close);
  const content=create('div','dynasty-content');
  const lede=create('p','dynasty-lede','Один человек может занимать должности в разных государствах. Браки, соправительство и наследование показаны отдельными типами связей.');
  const timeline=create('div','dynasty-timeline');
  const yearRow=create('div','dynasty-year-row');
  const back=create('button','dynasty-step','←');
  back.type='button';
  back.setAttribute('aria-label','Предыдущий год');
  const yearOutput=create('strong','dynasty-year','1762');
  yearOutput.id='dynasty-year';
  const forward=create('button','dynasty-step','→');
  forward.type='button';
  forward.setAttribute('aria-label','Следующий год');
  yearRow.append(back,yearOutput,forward);
  const rangeLabel=create('label','dynasty-slider-label');
  rangeLabel.append(create('span',null,'1762'),create('span',null,'1800'));
  const slider=create('input','dynasty-year-range');
  slider.id='dynasty-year-range';
  slider.type='range';
  slider.min='1762';
  slider.max='1800';
  slider.step='1';
  slider.value='1762';
  slider.setAttribute('aria-label','Выбранный год в международном атласе');
  const milestones=create('div','dynasty-milestones');
  milestones.setAttribute('aria-label','Исторические годы');
  timeline.append(yearRow,slider,rangeLabel,milestones);
  const colorControls=create('div','dynasty-color-controls');
  colorControls.setAttribute('role','group');
  colorControls.setAttribute('aria-label','Окраска династической сети');
  const colorButtons=new Map();
  const modeNames=[['state','Государства'],['dynasty','Династии'],['origin','Происхождение']];
  let colorMode='state';
  for(const [key,label] of modeNames) {
    const b=create('button','dynasty-color-mode',label);
    b.type='button';
    b.dataset.dynastyMode=key;
    b.setAttribute('aria-pressed',String(key===colorMode));
    b.addEventListener('click',()=>{
      colorMode=key;
      for(const [id,node] of colorButtons)node.setAttribute('aria-pressed',String(id===key));
      render();
    });
    colorButtons.set(key,b);
    colorControls.append(b);
  }
  const notice=create('p','dynasty-notice','Загружаем исторические свидетельства…');
  notice.setAttribute('role','status');
  notice.setAttribute('aria-live','polite');
  const graphicTitle=create('h3','dynasty-section-title','Граф связей');
  const countryJump=create('nav','dynasty-country-jump');
  countryJump.setAttribute('aria-label','Быстрый переход к государству на графе');
  countryJump.hidden=true;
  const graphContainer=create('div','dynasty-graph-scroll');
  graphContainer.setAttribute('role','region');
  graphContainer.setAttribute('aria-label','Граф родственных и династических отношений с горизонтальной прокруткой');
  graphContainer.tabIndex=0;
  const key=create('div','dynasty-legend');
  const keys=[
    ['marriage','Брак'],['parent','Родство'],['succession','Смена престола'],
    ['co_regency','Соправительство'],['personal_union','Личная уния государств']
  ];
  keys.forEach(([id,label])=>{
    const el=create('span','dynasty-legend-item',label);
    el.dataset.relationKind=id;
    key.append(el);
  });
  const graphNote=create('p','dynasty-graph-note',
    'Узел — человек, линии — разные типы связей. По нажатию на узел можно перейти к подробностям. Пунктир договора — межгосударственное событие, не родство.');
  // Two presentations over the SAME sourced role database. The familiar
  // personal graph remains the default; the new dynasty-by-country view has
  // its own deep link (?dynView=houses).
  const viewSwitch=create('div','dynasty-view-switch');
  viewSwitch.setAttribute('role','group');
  viewSwitch.setAttribute('aria-label','Способ представления международной истории');
  const networkViewButton=create('button','dynasty-view-button','Люди и связи');
  const housesViewButton=create('button','dynasty-view-button','Династии × государства');
  const coverageViewButton=create('button','dynasty-view-button','Покрытие базы');
  networkViewButton.type=housesViewButton.type=coverageViewButton.type='button';
  networkViewButton.dataset.dynastyView='network';
  housesViewButton.dataset.dynastyView='houses';
  coverageViewButton.dataset.dynastyView='coverage';
  viewSwitch.append(networkViewButton,housesViewButton,coverageViewButton);
  const networkPanel=create('section','dynasty-person-graph-panel');
  networkPanel.append(graphicTitle,key,countryJump,graphContainer,graphNote);
  const footprintPanel=create('section','dynasty-footprint-panel');
  footprintPanel.hidden=true;
  footprintPanel.setAttribute('aria-label','Династические дома по государствам и годам');
  const footprintLead=create('p','dynasty-footprint-lead',
    'Горизонтальные полосы — источниковые сроки, не непрерывная фактическая власть. Одна семья в разных государствах не означает общий кабинет или общую национальность.');
  const footprintTools=create('div','dynasty-footprint-tools');
  const showSecondaryInput=create('input');
  showSecondaryInput.id='dynasty-show-secondary';
  showSecondaryInput.type='checkbox';
  const showSecondaryLabel=create('label','dynasty-show-secondary');
  showSecondaryLabel.htmlFor=showSecondaryInput.id;
  showSecondaryLabel.append(showSecondaryInput,
    create('span',null,'Также показывать консортов, регентов, соправителей и императорский титул'));
  footprintTools.append(showSecondaryLabel);
  const footprintSummary=create('div','dynasty-footprint-summary');
  footprintSummary.setAttribute('role','status');
  footprintSummary.setAttribute('aria-live','polite');
  const footprintScroll=create('div','dynasty-footprint-scroll');
  footprintScroll.setAttribute('role','region');
  footprintScroll.setAttribute('aria-label','Временная диаграмма четырёх династических домов; горизонтальная прокрутка');
  footprintScroll.tabIndex=0;
  const footprintRows=create('div','dynasty-footprint-rows');
  footprintScroll.append(footprintRows);
  const footprintLegend=create('p','dynasty-footprint-legend',
    'Сплошная полоса — правящая должность. Штриховая — родственная линия или дополнительная роль. Серые пустоты — неполнота нашей выборки.');
  const footprintDetail=create('article','dynasty-footprint-detail');
  footprintDetail.tabIndex=-1;
  footprintDetail.setAttribute('aria-label','Источники выбранной династической полосы');
  // Put the actual diagram BEFORE the explanatory prose, so it is visible
  // on a small phone instead of being pushed below the first screen.
  footprintPanel.append(footprintTools,footprintScroll,footprintLegend,
    footprintSummary,footprintDetail,footprintLead);
  // A third source-aware view: coverage of the RESEARCH REGISTER,
  // not a historical claim that a country did or did not have a ruler.
  const coveragePanel=create('section','dynasty-coverage-panel');
  coveragePanel.hidden=true;
  coveragePanel.setAttribute('aria-label','Покрытие исторической базы по странам и годам');
  const coverageIntro=create('p','dynasty-coverage-intro',
    'Матрица отмечает наличие юридических и институциональных записей, а не полноту исторической науки. Пустые годы исследования не означают отсутствия правителя.');
  const coverageOverview=create('p','dynasty-coverage-overview');
  coverageOverview.setAttribute('role','status');
  coverageOverview.setAttribute('aria-live','polite');
  const coverageLegend=create('div','dynasty-coverage-legend');
  const coverageStatusLabels=[
    ['office','Должность главы / императора'],
    ['institution','Коллективный орган'],
    ['supplementary','Дополнительная роль'],
    ['research_gap','Пробел в реестре'],
    ['outside_sample','Вне нашей выборки'],
    ['historically_not_in_force','Режим ещё не возник / прекращён'],
    ['birthplace_context','Только место рождения']
  ];
  coverageStatusLabels.forEach(([status,label])=>{
    const item=create('span','dynasty-coverage-legend-item',label);
    item.dataset.coverageStatus=status;
    coverageLegend.append(item);
  });
  const coverageScroll=create('div','dynasty-coverage-scroll');
  coverageScroll.tabIndex=0;
  coverageScroll.setAttribute('role','region');
  coverageScroll.setAttribute('aria-label','Матрица покрытия реестра: 13 политических контекстов на 39 лет, горизонтальная прокрутка');
  const coverageTable=create('div','dynasty-coverage-table');
  coverageScroll.append(coverageTable);
  const coverageDetail=create('section','dynasty-coverage-detail');
  coverageDetail.id='dynasty-coverage-detail';
  coverageDetail.setAttribute('aria-label','Источники и статус выбранного года и страны');
  coverageDetail.tabIndex=-1;
  const coverageTasks=create('section','dynasty-coverage-tasks');
  const coverageMethod=create('p','dynasty-coverage-method',
    'Одна длинная должность даёт много отмеченных годов. Ни одна ячейка не доказывает, что все документы эпохи изучены. Страны, которых ещё нет в данной исследовательской партии, не окрашены как исторически отсутствовавшие.');
  coveragePanel.append(coverageIntro,coverageOverview,coverageLegend,
    coverageScroll,coverageDetail,coverageTasks,coverageMethod);
  let selectedView='network';
  let showSecondary=false;
  let selectedFootprint=null;
  let lastCenteredFootprintYear=null;
  const modeFromUrl=()=>{
    const candidate=new URL(location.href).searchParams.get('dynView');
    return ['houses','coverage'].includes(candidate)?candidate:'network';
  };
  function updateView(){
    networkPanel.hidden=selectedView!=='network';
    footprintPanel.hidden=selectedView!=='houses';
    coveragePanel.hidden=selectedView!=='coverage';
    // These palette controls belong to the personal graph only: dynasty
    // colors in the matrix are fixed house identifiers, never ethnicity.
    colorControls.hidden=selectedView!=='network';
    notice.hidden=selectedView!=='network';
    for(const button of [networkViewButton,housesViewButton,coverageViewButton]){
      button.setAttribute('aria-pressed',String(button.dataset.dynastyView===selectedView));
    }
    if(selectedView==='houses' && footprints && data && extension)renderFootprints();
    if(selectedView==='coverage' && coverage && data && extension)renderCoverage();
  }
  function setView(next,push){
    if(!['network','houses','coverage'].includes(next))return;
    selectedView=next;
    if(isNetworkURL()){
      const url=new URL(location.href);
      if(next==='houses'||next==='coverage')url.searchParams.set('dynView',next);
      else url.searchParams.delete('dynView');
      history[push?'pushState':'replaceState'](null,'',url.pathname+url.search+url.hash);
    }
    updateView();
  }
  networkViewButton.addEventListener('click',()=>setView('network',true));
  housesViewButton.addEventListener('click',()=>setView('houses',true));
  coverageViewButton.addEventListener('click',()=>setView('coverage',true));
  showSecondaryInput.addEventListener('change',()=>{
    showSecondary=showSecondaryInput.checked;
    selectedFootprint=null;
    renderFootprints();
  });
  const timelineTitle=create('h3','dynasty-section-title','События выбранного года');
  const events=create('section','dynasty-events');
  const institutionsTitle=create('h3','dynasty-section-title','Должности по государствам');
  const polities=create('div','dynasty-polities');
  const participantsTitle=create('h3','dynasty-section-title','Люди, династии и происхождение');
  const persons=create('div','dynasty-persons');
  const relationsTitle=create('h3','dynasty-section-title','Подтверждённые связи');
  const relations=create('div','dynasty-relations');
  const caveats=create('details','dynasty-caveats');
  caveats.append(create('summary',null,'Как читать эту диаграмму?'));
  const caveatList=create('ul');
  caveats.append(caveatList);
  const original=create('a','dynasty-previous','← Открыть исходный пилот 1762 года');
  original.href='?world=1762#/timeline/1762';
  content.append(lede,timeline,colorControls,notice,viewSwitch,
    networkPanel,footprintPanel,coveragePanel,timelineTitle,events,institutionsTitle,
    polities,participantsTitle,persons,relationsTitle,relations,caveats,original);
  dialog.append(head,content);
  layer.append(dialog);
  document.body.append(layer);

  let data=null,base=null,atlas=null,extension=null,footprints=null,coverage=null,pending=null,previousFocus=null;
  let year=1762;
  const abbr={
    ru:'Россия',fr:'Франция',pr:'Пруссия',gb:'Великобритания',
    han:'Ганновер',hab:'Габсбурги',hre:'Римская империя',meck:'Мекленбург',
    es:'Испания',pt:'Португалия',sw:'Швеция',tusc:'Тоскана',frrep:'Французская республика'
  };
  const familyPalette={
    romanov:'#6884ae','holstein-gottorp':'#8167a5',
    'anhalt-zerbst':'#c18d57',bourbon:'#4c78ad',
    hohenzollern:'#679a78',hanover:'#9c8056',mecklenburg:'#698d9a',
    habsburg:'#bd688b','habsburg-lorraine':'#9d609a',lorraine:'#8b82ab',
    braganza:'#398875'
  };
  const edgePalette={
    marriage:'#926baa',parent:'#b08755',succession:'#318b78',
    imperial_succession:'#318b78',co_regency:'#5e91ad',
    personal_union:'#6a66a9',treaty:'#a3754a',regency:'#5380ad',
    regime_change:'#a56a4b',institutional_change:'#6f8c88'
  };
  const positions={
    'ru-elizabeth':[115,120],
    'ru-peter3':[115,290],
    'ru-catherine2':[115,460],
    'fr-louis15':[385,120],
    'fr-louis16':[385,290],
    'fr-antoinette':[575,460],
    'pr-frederick2':[660,120],
    'gb-george3':[930,120],
    'gb-charlotte':[930,290],
    'hab-maria':[1190,120],
    'hre-francis':[1420,290],
    'hre-joseph':[1190,460]
  };
  const isActive=(r,y)=>r.start_year<=y && y<=r.end_year;
  const allPeople=()=>[
    ...(base?.persons||[]),...(data?.additional_persons||[]),
    ...(extension?.additional_persons||[])
  ];
  const allPolities=()=>[
    ...(base?.countries||[]),...(data?.additional_polities||[]),
    ...(extension?.additional_polities||[])
  ].map(p=>({...p,name:p.name||p.label})).filter(p=>
    (!p.introduced_from||year>=p.introduced_from) &&
    !(p.id==='fr' && year>1792)
  );
  const getPerson=id=>allPeople().find(p=>p.id===id);
  const getPolity=id=>allPolities().find(p=>p.id===id);
  const validLink=url=>{
    try{
      const u=new URL(url);
      return u.protocol==='https:' && !u.username && !u.password &&
        ![['drive','.google.com'].join(''),['docs','.google.com'].join('')].includes(u.hostname);
    }catch(_){return false;}
  };
  function sources(ids) {
    const wrap=create('div','dynasty-sources');
    const index=new Map([...(base?.sources||[]),...(data?.sources||[]),
      ...(extension?.sources||[]),...(footprints?.sources||[]),
      ...(coverage?.sources||[]),...(atlas?.sources||[])].map(s=>[s.id,s]));
    [...new Set(ids||[])].forEach(id=>{
      const source=index.get(id);
      if(!source||!validLink(source.url))return;
      const a=create('a','dynasty-source',id+' ↗');
      a.href=source.url;a.target='_blank';a.rel='noopener noreferrer';
      a.title=source.title||id;
      wrap.append(a);
    });
    return wrap;
  }
  function actorName(actor){
    const canonical=(atlas?.people||[]).find(p=>p.id===actor.canonical_person_id);
    return canonical?.name || actor.name || 'Личность не установлена';
  }
  function actorHouses(actor) {
    if(actor.houses)return actor.houses;
    return actor.dynasty?[{
      id:actor.dynasty.id,name:actor.dynasty.name,
      qualifier:actor.dynasty.qualifier,source_ids:actor.dynasty.sources
    }]:[];
  }
  function actorOrigin(actor) {
    // No guessing ethnicity from birth, citizenship, dynasty, country or name.
    const match=(atlas?.person_facts||[]).find(f=>
      actor.canonical_person_id &&
      f.id===actor.ethnic_origin_fact_id &&
      f.person_id===actor.canonical_person_id &&
      f.kind==='ethnic_origin' &&
      f.verification==='reference_checked');
    return match||null;
  }
  function activeRoles(){
    return [...(data?.roles||[]),...(extension?.additional_roles||[])]
      .filter(r=>isActive(r,year));
  }
  function activeInstitutions(){
    return (extension?.institutions||[]).filter(r=>isActive(r,year));
  }
  function activeIds(){return new Set(activeRoles().map(r=>r.person_id));}
  function activeRelations() {
    const people=activeIds();
    return [...(data?.relations||[]),...(extension?.additional_relations||[])]
      .filter(r=>isActive(r,year) && (r.subjects||[]).every(id=>people.has(id)));
  }
  function mainHouse(actor){
    const h=actorHouses(actor);
    return h.find(x=>x.id==='habsburg-lorraine')||h[0];
  }
  function colorFor(actor) {
    if(colorMode==='origin')return actorOrigin(actor)?'#9869aa':'#8e9594';
    if(colorMode==='dynasty')return familyPalette[mainHouse(actor)?.id]||'#8e9594';
    const roles=activeRoles().filter(r=>r.person_id===actor.id);
    return getPolity(roles[0]?.polity_id)?.color||'#8e9594';
  }
  function swatchesFor(actor) {
    const sw=create('span','dynasty-role-swatches');
    [...new Set(activeRoles().filter(r=>r.person_id===actor.id).map(r=>r.polity_id))]
      .forEach(id=>{
        const dot=create('i','dynasty-state-dot');
        dot.title=getPolity(id)?.name||id;
        dot.style.background=getPolity(id)?.color||'#777';
        sw.append(dot);
      });
    return sw;
  }
  function titleFor(role){
    if(role.id==='dn-pr-frederick2' && year>=1772)return 'Король Пруссии';
    return role.title;
  }
  // The original year graph keeps its reviewed positions. Later years use
  // a data-driven layout that places one PERSON once, regardless of offices.
  function layoutForYear(){
    if(year<=1780)return {positions, width:1540,height:590,groups:[],institutions:[]};
    const groups=[
      ['ru','Россия'],['fr','Франция'],['pr','Пруссия'],['gb','Великобритания / Ганновер'],
      ['hab','Габсбургские владения / Империя'],
      ['es','Испания'],['pt','Португалия'],['sw','Швеция']
    ];
    const groupKey=id=>
      id==='han'?'gb':id==='hre'||id==='tusc'?'hab':
      id==='frrep'?'fr':id;
    const occupied=new Map(groups.map(([id])=>[id,[]]));
    for(const person of allPeople()){
      const roles=activeRoles().filter(r=>r.person_id===person.id);
      if(!roles.length)continue;
      const chosen=roles.find(r=>r.role_kind==='sovereign'||r.role_kind==='emperor')||roles[0];
      const key=groupKey(chosen.polity_id);
      if(occupied.has(key))occupied.get(key).push(person.id);
    }
    const icons=(activeInstitutions()||[]).map(i=>({
      ...i,group:groupKey(i.polity_id)
    }));
    const nodes={};
    let longest=0;
    groups.forEach(([id],index)=>{
      const people=occupied.get(id)||[];
      const corp=icons.filter(i=>i.group===id);
      const total=people.length+corp.length;
      longest=Math.max(longest,total);
      const cx=155+index*255;
      people.forEach((pid,row)=>{nodes[pid]=[cx,134+row*145];});
      corp.forEach((institution,row)=>{institution.x=cx;institution.y=134+(people.length+row)*145;});
    });
    return {
      positions:nodes,width:groups.length*255+65,
      height:Math.max(500,195+Math.max(longest,2)*145),
      groups,institutions:icons
    };
  }
  function drawGraph(){
    const layout=layoutForYear();
    const positions=layout.positions;
    const canvas=svgNode('svg',{
      viewBox:'0 0 '+layout.width+' '+layout.height,
      width:layout.width,height:layout.height,
      role:'img',
      'aria-label':'Источник: граф людей, институтов, родства, переходов и отдельных государственных должностей по выбранному году'
    });
    // Inline width is intentional: >1780 has eight state columns. The container,
    // not the page, handles sideways touch/keyboard scrolling.
    canvas.style.width=layout.width+'px';
    canvas.style.height=layout.height+'px';
    if(layout.groups.length){
      layout.groups.forEach(([id,label],index)=>{
        const cx=155+index*255;
        canvas.append(svgNode('rect',{
          x:cx-120,y:62,width:240,height:layout.height-112,rx:12,
          fill:index%2===0?'#f3f6f2':'#f8f8f4',stroke:'#dce5db','stroke-width':1
        }));
        canvas.append(svgNode('text',{
          x:cx,y:44,'text-anchor':'middle','font-size':13,
          'font-weight':750,fill:'#40584b'
        },label.length>22?label.slice(0,22)+'…':label));
      });
    }
    canvas.append(svgNode('title',{},'Династические связи Европы · '+year));
    canvas.append(svgNode('desc',{},'Узел — отдельная личность, двойная государственная роль Георга III сохраняется в одной вершине. Связи имеют различные значения и источники.'));
    const people=activeIds();
    const rels=activeRelations();
    // Edges follow explicitly cited relationship records; never generated from surnames.
    rels.forEach(r=>{
      if(r.subjects?.length!==2)return;
      const a=positions[r.subjects[0]],b=positions[r.subjects[1]];
      if(!a||!b)return;
      const color=edgePalette[r.kind]||'#777';
      const dy=Math.abs(a[1]-b[1]);
      const dx=b[0]-a[0];
      const lift=dy===0?38:35;
      const path=svgNode('path',{
        d:'M'+a[0]+' '+a[1]+' Q'+((a[0]+b[0])/2)+' '+((a[1]+b[1])/2-lift)+' '+b[0]+' '+b[1],
        fill:'none',stroke:color,'stroke-width':r.kind==='marriage'?3:2.3,
        'stroke-dasharray':r.kind==='parent'?'5 4':r.kind==='co_regency'?'2 4':'',
        opacity:.84
      });
      path.append(svgNode('title',{},r.title+' · '+(r.source_ids||[]).join(', ')));
      canvas.append(path);
    });
    if(year===1762) {
      // Treaty connects political entities, NOT two royal family members.
      const banner=svgNode('g',{},null);
      banner.append(svgNode('rect',{x:160,y:14,width:420,height:35,rx:9,fill:'#f3eee3',stroke:'#c2a274'}));
      banner.append(svgNode('text',{x:370,y:37,'text-anchor':'middle',
        fill:'#755634','font-size':14,'font-weight':700},'Договор Россия — Пруссия, 1762 · не родство'));
      canvas.append(banner);
    }
    for(const actor of allPeople()) {
      if(!people.has(actor.id))continue;
      const center=positions[actor.id];
      if(!center)continue;
      const [x,y]=center;
      const ink=colorFor(actor),group=svgNode('g',{
        role:'button',tabindex:'0','data-actor-id':actor.id,
        'aria-label':actorName(actor)+'. Открыть карточку и источники.'
      });
      group.append(svgNode('rect',{x:x-98,y:y-38,width:196,height:79,rx:12,
        fill:'#fffefa',stroke:ink,'stroke-width':3}));
      // Abbreviations are purely visual; full sourced names remain in cards.
      const title=({
        'gb-charlotte':'Шарлотта', 'hre-francis':'Франц I',
        'ru-peter3':'Пётр III', 'ru-catherine2':'Екатерина II',
        'fr-antoinette':'Мария-Антуанетта',
        'hab-maria':'Мария Терезия',
        'sw-charles':'Герцог Карл', 'pt-carlota':'Карлота Жоакина',
        'hab-maria-luisa':'Мария Луиза', 'pr-fw2':'Фридрих Вильгельм II',
        'pr-fw3':'Фридрих Вильгельм III', 'sw-gustav3':'Густав III',
        'sw-gustav4':'Густав IV Адольф', 'hab-leopold':'Леопольд II',
        'hab-francis2':'Франц II', 'ru-paul1':'Павел I',
        'pt-joao':'Жуан', 'pt-maria1':'Мария I', 'pt-pedro3':'Педру III',
        'es-carlos3':'Карл III', 'es-carlos4':'Карл IV',
        'fr-napoleon':'Бонапарт'
      }[actor.id]) || actorName(actor)
        .replace('Алексеевна','').replace('Петровна','');
      group.append(svgNode('text',{x,y:y-8,'text-anchor':'middle',
        fill:'#28382f','font-size':title.length>18?11.5:14,'font-weight':750},title));
      const ownRoles=activeRoles().filter(r=>r.person_id===actor.id);
      const lead=ownRoles.find(r=>r.role_kind==='sovereign'||r.role_kind==='emperor')||ownRoles[0];
      const shortRole=lead?.role_kind==='consort'?'Консорт':
        lead?.role_kind==='co_regent'?'Соправительство':
        lead?.role_kind==='heir'?'Наследник':
        lead?.role_kind==='emperor'?'Император':
        lead?.role_kind==='regent'?'Регент':
        lead?.role_kind==='first_consul'?'Первый консул':
        lead?.role_kind==='dynastic_person'?'Член династии':'Правитель';
      group.append(svgNode('text',{x,y:y+13,'text-anchor':'middle',
        fill:'#607167','font-size':12},shortRole));
      const codes=[...new Set(ownRoles.map(r=>r.polity_id))];
      group.append(svgNode('text',{x,y:y+31,'text-anchor':'middle',
        fill:ink,'font-size':11,'font-weight':700},codes.map(id=>abbr[id]||id).join(' · ')));
      group.addEventListener('click',()=>{
        const node=persons.querySelector('[data-person-id="'+actor.id+'"]');
        if(node){node.scrollIntoView({block:'center',behavior:'auto'});node.focus({preventScroll:true});}
      });
      group.addEventListener('keydown',event=>{
        if(event.key==='Enter'||event.key===' '){event.preventDefault();group.dispatchEvent(new MouseEvent('click',{bubbles:true}));}
      });
      canvas.append(group);
    }
    for(const institution of layout.institutions){
      const {x,y}=institution;
      const node=svgNode('g',{
        role:'button',tabindex:'0','data-institution-id':institution.id,
        'aria-label':institution.name+' — коллективное учреждение. Перейти к источникам.'
      });
      node.append(svgNode('rect',{
        x:x-99,y:y-38,width:198,height:78,rx:6,fill:'#e6edf1',
        stroke:'#547c86','stroke-width':2.5,'stroke-dasharray':'5 4'
      }));
      node.append(svgNode('text',{
        x,y:y-4,'text-anchor':'middle','font-size':14,'font-weight':750,
        fill:'#2b5664'
      },institution.name));
      node.append(svgNode('text',{
        x,y:y+19,'text-anchor':'middle','font-size':12,fill:'#426878'
      },'Институт · не монарх'));
      const focus=()=>{
        const card=polities.querySelector('[data-institution-id="'+institution.id+'"]');
        if(card){card.scrollIntoView({block:'center',behavior:'auto'});card.focus({preventScroll:true});}
      };
      node.addEventListener('click',focus);
      node.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();focus();}});
      canvas.append(node);
    }
    if(!people.size && !layout.institutions.length)canvas.append(svgNode('text',{
      x:layout.width/2,y:layout.height/2,'text-anchor':'middle','font-size':20
    },'На этот год исследованных ролей нет'));
    return canvas;
  }
  function renderEvents(){
    const records=[...(data?.milestones||[]),...(extension?.milestones||[])]
      .filter(e=>e.year===year);
    events.replaceChildren();
    if(!records.length)events.append(create('p','dynasty-empty','Для этого года в пилоте нет отдельного исследованного перехода. Это не означает отсутствия событий.'));
    for(const record of records){
      const card=create('article','dynasty-event');
      card.append(create('h4',null,record.title),create('p',null,record.description),
        sources(record.source_ids));
      events.append(card);
    }
  }
  function renderPolities(){
    const roles=activeRoles();
    polities.replaceChildren();
    const people=new Map(allPeople().map(p=>[p.id,p]));
    for(const p of allPolities()){
      const article=create('section','dynasty-polity');
      article.dataset.polity=p.id;
      article.style.setProperty('--dynasty-polity-color',p.color);
      const head=create('h4',null,p.name);
      article.append(head);
      const here=roles.filter(r=>r.polity_id===p.id);
      for(const r of here){
        const person=people.get(r.person_id);
        const item=create('div','dynasty-office');
        item.dataset.roleKind=r.role_kind;
        const name=create('strong',null,actorName(person));
        const line=create('span',null,titleFor(r));
        item.append(name,line);
        if(r.role_kind==='consort')item.append(create('em','dynasty-role-qualifier','Не правящий монарх'));
        if(r.role_kind==='co_regent')item.append(create('em','dynasty-role-qualifier','Соправительство ≠ единоличное правление'));
        if(r.role_kind==='regent')item.append(create('em','dynasty-role-qualifier','Регент, не новый самостоятельный монарх'));
        if(r.role_kind==='dynastic_person')item.append(create('em','dynasty-role-qualifier','Член династии, без правящего титула'));
        if(r.role_kind==='first_consul')item.append(create('em','dynasty-role-qualifier','Республиканская должность, не император'));
        if(r.actual_start_year) item.append(create('span','dynasty-role-start','Полный срок начался в '+r.actual_start_year+'; наш охват с '+r.start_year));
        item.append(sources(r.source_ids));
        article.append(item);
      }
      for(const institution of activeInstitutions().filter(i=>i.polity_id===p.id)) {
        const item=create('div','dynasty-office dynasty-institution');
        item.dataset.roleKind='institution';
        item.dataset.institutionId=institution.id;
        item.tabIndex=-1;
        item.append(create('strong',null,institution.name),
          create('span',null,'Коллективный / институциональный орган, не отдельный монарх'),
          create('p','dynasty-person-note',institution.note),sources(institution.source_ids));
        article.append(item);
      }
      if(!here.length && !activeInstitutions().some(i=>i.polity_id===p.id)) article.append(create('p','dynasty-empty',
        p.kind==='birthplace_context_only'?
          'Представлено как историческое место рождения, не как ещё один британский престол.':
          'Политических должностей в этом году в пилоте нет; это пробел, не историческое отрицание.'));
      article.append(create('p','dynasty-polity-note',p.note||'Даты и полномочия сохраняют исходную точность.'));
      polities.append(article);
    }
  }
  function renderPersons(){
    const active=activeIds(),roles=activeRoles();
    persons.replaceChildren();
    for(const p of allPeople().filter(p=>active.has(p.id))){
      const card=create('article','dynasty-person');
      card.dataset.personId=p.id;
      card.tabIndex=-1;
      card.style.setProperty('--dynasty-person-color',colorFor(p));
      const name=create('h4',null,actorName(p));
      name.append(swatchesFor(p));
      card.append(name);
      const own=roles.filter(r=>r.person_id===p.id);
      card.append(create('p','dynasty-person-role',own.map(titleFor).join(' · ')));
      if(p.canonical_person_id){
        const link=create('a','dynasty-person-link','Биография основного атласа ↗');
        link.href='#/people/'+encodeURIComponent(p.canonical_person_id);
        link.addEventListener('click',()=>closeSheet(false));
        card.append(link);
      }
      const facts=create('dl','dynasty-facts');
      const add=(label,value)=>{
        facts.append(create('dt',null,label),create('dd',null,value));
      };
      add('Должности в', [...new Set(own.map(r=>getPolity(r.polity_id)?.name))].join('; '));
      add('Дом / род', actorHouses(p).map(x=>x.name+' ('+x.qualifier+')').join('; '));
      const born=p.birthplace||p.birth;
      add('Место рождения',born?.name||born?.place||'Не исследовано');
      const origin=actorOrigin(p);
      const originText=origin?.value||'Не исследовано; по месту рождения не выводится';
      const originRow=create('dd','dynasty-origin',originText);
      facts.append(create('dt',null,'Этнокультурное происхождение'),originRow);
      card.append(facts);
      const notes=create('p','dynasty-person-note',
        own.map(r=>r.note).filter(Boolean).join(' '));
      card.append(notes);
      const refs=[...(p.source_ids||p.sources||[]),
        ...own.flatMap(r=>r.source_ids||[]),
        ...actorHouses(p).flatMap(h=>h.source_ids||[]),
        ...(born?.source_ids||born?.sources||[]),
        ...(origin?.sources||[])];
      card.append(sources(refs));
      persons.append(card);
    }
  }
  function renderRelations(){
    relations.replaceChildren();
    const active=activeRelations();
    if(!active.length)relations.append(create('p','dynasty-empty','В этом году исследованные связи пока не добавлены.'));
    for(const r of active){
      const card=create('article','dynasty-relation');
      card.dataset.kind=r.kind;
      const kind={
        marriage:'Брак',parent:'Родство',personal_union:'Личная уния',
        regency:'Регентство',regime_change:'Изменение государственного строя',
        institutional_change:'Смена учреждений',
        co_regency:'Соправительство',imperial_succession:'Императорская должность',
        succession:'Смена монарха',treaty:'Межгосударственный договор'
      }[r.kind]||'Историческое отношение';
      card.append(create('span','dynasty-relation-type',kind),
        create('h4',null,r.title),create('p',null,r.note),sources(r.source_ids));
      relations.append(card);
    }
  }
  // Projection of sourced house memberships onto juridical terms. A shared
  // surname or birthplace NEVER creates a member or a political relation.
  // Only the vetted membership/source arrays authorize a new timeline bar.
  const FOOTPRINT_START=1762;
  const FOOTPRINT_END=1800;
  const FOOTPRINT_YEARS=FOOTPRINT_END-FOOTPRINT_START+1;
  const coreKinds=new Set(['sovereign','elector']);
  const additionalKinds=new Set([
    'emperor','co_regent','consort','regent','heir','dynastic_person'
  ]);
  const excludesFromStateCount=new Set(['hre','frrep','meck']);
  const fullRoles=()=>[...(data?.roles||[]),...(extension?.additional_roles||[])];
  const allJurisdictions=()=>[...(base?.countries||[]),
    ...(data?.additional_polities||[]),...(extension?.additional_polities||[])]
    .map(p=>({...p,name:p.name||p.label}));
  function segmentsForHouse(family,secondary){
    const byPolity=new Map();
    const actors=new Map(allPeople().map(p=>[p.id,p]));
    for(const member of family.members){
      const actor=actors.get(member.person_id);
      if(!actor)continue;
      for(const role of fullRoles().filter(r=>r.person_id===member.person_id)){
        if(role.end_year<FOOTPRINT_START || role.start_year>FOOTPRINT_END)
          continue;
        const isCore=coreKinds.has(role.role_kind) && member.membership!=='dynastic_union';
        const extra=additionalKinds.has(role.role_kind) || member.membership==='dynastic_union';
        if(!isCore && !(secondary&&extra))continue;
        const entry={
          role,member,actor,
          start:Math.max(FOOTPRINT_START,role.start_year),
          end:Math.min(FOOTPRINT_END,role.end_year),
          category:member.membership==='branch_lineage'?'lineage':
            !isCore?'extra':'core'
        };
        if(!byPolity.has(role.polity_id))byPolity.set(role.polity_id,[]);
        byPolity.get(role.polity_id).push(entry);
      }
    }
    const jurisdictions=new Map(allJurisdictions().map(p=>[p.id,p]));
    return [...byPolity.entries()].map(([id,bars])=>({
      polity:jurisdictions.get(id),id,
      bars:bars.sort((a,b)=>a.start-b.start||a.end-b.end)
    })).sort((a,b)=>
      (a.polity?.name||a.id).localeCompare(b.polity?.name||b.id,'ru'));
  }
  function summaryForHouse(family,selectedYear){
    const matches=family.members.flatMap(member=>
      fullRoles().filter(r=>r.person_id===member.person_id &&
        isActive(r,selectedYear) && coreKinds.has(r.role_kind) &&
        !excludesFromStateCount.has(r.polity_id))
        .map(role=>({role,member})));
    const strict=matches.filter(x=>x.member.membership==='house');
    const sovereignStates=new Set(strict.map(x=>x.role.polity_id));
    const strictPersons=new Set(strict.map(x=>x.role.person_id));
    const withLineage=new Set(matches.map(x=>x.role.polity_id));
    const names=ids=>[...ids].map(id=>allJurisdictions().find(p=>p.id===id)?.name||
      id).join(' · ');
    return {strictStates:sovereignStates.size,strictPersons:strictPersons.size,
      coreText:names(sovereignStates),
      lineageText:names(withLineage),
      lineageOnly:withLineage.size>1 && sovereignStates.size<2};
  }
  function footprintBarDetail(family,entry){
    const {role,actor,member,start,end,category}=entry;
    selectedFootprint={familyId:family.id,roleId:role.id};
    footprintDetail.replaceChildren();
    const title=create('h4',null,actorName(actor)+' · '+family.name);
    const qual=category==='lineage'
      ? 'Генеалогическая ветвь; НЕ официальный династический ярлык российской короны.'
      : category==='extra'
        ? 'Дополнительная роль / династический союз, НЕ доказательство правления этим домом.'
        : role.role_kind==='elector'?'Курфюрст, отдельная должность в Ганновере.'
        : 'Правящая юридическая должность; действительную власть исследуем отдельно.';
    footprintDetail.append(title,
      create('p',null,role.title+' · '+start+'–'+end+' годы. '+qual),
      create('p','dynasty-footprint-branch','Ветвь: '+member.branch),
      create('p','dynasty-footprint-caution',
        'Годы включены с календарной точностью источника; совпадение полос не доказывает общего дня правления.'),
      sources([...family.source_ids,...member.source_ids,...role.source_ids]));
  }
  function renderFootprints(){
    if(!footprints||!data||!base||!extension)return;
    const jurisdictionIndex=new Map(allJurisdictions().map(p=>[p.id,p]));
    const rows=create('div','dynasty-house-matrix');
    const axis=create('div','dynasty-house-axis');
    axis.append(create('div','dynasty-house-sticky-label','Династия / государство'));
    const axisYears=create('div','dynasty-house-years');
    for(const tick of [1762,1770,1780,1790,1800]){
      const item=create('span','dynasty-house-year',String(tick));
      item.style.left=((tick-FOOTPRINT_START+.5)/FOOTPRINT_YEARS*100)+'%';
      axisYears.append(item);
    }
    axis.append(axisYears);rows.append(axis);
    for(const family of footprints.families){
      const group=create('section','dynasty-house-group');
      group.dataset.familyId=family.id;
      group.style.setProperty('--dynasty-family-color',family.color);
      const label=create('h4','dynasty-house-family-title',family.name);
      const synopsis=summaryForHouse(family,year);
      if(synopsis.strictStates>=2){
        label.append(create('span','dynasty-house-multistate',
          synopsis.strictPersons===1?'Личная уния':'Несколько государств'));
      } else if(synopsis.lineageOnly){
        label.append(create('span','dynasty-house-lineage-tag','Родственные ветви'));
      }
      group.append(label);
      group.append(create('p','dynasty-house-family-note',family.description));
      const groups=segmentsForHouse(family,showSecondary);
      for(const row of groups){
        if(!row.polity)continue;
        const node=create('div','dynasty-house-row');
        node.dataset.country=row.id;
        const left=create('div','dynasty-house-sticky-label',row.polity.name);
        const bars=create('div','dynasty-house-track');
        // Same-year legal transitions must not be flattened into one reign.
        const lanes=[];
        for(const entry of row.bars){
          let lane=lanes.findIndex(end=>entry.start>end);
          if(lane<0){lane=lanes.length;lanes.push(entry.end);}
          else lanes[lane]=entry.end;
          entry.lane=lane;
        }
        bars.style.height=Math.max(49,lanes.length*44+6)+'px';
        const cursor=create('span','dynasty-house-year-cursor');
        cursor.style.left=((year-FOOTPRINT_START+.5)/FOOTPRINT_YEARS*100)+'%';
        cursor.setAttribute('aria-hidden','true');
        bars.append(cursor);
        row.bars.forEach(entry=>{
          const {role,actor,member,start,end,category}=entry;
          const button=create('button','dynasty-house-bar',actorName(actor));
          button.type='button';
          button.dataset.roleId=role.id;
          button.dataset.familyId=family.id;
          button.dataset.category=category;
          button.dataset.roleKind=role.role_kind;
          button.style.left=((start-FOOTPRINT_START)/FOOTPRINT_YEARS*100)+'%';
          button.style.width=((end-start+1)/FOOTPRINT_YEARS*100)+'%';
          button.style.top=(3+entry.lane*44)+'px';
          button.title=actorName(actor)+': '+role.title+' ('+start+'–'+end+') · '+member.branch;
          button.setAttribute('aria-label',
            family.name+', '+row.polity.name+', '+actorName(actor)+', '+role.title+
            ', '+start+'–'+end+'. Показать источники.');
          if(selectedFootprint?.familyId===family.id &&
            selectedFootprint?.roleId===role.id)button.setAttribute('aria-pressed','true');
          button.addEventListener('click',()=>{
            selectedFootprint={familyId:family.id,roleId:role.id};
            if(year<start||year>end){
              chooseYear(Math.min(end,Math.max(start,year)),true);
            }else renderFootprints();
            footprintBarDetail(family,entry);
            footprintDetail.focus({preventScroll:true});
          });
          bars.append(button);
        });
        node.append(left,bars);
        group.append(node);
      }
      if(!groups.length)group.append(create('p','dynasty-house-empty',
        'В выбранной выборке нет должностных записей данного типа. Это не доказательство отсутствия семьи.'));
      rows.append(group);
    }
    footprintRows.replaceChildren(rows);
    const conclusions=create('div','dynasty-house-conclusions');
    const strict=[];
    const lineage=[];
    for(const family of footprints.families){
      const stat=summaryForHouse(family,year);
      if(stat.strictStates>=2){
        const sentence=stat.strictPersons===1?
          'личная уния: один человек занимает две должности':
          'разные представители одного дома в нескольких государствах';
        strict.push(create('p','dynasty-house-summary-line',
          family.name+': '+stat.coreText+' — '+sentence+'.'));
      }
      if(stat.lineageOnly)
        lineage.push(create('p','dynasty-house-summary-line',
          family.name+': '+stat.lineageText+
          ' — совпадают документированные родственные ветви, но не официальные имена правящих домов.'));
    }
    conclusions.append(create('h4',null,'Срез '+year+' года'));
    if(strict.length)conclusions.append(...strict);
    else conclusions.append(create('p','dynasty-house-summary-line',
      'Среди исследованных правящих должностей нет строго подтверждённого совпадения одного дома в нескольких государствах.'));
    conclusions.append(...lineage);
    conclusions.append(create('p','dynasty-house-summary-caveat',
      'Считаем только правящие должности и должность курфюрста. Император Священной Римской империи — отдельное выборное достоинство. Консорты и регенты не увеличивают число государств дома.'));
    footprintSummary.replaceChildren(conclusions);
    if(!selectedFootprint)footprintDetail.replaceChildren(create('p',null,
      'Нажмите на цветную полосу, чтобы увидеть имя, тип отношения, годы и источники. Используйте Tab и Enter для клавиатуры.'));
    // The selected year must be on screen when opening a mobile deep link
    // (e.g. 1788); do not strand the user at the historical start of 1762.
    // Re-center only if the YEAR changed, not when opening sources/toggling
    // secondary roles, so the reader may pan the matrix freely.
    if(lastCenteredFootprintYear!==year){
      const axis=footprintRows.querySelector('.dynasty-house-years');
      if(axis){
        const axisX=axis.getBoundingClientRect().left-
          footprintScroll.getBoundingClientRect().left+footprintScroll.scrollLeft;
        const yearX=axisX+(year-FOOTPRINT_START+.5)/FOOTPRINT_YEARS*axis.clientWidth;
        footprintScroll.scrollLeft=Math.max(0,yearX-footprintScroll.clientWidth*.62);
      }
      lastCenteredFootprintYear=year;
    }
  }
  function renderCountryJump(){
    // Each tab scrolls only the independent SVG viewport, not the entire page.
    countryJump.replaceChildren();
    countryJump.hidden=year<=1780;
    if(countryJump.hidden)return;
    const groups=[
      ['ru','Россия'],['fr','Франция'],['pr','Пруссия'],
      ['gb','Великобритания / Ганновер'],['hab','Габсбурги / Империя'],
      ['es','Испания'],['pt','Португалия'],['sw','Швеция']
    ];
    groups.forEach(([id,label],index)=>{
      const button=create('button','dynasty-country-button',label);
      button.type='button';
      button.dataset.country=id;
      button.setAttribute('aria-pressed',String(index===0));
      button.addEventListener('click',()=>{
        for(const item of countryJump.querySelectorAll('button'))
          item.setAttribute('aria-pressed',String(item===button));
        const x=155+index*255;
        graphContainer.scrollTo({
          left:Math.max(0,x-graphContainer.clientWidth/2),
          behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'
        });
      });
      countryJump.append(button);
    });
  }
  function render(){
    if(!data||!base||!atlas||!extension||!footprints)return;
    slider.value=String(year);
    yearOutput.textContent=String(year);
    back.disabled=year<=data.period.start;
    forward.disabled=year>=extension.full_period.end;
    const active=activeIds(),roles=activeRoles();
    notice.textContent=year+' год · '+active.size+' участников · '+roles.length+
      ' записей о должностях · '+activeInstitutions().length+' органов · '+activeRelations().length+' связей. '+
      (colorMode==='state'?'Цвет по государству':
       colorMode==='dynasty'?'Цвет по династии':'Цвет по доказанному происхождению');
    graphContainer.replaceChildren(drawGraph());
    renderCountryJump();
    if(selectedView==='houses')renderFootprints();
    renderEvents();renderPolities();renderPersons();renderRelations();
  }
  function chooseYear(value,push){
    const next=Math.max(1762,Math.min(1800,Number(value)||1762));
    year=next;
    if(isNetworkURL()){
      const u=new URL(location.href);
      u.searchParams.set('dynYear',String(year));
      history[push?'pushState':'replaceState'](null,'',u.pathname+u.search+u.hash);
    }
    render();
  }
  back.addEventListener('click',()=>chooseYear(year-1,true));
  forward.addEventListener('click',()=>chooseYear(year+1,true));
  slider.addEventListener('input',()=>chooseYear(slider.value,false));
  const isNetworkURL=()=>new URL(location.href).searchParams.get('world')==='dynasty18';
  async function load(){
    if(data&&base&&atlas&&extension&&footprints)return;
    if(pending)return pending;
    pending=Promise.all([
      fetch('./world-dynasty-18c.json',{cache:'no-cache'}).then(r=>{if(!r.ok)throw Error('network');return r.json();}),
      fetch('./world-1762.json',{cache:'no-cache'}).then(r=>{if(!r.ok)throw Error('base');return r.json();}),
      fetch('./atlas.json',{cache:'no-cache'}).then(r=>{if(!r.ok)throw Error('atlas');return r.json();}),
      fetch('./world-extension-1800.json',{cache:'no-cache'}).then(r=>{if(!r.ok)throw Error('extension');return r.json();}),
      fetch('./world-house-footprints.json',{cache:'no-cache'}).then(r=>{if(!r.ok)throw Error('footprints');return r.json();})
    ]).then(([d,b,a,e,houses])=>{
      if(d.schema_version!=='dynasty-network-v1' ||
         b.schema_version!=='world-pilot-v1' ||
         e.schema_version!=='dynasty-extension-v1' ||
         houses.schema_version!=='dynasty-footprints-v1' ||
         houses.period.start!==1762 || houses.period.end!==1800 ||
         d.period.start!==1762 || d.period.end!==1780 ||
         e.full_period.start!==1762 || e.full_period.end!==1800 ||
         !Array.isArray(a.tenures) || !Array.isArray(a.people))
        throw Error('schema');
      const everyone=[...b.persons,...d.additional_persons,...e.additional_persons];
      const ids=new Set(everyone.map(x=>x.id));
      if(ids.size!==everyone.length)throw Error('duplicate persons');
      const politiesAll=new Set([...b.countries,...d.additional_polities,...e.additional_polities].map(x=>x.id));
      for(const r of [...d.roles,...e.additional_roles]){
        if(!ids.has(r.person_id)||!politiesAll.has(r.polity_id)||r.start_year>r.end_year||
           !(r.source_ids||[]).length)throw Error('invalid roles');
      }
      const pids=new Set(a.people.map(x=>x.id));
      const tenures=new Map(a.tenures.map(x=>[x.id,x]));
      const allSources=new Set([...b.sources,...d.sources,...e.sources,...a.sources].map(x=>x.id));
      for(const row of [...e.additional_roles,...e.institutions,...e.additional_relations,...e.milestones]){
        if(!(row.source_ids||[]).length || !row.source_ids.every(s=>allSources.has(s))) throw Error('missing source');
      }
      for(const rel of [...d.relations,...e.additional_relations]) {
        if(!(rel.subjects||[]).every(id=>ids.has(id)))throw Error('missing relation person');
      }
      for(const actor of everyone){
        if(!actor.canonical_person_id)continue;
        if(!pids.has(actor.canonical_person_id) ||
           tenures.get(actor.canonical_tenure_id)?.person_id!==actor.canonical_person_id)
          throw Error('canonical identity mismatch');
      }
      const sourceKeys=new Set([
        ...b.sources,...d.sources,...e.sources,...houses.sources,...a.sources
      ].map(x=>x.id));
      for(const family of houses.families){
        if(!family.members.length || !(family.source_ids||[]).every(x=>sourceKeys.has(x)))
          throw Error('dynasty family has no sourced members');
        for(const member of family.members){
          if(!ids.has(member.person_id) ||
             !['house','dynastic_union','branch_lineage'].includes(member.membership) ||
             !(member.source_ids||[]).length ||
             !member.source_ids.every(x=>sourceKeys.has(x)))
            throw Error('unsourced family membership');
        }
      }
      data=d;base=b;atlas=a;extension=e;footprints=houses;
      slider.max=String(e.full_period.end);
      const rangeEnd=rangeLabel.querySelector('span:last-child');
      if(rangeEnd)rangeEnd.textContent=String(e.full_period.end);
      milestones.replaceChildren(...[...d.period.presets,...e.additional_presets].map(y=>{
        const button=create('button','dynasty-milestone',String(y));
        button.type='button';button.dataset.year=String(y);
        button.addEventListener('click',()=>chooseYear(y,true));
        return button;
      }));
      caveatList.replaceChildren(...[...d.caveats,...e.caveats].map(text=>create('li',null,text)));
      selectedView=modeFromUrl();
      updateView();
      render();
    }).catch(()=>{
      notice.textContent='Сеть не загружена: проверенная историческая модель недоступна. Не подменяем данные догадками.';
    }).finally(()=>{pending=null;});
    return pending;
  }
  function openSheet(fromUser){
    if(!layer.hidden)return;
    if(fromUser)previousFocus=document.activeElement;
    layer.hidden=false;
    document.documentElement.classList.add('dynasty-open');
    const u=new URL(location.href);
    const number=Number(u.searchParams.get('dynYear'));
    year=Number.isInteger(number)&&number>=1762&&number<=1800?number:1762;
    selectedView=modeFromUrl();
    updateView();
    close.focus({preventScroll:true});
    load();
  }
  function closeSheet(push){
    if(isNetworkURL()){
      const u=new URL(location.href);
      u.searchParams.delete('world');
      u.searchParams.delete('dynYear');
      u.searchParams.delete('dynView');
      history[push?'pushState':'replaceState'](null,'',u.pathname+u.search+u.hash);
    }
    layer.hidden=true;
    document.documentElement.classList.remove('dynasty-open');
    if(previousFocus?.isConnected)previousFocus.focus({preventScroll:true});
    previousFocus=null;
  }
  function sync(){
    if(isNetworkURL()){
      const value=Number(new URL(location.href).searchParams.get('dynYear'));
      year=Number.isInteger(value)&&value>=1762&&value<=1800?value:1762;
      selectedView=modeFromUrl();
      if(layer.hidden)openSheet(false);
      else {updateView();render();}
    } else if(!layer.hidden)closeSheet(false);
  }
  close.addEventListener('click',()=>closeSheet(true));
  layer.addEventListener('click',event=>{if(event.target===layer)closeSheet(true);});
  dialog.addEventListener('keydown',event=>{
    if(event.key==='Escape'){event.preventDefault();closeSheet(true);return;}
    if(event.key!=='Tab')return;
    const elements=[...dialog.querySelectorAll('button:not([disabled]),input:not([disabled]),a[href],[tabindex="0"]')]
      .filter(x=>x.getClientRects().length>0);
    if(!elements.length)return;
    const first=elements[0],last=elements[elements.length-1];
    if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}
    else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
  });
  window.addEventListener('popstate',sync);
  window.addEventListener('hashchange',sync);
  sync();
})();
