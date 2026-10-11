#!/usr/bin/env python3
"""Offline structural audit and report build. Does NOT verify historical truth."""
from __future__ import annotations

import argparse
import calendar
import csv
import hashlib
import html
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

TRACKS = {
    "party": "Партия",
    "government": "Правительство",
    "state_institutions": "Государственные органы",
    "separate_records": "Отдельные и спорные эпизоды",
}
DISCLAIMER = (
    "Автоматическая проверка структуры, а не исторической достоверности. "
    "Спорные датировки и непроверенные первичные акты сохраняются как оговорки."
)
TRANSCRIPT_BLOB = "0821715312c04f2c51d8b260e0319fb6e9c401ad"
SOURCE_PATH = "research/soviet-parallel-sources.md"
DATA_PATH = "data/soviet-parallel-chronology.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def no_duplicate_keys(pairs: list[tuple]) -> dict:
    obj = {}
    for key, value in pairs:
        require(key not in obj, f"Duplicate JSON key: {key}")
        obj[key] = value
    return obj


def date_bounds(value: str) -> tuple[date, date]:
    """Bounds express stated precision; they do not invent exact appointment dates."""
    require(isinstance(value, str) and bool(re.fullmatch(r"\d{4}(-\d{2}){0,2}", value)),
            f"Invalid date format: {value!r}")
    parts = list(map(int, value.split("-")))
    y = parts[0]
    if len(parts) == 1:
        return date(y, 1, 1), date(y, 12, 31)
    m = parts[1]
    if len(parts) == 2:
        return date(y, m, 1), date(y, m, calendar.monthrange(y, m)[1])
    day = date(y, m, parts[2])
    return day, day


def source_index(text: str) -> dict:
    pattern = r"^\|\s*(PC\d+)\s*\|\s*\[([^\]]+)\]\((https?://.+?)\)\s*\|([^\n]*)"
    found = {}
    for ident, title, url, note in re.findall(pattern, text, re.M):
        require(ident not in found, f"Duplicate source: {ident}")
        p = urlsplit(url)
        require(p.scheme == "https" and bool(p.hostname) and not p.username and not p.password,
                f"Unsafe source URL: {ident}")
        require(p.hostname not in {"drive.google.com", "docs.google.com"},
                f"Private-source locator must not enter report: {ident}")
        found[ident] = {"id": ident, "title": title, "url": url, "note": note.rstrip(" |")}
    declared = re.findall(r"^\|\s*(PC\d+)\s*\|", text, re.M)
    require(bool(found) and len(declared) == len(found), "Malformed/duplicate source table row")
    return found


def validate(data: dict, sources: dict) -> dict:
    require(isinstance(data, dict) and data.get("schema_version") == 1, "Unsupported schema")
    require(isinstance(data.get("primary_acts_for_every_appointment_verified"), bool),
            "Missing primary-act verification flag")
    for field in ("title", "scope", "method", "calendar"):
        require(isinstance(data.get(field), str) and bool(data[field].strip()), f"Missing {field}")
    date.fromisoformat(data["as_of"])
    require(data.get("source_index") == SOURCE_PATH, "Unexpected source index path")
    known_ids = set()
    counts = {}
    statuses = {}
    for track in TRACKS:
        rows = data.get(track)
        require(isinstance(rows, list) and len(rows) > 0, f"Missing track: {track}")
        counts[track] = len(rows)
        for row in rows:
            require(isinstance(row, dict), f"Not an object in {track}")
            ident = row.get("id")
            require(isinstance(ident, str) and bool(re.fullmatch(r"[PGSX]\d{2,}", ident)),
                    f"Invalid record ID in {track}")
            require(ident not in known_ids, f"Duplicate record: {ident}")
            known_ids.add(ident)
            for field in ("role", "status"):
                require(isinstance(row.get(field), str) and bool(row[field].strip()),
                        f"Missing {field}: {ident}")
            statuses[row["status"]] = statuses.get(row["status"], 0) + 1
            begin, _ = date_bounds(row.get("from"))
            _, end = date_bounds(row.get("to"))
            require(begin <= end, f"Reversed interval: {ident}")
            refs = row.get("sources")
            require(isinstance(refs, list) and len(refs) > 0, f"Missing sources: {ident}")
            require(all(isinstance(ref, str) and ref in sources for ref in refs),
                    f"Unknown source: {ident}")
            require(len(refs) == len(set(refs)), f"Duplicate source reference: {ident}")
            person = row.get("person")
            require(person is None or isinstance(person, str), f"Invalid person: {ident}")
            for field in ("persons", "initial_cochairs"):
                if field in row:
                    require(isinstance(row[field], list) and len(row[field]) > 0
                            and all(isinstance(x, str) and x.strip() for x in row[field]),
                            f"Invalid {field}: {ident}")
    pending = data.get("open_verification_items")
    require(isinstance(pending, list) and all(isinstance(x, str) and x.strip() for x in pending),
            "Invalid open verification items")
    examples = data.get("synchronized_examples")
    require(isinstance(examples, list), "Missing synchronized examples")
    for row in examples:
        date.fromisoformat(row["date"])
        require(all(isinstance(row.get(k), str) and row[k].strip()
                    for k in ("party", "government", "state")), "Malformed synchronized example")
    return {"structural_validation": "passed", "historical_truth_verified_by_ci": False,
            "records": sum(counts.values()), "tracks": counts, "sources": len(sources),
            "statuses": statuses, "open_items": len(pending), "disclaimer": DISCLAIMER}


