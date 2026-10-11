/* Coverage of historical RESEARCH RECORDS, never of territorial rule itself.
   Empty cell == unresearched in our pilot; existing cell == PARTIAL source sample.
   No maps, inferred borders, invented office-holders, percentage completeness,
   historical absence or interpolation between 1688, 1788 and 1888.
*/
(() => {
  'use strict';
  const host=document.getElementById('world-coverage-app');
  if(!host)return;
  const DIMENSIONS=[
    ['all','Все типы'],
    ['legal','Юридические'],
    ['practical','Фактические (локально)'],
    ['institutional','Институциональные'],
    ['military','Военные'],
    ['diplomatic','Дипломатические']
  ];
  const allowedDims=new Set(DIMENSIONS.map(x=>x[0]));
  const element=(tag,cls,txt)=>{
    const n=document.createElement(tag);
    if(cls)n.className=cls;
    if(txt!==undefined)n.textContent=String(txt);
    return n;
  };
  const add=(parent,...children)=>parent.append(...children);
  const query=k=>new URL(location.href).searchParams.get(k);
  const safeUrl=url=>{
    try{
      const x=new URL(url);
      return x.protocol==='https:'&&!x.username&&!x.password&&
        ![['drive','.google.com'].join(''),
          ['docs','.google.com'].join('')].includes(x.hostname);
    }catch(_){return false;}
  };
  let model=null,dim='all',selection=null;
  const main=element('div','coverage-content');
  const heading=element('h1',null,'Где мы уже исследовали историю?');
  const lead=element('p','coverage-lead',
    'Матрица показывает только записи нашего пилота о политической власти. '+
    'Она не показывает отсутствие государств и не оценивает полноту мировой истории.');
  const summary=element('p','coverage-summary','Загружаем исследовательские срезы…');
  summary.setAttribute('role','status');summary.setAttribute('aria-live','polite');
  const legend=element('div','coverage-legend');
  const part=element('span','coverage-legend-item',
    'Частичный срез — есть ссылки на конкретные сведения');
  part.dataset.status='partial_sample';
  const unknown=element('span','coverage-legend-item',
    'Не исследовано — нет записей в нашем реестре');
  unknown.dataset.status='not_researched';
  add(legend,part,unknown);
  const controls=element('div','coverage-dim-controls');
  controls.setAttribute('role','group');
  controls.setAttribute('aria-label','Выбранный тип политических отношений');
  const caption=element('h2','coverage-section-heading','Матрица по темам и годам');
  const scroll=element('div','coverage-matrix-scroll');
  scroll.tabIndex=0;
  scroll.setAttribute('role','region');
  scroll.setAttribute('aria-label','Таблица семи исследовательских тем для трёх несмежных лет');
  const table=element('table','coverage-table');
  const tableCaption=element('caption',null,'Покрытие записей: 1688, 1788, 1888');
  const thead=element('thead'),tbody=element('tbody');
  add(table,tableCaption,thead,tbody);scroll.append(table);
  const help=element('p','coverage-help',
    'Ячейка со сведениями означает неполный набор фактов. '+
    'Нулевая ячейка не доказывает, что власть или государство отсутствовали. '+
    'Мы не проверяли все годы между тремя выбранными датами.');
  const detail=element('section','coverage-detail');
  detail.id='coverage-detail';detail.tabIndex=-1;
  detail.setAttribute('aria-label','Подробности и источники исследования выбранной ячейки');
  const method=element('details','coverage-method');
  const methodHeading=element('summary',null,'Что означают цвета и пустые клетки?');
  const methodBody=element('div','coverage-method-content');
  method.append(methodHeading,methodBody);
  add(main,heading,lead,summary,legend,controls,caption,
      scroll,help,detail,method);
  host.replaceChildren(main);

  const currentCell=()=>model?.cells.find(c=>selection&&
    c.year===selection.year&&c.scope_id===selection.scope_id);
  function restore(){
    const kind=query('kind');
    dim=allowedDims.has(kind)?kind:'all';
    const year=Number(query('year'));
    const area=query('area');
    selection=model?.cells.some(c=>c.year===year&&c.scope_id===area)
      ?{year,scope_id:area}:null;
  }
  function address(push){
    const u=new URL(location.href);
    if(dim==='all')u.searchParams.delete('kind');
    else u.searchParams.set('kind',dim);
    if(selection){
      u.searchParams.set('year',String(selection.year));
      u.searchParams.set('area',selection.scope_id);
    }else{
      u.searchParams.delete('year');u.searchParams.delete('area');
    }
    history[push?'pushState':'replaceState'](null,'',u.pathname+u.search+u.hash);
  }
  function sourceList(ids){
    const box=element('div','coverage-sources');
    for(const id of [...new Set(ids||[])]){
      const ref=model.sources[id];
      if(!ref||!safeUrl(ref.url))continue;
      const link=element('a','coverage-source',ref.title+' ↗');
      link.href=ref.url;link.target='_blank';
      link.rel='noopener noreferrer';
      link.title='Источник '+id+'. Проверка ссылки не означает проверки всех исторических выводов.';
      box.append(link);
    }
    return box;
  }
  function showDetails(){
    detail.replaceChildren();
    const c=currentCell();
    if(!c){
      add(detail,element('h2',null,'Откройте ячейку матрицы'),
        element('p',null,'Нажмите на интересующие регион и год. '+
          'Покажу, какие конкретно свидетельства изучены, и ссылки на источники.'));
      return;
    }
    const area=model.areas.find(a=>a.id===c.scope_id);
    add(detail,element('h2',null,area.label+' · '+c.year),
      element('p','coverage-caveat',area.scope_caveat));
    if(c.status==='not_researched'){
      add(detail,element('p','coverage-empty-note',
        model.methodology.unobserved),
        element('p',null,
          'Поэтому для этого года я не могу назвать проверенную по источникам '+
          'сеть правителей внутри этой темы. Это исследовательский пробел, '+
          'а не историческое утверждение.'));
      return;
    }
    const filtered=c.evidence.filter(e=>dim==='all'||e.dimension===dim);
    add(detail,element('p','coverage-caveat',
      'Статус: частичная источниковая выборка; '+c.edge_count+
      ' документированных отношений, '+c.node_count+' связанных узлов, '+
      c.source_ids.length+' ссылок на источники. '+
      'Фактическая власть и полный территориальный охват не проверены.'),
      element('p',null,c.scope_description),
      element('p','coverage-caveat',c.research_warning));
    const graph=element('a','coverage-open-network','Открыть сеть власти за '+c.year+' год ↗');
    graph.href='./authority.html?year='+c.year+'&region='+encodeURIComponent(c.scope_id);
    detail.append(graph);
    if(!filtered.length){
      detail.append(element('p','coverage-empty-note',
        'Для выбранного типа отношений в этом частичном срезе нет записей. '+
        'Это не доказывает отсутствие такого вида власти в действительности.'));
    }else{
      const label=element('h3','coverage-detail-heading',
        'Сведения выбранного типа: '+filtered.length);
      detail.append(label);
      const items=element('div','coverage-evidence-list');
      for(const event of filtered){
        const article=element('article','coverage-evidence');
        const type=DIMENSIONS.find(x=>x[0]===event.dimension)?.[1]||event.dimension;
        add(article,element('span','coverage-evidence-kind',type),
          element('h4',null,event.label),
          element('p',null,event.explanation),
          element('p','coverage-caveat',event.caveat),
          sourceList(event.source_ids));
        items.append(article);
      }
      detail.append(items);
    }
    const allSources=element('details','coverage-all-sources');
    allSources.append(element('summary',null,
      'Все источники этой исследовательской ячейки ('+c.source_ids.length+')'),
      sourceList(c.source_ids));
    detail.append(allSources);
  }
  function selectCell(cell){
    selection={scope_id:cell.scope_id,year:cell.year};
    address(true);render();
    detail.scrollIntoView({block:'nearest',behavior:'auto'});
  }
  function render(){
    if(!model)return;
    const n=model.summary;
    heading.textContent='Где мы уже исследовали историю?';
    document.title='Покрытие мировой исторической базы — исследовательская матрица';
    summary.textContent=n.partial_samples+' частичных исследовательских срезов · '+
      n.not_researched+' ячеек без исследования · '+
      n.documented_links+' отношений с источниками · '+
      n.year_count+' отдельных года';
    controls.replaceChildren();
    for(const [key,label] of DIMENSIONS){
      const button=element('button','coverage-dim-button',label);
      button.type='button';button.dataset.dimension=key;
      button.setAttribute('aria-pressed',String(dim===key));
      button.addEventListener('click',()=>{
        if(dim===key)return;
        dim=key;address(false);render();
      });
      controls.append(button);
    }
    thead.replaceChildren();tbody.replaceChildren();
    const header=element('tr');
    const leadCell=element('th',null,'Исследовательская тема');
    leadCell.scope='col';header.append(leadCell);
    for(const year of model.years){
      const th=element('th',null,String(year));th.scope='col';header.append(th);
    }
    thead.append(header);
    for(const area of model.areas){
      const tr=element('tr');
      const th=element('th','coverage-scope');
      th.scope='row';
      th.append(element('strong',null,area.label));
      tr.append(th);
      for(const year of model.years){
        const cell=model.cells.find(x=>x.scope_id===area.id&&x.year===year);
        const td=element('td','coverage-cell');
        td.dataset.status=cell.status;
        const button=element('button','coverage-cell-button');
        button.type='button';button.dataset.area=area.id;
        button.dataset.year=String(year);
        button.dataset.status=cell.status;
        const chosen=Boolean(selection&&selection.scope_id===area.id&&
                             selection.year===year);
        button.setAttribute('aria-pressed',String(chosen));
        const count=dim==='all'?cell.edge_count:cell.dimension_counts[dim];
        if(cell.status==='partial_sample'){
          add(button,element('strong',null,count+' '+(count===1?'запись':'записей')),
            element('span',null,count===0?
              'Нет записей этого типа':'Частичный срез'));
        }else{
          add(button,element('strong',null,'—'),
            element('span',null,'Не исследовано'));
        }
        button.setAttribute('aria-label',area.label+', '+year+
          (cell.status==='partial_sample'
            ?', частичная выборка, '+count+' записей выбранного типа'
            :', ещё не исследовано')+', открыть подробности');
        button.addEventListener('click',()=>selectCell(cell));
        td.append(button);tr.append(td);
      }
      tbody.append(tr);
    }
    showDetails();
    methodBody.replaceChildren(
      element('p',null,model.methodology.observed),
      element('p',null,model.methodology.unobserved),
      element('p',null,model.methodology.time),
      element('p',null,model.methodology.regions),
      element('p',null,model.methodology.dimension)
    );
  }
  function accept(payload){
    if(payload.schema_version!=='world-authority-coverage-v1'||
       payload.historical_truth_verified_by_ci!==false||
       payload.worldwide_coverage_verified!==false||
       payload.geographic_boundaries_verified!==false||
       !Array.isArray(payload.years)||payload.years.join(',')!=='1688,1788,1888'||
       !Array.isArray(payload.areas)||!Array.isArray(payload.cells)||
       payload.cells.length!==21||!payload.sources||
       payload.summary.partial_samples!==8||payload.summary.not_researched!==13){
      throw Error('Неподдерживаемая или неполная исследовательская матрица');
    }
    model=payload;restore();render();
  }
  fetch('./world-authority-coverage.json',{cache:'no-cache'})
    .then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json();})
    .then(accept)
    .catch(err=>{
      summary.textContent='Не удалось открыть реестр исследований: '+
        String(err.message||err);
    });
  window.addEventListener('popstate',()=>{
    if(model){restore();render();}
  });
})();