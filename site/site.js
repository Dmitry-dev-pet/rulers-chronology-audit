/* Progressive enhancement for the three modes. No external dependencies or requests. */
(() => {
  'use strict';
  const source = document.getElementById('chronology-data');
  if (!source) return;
  let data;
  try { data = JSON.parse(source.textContent); }
  catch (error) { document.getElementById('timeline-status').textContent = 'Данные шкалы недоступны.'; return; }


  // Create one additional accessible screen in the existing static document.
  const navHost=document.querySelector('.modes[role="tablist"]');
  const mainHost=document.querySelector('main.container');
  if(navHost && mainHost && !document.getElementById('panel-people')){
    const tab=document.createElement('button');
    tab.id='tab-people';tab.type='button';tab.role='tab';tab.className='mode-tab';
    tab.dataset.view='people';tab.setAttribute('aria-selected','false');
    tab.setAttribute('aria-controls','panel-people');tab.tabIndex=-1;
    const index=document.createElement('span');index.className='num';index.textContent='02';
    tab.append(index,document.createTextNode(' Биографии'));navHost.insertBefore(tab,navHost.querySelector('#tab-poster'));
    const pane=document.createElement('section');
    pane.id='panel-people';pane.className='mode-panel';pane.dataset.mode='people';
    pane.setAttribute('role','tabpanel');pane.setAttribute('aria-labelledby','tab-people');pane.hidden=true;
    // All HTML below is a static shell, never inserted historical data.
    pane.innerHTML='<div class="section-top"><div><div class="kicker">Режим 04 / база людей</div>'+
      '<h2>Биографии и сроки власти</h2><p>Возраст, происхождение, юридические должности и оценки влияния '+
      'хранятся отдельно. Неизвестные сведения не домысливаются.</p></div></div>'+
      '<div id="spa-people-tools" class="spa-people-tools"><label for="spa-people-search">Поиск по именам и должностям'+
      '<input type="search" id="spa-people-search" autocomplete="off" placeholder="Имя, должность, династия…"></label>'+
      '<p>Каждая личность — одна запись. Открывайте карточки без перехода на другой сайт.</p></div>'+
      '<p class="spa-people-status" id="spa-people-status" role="status" aria-live="polite">Откройте биографии, чтобы загрузить базу.</p>'+
      '<div id="spa-people-list" class="spa-people-grid"></div>'+
      '<section id="spa-person-detail" class="spa-person-detail" hidden aria-label="Карточка выбранного человека"></section>'+
      '<p class="spa-people-footnote">Историческая проверка неполна. '+
      '<a href="./database.html">Резервная табличная версия</a>.</p>';
    mainHost.appendChild(pane);
  }

  // The year-centric authority view is the primary application destination.
  // Reordering happens only with JS; the original poster remains the noscript fallback.
  const tabOrder = [
    ['timeline', 'Год и власть'], ['people', 'Биографии'],
    ['poster', 'Плакат'], ['research', 'Исследование']
  ];
  for (const [index, [view, label]] of tabOrder.entries()) {
    const node = navHost && navHost.querySelector('.mode-tab[data-view="' + view + '"]');
    if (!node) continue;
    const number = node.querySelector('.num');
    if (number) number.textContent = String(index + 1).padStart(2, '0');
    const last = node.lastChild;
    if (last && last.nodeType === 3) last.textContent = ' ' + label;
    else node.appendChild(document.createTextNode(' ' + label));
    navHost.appendChild(node);
  }
  const tabNames = new Set(['poster', 'timeline', 'research', 'people']);
  const routeNames = new Set([...tabNames, 'home']);
  const tabs = Array.from(document.querySelectorAll('.mode-tab'));
  const panels = new Map(Array.from(document.querySelectorAll('.mode-panel')).map(panel => [panel.dataset.mode, panel]));
  let currentMode = 'home';
  const originalTitle=document.title;
  function navigate(name, updateHash) {
    if (!routeNames.has(name)) return;
    currentMode = name;
    document.documentElement.classList.toggle('atlas-home-open', name === 'home');
    tabs.forEach(tab => {
      const selected = tab.dataset.view === name;
      tab.setAttribute('aria-selected', String(selected));
      tab.tabIndex = selected || (name === 'home' && tab.dataset.view === 'timeline') ? 0 : -1;
    });
    panels.forEach((panel, id) => { panel.hidden = id !== name; });
    if (name === 'timeline' && !rendered) renderTimeline();
    if(updateHash){
      const year=document.getElementById('atlas-year-range');
      const route='#/'+name+(name==='timeline' && year ? '/'+year.value : '');
      if(location.hash!==route)location.hash=route;
      if (document.documentElement.classList.contains('atlas-app')) {
        const view = panels.get(name);
        if (view) view.scrollTop = 0;
      } else {
        document.querySelector('.modes-wrap').scrollIntoView({block:'start'});
      }
    }
    document.title=name==='people'?'Биографии · '+originalTitle:originalTitle;
    window.dispatchEvent(new CustomEvent('atlas:route',{detail:{view:name}}));
  }
  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => navigate(tab.dataset.view, true));
    tab.addEventListener('keydown', event => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const target = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 :
        (index + tabs.length + (event.key === 'ArrowRight' ? 1 : -1)) % tabs.length;
      tabs[target].focus();
      navigate(tabs[target].dataset.view, true);
    });
  });

  document.querySelectorAll('.detail-trigger').forEach(button => {
    button.addEventListener('click', () => {
      const expanded = button.getAttribute('aria-expanded') === 'true';
      const details = document.getElementById(button.getAttribute('aria-controls'));
      if (!details) return;
      details.hidden = expanded;
      button.setAttribute('aria-expanded', String(!expanded));
      button.textContent = expanded ? 'Пояснение ↓' : 'Свернуть ↑';
    });
  });

  const windows = {
    all: [Date.UTC(1417, 0, 1), Date.UTC(1991, 11, 26)],
    muscovy: [Date.UTC(1417, 0, 1), Date.UTC(1547, 11, 31)],
    tsardom: [Date.UTC(1547, 0, 1), Date.UTC(1617, 11, 31)],
    troubles: [Date.UTC(1598, 0, 1), Date.UTC(1613, 11, 31)],
    romanov: [Date.UTC(1617, 0, 1), Date.UTC(1721, 11, 31)],
    eighteenth: [Date.UTC(1721, 0, 1), Date.UTC(1817, 11, 31)],
    dual: [Date.UTC(1682, 0, 1), Date.UTC(1741, 11, 31)],
    imperial: [Date.UTC(1817, 0, 1), Date.UTC(1917, 10, 8)],
    transition: [Date.UTC(1894, 0, 1), Date.UTC(1925, 11, 31)],
    early: [Date.UTC(1917, 0, 1), Date.UTC(1953, 11, 31)],
    middle: [Date.UTC(1953, 0, 1), Date.UTC(1982, 11, 31)],
    late: [Date.UTC(1982, 0, 1), Date.UTC(1991, 11, 26)],
  };
  // Three conceptual roles, not three unchanging legal offices:
  // monarchy -> party; ministries -> governments; advisory -> legislative bodies.
  const trackInfo = [
    ['authority', 'Цари / императоры → партия', 'Царская, регентская и партийная власть', 'party',
      ['muscovy_rulers', 'muscovy_regents', 'early_monarchy', 'early_regency', 'imperial_monarchy', 'party']],
    ['government', 'Управление', 'От приказов, Сената и коллегий до СНК СССР', 'gov',
      ['muscovy_government', 'early_executive', 'imperial_government', 'government']],
    ['state', 'Государственные органы', 'Советы, Дума, Президиум Верховного Совета', 'state',
      ['muscovy_institutions', 'early_institutions', 'imperial_institutions', 'state_institutions']],
  ];
  let currentEra = 'all';
  let selectedBar = null;
  let rendered = false;
  const canvas = document.getElementById('time-canvas');
  const ruler = document.getElementById('time-ruler');
  const detail = document.getElementById('timeline-selection');

  const persons = row => row.person || (row.persons || row.initial_cochairs || []).join('; ') || 'Коллегиальный орган / событие';
  function bounds(value) {
    if (!/^\d{4}(?:-\d{2}){0,2}$/.test(value)) return null;
    const [year, month, day] = value.split('-').map(Number);
    if (month && (month < 1 || month > 12)) return null;
    if (day && (day < 1 || day > 31)) return null;
    const lower = Date.UTC(year, (month || 1) - 1, day || 1);
    const upper = day ? lower : month ? Date.UTC(year, month, 0) : Date.UTC(year, 11, 31);
    return { lower, upper, partial: !day };
  }
  const pos = (timestamp, start, end) => 100 * (timestamp - start) / (end - start);
  function el(tag, cls, label) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (label != null) node.textContent = label;
    return node;
  }
  function ticks(start, end) {
    const a = new Date(start).getUTCFullYear(), b = new Date(end).getUTCFullYear();
    const gap = b - a;
    const step = gap <= 12 ? 2 : gap <= 35 ? 5 : gap <= 120 ? 10 : 25;
    const years = [a];
    for (let y = Math.ceil(a / step) * step; y < b; y += step) if (y > a) years.push(y);
    if (years[years.length - 1] !== b) years.push(b);
    const allTicks = years.map(year => ({ year, x: Math.max(0, Math.min(100, pos(Date.UTC(year, 0, 1), start, end))) }));
    // Keep boundary labels, suppress interior ticks if they would collide.
    return allTicks.filter((tick, index) => index === 0 || index === allTicks.length - 1 ||
      (tick.x - allTicks[index - 1].x >= 5.5 && allTicks[allTicks.length - 1].x - tick.x >= 5.5));
  }
  function lines(parent, yearTicks) {
    yearTicks.forEach(t => {
      const grid = el('span', 'plot-guide');
      grid.style.left = t.x + '%';
      grid.setAttribute('aria-hidden', 'true');
      parent.appendChild(grid);
    });
  }
  function select(row, track, bar) {
    if (selectedBar) selectedBar.classList.remove('selected');
    bar.classList.add('selected');
    selectedBar = bar;
    detail.replaceChildren();
    const main = el('div');
    main.append(el('div', 'selection-kicker', track), el('h3', null, persons(row)), el('p', null, row.role));
    if (row.note) main.append(el('p', null, row.note));
    const rhs = el('div', 'selection-date');
    rhs.append(el('div', null, row.from + ' — ' + row.to));
    const refs = el('div', 'selection-source', 'Источники: ');
    row.sources.forEach(ref => {
      const anchor = el('a', null, ref);
      anchor.href = '#source-' + ref;
      refs.append(anchor);
    });
    rhs.append(refs);
    detail.append(main, rhs);
  }
  function renderTimeline() {
    rendered = true;
    selectedBar = null;
    canvas.replaceChildren();
    const [start, end] = windows[currentEra];
    const yearTicks = ticks(start, end);
    ruler.replaceChildren();
    yearTicks.forEach(t => {
      const tick = el('span', null, String(t.year));
      tick.style.left = t.x + '%';
      ruler.appendChild(tick);
    });
    let total = 0;
    trackInfo.forEach(([key, label, caption, color, sourceKeys]) => {
      const authorityLabels = {
        all: 'Князья / цари / императоры → партия',
        muscovy: 'Великие князья и опека',
        tsardom: 'Цари и конкурирующие власти',
        troubles: 'Смута и претенденты',
        romanov: 'Цари и регенты',
        eighteenth: 'Императоры и регенты',
        dual: 'Соправители и регенты',
        imperial: 'Император',
        transition: 'Монархия → партия',
        early: 'Партия',
        middle: 'Партия',
        late: 'Партия',
      };
      const labelForEra = key === 'authority' ? authorityLabels[currentEra] || label : label;
      const entries = sourceKeys.flatMap(sourceKey => data[sourceKey] || []).map(item => {
        const from = bounds(item.from), to = bounds(item.to);
        return { item, a: from ? from.lower : null, b: to ? to.upper : null, partial: (from && from.partial) || (to && to.partial) };
      }).filter(x => x.a != null && x.b != null && x.a <= end && x.b >= start).sort((a, b) => a.a - b.a || a.b - b.b);
      const lanes = [];
      entries.forEach(x => {
        const firstEmpty = lanes.findIndex(last => last < x.a);
        x.lane = firstEmpty === -1 ? lanes.length : firstEmpty;
        lanes[x.lane] = x.b;
      });
      total += entries.length;
      const section = el('div', 'time-track');
      section.dataset.track = key;
      const side = el('div', 'track-name', labelForEra);
      side.append(el('small', null, caption + ' · ' + entries.length));
      const plot = el('div', 'track-plot');
      plot.style.height = Math.max(100, 23 + lanes.length * 39) + 'px';
      lines(plot, yearTicks);
      entries.forEach(x => {
        const clampedStart = Math.max(x.a, start);
        const clampedEnd = Math.min(x.b, end);
        const left = Math.max(0, Math.min(100, pos(clampedStart, start, end)));
        const width = Math.max(0, Math.min(100 - left, pos(clampedEnd, start, end) - left));
        const small = width < 1.6;
        const bar = el('button', 'time-bar ' + color + (small ? ' tiny' : '') + (x.partial ? ' approximate' : ''), width >= 8 ? persons(x.item) : '');
        bar.type = 'button';
        bar.title = persons(x.item) + ': ' + x.item.from + ' — ' + x.item.to + '\n' + x.item.role;
        bar.setAttribute('aria-label', persons(x.item) + ', ' + x.item.from + ' — ' + x.item.to + ': ' + x.item.role);
        bar.dataset.record = x.item.id;
        bar.style.left = left + '%';
        bar.style.width = (small ? 0.75 : width) + '%';
        bar.style.top = (14 + x.lane * 39) + 'px';
        bar.addEventListener('click', () => select(x.item, labelForEra, bar));
        plot.appendChild(bar);
      });
      section.append(side, plot);
      canvas.appendChild(section);
    });
    detail.replaceChildren(el('div', null, 'Выберите интервал на шкале, чтобы увидеть точные данные, роль и источники.'));
    document.getElementById('timeline-status').textContent = `Период ${new Date(start).getUTCFullYear()}–${new Date(end).getUTCFullYear()}; показано ${total} интервалов. Пересечения сохранены.`;
  }
  document.querySelectorAll('.era-btn').forEach(button => {
    button.addEventListener('click', () => {
      currentEra = button.dataset.era;
      document.querySelectorAll('.era-btn').forEach(x => x.setAttribute('aria-pressed', String(x === button)));
      renderTimeline();
    });
  });
  function fromHash() {
    const hash = decodeURIComponent(location.hash.slice(1));
    const route=/^\/(home|poster|timeline|research|people)(?:\/([A-Za-z0-9-]+))?$/.exec(hash);
    if(route)return navigate(route[1],false);
    if (tabNames.has(hash)) return navigate(hash, false);
    if (hash.startsWith('source-') || /^[MRIPGSX]\d{2,}$/.test(hash)) {
      navigate('research', false);
      const target = document.getElementById(hash);
      if (target) {
        if (target.tagName === 'DETAILS') target.open = true;
        requestAnimationFrame(() => target.scrollIntoView({block: 'start'}));
      }
      return;
    }
    if (hash.startsWith('poster-')) return navigate('poster', false);
    if (!hash) {
      const params = new URLSearchParams(location.search);
      if (['world', 'map', 'atlasView'].some(key => params.has(key))) {
        history.replaceState(null, '', location.pathname + location.search + '#/timeline/1685');
        return navigate('timeline', false);
      }
      return navigate('home', false);
    }
  }
  window.addEventListener('hashchange', fromHash);
  const homeYearForm = document.getElementById('atlas-home-year-form');
  if (homeYearForm) homeYearForm.addEventListener('submit', event => {
    event.preventDefault();
    const yearInput = homeYearForm.querySelector('#atlas-home-year');
    const year = Number(yearInput.value);
    if (!Number.isInteger(year) || year < 1417 || year > 1991) {
      yearInput.reportValidity();
      return;
    }
    location.hash = '#/timeline/' + year;
  });
  fromHash();
})();

