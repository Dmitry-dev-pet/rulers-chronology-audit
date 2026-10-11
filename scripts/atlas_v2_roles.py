"""P2: source-preserving European roles/institutions in a disposable v2 SQLite.

No mutation of Git-tracked atlas data, v1 schema, public site or deployment.
A role-year range is a source-window candidate, never guaranteed same-day power.
The international 1762 pilot is represented by overlapping dynasty-network
roles, so it must not be imported a second time as fabricated office records.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from datetime import date
from pathlib import Path

from scripts import atlas_v2_crosswalk as crosswalk

ROOT = crosswalk.ROOT
ROLE_DATASETS = ("dynasty-1762-1780.json", "extension-1781-1800.json")
ALLOWED_ROLES = frozenset({
    "sovereign", "elector", "emperor", "regent", "co_regent",
    "consort", "heir", "dynastic_person", "first_consul",
})
DYNASTIC_ROLES = frozenset({"consort", "heir", "dynastic_person"})
INSTITUTION_KINDS = frozenset({"collective", "collegial_executive", "executive_system"})
SOURCE_FILE_PREFIX = "data/atlas/world-pilots/"


def require(condition: bool, message: str) -> None:
    crosswalk.require(condition, "P2: " + message)


def dump(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def world_records(snapshot: dict) -> tuple[list[tuple[str, dict]], list[tuple[str, dict]]]:
    """Import each explicitly specified pilot record once, without inference."""
    world = snapshot["world"]
    roles = [(ROLE_DATASETS[0],r) for r in world[ROLE_DATASETS[0]]["roles"]]
    roles += [(ROLE_DATASETS[1],r) for r in world[ROLE_DATASETS[1]]["additional_roles"]]
    institutions = [(ROLE_DATASETS[1],r) for r in world[ROLE_DATASETS[1]]["institutions"]]
    return roles, institutions


def role_period(record: dict, dataset: str) -> tuple[dict, dict]:
    """The timeline indexes OBSERVED source years, not entire historical careers.

    The only explicitly day-precision endpoint in the current pilot is the
    labelled Gregorian death of Elizabeth in 1762. A role whose original
    actual_start_year predates start_year is LEFT-CENSORED; some extension rows
    end at the study limit 1800 and are RIGHT-CENSORED. These are NOT
    day-precision claims. Exact source JSON remains in v2_world_imports.
    """
    start, end = record["start_year"], record["end_year"]
    actual_start = record.get("actual_start_year")
    left_clipped = actual_start is not None and actual_start < start
    right_clipped = dataset == ROLE_DATASETS[1] and end == 1800
    begin_date = None if left_clipped else {
        "value": str(start), "calendar": "unspecified",
        "precision": "year", "qualifier": "as_recorded",
    }
    end_date = None if right_clipped else {
        "value": str(end), "calendar": "unspecified",
        "precision": "year", "qualifier": "as_recorded",
    }
    if "end_gregorian" in record:
        # Pilot provides this independently of the coarser canonical year.
        end_date = {
            "value": record["end_gregorian"],
            "calendar": "gregorian",
            "precision": "day",
            "qualifier": "as_recorded",
        }
    qualifiers = ["This is a world-pilot SOURCE ROLE WINDOW, not a certified"
                  " complete or continuous term of office."]
    if left_clipped:
        qualifiers.append(f"Study-window start {start} is later than"
                          f" explicitly recorded actual_start_year {actual_start};"
                          " true start date is not inferred here.")
    if right_clipped:
        qualifiers.append("End year 1800 may be the study horizon;"
                          " no termination of actual office is asserted.")
    if end_date and end_date["precision"] == "day":
        qualifiers.append("Day precision applies ONLY to the recorded endpoint.")
    qualifiers.append("Year overlaps do not establish same-day co-rule or territorial power.")
    return {
        "id": "v2-period-" + record["id"],
        "start_year": start,
        "end_year": end,
        "start_date_json": dump(begin_date) if begin_date is not None else None,
        "end_date_json": dump(end_date) if end_date is not None else None,
        "meaning": "role_window",
        "note": " ".join(qualifiers),
    }, {
        "left_censored": left_clipped,
        "right_censored": right_clipped,
        "day_endpoint": bool(end_date and end_date["precision"] == "day"),
    }


def validate_records(snapshot: dict) -> dict:
    """P2-specific validation, in addition to unchanged P1 crosswalk checks."""
    p1 = crosswalk.validate(snapshot)
    sources = {s["native_id"]: s for s in crosswalk.source_catalog(snapshot)}
    config = snapshot["crosswalk"]
    contexts = {
        r["native_id"]: c
        for c in config["contexts"] for r in c["refs"]
        if r["origin"] == config["world_context_origin"]
    }
    people = {p["world_id"]: p for p in config["people"]}
    roles, institutions = world_records(snapshot)
    seen = set()
    stats = {"person_roles":len(roles), "institutions":len(institutions),
             "known_original_start_years":0, "day_precision_endpoints":0,
             "right_censored_at_1800":0, "source_links":0}
    for dataset, record in roles + institutions:
        ident=record.get("id")
        require(isinstance(ident,str) and bool(re.fullmatch(r"[a-z0-9-]+",ident)),
                "unsafe source record ID")
        require(ident not in seen, "duplicate world role/institution id " + ident)
        seen.add(ident)
        require(record.get("polity_id") in contexts, "role has unknown context " + ident)
        kind = contexts[record["polity_id"]]["kind"]
        require(kind != "birthplace_context", "birthplace-only context cannot gain a ruler")
        start,end = record.get("start_year"),record.get("end_year")
        require(type(start) is int and type(end) is int and 1<=start<=end<=9999,
                "invalid study-year bounds in " + ident)
        ids=record.get("source_ids")
        require(isinstance(ids,list) and len(ids)>0 and
                all(isinstance(s,str) and s in sources for s in ids) and
                len(set(ids))==len(ids), "missing/ambiguous evidence for " + ident)
        require(isinstance(record.get("note"),str) and bool(record["note"].strip()),
                "source caveat absent in " + ident)
        stats["source_links"]+=len(ids)
        if dataset == ROLE_DATASETS[1] and end == 1800:
            stats["right_censored_at_1800"]+=1
        if (dataset,record) in roles:
            require(record.get("person_id") in people, "unknown person for " + ident)
            require(isinstance(record.get("title"),str) and bool(record["title"].strip()),
                    "missing role title for " + ident)
            require(record.get("role_kind") in ALLOWED_ROLES,
                    "invalid role kind for " + ident)
            require(kind!="elective_office_context" or record["role_kind"]=="emperor",
                    "HRE elective office context cannot be relabelled as a state ruler")
            if "canonical_tenure_id" in record:
                link=people[record["person_id"]]
                require(link["resolution"]=="linked" and
                        link["canonical_tenure_id"]==record["canonical_tenure_id"],
                        "canonical tenure identity mismatch for " + ident)
            if "end_gregorian" in record:
                value=record["end_gregorian"]
                require(isinstance(value,str) and
                        re.fullmatch(r"\d{4}-\d{2}-\d{2}",value) is not None,
                        "unsupported day date for " + ident)
                try:
                    normalized=date.fromisoformat(value)
                except ValueError as exc:
                    raise ValueError("P2: impossible Gregorian day in "+ident) from exc
                require(normalized.year==end, "day endpoint year mismatch in "+ident)
                stats["day_precision_endpoints"]+=1
            if "actual_start_year" in record:
                actual=record["actual_start_year"]
                require(type(actual) is int and 1<=actual<=start,
                        "actual start must not be later than pilot start in "+ident)
                stats["known_original_start_years"]+=1
        else:
            require(dataset==ROLE_DATASETS[1] and
                    record.get("kind") in INSTITUTION_KINDS and
                    isinstance(record.get("name"),str) and bool(record["name"].strip()),
                    "invalid collective institution " + ident)
            require(record["polity_id"]=="frrep",
                    "unexpected institutional context; requires independent review")

    # Not a new historical assertion: only a syntactic proof that the currently
    # three pilot files have matching person-reference semantics.
    require(not snapshot["world"][ROLE_DATASETS[0]]["historical_truth_verified_by_ci"]
            and not snapshot["world"][ROLE_DATASETS[1]]["historical_truth_verified_by_ci"],
            "pilot must not claim verified historical truth")
    stats.update({
        "crosswalk_contexts":p1["unified_contexts"],
        "linked_people":p1["linked_people"],
        "historical_truth_verified_by_ci":False,
    })
    return stats


def period_insert(conn: sqlite3.Connection, period: dict) -> None:
    conn.execute(
        """INSERT INTO v2_periods
            (id,start_year,end_year,start_date_json,end_date_json,meaning,note)
            VALUES(:id,:start_year,:end_year,:start_date_json,:end_date_json,
                   :meaning,:note)""", period)


def assertion_insert(conn: sqlite3.Connection, *, ident: str, dataset: str,
                     record: dict, sources: dict[str, dict], category: str,
                     title: str, period_note: str) -> None:
    origins=[sources[sid] for sid in record["source_ids"]]
    priority={"unverified":0,"imported_not_rechecked":1,
              "reference_checked":2,"primary_checked":3}
    verification=min((s["verification"] for s in origins),key=lambda s:priority[s])
    caveat=(record["note"].strip()+" "+period_note+
            " Source reference_checked is not independent fact verification."
            " A formal or supplementary role never proves actual political control.")
    conn.execute(
        """INSERT INTO v2_assertions
            (id,category,statement,caveat,confidence,verification)
            VALUES(?,?,?,?,?,?)""",
        (ident,category,title,caveat,"not_assessed",verification))
    for source_id in record["source_ids"]:
        sid=sources[source_id]["key"]
        conn.execute(
            """INSERT INTO v2_assertion_sources(assertion_id,source_id,pinpoint)
               VALUES(?,?,?)""",
            (ident,sid,SOURCE_FILE_PREFIX+dataset+"#"+record["id"]))


def import_roles(conn: sqlite3.Connection, snapshot: dict) -> dict:
    """Populate only the experimental overlay, no write to v1 or public JSON."""
    stats=validate_records(snapshot)
    world_origin=snapshot["crosswalk"]["world_context_origin"]
    person_origin=snapshot["crosswalk"]["world_person_origin"]
    context_by_native={
        ref["native_id"]:c["id"]
        for c in snapshot["crosswalk"]["contexts"] for ref in c["refs"]
        if ref["origin"]==world_origin
    }
    persons={p["world_id"]:p for p in snapshot["crosswalk"]["people"]}
    source_map={s["native_id"]:s for s in crosswalk.source_catalog(snapshot)}
    roles,institutions=world_records(snapshot)
    with conn:
        for dataset,record in roles:
            period,flags=role_period(record,dataset)
            period_insert(conn,period)
            role_kind=record["role_kind"]
            category="dynastic" if role_kind in DYNASTIC_ROLES else "legal"
            assertion_id="v2-assert-"+record["id"]
            assertion_insert(conn,ident=assertion_id,dataset=dataset,record=record,
                             sources=source_map,category=category,
                             title=record["title"],period_note=period["note"])
            link=persons[record["person_id"]]
            canonical=link.get("canonical_person_id")
            ext_origin=None if canonical else person_origin
            ext_id=None if canonical else record["person_id"]
            role_id="v2-role-"+record["id"]
            role_origin=snapshot["crosswalk"]["source_namespaces"][dataset]
            conn.execute(
                """INSERT INTO v2_roles
                (id,context_id,person_id,external_person_origin,external_person_id,
                 title,role_kind,period_id,assertion_id,canonical_tenure_id,origin,native_id)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (role_id,context_by_native[record["polity_id"]],canonical,
                 ext_origin,ext_id,record["title"],role_kind,
                 period["id"],assertion_id,record.get("canonical_tenure_id"),
                 role_origin,record["id"]))
            conn.execute(
                """INSERT INTO v2_world_imports
                (origin,native_id,dataset,kind,role_id,raw_json)
                VALUES(?,?,?,?,?,?)""",
                (role_origin,record["id"],dataset,"person_role",role_id,dump(record)))
        for dataset,record in institutions:
            period,flags=role_period(record,dataset)
            period_insert(conn,period)
            institution_id="v2-inst-"+record["id"]
            conn.execute(
                "INSERT INTO v2_institutions(id,label,kind,note) VALUES(?,?,?,?)",
                (institution_id,record["name"],record["kind"],record["note"]))
            assertion_id="v2-assert-"+record["id"]
            assertion_insert(conn,ident=assertion_id,dataset=dataset,record=record,
                             sources=source_map,category="institutional",
                             title=record["name"],period_note=period["note"])
            role_origin=snapshot["crosswalk"]["source_namespaces"][dataset]
            role_id="v2-role-"+record["id"]
            conn.execute(
                """INSERT INTO v2_roles
                (id,context_id,institution_id,title,role_kind,period_id,
                 assertion_id,origin,native_id) VALUES(?,?,?,?,?,?,?,?,?)""",
                (role_id,context_by_native[record["polity_id"]],institution_id,
                 record["name"],"institutional",period["id"],assertion_id,
                 role_origin,record["id"]))
            conn.execute(
                """INSERT INTO v2_world_imports
                (origin,native_id,dataset,kind,institution_id,raw_json)
                VALUES(?,?,?,?,?,?)""",
                (role_origin,record["id"],dataset,"institution",institution_id,
                 dump(record)))

    require(conn.execute("PRAGMA integrity_check").fetchone()[0]=="ok",
            "SQLite integrity_check failure")
    require(not conn.execute("PRAGMA foreign_key_check").fetchall(),
            "SQLite foreign_key_check failure")
    require(not conn.execute("SELECT id FROM v2_assertions_without_sources").fetchall(),
            "assertion without supporting source")
    require(conn.execute("SELECT count(*) FROM v2_world_imports").fetchone()[0] ==
            len(roles)+len(institutions),
            "incomplete source payload preservation")
    return stats


