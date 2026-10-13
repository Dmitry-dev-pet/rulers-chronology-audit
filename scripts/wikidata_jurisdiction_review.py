#!/usr/bin/env python3
"""Read-only, source-scoped Wikidata P39 jurisdiction review.

Classifies separately typed historical office contexts. Does not migrate
canonical people, tenures, sovereignty, territories, institutions or dates.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from scripts import wikidata_office_review as offices
from scripts import wikidata_sync as wd

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = "design/wikidata/jurisdiction-crosswalk-v1.json"

CONTEXT_KINDS = {
    "elective_institution", "historic_crown", "joint_sovereignty",
    "political_party_institution", "legislative_institution",
    "executive_institution", "existing_pilot_polity", "composite_crown", "post_pilot_polity",
}
POSITION_KINDS = {
    "electoral_dignity", "legal_crown", "co_head_of_state",
    "institutional_membership", "party_candidate_membership",
    "legislative_membership", "government_deputy", "government_first_deputy",
    "legal_monarchical_office", "compound_royal_office", "post_pilot_imperial_title",
}
TIME = re.compile(r"^\+([0-9]{4})-[0-9]{2}-[0-9]{2}T")


def registry(root: Path) -> tuple[dict[str, dict], dict[str, dict], tuple[int, int]]:
    doc = wd.read_json(root / REGISTRY)
    if doc.get("schema_version") != "wikidata-jurisdiction-crosswalk-v1":
        raise ValueError("Unsupported jurisdiction registry schema")
    window = doc.get("pilot_window", {})
    lo, hi = window.get("start_year"), window.get("end_year")
    if not isinstance(lo, int) or not isinstance(hi, int) or lo < 1 or hi < lo:
        raise ValueError("Invalid year-only pilot window")
    world_refs = offices.world_context_ids(root)
    contexts = {}
    for row in doc.get("contexts", []):
        k = row.get("id")
        refs = row.get("related_world_contexts")
        if (
            not isinstance(k, str) or not k or k in contexts or
            row.get("kind") not in CONTEXT_KINDS or
            not isinstance(row.get("label"), str) or not row["label"] or
            not isinstance(row.get("caveat"), str) or not row["caveat"] or
            not isinstance(refs, list) or len(refs) != len(set(refs)) or
            not set(refs) <= world_refs or
            row.get("same_as_canonical_state") is not False or
            row.get("geographic_boundaries_verified") is not False or
            row.get("relationship") != "related_not_equivalent" or
            (k.startswith("world:") and
             (k not in world_refs or row["kind"] != "existing_pilot_polity")) or
            (not k.startswith("world:") and row["kind"] == "existing_pilot_polity")
        ):
            raise ValueError("Invalid/merging historical jurisdiction: " + str(k))
        if row["kind"] == "executive_institution":
            years = row.get("title_year_window")
            if (row.get("government_tier") != "union" or
                row.get("office_era") not in {"pre_1946_snk", "post_1946_sovmin"} or
                not isinstance(years, dict) or
                not all(isinstance(years.get(n), int) for n in ("start", "end")) or
                (years["start"], years["end"]) not in {(1923, 1946), (1946, 1991)} or
                row["office_era"] != ("pre_1946_snk" if years["start"] == 1923
                                       else "post_1946_sovmin") or
                row.get("legal_title_transition_date") != "1946-03-15" or
                not isinstance(row.get("transition_source_url"), str) or
                not row["transition_source_url"].startswith("https://docs.historyrussia.org/")):
                raise ValueError("Unreviewed government office era or transition law")
        contexts[k] = row
    old_offices = offices.reviewed_offices(root)
    by_qid = {}
    for row in doc.get("offices", []):
        qid = row.get("wikidata_qid")
        cid = row.get("context_id")
        if (
            not isinstance(qid, str) or not wd.QID.fullmatch(qid) or
            qid in by_qid or qid in old_offices or
            cid not in contexts or row.get("position_kind") not in POSITION_KINDS or
            row.get("review_status") != "scope_reviewed_not_tenure" or
            row.get("evidence_url") != "https://www.wikidata.org/wiki/" + qid or
            not isinstance(row.get("caveat"), str) or not row["caveat"]
        ):
            raise ValueError("Invalid/overlapping jurisdiction office: " + str(qid))
        if row["position_kind"] in {"institutional_membership", "party_candidate_membership"} and contexts[cid]["kind"] != "political_party_institution":
            raise ValueError("Party membership must have a political-party institutional context")
        if row["position_kind"] == "legislative_membership" and contexts[cid]["kind"] != "legislative_institution":
            raise ValueError("Legislative membership must have a legislative institutional context")
        if row["position_kind"] in {"government_deputy", "government_first_deputy"}:
            needed = "first_deputy" if row["position_kind"] == "government_first_deputy" else "deputy"
            if (contexts[cid]["kind"] != "executive_institution" or
                row.get("office_era") != contexts[cid].get("office_era") or
                row.get("office_rank") != needed):
                raise ValueError("Wrong Soviet executive title era, office rank or jurisdiction")
        if row["position_kind"] == "electoral_dignity" and contexts[cid]["kind"] != "elective_institution":
            raise ValueError("Electoral dignity must have an elective context")
        if row["position_kind"] == "co_head_of_state" and contexts[cid]["kind"] != "joint_sovereignty":
            raise ValueError("Co-head office must have joint-sovereignty context")
        if row["position_kind"] == "post_pilot_imperial_title" and contexts[cid]["kind"] != "post_pilot_polity":
            raise ValueError("Post-pilot title must not be the republican pilot context")
        by_qid[qid] = row
    if not contexts or not by_qid:
        raise ValueError("Empty historical jurisdiction crosswalk")
    return contexts, by_qid, (lo, hi)


def boundary_year(qualifiers: dict, kind: str) -> int | None:
    values = qualifiers.get(kind, [])
    if len(values) != 1:
        return None
    stamp = values[0].get("time")
    if (not isinstance(stamp, dict) or not isinstance(stamp.get("precision"), int)
            or stamp["precision"] < 9):
        return None
    matched = TIME.match(stamp.get("time", ""))
    return int(matched.group(1)) if matched else None


def window_review(claim: dict, window: tuple[int, int]) -> str:
    """Year filtering NEVER proves simultaneous holding on a particular day."""
    q = claim.get("qualifiers", {})
    start, end = boundary_year(q, "P580"), boundary_year(q, "P582")
    lo, hi = window
    if start is not None and end is not None and start > end:
        return "inconsistent_source_boundaries"
    if start is not None and start > hi:
        return "after_world_pilot_window"
    if end is not None and end < lo:
        return "before_world_pilot_window"
    if start is None or end is None:
        return "incomplete_year_bounds_not_an_absence"
    return "year_overlap_candidate_not_day_verified"


def review(root: Path, source: dict) -> dict:
    if (
        source.get("schema_version") != "wikidata-reconciliation-v1" or
        source.get("mutated_canonical_data") is not False or
        source.get("historical_truth_verified") is not False
    ):
        raise ValueError("Refuse input that is not read-only Wikidata reconciliation")
    contexts, registry_offices, window = registry(root)
    canonical = {s["subject_id"]: s for s in wd.roster(root)}
    seen = set()
    rows = []
    counts = Counter()
    multi_scope = []
    for subject in source.get("records", []):
        sid = subject.get("subject_id")
        if sid in seen:
            raise ValueError("Duplicate subject in external report: " + str(sid))
        seen.add(sid)
        if sid not in canonical or subject.get("kind") != canonical[sid]["kind"] or subject.get("wikidata_id") != canonical[sid]["wikidata_id"]:
            raise ValueError("Report contains unknown or unreviewed identity: " + str(sid))
        if "wikidata" not in subject:
            continue
        if subject["wikidata"].get("qid") != subject["wikidata_id"]:
            raise ValueError("Wikidata QID mismatch: " + str(sid))
        subjects_positions = []
        distinct = set()
        for claim in subject["wikidata"].get("statements", {}).get("position_held", []):
            counts["all_position_claims"] += 1
            if claim.get("rank") == "deprecated":
                counts["deprecated_skipped"] += 1
                continue
            qid = claim.get("value", {}).get("qid")
            if qid not in registry_offices:
                counts["not_in_jurisdiction_overlay"] += 1
                continue
            definition = registry_offices[qid]
            cid = definition["context_id"]
            distinct.add(cid)
            classification = definition["position_kind"]
            disposition = window_review(claim, window)
            counts["typed_claims"] += 1
            counts["role_" + classification] += 1
            counts["window_" + disposition] += 1
            subjects_positions.append({
                "wikidata_statement_id": claim.get("statement_id"),
                "wikidata_office_qid": qid, "jurisdiction_context_id": cid,
                "jurisdiction_context_kind": contexts[cid]["kind"],
                "legal_role_classification": classification,
                "office_rank": definition.get("office_rank"),
                "government_title_era": contexts[cid].get("office_era"),
                "pilot_window_relation": disposition,
                "qualifiers": claim.get("qualifiers", {}),
                "references": claim.get("references", []),
                "role_caveat": definition["caveat"],
                "context_caveat": contexts[cid]["caveat"],
                "actual_power_verified": False,
                "historical_borders_verified": False,
            })
        if len(distinct) > 1:
            multi_scope.append({
                "subject_id": sid, "context_ids": sorted(distinct),
                "explanation": ("Different offices of the same person are NOT"
                                " evidence of simultaneous rule, territorial union"
                                " or control at day precision."),
            })
        if subjects_positions:
            rows.append({"subject_id": sid, "kind": subject["kind"],
                         "name": subject["name"], "wikidata_qid": subject["wikidata_id"],
                         "positions": subjects_positions})
    counts["subjects_with_typed_roles"] = len(rows)
    counts["multi_context_subjects_to_review"] = len(multi_scope)
    return {
        "schema_version": "wikidata-jurisdiction-review-v1",
        "historical_truth_verified": False,
        "historical_borders_verified": False,
        "actual_power_inferred": False,
        "mutated_canonical_data": False,
        "pilot_window": {"start_year": window[0], "end_year": window[1]},
        "contexts": list(contexts.values()),
        "summary": dict(sorted(counts.items())),
        "subjects": rows,
        "multi_context_candidates": multi_scope,
        "warning": "A claim about an office never proves uninterrupted personal rule or a sovereign country. Dates are only year-overlap candidates, not day-level co-rulership. Not a world-completeness claim.",
    }


def render_markdown(report: dict) -> str:
    lines = ["# Wikidata P3: juridical contexts, separate from power and borders", "",
             "**Read-only candidate classification; no canonical ruler rows created.**", "",
             "## Summary", ""]
    for key, count in report["summary"].items():
        lines.append(f"- {key.replace('_', ' ')}: **{count}**")
    lines += ["", "## Typed P39 claims", "",
              "| Person | Wikidata position | Context | Classification | Pilot window |",
              "| --- | --- | --- | --- | --- |"]
    for person in report["subjects"]:
        name = str(person["name"] or person["subject_id"]).replace("|", "&#124;")
        for p in person["positions"]:
            lines.append(f"| {name} | {p['wikidata_office_qid']} | "
                         f"{p['jurisdiction_context_id']} | {p['legal_role_classification']} | "
                         f"{p['pilot_window_relation']} |")
    lines += ["", "## Multi-context persons requiring independent study", "",
              "Different scopes belonging to one person do not automatically establish personal union.",
              ""]
    for item in report["multi_context_candidates"]:
        lines.append("- " + item["subject_id"] + ": " + ", ".join(item["context_ids"]))
    lines += ["", "No modern nationalities, polygons, actual political influence,"
              " sovereignty scores, new historical reigns or independent source verification inferred.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--input", type=Path, default=Path("reports/wikidata/latest.json"))
    p.add_argument("--json-output", type=Path,
                   default=Path("reports/wikidata/jurisdictions.json"))
    p.add_argument("--markdown-output", type=Path,
                   default=Path("reports/wikidata/jurisdictions.md"))
    args = p.parse_args(argv)
    result = review(args.root, wd.read_json(args.input))
    for filename, text in (
        (args.json_output, json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"),
        (args.markdown_output, render_markdown(result)),
    ):
        filename.parent.mkdir(parents=True, exist_ok=True)
        filename.write_text(text, encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
