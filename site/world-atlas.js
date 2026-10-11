/* International source-backed pilot, integrated as a URL-addressable SPA sheet.
   Never infer ethnicity from state, dynasty, birthplace or personal name. */
(() => {
  'use strict';
  if (!document.getElementById('chronology-data')) return;

  const el = (tag, className, value) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (value !== undefined) node.textContent = String(value);
    return node;
  };
  const svgNS = 'http://www.w3.org/2000/svg';
  const sv = (tag, attrs, text) => {
    const node = document.createElementNS(svgNS, tag);
    Object.entries(attrs || {}).forEach(([key,value]) => node.setAttribute(key, String(value)));
    if (text !== undefined) node.textContent = String(text);
    return node;
  };
  const layer = el('div','atlas-world-layer');
  layer.hidden = true;
  const dialog = el('section','atlas-world-dialog');
  dialog.setAttribute('role','dialog');
  dialog.setAttribute('aria-modal','true');
  dialog.setAttribute('aria-labelledby','atlas-world-title');
  const head = el('div','atlas-world-head');
  const headTitle = el('div','atlas-world-head-title');
  headTitle.append(el('span','atlas-world-eyebrow','Международный исторический атлас · пилот 01'));
  const heading = el('h2',null,'Европа · 1762');
  heading.id='atlas-world-title';
  headTitle.append(heading);
  const close = el('button','atlas-world-close','Закрыть ×');
  close.type='button';
  close.setAttribute('aria-label','Закрыть международный граф');
  head.append(headTitle,close);
  const main = el('div','atlas-world-content');
  const lead = el('p','atlas-world-lead',
    'Три государства, четыре монарха. Цвет переключает признак, ' +
    'но не превращает место рождения или династию в национальность.');
  const controls = el('div','atlas-world-switches');
  controls.setAttribute('role','group');
  controls.setAttribute('aria-label','Как окрашивать участников графа');
  const modes = [
    ['state','Государства'],
    ['origin','Происхождение'],
    ['dynasty','Династии']
  ];
  let mode='state';
  const modeButtons = new Map();
  for (const [key,label] of modes) {
    const button=el('button','atlas-world-mode',label);
    button.type='button';
    button.dataset.worldMode=key;
    button.setAttribute('aria-pressed', String(mode===key));
    button.addEventListener('click',()=>{
      if (mode===key) return;
      mode=key;
      for (const [k,btn] of modeButtons) btn.setAttribute('aria-pressed',String(k===mode));
      render();
    });
    modeButtons.set(key,button);
    controls.appendChild(button);
  }
  const status = el('p','atlas-world-status','Загружаем источниковый срез…');
  status.setAttribute('role','status');
  status.setAttribute('aria-live','polite');
  const graph = el('div','atlas-world-graph-scroll');
  graph.setAttribute('role','region');
  graph.setAttribute('aria-label','Граф государств и правителей; прокрутка влево и вправо');
  graph.tabIndex=0;
  const graphHint=el('p','atlas-world-graph-hint','Граф можно листать горизонтально. Все записи и источники доступны также в карточках ниже.');
  const countryCards=el('div','atlas-world-country-grid');
  const relations=el('div','atlas-world-relations');
  const limitations=el('p','atlas-world-limitations',
    'Это не полный состав правительств и не карта исторических границ. ' +
    'Годовое пересечение не доказывает одновременность монархов. ' +
    'Неизвестное происхождение обозначено явно; гражданство не вычисляется.');
  main.append(lead,controls,status,graph,graphHint,countryCards,relations,limitations);
  dialog.append(head,main);
  layer.appendChild(dialog);
  document.body.appendChild(layer);

  let data=null,atlas=null,opening=null,focusBefore=null;
  const dynastyColors = {
    'holstein-gottorp':'#8a669a',
    'anhalt-zerbst':'#bd8947',
    'bourbon':'#527aac',
    'hohenzollern':'#508e7d'
  };
  const unknown = '#888d91';
  const sourceIndex=()=>new Map([
    ...(data?.sources||[]),
    ...(atlas?.sources||[])
  ].map(s=>[s.id,s]));
  const canonicalPeople=()=>new Map((atlas?.people||[]).map(x=>[x.id,x]));
  const canonicalTenures=()=>new Map((atlas?.tenures||[]).map(x=>[x.id,x]));
  const originFact = p => {
    const fact = (atlas?.person_facts||[]).find(f =>
      f.id===p.ethnic_origin_fact_id && f.person_id===p.canonical_person_id &&
      f.kind==='ethnic_origin' && f.verification==='reference_checked');
    return fact || null;
  };
  const nameOf = p => p.canonical_person_id
    ? canonicalPeople().get(p.canonical_person_id)?.name || 'Имя не установлено в основной базе'
    : p.name;
  const stateOf = id => (data?.countries||[]).find(c=>c.id===id);
  const personOf = id => (data?.persons||[]).find(p=>p.id===id);
  const accent = p => {
    if (mode==='state') return stateOf(p.country_id)?.color || unknown;
    if (mode==='origin') return originFact(p) ? '#9166a6' : unknown;
    return dynastyColors[p.dynasty?.id] || unknown;
  };
  const colorText = p => {
    if (mode==='state') return stateOf(p.country_id)?.label || 'Неизвестно';
    if (mode==='origin') return originFact(p)?.value || 'Не исследовано';
    return p.dynasty?.name || 'Не исследовано';
  };
  const safeUrl = url => {
    try {
      const u=new URL(url);
      return u.protocol==='https:' && !u.username && !u.password &&
        !['drive.google.com','docs.google.com'].includes(u.hostname);
    } catch(_) { return false; }
  };
  function sourcesFor(ids) {
    const result=el('div','atlas-world-citations');
    const sources=sourceIndex();
    [...new Set(ids || [])].forEach(id=>{
      const source=sources.get(id);
      if (!source || !safeUrl(source.url)) return;
      const link=el('a','atlas-world-source',id+' ↗');
      link.href=source.url;
      link.target='_blank';
      link.rel='noopener noreferrer';
      link.title=source.title || id;
      result.append(link);
    });
    return result;
  }
  function nodeText(parent,x,y,lines) {
    lines.forEach((line,i)=>{
      parent.appendChild(sv('text',{
        x,y:y+i*18,'text-anchor':'middle',
        fill: i===0 ? '#20302e' : '#52645e',
        'font-size': i===0?15:11,
        'font-weight':i===0?700:500
      },line));
    });
  }
  function drawGraph() {
    const svg=sv('svg',{viewBox:'0 0 1040 390',width:'1040',height:'390',
      role:'img','aria-label':'Россия: Пётр III и Екатерина II; Франция: Людовик XV; Пруссия: Фридрих II. Брак и мирный договор обозначены разными типами связей.'});
    const title=sv('title',{},'Структура четырёх монархов в трёх государствах, 1762');
    const desc=sv('desc',{},'Сплошные линии соединяют правителей с государствами. Брак Петра III и Екатерины II показан отдельной линией. Пунктир сверху — мирный договор России с Пруссией; это не родственная связь.');
    svg.append(title,desc);
    const stateX={ru:205,fr:520,pr:835};
    const personXY={
      'ru-peter3':{x:115,y:235},
      'ru-catherine2':{x:300,y:235},
      'fr-louis15':{x:520,y:235},
      'pr-frederick2':{x:835,y:235}
    };
    // Treaty is a relation between states; never turn it into kinship.
    svg.appendChild(sv('path',{
      d:'M205 77 C285 1 755 1 835 77',
      stroke:'#a27543','stroke-width':'2.5','stroke-dasharray':'7 5',
      fill:'none'
    }));
    const treatyText=sv('text',{x:520,y:24,'text-anchor':'middle',
      'font-size':'13','font-weight':'700',fill:'#8d602f'},'Петербургский мир · 1762');
    svg.appendChild(treatyText);
    data.countries.forEach(country=>{
      const cx=stateX[country.id];
      const rect=sv('rect',{x:cx-128,y:77,width:256,height:66,rx:12,
        fill:'#f5f5f0',stroke:country.color,'stroke-width':2.5});
      svg.appendChild(rect);
      nodeText(svg,cx,103,[country.label,country.id==='ru'?'Смена власти в 1762 году':'Правитель в 1762 году']);
    });
    data.persons.forEach(p=>{
      const pt=personXY[p.id], cx=stateX[p.country_id];
      svg.appendChild(sv('path',{d:'M'+cx+' 143 L'+pt.x+' 184',
        stroke:stateOf(p.country_id).color,'stroke-width':2,fill:'none'}));
      const paint=accent(p);
      svg.appendChild(sv('rect',{x:pt.x-88,y:185,width:176,height:104,rx:12,
        fill:'#fffdf8',stroke:paint,'stroke-width':3}));
      svg.appendChild(sv('circle',{cx:pt.x-65,cy:203,r:6,fill:paint}));
      const shortName=p.id==='ru-peter3'?'Пётр III':
        p.id==='ru-catherine2'?'Екатерина II':nameOf(p);
      nodeText(svg,pt.x,228,[shortName,p.role]);
      svg.appendChild(sv('text',{x:pt.x,y:273,'text-anchor':'middle',
        'font-size':'11',fill:paint,'font-weight':'600'},
        mode==='state'?'Государство':mode==='origin'?
        (originFact(p)?'Есть источник':'Не исследовано'):'Династия'));
    });
    svg.appendChild(sv('path',{d:'M115 289 Q207 358 300 289',fill:'none',
      stroke:'#8666a1','stroke-width':2.5}));
    svg.appendChild(sv('text',{x:207,y:357,'text-anchor':'middle',
      'font-size':'13',fill:'#74538f','font-weight':'700'},'Брак · 1745'));
    svg.appendChild(sv('text',{x:520,y:380,'text-anchor':'middle',
      'font-size':'11',fill:'#52645e'},'Цвет узла = выбранный признак · серый = нет источниковой этнической записи'));
    return svg;
  }
  function personCard(p) {
    const card=el('article','atlas-world-person');
    card.style.setProperty('--person-color',accent(p));
    const title=el('h4',null,nameOf(p));
    card.append(title,el('p','atlas-world-role',p.role));
    const when = p.term.label ||
      ((p.term.start||'?')+'–'+(p.term.end||'?')+' · годы, не точные дни');
    card.append(el('p','atlas-world-dates',when));
    if (p.canonical_person_id && canonicalTenures().has(p.canonical_tenure_id)) {
      const detail=el('a','atlas-world-person-link','Биография в нашем атласе ↗');
      detail.href='#/people/'+encodeURIComponent(p.canonical_person_id);
      detail.addEventListener('click',()=>dismiss(false));
      card.append(detail);
    }
    const traits=el('dl','atlas-world-traits');
    const add=(name,value)=>{
      traits.append(el('dt',null,name),el('dd',null,value));
    };
    add('Государство должности',stateOf(p.country_id).label);
    add('Место рождения',p.birth.place+' · '+p.birth.historical_polity);
    add('Дом / династия',p.dynasty.name+' ('+p.dynasty.qualifier+')');
    add('Этнокультурное происхождение',originFact(p)?.value || 'Не исследовано — не угадываем');
    card.append(traits,el('p','atlas-world-person-note',p.note));
    const ids=[...(p.sources||[]),...(p.birth.sources||[]),
      ...(p.dynasty.sources||[])];
    if (originFact(p)) ids.push(...(originFact(p).sources||[]));
    card.append(sourcesFor(ids));
    return card;
  }
  function render() {
    if (!data || !atlas) return;
    status.textContent='Три исторических государства · четыре монарха · '+
      (mode==='state'?'окраска по государству':
       mode==='origin'?'только документированное этнокультурное происхождение':
       'окраска по династическим домам');
    graph.replaceChildren(drawGraph());
    const countryNodes=[];
    data.countries.forEach(c=>{
      const section=el('section','atlas-world-country');
      section.style.setProperty('--country-color',c.color);
      section.append(el('h3',null,c.label));
      const people=el('div','atlas-world-people');
      data.persons.filter(p=>p.country_id===c.id).forEach(p=>people.append(personCard(p)));
      section.append(people,el('p','atlas-world-country-note',c.note));
      countryNodes.push(section);
    });
    countryCards.replaceChildren(...countryNodes);
    const heading=el('h3',null,'Подтверждённые связи');
    const items=el('div','atlas-world-relation-grid');
    data.relations.forEach(r=>{
      const box=el('article','atlas-world-relation');
      box.append(
        el('span','atlas-world-relation-type',r.kind==='marriage'?'Династическая связь':'Межгосударственные отношения'),
        el('h4',null,r.label),
        el('p',null,r.detail),
        sourcesFor(r.sources)
      );
      items.append(box);
    });
    const originInsight=el('p','atlas-world-insight',
      'Наблюдение пилота: Екатерина II родилась в прусском Штеттине, ' +
      'но в 1762 году стала императрицей России. Пётр III родился в Гольштейне. ' +
      'Это сведения о месте рождения, не оценка этнического состава правителей.');
    relations.replaceChildren(heading,items,originInsight);
  }
  async function load() {
    if (data && atlas) return;
    if (opening) return opening;
    opening=Promise.all([
      fetch('./world-1762.json',{cache:'no-cache'}).then(r=>{
        if(!r.ok)throw new Error('Пилот недоступен');
        return r.json();
      }),
      fetch('./atlas.json',{cache:'no-cache'}).then(r=>{
        if(!r.ok)throw new Error('Основная база недоступна');
        return r.json();
      })
    ]).then(([world,base])=>{
      if (world.schema_version!=='world-pilot-v1' || world.year!==1762 ||
          world.persons?.length!==4 || world.countries?.length!==3 ||
          !Array.isArray(base.people) || !Array.isArray(base.tenures))
        throw new Error('Некорректная структура');
      // Fail closed for canonical linkage, instead of silently duplicating IDs.
      const pids=new Set(base.people.map(x=>x.id));
      const tids=new Map(base.tenures.map(x=>[x.id,x]));
      world.persons.forEach(p=>{
        if (!p.canonical_person_id) return;
        if (!pids.has(p.canonical_person_id) ||
            tids.get(p.canonical_tenure_id)?.person_id!==p.canonical_person_id)
          throw new Error('Связь с основной базой не подтверждена');
      });
      data=world; atlas=base; render();
    }).catch(()=>{
      status.textContent='Не удалось загрузить проверенные данные. Исторические сведения не подставляются догадками.';
    }).finally(()=>{opening=null;});
    return opening;
  }
  const isWorldURL=()=>new URL(location.href).searchParams.get('world')==='1762';
  function urlFor(open) {
    const u=new URL(location.href);
    if(open) u.searchParams.set('world','1762');
    else u.searchParams.delete('world');
    return u.pathname+u.search+u.hash;
  }
  function show(fromClick) {
    if (!layer.hidden) return;
    if (fromClick) focusBefore=document.activeElement;
    layer.hidden=false;
    document.documentElement.classList.add('atlas-world-open');
    close.focus({preventScroll:true});
    load();
  }
  function hide() {
    if (layer.hidden) return;
    layer.hidden=true;
    document.documentElement.classList.remove('atlas-world-open');
    if(focusBefore?.isConnected) focusBefore.focus({preventScroll:true});
    focusBefore=null;
  }
  function dismiss(push) {
    if (isWorldURL()) {
      const next=urlFor(false);
      if(push) history.pushState(null,'',next);
      else history.replaceState(null,'',next);
    }
    hide();
  }
  function sync() { if (isWorldURL()) show(false); else hide(); }
  document.addEventListener('click',event=>{
    const trigger=event.target.closest('a[data-world-open]');
    if (!trigger) return;
    if (event.metaKey||event.ctrlKey||event.altKey||event.shiftKey||event.button!==0) return;
    event.preventDefault();
    if (!isWorldURL()) history.pushState(null,'',urlFor(true));
    show(true);
  });
  close.addEventListener('click',()=>dismiss(true));
  layer.addEventListener('click',event=>{if(event.target===layer)dismiss(true);});
  dialog.addEventListener('keydown',event=>{
    if(event.key==='Escape'){event.preventDefault();dismiss(true);return;}
    if(event.key!=='Tab')return;
    const focusable=Array.from(dialog.querySelectorAll('button:not([disabled]),a[href],[tabindex="0"]'))
      .filter(x=>x.getClientRects().length>0);
    if(!focusable.length)return;
    const first=focusable[0],last=focusable[focusable.length-1];
    if(event.shiftKey&&document.activeElement===first){
      event.preventDefault();last.focus();
    } else if(!event.shiftKey&&document.activeElement===last){
      event.preventDefault();first.focus();
    }
  });
  window.addEventListener('popstate',sync);
  window.addEventListener('hashchange',sync);
  sync();
})();
