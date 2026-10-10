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


def render(data: dict, sources: dict, result: dict, revision: str) -> str:
    out = ["<!doctype html><html lang='ru'><meta charset='utf-8'>",
           "<meta name='viewport' content='width=device-width,initial-scale=1'>",
           "<title>Советская власть · три хронологии</title>",
           "<style>body{font:17px/1.55 system-ui,sans-serif;max-width:1500px;margin:auto;padding:28px}"
           "h1{font-size:2.1rem;line-height:1.2}h2{line-height:1.2}small{display:block}"
           "aside,article{border:1px solid;padding:16px;margin:14px 0;border-radius:8px}"
           ".tracks{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:24px}"
           "article h3{margin:0 0 8px;font-size:1.12rem}p{margin:8px 0}code{overflow-wrap:anywhere}"
           "table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid;text-align:left;"
           "padding:10px;vertical-align:top}.scroll{overflow:auto}a,td,p{overflow-wrap:anywhere}"
           "@media(max-width:950px){.tracks{grid-template-columns:1fr}body{padding:16px}}"
           "@media print{body{font-size:11px}.tracks{grid-template-columns:1fr}article{break-inside:avoid}}"
           "</style><header><p>1917–1991 · РАБОЧЕЕ ИССЛЕДОВАНИЕ</p>"
           "<h1>Советская власть: три параллельные хронологии</h1></header>",
           f"<aside><strong>{esc(DISCLAIMER)}</strong><p>{esc(data['scope'])}</p>"
           f"<p>{esc(data['method'])}</p><p>Срез данных: {esc(data['as_of'])}. "
           f"Версия: <code>{esc(revision)}</code>.</p><p>Записей: {result['records']}; "
           f"источников: {result['sources']}; открытых вопросов: {result['open_items']}.</p>"
           "<p>Исходная фотография хранится отдельно в закрытом Google Drive. "
           "В отчёт и артефакт она не включена.</p></aside>",
           "<h2>Одновременно занимавшие разные должности</h2><div class='scroll'><table>"
           "<tr><th>Дата</th><th>Партия</th><th>Правительство</th><th>Государственные органы</th></tr>"]
    for row in data["synchronized_examples"]:
        out.append("<tr>" + "".join(f"<td>{esc(row[k])}</td>" for k in ("date", "party", "government", "state")) + "</tr>")
    out.append("</table></div><p>Срезы взяты из исследовательского набора; CI не подтверждает их историческую истинность.</p><div class='tracks'>")
    for key, label in TRACKS.items():
        if key == "separate_records":
            out.append("</div>")
        out.append(f"<section><h2>{esc(label)}</h2>")
        for row in data[key]:
            refs = " · ".join(f"<a href='#source-{esc(s)}'>{esc(s)}</a>" for s in row["sources"])
            out.append(f"<article id='{esc(row['id'])}'><small>{esc(row['from'])} — {esc(row['to'])}</small>"
                       f"<h3>{esc(person_label(row))}</h3><p>{esc(row['role'])}</p>"
                       f"<small>{esc(row['status'])} · {refs}</small>")
            if row.get("note"):
                out.append(f"<p>{esc(row['note'])}</p>")
            out.append("</article>")
        out.append("</section>")
    out.append("<section><h2>Документальная проверка ещё требуется</h2><ul>")
    out.extend(f"<li>{esc(item)}</li>" for item in data["open_verification_items"])
    out.append("</ul></section><section><h2>Источники и границы проверки</h2>")
    for ident, s in sources.items():
        out.append(f"<p id='source-{esc(ident)}'><b>{esc(ident)}</b> · "
                   f"<a href='{esc(s['url'])}' rel='noreferrer'>{esc(s['title'])}</a>"
                   f"<small>{esc(s['note'])}</small></p>")
    out.append("</section></html>")
    return "\n".join(out)


def dump_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build(root: Path, out: Path, revision: str) -> dict:
    require(out.resolve() == (root / "dist").resolve(), "Output must be the repository dist directory")
    inputs = [root / DATA_PATH, root / SOURCE_PATH, root / "data/poster-transcription.tsv"]
    data = json.loads(inputs[0].read_text(encoding="utf-8"), object_pairs_hook=no_duplicate_keys)
    sources = source_index(inputs[1].read_text(encoding="utf-8"))
    result = validate(data, sources)
    validate_transcription(inputs[2])
    require(not any((root / "assets/original").glob("*.jpg")), "Do not include original JPEG in checkout")
    out.mkdir(exist_ok=True)
    result["revision"] = revision
    result["input_sha256"] = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    (out / "index.html").write_text(render(data, sources, result, revision), encoding="utf-8")
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
