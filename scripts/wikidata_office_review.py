#!/usr/bin/env python3
"""Compare Wikidata P39 with explicitly curated legal-office QIDs, read only.

An office match is a research candidate, NOT proof of historical correctness,
exact dates, legal continuity, or actual political control.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from scripts import wikidata_sync as wd

ROOT = Path(__file__).resolve().parents[1]
OFFICE_REGISTRY = "design/wikidata/office-crosswalk-v1.json"
ALLOWED_RELATIONS = {"exact_office", "office_family_only", "external_only"}


def world_context_ids(root: Path) -> set[str]:
    base = root / "data/atlas/world-pilots"
    return {
        "world:" + p["id"]
        for filename, key in (
            ("1762.json", "countries"),
            ("dynasty-1762-1780.json", "additional_polities"),
            ("extension-1781-1800.json", "additional_polities"),
        )
        for p in wd.read_json(base / filename)[key]
    }


def reviewed_offices(root: Path) -> dict[str, dict]:
    registry = wd.read_json(root / OFFICE_REGISTRY)
    if registry.get("schema_version") != "wikidata-office-crosswalk-v1":
        raise ValueError("Unknown Wikidata office crosswalk schema")
    canonical_offices = {o["id"] for o in wd.read_jsonl(root / "data/atlas/offices.jsonl")}
    contexts = {s["id"] for s in wd.read_jsonl(root / "data/atlas/states.jsonl")}
    contexts |= world_context_ids(root)
    result = {}
    for row in registry.get("mappings", []):
        qid = row.get("wikidata_qid")
        relation = row.get("relation")
        office = row.get("office_id")
        context_ids = row.get("context_ids")
        if (not isinstance(qid, str) or not wd.QID.fullmatch(qid) or
            qid in result or relation not in ALLOWED_RELATIONS or
            not isinstance(context_ids, list) or not context_ids or
            len(context_ids) != len(set(context_ids)) or
            not set(context_ids) <= contexts or
            not row.get("evidence_url") == "https://www.wikidata.org/wiki/" + qid or
            not row.get("note")):
            raise ValueError("Invalid, duplicate, or unverified office crosswalk row: " + str(qid))
        if relation == "external_only":
            if office is not None or any(not s.startswith("world:") for s in context_ids):
                raise ValueError("External offices cannot silently become canonical offices")
        elif office not in canonical_offices or any(s.startswith("world:") for s in context_ids):
            raise ValueError("Canonical office mapping must reference a known office/state")
        related = row.get("related_office_ids", [])
        if (not isinstance(related, list) or
            not set(related) <= canonical_offices or
            (related and relation != "office_family_only")):
            raise ValueError("Related offices only permitted for family-level review")
        result[qid] = row
    if not result:
        raise ValueError("No curated office mappings supplied")
    return result


def qualifier_comparison(qualifiers: dict, property_id: str,
                         canonical_date: dict) -> str:
    values = qualifiers.get(property_id, [])
    if not values:
        return "no_wikidata_boundary"
    if len(values) != 1:
        return "multiple_wikidata_boundaries_review"
    value = values[0]
    if value.get("snaktype") != "value" or not value.get("time"):
        return "unknown_or_non_date_boundary"
    return wd.calendar_comparison(value["time"], canonical_date)


def office_review(root: Path, reconciliation: dict) -> dict:
    """Use *only* explicit QIDs and existing tenure foreign keys."""
    if reconciliation.get("schema_version") != "wikidata-reconciliation-v1":
        raise ValueError("Unsupported input report version")
    if (reconciliation.get("historical_truth_verified") is not False or
            reconciliation.get("mutated_canonical_data") is not False):
        raise ValueError("Input must be a read-only, non-attesting Wikidata report")
    mapping = reviewed_offices(root)
    tenures = defaultdict(list)
    for row in wd.read_jsonl(root / "data/atlas/tenures.jsonl"):
        tenures[row["person_id"]].append(row)

    results, totals = [], Counter()
    seen = set()
    for subject in reconciliation["records"]:
        subject_id = subject["subject_id"]
        if subject_id in seen:
            raise ValueError("Duplicate Wikidata report subject: " + subject_id)
        seen.add(subject_id)
        if "wikidata" not in subject:
            continue
        qid = subject["wikidata_id"]
        if subject["wikidata"].get("qid") != qid:
            raise ValueError("Entity QID mismatch for " + subject_id)
        claims = []
        for statement in subject["wikidata"].get("statements", {}).get("position_held", []):
            totals["position_statements"] += 1
            pos = statement.get("value", {}).get("qid")
            rank = statement.get("rank", "normal")
            qualifiers = statement.get("qualifiers", {})
            if rank == "deprecated":
                decision = "deprecated_statement_not_used"
                totals["deprecated"] += 1
            elif not isinstance(pos, str) or not wd.QID.fullmatch(pos):
                decision = "no_valid_office_item"
                totals["unknown_or_no_value"] += 1
            elif pos not in mapping:
                decision = "unmapped_wikidata_office"
                totals["unmapped"] += 1
            else:
                relation = mapping[pos]["relation"]
                decision = relation
                totals[relation] += 1
            m = mapping.get(pos)
            candidates = []
            if (m and rank != "deprecated" and
                subject["kind"] == "canonical" and
                m["relation"] != "external_only"):
                allowed_offices = {m["office_id"], *m.get("related_office_ids", [])}
                for term in tenures.get(subject_id, []):
                    if (term["office_id"] not in allowed_offices or
                        not set(term["state_ids"]) & set(m["context_ids"])):
                        continue
                    candidates.append({
                        "canonical_tenure_id": term["id"],
                        "canonical_office_id": term["office_id"],
                        "canonical_context_ids": term["state_ids"],
                        "start_comparison": qualifier_comparison(
                            qualifiers, "P580", term["start"]),
                        "end_comparison": qualifier_comparison(
                            qualifiers, "P582", term["end"]),
                        "note": "Candidate only: validate reference, dates and legal role",
                    })
            if m and rank != "deprecated" and subject["kind"] == "canonical":
                if candidates and m["relation"] == "exact_office":
                    totals["exact_office_with_canonical_candidates"] += 1
                elif m["relation"] != "external_only" and not candidates:
                    totals["mapped_office_without_canonical_tenure"] += 1
            claims.append({
                "wikidata_statement_id": statement.get("statement_id"),
                "wikidata_office_qid": pos,
                "rank": rank,
                "decision": decision,
                "mapping": ({
                    "office_id": m["office_id"],
                    "context_ids": m["context_ids"],
                    "relation": m["relation"],
                    "note": m["note"],
                } if m else None),
                "candidate_canonical_tenures": candidates,
                "qualifiers": qualifiers,
                "references": statement.get("references", []),
            })
        totals["linked_subjects"] += 1
        results.append({"subject_id": subject_id, "subject_kind": subject["kind"],
                        "person_name": subject["name"], "wikidata_qid": qid,
                        "positions": claims})
    return {
        "schema_version": "wikidata-office-review-v1",
        "source_report_schema": reconciliation["schema_version"],
        "historical_truth_verified": False,
        "asserted_real_power": False,
        "mutated_canonical_data": False,
        "summary": dict(sorted(totals.items())),
        "subjects": results,
        "method": ("Only explicit P39 office QID crosswalks. Every canonical tenure "
                   "requires the same person ID, office and political context. "
                   "Dates keep original calendar/precision. Even exact_office "
                   "is a candidate, not evidence of power or full interval equality. "
                   "World-pilot people remain outside canonical v1."),
    }


def render_markdown(report: dict) -> str:
    counts = report["summary"]
    lines = ["# Wikidata P39 legal office review (experimental)", "",
             "No historical identity, tenure, actual-power assessment or SPA has "
             "been created or changed.", "",
             "## Counts", ""]
    for key, value in counts.items():
        lines.append("- " + key.replace("_", " ") + ": **" + str(value) + "**")
    lines += ["", "## Explicitly mapped offices and unresolved P39 statements", "",
              "| Subject | Position QID | Mapping decision | Canonical candidates |",
              "| --- | --- | --- | --- |"]
    for subject in report["subjects"]:
        name = str(subject["person_name"] or subject["subject_id"]).replace("|", "&#124;")
        for p in subject["positions"]:
            ids = ", ".join(c["canonical_tenure_id"]
                            for c in p["candidate_canonical_tenures"]) or "none"
            lines.append("| " + name + " | " + str(p["wikidata_office_qid"]) +
                         " | " + p["decision"] + " | " + ids + " |")
    lines += ["", "Unknown QIDs, term boundaries, deprecated claims and aliases "
              "require source review. P39 does not imply de-facto political power.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--input", type=Path, default=Path("reports/wikidata/latest.json"))
    parser.add_argument("--json-output", type=Path,
                        default=Path("reports/wikidata/offices.json"))
    parser.add_argument("--markdown-output", type=Path,
                        default=Path("reports/wikidata/offices.md"))
    args = parser.parse_args(argv)
    source = wd.read_json(args.input)
    report = office_review(args.root, source)
    for target, contents in (
        (args.json_output, json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"),
        (args.markdown_output, render_markdown(report)),
    ):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(contents, encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
