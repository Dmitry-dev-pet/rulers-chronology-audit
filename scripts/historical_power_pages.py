"""HPM P3: safely project the P2 source sample for an opt-in, static SPA lab.

All inputs are Git-tracked and read-only; the same in-memory SQLite connection
as P2 is used. This is NOT a migration, a new historical claim, a global
succession study, or a machine classification of accession mechanisms.
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts import historical_power_sqlite as hpm

ROOT = hpm.ROOT
SCHEMA_VERSION = "hpm-pages-p3-v1"
KINDS = frozenset(hpm.EVENT_KINDS)


def exactly_one(conn, query: str, params: tuple) -> dict:
    matches = hpm.rows(conn, query, params)
    hpm.require(len(matches) == 1, "P3 evidence crosswalk is not unique")
    return matches[0]


def projection(root: Path = ROOT) -> dict:
    """Return a public, read-only *projection*; do not write any files."""
    conn, _ = hpm.preview(root)
    try:
        report = hpm.report(conn)
        manifest = hpm.mapping(root)
        hpm.require(report["historical_truth_verified_by_ci"] is False
                    and report["historical_region_wide_inference_supported"] is False
                    and report["accession_mechanism_rates"] is None
                    and report["query_only"] is True,
                    "P2 research-only contract was relaxed")
        counts = report["counts"]
        hpm.require(counts["candidate_events"] == 10
                    and counts["reviewed_role_linkages"] == 3
                    and counts["candidate_only"] == 7
                    and counts["classified_mechanisms"] == 0
                    and counts["accession_mechanism_unknown"] == 10,
                    "unexpected source inventory: re-review P3 inclusion before publishing")
        events = []
        for item in report["evidence"]:
            rel = exactly_one(conn, """
                SELECT r.title, r.note, a.statement, a.caveat,
                       a.category, a.verification, p.meaning
                FROM v2_relationships r
                JOIN v2_assertions a ON a.id=r.assertion_id
                JOIN v2_periods p ON p.id=r.period_id
                WHERE r.id=?""", (item["relation_id"],))
            hpm.require(rel["meaning"] == "event",
                        "cannot show research window as point event")
            contexts = hpm.rows(conn, """
                SELECT c.id,c.label,c.kind FROM v2_relationship_contexts rc
                JOIN v2_contexts c ON c.id=rc.context_id
                WHERE rc.relation_id=? ORDER BY rc.position
                """, (item["relation_id"],))
            links = []
            for link in item["role_links"]:
                role = exactly_one(conn, """
                    SELECT r.title,r.role_kind,r.context_id,c.label AS context_label,
                           COALESCE(ep.display_label, ins.label, r.title) AS actor_label
                    FROM v2_roles r
                    JOIN v2_contexts c ON c.id=r.context_id
                    LEFT JOIN v2_external_people ep
                      ON ep.origin=r.external_person_origin
                     AND ep.native_id=r.external_person_id
                    LEFT JOIN v2_institutions ins ON ins.id=r.institution_id
                    WHERE r.id=?""", (link["role_id"],))
                sources = [src for src in item["role_documentary_sources"]
                           if src["direction"] == link["direction"]
                           and src["role_id"] == link["role_id"]]
                hpm.require(bool(sources), "reviewed role has no published trace")
                hpm.require(all(hpm.public_url(x["source_url"]) and x["pinpoint"]
                                for x in sources), "unsafe linked-role source")
                links.append({**link, **role, "sources": sources})
            hpm.require(item["accession_mechanism"] == "unknown"
                        and item["kind"] in KINDS
                        and bool(item["documentary_sources"]),
                        "an event was promoted beyond the source candidate")
            hpm.require(all(hpm.public_url(s["source_url"]) and s["pinpoint"]
                            for s in item["documentary_sources"]),
                        "unsafe event source")
            events.append({
                "id": item["id"],
                "relation_id": item["relation_id"],
                "event_year": item["event_year"],
                "year_resolution": "year_index_only",
                "kind": item["kind"],
                "title": rel["title"],
                "note": rel["note"],
                "contexts": contexts,
                "review_status": item["review_status"],
                "accession_mechanism": "unknown",
                "assertion": {
                    "id": item["assertion_id"],
                    "statement": rel["statement"],
                    "caveat": rel["caveat"],
                    "category": rel["category"],
                    "verification": rel["verification"],
                },
                "sources": item["documentary_sources"],
                "roles": links,
                "raw_observations": item["original_observations"],
            })
        hpm.require(len(events) == 10 and
                    len({row["id"] for row in events}) == 10
                    and sum(bool(row["roles"]) for row in events) == 3,
                    "source-to-event join accidentally multiplied or lost evidence")
        result = {
            "schema_version": SCHEMA_VERSION,
            "historical_truth_verified_by_ci": False,
            "historical_region_wide_inference_supported": False,
            "geographic_borders_verified": False,
            "accession_mechanism_rates": None,
            "sample": {
                "years": [1762, 1800],
                "unit": report["research_scope"]["unit"],
                "coverage": report["research_scope"]["coverage"],
                "source": report["research_scope"]["source"],
                "population_caveat": manifest["population"],
            },
            "counts": counts,
            "warning": report["warning"],
            "events": events,
        }
        raw = json.dumps(result, ensure_ascii=False)
        hpm.require("drive.google.com" not in raw.lower()
                    and "1000428575.jpg" not in raw.lower()
                    and "private" not in result["sample"]["coverage"],
                    "protected original appeared in public HPM projection")
        return result
    finally:
        conn.close()
