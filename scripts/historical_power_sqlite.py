#!/usr/bin/env python3
"""HPM P2: inspect source-qualified P3 transition candidates in disposable SQLite.

The input is the tested, Git-tracked Atlas v1/v2/P3 research snapshot. This
module never edits it, never infers an accession mechanism from a relation
name, and deliberately emits NO Europe-wide succession percentages. Only
three explicit source/role crosswalks are reviewed at the identity/link level.
Python standard library only. Database and report are not published.
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit

from scripts import atlas_v2_crosswalk as p1
from scripts import atlas_v2_relations as p3

ROOT = p1.ROOT
MAPPING_FILE = Path("design/atlas-v2/hpm-role-linkage-v1.json")
SCHEMA_FILE = Path("schemas/hpm_transition_candidate.sql")
EVENT_KINDS = (
    "succession", "imperial_succession", "regime_change", "institutional_change"
)
PINNED_LINKS = {
    "v2-p3-rel-dn-france-change-1774": (
        "succession", "ctx-world-fr", "v2-role-dn-fr-louis15", "v2-role-dn-fr-louis16"),
    "v2-p3-rel-dn-hre-change-1765": (
        "imperial_succession", "ctx-world-hre", "v2-role-dn-hre-francis", "v2-role-dn-hre-joseph"),
    "v2-p3-rel-ex-fr-1799": (
        "institutional_change", "ctx-world-frrep", "v2-role-ex-fr-directory", "v2-role-ex-fr-consulate"),
}
MAPPING_KEYS = {
    "relationship_id", "relation_kind", "context_id", "outgoing_role_id",
    "incoming_role_id", "review_dimension", "caveat"
}
WARNING = (
    "The denominators describe ONLY a selected published research pilot, "
    "not all European transitions. 'Reviewed' means source-to-role identity "
    "crosswalk only, not independently adjudicated historical truth. "
    "No accession mechanism or practical control is inferred. "
    "Year candidates do not imply same-day simultaneous office holding."
)


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError("HPM P2: " + reason)


def pairs(values: list[tuple[str, object]]) -> dict:
    result = {}
    for k, v in values:
        require(k not in result, "duplicate JSON key " + k)
        result[k] = v
    return result


def mapping(root: Path = ROOT) -> dict:
    # Fixed relative name; this is a versioned, public Git-tracked input.
    return json.loads((root / MAPPING_FILE).read_text(encoding="utf-8"),
                      object_pairs_hook=pairs)


def rows(conn: sqlite3.Connection, sql: str, params=()) -> list[dict]:
    cursor = conn.execute(sql, params)
    fields = [c[0] for c in cursor.description]
    return [dict(zip(fields, item)) for item in cursor.fetchall()]


def public_url(url: object) -> bool:
    if not isinstance(url, str):
        return False
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower()
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            return False  # no IP literals, even public ones, in source URLs
        return (parsed.scheme == "https" and bool(host) and "." in host
                and parsed.port in (None, 443)
                and parsed.username is None and parsed.password is None
                and host not in {"drive.google.com", "docs.google.com", "localhost"}
                and not any(host.endswith(s) for s in (".internal", ".local", ".private", ".localhost", ".lan"))
                and not any(s in url.lower() for s in
                            ("token=", "apikey=", "api_key=", "password=", "secret=")))
    except (ValueError, AttributeError):
        return False


def claim_sources(conn: sqlite3.Connection, assertion_id: str) -> list[dict]:
    sources = rows(conn, """SELECT s.id, s.origin, s.native_id, s.title,
                            s.url, s.verification, a.pinpoint
        FROM v2_assertion_sources a JOIN v2_sources s ON s.id=a.source_id
        WHERE a.assertion_id=? ORDER BY s.id, a.pinpoint""", (assertion_id,))
    require(bool(sources), "assertion lacks documentary sources " + assertion_id)
    for source in sources:
        require(public_url(source["url"]), "nonpublic / unsafe source URL")
        require(bool(source["origin"] and source["native_id"] and
                     source["pinpoint"]), "unqualified source/provenance")
    return sources


def event_records(conn: sqlite3.Connection) -> list[dict]:
    result = rows(conn, """SELECT r.id AS relation_id, r.kind, r.assertion_id,
                              r.period_id, r.event_year AS original_event_year,
                              p.start_year, p.end_year, p.meaning
        FROM v2_relationships r JOIN v2_periods p ON p.id=r.period_id
        WHERE r.kind IN ('succession','imperial_succession',
                         'regime_change','institutional_change')
        ORDER BY r.id""")
    for item in result:
        require(item["kind"] in EVENT_KINDS and item["meaning"] == "event",
                "relation is a research window, not a one-time transition")
        require(type(item["start_year"]) is int and
                item["start_year"] == item["end_year"] and
                1 <= item["start_year"] <= 9999,
                "event has uncertain / unsupported year scope")
        require(item["original_event_year"] is None or
                item["original_event_year"] == item["start_year"],
                "original event year contradicts the period")
        claim_sources(conn, item["assertion_id"])
        imported = rows(conn, """SELECT origin, native_id, dataset, raw_json
            FROM v2_relationship_imports WHERE relationship_id=? ORDER BY origin,native_id""",
            (item["relation_id"],))
        require(bool(imported), "P3 relation lacks lossless original source record")
        for source in imported:
            require(source["origin"] and source["native_id"] and source["dataset"],
                    "missing raw relation namespace")
            raw = json.loads(source["raw_json"], object_pairs_hook=pairs)
            require(raw.get("id") == source["native_id"], "raw relation identity drift")
    return result


def role_row(conn: sqlite3.Connection, role_id: str) -> dict:
    role = rows(conn, """SELECT r.id, r.context_id, r.role_kind,
                  r.person_id, r.external_person_origin, r.external_person_id,
                  r.body_id, r.institution_id, r.assertion_id,
                  p.start_year,p.end_year,p.meaning
                  FROM v2_roles r JOIN v2_periods p ON p.id=r.period_id
                  WHERE r.id=?""", (role_id,))
    require(len(role) == 1, "reviewed role not present in typed v2 SQL: " + role_id)
    claim_sources(conn, role[0]["assertion_id"])
    # Person roles are imported by role_id; collective institutions are
    # source-preserved under institution_id, not under their derived role_id.
    imported = rows(conn, """SELECT origin,native_id,raw_json FROM v2_world_imports
         WHERE role_id=? OR institution_id=? ORDER BY native_id""",
         (role_id, role[0]["institution_id"]))
    require(len(imported) == 1 and imported[0]["raw_json"],
            "role requires one unchanged source record in world imports")
    raw = json.loads(imported[0]["raw_json"], object_pairs_hook=pairs)
    require(raw.get("id") == imported[0]["native_id"], "world role source ID drift")
    return role[0]


def actor_matches(role: dict, participant: dict) -> bool:
    """Exact typed identity match; NEVER match a person by a display name."""
    if role["person_id"] is not None:
        return role["person_id"] == participant["person_id"] and \
            participant["external_person_id"] is None
    return (role["external_person_origin"] is not None and
            role["external_person_origin"] == participant["external_person_origin"] and
            role["external_person_id"] == participant["external_person_id"] and
            participant["person_id"] is None)


def verify_manifest(conn: sqlite3.Connection, document: dict,
                    events: list[dict] | None = None) -> list[dict]:
    require(type(document) is dict and set(document) == {
        "schema_version", "status", "historical_truth_verified_by_ci",
        "auto_classify_mechanism", "population", "reviewed_links"
    }, "unrecognized mapping document fields")
    require(document["schema_version"] == "hpm-role-linkage-v1" and
            document["status"] == "research_crosswalk_only" and
            document["historical_truth_verified_by_ci"] is False and
            document["auto_classify_mechanism"] is False,
            "manifest cannot promote crosswalks to historical interpretations")
    require(isinstance(document["population"], str) and
            len(document["population"].strip()) > 50,
            "research denominator requires clear inclusion/caveats")
    links = document["reviewed_links"]
    require(type(links) is list and len(links) == len(PINNED_LINKS),
            "P2 pilot source-crosswalk inventory changed without review")
    registry = {record["relation_id"]: record for record in
                (events if events is not None else event_records(conn))}
    used = set()
    for link in links:
        require(isinstance(link, dict) and set(link) == MAPPING_KEYS,
                "reviewed link has incomplete or unsupported fields")
        rid = link["relationship_id"]
        require(type(rid) is str and rid in PINNED_LINKS and rid not in used,
                "duplicate/unapproved relationship crosswalk")
        used.add(rid)
        require((link["relation_kind"], link["context_id"],
                 link["outgoing_role_id"], link["incoming_role_id"]) == PINNED_LINKS[rid],
                "reviewed mapping differs from pinned source-person-role crosswalk")
        require(link["review_dimension"] == "source_record_role_identity_only" and
                isinstance(link["caveat"], str) and len(link["caveat"].strip()) >= 80,
                "reviewed crosswalk lacks narrow evidence caveat")
        require(rid in registry, "reviewed relationship is absent from P3 event scope")
        relation = registry[rid]
        require(relation["kind"] == link["relation_kind"],
                "reviewed relation kind does not match source")
        outgoing = role_row(conn, link["outgoing_role_id"])
        incoming = role_row(conn, link["incoming_role_id"])
        year = relation["start_year"]
        for role in (outgoing, incoming):
            require(role["context_id"] == link["context_id"] and
                    role["meaning"] in {"term", "role_window"},
                    "reviewed crosswalk crosses an unrelated jurisdiction or time kind")
            require(role["start_year"] <= year <= role["end_year"],
                    "source-year does not meet documented role-year window")
        persons = rows(conn, """SELECT person_id, external_person_origin,
                          external_person_id FROM v2_relationship_people
                          WHERE relation_id=? ORDER BY position""", (rid,))
        contexts = rows(conn, """SELECT context_id FROM v2_relationship_contexts
                       WHERE relation_id=? ORDER BY position""", (rid,))
        if relation["kind"] in {"succession", "imperial_succession"}:
            target_kind = "emperor" if relation["kind"] == "imperial_succession" else "sovereign"
            require(outgoing["role_kind"] == incoming["role_kind"] == target_kind,
                    "successor requires same documented type of legal role")
            require(outgoing["institution_id"] is None and
                    incoming["institution_id"] is None and len(persons) == 2 and
                    actor_matches(outgoing, persons[0]) and
                    actor_matches(incoming, persons[1]),
                    "source participant order or person identity mismatch")
        else:
            require(relation["kind"] == "institutional_change" and
                    outgoing["role_kind"] == incoming["role_kind"] == "institutional" and
                    outgoing["institution_id"] is not None and
                    incoming["institution_id"] is not None and
                    not persons and
                    link["context_id"] in {x["context_id"] for x in contexts},
                    "institutional transition cannot be a personal reign")
    require(used == set(PINNED_LINKS), "pinned linkage completeness")
    return links


def append_overlay(conn: sqlite3.Connection, document: dict, root: Path = ROOT) -> dict:
    require(conn.execute("PRAGMA user_version").fetchone()[0] == 1,
            "v1 SQLite version changed")
    require(conn.execute("PRAGMA database_list").fetchone()[2] == "",
            "SQLite is not memory-resident (refuse disk-backed modification)")
    require(conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1,
            "SQLite foreign keys must be enforced")
    events = event_records(conn)
    verified_links = verify_manifest(conn, document, events)
    before = conn.execute("PRAGMA user_version").fetchone()[0]
    # DDL only in disposable :memory: connection. Executescript cannot be inside
    # the canonical builder transaction; source Git and site assets are untouched.
    conn.executescript((root / SCHEMA_FILE).read_text(encoding="utf-8"))
    selected = {item["relationship_id"]: item for item in verified_links}
    with conn:
        for item in events:
            rid = item["relation_id"]
            conn.execute("""INSERT INTO hpm_transfer_candidates
                  (id,relation_id,period_id,assertion_id,event_year,kind,review_status)
                  VALUES(?,?,?,?,?,?,?)""",
                  ("hpm-" + rid, rid, item["period_id"],item["assertion_id"],
                   item["start_year"],item["kind"],
                   "reviewed_linkage" if rid in selected else "candidate"))
        for rid, item in selected.items():
            for direction in ("outgoing", "incoming"):
                conn.execute("""INSERT INTO hpm_transfer_roles
                    (transfer_id,direction,role_id,review_dimension,caveat)
                    VALUES(?,?,?,?,?)""",
                    ("hpm-" + rid,direction,item[direction + "_role_id"],
                     item["review_dimension"],item["caveat"]))
    require(conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok" and
            not conn.execute("PRAGMA foreign_key_check").fetchall(),
            "SQLite integrity or foreign-key verification failed")
    require(conn.execute("PRAGMA user_version").fetchone()[0] == before == 1,
            "SQLite user_version changed")
    require(conn.execute("SELECT COUNT(*) FROM hpm_transfer_event_evidence").fetchone()[0]
            >= len(events), "a candidate lost its original sources")
    require(conn.execute("SELECT COUNT(*) FROM hpm_transfer_role_evidence").fetchone()[0]
            >= 2 * len(verified_links), "reviewed role lost its source")
    return {"candidates": len(events),"reviewed_role_linkages":len(verified_links)}


def report(conn: sqlite3.Connection, year: int | None = None) -> dict:
    """Counts are about sampled SOURCE records, not historical mechanisms."""
    require(year is None or type(year) is int and 1 <= year <= 9999,
            "invalid filter year")
    scoped = "WHERE t.event_year=?" if year is not None else ""
    params = (year,) if year is not None else ()
    records = rows(conn, f"""SELECT t.id,t.relation_id,t.event_year,t.kind,
                                  t.review_status,t.accession_mechanism,t.assertion_id
                         FROM hpm_transfer_candidates t {scoped}
                         ORDER BY t.event_year,t.id""", params)
    evidence = []
    for row in records:
        sources = rows(conn, """SELECT source_namespace,source_native_id,source_title,
                         source_url,pinpoint FROM hpm_transfer_event_evidence
                         WHERE transfer_id=? ORDER BY source_namespace,source_native_id""",
                       (row["id"],))
        require(bool(sources) and all(public_url(s["source_url"]) for s in sources),
                "missing/unsafe source in projection")
        roles = rows(conn, """SELECT r.direction,r.role_id,r.review_dimension,r.caveat
                  FROM hpm_transfer_roles r WHERE r.transfer_id=?
                  ORDER BY r.direction,r.role_id""", (row["id"],))
        role_sources = rows(conn, """SELECT direction,role_id,role_assertion_id,
                    source_namespace,source_native_id,source_url,pinpoint
                    FROM hpm_transfer_role_evidence WHERE transfer_id=?
                    ORDER BY direction,role_id,source_namespace,source_native_id""",
                    (row["id"],))
        original = rows(conn,"""SELECT origin,native_id,dataset,raw_json
                         FROM v2_relationship_imports WHERE relationship_id=?
                         ORDER BY origin,native_id""", (row["relation_id"],))
        evidence.append({
            **row, "documentary_sources":sources,
            "role_links":roles,
            "role_documentary_sources":role_sources,
            "original_observations":[{
                "origin":o["origin"],"native_id":o["native_id"],
                "dataset":o["dataset"],
                "raw_sha256":hashlib.sha256(o["raw_json"].encode("utf-8")).hexdigest()
            } for o in original]
        })
    kinds = {kind:sum(1 for x in records if x["kind"] == kind) for kind in EVENT_KINDS}
    total = len(records)
    linked = sum(x["review_status"] == "reviewed_linkage" for x in records)
    require(all(x["accession_mechanism"] == "unknown" for x in records),
            "unsupported transfer mechanism appeared")
    return {
        "schema_version":"hpm-derived-sqlite-p2-v1",
        "historical_truth_verified_by_ci":False,
        "query_only":bool(conn.execute("PRAGMA query_only").fetchone()[0]),
        "research_scope":{"source":"Atlas v2/P3 world relationships 1762–1800",
                          "filter_event_year":year,
                          "unit":"normalized sourced relationship-event",
                          "coverage":"partial_pilot_not_population"},
        "counts":{"candidate_events":total,"reviewed_role_linkages":linked,
                  "candidate_only":total-linked,
                  "accession_mechanism_unknown":total,
                  "classified_mechanisms":0,"relation_kinds":kinds},
        "accession_mechanism_rates":None,
        "historical_region_wide_inference_supported":False,
        "warning":WARNING,
        "evidence":evidence
    }


def preview(root: Path = ROOT) -> tuple[sqlite3.Connection, dict]:
    """Build from real Git inputs, freeze the resulting SQLite as query-only."""
    snapshot = p1.load_snapshot(root)
    snapshot["root"] = root
    conn, base = p3.preview(snapshot)
    try:
        appended = append_overlay(conn, mapping(root), root)
        conn.execute("PRAGMA query_only=ON")
        require(conn.execute("PRAGMA query_only").fetchone()[0] == 1,
                "post-build connection must refuse writes")
        return conn, {"atlas_v2":base,"hpm":appended}
    except Exception:
        conn.close()
        raise


def build(root: Path = ROOT, year: int | None = None) -> dict:
    conn, _ = preview(root)
    try:
        return report(conn, year)
    finally:
        conn.close()


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year",type=int,help="optional source-event year filter")
    args=parser.parse_args()
    print(json.dumps(build(ROOT,args.year), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
