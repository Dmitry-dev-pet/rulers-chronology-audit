#!/usr/bin/env python3
"""Read-only Wikidata reconciliation for the historical atlas.

Never edits canonical data, SQLite, poster transcription, or GitHub Pages.
Names and searches are candidates only. Python 3.11+ standard library.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
API = "https://www.wikidata.org/w/api.php"
USER_AGENT = ("RulersChronologyAudit-Wikidata/0.1 "
              "(https://github.com/Dmitry-dev-pet/rulers-chronology-audit; "
              "public historical research)")
QID = re.compile(r"Q[1-9][0-9]*\Z")
WIKIDATA_TIME = re.compile(r"^([+-])([0-9]+)-([0-9]{2})-([0-9]{2})T")
CALENDARS = {
    "http://www.wikidata.org/entity/Q1985727": "gregorian",
    "http://www.wikidata.org/entity/Q1985786": "julian",
}
PROPERTIES = {
    "P569": "birth", "P570": "death", "P39": "position_held",
    "P19": "birthplace", "P27": "citizenship", "P53": "family",
    "P22": "father", "P25": "mother", "P26": "spouse",
}
QUALIFIERS = ("P580", "P582", "P1365", "P1366")
WORLD_FILES = (
    ("1762.json", "persons"),
    ("dynasty-1762-1780.json", "additional_persons"),
    ("extension-1781-1800.json", "additional_persons"),
)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines()
            if line.strip()]


def roster(root: Path) -> list[dict]:
    """Canonical people plus world-only IDs; never join by name."""
    atlas = root / "data" / "atlas"
    people = [read_json(p) for p in sorted((atlas / "people").glob("*.json"))]
    if not people:
        raise ValueError("No canonical people; refusing empty synchronization")
    ids, qids, subjects = set(), set(), []
    for p in people:
        person_id = p["id"]
        if person_id in ids:
            raise ValueError("Duplicate canonical person ID: " + person_id)
        ids.add(person_id)
        qid = p.get("external_ids", {}).get("wikidata")
        if qid is not None:
            if not isinstance(qid, str) or not QID.fullmatch(qid):
                raise ValueError("Invalid confirmed QID for " + person_id)
            if qid in qids:
                raise ValueError("QID linked to multiple people: " + qid)
            qids.add(qid)
        subjects.append({"subject_id": person_id, "kind": "canonical",
                         "name": p["name"], "wikidata_id": qid})
    world = {}
    for filename, key in WORLD_FILES:
        doc = read_json(atlas / "world-pilots" / filename)
        for p in doc[key]:
            native = p["id"]
            canonical = p.get("canonical_person_id")
            if canonical:
                if canonical not in ids:
                    raise ValueError("Unknown canonical person referenced by " + native)
                continue
            name = p.get("name")
            if native in world:
                if name and world[native]["name"] and world[native]["name"] != name:
                    raise ValueError("Conflicting world-person names for " + native)
                continue
            world[native] = {"subject_id": "world:" + native,
                             "kind": "world_unlinked", "name": name,
                             "wikidata_id": None}
    # P2: independent world identities may have reviewed QIDs, but never
    # canonical_person_id. The reviewed registry is distinct from name-search
    # candidates and never mutates source pilot JSON.
    registry = root / "design/wikidata/reviewed-world-links-v1.json"
    if registry.exists():
        entries = read_json(registry)
        if entries.get("schema_version") != "wikidata-reviewed-world-links-v1":
            raise ValueError("Unknown world identity registry schema")
        seen_world = set()
        for item in entries.get("links", []):
            native = item.get("world_id")
            qid = item.get("wikidata_qid")
            if (native not in world or native in seen_world or
                    not isinstance(qid, str) or not QID.fullmatch(qid) or
                    qid in qids or item.get("verification") != "identity_reviewed" or
                    not isinstance(item.get("evidence"), list) or
                    len(item["evidence"]) < 2):
                raise ValueError("Invalid/duplicate reviewed world identity: " + str(native))
            seen_world.add(native)
            qids.add(qid)
            world[native]["wikidata_id"] = qid
        seen_rejections = set()
        for item in entries.get("rejected_candidates", []):
            native = item.get("world_id")
            qid = item.get("wikidata_qid")
            if (native not in world or not isinstance(qid, str) or
                    not QID.fullmatch(qid) or
                    (native, qid) in seen_rejections or
                    not item.get("reason") or world[native]["wikidata_id"] == qid):
                raise ValueError("Contradictory world QID exclusion: " + str(native))
            seen_rejections.add((native, qid))
    subjects.extend(world.values())
    return sorted(subjects, key=lambda s: (s["kind"] != "canonical",
                                            (s["name"] or "").casefold(),
                                            s["subject_id"]))


def http_api(params: dict, *, attempts: int = 4) -> dict:
    """Serial Action API requests with Wikimedia attribution and 429 backoff."""
    url = API + "?" + urlencode({"format": "json", "formatversion": 2, **params})
    req = Request(url, headers={"User-Agent": USER_AGENT,
                                "Accept": "application/json",
                                "Accept-Encoding": "identity"})
    for attempt in range(attempts):
        try:
            with urlopen(req, timeout=35) as response:
                body = response.read(12_000_001)
                if len(body) > 12_000_000:
                    raise RuntimeError("Wikidata response too large")
                result = json.loads(body.decode("utf-8"))
                if not isinstance(result, dict) or "error" in result:
                    raise RuntimeError("Wikidata API error: " + str(result))
                return result
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == attempts - 1:
                raise
            try:
                delay = min(60, max(1, int(exc.headers.get("Retry-After", ""))))
            except ValueError:
                delay = min(30, 2 ** attempt)
            time.sleep(delay)
        except (URLError, TimeoutError):
            if attempt == attempts - 1:
                raise
            time.sleep(min(30, 2 ** attempt))
    raise RuntimeError("Unreachable retry state")


def time_value(snak: dict) -> dict | None:
    if snak.get("snaktype") != "value":
        return None
    value = snak.get("datavalue", {}).get("value")
    if not isinstance(value, dict) or "time" not in value:
        return None
    cal = value.get("calendarmodel")
    return {"time": value["time"], "precision": value.get("precision"),
            "calendar": CALENDARS.get(cal, "other_or_unspecified"),
            "calendarmodel": cal, "before": value.get("before"),
            "after": value.get("after"), "timezone": value.get("timezone")}


def snak_value(snak: dict) -> dict:
    result = {"snaktype": snak.get("snaktype", "unknown")}
    if result["snaktype"] != "value":
        return result
    dv = snak.get("datavalue", {})
    value = dv.get("value")
    if dv.get("type") == "time":
        result["time"] = time_value(snak)
    elif dv.get("type") == "wikibase-entityid" and isinstance(value, dict):
        result["qid"] = value.get("id")
    elif dv.get("type") == "string" and isinstance(value, str):
        result["text"] = value
    else:
        result["datatype"] = dv.get("type", "unsupported")
    return result


def references(claim: dict) -> list[dict]:
    output = []
    for ref in claim.get("references", []):
        snaks = ref.get("snaks", {})
        output.append({
            "hash": ref.get("hash"),
            "stated_in": [v["qid"] for s in snaks.get("P248", [])
                          if (v := snak_value(s)).get("qid")],
            "urls": [v["text"] for s in snaks.get("P854", [])
                     if (v := snak_value(s)).get("text", "").startswith(("https://", "http://"))],
            "retrieved": [v["time"] for s in snaks.get("P813", [])
                          if (v := snak_value(s)).get("time")],
        })
    return output


def normalize_claim(claim: dict, property_id: str) -> dict:
    qualifiers = claim.get("qualifiers", {})
    return {"statement_id": claim.get("id"),
            "property_id": property_id, "rank": claim.get("rank", "normal"),
            "value": snak_value(claim.get("mainsnak", {})),
            "qualifiers": {key: [snak_value(v) for v in qualifiers[key]]
                           for key in QUALIFIERS if key in qualifiers},
            "references": references(claim)}


def normalize_entity(entity: dict) -> dict:
    labels, descriptions, claims = (entity.get(k, {}) for k in
                                    ("labels", "descriptions", "claims"))
    return {"qid": entity["id"], "lastrevid": entity.get("lastrevid"),
            "labels": {k: labels[k]["value"] for k in ("ru", "en") if k in labels},
            "descriptions": {k: descriptions[k]["value"] for k in ("ru", "en")
                             if k in descriptions},
            "statements": {name: [normalize_claim(c, prop) for c in claims.get(prop, [])]
                           for prop, name in PROPERTIES.items() if claims.get(prop)},
            "historical_truth_verified": False}


def calendar_comparison(wikidata_date: dict, canonical_date: dict) -> str:
    """Never convert Julian/Gregorian dates or turn a year into an exact day."""
    match = WIKIDATA_TIME.match(wikidata_date.get("time", ""))
    local = canonical_date.get("value", "")
    if not match or match.group(1) != "+" or not isinstance(local, str):
        return "needs_review"
    year, month, day = match.group(2), match.group(3), match.group(4)
    if len(year) != 4:
        return "needs_review"
    cal = wikidata_date.get("calendar")
    if cal not in ("julian", "gregorian") or canonical_date.get("calendar") != cal:
        return "calendar_review"
    wp, cp = wikidata_date.get("precision"), canonical_date.get("precision")
    by_precision = {9: year, 10: f"{year}-{month}", 11: f"{year}-{month}-{day}"}
    if wp not in by_precision or cp not in ("year", "month", "day"):
        return "needs_review"
    norm = by_precision[wp]
    if local == norm and {"year": 9, "month": 10, "day": 11}[cp] == wp:
        return "same_recorded_date"
    if local.startswith(norm) or norm.startswith(local):
        return "compatible_lower_precision"
    return "date_disagreement_candidate"


def compare_dates(statements: list[dict], facts: list[dict]) -> dict:
    active = [s for s in statements if s["rank"] != "deprecated"
              and s["value"].get("time")]
    if not active:
        return {"status": "wikidata_date_missing", "claims": []}
    reviews = []
    for statement in active:
        wd = statement["value"]["time"]
        checks = [{"canonical_fact_id": fact["id"],
                   "result": calendar_comparison(wd, fact["value"])}
                  for fact in facts if isinstance(fact.get("value"), dict)]
        reviews.append({"statement_id": statement["statement_id"],
                        "rank": statement["rank"], "checks": checks,
                        "status": "needs_source_research" if not checks else
                                  "same_recorded_date" if any(
                                      c["result"] == "same_recorded_date" for c in checks)
                                  else "requires_review"})
    return {"status": "no_canonical_fact" if not facts else
                      "review_multiple_wikidata_claims" if len(active) > 1 else
                      reviews[0]["status"],
            "claims": reviews, "canonical_fact_ids": [f["id"] for f in facts]}


def load_facts(root: Path) -> dict:
    facts = defaultdict(lambda: {"birth": [], "death": []})
    for item in read_jsonl(root / "data/atlas/person_facts.jsonl"):
        if item["kind"] in ("birth", "death"):
            facts[item["person_id"]][item["kind"]].append(item)
    return facts


def search_candidates(api, name: str, limit: int = 5) -> list[dict]:
    response = api({"action": "wbsearchentities", "search": name, "language": "ru",
                    "type": "item", "limit": limit})
    return [{"qid": row["id"], "label": row.get("label"),
             "description": row.get("description")}
            for row in response.get("search", [])
            if QID.fullmatch(row.get("id", ""))]


def run(root: Path = ROOT, *, api=http_api, discover: bool = False,
        max_searches: int = 107, request_delay: float = 0.4) -> dict:
    subjects, facts = roster(root), load_facts(root)
    confirmed = {s["wikidata_id"]: s for s in subjects if s["wikidata_id"]}
    entities, keys = {}, sorted(confirmed, key=lambda q: int(q[1:]))
    for offset in range(0, len(keys), 40):
        batch = keys[offset:offset + 40]
        result = api({"action": "wbgetentities", "ids": "|".join(batch),
                      "props": "labels|descriptions|claims|info", "languages": "ru|en"})
        for qid in batch:
            entity = result.get("entities", {}).get(qid)
            if not entity or "missing" in entity or entity.get("id") != qid:
                raise ValueError("Missing/redirected QID needs review: " + qid)
            entities[qid] = normalize_entity(entity)
        if request_delay and offset + 40 < len(keys):
            time.sleep(request_delay)
    records, searches = [], 0
    for s in subjects:
        person = dict(s)
        qid = s["wikidata_id"]
        if qid:
            person["status"] = ("confirmed_link_external_data_only" if
                                s["kind"] == "canonical" else
                                "reviewed_world_qid_no_canonical_merge")
            person["wikidata"] = entities[qid]
            if s["kind"] == "canonical":
                person["date_review"] = {
                    kind: compare_dates(entities[qid]["statements"].get(kind, []),
                                        facts[s["subject_id"]][kind])
                    for kind in ("birth", "death")}
        elif discover and s["name"] and searches < max_searches:
            person["status"] = "candidate_search_unverified"
            person["candidates"] = search_candidates(api, s["name"])
            searches += 1
            if request_delay:
                time.sleep(request_delay)
        else:
            person["status"] = "not_searched"
        records.append(person)
    statuses = Counter(p["status"] for p in records)
    return {"schema_version": "wikidata-reconciliation-v1",
            "source": "Wikidata Action API", "historical_truth_verified": False,
            "auto_merge_names": False, "mutated_canonical_data": False,
            "summary": {"canonical_people": sum(s["kind"] == "canonical" for s in subjects),
                        "unlinked_world_people": sum(s["kind"] == "world_unlinked"
                                                     for s in subjects),
                        "confirmed_qids": len(keys),
                        "confirmed_canonical_qids": sum(
                            s["kind"] == "canonical" and bool(s["wikidata_id"])
                            for s in subjects),
                        "reviewed_world_qids": sum(
                            s["kind"] == "world_unlinked" and bool(s["wikidata_id"])
                            for s in subjects),
                        "candidate_searches": searches,
                        "statuses": dict(sorted(statuses.items()))},
            "records": records,
            "policy": ("Names are search candidates, never identity joins. Rank, "
                       "calendar precision, qualifiers, sources remain external. "
                       "No automatically canonical dates, ethnicity, office terms "
                       "or de-facto power.")}


def render_markdown(report: dict) -> str:
    s = report["summary"]
    lines = ["# Wikidata reconciliation — review only", "",
             "External assertions are not verified historical truth.",
             "No canonical date, real-power assessment, or identity was changed.", "",
             f"- Canonical people: **{s['canonical_people']}**",
             f"- Unlinked world-pilot people: **{s['unlinked_world_people']}**",
             f"- Confirmed QIDs read: **{s['confirmed_qids']}**",
             f"- Unverified name searches: **{s['candidate_searches']}**", "",
             "## Reviewed identity references (not historical fact import)", "",
             "| Subject | Kind | Wikidata | Birth review | Death review |",
             "| --- | --- | --- | --- | --- |"]
    for p in report["records"]:
        if "wikidata" not in p:
            continue
        qid = p["wikidata_id"]
        clean = str(p["name"]).replace("|", "&#124;").replace("[", "&#91;")
        reviews = p.get("date_review", {})
        lines.append(f"| {clean} | {p['kind']} | [{qid}](https://www.wikidata.org/wiki/{qid})"
                     f" | {reviews.get('birth', {}).get('status', 'not_in_canonical')}"
                     f" | {reviews.get('death', {}).get('status', 'not_in_canonical')} |")
    lines.extend(["", "## Discovery queue — candidates are NOT linked", "",
                  "| Subject | Unverified candidate QIDs |", "| --- | --- |"])
    for p in report["records"]:
        if p["status"] != "candidate_search_unverified":
            continue
        clean = str(p["name"]).replace("|", "&#124;").replace("[", "&#91;")
        candidates = ", ".join(c["qid"] for c in p["candidates"]) or "none"
        lines.append(f"| {p['subject_id']} · {clean} | {candidates} |")
    lines.extend(["", "## Review rules", "",
                  "JSON preserves statement IDs, ranks (including deprecated), "
                  "date/calendar precision, qualifiers, and reference pointers.",
                  "Different calendars are never silently reconciled. P39 does not "
                  "prove factual political control. Ethnicity is not imported.",
                  "This report is not published as canonical SQLite or SPA facts.", ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--discover", action="store_true",
                        help="Discover unverified QID candidates (never link automatically)")
    parser.add_argument("--max-searches", type=int, default=107)
    parser.add_argument("--request-delay", type=float, default=0.4)
    parser.add_argument("--json-output", type=Path,
                        default=Path("reports/wikidata/latest.json"))
    parser.add_argument("--markdown-output", type=Path,
                        default=Path("reports/wikidata/latest.md"))
    args = parser.parse_args(argv)
    if not 0 <= args.max_searches <= 1000 or not 0 <= args.request_delay <= 10:
        parser.error("Invalid request limits")
    report = run(args.root, discover=args.discover,
                 max_searches=args.max_searches, request_delay=args.request_delay)
    for target, contents in (
        (args.json_output, json.dumps(report, ensure_ascii=False, sort_keys=True,
                                      indent=2) + "\n"),
        (args.markdown_output, render_markdown(report)),
    ):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(contents, encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
