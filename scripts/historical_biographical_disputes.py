#!/usr/bin/env python3
"""Read-only biography adapter to the historical disagreement registry.

It pins existing canonical person-fact rows and source-registry entries by
stable IDs, without copying them into canon, changing age, or deciding truth.
"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

from scripts import historical_disputes as h

ROOT = h.ROOT
REGISTRY = Path("research/contradictions/biography-v1.json")
FACTS = "data/atlas/person_facts.jsonl"
SOURCES = "data/atlas/sources.jsonl"
CASE_KEYS = {
    "id", "kind", "review_status", "person_id", "person_name", "field",
    "canonical_fact_ids", "comparison_relation", "question", "resolution",
    "reviewed_primary_acts", "actual_power_inferred",
    "historical_truth_verified_by_ci", "observations",
}
OBS_KEYS = {
    "id", "canonical_fact_id", "source_id", "source_kind",
    "source_url", "corroborating_url", "source_locator", "claim_type",
    "verification", "independent_primary_checked", "value",
    "pinned_canonical_fact", "pinned_source_record", "note",
}
SOURCE_KINDS = {"archival_register_description", "historical_biography"}


def index_unique(rows: list[dict], kind: str) -> dict[str, dict]:
    result = {}
    for row in rows:
        key = row.get("id")
        if not isinstance(key, str) or not key or key in result:
            raise ValueError("Duplicate/invalid " + kind + " ID")
        result[key] = row
    return result


def validate_resolution(case: dict) -> None:
    status = case["review_status"]
    outcome = case["resolution"]
    if status not in {"open", "in_review", "resolved"}:
        raise ValueError("Unknown biographical review status")
    if status != "resolved":
        if outcome is not None:
            raise ValueError("Unresolved birth dates cannot carry an automatic resolution")
        return
    if (not isinstance(outcome, dict) or
        set(outcome) != {"reviewer", "reason", "evidence_urls"} or
        not isinstance(outcome["reviewer"], str) or not outcome["reviewer"].strip()
        or not isinstance(outcome["reason"], str) or not outcome["reason"].strip()
        or not isinstance(outcome["evidence_urls"], list) or
        len(outcome["evidence_urls"]) < 2 or
        len(set(outcome["evidence_urls"])) != len(outcome["evidence_urls"]) or
        not all(h.safe_url(url) for url in outcome["evidence_urls"])):
        raise ValueError("A manual biographical resolution needs a reviewer and two distinct public sources")


def registry(root: Path = ROOT) -> dict:
    document = h.load_json(root / REGISTRY)
    if (document.get("schema_version") != "historical-biographical-dispute-registry-v1"
        or document.get("historical_truth_verified_by_ci") is not False
        or document.get("changes_to_canonical_data") is not False
        or document.get("auto_resolution_allowed") is not False
        or not isinstance(document.get("cases"), list) or not document["cases"]):
        raise ValueError("Invalid/nonattesting biographical source registry")
    scope = document.get("source_scope")
    if (not isinstance(scope, dict) or
        scope.get("canonical_person_facts_path") != FACTS or
        scope.get("source_registry_path") != SOURCES or
        not isinstance(scope.get("fact_ids"), list) or
        not isinstance(scope.get("source_ids"), list) or
        len(set(scope["fact_ids"])) != len(scope["fact_ids"]) or
        len(set(scope["source_ids"])) != len(scope["source_ids"]) or
        not scope.get("method")):
        raise ValueError("Biography source scope must use canonical fact/source IDs")
    facts = index_unique(h.read_jsonl(root / FACTS), "person fact")
    sources = index_unique(h.read_jsonl(root / SOURCES), "source")
    people = index_unique(
        [h.load_json(p) for p in sorted((root / "data/atlas/people").glob("*.json"))],
        "person",
    )
    seen_cases, seen_obs, seen_facts = set(), set(), set()
    for case in document["cases"]:
        if (not isinstance(case, dict) or set(case) != CASE_KEYS
            or not isinstance(case["id"], str) or not h.CASE_ID.fullmatch(case["id"])
            or case["id"] in seen_cases
            or case["kind"] != "birth_date_disagreement"
            or case["field"] != "birth"
            or case["comparison_relation"] != "competing_published_birth_datings"
            or not isinstance(case["person_name"], str)
            or case["person_id"] not in people
            or case["person_name"] != people[case["person_id"]]["name"]
            or not isinstance(case["question"], str) or not case["question"].strip()
            or case["reviewed_primary_acts"] is not False
            or case["historical_truth_verified_by_ci"] is not False
            or case["actual_power_inferred"] is not False
            or not isinstance(case["canonical_fact_ids"], list)
            or len(case["canonical_fact_ids"]) != 2
            or len(set(case["canonical_fact_ids"])) != 2
            or not isinstance(case["observations"], list)
            or len(case["observations"]) != 2):
            raise ValueError("Biographical conflict requires two verified identity-bound birth observations")
        validate_resolution(case)
        birth_dates, local_source_ids, local_facts = [], set(), set()
        for obs in case["observations"]:
            if (not isinstance(obs, dict) or set(obs) != OBS_KEYS
                or not isinstance(obs["id"], str) or
                not obs["id"].startswith(case["id"] + "-") or
                obs["id"] in seen_obs
                or obs["source_kind"] not in SOURCE_KINDS
                or obs["claim_type"] != "birth_date"
                or not isinstance(obs["source_locator"], str) or
                not obs["source_locator"].strip()
                or not isinstance(obs["note"], str) or not obs["note"].strip()
                or not h.safe_url(obs["source_url"])
                or not h.safe_url(obs["corroborating_url"])
                or obs["independent_primary_checked"] is not False):
                raise ValueError("Missing historical source, original date, or unsafe biography attestation")
            factid, sourceid = obs["canonical_fact_id"], obs["source_id"]
            fact, origin = facts.get(factid), sources.get(sourceid)
            if (fact is None or origin is None or
                factid not in case["canonical_fact_ids"] or
                factid in seen_facts or factid in local_facts or
                sourceid in local_source_ids or
                obs["pinned_canonical_fact"] != fact or
                obs["pinned_source_record"] != origin or
                obs["source_url"] != origin.get("url") or
                obs["verification"] != fact.get("verification") or
                fact.get("person_id") != case["person_id"] or
                fact.get("kind") != "birth" or
                sourceid not in fact.get("sources", [])):
                raise ValueError("Biographical fact/source drift or unrelated person")
            value = obs.get("value")
            if (not isinstance(value, dict) or
                set(value) != {"old_style", "new_style"}):
                raise ValueError("Date observations must show two separately recorded calendar styles")
            old, new = value["old_style"], value["new_style"]
            h.validate_date(old)
            h.validate_date(new)
            if (old["calendar"] != "julian" or new["calendar"] != "gregorian"
                or old["precision"] != new["precision"] or
                old["precision"] != "day"
                or old["format"] != "literal_iso"
                or new["format"] != "literal_iso"
                or old["value"] != fact["value"]["value"]
                or old["calendar"] != fact["value"]["calendar"]
                or old["precision"] != fact["value"]["precision"]
                or old["value"] == new["value"]
                or old["value"][:4] != new["value"][:4]):
                raise ValueError("Source birth date, precision, or calendar does not match canon")
            seen_obs.add(obs["id"])
            local_facts.add(factid)
            seen_facts.add(factid)
            local_source_ids.add(sourceid)
            birth_dates.append(old["value"])
        if len(set(birth_dates)) != 2:
            raise ValueError("This case is not a competing-dates dispute")
        seen_cases.add(case["id"])
    all_case_facts = {f for case in document["cases"] for f in case["canonical_fact_ids"]}
    if all_case_facts != seen_facts or all_case_facts != set(scope["fact_ids"]):
        raise ValueError("Source-scope fact IDs do not match the exact observed facts")
    if set(scope["source_ids"]) != {
        obs["source_id"] for case in document["cases"] for obs in case["observations"]
    }:
        raise ValueError("Source-scope source IDs do not match the source observations")
    return document


def summary(document: dict) -> dict:
    return {"schema_version": document["schema_version"],
            "case_count": len(document["cases"]),
            "by_status": dict(sorted(Counter(c["review_status"]
                                             for c in document["cases"]).items())),
            "distinct_people": len({c["person_id"] for c in document["cases"]}),
            "source_observations": sum(len(c["observations"]) for c in document["cases"]),
            "historical_truth_verified_by_ci": False,
            "changes_to_canonical_data": False,
            "auto_resolution_allowed": False}


def main(argv=None) -> int:
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=ROOT)
    args = p.parse_args(argv)
    print(json.dumps(summary(registry(args.root)), ensure_ascii=False, indent=2,
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
