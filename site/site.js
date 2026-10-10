/* Progressive enhancement for the three modes. No external dependencies or requests. */
(() => {
  'use strict';
  const source = document.getElementById('chronology-data');
  if (!source) return;
  let data;
  try { data = JSON.parse(source.textContent); }
  catch (error) { document.getElementById('timeline-status').textContent = 'Данные шкалы недоступны.'; return; }

  const tabNames = new Set(['poster', 'timeline', 'research']);
  const tabs = Array.from(document.querySelectorAll('.mode-tab'));
  const panels = new Map(Array.from(document.querySelectorAll('.mode-panel')).map(panel => [panel.dataset.mode, panel]));
  let currentMode = 'poster';
  function navigate(name, updateHash) {
    if (!tabNames.has(name)) return;
    currentMode = name;
    tabs.forEach(tab => {
      const selected = tab.dataset.view === name;
      tab.setAttribute('aria-selected', String(selected));
      tab.tabIndex = selected ? 0 : -1;
    });
    panels.forEach((panel, id) => { panel.hidden = id !== name; });
    if (name === 'timeline' && !rendered) renderTimeline();
    if (updateHash && location.hash !== '#' + name) history.replaceState(null, '', '#' + name);
    if (updateHash) document.querySelector('.modes-wrap').scrollIntoView({block: 'start'});
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
    all: [Date.UTC(1817, 0, 1), Date.UTC(1991, 11, 26)],
    imperial: [Date.UTC(1817, 0, 1), Date.UTC(1917, 10, 8)],
    transition: [Date.UTC(1894, 0, 1), Date.UTC(1925, 11, 31)],
    early: [Date.UTC(1917, 0, 1), Date.UTC(1953, 11, 31)],
    middle: [Date.UTC(1953, 0, 1), Date.UTC(1982, 11, 31)],
    late: [Date.UTC(1982, 0, 1), Date.UTC(1991, 11, 26)],
  };
  // Three conceptual roles, not three unchanging legal offices:
  // monarchy -> party; ministries -> governments; advisory -> legislative bodies.
  const trackInfo = [
    ['authority', 'Император → партия', 'Монархическая и партийная политическая власть', 'party',
      ['imperial_monarchy', 'party']],
    ['government', 'Правительство', 'От Комитета министров до СНК СССР', 'gov',
      ['imperial_government', 'government']],
    ['state', 'Государственные органы', 'От Государственного совета и Думы до Президиума ВС', 'state',
      ['imperial_institutions', 'state_institutions']],
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
      const labelForEra = currentEra === 'imperial' && key === 'authority'
        ? 'Император'
        : currentEra !== 'all' && currentEra !== 'imperial' && key === 'authority'
          ? 'Партия'
          : label;
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
    if (tabNames.has(hash)) return navigate(hash, false);
    if (hash.startsWith('source-') || /^[IPGSX]\d{2,}$/.test(hash)) {
      navigate('research', false);
      const target = document.getElementById(hash);
      if (target) {
        if (target.tagName === 'DETAILS') target.open = true;
        requestAnimationFrame(() => target.scrollIntoView({block: 'start'}));
      }
      return;
    }
    if (hash.startsWith('poster-')) return navigate('poster', false);
    if (!hash) return navigate('poster', false);
  }
  window.addEventListener('hashchange', fromHash);
  fromHash();
})();
