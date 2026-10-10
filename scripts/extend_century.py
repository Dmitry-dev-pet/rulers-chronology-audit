#!/usr/bin/env python3
"""Add a source-qualified 1817–1917 imperial layer to the existing Soviet site.

Run AFTER scripts/soviet_audit.py. This is a presentation overlay, not a
replacement or modification of the immutable source poster or Soviet records.
"""
from __future__ import annotations

import csv
import hashlib
import html
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from scripts.soviet_audit import date_bounds, require

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
IMPERIAL_JSON = ROOT / "data/imperial-chronology.json"
IMPERIAL_CSV = ROOT / "data/imperial-period-review.csv"
IMPERIAL_SOURCES = ROOT / "research/imperial-sources.md"
SOURCE_TSV = ROOT / "data/poster-transcription.tsv"

TRACKS = {
    "imperial_monarchy": "Российские императоры",
    "imperial_government": "Правительственные учреждения: XIX век — 1917 год",
    "imperial_institutions": "Государственный совет и Государственная дума",
    "imperial_events": "Поворотные события и оспариваемые переходы",
}

def escape(value: object) -> str:
    return html.escape(str(value), quote=True)

def replace_once(text: str, before: str, after: str, where: str) -> str:
    require(text.count(before) == 1, f"Site template mismatch: {where}")
    return text.replace(before, after, 1)

def get_sources() -> dict:
    raw = IMPERIAL_SOURCES.read_text(encoding="utf-8")
    pattern = r"^\|\s*(IM\d+)\s*\|\s*\[([^\]]+)\]\((https?://.+?)\)\s*\|([^\n]*)"
    rows = re.findall(pattern, raw, re.M)
    declared = re.findall(r"^\|\s*(IM\d+)\s*\|", raw, re.M)
    require(bool(rows) and len(rows) == len(declared), "Malformed imperial source index")
    found = {}
    for code, title, url, explanation in rows:
        require(code not in found, f"Duplicate imperial source {code}")
        parsed = urlsplit(url)
        require(parsed.scheme == "https" and bool(parsed.netloc) and not parsed.username
                and not parsed.password and parsed.hostname not in {"drive.google.com", "docs.google.com"},
                f"Private/unsafe imperial source {code}")
        found[code] = dict(id=code, title=title, url=url, note=explanation.strip(" |"))
    return found

def validated_input():
    data = json.loads(IMPERIAL_JSON.read_text(encoding="utf-8"))
    require(data.get("schema_version") == 1 and data.get("boundary_from") == "1817-01-01",
            "Expected documented 1817 imperial extension")
    require(data.get("boundary_to") == "1917-11-08", "Unexpected end of imperial transition")
    require(data.get("primary_acts_for_every_appointment_verified") is False,
            "Do not claim every historical date verified")
    sources = get_sources()
    ids = set()
    for track in TRACKS:
        items = data.get(track)
        require(isinstance(items, list) and items, f"Imperial track missing: {track}")
        for row in items:
            ident = row.get("id")
            require(isinstance(ident, str) and re.fullmatch(r"I\d{2,}", ident),
                    "Invalid record ID")
            require(ident not in ids, f"Duplicate imperial record ID: {ident}")
            ids.add(ident)
            lower, _ = date_bounds(row.get("from"))
            _, upper = date_bounds(row.get("to"))
            require(lower <= upper, f"Reverse imperial tenure: {ident}")
            require(isinstance(row.get("role"), str) and row["role"].strip(),
                    f"No role: {ident}")
            require(isinstance(row.get("status"), str) and row["status"].strip(),
                    f"No status: {ident}")
            refs = row.get("sources")
            require(isinstance(refs, list) and refs and len(set(refs)) == len(refs)
                    and all(code in sources for code in refs),
                    f"Missing evidence in {ident}")
    require(len(data["imperial_monarchy"]) == 5, "Five reigning emperors expected")
    require(len(data["imperial_events"]) >= 2, "1925 crisis and 1917 transition missing")
    original = {}
    with SOURCE_TSV.open(encoding="utf-8", newline="") as f:
        original = {row["row_id"]: row for row in csv.DictReader(f, delimiter="\t")}
    with IMPERIAL_CSV.open(encoding="utf-8-sig", newline="") as f:
        annotations = list(csv.DictReader(f))
    require([r["row_id"] for r in annotations] == [f"{i:03d}" for i in range(91, 97)],
            "Imperial review rows must be exactly 091..096")
    for record in annotations:
        o = original[record["row_id"]]
        require(record["printed_name"] == o["person_as_printed"] and
                record["printed_reign"] == o["reign_as_printed"] and
                record["printed_life"] == o["lifespan_as_printed"] and
                o["poster_side"] == "R",
                f"Source/transcription mismatch on row {record['row_id']}")
        refs = record["source_ids"].split(";")
        require(refs and all(ref in sources for ref in refs),
                f"Missing sources for poster {record['row_id']}")
    return data, sources, annotations

