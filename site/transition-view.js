/* Source-qualified dossiers for complex, overlapping transitions of power.
   No conclusions are deduced from a title or rendered without canonical links. */
(() => {
  'use strict';
  const panel = document.getElementById('panel-timeline');
  const dashboard = document.getElementById('atlas-year-dashboard');
  const slider = document.getElementById('atlas-year-range');
  const workspace = panel && panel.querySelector('.atlas-timeline-workspace');
  if (!panel || !dashboard || !slider || !workspace) return;

  const make = (tag, name, value) => {
    const el = document.createElement(tag);
    if (name) el.className = name;
    if (value !== undefined) el.textContent = String(value);
    return el;
  };
  const controls = make('div', 'atlas-transition-controls');
  const heading = make('span', 'atlas-transition-label', 'Переломы власти');
  const picks = make('div', 'atlas-transition-picks');
  const teaser = make('span', 'atlas-transition-teaser',
    'Сравните законную власть, фактическое управление и спорные притязания.');
  controls.append(heading, picks, teaser);
  dashboard.appendChild(controls);

  const sheet = make('aside', 'atlas-transition-sheet');
  sheet.id = 'atlas-transition-sheet';
  sheet.hidden = true;
  sheet.setAttribute('role', 'dialog');
  sheet.setAttribute('aria-modal', 'false');
  sheet.setAttribute('aria-labelledby', 'atlas-transition-sheet-title');
  const header = make('div', 'atlas-transition-sheet-head');
  const textArea = make('div', 'atlas-transition-sheet-title-area');
  const kicker = make('span', 'atlas-transition-sheet-kicker', 'Источниковое досье');
  const title = make('h3', null, 'Переход власти');
  title.id = 'atlas-transition-sheet-title';
  const close = make('button', 'atlas-transition-close', 'Закрыть ×');
  close.type = 'button';
  close.setAttribute('aria-label', 'Закрыть историческое досье');
  textArea.append(kicker, title);
  header.append(textArea, close);
  const intro = make('p', 'atlas-transition-sheet-intro');
  const caution = make('p', 'atlas-transition-sheet-caution');
  const tabs = make('div', 'atlas-transition-filters');
  tabs.setAttribute('role', 'group');
  tabs.setAttribute('aria-label', 'Тип исторических утверждений');
  const body = make('div', 'atlas-transition-entries');
  const count = make('p', 'atlas-transition-result-count');
  count.setAttribute('role', 'status');
  const sectionPicker = make('div', 'atlas-transition-sections');
  sectionPicker.setAttribute('role', 'group');
  sectionPicker.setAttribute('aria-label', 'Вид исторического досье');
  sheet.append(header, intro, caution, sectionPicker, tabs, count, body);
  workspace.appendChild(sheet);

  const categories = [
    ['all', 'Все события'],
    ['legal', 'Юридическая власть'],
    ['practical', 'Фактическая'],
    ['claim', 'Претензии'],
    ['institutional', 'Органы и решения'],
  ];
  const geoCategories = [
    ['all', 'Все местности'],
    ['practice', 'Местное управление'],
    ['military', 'Военное присутствие'],
    ['claim', 'Притязания'],
    ['law', 'Правовой статус'],
  ];
  let cases = [];
  let sourceIndex = new Map();
  let selected = null;
  let activeFilter = 'all';
  let viewMode = 'events';
  let currentTrigger = null;
  let buttonByCase = new Map();
  const isSafe = value => {
    try {
      const url = new URL(value);
      return url.protocol === 'https:' && !url.username && !url.password &&
        ![['drive', '.google.com'].join(''), ['docs', '.google.com'].join('')].includes(url.hostname);
    } catch (_) { return false; }
  };
  const currentYear = () => Number(slider.value);
  const caseAt = year => cases.find(c => c.start_year <= year && year <= c.end_year);
  function hrefs(parent, record) {
    const seen = new Set();
    for (const id of record.sources || []) {
      if (seen.has(id)) continue;
      seen.add(id);
      const source = sourceIndex.get(id);
      if (!source || !isSafe(source.url)) continue;
      const link = make('a', 'atlas-transition-source', id);
      link.title = source.title || id;
      link.href = source.url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      parent.appendChild(link);
    }
  }
  function dateLabel(item) {
    const date = item.date;
    const suffix = date.calendar === 'julian' ? ' · ст. ст.' :
      date.calendar === 'gregorian' ? ' · н. ст.' :
      ' · календарь не уточнён';
    return date.value + suffix;
  }
  function displayEntries() {
    if (!selected) return;
    if (viewMode === 'geography') {
      displayGeography();
      return;
    }
    const visible = selected.records.filter(r => activeFilter === 'all' || r.category === activeFilter);
    const year = currentYear();
    body.replaceChildren();
    const labels = new Map(categories);
    for (const item of visible) {
      const event = make('article', 'atlas-transition-entry' +
        (Number(item.date.value.slice(0, 4)) === year ? ' is-year' : ''));
      event.dataset.category = item.category;
      const row = make('div', 'atlas-transition-entry-meta');
      row.append(make('span', 'atlas-transition-entry-date', dateLabel(item)),
        make('span', 'atlas-transition-kind', labels.get(item.category)));
      if (Number(item.date.value.slice(0, 4)) === year)
        row.appendChild(make('span', 'atlas-transition-year-mark', 'Выбранный год'));
      event.appendChild(row);
      event.appendChild(make('h4', null, item.title));
      const actor = make('div', 'atlas-transition-actor');
      if (item.person_id) {
        const link = make('a', null, item.actor);
        link.href = '#/people/' + encodeURIComponent(item.person_id);
        actor.appendChild(link);
      } else actor.textContent = item.actor;
      event.append(actor,
        make('p', 'atlas-transition-summary', item.summary),
        make('p', 'atlas-transition-note', item.caveat));
      const refs = make('div', 'atlas-transition-sources');
      refs.append(make('span', null, 'Источники: '));
      hrefs(refs, item);
      event.appendChild(refs);
      body.appendChild(event);
    }
    count.textContent = 'Показано ' + visible.length + ' записей · ' +
      'события разных дат не означают одновременную власть.';
  }

  function displayGeography() {
    if (!selected) return;
    const observations = selected.territorial_evidence || [];
    const visible = observations.filter(r => activeFilter === 'all' || r.nature === activeFilter);
    const year = currentYear();
    const labels = new Map(geoCategories);
    body.replaceChildren();
    const disclaimer = make('p', 'atlas-geo-disclaimer',
      selected.geography_policy + ' Это свидетельства о местах и юридических притязаниях, не достоверная карта границ.');
    body.appendChild(disclaimer);
    for (const record of visible) {
      const card = make('article', 'atlas-transition-entry atlas-geo-entry' +
        (Number(record.date.value.slice(0, 4)) === year ? ' is-year' : ''));
      card.dataset.category = record.nature;
      const head = make('div', 'atlas-transition-entry-meta');
      head.append(make('span', 'atlas-transition-entry-date', dateLabel(record)),
        make('span', 'atlas-transition-kind', labels.get(record.nature)));
      if (Number(record.date.value.slice(0,4)) === year)
        head.appendChild(make('span', 'atlas-transition-year-mark', 'Выбранный год'));
      card.appendChild(head);
      card.appendChild(make('h4', null, record.place));
      card.appendChild(make('div', 'atlas-transition-actor', record.authority));
      card.appendChild(make('p', 'atlas-transition-summary', record.statement));
      const limit = make('p', 'atlas-transition-note', 'Не доказывает: ' + record.limitation);
      card.appendChild(limit);
      const refs = make('div', 'atlas-transition-sources');
      refs.append(make('span', null, 'Источники: '));
      hrefs(refs, record);
      card.appendChild(refs);
      body.appendChild(card);
    }
    count.textContent = 'Географические свидетельства: ' + visible.length +
      ' · точные границы не реконструированы.';
  }
  function renderSections() {
    sectionPicker.replaceChildren();
    for (const [mode, caption] of [
      ['events', 'События · ' + (selected?.records?.length || 0)],
      ['geography', 'География власти · ' + (selected?.territorial_evidence?.length || 0)]
    ]) {
      const button = make('button', 'atlas-transition-section', caption);
      button.type = 'button';
      button.setAttribute('aria-pressed', String(viewMode === mode));
      button.addEventListener('click', () => {
        viewMode = mode;
        activeFilter = 'all';
        renderSections();
        renderFilters();
        displayEntries();
        body.scrollTop = 0;
      });
      sectionPicker.appendChild(button);
    }
  }
  function renderFilters() {
    tabs.replaceChildren();
    const groups = viewMode === 'geography' ? geoCategories : categories;
    tabs.setAttribute('aria-label', viewMode === 'geography' ?
      'Тип территориального свидетельства' : 'Тип исторических утверждений');
    for (const [kind, caption] of groups) {
      const button = make('button', 'atlas-transition-filter', caption);
      button.type = 'button';
      button.setAttribute('aria-pressed', String(activeFilter === kind));
      button.addEventListener('click', () => {
        activeFilter = kind;
        renderFilters();
        displayEntries();
      });
      tabs.appendChild(button);
    }
  }
  function openCase(c, trigger) {
    selected = c;
    activeFilter = 'all';
    viewMode = 'events';
    currentTrigger = trigger || null;
    sheet.hidden = false;
    title.textContent = c.title;
    intro.textContent = c.lead;
    caution.textContent = c.caveat;
    renderSections();
    renderFilters();
    displayEntries();
    body.scrollTop = 0;
    sheet.scrollTop = 0;
    close.focus({preventScroll: true});
    updateJumps();
  }
  function closeCase(restoreFocus = true) {
    const trigger = currentTrigger;
    selected = null;
    sheet.hidden = true;
    currentTrigger = null;
    updateJumps();
    if (restoreFocus && trigger && trigger.isConnected) trigger.focus({preventScroll: true});
  }
  close.addEventListener('click', () => closeCase());
  sheet.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      event.preventDefault();
      event.stopPropagation();
      closeCase();
    }
  });
  window.addEventListener('atlas:route', event => {
    if (event.detail.view !== 'timeline' && selected) closeCase(false);
  });

  function jump(c, trigger) {
    const all = panel.querySelector('.era-btn[data-era="all"]');
    if (all && all.getAttribute('aria-pressed') !== 'true') all.click();
    // The existing era handler synchronizes the min/max before this callback.
    queueMicrotask(() => {
      slider.value = String(c.focus_year);
      slider.dispatchEvent(new Event('input', {bubbles: true}));
      openCase(c, trigger);
    });
  }
  function updateJumps() {
    const year = currentYear();
    const active = caseAt(year);
    teaser.textContent = active ?
      'Для ' + year + ' г. есть досье: ' + active.title + '.' :
      'Отдельные разборы 1598–1613 и 1991 годов.';
    for (const c of cases) {
      const b = buttonByCase.get(c.id);
      if (b) b.setAttribute('aria-pressed', String(
        !!active && c.id === active.id || !!selected && c.id === selected.id));
    }
  }
  const preview = make('button', 'atlas-transition-preview');
  preview.type = 'button';
  preview.hidden = true;
  preview.setAttribute('aria-controls', sheet.id);
  preview.addEventListener('click', () => {
    const c = caseAt(currentYear());
    if (c) openCase(c, preview);
  });
  controls.appendChild(preview);
  function syncYear() {
    updateJumps();
    const c = caseAt(currentYear());
    preview.hidden = !c;
    if (c) {
      const matching = c.records.filter(r => Number(r.date.value.slice(0, 4)) === currentYear());
      preview.textContent = 'События ' + currentYear() + ' года: ' + matching.length +
        ' · Читать источниковое досье →';
    }
    if (selected) displayEntries();
  }
  slider.addEventListener('input', syncYear);
  window.addEventListener('hashchange', () => queueMicrotask(syncYear));
  panel.querySelectorAll('.era-btn').forEach(b =>
    b.addEventListener('click', () => queueMicrotask(syncYear)));

  fetch('./transition-cases.json', {cache: 'no-cache'}).then(response => {
    if (!response.ok) throw new Error('HTTP ' + response.status);
    return response.json();
  }).then(data => {
    if (!Array.isArray(data.cases) || !Array.isArray(data.sources) ||
        data.historical_truth_verified_by_ci !== false) throw new Error('Неполные исторические данные');
    cases = data.cases;
    sourceIndex = new Map(data.sources.map(s => [s.id, s]));
    for (const c of cases) {
      const btn = make('button', 'atlas-transition-jump',
        c.id === 'ussr-1991' ? '1991 · СССР' : '1598–1613 · Смута');
      btn.type = 'button';
      btn.setAttribute('aria-pressed', 'false');
      btn.setAttribute('aria-controls', sheet.id);
      btn.addEventListener('click', () => jump(c, btn));
      picks.appendChild(btn);
      buttonByCase.set(c.id, btn);
    }
    syncYear();
  }).catch(error => {
    teaser.textContent = 'Переходы власти: источниковое досье пока недоступно (' +
      error.message + '). Основной атлас продолжает работать.';
  });
})();
