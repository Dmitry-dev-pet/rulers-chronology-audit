#!/usr/bin/env python3
"""Read-only QID-level backlog for Wikidata P39 (source-reviewed, not power)."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "research/wikidata/p8-unmapped-qid-groups-2026-10-13.csv"
QUEUE = ROOT / "design/wikidata/p8-manual-review-queue-v1.json"
QID = re.compile(r"Q[1-9][0-9]*\Z")
COLUMNS = ("qid", "claims", "people", "with_references", "with_both_boundaries")


def baseline(path: Path = BASELINE) -> dict[str, dict]:
    """The fixed P7 grouping; not a dynamic list of proven historical offices."""
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if tuple(reader.fieldnames or []) != COLUMNS:
            raise ValueError("Unexpected P39 QID-group CSV schema")
        data = {}
        for row in reader:
            qid = row["qid"]
            if not QID.fullmatch(qid) or qid in data:
                raise ValueError("Duplicate or invalid exact office QID: " + str(qid))
            try:
                fields = {name: int(row[name]) for name in COLUMNS[1:]}
            except (TypeError, ValueError) as exc:
                raise ValueError("Invalid integer QID evidence counter") from exc
            if (fields["claims"] < 1 or fields["people"] < 1 or
                fields["people"] > fields["claims"] or
                any(fields[key] < 0 or fields[key] > fields["claims"]
                    for key in ("with_references", "with_both_boundaries"))):
                raise ValueError("Impossible frequency, person or evidence counts")
            data[qid] = fields
    if not data:
        raise ValueError("Empty historical P39 research sample")
    return data


def queue(path: Path = QUEUE, known: dict | None = None) -> dict[str, dict]:
    review = json.loads(path.read_text(encoding="utf-8"))
    if review.get("schema_version") != "wikidata-p39-manual-triage-v1":
        raise ValueError("Unknown manual review policy schema")
    out = {}
    for item in review.get("items", []):
        qid = item.get("qid")
        if (not isinstance(qid, str) or not QID.fullmatch(qid) or
            qid in out or (known is not None and qid not in known) or
            item.get("status") not in {"first", "quarantine", "later"} or
            not item.get("label") or not item.get("question") or
            item.get("source_url") != "https://www.wikidata.org/wiki/" + qid or
            any(x in item for x in ("office_id", "canon_id", "is_ruler", "power_score"))):
            raise ValueError("Review hint cannot approve unknown office or historical power")
        out[qid] = item
    return out


def from_live_reports(latest: dict, offices: dict, jurisdictions: dict) -> tuple[dict, int]:
    """Match P39 *statement IDs* in the same three read-only reports, never names."""
    schemas = ("wikidata-reconciliation-v1", "wikidata-office-review-v1",
               "wikidata-jurisdiction-review-v1")
    if tuple(x.get("schema_version") for x in
             (latest, offices, jurisdictions)) != schemas:
        raise ValueError("Cannot compare incompatible Wikidata reports")
    if any(x.get("historical_truth_verified") is not False or
           x.get("mutated_canonical_data") is not False
           for x in (latest, offices, jurisdictions)):
        raise ValueError("No attested/mutating external source inputs allowed")
    if (offices.get("asserted_real_power") is not False or
        jurisdictions.get("actual_power_inferred") is not False or
        jurisdictions.get("historical_borders_verified") is not False):
        raise ValueError("Not a historical-power classification report")
    p2 = {}
    for subject in offices.get("subjects", []):
        for pos in subject.get("positions", []):
            sid = pos.get("wikidata_statement_id")
            if not isinstance(sid, str) or not sid or sid in p2:
                raise ValueError("Duplicate P2 source statement ID")
            p2[sid] = (subject["subject_id"], subject["wikidata_qid"],
                       pos.get("wikidata_office_qid"), pos.get("rank"),
                       pos.get("qualifiers"), pos.get("references"),
                       pos.get("decision"))
    p3 = {}
    for subject in jurisdictions.get("subjects", []):
        for pos in subject.get("positions", []):
            sid = pos.get("wikidata_statement_id")
            if not isinstance(sid, str) or not sid or sid in p3:
                raise ValueError("Duplicate P3 source statement ID")
            p3[sid] = (subject["subject_id"], subject["wikidata_qid"],
                       pos.get("wikidata_office_qid"), pos.get("qualifiers"),
                       pos.get("references"))
    found, grouped, all_people = set(), defaultdict(list), set()
    for subject in latest.get("records", []):
        record = subject.get("wikidata")
        if not record:
            continue
        sid, who = subject["subject_id"], subject["wikidata_id"]
        if not QID.fullmatch(who) or record.get("qid") != who:
            raise ValueError("Unknown or changed person identity")
        for claim in record.get("statements", {}).get("position_held", []):
            stmt, qid, rank = claim.get("statement_id"), claim.get("value", {}).get("qid"), claim.get("rank")
            if stmt in found or stmt not in p2:
                raise ValueError("Missing/duplicate P2 statement ID")
            found.add(stmt)
            who2, p2person, posqid, p2rank, quals, refs, decision = p2[stmt]
            if (who2, p2person, posqid, p2rank, quals, refs) != (
                sid, who, qid, rank, claim.get("qualifiers", {}),
                claim.get("references", [])):
                raise ValueError("P2 office QID, statement, dates or references drift")
            if stmt in p3 and p3[stmt] != (
                sid, who, qid, claim.get("qualifiers", {}), claim.get("references", [])):
                raise ValueError("P3 office QID, statement, dates or references drift")
            if rank == "deprecated":
                if decision != "deprecated_statement_not_used" or stmt in p3:
                    raise ValueError("Deprecated source statement promoted")
                continue
            if rank not in ("normal", "preferred") or not isinstance(qid, str) or not QID.fullmatch(qid):
                raise ValueError("Unknown P39 rank or office ID needs separate manual review")
            if decision in ("exact_office", "external_only", "office_family_only"):
                if stmt in p3:
                    raise ValueError("P2 and P3 both classified same statement")
                continue
            if decision != "unmapped_wikidata_office":
                raise ValueError("Unknown P2 office decision")
            if stmt in p3:
                continue
            dates = claim.get("qualifiers", {})
            start, end = dates.get("P580", []), dates.get("P582", [])
            if not isinstance(start, list) or not isinstance(end, list):
                raise ValueError("Malformed external time qualifiers")
            grouped[qid].append((sid, bool(claim.get("references")),
                                 bool(start and end)))
            all_people.add(sid)
    if (found != set(p2) or len(p3) != jurisdictions["summary"]["typed_claims"] or
        sum(map(len, grouped.values())) != offices["summary"]["unmapped"] - len(p3) or
        len(found) != offices["summary"]["position_statements"]):
        raise ValueError("Source reports disagree on active, typed or residual P39 counts")
    result = {}
    for qid, entries in grouped.items():
        result[qid] = {
            "claims": len(entries), "people": len({p for p, _, _ in entries}),
            "with_references": sum(ref for _, ref, _ in entries),
            "with_both_boundaries": sum(both for _, _, both in entries),
        }
    return result, len(all_people)


def measures(groups: dict) -> dict:
    return {
        "distinct_qids":len(groups),
        "unclassified_claims":sum(x["claims"] for x in groups.values()),
        "qids_seen_once":sum(x["claims"] == 1 for x in groups.values()),
        "qids_seen_more_than_once":sum(x["claims"] > 1 for x in groups.values()),
        "statements_with_explicit_references":sum(x["with_references"] for x in groups.values()),
        "statements_with_both_date_qualifiers":sum(x["with_both_boundaries"] for x in groups.values()),
        "frequencies":dict(sorted(Counter(x["claims"] for x in groups.values()).items())),
        "historical_truth_verified": False, "effective_power_inferred": False,
    }


def compare(actual: dict, expected: dict) -> dict:
    return {
        "added_qids":sorted(set(actual)-set(expected)),
        "removed_qids":sorted(set(expected)-set(actual)),
        "changed_qids":sorted(q for q in set(actual)&set(expected)
                              if actual[q] != expected[q]),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline", type=Path, default=BASELINE)
    p.add_argument("--queue", type=Path, default=QUEUE)
    p.add_argument("--latest", type=Path)
    p.add_argument("--offices", type=Path)
    p.add_argument("--jurisdictions", type=Path)
    args = p.parse_args(argv)
    frozen = baseline(args.baseline)
    proposed = queue(args.queue, frozen)
    triple = (args.latest, args.offices, args.jurisdictions)
    results = {"frozen": measures(frozen),
               "priority_qids":sorted(q for q,v in proposed.items() if v["status"]=="first"),
               "quarantined_qids":sorted(q for q,v in proposed.items() if v["status"]=="quarantine")}
    if any(triple):
        if not all(triple):
            p.error("--latest, --offices and --jurisdictions must be supplied together")
        actual, distinct_people = from_live_reports(
            *(json.loads(path.read_text(encoding="utf-8")) for path in triple))
        results["live"] = measures(actual)
        results["distinct_people_with_unclassified_p39"] = distinct_people
        results["compared_to_frozen"] = compare(actual, frozen)
    print(json.dumps(results, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
