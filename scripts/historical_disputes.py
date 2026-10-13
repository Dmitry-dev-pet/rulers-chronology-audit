#!/usr/bin/env python3
"""Offline, read-only validation/reporting for source disagreements in the atlas.

This script NEVER edits canon, reconciles dates, promotes an office, or
decides which historical statement is true. Python 3.11+ standard library.
"""
from __future__ import annotations

import argparse
import hashlib
from collections import Counter
import json
from pathlib import Path
import re
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = Path("research/contradictions/register-v1.json")
SOURCE_LEDGER = Path("research/wikidata/p9-office-claims-2026-10-13.json")
QID = re.compile(r"Q[1-9][0-9]*\Z")
CASE_ID = re.compile(r"HC-[0-9]{4}\Z")
WIKIDATA_STAMP = re.compile(r"\+[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z")
ISO_YEAR = re.compile(r"[0-9]{4}\Z")
ISO_MONTH = re.compile(r"[0-9]{4}-(0[1-9]|1[0-2])\Z")
ISO_DAY = re.compile(r"[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])\Z")
CASE_KINDS = {
    "office_period_disagreement": "possibly_different_legal_events",
    "date_calendar_mismatch_candidate": "different_event_not_equated",
    "office_scope_anomaly": "non_equivalent_legal_contexts",
}
CASE_KEYS = {
    "id", "kind", "review_status", "person_id", "person_qid", "office_id",
    "context_id", "canonical_tenure_ids", "external_statement_id",
    "comparison_relation", "question", "resolution", "reviewed_primary_acts",
    "actual_power_inferred", "historical_truth_verified_by_ci", "observations",
}
OBS_KEYS = {
    "id", "source_kind", "source_url", "source_locator", "claim_type",
    "verification", "independent_primary_checked", "source_references_count",
    "value", "note",
}
DATES = {"start", "end", "date", "old_style", "new_style"}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def safe_url(url: object) -> bool:
    """Only public HTTPS references; never local/private source links."""
    if not isinstance(url, str):
        return False
    p = urlparse(url)
    host = (p.hostname or "").lower()
    return (p.scheme == "https" and p.username is None and p.password is None
            and not p.fragment.startswith("access_token")
            and bool(host) and "." in host and
            host not in {"drive.google.com", "docs.google.com", "localhost"}
            and not host.endswith(".local") and not host.endswith(".internal")
            and not host.endswith(".private") and
            not any(s in url.lower() for s in ("token=", "api_key=", "password=")))


def validate_date(item: object) -> None:
    if not isinstance(item, dict) or set(item) != {
        "value", "precision", "calendar", "format",
    }:
        raise ValueError("Date must retain raw value, precision, calendar and source format")
    value, prec, cal, fmt = (item["value"], item["precision"],
                             item["calendar"], item["format"])
    if (prec not in {"year", "month", "day"} or
        cal not in {"julian", "gregorian", "unspecified"} or
        fmt not in {"wikidata_time", "literal_iso"} or
        not isinstance(value, str)):
        raise ValueError("Unsupported or guessed date style/precision")
    if fmt == "wikidata_time":
        if not WIKIDATA_STAMP.fullmatch(value):
            raise ValueError("Original Wikidata time must be literal, not converted")
        month, day = int(value[6:8]), int(value[9:11])
        if (prec == "day" and not (1 <= month <= 12 and 1 <= day <= 31) or
            prec == "month" and not 1 <= month <= 12):
            raise ValueError("Wikidata timestamp precision exceeds known fields")
    elif not {"year": ISO_YEAR, "month": ISO_MONTH, "day": ISO_DAY}[prec].fullmatch(value):
        raise ValueError("Literal date precision does not match the source")
    if value[:4] in {"0000", "+000"}:
        raise ValueError("Zero year requires a different, reviewed temporal contract")


