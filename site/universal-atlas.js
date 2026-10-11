/* Universal 1417–1991 navigator and cross-century comparison.
   Presentation ONLY: claims, sources and interval precision come from atlas.json.
   Nothing here infers local territorial control, ethnicity, historical completeness,
   de facto rule from a formal title, or simultaneous authority within a year. */
(() => {
  'use strict';
  const panel = document.getElementById('panel-timeline');
  const dashboard = document.getElementById('atlas-year-dashboard');
  const workspace = panel?.querySelector('.atlas-timeline-workspace');
  const slider = document.getElementById('atlas-year-range');
  const toolbar = panel?.querySelector('.timeline-toolbar');
  if (!panel || !dashboard || !workspace || !slider || !toolbar) return;

  const MIN = 1417, MAX = 1991;
  const PERIODS = [
    {label:'XV–XVI века', start:1417, end:1599, entry:1500},
    {label:'XVII век', start:1600, end:1699, entry:1650},
    {label:'XVIII век', start:1700, end:1799, entry:1750},
    {label:'XIX век', start:1800, end:1899, entry:1850},
    {label:'XX век', start:1900, end:1991, entry:1950}
  ];
  const GROUPS = [
    ['formal','Юридические должности'],
    ['influence','Оценки политического влияния'],
    ['regency','Регентство и соправители'],
    ['institutions','Коллективные органы']
  ];
  const nominal = new Set([
    'nominal_due_to_illness','nominal_grand_prince','infant_emperor',
    'leadership_constrained_by_illness'
  ]);
  const regencies = new Set([
    'regent','guardian_influence_approx','patriarch_political_co_ruler'
  ]);

  const el = (tag, cls, value) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (value !== undefined) n.textContent = String(value);
    return n;
  };
  const button = (caption, cls, fn) => {
    const b = el('button', cls, caption);
    b.type = 'button';
    b.addEventListener('click', fn);
    return b;
  };
  const parseYear = x => {
    const s = String(x);
    if (!/^\d{4}$/.test(s)) return null;
    const y = Number(s);
    return y >= MIN && y <= MAX ? y : null;
  };
  const yearNow = () => Number(slider.value);
  const intersect = (r, year) => {
    const a = Number(String(r.start?.value || '').slice(0,4));
    const b = Number(String(r.end?.value || '').slice(0,4));
    return Number.isInteger(a) && Number.isInteger(b) && a <= year && year <= b;
  };
  const regent = r => regencies.has(r.status) ||
    /регент|соправител|опекун/i.test(r.description || '');
  const safeSource = value => {
    try {
      const url = new URL(value);
      return url.protocol === 'https:' && !url.username && !url.password &&
        ![['drive','.google.com'].join(''),['docs','.google.com'].join('')].includes(url.hostname);
    } catch (_) { return false; }
  };

  let db=null, failure=null;
  let people=new Map(), bodies=new Map(), sources=new Map(), offices=new Map(), states=new Map();
  const cache = new Map();
  let visible=false, mode='overview', leftYear=1685, rightYear=1953;
  let mobileComparisonTab='a';
  let trigger=null;

  // Keep all five eras in the same always-visible navigation: no historical
  // interpretation is encoded by these neutral *century* calendar ranges.
  const controls=el('div','atlas-global-controls');
  controls.id='atlas-global-controls';
  controls.setAttribute('aria-label','Вся хронология 1417–1991');
  const quick=el('div','atlas-global-centuries');
  const quickLabel=el('span','atlas-global-kicker','Вся хронология');
  quick.append(quickLabel);
  for (const p of PERIODS) {
    const b=button(p.label,'atlas-global-century',()=>goToYear(p.entry));
    b.dataset.start=String(p.start);
    b.dataset.end=String(p.end);
    b.setAttribute('aria-label','Перейти к '+p.entry+' году, '+p.label);
    quick.append(b);
  }
  const actions=el('div','atlas-global-actions');
  const overviewButton=button('Обзор веков','atlas-global-open',()=>openSheet('overview',overviewButton));
  const compareButton=button('Сравнить два года','atlas-global-open',()=>openSheet('compare',compareButton));
  overviewButton.setAttribute('aria-controls','atlas-global-sheet');
  compareButton.setAttribute('aria-controls','atlas-global-sheet');
  overviewButton.setAttribute('aria-expanded','false');
  compareButton.setAttribute('aria-expanded','false');
  actions.append(overviewButton,compareButton);
  controls.append(quick,actions);
  const status = dashboard.querySelector('.atlas-year-dashboard-status');
  if (status) dashboard.insertBefore(controls,status);
  else dashboard.append(controls);

  const sheet=el('aside','atlas-global-sheet');
  sheet.id='atlas-global-sheet';
  sheet.hidden=true;
  sheet.setAttribute('role','dialog');
  sheet.setAttribute('aria-modal','false');
  sheet.setAttribute('aria-labelledby','atlas-global-heading');
  const head=el('header','atlas-global-sheet-head');
  const mainTitle=el('div','atlas-global-sheet-titles');
  mainTitle.append(el('span','atlas-global-eyebrow','Атлас власти · 1417–1991'));
  const title=el('h3',null,'Обзор веков');
  title.id='atlas-global-heading';
  mainTitle.append(title);
  const close=button('Закрыть ×','atlas-global-close',()=>closeSheet());
  close.setAttribute('aria-label','Закрыть обзор эпох');
  head.append(mainTitle,close);
  const tabs=el('nav','atlas-global-sheet-tabs');
  tabs.setAttribute('aria-label','Режимы общего атласа');
  const tabOverview=button('Обзор всех веков','atlas-global-tab',()=>selectMode('overview'));
  const tabCompare=button('Сравнить годы','atlas-global-tab',()=>selectMode('compare'));
  tabs.append(tabOverview,tabCompare);
  const body=el('div','atlas-global-sheet-body');
  body.tabIndex=0;
  body.setAttribute('aria-label','Сведения по векам и годам');
  const foot=el('p','atlas-global-sheet-foot',
    'В атласе учитываются годовые пересечения отдельных записей, а не непрерывный фактический контроль и не полнота исторических источников.');
  sheet.append(head,tabs,body,foot);
  workspace.append(sheet);
  sheet.addEventListener('keydown',e=>{
    if(e.key==='Escape'){e.preventDefault();e.stopPropagation();closeSheet();}
  });

  function updateButtons() {
    overviewButton.setAttribute('aria-expanded',String(visible && mode==='overview'));
    compareButton.setAttribute('aria-expanded',String(visible && mode==='compare'));
    tabOverview.setAttribute('aria-pressed',String(mode==='overview'));
    tabCompare.setAttribute('aria-pressed',String(mode==='compare'));
    for (const btn of quick.querySelectorAll('.atlas-global-century')) {
      btn.setAttribute('aria-current',String(yearNow()>=Number(btn.dataset.start) &&
        yearNow()<=Number(btn.dataset.end)));
    }
  }
  function writeUrl(push=true) {
    const url = new URL(location.href);
    if(visible) {
      url.searchParams.set('atlasView',mode);
      if(mode==='compare') {
        url.searchParams.set('atlasYears',String(leftYear)+','+String(rightYear));
      } else url.searchParams.delete('atlasYears');
    } else {
      url.searchParams.delete('atlasView');
      url.searchParams.delete('atlasYears');
    }
    const next=url.pathname+url.search+url.hash;
    if(next!==location.pathname+location.search+location.hash)
      history[push?'pushState':'replaceState'](null,'',next);
  }
  // The mobile action bar can open this same canonical drawer without
  // clicking a hidden desktop control or inventing a second comparison app.
  window.addEventListener('atlas:mobile-open-overview',()=>openSheet('overview'));
  window.addEventListener('atlas:mobile-open-compare',()=>openSheet('compare'));
  function openSheet(which,element=null) {
    if(!['overview','compare'].includes(which))return;
    if(!visible) {
      trigger=element||null;
      leftYear=parseYear(slider.value)||1685;
      rightYear=leftYear===1953?1685:1953;
    } else if(element)trigger=element;
    visible=true;mode=which;sheet.hidden=false;
    writeUrl(true);updateButtons();render();
    close.focus({preventScroll:true});
  }
  function selectMode(which) {
    mode=which;
    writeUrl(true);
    updateButtons();render();
    body.scrollTop=0;
  }
  function closeSheet(restore=true,updateUrl=true) {
    const previous=trigger;
    visible=false;sheet.hidden=true;trigger=null;
    updateButtons();
    if(updateUrl)writeUrl(true);
    if(restore && previous?.isConnected) previous.focus({preventScroll:true});
  }
  function fromUrl() {
    const url=new URL(location.href);
    const next=url.searchParams.get('atlasView');
    if(!['overview','compare'].includes(next) || !/^#\/timeline(?:\/\d{4})?$/.test(location.hash)) {
      if(visible)closeSheet(false,false);
      return;
    }
    if(next==='compare') {
      const numbers=/^(\d{4}),(\d{4})$/.exec(url.searchParams.get('atlasYears')||'');
      leftYear=numbers&&parseYear(numbers[1])||parseYear(slider.value)||1685;
      rightYear=numbers&&parseYear(numbers[2])||1953;
    }
    mode=next;visible=true;sheet.hidden=false;
    updateButtons();render();
  }
  window.addEventListener('popstate',fromUrl);
  window.addEventListener('hashchange',()=>queueMicrotask(fromUrl));
  window.addEventListener('atlas:route',e=>{
    if(e.detail?.view!=='timeline'&&visible)closeSheet(false,true);
  });

  function goToYear(year) {
    if(!Number.isInteger(year)||year<MIN||year>MAX)return;
    if(visible)closeSheet(false,false);
    const url=new URL(location.href);
    url.searchParams.delete('atlasView');
    url.searchParams.delete('atlasYears');
    // Leaving a previously selected historic pilot must not obscure the
    // *universal* atlas underneath it.
    for(const key of ['map','place','kind','scope','month','compare','rivers','matrix'])
      url.searchParams.delete(key);
    history.replaceState(null,'',url.pathname+url.search+url.hash);
    const all=toolbar.querySelector('.era-btn[data-era="all"]');
    if(all&&all.getAttribute('aria-pressed')!=='true')all.click();
    queueMicrotask(()=>{
      slider.value=String(year);
      slider.dispatchEvent(new Event('input',{bubbles:true}));
      const wanted='#/timeline/'+year;
      if(location.hash!==wanted)location.hash=wanted;
      updateButtons();
    });
  }

  function groupsFor(year) {
    if(cache.has(year))return cache.get(year);
    const tenure=db.tenures.filter(x=>intersect(x,year));
    const power=db.power_assessments.filter(x=>intersect(x,year));
    const institute=db.institution_periods.filter(x=>intersect(x,year));
    const regentTerms=tenure.filter(regent);
    const regentPower=power.filter(r=>regencies.has(r.status));
    const o={
      formal:tenure.filter(x=>!regentTerms.includes(x)),
      influence:power.filter(x=>!nominal.has(x.status)&&!regencies.has(x.status)&&!x.body_id),
      regency:[...regentTerms,...regentPower],
      institutions:[...institute,...power.filter(x=>x.body_id&&!nominal.has(x.status))],
      limited:power.filter(x=>nominal.has(x.status))
    };
    cache.set(year,o);
    return o;
  }
  function addSources(host,record) {
    const ids=[...new Set(record.sources||[])];
    const links=el('div','atlas-global-sources');
    for(const id of ids.slice(0,3)) {
      const s=sources.get(id);
      if(!s||!safeSource(s.url))continue;
      const a=el('a',null,id);
      a.href=s.url;a.title=s.title;a.rel='noopener noreferrer';a.target='_blank';
      links.append(a);
    }
    if(ids.length>3)links.append(el('span',null,'+'+(ids.length-3)+' источника'));
    host.append(links);
  }
  function formatDate(d) {
    if(!d)return 'дата не установлена';
    const precision=d.precision==='year'?' (год)':
      d.precision==='month'?' (месяц)':'';
    const calendar=d.calendar==='julian'?' · ст. ст.':
      d.calendar==='gregorian'?' · н. ст.':' · стиль не указан';
    return d.value+precision+calendar;
  }
  function recordName(record) {
    if(record.person_id && people.has(record.person_id))
      return people.get(record.person_id).name;
    if(record.body_id && bodies.has(record.body_id))
      return bodies.get(record.body_id).name;
    return 'Участник не установлен';
  }
  function recordCard(record) {
    const row=el('article','atlas-global-record');
    if(record.person_id&&people.has(record.person_id)) {
      const name=el('a','atlas-global-person',recordName(record));
      name.href='#/people/'+encodeURIComponent(record.person_id);
      row.append(name);
    } else row.append(el('strong','atlas-global-person',recordName(record)));
    const tags=el('div','atlas-global-record-meta');
    tags.append(el('span',null,formatDate(record.start)+' — '+formatDate(record.end)));
    if(record.office_id&&offices.has(record.office_id))
      tags.append(el('span',null,'Должность: '+offices.get(record.office_id).title));
    if(Array.isArray(record.state_ids)&&record.state_ids.length)
      tags.append(el('span',null,'Контекст: '+record.state_ids.map(id=>
        states.get(id)?.name||id).join(' / ')));
    row.append(tags,el('p','atlas-global-record-description',record.description||''));
    if(record.note)row.append(el('p','atlas-global-record-note',record.note));
    if(record.verification!=='reference_checked')
      row.append(el('p','atlas-global-unverified','Историческое утверждение ещё не перепроверено по источникам.'));
    addSources(row,record);
    return row;
  }
  function renderYearGroup(host,records,titleText) {
    const section=el('section','atlas-global-year-group');
    section.append(el('h5',null,titleText+' · '+records.length));
    if(!records.length) {
      section.append(el('p','atlas-global-missing',
        'Отдельных сведений в реестре нет. Это не означает отсутствия власти или такого института.'));
    } else {
      for(const r of records.slice(0,6))section.append(recordCard(r));
      if(records.length>6)section.append(el('p','atlas-global-missing',
        'Ещё '+(records.length-6)+' записей. Откройте полный исторический срез.'));
    }
    host.append(section);
  }
  function renderYearColumn(year) {
    const g=groupsFor(year);
    const col=el('section','atlas-global-year-column');
    col.dataset.year=String(year);
    const heading=el('div','atlas-global-column-head');
    heading.append(el('h4',null,year+' год'));
    const goto=button('К году на шкале →','atlas-global-year-jump',()=>goToYear(year));
    goto.dataset.year=String(year);
    heading.append(goto);col.append(heading);
    const counts=el('p','atlas-global-year-counts',
      GROUPS.map(([key,label])=>label+': '+g[key].length).join(' · '));
    col.append(counts);
    for(const [key,label] of GROUPS)renderYearGroup(col,g[key],label);
    if(g.limited.length)renderYearGroup(col,g.limited,'Номинальная / ограниченная власть');
    return col;
  }

  function renderOverview() {
    body.append(el('p','atlas-global-intro',
      'Переходите между веками. Полосы отражают лишь годы, на которые распространяются записи базы, а не полноту источников или непрерывный фактический контроль.'));
    const goto=el('div','atlas-global-goto');
    const label=el('label',null,'Перейти к году');
    const input=el('input','atlas-global-goto-input');
    input.type='number';input.min=String(MIN);input.max=String(MAX);input.step='1';
    input.value=String(yearNow());input.setAttribute('aria-label','Год от 1417 до 1991');
    label.append(input);
    const message=el('span','atlas-global-goto-error');
    message.setAttribute('role','status');
    const action=button('Открыть →','atlas-global-goto-button',()=>{
      const year=parseYear(input.value);
      if(year===null) {
        message.textContent='Введите год от 1417 до 1991.';
        input.focus();return;
      }
      goToYear(year);
    });
    input.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();action.click();}});
    goto.append(label,action,message);body.append(goto);
    const grid=el('div','atlas-global-century-grid');
    for(const p of PERIODS) {
      const card=el('article','atlas-global-century-card');
      card.dataset.period=p.label;
      const head=el('div','atlas-global-century-head');
      head.append(el('h4',null,p.label),el('span',null,p.start+'–'+p.end));
      card.append(head);
      const totals=Object.fromEntries(GROUPS.map(([key])=>[key,0]));
      const n=p.end-p.start+1;
      for(let year=p.start;year<=p.end;year++) {
        const grouped=groupsFor(year);
        for(const [key] of GROUPS)if(grouped[key].length)totals[key]++;
      }
      for(const [key,name] of GROUPS) {
        const frac=totals[key]/n*100;
        const line=el('div','atlas-global-coverage-row');
        line.dataset.kind=key;
        line.append(el('span','atlas-global-coverage-name',name),
          el('span','atlas-global-coverage-count',totals[key]+' / '+n+' лет с записью'));
        const track=el('div','atlas-global-coverage-track');
        const bar=el('span','atlas-global-coverage-fill');
        bar.style.width=frac.toFixed(2)+'%';
        bar.setAttribute('aria-hidden','true');
        track.append(bar);line.append(track);card.append(line);
      }
      card.append(button('Открыть '+p.entry+' год →','atlas-global-century-entry',()=>goToYear(p.entry)));
      grid.append(card);
    }
    body.append(grid);
    body.append(el('p','atlas-global-method',
      'Масштаб — календарные века. Государственные границы, национальность людей, реальное осуществление законов и источниковая полнота из этих полос не выводятся.'));
  }

  function setMobileComparisonTab(tab){
    if(!['a','b','diff'].includes(tab))return;
    mobileComparisonTab=tab;
    const switches=body.querySelectorAll('.atlas-mobile-compare-segment button');
    switches.forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.tab===tab)));
    const columns=body.querySelector('.atlas-global-compare-columns');
    if(columns)columns.dataset.mobileSelected=tab;
    const changes=body.querySelector('.atlas-mobile-differences');
    if(changes)changes.hidden=tab!=='diff';
  }
  function makeDifferenceRow(group,label,year){
    const area=el('div','atlas-mobile-diff-side');
    area.dataset.year=String(year);
    area.append(el('h6',null,label+' · '+group.length));
    if(!group.length)
      area.append(el('p','atlas-global-missing','Отдельных записей только за этот год в данном разделе нет.'));
    else{
      group.slice(0,5).forEach(r=>area.append(recordCard(r)));
      if(group.length>5)
        area.append(el('p','atlas-global-missing','Остальные '+(group.length-5)+' записей доступны при выборе года.'));
    }
    return area;
  }
  function renderMobileDifferences() {
    const container=el('section','atlas-mobile-differences');
    container.setAttribute('aria-label','Различия записей между годами');
    container.append(el('h4',null,'Различия источниковых записей'),
      el('p','atlas-global-intro',
        'Показаны записи, пересекающие только один из двух выбранных годов. Это НЕ доказательство смены правителя, исчезновения власти или непрерывности его полномочий между датами.'));
    const a=groupsFor(leftYear),b=groupsFor(rightYear);
    for(const [key,label] of GROUPS){
      const leftIds=new Set(a[key].map(x=>x.id));
      const rightIds=new Set(b[key].map(x=>x.id));
      const onlyLeft=a[key].filter(x=>!rightIds.has(x.id));
      const onlyRight=b[key].filter(x=>!leftIds.has(x.id));
      const group=el('section','atlas-mobile-diff-group');
      group.dataset.kind=key;
      group.append(el('h5',null,label));
      group.append(
        makeDifferenceRow(onlyLeft,'Только в '+leftYear,leftYear),
        makeDifferenceRow(onlyRight,'Только в '+rightYear,rightYear));
      container.append(group);
    }
    return container;
  }
  function renderComparison() {
    body.append(el('p','atlas-global-intro',
      'Сопоставьте два любых года от 1417 до 1991. Годовые пересечения могут включать несколько последовательных должностей: это не доказательство их одновременной власти.'));
    const inputs=el('div','atlas-global-year-inputs');
    function field(caption,year,change) {
      const label=el('label',null,caption);
      const input=el('input');
      input.type='number';input.min=String(MIN);input.max=String(MAX);input.step='1';
      input.value=String(year);input.setAttribute('aria-label',caption);
      const error=el('span','atlas-global-year-error');
      input.addEventListener('change',()=>{
        const y=parseYear(input.value);
        if(y===null) {error.textContent='1417–1991';return;}
        error.textContent='';change(y);
      });
      label.append(input,error);return label;
    }
    inputs.append(field('Первый год',leftYear,y=>{
      leftYear=y;writeUrl(true);render();
    }),field('Второй год',rightYear,y=>{
      rightYear=y;writeUrl(true);render();
    }));
    const swap=button('⇄','atlas-global-swap',()=>{
      [leftYear,rightYear]=[rightYear,leftYear];writeUrl(true);render();
    });
    swap.setAttribute('aria-label','Поменять годы местами');
    inputs.append(swap);
    body.append(inputs);
    const presets=el('div','atlas-global-presets');
    for(const [a,b] of [[1685,1953],[1812,1917],[1917,1991]]) {
      const pick=button(a+' ↔ '+b,'atlas-global-preset',()=>{
        leftYear=a;rightYear=b;writeUrl(true);render();
      });
      pick.dataset.left=String(a);pick.dataset.right=String(b);
      presets.append(pick);
    }
    body.append(presets);
    const mobileTabs=el('nav','atlas-mobile-compare-segment');
    mobileTabs.setAttribute('aria-label','Выберите год или различия');
    for(const [tab,label] of [['a',leftYear+' год'],['b',rightYear+' год'],['diff','Различия']]){
      const choice=button(label,'atlas-mobile-compare-tab',()=>setMobileComparisonTab(tab));
      choice.dataset.tab=tab;
      mobileTabs.append(choice);
    }
    body.append(mobileTabs);
    const cols=el('div','atlas-global-compare-columns');
    cols.append(renderYearColumn(leftYear),renderYearColumn(rightYear));
    body.append(cols);
    const differences=renderMobileDifferences();
    body.append(differences);
    setMobileComparisonTab(mobileComparisonTab);
    body.append(el('p','atlas-global-method',
      'Сравниваются записанные должности, отдельные оценки политического влияния, регентство и коллективные органы. Отсутствие записи об оценке влияния не доказывает отсутствия реальной власти. Примечания о неопределённости каждого источника сохранены.'));
  }

  function render() {
    updateButtons();
    if(!visible)return;
    title.textContent=mode==='overview'?'Вся хронология по векам':'Сравнение двух годов';
    body.replaceChildren();
    if(!db) {
      const p=el('p','atlas-global-loading',failure?
        'Не удалось загрузить историческую базу: '+failure:
        'Загрузка общей базы атласа…');
      body.append(p);return;
    }
    if(mode==='overview')renderOverview();
    else renderComparison();
  }
  slider.addEventListener('input',updateButtons);
  toolbar.querySelectorAll('.era-btn').forEach(x=>
    x.addEventListener('click',()=>queueMicrotask(updateButtons)));
  fromUrl();
  fetch('./atlas.json',{cache:'no-cache'}).then(r=>{
    if(!r.ok)throw Error('HTTP '+r.status);
    return r.json();
  }).then(result=>{
    if(!result.metadata || result.metadata.historical_truth_verified_by_ci!==false ||
       !Array.isArray(result.people)||!Array.isArray(result.bodies)||
       !Array.isArray(result.sources)||!Array.isArray(result.tenures)||
       !Array.isArray(result.power_assessments)||!Array.isArray(result.institution_periods)||
       !Array.isArray(result.states)||!Array.isArray(result.offices))
      throw Error('Неполная или неподтверждённая структура атласа');
    db=result;
    people=new Map(result.people.map(p=>[p.id,p]));
    bodies=new Map(result.bodies.map(p=>[p.id,p]));
    sources=new Map(result.sources.map(p=>[p.id,p]));
    offices=new Map(result.offices.map(p=>[p.id,p]));
    states=new Map(result.states.map(p=>[p.id,p]));
    render();
  }).catch(e=>{failure=e.message;render();});
})();