#!/usr/bin/env python3
"""Add Moscow Grand Principality / Russian Tsardom / Time of Troubles 1417–1617.

Run AFTER the Soviet, imperial and early-Romanov generators. This is an offline
append-only research presentation; it never modifies source historical files.
CI validates structure, provenance and publication isolation, not historical truth.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from scripts.extend_romanovs import ROOT, DIST, SOURCE_TSV, escape, replace_once
from scripts.soviet_audit import date_bounds, require

CHRONOLOGY = ROOT / "data/muscovy-chronology.json"
REVIEW = ROOT / "data/muscovy-period-review.csv"
SOURCES = ROOT / "research/muscovy-sources.md"
TRACKS = {
    "muscovy_rulers": "Великие князья и цари 1417–1610",
    "muscovy_regents": "Опека, фактические правители и претенденты",
    "muscovy_government": "Приказы, Избранная рада, опричнина и земщина",
    "muscovy_institutions": "Боярская дума и разовые земские соборы",
    "muscovy_events": "Объединение земель, реформы и Смута",
}

def source_index() -> dict:
    raw = SOURCES.read_text(encoding="utf-8")
    pattern = r"^\|\s*(MS\d+)\s*\|\s*\[([^\]]+)\]\((https?://.+?)\)\s*\|([^\n]*)"
    found = {}
    seen = re.findall(r"^\|\s*(MS\d+)\s*\|", raw, re.M)
    for code, title, url, note in re.findall(pattern, raw, re.M):
        require(code not in found, f"Duplicate source {code}")
        uri = urlsplit(url)
        require(uri.scheme == "https" and uri.hostname
                and not uri.username and not uri.password
                and uri.hostname not in {"drive.google.com", "docs.google.com"},
                f"Unsafe source URL: {code}")
        found[code] = {"id": code, "title": title, "url": url, "note": note.strip(" |")}
    require(bool(found) and len(found) == len(seen),
            "Muscovy bibliography malformed or duplicate")
    return found

def validated_input() -> tuple[dict, dict, list[dict]]:
    data = json.loads(CHRONOLOGY.read_text(encoding="utf-8"))
    require(data.get("schema_version") == 1 and data.get("source_index") == "research/muscovy-sources.md",
            "Unsupported Muscovy dataset contract")
    require(data.get("boundary_from") == "1417-01-01"
            and data.get("boundary_to") == "1617-01-01",
            "Expected exactly 200-year extension 1417–1617")
    require(data.get("primary_acts_for_every_appointment_verified") is False,
            "Do not promote editorial source checks into primary-act verification")
    refs = source_index()
    ids = set()
    for track in TRACKS:
        entries = data.get(track)
        require(isinstance(entries, list) and bool(entries),
                f"Missing Muscovy track {track}")
        for row in entries:
            key = row.get("id")
            require(isinstance(key, str) and re.fullmatch(r"M\d{2,}", key)
                    and key not in ids, f"Duplicate or invalid Muscovy id: {key}")
            ids.add(key)
            first, _ = date_bounds(row.get("from"))
            _, last = date_bounds(row.get("to"))
            require(first <= last, f"Reversed Muscovy interval {key}")
            for field in ("person", "role", "status"):
                require(isinstance(row.get(field), str) and bool(row[field].strip()),
                        f"Empty Muscovy {field}: {key}")
            source_ids = row.get("sources")
            require(isinstance(source_ids, list) and len(source_ids) > 0
                    and len(source_ids) == len(set(source_ids))
                    and all(code in refs for code in source_ids),
                    f"Missing or invalid source in {key}")
    rulers = data["muscovy_rulers"]
    require(any(r["person"].startswith("Василий I") and r["from"] == "1389" for r in rulers),
            "1417 display must not replace Vasily I's real reign from 1389")
    require(any(r["person"].startswith("Василий II") and r["from"] == "1425" for r in rulers),
            "Vasily II begins formal reign in 1425")
    require(any(r["person"].startswith("Иван IV") and r["from"] == "1533" for r in rulers),
            "Ivan IV must be Grand Prince from 1533")
    require(any(r["person"].startswith("Иван IV") and r["from"] == "1547" for r in rulers),
            "Ivan IV must be Tsar from 1547")
    require(not any(r["person"].startswith("Михаил Фёдорович") for r in rulers),
            "Michael Romanov 1613–1645 is already present in the next layer")
    require(any(r["person"].startswith("Фёдор Иванович") and r["to"] == "1598" for r in rulers),
            "Feodor must remain tsar until 1598")
    require(any(r["person"].startswith("Борис Фёдорович") and r["from"] == "1598" for r in rulers),
            "Boris becomes tsar only in 1598")
    require(any(r["person"].startswith("Симеон") and r["from"] == "1575"
                and r["to"] == "1576" for r in data["muscovy_regents"]),
            "Simeon nominal period is 1575–1576")
    with SOURCE_TSV.open(encoding="utf-8", newline="") as file:
        original = {row["row_id"]: row for row in csv.DictReader(file, delimiter="\t")}
    with REVIEW.open(encoding="utf-8-sig", newline="") as file:
        annotations = list(csv.DictReader(file))
    require([row["row_id"] for row in annotations] == [f"{n:03}" for n in range(59, 78)],
            "Poster rows 059–077 must appear in original order, exactly once")
    for row in annotations:
        ident = row["row_id"]
        orig = original.get(ident)
        require(orig is not None and orig["poster_side"] == "R"
                and orig["person_as_printed"] == row["printed_name"]
                and orig["reign_as_printed"] == row["printed_reign"]
                and orig["lifespan_as_printed"] == row["printed_life"],
                f"Source photograph mismatch: {ident}")
        citations = row["source_ids"].split(";")
        require(citations and len(citations) == len(set(citations))
                and all(code in refs for code in citations),
                f"Poster row {ident} has invalid references")
        for name in ("verified_role_dates", "corrected_life", "assessment", "category"):
            require(row.get(name) is not None and bool(row[name].strip()),
                    f"Missing {name} in poster annotation {ident}")
    return data, refs, annotations

def poster_rows(annotations: list[dict]) -> str:
    fragments = []
    for row in annotations:
        ident = row["row_id"]
        chapters = {
            "059": "1417–1462 · Московское княжество и династическая усобица",
            "064": "1462–1547 · Объединение земель и великие князья",
            "068": "1547–1584 · Русское царство и Иван IV",
            "071": "1584–1617 · От последних московских Рюриковичей к Смуте",
        }
        if ident in chapters:
            fragments.append("<tr class='chapter-row'><th colspan='4' scope='colgroup'>"
                             + escape(chapters[ident]) + "</th></tr>")
        disputed = ident in {"060", "061", "067", "068", "069", "071", "072", "074", "076", "077"}
        status = "issue" if disputed else "neutral"
        badge = "Нужна сверка" if disputed else "По годам"
        printed = row["printed_name"]
        if ident == "060":
            printed += " (Литовская)"
        if ident == "069":
            printed += " (Касимовский)"
        if ident == "077":
            printed += " (Польский)"
        fragments.append(
            f"<tr id='poster-{ident}' class='{'row-important' if disputed else ''}'>"
            f"<td class='period'>{escape(row['printed_reign'])}</td>"
            f"<td><span class='person'>{escape(printed)}</span>"
            f"<span class='name-meta'>Строка №{ident}</span></td>"
            f"<td class='lifetime'>{escape(row['printed_life'])}</td>"
            f"<td class='notes-cell'><span class='tag {status}'>{badge}</span>"
            f"<span>{escape(row['assessment'])}</span>"
            f"<div><button type='button' class='detail-trigger' aria-expanded='false' "
            f"aria-controls='poster-detail-{ident}'>Пояснение ↓</button></div></td></tr>"
        )
        links = " · ".join(f"<a href='#source-{escape(code)}'>{escape(code)}</a>"
                           for code in row["source_ids"].split(";"))
        fragments.append(
            f"<tr id='poster-detail-{ident}' class='detail-row' hidden>"
            f"<td colspan='4'><p><strong>Сверка:</strong> {escape(row['verified_role_dates'])}</p>"
            f"<p><strong>Годы жизни:</strong> {escape(row['corrected_life'])}. "
            f"<strong>Источники:</strong> {links}</p></td></tr>"
        )
    return "\n".join(fragments)

def research_sections(data: dict) -> str:
    chunks = []
    for track, label in TRACKS.items():
        chunks.append(f"<section class='research-category'><h3>{escape(label)}</h3>")
        for row in data[track]:
            refs = " · ".join(f"<a href='#source-{escape(code)}'>{escape(code)}</a>"
                               for code in row["sources"])
            chunks.append(
                f"<details id='{escape(row['id'])}' class='record'>"
                f"<summary><span class='dates'>{escape(row['from'])} — {escape(row['to'])}</span>"
                f"<span class='who'>{escape(row['person'])}</span>"
                f"<span class='state'>{escape(row['status'])}</span>"
                "<span class='open' aria-hidden='true'>+</span></summary>"
                f"<div class='record-detail'><p>{escape(row['role'])}</p>"
                + (f"<p>{escape(row['note'])}</p>" if row.get("note") else "")
                + f"<div class='refs'>Источники: {refs}</div></div></details>"
            )
        chunks.append("</section>")
    return "\n".join(chunks)

def build() -> dict:
    data, refs, annotations = validated_input()
    output = DIST / "index.html"
    require(output.is_file(), "Run earlier three build stages first")
    page = output.read_text(encoding="utf-8")
    require("id='poster-078'" in page and "id='poster-059'" not in page,
            "Expected the 1617–1991 page, without this overlay already applied")
    poster_marker = ("<tr class='chapter-row'><th colspan='4' scope='colgroup'>"
                     "1617–1721 · Русское царство, ранние Романовы и соправительство"
                     "</th></tr>")
    page = replace_once(page, poster_marker,
                        poster_rows(annotations) + "\n" + poster_marker, "poster chapter")
    research_marker = ("<section class='research-category'>"
                       "<h3>Цари и императоры, 1617–1801</h3>")
    page = replace_once(page, research_marker,
                        research_sections(data) + research_marker,
                        "research chapter")
    issues_marker = ("<section class='open-items'>"
                     "<h3>Что ещё нужно проверить по документам</h3><ul>")
    page = replace_once(page, issues_marker,
                        issues_marker + "".join("<li>" + escape(note) + "</li>"
                                                for note in data["open_verification_items"]),
                        "open historical checks")
    sources_marker = ("<section class='research-category'>"
                      "<h3>Библиография</h3><div class='sources-table'>")
    bibliography = "".join(
        f"<div class='source-item' id='source-{escape(code)}'>"
        f"<div class='sid'>{escape(code)}</div><div>"
        f"<a class='source-name' href='{escape(row['url'])}' "
        f"target='_blank' rel='noopener noreferrer'>{escape(row['title'])} ↗</a>"
        f"<p>{escape(row['note'])}</p></div></div>"
        for code, row in refs.items()
    )
    page = replace_once(page, sources_marker, sources_marker + bibliography,
                        "independent bibliography")
    marker = "<script id='chronology-data' type='application/json'>"
    require(page.count(marker) == 1, "Serialized chronology not found")
    before, after = page.split(marker, 1)
    payload, rest = after.split("</script>", 1)
    records = json.loads(payload)
    require(all(key not in records for key in TRACKS), "Early-Moscow data already embedded")
    records.update({key: data[key] for key in TRACKS})
    encoded = json.dumps(records, ensure_ascii=False, separators=(",", ":"))
    encoded = encoded.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    page = before + marker + encoded + "</script>" + rest
    result_path = DIST / "validation.json"
    receipt = json.loads(result_path.read_text(encoding="utf-8"))
    added = sum(len(data[track]) for track in TRACKS)
    page = replace_once(page, f"<b>{receipt['poster_rows']}</b> строк плаката",
                        f"<b>{receipt['poster_rows'] + len(annotations)}</b> строк плаката",
                        "poster count")
    page = replace_once(page, f"<b>{receipt['records']}</b> записей о должностях и событиях",
                        f"<b>{receipt['records'] + added}</b> записей о должностях и событиях",
                        "record count")
    page = replace_once(page, f"<b>{receipt['sources']}</b> ссылок на источники",
                        f"<b>{receipt['sources'] + len(refs)}</b> ссылок на источники",
                        "bibliography count")
    labels = [
        ("Правители государства · 1617–1991", "Правители государства · 1417–1991"),
        ("1617–1991: Русское царство, Российская империя и СССР",
         "1417–1991: Московское княжество, Русское царство, Российская империя и СССР"),
        ("Исторический атлас / выпуск 01 / 1617–1991",
         "Исторический атлас / выпуск 01 / 1417–1991"),
        ("<strong>1617—1991</strong>", "<strong>1417—1991</strong>"),
        ("Атлас власти · 1617–1991", "Атлас власти · 1417–1991"),
        ("<button class='era-btn' type='button' data-era='all' aria-pressed='true'>1617–1991</button>",
         "<button class='era-btn' type='button' data-era='all' aria-pressed='true'>1417–1991</button>"
         "<button class='era-btn' type='button' data-era='muscovy' aria-pressed='false'>1417–1547</button>"
         "<button class='era-btn' type='button' data-era='tsardom' aria-pressed='false'>1547–1617</button>"
         "<button class='era-btn' type='button' data-era='troubles' aria-pressed='false'>1598–1613</button>"),
        ("Цари / императоры / партия</span>",
         "Князья / цари / императоры / партия</span>"),
        ("Царство Русское до 1721, затем Российская империя до 1917; советская Россия с 1917 года.",
         "Московское княжество, затем царский титул с 1547, императорский с 1721; советское государство с 1917 года."),
    ]
    for old, new in labels:
        page = replace_once(page, old, new, old[:50])
    output.write_text(page, encoding="utf-8")

    chronology_path = DIST / "chronology.json"
    timeline = json.loads(chronology_path.read_text(encoding="utf-8"))
    require(all(key not in timeline for key in TRACKS), "Muscovy data already in JSON")
    timeline.update({key: data[key] for key in TRACKS})
    chronology_path.write_text(json.dumps(timeline, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
    bibliography_path = DIST / "sources.json"
    prev_sources = json.loads(bibliography_path.read_text(encoding="utf-8"))
    existing_refs = {r["id"] for r in prev_sources}
    require(all(code not in existing_refs for code in refs),
            "Duplicated research source IDs")
    bibliography_path.write_text(
        json.dumps(prev_sources + list(refs.values()), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    receipt["muscovy_records"] = added
    receipt["records"] += added
    receipt["sources"] += len(refs)
    receipt["poster_rows"] += len(annotations)
    receipt["display_range"] = "1417–1991"
    receipt["muscovy_primary_acts_verified"] = False
    receipt["historical_truth_verified_by_ci"] = False
    receipt["open_items"] += len(data["open_verification_items"])
    for inp in (CHRONOLOGY, REVIEW, SOURCES):
        receipt["input_sha256"][str(inp.relative_to(ROOT))] = hashlib.sha256(inp.read_bytes()).hexdigest()
    result_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")

    with (DIST / "muscovy.csv").open("w", encoding="utf-8-sig", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["track", "id", "from", "to", "person", "role", "status", "sources", "note"])
        for track in TRACKS:
            for item in data[track]:
                cells = [track, item["id"], item["from"], item["to"], item["person"],
                         item["role"], item["status"], ";".join(item["sources"]), item.get("note", "")]
                writer.writerow(["'" + x if x.lstrip().startswith(("=", "+", "-", "@")) else x
                                 for x in cells])
    readme = DIST / "README.md"
    prev = readme.read_text(encoding="utf-8")
    readme.write_text(prev.replace("1617–1991", "1417–1991")
                      + "\nМосковское княжество и Смута добавлены независимым источниковым слоем.\n",
                      encoding="utf-8")
    checksums = "".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
        for path in sorted(DIST.iterdir()) if path.is_file() and path.name != "SHA256SUMS"
    )
    (DIST / "SHA256SUMS").write_text(checksums, encoding="utf-8")
    return {"records_added": added, "sources_added": len(refs),
            "original_poster_rows": receipt["poster_rows"], "range": "1417–1991",
            "historical_truth_verified_by_ci": False}


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