def validate_observation(obs: dict, case: dict, pinned: dict) -> None:
    if not isinstance(obs, dict) or set(obs) != OBS_KEYS:
        raise ValueError("Observation fields incomplete or include unsupported assertions")
    if (not isinstance(obs["id"], str) or not obs["id"].startswith(case["id"] + "-")
        or obs["source_kind"] not in {"wikidata_p39", "institutional_reference"}
        or not safe_url(obs["source_url"]) or
        not isinstance(obs["source_locator"], str) or not obs["source_locator"]
        or not isinstance(obs["note"], str) or not obs["note"]
        or obs["independent_primary_checked"] is not False
        or not isinstance(obs["value"], dict)):
        raise ValueError("Observation missing source, locator, explanation, or unsafe attestation")
    value = obs["value"]
    if obs["source_kind"] == "wikidata_p39":
        if (obs["verification"] != "raw_external_statement"
            or obs["source_url"] != "https://www.wikidata.org/wiki/" + case["person_qid"]
            or obs["source_locator"] != pinned["statement_id"]
            or obs["source_references_count"] != pinned["p39_reference_count"]
            or obs["claim_type"] not in {"office_period", "office_start", "office_end", "office_type"}):
            raise ValueError("External P39 source ID or original evidence changed")
        allowed = {
            "office_period": {"start", "end"},
            "office_start": {"date"},
            "office_end": {"date"},
            "office_type": {"office_qid", "start", "end"},
        }[obs["claim_type"]]
        if set(value) != allowed:
            raise ValueError("Source P39 claim has unexpected boundaries")
        if obs["claim_type"] == "office_type" and value["office_qid"] != pinned["p39_office_qid"]:
            raise ValueError("Raw office QID changed")
        boundaries = {
            "start": pinned["p39_start"],
            "end": pinned["p39_end"],
            "date": (pinned["p39_end"] if obs["claim_type"] == "office_end"
                     else pinned["p39_start"]),
        }
        for key, d in value.items():
            if key not in DATES:
                continue
            validate_date(d)
            if (d["format"] != "wikidata_time" or d["value"] != boundaries[key] or
                d["calendar"] != pinned["calendar"] or
                d["precision"] != {9: "year", 10: "month", 11: "day"}.get(pinned["precision"])):
                raise ValueError("P39 value, date precision or calendar drifted from frozen source")
    else:
        if (obs["verification"] != "reference_text_checked" or
            obs["source_references_count"] is not None or
            obs["claim_type"] not in {"formal_office_period", "election_event",
                                      "death_event", "legal_office_type"}):
            raise ValueError("Institutional reference is not an external P39 statement")
        allowed = {
            "formal_office_period": {"start", "end"},
            "election_event": {"old_style", "new_style"},
            "death_event": {"old_style", "new_style"},
            "legal_office_type": {"office_id", "start", "end"},
        }[obs["claim_type"]]
        if set(value) != allowed:
            raise ValueError("Unqualified institutional reference claims")
        if obs["claim_type"] == "legal_office_type" and value["office_id"] != case["office_id"]:
            raise ValueError("Institutional office type is not the existing canonical office")
        for key, d in value.items():
            if key in DATES:
                validate_date(d)
                if d["format"] != "literal_iso":
                    raise ValueError("Institutional summary cannot claim a Wikidata literal")
        if obs["claim_type"] in {"election_event", "death_event"}:
            if not (value["old_style"]["calendar"] == "julian" and
                    value["new_style"]["calendar"] == "gregorian" and
                    value["old_style"]["precision"] == value["new_style"]["precision"] == "day"):
                raise ValueError("Original old/new calendar pair must be explicitly labelled")


