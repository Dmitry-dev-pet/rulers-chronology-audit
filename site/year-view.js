/* A year-first, source-aware entry screen for the historical atlas.
   This is a UI over atlas.json, not a new historical dataset. */
(() => {
  'use strict';
  const panel = document.getElementById('panel-timeline');
  const inspector = panel && panel.querySelector('.atlas-year-inspector');
  const slider = inspector && inspector.querySelector('#atlas-year-range');
  const originalHead = inspector && inspector.querySelector('.atlas-year-head');
  const yearNumber = document.getElementById('atlas-year-value');
  const toolbar = panel && panel.querySelector('.timeline-toolbar');
  if (!panel || !inspector || !slider || !originalHead || !yearNumber || !toolbar) return;

  const elem = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = String(text);
    return node;
  };
  const dashboard = elem('section', 'atlas-year-dashboard');
  dashboard.id = 'atlas-year-dashboard';
  dashboard.setAttribute('aria-label', 'Кто управлял в выбранном году');
  const heading = elem('div', 'atlas-year-dashboard-heading');
  const title = elem('h2');
  // Desktop keeps its full question; mobile elevates the selected year
  // visually rather than wrapping a long sentence around 4 digits.
  title.append(
    elem('span','atlas-year-question-prefix','Кто управлял в '),
    yearNumber,
    elem('span','atlas-year-question-suffix',' году?'),
    elem('span','atlas-mobile-year-caption','Кто управлял в этом году?'));
  const stepYear = (delta) => {
    const min = Number(slider.min), max = Number(slider.max);
    const next = Math.min(max, Math.max(min, Number(slider.value) + delta));
    if (next === Number(slider.value)) return;
    slider.value = String(next);
    slider.dispatchEvent(new Event('input', {bubbles: true}));
  };
  const prev = elem('button', 'atlas-year-step', '‹');
  prev.type = 'button';
  prev.setAttribute('aria-label', 'Предыдущий год');
  prev.addEventListener('click', () => stepYear(-1));
  const next = elem('button', 'atlas-year-step', '›');
  next.type = 'button';
  next.setAttribute('aria-label', 'Следующий год');
  next.addEventListener('click', () => stepYear(1));
  heading.append(prev, title, next);
  originalHead.replaceChildren(heading);

  const range = elem('div', 'atlas-year-dashboard-range');
  const from = elem('span', null, slider.min);
  const to = elem('span', null, slider.max);
  range.append(from, slider, to);
  // Histography-inspired playback reuses the canonical year slider. Every frame
  // is a source-backed year query, NOT an inferred transfer of actual power.
  const playback = elem('div', 'atlas-year-playback');
  playback.setAttribute('role', 'group');
  playback.setAttribute('aria-label', 'Воспроизведение хронологии');
  const play = elem('button', 'atlas-year-play', '▶ Воспроизвести');
  play.type = 'button';
  play.setAttribute('aria-pressed', 'false');
  const speedLabel = elem('label', 'atlas-year-playback-speed', 'Шаг: ');
  const speed = elem('select', 'atlas-year-playback-step');
  speed.setAttribute('aria-label', 'Шаг между историческими срезами');
  for (const [value, label] of [[1, '1 год'], [5, '5 лет'], [10, '10 лет']]) {
    const option = elem('option', null, label);
    option.value = String(value);
    speed.appendChild(option);
  }
  speed.value = '5';
  speedLabel.appendChild(speed);
  const playbackNote = elem('span', 'atlas-year-playback-note',
    'Срезы по годам — не анимация фактической передачи власти.');
  playback.append(play, speedLabel, playbackNote);
  let playbackTimer = null;
  let playbackFrame = false;
  function stopPlayback() {
    if (playbackTimer !== null) window.clearInterval(playbackTimer);
    playbackTimer = null;
    play.textContent = '▶ Воспроизвести';
    play.setAttribute('aria-pressed', 'false');
  }
  function advancePlayback() {
    if (document.hidden || panel.hidden || Number(slider.value) >= Number(slider.max)) {
      stopPlayback();
      return;
    }
    playbackFrame = true;
    try { stepYear(Number(speed.value)); }
    finally { playbackFrame = false; }
    if (Number(slider.value) >= Number(slider.max)) stopPlayback();
  }
  play.addEventListener('click', () => {
    if (playbackTimer !== null) { stopPlayback(); return; }
    // At the end of a selected era, explicitly restart from that era's start.
    if (Number(slider.value) >= Number(slider.max)) {
      slider.value = slider.min;
      slider.dispatchEvent(new Event('input', {bubbles: true}));
    }
    play.textContent = 'Ⅱ Пауза';
    play.setAttribute('aria-pressed', 'true');
    playbackTimer = window.setInterval(advancePlayback, 850);
  });
  // Any direct navigation or a backgrounded tab cancels playback.
  slider.addEventListener('input', () => { if (!playbackFrame) stopPlayback(); });
  window.addEventListener('hashchange', stopPlayback);
  window.addEventListener('atlas:route', event => {
    if (event.detail?.view !== 'timeline') stopPlayback();
  });
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) stopPlayback();
  });
  const caveat = elem('p', 'atlas-year-dashboard-caveat',
    'Показаны записи, пересекающие год, а не обязательно действовавшие одновременно. ' +
    'Должность не доказывает фактическую власть; историческая проверка продолжается.');
  const status = elem('p', 'atlas-year-dashboard-status', 'Загружаем источниковые сведения…');
  status.setAttribute('role', 'status');
  status.setAttribute('aria-live', 'polite');
  const cards = elem('div', 'atlas-year-dashboard-cards');
  cards.setAttribute('aria-label', 'Роли и центры власти');
  // A compact, source-derived reading guide; never a newly inferred ruler list.
  // On desktop this is hidden and the existing four-column layout is unchanged.
  const highlights = elem('section', 'atlas-mobile-highlights');
  highlights.setAttribute('aria-label', 'Краткий источниковый срез года');
  const worldLink = elem('a', 'atlas-year-world-link', '◈ Мир · 1762: происхождение и династии ↗');
  worldLink.href = '?world=1762#/timeline/1762';
  worldLink.dataset.worldOpen = '1762';
  dashboard.append(originalHead, range, playback, worldLink, caveat, status, highlights, cards);
  panel.insertBefore(dashboard, toolbar);

  // The historical statements remain in the canonical atlas database,
  // rather than in strings that could silently disagree with source records.
  let db = null;
  let people = new Map(), bodies = new Map(), sources = new Map();
  const nominal = new Set([
    'nominal_due_to_illness', 'nominal_grand_prince', 'infant_emperor',
    'leadership_constrained_by_illness'
  ]);
  const regencies = new Set([
    'regent', 'guardian_influence_approx', 'patriarch_political_co_ruler'
  ]);
  const special = new Set([
    'contested_grand_prince', 'tsar_contested_identity',
    'uncrowned_rival_claimant', 'uncrowned_claimant',
    'provisional_reference_only', 'contested_takeover_not_regular_succession'
  ]);

  function validSource(url) {
    try {
      const parsed = new URL(url);
      return parsed.protocol === 'https:' && !parsed.username && !parsed.password &&
        ![[ 'drive', '.google.com' ].join(''), [ 'docs', '.google.com' ].join('')].includes(parsed.hostname);
    } catch (_) { return false; }
  }
  // Each year is a time window, not an exact daily snapshot.
  // Date precision and calendars are preserved and never narrowed.
  const intersects = (record, year) => {
    const start = Number(String(record.start?.value || '').slice(0, 4));
    const end = Number(String(record.end?.value || '').slice(0, 4));
    return Number.isInteger(start) && Number.isInteger(end) &&
      start <= year && year <= end;
  };
  const regency = record =>
    regencies.has(record.status) || /соправител|регент|опекун/i.test(record.description || '');

  function qualifiedName(record) {
    if (record.person_id && people.has(record.person_id))
      return people.get(record.person_id).name;
    if (record.body_id && bodies.has(record.body_id))
      return bodies.get(record.body_id).name;
    return 'Участник не установлен';
  }
  function sourceLinks(parent, record) {
    const unique = [...new Set(record.sources || [])];
    for (const id of unique.slice(0, 2)) {
      const src = sources.get(id);
      if (!src || !validSource(src.url)) continue;
      const a = elem('a', 'atlas-year-source', id);
      a.href = src.url;
      a.title = src.title || id;
      a.rel = 'noopener noreferrer';
      a.target = '_blank';
      parent.appendChild(a);
    }
    if (unique.length > 2) parent.appendChild(elem('span', 'atlas-year-more-sources', '+' + (unique.length - 2)));
  }
  // Accordion state is presentation-only; keep each category's expanded
  // state when the selected year changes, without storing historical data.
  // All four categories start collapsed on a phone: the short, qualified
  // year scan stays visible before the user chooses a detailed source card.
  const expandedMobileGroups = new Set();
  function makeGroup(titleText, description, records, kind) {
    const card = elem('article', 'atlas-year-role-card');
    card.dataset.kind = kind;
    card.classList.toggle('mobile-expanded', expandedMobileGroups.has(kind));
    const header = elem('div', 'atlas-year-role-head');
    const heading = elem('h3', null, titleText);
    const count = elem('span', 'atlas-year-role-count', records.length);
    header.append(heading, count);
    // The existing desktop headings remain unchanged. Touch users receive
    // a real button, an accessible count, and an independent expandable area.
    const mobileToggle = elem('button', 'atlas-mobile-role-toggle');
    mobileToggle.type = 'button';
    const listId = 'atlas-mobile-items-' + kind;
    mobileToggle.setAttribute('aria-controls', listId);
    mobileToggle.setAttribute('aria-expanded', String(expandedMobileGroups.has(kind)));
    mobileToggle.setAttribute('aria-label', titleText + ': ' + records.length + ' записей');
    mobileToggle.append(
      elem('span','atlas-mobile-role-title', titleText),
      elem('span','atlas-mobile-role-count',records.length),
      elem('span','atlas-mobile-role-chevron','⌄'));
    mobileToggle.addEventListener('click', () => {
      const next = !card.classList.contains('mobile-expanded');
      card.classList.toggle('mobile-expanded', next);
      mobileToggle.setAttribute('aria-expanded', String(next));
      if (next) expandedMobileGroups.add(kind);
      else expandedMobileGroups.delete(kind);
    });
    header.append(mobileToggle);
    card.append(header, elem('p', 'atlas-year-role-description', description));
    const list = elem('ul', 'atlas-year-role-items');
    list.id = listId;
    const shown = records.slice(0, 3);
    for (const record of shown) {
      const row = elem('li', 'atlas-year-role-item');
      const name = qualifiedName(record);
      if (record.person_id && people.has(record.person_id)) {
        const a = elem('a', 'atlas-year-person-link', name);
        a.href = '#/people/' + encodeURIComponent(record.person_id);
        row.appendChild(a);
      } else row.appendChild(elem('strong', 'atlas-year-person-link', name));
      row.appendChild(elem('div', 'atlas-year-role-explanation', record.description));
      if (nominal.has(record.status)) {
        row.appendChild(elem('span', 'atlas-year-qualification', 'Номинальный / ограниченный статус'));
      } else if (special.has(record.status)) {
        row.appendChild(elem('span', 'atlas-year-qualification', 'Спорный статус'));
      }
      if (record.verification === 'imported_not_rechecked') {
        row.appendChild(elem('span', 'atlas-year-verification', 'Требует независимой проверки'));
      }
      const citations = elem('div', 'atlas-year-role-sources');
      sourceLinks(citations, record);
      row.appendChild(citations);
      list.appendChild(row);
    }
    if (!records.length) list.appendChild(elem('li', 'atlas-year-role-empty',
      'Отдельных записей пока нет. Это не доказывает отсутствия такой власти.'));
    card.appendChild(list);
    const bottom = elem('div', 'atlas-year-role-bottom');
    if (records.length > shown.length)
      bottom.appendChild(elem('span', 'atlas-year-role-remaining', 'Ещё ' + (records.length - shown.length) + ' записей'));
    const more = elem('button', 'atlas-year-role-details', 'Все записи →');
    more.type = 'button';
    more.addEventListener('click', () =>
      window.dispatchEvent(new CustomEvent('atlas:show-year-details')));
    bottom.appendChild(more);
    card.appendChild(bottom);
    return card;
  }


  // Names come only from the canonical year-overlap records. In particular,
  // a year does not establish who held power on any one date within it.
  function renderHighlights(groups) {
    const rows = [elem('h3', 'atlas-mobile-highlights-title', 'Краткий срез года')];
    const labels = {
      formal:'Должности', effective:'Оценки влияния',
      regency:'Регентство', institutions:'Учреждения'
    };
    for (const [title, , records, kind] of groups) {
      // Show regents first instead of hiding them behind formal co-rulers.
      const regentRecords = kind === 'regency'
        ? records.filter(record => regencies.has(record.status)) : [];
      const entries = regentRecords.length ? regentRecords : records;
      if (!entries.length) continue;
      const names = [...new Set(entries.map(qualifiedName))];
      const button = elem('button', 'atlas-mobile-highlight');
      button.type = 'button';
      button.dataset.kind = kind;
      button.setAttribute('aria-controls', 'atlas-mobile-items-' + kind);
      button.setAttribute('aria-label', 'Раскрыть источниковые записи: ' + title);
      button.append(
        elem('span', 'atlas-mobile-highlight-kind', labels[kind]),
        elem('span', 'atlas-mobile-highlight-names',
          names.slice(0, 2).join(' · ') +
          (names.length > 2 ? ' · +' + (names.length - 2) : '')),
        elem('span', 'atlas-mobile-highlight-arrow', '›'));
      button.addEventListener('click', () => {
        const card = cards.querySelector('.atlas-year-role-card[data-kind="' + kind + '"]');
        const toggle = card?.querySelector('.atlas-mobile-role-toggle');
        if (toggle && !card.classList.contains('mobile-expanded')) toggle.click();
        if (card && document.documentElement.classList.contains('atlas-mobile'))
          card.scrollIntoView({block:'nearest'});
      });
      rows.push(button);
    }
    if (rows.length === 1) rows.push(elem('p', 'atlas-mobile-highlights-empty',
      'Подтверждённых отдельных записей на этот год в реестре пока нет.'));
    rows.push(elem('p', 'atlas-mobile-highlights-note',
      'Это пересечения внутри года, не одновременный состав власти. Нажмите строку, чтобы увидеть сведения и источники.'));
    highlights.replaceChildren(...rows);
  }

  function render() {
    const year = Number(slider.value);
    prev.disabled = year <= Number(slider.min);
    next.disabled = year >= Number(slider.max);
    from.textContent = slider.min;
    to.textContent = slider.max;
    // Existing inspector owns the date number and hash-route state.
    if (!db) return;
    const tenures = db.tenures.filter(r => intersects(r, year));
    const powers = db.power_assessments.filter(r => intersects(r, year));
    const institutions = (db.institution_periods || []).filter(r => intersects(r, year));
    const formal = tenures.filter(r => r.status !== 'regent');
    const effective = powers.filter(r => !nominal.has(r.status));
    const coRulers = [
      ...tenures.filter(regency),
      ...powers.filter(r => regencies.has(r.status) &&
        !tenures.some(t => t.person_id && t.person_id === r.person_id &&
          t.status === r.status && intersects(t, year)))
    ];
    // A body can exercise collective power without being a person.
    const collective = [
      ...institutions,
      ...powers.filter(r => r.body_id && !institutions.some(x =>
        x.body_id === r.body_id && x.description === r.description))
    ];
    const groups = [
      ['Формальные должности', 'Титулы, должности и юридические полномочия', formal, 'formal'],
      ['Политическое влияние', 'Только отдельные источниковые оценки, не вывод из титула', effective, 'effective'],
      ['Регентство и соправители', 'Параллельные и опекунские формы власти', coRulers, 'regency'],
      ['Учреждения и коллегии', 'Органы управления без выдуманных личных правителей', collective, 'institutions']
    ];
    cards.replaceChildren(...groups.map(([name, about, records, kind]) =>
      makeGroup(name, about, records, kind)));
    renderHighlights(groups);
    window.dispatchEvent(new CustomEvent('atlas:year-cards-ready',
      {detail:{year,groups:groups.map(([title,,records,kind])=>
        ({title,count:records.length,kind}))}}));
    status.textContent = 'Исторический срез: ' + year + ' · ' +
      'оценки власти и юридические должности показаны отдельно.';
  }

  slider.addEventListener('input', render);
  window.addEventListener('hashchange', () => queueMicrotask(render));
  toolbar.querySelectorAll('.era-btn').forEach(button =>
    button.addEventListener('click', () => queueMicrotask(render)));

  fetch('./atlas.json', {cache: 'no-cache'}).then(response => {
    if (!response.ok) throw new Error('HTTP ' + response.status);
    return response.json();
  }).then(result => {
    if (!Array.isArray(result.people) || !Array.isArray(result.bodies) ||
        !Array.isArray(result.sources) || !Array.isArray(result.tenures) ||
        !Array.isArray(result.power_assessments) ||
        !Array.isArray(result.institution_periods)) throw new Error('Неполная база атласа');
    db = result;
    people = new Map(db.people.map(p => [p.id, p]));
    bodies = new Map(db.bodies.map(b => [b.id, b]));
    sources = new Map(db.sources.map(s => [s.id, s]));
    render();
  }).catch(error => {
    status.textContent = 'Не удалось загрузить источниковые записи: ' + error.message;
    cards.replaceChildren(elem('p', 'atlas-year-role-empty',
      'Основная хронология доступна; попробуйте обновить страницу.'));
  });
})();
