"""Audit source-record coverage without claiming historical completeness.

Editable source: three existing international JSON parties and the separate,
source-backed editorial policy for research windows and regime boundaries.
This program does not modify source files or populate missing monarchs.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/atlas/world-pilots"
START, END = 1762, 1800
CORE = frozenset(("sovereign", "elector", "emperor"))


def read(filename: str):
    return json.loads((SOURCE / filename).read_text(encoding="utf-8"))


def classify(policy: dict, year: int, roles: list, institutions: list) -> str:
    """Seven non-overlapping states, highest-precedence semantic rule first."""
    if policy.get("display_only") == "birthplace_context":
        return "birthplace_context"
    if ((policy.get("historical_start") and year < policy["historical_start"]) or
            (policy.get("historical_end") and year > policy["historical_end"])):
        return "historically_not_in_force"
    if year < policy["researched_from"] or year > policy["researched_through"]:
        return "outside_sample"
    if any(role["role_kind"] in CORE for role in roles):
        return "office"
    if institutions:
        return "institution"
    if roles:
        return "supplementary"
    return "research_gap"


def coverage() -> dict:
    original = read("1762.json")
    dyn = read("dynasty-1762-1780.json")
    ext = read("extension-1781-1800.json")
    editorial = read("coverage-1762-1800.json")
    assert editorial["schema_version"] == "coverage-matrix-v1"
    assert editorial["period"] == {"start": START, "end": END}
    polities = (original["countries"] + dyn["additional_polities"] +
                ext["additional_polities"])
    roles = dyn["roles"] + ext["additional_roles"]
    institutions = ext["institutions"]
    source_ids = {x["id"] for x in (original["sources"] + dyn["sources"] +
                                    ext["sources"] + editorial["sources"])}
    policies = {x["polity_id"]: x for x in editorial["polities"]}
    ids = [s["id"] for s in polities]
    if len(ids) != len(set(ids)) or set(ids) != set(policies):
        raise ValueError("Coverage polities and historical sources disagree")
    output = []
    counts = Counter()
    for state in polities:
        policy = policies[state["id"]]
        if not set(policy["source_ids"]) <= source_ids:
            raise ValueError("Coverage boundary lacks source references")
        years = []
        for year in range(START, END + 1):
            active = [role for role in roles if role["polity_id"] == state["id"]
                      and role["start_year"] <= year <= role["end_year"]]
            organs = [x for x in institutions if x["polity_id"] == state["id"]
                      and x["start_year"] <= year <= x["end_year"]]
            status = classify(policy, year, active, organs)
            counts[status] += 1
            years.append({
                "year": year, "status": status,
                "role_ids": [r["id"] for r in active],
                "institution_ids": [x["id"] for x in organs],
                # These support the coverage boundary and its known entries;
                # they do NOT prove that unrecorded rulers were absent.
                "source_ids": sorted(set(policy["source_ids"] +
                    [src for r in active for src in r["source_ids"]] +
                    [src for i in organs for src in i["source_ids"]]))
            })
        output.append({
            "polity_id": state["id"],
            "name": state.get("name") or state.get("label"),
            "classification": policy["classification"],
            "researched_from": policy["researched_from"],
            "years": years
        })
    result = {
        "schema_version": "europe-coverage-v2",
        "period": {"start": START, "end": END},
        "historical_truth_verified_by_ci": False,
        "completeness_established": False,
        "methodology": (
            "Year intersection means a recorded role or institution, NOT complete "
            "research, verified political control, or same-day coexistence. "
            "No entries is never inferred as no ruler."
        ),
        "status_counts": dict(sorted(counts.items())),
        "states": output
    }
    if sum(counts.values()) != len(polities) * (END - START + 1):
        raise ValueError("Missing country-year cells")
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--output",type=Path,default=Path("coverage-1762-1800.json"))
    args = p.parse_args()
    args.output.write_text(json.dumps(coverage(), ensure_ascii=False, indent=2)
                           + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