def registry(root: Path = ROOT) -> dict:
    doc = load_json(root / REGISTRY)
    if (doc.get("schema_version") != "historical-dispute-registry-v1"
        or doc.get("historical_truth_verified_by_ci") is not False
        or doc.get("changes_to_canonical_data") is not False
        or doc.get("auto_resolution_allowed") is not False
        or not isinstance(doc.get("cases"), list) or not doc["cases"]):
        raise ValueError("Not a versioned, non-attesting research registry")
    snapshot = doc.get("source_snapshot")
    if (not isinstance(snapshot, dict) or
        snapshot.get("path") != SOURCE_LEDGER.as_posix() or
        not re.fullmatch(r"[0-9a-f]{40}", snapshot.get("commit", "")) or
        not safe_url(snapshot.get("audit_run")) or
        not re.fullmatch(r"[0-9a-f]{40}", snapshot.get("git_blob_sha1", ""))):
        raise ValueError("Missing immutable P9 source snapshot identity")
    raw_ledger = (root / SOURCE_LEDGER).read_bytes()
    git_object = b"blob " + str(len(raw_ledger)).encode("ascii") + b"\0" + raw_ledger
    if hashlib.sha1(git_object).hexdigest() != snapshot["git_blob_sha1"]:
        raise ValueError("Pinned P9 historical-source bytes changed: explicit new review needed")
    ledger = json.loads(raw_ledger.decode("utf-8"))
    if (ledger.get("schema_version") != "wikidata-p9-claim-case-review-v1"
        or snapshot["audit_run"] != ledger.get("frozen_source_run")):
        raise ValueError("P9 frozen-source audit identity mismatch")
    p9_by_id = {x["statement_id"]: x for x in ledger["cases"]}
    # Multiple cases can study different boundaries of the SAME P39 statement.
    people = {x["id"]: x for f in (root / "data/atlas/people").glob("*.json")
              for x in [load_json(f)]}
    terms = {x["id"]: x for x in read_jsonl(root / "data/atlas/tenures.jsonl")}
    offices = {x["id"] for x in read_jsonl(root / "data/atlas/offices.jsonl")}
    contexts = {x["id"] for x in read_jsonl(root / "data/atlas/states.jsonl")}
    case_ids, obs_ids, raw_claim_facets = set(), set(), set()
    for case in doc["cases"]:
        if (not isinstance(case, dict) or set(case) != CASE_KEYS
            or not isinstance(case["id"], str) or not CASE_ID.fullmatch(case["id"])
            or case["id"] in case_ids or case["kind"] not in CASE_KINDS
            or case["comparison_relation"] != CASE_KINDS[case["kind"]]
            or case["review_status"] not in {"open", "in_review", "resolved"}
            or case["historical_truth_verified_by_ci"] is not False
            or case["actual_power_inferred"] is not False
            or case["reviewed_primary_acts"] is not False
            or not isinstance(case["question"], str) or not case["question"]
            or case["person_id"] not in people or case["office_id"] not in offices
            or case["context_id"] not in contexts
            or people[case["person_id"]].get("external_ids", {}).get("wikidata")
                  != case["person_qid"] or
            not isinstance(case["canonical_tenure_ids"], list) or
            not case["canonical_tenure_ids"] or
            len(set(case["canonical_tenure_ids"])) != len(case["canonical_tenure_ids"])):
            raise ValueError("Case is not an unresolved, typed historical question with stable IDs")
        if case["review_status"] == "resolved":
            resolution = case["resolution"]
            if (not isinstance(resolution, dict) or
                not resolution.get("reviewer") or not resolution.get("reason") or
                not isinstance(resolution.get("evidence_urls"), list) or
                len(resolution["evidence_urls"]) < 2 or
                len(set(resolution["evidence_urls"])) != len(resolution["evidence_urls"]) or
                not all(safe_url(u) for u in resolution["evidence_urls"])):
                raise ValueError("Manual historical resolution requires a reviewer and independent evidence")
        elif case["resolution"] is not None:
            raise ValueError("A CI run cannot auto-resolve an unsettled case")
        for tid in case["canonical_tenure_ids"]:
            t = terms.get(tid)
            if (not t or t["person_id"] != case["person_id"] or
                t["office_id"] != case["office_id"] or
                case["context_id"] not in t["state_ids"]):
                raise ValueError("Reference to another person's or type's canonical tenure")
        pinned = p9_by_id.get(case["external_statement_id"])
        if (not pinned or pinned["canonical_person_id"] != case["person_id"] or
            pinned["wikidata_person_qid"] != case["person_qid"]):
            raise ValueError("External P39 statement cannot be assigned to this person")
        observations = case["observations"]
        if (not isinstance(observations, list) or len(observations) != 2 or
            {x.get("source_kind") for x in observations if isinstance(x, dict)}
              != {"wikidata_p39", "institutional_reference"}):
            raise ValueError("Each case needs independently attributable competing observations")
        for obs in observations:
            validate_observation(obs, case, pinned)
            if obs["id"] in obs_ids:
                raise ValueError("Duplicate stable observation ID")
            obs_ids.add(obs["id"])
        wiki = next(x for x in observations if x["source_kind"] == "wikidata_p39")
        independent = next(x for x in observations if x["source_kind"] == "institutional_reference")
        expected = {
            "office_period_disagreement": ("office_period", "formal_office_period"),
            "date_calendar_mismatch_candidate": ({"office_start": "election_event",
                                                  "office_end": "death_event"}),
            "office_scope_anomaly": ("office_type", "legal_office_type"),
        }[case["kind"]]
        if case["kind"] == "date_calendar_mismatch_candidate":
            if (wiki["claim_type"] not in expected or
                independent["claim_type"] != expected[wiki["claim_type"]]):
                raise ValueError("Do not silently equate election/death with office dates")
        elif (wiki["claim_type"], independent["claim_type"]) != expected:
            raise ValueError("Two source observations concern incompatible research facets")
        facet = (case["external_statement_id"], wiki["claim_type"])
        if facet in raw_claim_facets:
            raise ValueError("Duplicate conflict over the same source field; add another observation instead")
        raw_claim_facets.add(facet)
        case_ids.add(case["id"])
    return doc