def validate_transcription(path: Path) -> None:
    raw = path.read_bytes()
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    require(blob == TRANSCRIPT_BLOB, "Original transcription changed; review provenance separately")
    rows = list(csv.DictReader(raw.decode("utf-8").splitlines(), delimiter="\t"))
    require([x["row_id"] for x in rows] == [f"{n:03}" for n in range(1, 107)],
            "Original transcription must contain rows 001..106")


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def person_label(row: dict) -> str:
    return row.get("person") or "; ".join(row.get("persons") or row.get("initial_cochairs") or []) or "Коллегиальный орган / событие"



STATUS_LABELS = {
    "political_leadership": "Политическое лидерство",
    "formal_office": "Должность",
    "formal_office_and_political_leadership": "Должность и лидерство",
    "collective_transition": "Коллективное руководство",
    "nominal_due_to_illness": "Номинальный срок",
    "collective_acting_functions": "Коллективное исполнение обязанностей",
    "formal_office_with_reorganization": "Реорганизация органов",
    "formal_office_with_transition": "Переходный период",
    "transitional_bodies_not_same_premiership": "Переходные органы",
    "chair_of_collective_body": "Председатель коллегии",
    "acting": "Исполняющий обязанности",
    "collective_body": "Коллегиальный орган",
    "highest_state_official": "Высшее должностное лицо",
    "president": "Президент",
    "provisional_reference_only": "Нужна независимая проверка",
    "contested_takeover_not_regular_succession": "Оспариваемые полномочия",
    "institutional_event": "Событие",
}


def poster_data(transcription_path: Path, review_path: Path) -> list[dict]:
    """Join the unchanged literal poster with independently reviewed annotations."""
    with transcription_path.open(encoding="utf-8", newline="") as f:
        original = {row["row_id"]: row for row in csv.DictReader(f, delimiter="\t")}
    with review_path.open(encoding="utf-8-sig", newline="") as f:
        reviews = list(csv.DictReader(f))
    require([r["row_id"] for r in reviews] == [f"{x:03d}" for x in range(97, 107)],
            "Soviet poster review must contain rows 097..106 exactly once, in source order")
    output = []
    for review in reviews:
        ident = review["row_id"]
        require(ident in original, f"Missing original poster row {ident}")
        orig = original[ident]
        require(orig["poster_side"] == "R", f"Unexpected side for {ident}")
        require(orig["reign_as_printed"] == review["printed_reign"] and
                orig["lifespan_as_printed"] == review["printed_life"],
                f"Review does not match literal photograph for row {ident}")
        for field in ("category", "verified_role_dates", "corrected_life", "assessment", "source_ids"):
            require(review.get(field) is not None and review[field].strip(),
                    f"Missing Soviet poster review {field} in row {ident}")
        output.append({**orig, **review})
    return output


