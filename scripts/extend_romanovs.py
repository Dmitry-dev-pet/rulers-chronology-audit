#!/usr/bin/env python3
"""Extend the verified 1817–1991 report 200 years backwards to 1617.

Runs AFTER scripts.soviet_audit AND scripts.extend_century. Never rewrites
the source poster, reviewed 1817–1917 or Soviet chronology. This is an offline
source-qualified presentation layer, NOT historical truth verification.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from scripts.extend_century import ROOT, DIST, SOURCE_TSV, escape, replace_once
from scripts.soviet_audit import date_bounds, require

ROMANOV_JSON = ROOT / "data/early-romanov-chronology.json"
ROMANOV_REVIEW = ROOT / "data/early-romanov-period-review.csv"
ROMANOV_SOURCES = ROOT / "research/early-romanov-sources.md"

TRACKS = {
    "early_monarchy": "Цари и императоры, 1617–1801",
    "early_regency": "Регентство и политическое соправление",
    "early_executive": "Приказы, коллегии и Сенат",
    "early_institutions": "Боярская дума и высшие советы",
    "early_events": "Перемены статуса государства и политические события",
}

def sources() -> dict:
    markdown = ROMANOV_SOURCES.read_text(encoding="utf-8")
    rows = re.findall(r"^\|\s*(RM\d+)\s*\|\s*\[([^\]]+)\]\((https?://.+?)\)\s*\|([^\n]*)", markdown, re.M)
    declared = re.findall(r"^\|\s*(RM\d+)\s*\|", markdown, re.M)
    require(bool(rows) and len(rows) == len(declared),
            "Early Romanov source index is incomplete or malformed")
    found = {}
    for key, title, url, note in rows:
        require(key not in found, f"Duplicate source: {key}")
        parts = urlsplit(url)
        require(parts.scheme == "https" and bool(parts.hostname)
                and not parts.username and not parts.password
                and parts.hostname not in ("drive.google.com", "docs.google.com"),
                f"Unsafe or private source URL: {key}")
        found[key] = {"id": key, "title": title, "url": url, "note": note.strip(" |")}
    return found

def validated_input() -> tuple[dict, dict, list[dict]]:
    source = json.loads(ROMANOV_JSON.read_text(encoding="utf-8"))
    require(source.get("schema_version") == 1, "Unsupported early Romanov data schema")
    require(source.get("boundary_from") == "1617-01-01" and
            source.get("boundary_to") == "1817-01-01",
            "Display must extend exactly 200 years backwards to 1617")
    require(source.get("primary_acts_for_every_appointment_verified") is False,
            "Never promote preliminary historical research into verified fact")
    require(source.get("source_index") == "research/early-romanov-sources.md",
            "Unexpected Romanov source index")
    found = sources()
    ids: set[str] = set()
    for track in TRACKS:
        rows = source.get(track)
        require(isinstance(rows, list) and len(rows) >= 1,
                f"Missing early Romanov track: {track}")
        for row in rows:
            ident = row.get("id")
            require(isinstance(ident, str) and re.fullmatch(r"R\d{2,}", ident)
                    and ident not in ids, f"Duplicate/bad Romanov record: {ident}")
            ids.add(ident)
            a, _ = date_bounds(row.get("from"))
            _, b = date_bounds(row.get("to"))
            require(a <= b, f"Reversed Romanov interval: {ident}")
            require(isinstance(row.get("person"), str) and row["person"].strip(),
                    f"Unnamed Romanov institution/ruler: {ident}")
            for field in ("role", "status"):
                require(isinstance(row.get(field), str) and row[field].strip(),
                        f"Missing {field}: {ident}")
            refs = row.get("sources")
            require(isinstance(refs, list) and bool(refs)
                    and len(refs) == len(set(refs))
                    and all(code in found for code in refs),
                    f"Missing or duplicate source: {ident}")
    rulers = source["early_monarchy"]
    require(len(rulers) == 13, "Expected 13 early Romanov sovereign records")
    require(not any("Александр I" in r["person"] for r in rulers),
            "Alexander I already exists in 1817–1917 data: no duplicate tenure")
    ivan = next(r for r in rulers if r["person"].startswith("Иван V"))
    peter = next(r for r in rulers if r["person"].startswith("Пётр I"))
    sophia = next(r for r in source["early_regency"] if r["person"].startswith("Софья"))
    require(ivan["from"] == peter["from"] == sophia["from"] == "1682"
            and ivan["to"] == "1696" and sophia["to"] == "1689",
            "Must preserve both 1682–1696 tsars and overlapping 1682–1689 regency")
    ivan_six = next(r for r in rulers if r["person"].startswith("Иван VI"))
    require("Ивана V" in ivan_six["note"], "Ivan VI must descend from Ivan V")
    original = {}
    with SOURCE_TSV.open(encoding="utf-8", newline="") as fh:
        original = {row["row_id"]: row for row in csv.DictReader(fh, delimiter="\t")}
    with ROMANOV_REVIEW.open(encoding="utf-8-sig", newline="") as fh:
        annotations = list(csv.DictReader(fh))
    require([r["row_id"] for r in annotations] == [f"{x:03}" for x in range(78, 91)],
            "Romanov poster annotations must cover exactly 078–090 in order")
    for row in annotations:
        actual = original.get(row["row_id"])
        require(actual is not None and actual["poster_side"] == "R",
                f"Missing original poster row: {row['row_id']}")
        require(actual["person_as_printed"] == row["printed_name"]
                and actual["reign_as_printed"] == row["printed_reign"]
                and actual["lifespan_as_printed"] == row["printed_life"],
                f"Romanov annotation alters the source photo: {row['row_id']}")
        refs = row["source_ids"].split(";")
        require(refs and len(refs) == len(set(refs)) and all(c in found for c in refs),
                f"Source references missing for poster row: {row['row_id']}")
        for field in ("category", "verified_role_dates", "corrected_life", "assessment"):
            require(row.get(field) is not None and row[field].strip(),
                    f"Missing corrected annotation {field} for {row['row_id']}")
    return source, found, annotations

def poster_rows(annotations: list[dict]) -> str:
    result = []
    for row in annotations:
        number = row["row_id"]
        if number == "078":
            result.append("<tr class='chapter-row'><th colspan='4' scope='colgroup'>"
                          "1617–1721 · Русское царство, ранние Романовы и соправительство"
                          "</th></tr>")
        if number == "083":
            result.append("<tr class='chapter-row'><th colspan='4' scope='colgroup'>"
                          "1721–1817 · Российская империя (титул Петра I с 1721 года)"
                          "</th></tr>")
        disputed = number in {"081", "082", "086"}
        calendar = number in {"087", "088"}
        state = "issue" if disputed else "context" if calendar else "neutral"
        caption = "Регент" if number == "081" else (
            "Уточнить" if disputed else "Календарь" if calendar else "По годам"
        )
        person = row["printed_name"]
        # The photo's qualifier (e.g. Ivan VI's incorrect pedigree) remains
        # in the immutable TSV; it is displayed as printed here too.
        if number == "085":
            person += " (племянница Петра I)"
        if number == "086":
            person += " (правнук Петра I — как в оригинале)"
        if number == "088":
            person += " (внук Петра I)"
        result.append(
            f"<tr id='poster-{number}' class='{'row-important' if disputed else ''}'>"
            f"<td class='period'>{escape(row['printed_reign'])}</td>"
            f"<td><span class='person'>{escape(person)}</span>"
            f"<span class='name-meta'>Строка №{number}</span></td>"
            f"<td class='lifetime'>{escape(row['printed_life'])}</td>"
            f"<td class='notes-cell'><span class='tag {state}'>{caption}</span>"
            f"<span>{escape(row['assessment'])}</span>"
            f"<div><button type='button' class='detail-trigger' aria-expanded='false'"
            f" aria-controls='poster-detail-{number}'>Пояснение ↓</button></div></td></tr>"
        )
        links = " · ".join(
            f"<a href='#source-{escape(ref)}'>{escape(ref)}</a>"
            for ref in row["source_ids"].split(";")
        )
        result.append(
            f"<tr id='poster-detail-{number}' class='detail-row' hidden>"
            "<td colspan='4'>"
            f"<p><strong>Статус:</strong> {escape(row['verified_role_dates'])}</p>"
            f"<p><strong>Годы жизни с учётом источников:</strong> "
            f"{escape(row['corrected_life'])}. <strong>Источники:</strong> {links}</p>"
            "</td></tr>"
        )
    return "\n".join(result)

def research_sections(data: dict) -> str:
    out = []
    for track, name in TRACKS.items():
        out.append(f"<section class='research-category'><h3>{escape(name)}</h3>")
        for row in data[track]:
            links = " · ".join(f"<a href='#source-{escape(s)}'>{escape(s)}</a>"
                               for s in row["sources"])
            out.append(
                f"<details id='{escape(row['id'])}' class='record'>"
                f"<summary><span class='dates'>{escape(row['from'])} — {escape(row['to'])}</span>"
                f"<span class='who'>{escape(row['person'])}</span>"
                f"<span class='state'>{escape(row['status'])}</span>"
                "<span class='open' aria-hidden='true'>+</span></summary>"
                f"<div class='record-detail'><p>{escape(row['role'])}</p>"
                + (f"<p>{escape(row['note'])}</p>" if row.get("note") else "")
                + f"<div class='refs'>Источники: {links}</div></div></details>"
            )
        out.append("</section>")
    return "\n".join(out)

def build() -> dict:
    data, refs, annotations = validated_input()
    index = DIST / "index.html"
    require(index.is_file(), "Build Soviet + imperial report first")
    document = index.read_text(encoding="utf-8")
    require("id='poster-091'" in document and "id='poster-078'" not in document,
            "Expected exactly one already-integrated imperial layer, without Romanovs")
    marker = ("<tr class='chapter-row'><th colspan='4' scope='colgroup'>"
              "1817–1917 · Российская империя — пять императоров, кризис наследования 1825 года"
              "</th></tr>")
    document = replace_once(document, marker,
                            poster_rows(annotations) + "\n" + marker, "new early poster")
    research_marker = ("<section class='research-category'>"
                       "<h3>Российские императоры</h3>")
    document = replace_once(document, research_marker,
                            research_sections(data) + research_marker,
                            "source-qualified early research")
    open_marker = "<section class='open-items'><h3>Что ещё нужно проверить по документам</h3><ul>"
    document = replace_once(document, open_marker,
                            open_marker + "".join(
                                f"<li>{escape(item)}</li>"
                                for item in data["open_verification_items"]),
                            "unresolved early historical issues")
    bibliography = "<section class='research-category'><h3>Библиография</h3><div class='sources-table'>"
    additions = "".join(
        f"<div class='source-item' id='source-{escape(key)}'>"
        f"<div class='sid'>{escape(key)}</div><div>"
        f"<a class='source-name' href='{escape(item['url'])}'"
        f" target='_blank' rel='noopener noreferrer'>{escape(item['title'])} ↗</a>"
        f"<p>{escape(item['note'])}</p></div></div>"
        for key, item in refs.items()
    )
    document = replace_once(document, bibliography, bibliography + additions,
                            "early Romanov bibliography")
    begin = "<script id='chronology-data' type='application/json'>"
    require(document.count(begin) == 1, "Missing timeline data payload")
    before, suffix = document.split(begin, 1)
    embedded, after = suffix.split("</script>", 1)
    payload = json.loads(embedded)
    require(all(key not in payload for key in TRACKS), "Early data was already embedded")
    payload.update({key: data[key] for key in TRACKS})
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    encoded = encoded.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    document = before + begin + encoded + "</script>" + after

    previous = json.loads((DIST / "validation.json").read_text(encoding="utf-8"))
    count = sum(len(data[k]) for k in TRACKS)
    document = replace_once(document,
                            f"<b>{previous['poster_rows']}</b> строк плаката",
                            f"<b>{previous['poster_rows'] + len(annotations)}</b> строк плаката",
                            "visible poster count")
    document = replace_once(document,
                            f"<b>{previous['records']}</b> записей о должностях и событиях",
                            f"<b>{previous['records'] + count}</b> записей о должностях и событиях",
                            "office and event count")
    document = replace_once(document,
                            f"<b>{previous['sources']}</b> ссылок на источники",
                            f"<b>{previous['sources'] + len(refs)}</b> ссылок на источники",
                            "bibliography count")
    changes = [
        ("Правители государства · 1817–1991", "Правители государства · 1617–1991"),
        ("1817–1991: Российская империя и СССР",
         "1617–1991: Русское царство, Российская империя и СССР"),
        ("Исторический атлас / выпуск 01 / 1817–1991",
         "Исторический атлас / выпуск 01 / 1617–1991"),
        ("<strong>1817—1991</strong>", "<strong>1617—1991</strong>"),
        ("Атлас власти · 1817–1991", "Атлас власти · 1617–1991"),
        ("<button class='era-btn' type='button' data-era='all' aria-pressed='true'>1817–1991</button>",
         "<button class='era-btn' type='button' data-era='all' aria-pressed='true'>1617–1991</button>"
         "<button class='era-btn' type='button' data-era='romanov' aria-pressed='false'>1617–1721</button>"
         "<button class='era-btn' type='button' data-era='eighteenth' aria-pressed='false'>1721–1817</button>"
         "<button class='era-btn' type='button' data-era='dual' aria-pressed='false'>1682–1741</button>"),
        ("Монархия / партия</span>", "Цари / императоры / партия</span>"),
        ("Российская империя до 1917; советская Россия с 1917 года.",
         "Царство Русское до 1721, затем Российская империя до 1917; советская Россия с 1917 года."),
    ]
    for old, new in changes:
        document = replace_once(document, old, new, old[:60])
    index.write_text(document, encoding="utf-8")

    chronology = DIST / "chronology.json"
    full = json.loads(chronology.read_text(encoding="utf-8"))
    require(all(k not in full for k in TRACKS), "Unexpected duplicate Romanov chronology")
    full.update({k: data[k] for k in TRACKS})
    chronology.write_text(json.dumps(full, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
    bibliography_path = DIST / "sources.json"
    other_sources = json.loads(bibliography_path.read_text(encoding="utf-8"))
    already = {r["id"] for r in other_sources}
    require(not any(key in already for key in refs), "Romanov source IDs already exist")
    bibliography_path.write_text(
        json.dumps(other_sources + list(refs.values()), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )
    previous["early_romanov_records"] = count
    previous["records"] += count
    previous["sources"] += len(refs)
    previous["poster_rows"] += len(annotations)
    previous["display_range"] = "1617–1991"
    previous["historical_truth_verified_by_ci"] = False
    previous["early_romanov_primary_acts_verified"] = False
    previous["open_items"] += len(data["open_verification_items"])
    for input_path in (ROMANOV_JSON, ROMANOV_REVIEW, ROMANOV_SOURCES):
        previous["input_sha256"][str(input_path.relative_to(ROOT))] = hashlib.sha256(input_path.read_bytes()).hexdigest()
    (DIST / "validation.json").write_text(
        json.dumps(previous, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (DIST / "romanov.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["track", "id", "from", "to", "person", "role", "status", "sources", "note"])
        for track in TRACKS:
            for row in data[track]:
                line = [track, row["id"], row["from"], row["to"], row["person"],
                        row["role"], row["status"], ";".join(row["sources"]), row.get("note", "")]
                writer.writerow(["'" + x if x.lstrip().startswith(("=", "+", "-", "@"))
                                 else x for x in line])
    index_readme = DIST / "README.md"
    original = index_readme.read_text(encoding="utf-8")
    index_readme.write_text(original.replace("1817–1991", "1617–1991") +
                            "\nРанние Романовы добавлены отдельным слоем, включая соправление и регентство.\n",
                            encoding="utf-8")
    sums = "".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
        for path in sorted(DIST.iterdir()) if path.is_file() and path.name != "SHA256SUMS"
    )
    (DIST / "SHA256SUMS").write_text(sums, encoding="utf-8")
    return {"records_added": count, "sources_added": len(refs),
            "original_poster_rows": previous["poster_rows"],
            "range": "1617–1991", "historical_truth_verified_by_ci": False}


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