def registry_all(root: Path = ROOT) -> dict:
    """Union of separately verified P9 and canonical-biography source adapters.

    Preserve the old P9 registry and its pinned blob/source compatibility.
    The new biographical case is aggregated *without* pretending to be P39.
    """
    from scripts import historical_biographical_disputes as biography

    old = registry(root)
    bio = biography.registry(root)
    all_cases = old["cases"] + bio["cases"]
    identifiers = [case["id"] for case in all_cases]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("Duplicate stable historical dispute case ID across adapters")
    return {
        "schema_version": "historical-dispute-overview-v2",
        "historical_truth_verified_by_ci": False,
        "changes_to_canonical_data": False,
        "auto_resolution_allowed": False,
        "sources": [
            {"kind": "wikidata_p9", "path": str(REGISTRY)},
            {"kind": "canonical_biography", "path": str(biography.REGISTRY)},
        ],
        "cases": sorted(all_cases, key=lambda case: case["id"]),
    }


def render_markdown(document: dict) -> str:
    from collections import Counter
    kinds = Counter(x["kind"] for x in document["cases"])
    lines = ["# Исторические противоречия: исследовательский реестр",
             "", "**Не является автоматическим историческим заключением.**",
             "", f"Открытых/проверяемых кейсов: **{sum(x['review_status'] != 'resolved' for x in document['cases'])}**.",
             "", "## Типы вопросов", ""]
    lines += [f"- {k}: {v}" for k, v in sorted(kinds.items())]
    lines += ["", "## Карточки", "", "| ID | Личность | Проблема | Статус | Источники |",
              "| --- | --- | --- | --- | --- |"]
    for x in document["cases"]:
        urls = " / ".join(f"[{o['source_kind']}]({o['source_url']})" for o in x["observations"])
        display_person = x.get("person_name") or x.get("person_qid") or x["person_id"]
        lines.append(f"| {x['id']} | {display_person} | {x['kind']} | {x['review_status']} | {urls} |")
        lines.extend(["", f"**{x['id']}:** {x['question']}", ""])
    lines.extend(["Нет автоматического исправления календарей, титулов, правления, границ и реальной власти.", ""])
    return "\n".join(lines)


def summary(document: dict) -> dict:
    cases = document["cases"]
    return {"schema_version": document["schema_version"],
            "case_count": len(cases),
            "by_type": dict(sorted(Counter(x["kind"] for x in cases).items())),
            "by_status": dict(sorted(Counter(x["review_status"] for x in cases).items())),
            "distinct_people": len({x["person_id"] for x in cases}),
            "source_observations": sum(len(x["observations"]) for x in cases),
            "historical_truth_verified_by_ci": False,
            "changes_to_canonical_data": False,
            "auto_resolution_allowed": False}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--format", choices=["json", "markdown"], default="markdown")
    p.add_argument("--legacy-only", action="store_true",
                   help="Validate and display only the original pinned P9 source registry")
    args = p.parse_args(argv)
    doc = registry(args.root) if args.legacy_only else registry_all(args.root)
    if args.format == "json":
        print(json.dumps(summary(doc), ensure_ascii=False, sort_keys=True, indent=2))
    else:
        print(render_markdown(doc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
