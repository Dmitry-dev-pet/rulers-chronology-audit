#!/usr/bin/env python3
"""Validated, source-qualified case studies of disputed transitions of power.

This research annotation layer augments the canonical atlas, but is NOT a new
tenure, person, governing institution, source-free claim or SQLite v1 table.
The first-party photo and private Drive URIs are never part of the export.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from scripts import atlas_db

ROOT = atlas_db.ROOT
SOURCE = Path("data/atlas/transition-cases.json")
CATEGORIES = {"legal", "practical", "claim", "institutional"}
VERIFICATIONS = {"reference_checked", "imported_not_rechecked", "disputed"}
CONFIDENCES = {"high", "medium", "low", "not_assessed"}


def load(root: Path = ROOT, db: dict | None = None) -> dict:
    """Verify the authored dossier and resolve public citations for the SPA."""
    root = Path(root)
    db = db if db is not None else atlas_db.load(root)
    data = atlas_db.read_json(root / SOURCE)
    require = atlas_db.require
    require(isinstance(data, dict), "Transition dossier must be an object")
    require(data.get("schema_version") == 1, "Unsupported transition-case version")
    require(data.get("historical_truth_verified_by_ci") is False,
            "Technical validation is not historical proof")
    require(isinstance(data.get("method"), str) and bool(data["method"].strip()),
            "Missing transition research method")
    cases = data.get("cases")
    require(isinstance(cases, list) and bool(cases), "No researched transition cases")
    source_index = {s["id"]: s for s in db["sources"]}
    actors = {p["id"] for p in db["people"]}
    bodies = {p["id"] for p in db["bodies"]}
    known_case_ids: set[str] = set()
    known_event_ids: set[str] = set()
    cited: set[str] = set()
    for case in cases:
        cid = case.get("id")
        require(isinstance(cid, str) and re.fullmatch(r"[a-z0-9-]+", cid)
                and cid not in known_case_ids, "Duplicate/invalid transition case")
        known_case_ids.add(cid)
        for field in ("title", "period", "lead", "caveat"):
            require(isinstance(case.get(field), str) and bool(case[field].strip()),
                    f"Empty {field} in {cid}")
        a, b, focus = (case.get(k) for k in ("start_year", "end_year", "focus_year"))
        require(all(type(x) is int for x in (a, b, focus))
                and 1417 <= a <= focus <= b <= 1991,
                f"Invalid visible-year window for {cid}")
        records = case.get("records")
        require(isinstance(records, list) and len(records) >= 4,
                f"Too few researched transition events for {cid}")
        last_date = ""
        found_categories: set[str] = set()
        for item in records:
            rid = item.get("id")
            require(isinstance(rid, str) and re.fullmatch(r"[a-z0-9-]+", rid)
                    and rid not in known_event_ids and rid.startswith(cid.split("-")[0] + "-"),
                    f"Invalid or duplicate transition event ID: {rid}")
            known_event_ids.add(rid)
            dt = item.get("date")
            atlas_db.validate_date(dt)
            # Preserve unknown old-calendar styles. Precise day means source
            # actually states that day; it is not manufactured from a year.
            year = int(dt["value"][:4])
            require(a <= year <= b, f"Transition date out of case range: {rid}")
            require(dt["value"] >= last_date, f"Events must be chronological: {rid}")
            last_date = dt["value"]
            require(item.get("category") in CATEGORIES, f"Unknown category: {rid}")
            found_categories.add(item["category"])
            for field in ("title", "actor", "summary", "caveat"):
                require(isinstance(item.get(field), str) and bool(item[field].strip()),
                        f"Empty {field}: {rid}")
            actor, body = item.get("person_id"), item.get("body_id")
            require(actor is None or actor in actors, f"Unknown person ID: {rid}")
            require(body is None or body in bodies, f"Unknown body ID: {rid}")
            require(not (actor and body), f"Ambiguous actor/body ID: {rid}")
            require(item.get("verification") in VERIFICATIONS,
                    f"Invalid verification status: {rid}")
            require(item.get("confidence") in CONFIDENCES,
                    f"Invalid confidence: {rid}")
            refs = item.get("sources")
            require(isinstance(refs, list) and bool(refs)
                    and len(refs) == len(set(refs)) and set(refs) <= source_index.keys(),
                    f"Unresolved citations for {rid}")
            cited.update(refs)
        require(found_categories == CATEGORIES,
                f"Transition case must distinguish legal, practical, claims, institutions: {cid}")
    if "smuta-1598-1613" in known_case_ids:
        smuta = next(c for c in cases if c["id"] == "smuta-1598-1613")
        require(smuta["start_year"] == 1598 and smuta["end_year"] == 1613,
                "Smuta coverage must not silently shrink")
    if "ussr-1991" in known_case_ids:
        ussr = next(c for c in cases if c["id"] == "ussr-1991")
        require(ussr["start_year"] == ussr["end_year"] == 1991,
                "1991 events belong to one year, but different exact dates")
    # Export only the public source URL/title needed for evidence links; this
    # layer does not duplicate or mutate the underlying canonical source index.
    resolved = [{
        "id": k,
        "title": source_index[k]["title"],
        "url": source_index[k]["url"],
        "verification": source_index[k]["verification"],
    } for k in sorted(cited)]
    out = {
        "schema_version": 1,
        "historical_truth_verified_by_ci": False,
        "method": data["method"],
        "cases": cases,
        "sources": resolved,
    }
    dump = json.dumps(out, ensure_ascii=False)
    require("1000428575.jpg" not in dump and "drive.google.com" not in dump,
            "Private source in transition export")
    return out


if __name__ == "__main__":
    print(json.dumps(load(), ensure_ascii=False, indent=2))
