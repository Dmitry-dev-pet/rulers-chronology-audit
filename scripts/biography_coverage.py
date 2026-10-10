#!/usr/bin/env python3
"""Report bibliography completeness without creating unsupported facts."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from scripts.atlas_db import load, ROOT


def coverage(db: dict) -> dict:
    facts = defaultdict(list)
    for fact in db["person_facts"]:
        facts[fact["person_id"]].append(fact)
    records = []
    for person in sorted(db["people"],key=lambda p:p["name"].casefold()):
        pf=facts[person["id"]]
        births=[f for f in pf if f["kind"]=="birth"]
        birth_status=(
            "unresearched" if not births else
            "disputed" if any(f["verification"]=="disputed" or f["value"]["qualifier"]=="uncertain" for f in births) or len(births)>1 else
            "reference_checked" if any(f["verification"]=="reference_checked" for f in births) else
            "preliminary"
        )
        records.append({
            "person_id":person["id"],"name":person["name"],
            "birth_status":birth_status,
            "birth_assertions":len(births),
            "lifespan_review_texts":[str(f["value"]) for f in pf if f["kind"]=="lifespan_text"],
            "has_sourced_ethnic_origin":any(f["kind"]=="ethnic_origin" for f in pf),
            "has_sourced_dynasty":any(f["kind"]=="dynasty" for f in pf),
        })
    stats=Counter(r["birth_status"] for r in records)
    return {
        "schema_version":1,"total_people":len(records),
        "with_any_birth_fact":sum(r["birth_assertions"]>0 for r in records),
        "missing_birth_fact":sum(r["birth_status"]=="unresearched" for r in records),
        "status_counts":dict(stats),
        "rows":records,
        "warning":"Life-span strings, disputed dates and ethnic origin are not independently verified by this report."
    }


if __name__=="__main__":
    print(json.dumps(coverage(load(ROOT)),ensure_ascii=False,indent=2))