/* Static, source-aware biographies and selected-year inspector. */
(() => {
  'use strict';
  const panel=document.getElementById('panel-timeline'), canvas=document.getElementById('time-canvas');
  const toolbar=panel && panel.querySelector('.timeline-toolbar');
  if (!panel || !toolbar || !canvas) return;
  const root=document.createElement('section');
  root.className='atlas-year-inspector';
  root.setAttribute('aria-label','Правители в выбранном году');
  root.innerHTML='<div class="atlas-year-head"><label for="atlas-year-range">Исторический срез: <strong id="atlas-year-value">1685</strong> год</label><span>Возраст и правовой статус</span></div><input type="range" id="atlas-year-range" min="1417" max="1991" step="1" value="1685" aria-label="Выбрать год"><p class="atlas-year-caveat">Показаны периоды, пересекающие выбранный год, а не гарантированное совпадение должностей в конкретный день. Возраст дан диапазоном в течение года.</p><div id="atlas-year-results" aria-live="polite">Загрузка биографических сведений…</div>';
  toolbar.insertAdjacentElement('afterend',root);
  const slider=root.querySelector('#atlas-year-range'), yearLabel=root.querySelector('#atlas-year-value'), results=root.querySelector('#atlas-year-results');
  const deepYear=/^#\/timeline\/(\d{4})$/.exec(location.hash);
  let atlas=null, currentYear=deepYear?Number(deepYear[1]):1685, people=new Map(), bodies=new Map(), sources=new Map(), facts=new Map(), recordPerson=new Map();
  slider.value=String(Math.max(1417,Math.min(1991,currentYear)));
  function el(tag,cls,t) {const n=document.createElement(tag);if(cls)n.className=cls;if(t!==undefined)n.textContent=String(t);return n;}
  function windowYears() {
    const btn=panel.querySelector('.era-btn[aria-pressed="true"]');
    const numbers=btn && btn.textContent.match(/\d{4}/g);
    return numbers && numbers.length>=2 ? numbers.slice(0,2).map(Number) : [1417,1991];
  }
  function markYear() {
    const bounds=windowYears(), a=Date.UTC(bounds[0],0,1), b=Date.UTC(bounds[1],11,31);
    const percentage=Math.max(0,Math.min(100,100*(Date.UTC(currentYear,6,1)-a)/(b-a)));
    canvas.querySelectorAll('.time-track .track-plot').forEach(plot=>{
      let marker=plot.querySelector('.atlas-year-cursor');
      if(!marker){marker=el('div','atlas-year-cursor');marker.setAttribute('aria-hidden','true');plot.appendChild(marker);}
      marker.style.left=percentage+'%';
    });
  }
  // The timeline renderer replaces its own plots when zooming.
  new MutationObserver(markYear).observe(canvas,{childList:true});
  function julian(y,m,d) {
    const a=Math.floor((14-m)/12), yy=y+4800-a, mm=m+12*a-3;
    const jd=d+Math.floor((153*mm+2)/5)+365*yy+Math.floor(yy/4)-32083;
    const v=jd+32044,b=Math.floor((4*v+3)/146097),c=v-Math.floor(146097*b/4),e=Math.floor((4*c+3)/1461);
    const f=c-Math.floor(1461*e/4),g=Math.floor((5*f+2)/153);
    return [100*b+e-4800+Math.floor(g/10),g+3-12*Math.floor(g/10),f-Math.floor((153*g+2)/5)+1];
  }
  function bounds(d) {
    if(!d || !['julian','gregorian'].includes(d.calendar))return null;
    const p=d.value.split('-').map(Number), year=p[0], month=p[1]||1;
    const monthEnd=p[1]||12;
    const dayEnd=p[2]||new Date(Date.UTC(year,monthEnd,0)).getUTCDate();
    const lower=[year,month,p[2]||1],upper=[year,monthEnd,dayEnd];
    return {start:d.calendar==='julian'?julian(...lower):lower,
            end:d.calendar==='julian'?julian(...upper):upper};
  }
  const completed=(b,day)=>day[0]-b[0]-((day[1]<b[1]||(day[1]===b[1]&&day[2]<b[2]))?1:0);
  function age(id,y) {
    const variants=(facts.get(id)||[]).filter(f=>f.kind==='birth'),ranges=[];
    for(const fact of variants) {
      const b=bounds(fact.value);if(!b||b.start[0]>y)continue;
      const lo=Math.max(0,completed(b.end,[y,1,1])),hi=completed(b.start,[y,12,31]);
      if(hi>=0)ranges.push({lo,hi,disputed:fact.verification==='disputed'});
    }
    if(!ranges.length)return 'не установлен';
    const low=Math.min(...ranges.map(x=>x.lo)),high=Math.max(...ranges.map(x=>x.hi));
    return (low===high?String(low):low+'–'+high)+' лет'+(ranges.length>1||ranges.some(x=>x.disputed)?' (спорные даты)':'');
  }
  function fact(id,kind) {
    return [...new Set((facts.get(id)||[]).filter(f=>f.kind===kind).map(f=>f.value))].join(' / ');
  }
  function bio(personId) {
    if(!personId)return '';
    const segments=['Возраст: '+age(personId,currentYear)],origin=fact(personId,'ethnic_origin'),dynasty=fact(personId,'dynasty');
    if(origin)segments.push('Происхождение: '+origin);
    if(dynasty)segments.push('Династия: '+dynasty);
    return segments.join(' · ');
  }
  function references(parent,ids) {
    for(const id of [...new Set(ids)].slice(0,4)) {
      const s=sources.get(id);
      if(!s || !/^https:\/\//.test(s.url||''))continue;
      const link=el('a',null,id);
      link.href=s.url;link.title=s.title;link.rel='noopener noreferrer';link.target='_blank';
      parent.appendChild(link);
    }
  }
  function active(x) {return Number(x.start.value.slice(0,4))<=currentYear&&currentYear<=Number(x.end.value.slice(0,4));}
  function group(title,entries,out,power) {
    const section=el('section','atlas-year-group'+(power?' power':'')),list=el('ul','atlas-year-list');
    section.appendChild(el('h4',null,title+' · '+entries.length));
    for(const x of entries.slice(0,24)) {
      const name=people.get(x.person_id)?.name||bodies.get(x.body_id)?.name||'Неуточнённые участники';
      const item=el('li','atlas-year-item');
      item.append(el('div','atlas-year-person',name),el('div','atlas-year-meta',x.start.value+' — '+x.end.value+' · '+x.description+' ['+x.status+']'));
      if(x.person_id)item.appendChild(el('div','atlas-year-biography',bio(x.person_id)));
      if(power && x.note)item.appendChild(el('p','atlas-year-note',x.note));
      const links=el('div','atlas-year-citations');references(links,x.sources||[]);item.appendChild(links);
      list.appendChild(item);
    }
    section.appendChild(list);
    if(entries.length>24)section.appendChild(el('p','atlas-year-caveat','Ещё '+(entries.length-24)+' записей доступны в полном JSON.'));
    out.appendChild(section);
  }
  function render() {
    currentYear=Number(slider.value);yearLabel.textContent=String(currentYear);markYear();
    if(/^#\/timeline(?:\/\d{4})?$/.test(location.hash)){
      const path='#/timeline/'+currentYear;
      if(location.hash!==path)history.replaceState(null,'',path);
    }
    if(!atlas)return;
    const container=el('div','atlas-year-columns');
    // Formal/nominal or contested titles must not look like verified personal control.
    const nominal=new Set(['infant_emperor','nominal_grand_prince','nominal_due_to_illness','leadership_constrained_by_illness']);
    const all=atlas.power_assessments.filter(active);
    group('Фактическая и коллективная власть',all.filter(x=>!nominal.has(x.status)),container,true);
    group('Юридические должности',atlas.tenures.filter(active),container,false);
    if(all.some(x=>nominal.has(x.status))) group('Номинальные роли и ограничения',all.filter(x=>nominal.has(x.status)),container,true);
    results.replaceChildren(container);
  }
  function syncWindow() {
    const [a,b]=windowYears();slider.min=a;slider.max=b;
    if(currentYear<a||currentYear>b)slider.value=Math.floor((a+b)/2);
    render();queueMicrotask(markYear);
  }
  slider.addEventListener('input',render);
  window.addEventListener('hashchange',()=>{
    const route=/^#\/timeline\/(\d{4})$/.exec(location.hash);
    if(route){const y=Number(route[1]);if(y>=1417&&y<=1991&&y!==currentYear){slider.value=String(y);render();}}
  });
  panel.querySelectorAll('.era-btn').forEach(x=>x.addEventListener('click',()=>queueMicrotask(syncWindow)));
  canvas.addEventListener('click',event=>{
    const bar=event.target.closest('.time-bar');if(!bar||!atlas)return;
    queueMicrotask(()=>{
      const id=recordPerson.get(bar.dataset.record), detail=document.getElementById('timeline-selection');
      if(!id||!detail)return;
      detail.appendChild(el('p','atlas-year-biography','На '+currentYear+' год · '+bio(id)));
      const profile=el('a','spa-open-profile','Открыть биографию →');
      profile.href='#/people/'+encodeURIComponent(id);
      detail.appendChild(profile);
      const links=el('div','atlas-year-citations');
      references(links,(facts.get(id)||[]).filter(f=>['birth','dynasty','ethnic_origin'].includes(f.kind)).flatMap(f=>f.sources||[]));
      detail.appendChild(links);
    });
  });
  render();
  fetch('./atlas.json',{cache:'no-cache'}).then(response=>{
    if(!response.ok)throw new Error('HTTP '+response.status);
    return response.json();
  }).then(db=>{
    if(!db.people||!db.tenures||!db.power_assessments||!db.person_facts||!db.provenance)throw new Error('Неполная база');
    atlas=db;people=new Map(db.people.map(x=>[x.id,x]));bodies=new Map(db.bodies.map(x=>[x.id,x]));sources=new Map(db.sources.map(x=>[x.id,x]));
    facts=new Map(db.people.map(x=>[x.id,[]]));
    db.person_facts.forEach(x=>{if(facts.has(x.person_id))facts.get(x.person_id).push(x);});
    window.atlasAgeFor=(personId,year)=>age(personId,year);
    [...db.tenures,...db.power_assessments].forEach(x=>{if(x.person_id)recordPerson.set(x.record_id,x.person_id);});
    render();
  }).catch(error=>{
    results.replaceChildren(el('p','atlas-year-caveat','База биографий недоступна ('+error.message+'). Основная шкала продолжает работать.'));
  });
})();


/* SPA biography routing: client-only views of canonical, source-qualified data. */
(() => {
  'use strict';
  const panel=document.getElementById('panel-people');
  if(!panel)return;
  const search=document.getElementById('spa-people-search');
  const tools=document.getElementById('spa-people-tools');
  const status=document.getElementById('spa-people-status');
  const list=document.getElementById('spa-people-list');
  const detail=document.getElementById('spa-person-detail');
  const footerLink=document.querySelector('[data-atlas-database] a');
  if(footerLink){
    footerLink.href='#/people';
    footerLink.textContent='Биографии и источники · открыть в приложении';
  }
  let db=null,request=null,persons=new Map(),facts=new Map(),terms=new Map(),influence=new Map(),sources=new Map();
  function el(tag,cls,value){
    const node=document.createElement(tag);
    if(cls)node.className=cls;
    if(value!==undefined)node.textContent=String(value);
    return node;
  }
  function validUrl(uri){
    try{
      const url=new URL(uri);
      return url.protocol==='https:' && !url.username && !url.password &&
        !(['drive','.google.com'].join('')===url.hostname || ['docs','.google.com'].join('')===url.hostname);
    }catch(_){return false;}
  }
  function citations(parent,keys){
    const seen=new Set();
    for(const key of keys||[]){
      if(seen.has(key))continue;
      seen.add(key);
      const entry=sources.get(key);
      if(!entry || !validUrl(entry.url))continue;
      const link=el('a','spa-citation',key);
      link.href=entry.url;link.title=entry.title||key;
      link.target='_blank';link.rel='noopener noreferrer';
      parent.appendChild(link);
    }
  }
  function describe(f){
    if(f.value && typeof f.value==='object'){
      const calendar=f.value.calendar==='julian'?'старый стиль':
        f.value.calendar==='gregorian'?'новый стиль':'календарь не установлен';
      return f.value.value+' ('+calendar+(f.value.precision==='day'?'':', '+f.value.precision)+')';
    }
    return String(f.value||'нет данных');
  }
  function birth(id){
    const dates=(facts.get(id)||[]).filter(f=>f.kind==='birth');
    return dates.length?dates.map(describe).join(' / '):'Дата рождения не исследована';
  }
  function indexText(p){
    return [p.name,...(p.aliases||[]),
      ...(terms.get(p.id)||[]).map(x=>x.description),
      ...(facts.get(p.id)||[]).filter(x=>['dynasty','ethnic_origin','citizenship'].includes(x.kind)).map(describe)
    ].join(' ').toLocaleLowerCase('ru');
  }
  function showList(){
    panel.classList.remove('spa-profile-open');
    tools.hidden=false;list.hidden=false;detail.hidden=true;
    list.replaceChildren();
    const q=search.value.trim().toLocaleLowerCase('ru');
    const matches=[...persons.values()].filter(p=>indexText(p).includes(q))
      .sort((a,b)=>a.name.localeCompare(b.name,'ru'));
    status.textContent='Найдено '+matches.length+' из '+persons.size+' человек. Исходные источники доступны в карточках.';
    for(const p of matches){
      const card=el('a','spa-person-card');
      card.href='#/people/'+encodeURIComponent(p.id);
      const tenures=terms.get(p.id)||[];
      card.appendChild(el('strong',null,p.name));
      card.appendChild(el('small',null,birth(p.id)));
      card.appendChild(el('span','spa-card-description',
        tenures.length?tenures[0].description+(tenures.length>1?' · ещё '+(tenures.length-1)+' периода':''):
        'Участник регентства, коллективного органа или политического события'));
      list.appendChild(card);
    }
    if(!matches.length)list.appendChild(el('p','spa-empty','Совпадений нет. Попробуйте другую формулировку.'));
  }
  function factSection(id){
    const section=el('section','spa-fact-section');
    section.appendChild(el('h4',null,'Биографические сведения'));
    const records=(facts.get(id)||[]).filter(x=>x.kind!=='lifespan_text');
    if(!records.length)section.appendChild(el('p','spa-empty','Проверенные биографические сведения пока не внесены.'));
    const labels={birth:'Рождение',death:'Смерть',dynasty:'Династия / дом',
      ethnic_origin:'Этнокультурное происхождение',citizenship:'Подданство / гражданство'};
    for(const f of records){
      const part=el('div','spa-fact');
      part.append(el('b',null,(labels[f.kind]||f.kind)+': '),el('span',null,describe(f)));
      if(f.verification==='disputed' || (f.value && f.value.qualifier==='uncertain'))
        part.appendChild(el('small','spa-warning','Спорная или неопределённая датировка'));
      else if(f.verification==='imported_not_rechecked')
        part.appendChild(el('small','spa-warning','Нужна независимая проверка'));
      const links=el('div','spa-source-list');citations(links,f.sources);
      part.appendChild(links);section.appendChild(part);
    }
    return section;
  }
  function intervalSection(title,records){
    const section=el('section','spa-interval-section');
    section.appendChild(el('h4',null,title));
    if(!records.length){
      section.appendChild(el('p','spa-empty','Отдельная запись отсутствует; это не доказывает отсутствие влияния.'));
      return section;
    }
    const items=el('ul','spa-interval-list');
    for(const entry of records){
      const item=el('li','spa-interval');
      item.append(el('b',null,entry.start.value+' — '+entry.end.value),
        el('span',null,entry.description+' · '+entry.status));
      if(entry.note)item.appendChild(el('p',null,entry.note));
      const links=el('div','spa-source-list');citations(links,entry.sources);
      item.appendChild(links);items.appendChild(item);
    }
    section.appendChild(items);return section;
  }
  function showProfile(id){
    panel.classList.add('spa-profile-open');
    tools.hidden=false;list.hidden=false;detail.hidden=false;detail.replaceChildren();
    const back=el('a','spa-back','← Все биографии');back.href='#/people';detail.appendChild(back);
    const p=persons.get(id);
    if(!p){status.textContent='Такой личности в базе нет.';detail.appendChild(el('p','spa-empty','Запись не найдена.'));return;}
    detail.appendChild(el('h3',null,p.name));
    if((p.aliases||[]).length)detail.appendChild(el('p','spa-aliases','Другие имена: '+p.aliases.join(', ')));
    const appointments=terms.get(id)||[];
    const start=appointments.length?Number(appointments[0].start.value.slice(0,4)):
      Number(document.getElementById('atlas-year-range')?.value||1685);
    const chosen=Math.max(1417,Math.min(1991,start));
    const yearBar=el('div','spa-person-year');
    const label=el('label',null,'Возраст в году');label.htmlFor='spa-profile-year';
    const input=el('input','spa-year-number');
    input.type='number';input.id='spa-profile-year';input.min='1417';input.max='1991';input.step='1';
    input.value=String(chosen);
    const age=el('strong','spa-age-result');
    const timeline=el('a','spa-timeline-profile-link','Показать на временной шкале →');
    const updateAge=()=>{
      const y=Number(input.value);
      const valid=Number.isInteger(y)&&y>=1417&&y<=1991;
      age.textContent=valid?(typeof window.atlasAgeFor==='function'?window.atlasAgeFor(id,y):'не установлен')+' · '+y+' год':
        'Выберите год в диапазоне 1417–1991';
      timeline.href='#/timeline/'+(valid?y:chosen);
    };
    input.addEventListener('input',updateAge);
    yearBar.append(label,input,age,timeline);
    detail.append(yearBar,factSection(id),
      intervalSection('Юридические должности и правления',appointments),
      intervalSection('Оценки фактического влияния',influence.get(id)||[]));
    updateAge();status.textContent='Карточка: '+p.name+'. Каждое утверждение хранится отдельно от должности.';
  }
  function load(){
    if(db)return Promise.resolve(db);
    if(!request)request=fetch('./atlas.json',{cache:'no-cache'}).then(r=>{
      if(!r.ok)throw new Error('HTTP '+r.status);
      return r.json();
    }).then(result=>{
      if(!result.people || !result.tenures || !result.person_facts ||
         !result.power_assessments || !result.sources)throw new Error('Неполная база');
      db=result;
      persons=new Map(db.people.map(p=>[p.id,p]));
      sources=new Map(db.sources.map(s=>[s.id,s]));
      facts=new Map(db.people.map(p=>[p.id,[]]));
      terms=new Map(db.people.map(p=>[p.id,[]]));
      influence=new Map(db.people.map(p=>[p.id,[]]));
      db.person_facts.forEach(f=>{if(facts.has(f.person_id))facts.get(f.person_id).push(f);});
      db.tenures.forEach(t=>{if(terms.has(t.person_id))terms.get(t.person_id).push(t);});
      db.power_assessments.forEach(t=>{if(influence.has(t.person_id))influence.get(t.person_id).push(t);});
      for(const records of [...terms.values(),...influence.values()])
        records.sort((a,b)=>a.start.value.localeCompare(b.start.value));
      return db;
    }).catch(error=>{request=null;throw error;});
    return request;
  }
  let ticket=0;
  function handleRoute(){
    if(panel.hidden)return;
    const seq=++ticket;
    const route=/^\/people(?:\/(person-[a-z0-9-]+))?$/.exec(decodeURIComponent(location.hash.slice(1)));
    const personId=route?route[1]:null;
    status.textContent='Загрузка биографий…';
    load().then(()=>{
      if(seq!==ticket||panel.hidden)return;
      if(personId)showProfile(personId);else showList();
    }).catch(error=>{
      if(seq!==ticket||panel.hidden)return;
      status.textContent='База недоступна: '+error.message;
      list.replaceChildren();
      const fallback=el('a',null,'Открыть резервную таблицу');fallback.href='./database.html';
      list.appendChild(fallback);list.hidden=false;detail.hidden=true;
    });
  }
  search.addEventListener('input',()=>{if(db&&!panel.hidden&&detail.hidden)showList();});
  window.addEventListener('atlas:route',handleRoute);
  handleRoute();
})();


/* Atlas workspace: persistent navigation and independent scrolling regions.
   No history data, source links or storage are changed by this module. */
(() => {
  'use strict';
  const timeline = document.getElementById('panel-timeline');
  const people = document.getElementById('panel-people');
  const toolbar = timeline && timeline.querySelector('.timeline-toolbar');
  const inspector = timeline && timeline.querySelector('.atlas-year-inspector');
  const chart = timeline && timeline.querySelector('.timeline-box');
  const selected = chart && chart.querySelector('#timeline-selection');
  const viewport = chart && chart.querySelector('.timeline-scroll');
  const canvas = chart && chart.querySelector('.time-canvas');
  if (!timeline || !people || !toolbar || !inspector || !chart ||
      !selected || !viewport || !canvas) return;

  document.documentElement.classList.add('atlas-app');
  const brand = document.querySelector('.brand');
  if (brand) {
    brand.textContent = 'АТЛАС ВЛАСТИ';
    const years = document.createElement('span');
    years.className = 'atlas-brand-years';
    years.textContent = '1417–1991';
    brand.appendChild(years);
  }
  const researchLink = document.querySelector('.topnav-links a[href="#research"]');
  if (researchLink) researchLink.href = '#/research';

  // The public source/revision footer remains available in Research, but
  // must not consume viewport height below the application work area.
  const footer = document.querySelector('body > footer.footer');
  const research = document.getElementById('panel-research');
  if (footer && research) {
    footer.classList.add('atlas-inline-footer');
    research.appendChild(footer);
  }

  // Biographies keep search/results visible beside the open profile on desktop.
  // Mobile displays the profile as its own screen with a back link.
  const search = people.querySelector('#spa-people-tools');
  const status = people.querySelector('#spa-people-status');
  const cards = people.querySelector('#spa-people-list');
  const profile = people.querySelector('#spa-person-detail');
  if (search && status && cards && profile) {
    const work = document.createElement('div');
    work.className = 'spa-people-workspace';
    const browser = document.createElement('div');
    browser.className = 'spa-people-browser';
    people.insertBefore(work, search);
    browser.append(search, status, cards);
    profile.tabIndex = -1;
    work.append(browser, profile);
  }

  // Build a two-pane historical workspace without changing legacy generated
  // HTML anchors, the three tracks or the year-inspector data contract.
  const work = document.createElement('div');
  work.className = 'atlas-timeline-workspace';
  timeline.insertBefore(work, inspector);
  const sidebar = document.createElement('aside');
  sidebar.className = 'atlas-sidebar';
  sidebar.id = 'atlas-sidebar';
  sidebar.setAttribute('aria-label', 'Сведения о выбранном периоде');
  const sidebarHeading = document.createElement('div');
  sidebarHeading.className = 'atlas-sidebar-heading';
  const sidebarTitle = document.createElement('strong');
  sidebarTitle.textContent = 'Год и исторические сведения';
  const close = document.createElement('button');
  close.className = 'atlas-sidebar-close';
  close.type = 'button';
  close.textContent = 'Закрыть';
  sidebarHeading.append(sidebarTitle, close);
  sidebar.append(sidebarHeading, selected, inspector);
  timeline.querySelectorAll(':scope > .timeline-footnote').forEach(node => sidebar.appendChild(node));
  work.append(chart, sidebar);

  // A real, dismissible backdrop makes historical details a readable mobile
  // bottom sheet instead of the old narrow sidebar crammed alongside a chart.
  const scrim=document.createElement('button');
  scrim.type='button';
  scrim.className='atlas-mobile-scrim';
  scrim.hidden=true;
  scrim.textContent='Закрыть сведения';
  scrim.setAttribute('aria-label','Закрыть сведения о выбранном периоде');
  document.body.appendChild(scrim);

  // Explicit zoom and century navigation; track rows are panned together by
  // their own horizontal scroll container. Touch uses native scrolling.
  const controls = document.createElement('div');
  controls.className = 'atlas-timeline-controls';
  controls.setAttribute('role', 'group');
  controls.setAttribute('aria-label', 'Навигация по временной шкале');
  function button(label, title, cls) {
    const b = document.createElement('button');
    b.type = 'button'; b.textContent = label; b.title = title;
    b.className = 'atlas-control ' + cls;
    controls.appendChild(b);
    return b;
  }
  const earlier = button('← Раньше', 'Переместить шкалу назад во времени', 'atlas-pan');
  const later = button('Позже →', 'Переместить шкалу вперёд во времени', 'atlas-pan');
  const minus = button('−', 'Уменьшить масштаб', 'atlas-zoom-out');
  const zoomLabel = document.createElement('output');
  zoomLabel.className = 'atlas-zoom-label';
  zoomLabel.setAttribute('aria-live', 'polite');
  controls.appendChild(zoomLabel);
  const plus = button('+', 'Увеличить масштаб', 'atlas-zoom-in');
  const fit = button('Весь период', 'Показать весь выбранный период', 'atlas-fit');
  const dateLabel = document.createElement('label');
  dateLabel.className = 'atlas-goto-label';
  dateLabel.textContent = 'Год ';
  const date = document.createElement('input');
  date.id = 'atlas-goto-year';
  date.type = 'number'; date.min = '1417'; date.max = '1991'; date.step = '1';
  date.setAttribute('aria-label', 'Перейти к году');
  dateLabel.appendChild(date);
  controls.appendChild(dateLabel);
  const toggle = button('Сведения о годе', 'Открыть сведения о выбранном годе', 'atlas-sidebar-toggle');
  toggle.setAttribute('aria-controls', 'atlas-sidebar');
  toggle.setAttribute('aria-expanded', 'false');
  toggle.setAttribute('aria-haspopup', 'dialog');
  toolbar.appendChild(controls);

  const yearSlider = inspector.querySelector('#atlas-year-range');
  const zoomSteps = [1, 1.5, 2.3, 3.5, 5, 7.5, 11];
  let zoomIndex = 2;
  let drag = null;
  const narrow = window.matchMedia('(max-width: 900px)');
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

  function yearBounds() {
    const active = toolbar.querySelector('.era-btn[aria-pressed="true"]');
    const nums = active && active.textContent.match(/\d{4}/g);
    return nums && nums.length >= 2 ? nums.slice(0, 2).map(Number) : [1417, 1991];
  }
  function layoutWidth() {
    return Math.ceil(Math.max(320, viewport.clientWidth) * zoomSteps[zoomIndex]);
  }
  function updateCanvas(keepCenter) {
    if (!viewport.clientWidth) return;
    const oldWidth = Math.max(1, canvas.getBoundingClientRect().width);
    const ratio = oldWidth > viewport.clientWidth
      ? (viewport.scrollLeft + viewport.clientWidth / 2) / oldWidth : 0.5;
    canvas.style.width = layoutWidth() + 'px';
    if (keepCenter) viewport.scrollLeft = ratio * canvas.getBoundingClientRect().width - viewport.clientWidth / 2;
    zoomLabel.textContent = Math.round(zoomSteps[zoomIndex] * 100) + '%';
    minus.disabled = zoomIndex === 0;
    plus.disabled = zoomIndex === zoomSteps.length - 1;
  }
  function focusYear(year) {
    if (!viewport.clientWidth) return;
    const range = yearBounds();
    const fraction = Math.max(0, Math.min(1, (year - range[0]) / Math.max(1, range[1] - range[0])));
    const x = 142 + Math.max(0, canvas.clientWidth - 142) * fraction;
    viewport.scrollLeft = Math.max(0, x - viewport.clientWidth / 2);
  }
  function selectedYear() {
    return yearSlider ? Number(yearSlider.value) : 1685;
  }
  function updateYearInput() {
    if (!yearSlider) return;
    date.min = yearSlider.min;
    date.max = yearSlider.max;
    date.value = yearSlider.value;
  }
  function setZoom(index) {
    zoomIndex = Math.max(0, Math.min(zoomSteps.length - 1, index));
    updateCanvas(true);
  }
  minus.addEventListener('click', () => setZoom(zoomIndex - 1));
  plus.addEventListener('click', () => setZoom(zoomIndex + 1));
  fit.addEventListener('click', () => {setZoom(0); focusYear(selectedYear());});
  function pan(direction) {
    const distance = Math.max(100, viewport.clientWidth * 0.75);
    viewport.scrollBy({left: direction * distance, behavior: reducedMotion.matches ? 'instant' : 'smooth'});
  }
  earlier.addEventListener('click', () => pan(-1));
  later.addEventListener('click', () => pan(1));
  date.addEventListener('change', () => {
    const year = Number(date.value);
    if (!yearSlider || !Number.isInteger(year) ||
        year < Number(yearSlider.min) || year > Number(yearSlider.max)) {
      updateYearInput();
      return;
    }
    yearSlider.value = String(year);
    yearSlider.dispatchEvent(new Event('input', {bubbles: true}));
    focusYear(year);
  });
  if (yearSlider) yearSlider.addEventListener('input', () => {
    updateYearInput();
    focusYear(selectedYear());
  });
  toolbar.querySelectorAll('.era-btn').forEach(b => b.addEventListener('click', () => {
    queueMicrotask(() => {updateYearInput(); updateCanvas(false); focusYear(selectedYear());});
  }));

  function openSidebar() {
    if (!narrow.matches) return;
    work.classList.add('atlas-sidebar-open');
    toggle.setAttribute('aria-expanded', 'true');
    sidebar.removeAttribute('inert');
    sidebar.setAttribute('role','dialog');
    sidebar.setAttribute('aria-modal','true');
    scrim.hidden=false;
    document.documentElement.classList.add('atlas-mobile-details-open');
    close.focus({preventScroll: true});
  }
  function closeSidebar() {
    work.classList.remove('atlas-year-overview-open');
    work.classList.remove('atlas-sidebar-open');
    toggle.setAttribute('aria-expanded', 'false');
    if (narrow.matches) sidebar.setAttribute('inert', '');
    scrim.hidden=true;
    document.documentElement.classList.remove('atlas-mobile-details-open');
    sidebar.removeAttribute('aria-modal');
    sidebar.removeAttribute('role');
    if (!timeline.hidden) toggle.focus({preventScroll: true});
  }
  function syncSidebar() {
    if (narrow.matches && !work.classList.contains('atlas-sidebar-open'))
      sidebar.setAttribute('inert', '');
    else sidebar.removeAttribute('inert');
    if (!narrow.matches){
      scrim.hidden=true;
      document.documentElement.classList.remove('atlas-mobile-details-open');
      sidebar.removeAttribute('aria-modal');
      sidebar.removeAttribute('role');
    }
  }
  // Year summary cards can show the full, sourced dossier on demand.
  window.addEventListener('atlas:show-year-details', () => {
    if (timeline.hidden) return;
    work.classList.add('atlas-year-overview-open');
    sidebarTitle.textContent='Все записи · '+selectedYear()+' год';
    if (narrow.matches) openSidebar();
    else {
      sidebar.scrollTop = 0;
      sidebar.tabIndex = -1;
      sidebar.focus({preventScroll: true});
    }
  });
  toggle.addEventListener('click', () => {
    if (work.classList.contains('atlas-sidebar-open')) closeSidebar();
    else openSidebar();
  });
  close.addEventListener('click', closeSidebar);
  scrim.addEventListener('click',closeSidebar);
  // Touch-down on the sheet heading allows a familiar downward dismissal
  // without stealing vertical scrolling inside historical evidence text.
  let sheetTouch=null;
  sidebarHeading.addEventListener('pointerdown',event=>{
    if(event.pointerType!=='touch'||event.target.closest('button'))return;
    sheetTouch={id:event.pointerId,x:event.clientX,y:event.clientY};
  });
  sidebarHeading.addEventListener('pointerup',event=>{
    if(!sheetTouch||sheetTouch.id!==event.pointerId)return;
    const dy=event.clientY-sheetTouch.y,dx=event.clientX-sheetTouch.x;
    sheetTouch=null;
    if(dy>70&&Math.abs(dx)<65)closeSidebar();
  });
  sidebarHeading.addEventListener('pointercancel',()=>{sheetTouch=null;});
  timeline.addEventListener('keydown', event => {
    if(!work.classList.contains('atlas-sidebar-open'))return;
    if(event.key === 'Escape'){
      event.preventDefault();closeSidebar();return;
    }
    if(event.key==='Tab'&&narrow.matches){
      const items=[...sidebar.querySelectorAll('button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), [tabindex="0"]')]
        .filter(node=>node.getClientRects().length);
      if(!items.length)return;
      const first=items[0],last=items[items.length-1];
      if(event.shiftKey&&document.activeElement===first){
        event.preventDefault();last.focus();
      }else if(!event.shiftKey&&document.activeElement===last){
        event.preventDefault();first.focus();
      }
    }
  });
  if (narrow.addEventListener) narrow.addEventListener('change', syncSidebar);
  syncSidebar();

  // Bar clicks retain the existing sourced details; expose them in a drawer
  // on narrow screens instead of pushing the timeline below the fold.
  const plots = timeline.querySelector('#time-canvas');
  if (plots) plots.addEventListener('click', event => {
    if (event.target.closest('.time-bar')) {
      work.classList.remove('atlas-year-overview-open');
      sidebarTitle.textContent='Выбранный период';
      if (narrow.matches) openSidebar();
      else sidebar.scrollTop = 0;
    }
  });

  // Desktop mouse dragging pans empty chart background, without stealing bar
  // clicks. Mobile touch panning remains native and scrollable on both axes.
  viewport.addEventListener('pointerdown', event => {
    if (event.pointerType !== 'mouse' || event.button !== 0 ||
        event.target.closest('button,a,input,summary')) return;
    drag = {id: event.pointerId, x: event.clientX, scroll: viewport.scrollLeft};
    viewport.setPointerCapture(event.pointerId);
    viewport.classList.add('atlas-is-panning');
  });
  viewport.addEventListener('pointermove', event => {
    if (!drag || event.pointerId !== drag.id) return;
    viewport.scrollLeft = drag.scroll - (event.clientX - drag.x);
  });
  function stopDrag(event) {
    if (!drag || event.pointerId !== drag.id) return;
    drag = null; viewport.classList.remove('atlas-is-panning');
    if (viewport.hasPointerCapture(event.pointerId)) viewport.releasePointerCapture(event.pointerId);
  }
  viewport.addEventListener('pointerup', stopDrag);
  viewport.addEventListener('pointercancel', stopDrag);
  viewport.addEventListener('lostpointercapture', () => {
    drag = null; viewport.classList.remove('atlas-is-panning');
  });

  window.addEventListener('atlas:route', event => {
    if (event.detail.view === 'timeline') {
      updateCanvas(false);
      updateYearInput();
      focusYear(selectedYear());
    } else {
      work.classList.remove('atlas-sidebar-open');
      work.classList.remove('atlas-year-overview-open');
      toggle.setAttribute('aria-expanded', 'false');
      scrim.hidden=true;
      document.documentElement.classList.remove('atlas-mobile-details-open');
      sidebar.removeAttribute('aria-modal');
      sidebar.removeAttribute('role');
      syncSidebar();
    }
  });
  window.addEventListener('resize', () => updateCanvas(true));
  updateCanvas(false);
  updateYearInput();
  if (!timeline.hidden) focusYear(selectedYear());
})();