def poster_rows(annotations: list[dict]) -> str:
    result = ["<tr class='chapter-row'><th colspan='4' scope='colgroup'>"
              "1817–1917 · Российская империя — пять императоров, кризис наследования 1825 года"
              "</th></tr>"]
    for row in annotations:
        ident = row["row_id"]
        uncertain = ident in {"092", "096"}
        cls = "row-important" if uncertain else ""
        label = "Спорный статус" if ident == "092" else "Уточнить" if uncertain else "По годам"
        status = "issue" if uncertain else "neutral"
        result.append(
            f"<tr id='poster-{ident}' class='{cls}'>"
            f"<td class='period'>{escape(row['printed_reign'])}</td>"
            f"<td><span class='person'>{escape(row['printed_name'])}</span>"
            f"<span class='name-meta'>Строка №{ident}</span></td>"
            f"<td class='lifetime'>{escape(row['printed_life'])}</td>"
            f"<td class='notes-cell'><span class='tag {status}'>{label}</span>"
            f"<span>{escape(row['assessment'])}</span>"
            f"<div><button type='button' class='detail-trigger' aria-expanded='false' "
            f"aria-controls='poster-detail-{ident}'>Пояснение ↓</button></div></td></tr>"
        )
        source_links = " · ".join(
            f"<a href='#source-{escape(code)}'>{escape(code)}</a>"
            for code in row["source_ids"].split(";")
        )
        result.append(
            f"<tr id='poster-detail-{ident}' class='detail-row' hidden><td colspan='4'>"
            f"<p><strong>Статус и сверка:</strong> {escape(row['verified_role_dates'])}</p>"
            f"<p><strong>Уточнённые годы жизни:</strong> {escape(row['corrected_life'])}. "
            f"<strong>Источники:</strong> {source_links}</p></td></tr>"
        )
    return "\n".join(result)

def research_sections(data: dict) -> str:
    items = []
    for key, name in TRACKS.items():
        items.append(f"<section class='research-category'><h3>{escape(name)}</h3>")
        for row in data[key]:
            person = row.get("person") or "Учреждение / событие"
            refs = " · ".join(f"<a href='#source-{escape(ref)}'>{escape(ref)}</a>"
                              for ref in row["sources"])
            items.append(
                f"<details id='{escape(row['id'])}' class='record'>"
                f"<summary><span class='dates'>{escape(row['from'])} — {escape(row['to'])}</span>"
                f"<span class='who'>{escape(person)}</span>"
                f"<span class='state'>{escape(row['status'])}</span>"
                f"<span class='open' aria-hidden='true'>+</span></summary>"
                f"<div class='record-detail'><p>{escape(row['role'])}</p>"
                + (f"<p>{escape(row['note'])}</p>" if row.get("note") else "")
                + f"<div class='refs'>Источники: {refs}</div></div></details>"
            )
        items.append("</section>")
    return "\n".join(items)