def preview(snapshot: dict) -> tuple[sqlite3.Connection, dict]:
    """Compose the tested P1 preview with additional P2 roles and institutions."""
    conn, p1=crosswalk.in_memory_preview(snapshot)
    try:
        summary=import_roles(conn,snapshot)
        return conn, {"p1":p1,"p2":summary}
    except Exception:
        conn.close()
        raise




def year_candidates(conn: sqlite3.Connection, year: int,
                    context_id: str | None = None) -> list[dict]:
    """Read-only YEAR-CANDIDATE projection; never infer exact simultaneity."""
    require(type(year) is int and 1<=year<=9999, "invalid candidate year")
    sql = """SELECT v.item_id, v.item_kind, v.origin_layer, v.context_id,
                    c.label AS context_label,
                    COALESCE(p.name, ep.display_label, b.name, inst.label)
                      AS actor_label,
                    v.role_kind, v.start_year, v.end_year
             FROM v2_timeline_year_candidates v
             JOIN v2_contexts c ON c.id=v.context_id
             LEFT JOIN people p ON p.id=v.person_id
             LEFT JOIN v2_external_people ep
               ON ep.origin=v.external_person_origin
              AND ep.native_id=v.external_person_id
             LEFT JOIN bodies b ON b.id=v.body_id
             LEFT JOIN v2_institutions inst ON inst.id=v.institution_id
             WHERE v.start_year<=? AND v.end_year>=?"""
    params = [year, year]
    if context_id is not None:
        require(isinstance(context_id,str) and bool(context_id),
                "invalid context identifier")
        sql += " AND v.context_id=?"
        params.append(context_id)
    sql += " ORDER BY c.label,v.origin_layer,v.item_id"
    cursor=conn.execute(sql,params)
    keys=[x[0] for x in cursor.description]
    return [dict(zip(keys,row)) for row in cursor.fetchall()]


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=ROOT)
    parser.add_argument("--year",type=int,help="Inspect a year as a source-candidate slice")
    parser.add_argument("--context",help="Optional v2 context ID, e.g. ctx-world-frrep")
    args=parser.parse_args()
    if args.context and args.year is None:
        parser.error("--context requires --year")
    snap=crosswalk.load_snapshot(args.root)
    snap["root"]=args.root
    conn,result=preview(snap)
    try:
        result["sqlite"]={
            "integrity":conn.execute("PRAGMA integrity_check").fetchone()[0],
            "foreign_key_violations":len(conn.execute("PRAGMA foreign_key_check").fetchall()),
            "user_version":conn.execute("PRAGMA user_version").fetchone()[0],
            "imported_roles":conn.execute("SELECT count(*) FROM v2_roles WHERE institution_id IS NULL").fetchone()[0],
            "collective_institutions":conn.execute("SELECT count(*) FROM v2_institutions").fetchone()[0],
            "assertions_with_sources":conn.execute("SELECT count(DISTINCT assertion_id) FROM v2_assertion_sources").fetchone()[0],
            "timeline_year_candidate_rows":conn.execute(
                "SELECT count(*) FROM v2_timeline_year_candidates").fetchone()[0],
            "world_timeline_candidates_deduped":conn.execute(
                "SELECT count(*) FROM v2_timeline_year_candidates WHERE origin_layer='world-pilot'").fetchone()[0],
        }
        if args.year is not None:
            result["year_candidate_slice"]={
                "year":args.year,
                "context":args.context,
                "warning":"Year overlap is not confirmed same-day rule or practical control.",
                "rows":year_candidates(conn,args.year,args.context),
            }
    finally:
        conn.close()
    print(json.dumps(result,indent=2,ensure_ascii=False,sort_keys=True))


if __name__=="__main__":
    main()