def render(data: dict, sources: dict, result: dict, revision: str,
           poster_rows: list[dict] | None = None) -> str:
    """Render dense archival table, aligned timeline mount and accessible research index."""
    poster_rows = poster_rows or []
    source_page = "https://github.com/Dmitry-dev-pet/rulers-chronology-audit/blob/main/research/soviet-period-sources.md"
    counts = sum(result.get("tracks", {}).values())
    head = [
        "<!doctype html>",
        "<html lang='ru'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        "<meta name='theme-color' content='#f7f5ee'>",
        "<meta name='description' content='Советский период, 1917–1991: исходная хронология, параллельные линии власти и источники.'>",
        "<title>Правители государства · Советский период 1917–1991</title>",
        f"<link rel='stylesheet' href='./site.css?v={revision[:12]}'>",
        "</head><body><div class='topline'></div>",
        "<header>",
        "<nav class='container topnav' aria-label='Главная навигация'>",
        "<span class='brand'>АРХИВ <span>/</span> ХРОНОЛОГИЯ</span>",
        "<div class='topnav-links'>",
        "<a href='https://github.com/Dmitry-dev-pet/rulers-chronology-audit' target='_blank' rel='noopener noreferrer' class='github-arrow'>GitHub проекта</a>",
        "<a href='#research'>Источники</a></div></nav>",
        "<div class='container hero'><div>",
        "<div class='eyebrow'>Исторический атлас / выпуск 01 / 1917–1991</div>",
        "<h1>Правители<br><em>советского периода</em></h1>",
        "<p class='lead'>От исходной печатной таблицы — к проверяемой хронологии. "
        "Сохраняем последовательность имён, но различаем политическое влияние, "
        "правительство и государственные должности.</p>",
        "<div class='hero-quicklinks' aria-label='Интерактивные разделы атласа'>"
        "<a class='hero-quicklink primary' href='#/people'>Биографии и поиск →</a>"
        "<a class='hero-quicklink' href='#/timeline/1685'>Исследовать год на шкале →</a></div>",
        f"<div class='facts'><span><b>{len(poster_rows)}</b> строк плаката</span>",
        f"<span><b>{counts}</b> записей о должностях и событиях</span>",
        f"<span><b>{len(sources)}</b> ссылок на источники</span></div>",
        "</div><div class='hero-aside' aria-label='Период исследования'>",
        "<strong>1917—1991</strong><p>Советская Россия с 1917 года. СССР образован в 1922 году. "
        "Даты разных должностей могут пересекаться.</p></div></div></header>",
        "<div class='modes-wrap'><div class='container modes' role='tablist' aria-label='Режим представления'>",
        "<button id='tab-poster' type='button' role='tab' class='mode-tab' data-view='poster' aria-selected='true' aria-controls='panel-poster' tabindex='0'><span class='num'>01</span> Плакат</button>",
        "<button id='tab-timeline' type='button' role='tab' class='mode-tab' data-view='timeline' aria-selected='false' aria-controls='panel-timeline' tabindex='-1'><span class='num'>02</span> Линии власти</button>",
        "<button id='tab-research' type='button' role='tab' class='mode-tab' data-view='research' aria-selected='false' aria-controls='panel-research' tabindex='-1'><span class='num'>03</span> Исследование</button>",
        "</div></div><main class='container'>",
        "<section id='panel-poster' class='mode-panel' data-mode='poster' role='tabpanel' aria-labelledby='tab-poster'>",
        "<div class='section-top'><div><div class='kicker'>Режим 01 / как в оригинале</div>",
        "<h2>Единая таблица правителей</h2>",
        "<p>Исходные годы, имена и годы жизни воспроизведены буквально. "
        "Пояснения не заменяют напечатанный текст, а помогают видеть ошибки и спорные границы.</p>",
        "</div><div class='right-note'>Одно поколение за другим. Компактная сетка по образцу старого плаката.</div></div>",
        "<p class='scroll-hint' hidden>Проведите таблицу влево, чтобы увидеть годы жизни и сверку →</p>",
        "<div class='paper-table table-scroll' role='region' aria-label='Исходная таблица советского периода' tabindex='0'>",
        "<table><colgroup><col style='width:19%'><col style='width:30%'><col style='width:18%'><col style='width:33%'></colgroup>",
        "<thead><tr><th scope='col'>Годы на плакате</th><th scope='col'>Правитель</th>",
        "<th scope='col'>Годы жизни</th><th scope='col'>Историческая сверка</th></tr></thead><tbody>",
    ]
    for row in poster_rows:
        ident = row["row_id"]
        if ident == '097':
            head.append("<tr class='chapter-row'><th colspan='4' scope='colgroup'>1917 · Переходная власть (до советского правительства)</th></tr>")
        if ident == '099':
            head.append("<tr class='chapter-row'><th colspan='4' scope='colgroup'>С ноября 1917 · Советская Россия → СССР с декабря 1922</th></tr>")
        if ident in {'097', '098'}:
            badge, status, css = "До СССР", "context", "row-context"
        elif ident in {'099', '100', '101', '106'}:
            badge, status, css = "Уточнить", "issue", "row-important"
        else:
            badge, status, css = "По годам", "neutral", ""
        person = row["person_as_printed"]
        if row.get("printed_qualifier"):
            person += f" ({row['printed_qualifier']})"
        head.append(
            f"<tr id='poster-{esc(ident)}' class='{css}'>"
            f"<td class='period'>{esc(row['reign_as_printed'])}</td>"
            f"<td><span class='person'>{esc(person)}</span><span class='name-meta'>Строка №{esc(ident)}</span></td>"
            f"<td class='lifetime'>{esc(row['lifespan_as_printed'])}</td>"
            f"<td class='notes-cell'><span class='tag {status}'>{badge}</span>"
            f"<span>{esc(row['assessment'])}</span> "
            f"<div><button type='button' class='detail-trigger' aria-expanded='false' "
            f"aria-controls='poster-detail-{esc(ident)}'>Пояснение ↓</button></div></td></tr>")
        refs = [r for r in row['source_ids'].split(';') if r]
        ref_html = " ".join(
            f"<a href='{source_page}' target='_blank' rel='noopener noreferrer'>{esc(ref)}</a>"
            for ref in refs)
        head.append(
            f"<tr id='poster-detail-{esc(ident)}' class='detail-row' hidden>"
            f"<td colspan='4'><p><strong>Сверка должности:</strong> {esc(row['verified_role_dates'])}</p>"
            f"<p><strong>Уточнённые годы жизни:</strong> {esc(row['corrected_life'])}. "
            f"<strong>Опорные источники:</strong> {ref_html}</p></td></tr>")
    head.extend([
        "</tbody></table></div>",
        "<div class='table-footer'><div class='legend'>"
        "<span><i class='square'></i> Нужна поправка</span>"
        "<span><i class='square context'></i> Смена режима</span>"
        "<span><i class='square neutral'></i> Совпадают годы</span></div>"
        "<span>Строки воспроизведены, а не отредактированы задним числом.</span></div>",
        "<div class='editor-note'><p><strong>Что важно понимать:</strong> "
        "слово «правитель» в исходном плакате не обозначает одну и ту же юридическую должность. "
        "Период партийного влияния не обязан совпадать со сроком председателя Совнаркома "
        "или главы государства.</p><p>Посмотреть реальные пересечения можно во вкладке "
        "<a href='#timeline'>«Линии власти»</a>.</p></div></section>",
        "<section id='panel-timeline' class='mode-panel' data-mode='timeline' role='tabpanel' aria-labelledby='tab-timeline' hidden>",
        "<div class='section-top'><div><div class='kicker'>Режим 02 / общий календарь</div>",
        "<h2>Три линии на одной оси времени</h2><p>Одинаковое положение по горизонтали означает "
        "один и тот же год. Пересекающиеся полномочия располагаются отдельными полосами, "
        "а не выстраиваются в ложную очередь.</p></div></div>",
        "<div class='timeline-toolbar'><div class='era-switch' role='group' aria-label='Масштаб временной шкалы'>",
        "<button class='era-btn' type='button' data-era='all' aria-pressed='true'>1917–1991</button>",
        "<button class='era-btn' type='button' data-era='early' aria-pressed='false'>1917–1953</button>",
        "<button class='era-btn' type='button' data-era='middle' aria-pressed='false'>1953–1982</button>",
        "<button class='era-btn' type='button' data-era='late' aria-pressed='false'>1982–1991</button>",
        "</div><div class='timeline-key' aria-hidden='true'><span><i></i> Партия</span>"
        "<span><i class='gov'></i> Правительство</span><span><i class='state'></i> Государство</span></div></div>",
        "<div class='timeline-box'><div class='timeline-scroll' role='region' aria-label='Прокручиваемая хронология трёх типов власти' tabindex='0'>",
        "<div class='time-canvas'><div class='time-axis'><div>Дорожка / годы</div><div id='time-ruler' class='time-ruler'></div></div>",
        "<div id='time-canvas'></div></div></div>",
        "<div class='timeline-selection' id='timeline-selection' aria-live='polite'>Выберите интервал на шкале, чтобы открыть объяснение.</div></div>",
        "<p class='timeline-footnote' id='timeline-status' aria-live='polite'>Показаны параллельные должности.</p>",
        "<p class='timeline-footnote'>Годы, месяцы и дни сохраняют исходную точность: если в источнике "
        "известен только год, границы полосы показаны приблизительно. "
        "На узком экране прокручивайте шкалу вбок. Краткие назначения обозначены точками.</p></section>",
        "<section id='panel-research' class='mode-panel' data-mode='research' role='tabpanel' aria-labelledby='tab-research' hidden>",
        "<div class='section-top'><div><div class='kicker'>Режим 03 / доказательства</div>",
        "<h2>Должности, контекст, источники</h2>"
        "<p>Раскрывайте записи для деталей и переходите от каждой записи к библиографии. "
        "Уровень уверенности не повышается автоматически после успешной сборки сайта.</p></div></div>",
        "<div class='research-intro'>",
        "<article><span class='index'>01 · ГОСУДАРСТВО</span><h3>СССР возник не в 1917</h3>"
        "<p>Советская Россия существовала до создания Союза в декабре 1922 года; "
        "союзное правительство сформировано позже.</p><a href='#source-PC05'>Основание: PC05 ↗</a></article>",
        "<article><span class='index'>02 · ПОЛИТИКА</span><h3>Власть не передавалась за день</h3>"
        "<p>1922–1929 и 1953–1958 годы требуют различать назначения и постепенное политическое первенство.</p>"
        "<a href='#source-PC03'>Основание: PC03 ↗</a></article>",
        "<article><span class='index'>03 · ПРАВО</span><h3>Коллегиальные органы</h3>"
        "<p>ЦИК СССР первоначально имел нескольких председателей; не следует превращать его в "
        "один президентский пост.</p><a href='#source-PC01'>Основание: PC01 ↗</a></article>",
        "</div>",
    ])
    for key, label in TRACKS.items():
        head.append(f"<section class='research-category'><h3>{esc(label)}</h3>")
        for row in data[key]:
            refs = ' · '.join(f"<a href='#source-{esc(ref)}'>{esc(ref)}</a>" for ref in row['sources'])
            head.append(
                f"<details id='{esc(row['id'])}' class='record'>"
                f"<summary><span class='dates'>{esc(row['from'])} — {esc(row['to'])}</span>"
                f"<span class='who'>{esc(person_label(row))}</span>"
                f"<span class='state'>{esc(STATUS_LABELS.get(row['status'], row['status']))}</span><span class='open' aria-hidden='true'>+</span></summary>"
                f"<div class='record-detail'><p>{esc(row['role'])}</p>")
            if row.get('note'):
                head.append(f"<p>{esc(row['note'])}</p>")
            head.append(f"<div class='refs'>Источники: {refs}</div></div></details>")
        head.append("</section>")
    head.extend(["<section class='open-items'><h3>Что ещё нужно проверить по документам</h3><ul>"])
    head.extend(f"<li>{esc(q)}</li>" for q in data['open_verification_items'])
    head.extend(["</ul></section>", "<section class='research-category'><h3>Библиография</h3><div class='sources-table'>"])
    for ident, item in sources.items():
        head.append(f"<div class='source-item' id='source-{esc(ident)}'><div class='sid'>{esc(ident)}</div>"
                    f"<div><a class='source-name' href='{esc(item['url'])}' target='_blank' rel='noopener noreferrer'>{esc(item['title'])} ↗</a>"
                    f"<p>{esc(item['note'])}</p></div></div>")
    head.extend([
        "</div></section></section></main>",
        "<footer class='container footer'><p><strong>Атлас власти · 1917–1991.</strong> "
        "Первичные материалы и изменения — в открытом GitHub-репозитории.</p>"
        "<p>Оригинальная фотография хранится отдельно и не опубликована. "
        f"Срез данных: {esc(data['as_of'])}. Ревизия: <code>{esc(revision[:12])}</code>.</p></footer>",
    ])
    # JSON is embedded verbatim in a non-executing script element; the characters
    # that could terminate or alter markup are encoded as JSON unicode escapes.
    embedded = json.dumps({k: data[k] for k in TRACKS}, ensure_ascii=False, separators=(',', ':'))
    embedded = embedded.replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    head.append(f"<script id='chronology-data' type='application/json'>{embedded}</script>")
    head.extend([f"<script defer src='./site.js?v={revision[:12]}'></script>",
                 f"<script defer src='./year-view.js?v={revision[:12]}'></script>",
                 f"<script defer src='./transition-view.js?v={revision[:12]}'></script>",
                  f"<script defer src='./universal-atlas.js?v={revision[:12]}'></script>",
                  f"<script defer src='./mobile-atlas.js?v={revision[:12]}'></script>",
                   f"<script defer src='./world-atlas.js?v={revision[:12]}'></script>",
                   f"<script defer src='./dynasty-atlas.js?v={revision[:12]}'></script>", "</body></html>"])
    return "\n".join(head)