def build() -> dict:
    data, sources, annotations = validated_input()
    index = DIST / "index.html"
    require(index.is_file(), "First run the existing Soviet renderer")
    site = index.read_text(encoding="utf-8")
    require("id='poster-091'" not in site, "Imperial overlay already applied")
    marker = "<tr class='chapter-row'><th colspan='4' scope='colgroup'>1917 · Переходная власть (до советского правительства)</th></tr>"
    site = replace_once(site, marker, poster_rows(annotations) + "\n" + marker, "poster insertion")
    source_marker = "<section class='research-category'><h3>Партия</h3>"
    site = replace_once(site, source_marker, research_sections(data) + source_marker,
                        "research insertion")
    open_marker = "<section class='open-items'><h3>Что ещё нужно проверить по документам</h3><ul>"
    site = replace_once(site, open_marker, open_marker + "".join(
        "<li>" + escape(item) + "</li>" for item in data["open_verification_items"]),
        "open research questions")
    sources_marker = "<section class='research-category'><h3>Библиография</h3><div class='sources-table'>"
    source_elements = "".join(
        f"<div class='source-item' id='source-{escape(code)}'>"
        f"<div class='sid'>{escape(code)}</div><div>"
        f"<a class='source-name' href='{escape(ref['url'])}' target='_blank'"
        f" rel='noopener noreferrer'>{escape(ref['title'])} ↗</a>"
        f"<p>{escape(ref['note'])}</p></div></div>"
        for code, ref in sources.items()
    )
    site = replace_once(site, sources_marker, sources_marker + source_elements, "bibliography")

    start = "<script id='chronology-data' type='application/json'>"
    finish = "</script>"
    require(site.count(start) == 1, "Missing serialized chronology")
    left, right = site.split(start, 1)
    raw, rest = right.split(finish, 1)
    payload = json.loads(raw)
    require(all(track not in payload for track in TRACKS), "Imperial data key collision")
    payload.update({track: data[track] for track in TRACKS})
    embedded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    embedded = (embedded.replace("<", "\\u003c").replace(">", "\\u003e")
                        .replace("&", "\\u0026"))
    site = left + start + embedded + finish + rest

    fixed = [
        ("Правители государства · Советский период 1917–1991",
         "Правители государства · 1817–1991"),
        ("Советский период, 1917–1991", "1817–1991: Российская империя и СССР"),
        ("Исторический атлас / выпуск 01 / 1917–1991",
         "Исторический атлас / выпуск 01 / 1817–1991"),
        ("Правители<br><em>советского периода</em>",
         "Правители<br><em>России и СССР</em>"),
        ("<strong>1917—1991</strong>", "<strong>1817—1991</strong>"),
        ("Атлас власти · 1917–1991", "Атлас власти · 1817–1991"),
        ("<button class='era-btn' type='button' data-era='all' aria-pressed='true'>1917–1991</button>",
         "<button class='era-btn' type='button' data-era='all' aria-pressed='true'>1817–1991</button>"
         "<button class='era-btn' type='button' data-era='imperial' aria-pressed='false'>1817–1917</button>"
         "<button class='era-btn' type='button' data-era='transition' aria-pressed='false'>1894–1925</button>"),
        ("Три линии на одной оси времени",
         "Император, правительство и партия: общая шкала"),
    ]
    for before, after in fixed:
        site = replace_once(site, before, after, before[:55])
    site = site.replace("Советская Россия с 1917 года. СССР образован в 1922 году.",
                        "Российская империя до 1917; советская Россия с 1917 года. СССР образован в 1922 году.")
    site = site.replace("Исторический атлас / выпуск 01", "Исторический атлас / выпуск 01")
    index.write_text(site, encoding="utf-8")

    chronology = DIST / "chronology.json"
    existing = json.loads(chronology.read_text(encoding="utf-8"))
    require(all(track not in existing for track in TRACKS), "Imperial data already in chronology")
    existing.update({track: data[track] for track in TRACKS})
    chronology.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
    bibliography = DIST / "sources.json"
    old_sources = json.loads(bibliography.read_text(encoding="utf-8"))
    require(all(row["id"] not in {x["id"] for x in old_sources} for row in sources.values()),
            "Duplicate source labels")
    bibliography.write_text(json.dumps(old_sources + list(sources.values()),
                                       ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = DIST / "validation.json"
    result = json.loads(report.read_text(encoding="utf-8"))
    count = sum(len(data[t]) for t in TRACKS)
    result["imperial_records"] = count
    result["records"] += count
    result["sources"] += len(sources)
    result["poster_rows"] = 10 + len(annotations)
    result["historical_truth_verified_by_ci"] = False
    result["display_range"] = "1817–1991"
    result["imperial_primary_acts_verified"] = False
    for path in (IMPERIAL_JSON, IMPERIAL_CSV, IMPERIAL_SOURCES):
        result["input_sha256"][str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")

    with (DIST / "imperial.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["track", "id", "from", "to", "person", "role", "status", "sources", "note"])
        for track in TRACKS:
            for row in data[track]:
                person = row.get("person") or ""
                cells = [track, row["id"], row["from"], row["to"], person,
                         row["role"], row["status"], ";".join(row["sources"]), row.get("note", "")]
                writer.writerow(["'" + cell if cell.lstrip().startswith(("=", "+", "-", "@"))
                                 else cell for cell in cells])

    readme = DIST / "README.md"
    original = readme.read_text(encoding="utf-8")
    readme.write_text(original.replace("Отчёт по советскому периоду",
                                      "Исторический атлас России: 1817–1991")
                     + "\nИмперская часть добавлена отдельным источниковедческим слоем.\n",
                     encoding="utf-8")
    digest = "".join(
        f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n"
        for p in sorted(DIST.iterdir()) if p.is_file() and p.name != "SHA256SUMS"
    )
    (DIST / "SHA256SUMS").write_text(digest, encoding="utf-8")
    return dict(imperial_records=count, poster_rows=10+len(annotations),
                source_count=len(sources), mode="source-preserving-overlay",
                historical_truth_verified_by_ci=False)

if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