def dump_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build(root: Path, out: Path, revision: str) -> dict:
    require(out.resolve() == (root / "dist").resolve(), "Output must be the repository dist directory")
    inputs = [root / DATA_PATH, root / SOURCE_PATH, root / "data/poster-transcription.tsv",
              root / "data/soviet-period-review.csv", root / "site/site.css", root / "site/site.js", root / "site/year-view.js",
              root / "site/transition-view.js", root / "site/universal-atlas.js", root / "site/mobile-atlas.js",
               root / "site/world-atlas.js", root / "data/atlas/world-pilots/1762.json",
               root / "site/dynasty-atlas.js", root / "data/atlas/world-pilots/dynasty-1762-1780.json",
               root / "data/atlas/world-pilots/extension-1781-1800.json",
               root / "data/atlas/world-pilots/dynasty-footprints-1762-1800.json",
               root / "data/atlas/world-pilots/coverage-1762-1800.json",
               root / "data/atlas/world-pilots/geographic-context-1762-1800.json"]
    data = json.loads(inputs[0].read_text(encoding="utf-8"), object_pairs_hook=no_duplicate_keys)
    sources = source_index(inputs[1].read_text(encoding="utf-8"))
    result = validate(data, sources)
    validate_transcription(inputs[2])
    poster_rows = poster_data(inputs[2], inputs[3])
    require(not any((root / "assets/original").glob("*.jpg")), "Do not include original JPEG in checkout")
    out.mkdir(exist_ok=True)
    result["revision"] = revision
    result["input_sha256"] = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    (out / "index.html").write_text(render(data, sources, result, revision, poster_rows), encoding="utf-8")
    shutil.copyfile(root / "site/site.css", out / "site.css")
    shutil.copyfile(root / "site/site.js", out / "site.js")
    shutil.copyfile(root / "site/year-view.js", out / "year-view.js")
    shutil.copyfile(root / "site/transition-view.js", out / "transition-view.js")
    shutil.copyfile(root / "site/universal-atlas.js", out / "universal-atlas.js")
    shutil.copyfile(root / "site/mobile-atlas.js", out / "mobile-atlas.js")
    shutil.copyfile(root / "site/world-atlas.js", out / "world-atlas.js")
    shutil.copyfile(root / "data/atlas/world-pilots/1762.json", out / "world-1762.json")
    shutil.copyfile(root / "site/dynasty-atlas.js", out / "dynasty-atlas.js")
    shutil.copyfile(root / "data/atlas/world-pilots/dynasty-1762-1780.json", out / "world-dynasty-18c.json")
    shutil.copyfile(root / "data/atlas/world-pilots/extension-1781-1800.json", out / "world-extension-1800.json")
    shutil.copyfile(root / "data/atlas/world-pilots/dynasty-footprints-1762-1800.json", out / "world-house-footprints.json")
    shutil.copyfile(root / "data/atlas/world-pilots/coverage-1762-1800.json", out / "world-coverage-1800.json")
    shutil.copyfile(root / "data/atlas/world-pilots/geographic-context-1762-1800.json", out / "world-geographic-1800.json")
    dump_json(out / "validation.json", result)
    dump_json(out / "chronology.json", data)
    dump_json(out / "sources.json", list(sources.values()))
    for key in TRACKS:
        with (out / f"{key}.csv").open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["id", "from", "to", "person_or_collective", "role", "status", "sources", "note"])
            for row in data[key]:
                cells = [row["id"], row["from"], row["to"], person_label(row), row["role"], row["status"], ";".join(row["sources"]), row.get("note", "")]
                # Do not allow spreadsheet formula execution when readers open a CSV.
                w.writerow(["'" + s if s.lstrip().startswith(("=", "+", "-", "@")) else s for s in cells])
    pending = "\n".join("- " + x for x in data["open_verification_items"])
    (out / "README.md").write_text("# Отчёт по советскому периоду\n\n" + DISCLAIMER + "\n\nОткройте index.html. JSON/CSV сохраняют исходную точность дат. Фотография не включена.\n\n## Открытые вопросы\n\n" + pending + "\n", encoding="utf-8")
    sums = "".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in sorted(out.iterdir()) if p.is_file() and p.name != "SHA256SUMS")
    (out / "SHA256SUMS").write_text(sums, encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", default="local-unversioned")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        result = build(root, root / "dist", args.revision)
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(f"Structural audit FAILED: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
