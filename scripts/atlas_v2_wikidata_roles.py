#!/usr/bin/env python3
"""P4: curated, dated crown-office roles in a disposable Atlas v2 SQLite.

Source contract: a reviewed Wikidata P39 statement + the already source-scoped
historical museum reference from the world pilot. No fuzzy person merge, new
factual-power inference, automated canonical promotion, or Pages mutation.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from scripts import atlas_v2_crosswalk as crosswalk
from scripts import atlas_v2_roles as roles
from scripts import wikidata_sync as wd

ROOT = crosswalk.ROOT
CONFIG = "design/wikidata/curated-crown-roles-v1.json"
P3_REGISTRY = "design/wikidata/jurisdiction-crosswalk-v1.json"
IDENTITY_REGISTRY = "design/wikidata/reviewed-world-links-v1.json"
SQL = "schemas/atlas_v2_wikidata_crowns.sql"
ORIGIN = "wikidata-curated-crowns"
TIME = re.compile(r"^\+([0-9]{4})-([0-9]{2})-([0-9]{2})T00:00:00Z$")
NATIVE_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError("Wikidata P4: " + message)


def read(root: Path, path: str) -> dict:
    return json.loads((root / path).read_text(encoding="utf-8"))


def wd_date(value: dict) -> int:
    """Validate raw P39 time, retaining day/year precision without promotion."""
    require(isinstance(value, dict), "raw time is not an object")
    stamp = value.get("time", "")
    match = TIME.fullmatch(stamp) if isinstance(stamp, str) else None
    require(match is not None, "time is not a supported positive Gregorian timestamp")
    year, month, day = map(int, match.groups())
    precision = value.get("precision")
    require(value.get("calendar") == "gregorian", "calendar not explicitly Gregorian")
    if precision == 9:
        require(month == 0 and day == 0, "year-precision time has invented day")
    elif precision == 11:
        date(year, month, day)
    else:
        require(False, "unsupported Wikidata source time precision")
    require(1 <= year <= 9999, "year outside SQLite v2 date domain")
    return year


def selected_live_claim(subject: dict, item: dict) -> dict | None:
    statements = subject.get("wikidata", {}).get("statements", {}).get("position_held", [])
    statement_id = item["wikidata"]["statement_id"].casefold()
    matches = [x for x in statements if
               isinstance(x.get("statement_id"), str) and
               x["statement_id"].casefold() == statement_id]
    return matches[0] if len(matches) == 1 else None


def live_review(item: dict, live: dict | None) -> str:
    """Flag Wikidata drift; never change a reviewed historical source window."""
    if live is None:
        return "not_checked"
    subjects = [p for p in live.get("records", [])
                if p.get("subject_id") == "world:" + item["world_person_id"]]
    if len(subjects) != 1 or subjects[0].get("wikidata_id") != item["person_qid"]:
        return "source_changed_review_required"
    claim = selected_live_claim(subjects[0], item)
    if claim is None or claim.get("rank") != "normal":
        return "source_changed_review_required"
    if claim.get("value", {}).get("qid") != item["position_qid"]:
        return "source_changed_review_required"
    for field, qualifier in (("start", "P580"), ("end", "P582")):
        values = claim.get("qualifiers", {}).get(qualifier, [])
        if len(values) != 1 or values[0].get("time") is None:
            return "source_changed_review_required"
        actual = values[0]["time"]
        expected = item["wikidata"][field]
        if any(actual.get(k) != expected[k] for k in ("time", "precision", "calendar")):
            return "source_changed_review_required"
    return "matches_reviewed_snapshot"


def validate_seed(root: Path, snapshot: dict, live: dict | None = None) -> tuple[dict, list[dict]]:
    seed = read(root, CONFIG)
    require(seed.get("schema_version") == "wikidata-curated-crown-roles-v1",
            "unknown role-seed version")
    require(seed.get("status") == "reviewed_reference_based_experimental",
            "role seed has not been reviewed")
    require(seed.get("historical_truth_verified_by_ci") is False,
            "no automatic claim of historical truth")
    window = seed.get("pilot_window", {})
    start, end = window.get("from_year"), window.get("to_year")
    require(type(start) is int and type(end) is int and start == 1762 and end == 1800,
            "pilot study horizon must remain explicit 1762–1800")
    require(not (live and live.get("schema_version") != "wikidata-reconciliation-v1"),
            "invalid live Wikidata report schema")
    if live:
        require(live.get("mutated_canonical_data") is False and
                live.get("historical_truth_verified") is False,
                "live audit must never be a canonical import")
    identities = read(root, IDENTITY_REGISTRY)
    ids = {x["world_id"]: x["wikidata_qid"] for x in identities["links"]}
    require(len(ids) == len(identities["links"]), "duplicate curated world QIDs")
    jurisdiction = read(root, P3_REGISTRY)
    scopes = {x["id"]: x for x in jurisdiction["contexts"]
              if x["kind"] == "historic_crown"}
    scope_offices = {x["context_id"]: x for x in jurisdiction["offices"]
                     if x["position_kind"] == "legal_crown"}
    require(len(scopes) == 2 and set(scopes) == set(scope_offices),
            "exactly the two independently typed crowns are required")
    require(set(scopes) == {"ctx-hab-crown-bohemia", "ctx-hab-crown-hungary"},
            "unapproved crown context")
    context_ids = {c["id"] for c in snapshot["crosswalk"]["contexts"]}
    require("ctx-world-hab" in context_ids and not set(scopes) & context_ids,
            "crown contexts must be new and separate from composite Habsburg")
    for scope in scopes.values():
        require(scope["kind"] == "historic_crown" and
                scope["relationship"] == "related_not_equivalent" and
                scope["same_as_canonical_state"] is False and
                scope["geographic_boundaries_verified"] is False and
                "world:hab" in scope["related_world_contexts"],
                "crown must not become modern sovereign territory")
    world_people = {p["world_id"]: p for p in snapshot["crosswalk"]["people"]}
    source_filenames = {"dynasty-1762-1780.json", "extension-1781-1800.json"}
    rows = seed.get("roles")
    require(isinstance(rows, list) and len(rows) > 0, "no curated crown evidence")
    seen, claims, pairs = set(), set(), set()
    enriched = []
    for row in rows:
        key = row.get("id")
        person = row.get("world_person_id")
        scid = row.get("context_id")
        qid = row.get("person_qid")
        wdsource = row.get("wikidata", {})
        source_file = row.get("source_dataset")
        source_id = row.get("source_id")
        require(isinstance(key, str) and NATIVE_ID.fullmatch(key) and key not in seen,
                "invalid or repeated role key: " + str(key))
        seen.add(key)
        require(person in world_people and
                world_people[person].get("resolution") == "unresolved",
                "world person is not a separate, explicitly foreign pilot person")
        require(qid == ids.get(person) and isinstance(qid, str) and wd.QID.fullmatch(qid),
                "QID is not the reviewed world person identity")
        require(scid in scopes and row.get("position_qid") ==
                scope_offices[scid]["wikidata_qid"], "QID does not match legal crown scope")
        require(row.get("role_kind") == "sovereign" and
                (person, scid) not in pairs, "duplicate scope role or non-legal-role import")
        pairs.add((person, scid))
        require(source_file in source_filenames and
                source_file == world_people[person]["dataset"], "wrong source/person dataset")
        source_lookup = {s["id"]: s for s in snapshot["world"][source_file]["sources"]}
        require(source_id in source_lookup and
                source_lookup[source_id].get("verification") == "reference_checked",
                "museum reference is missing or not source-reviewed")
        official = source_lookup[source_id]["url"]
        require(urlsplit(official).hostname == "www.habsburger.net" and
                urlsplit(row.get("independent_reference_url", "")).hostname ==
                "www.habsburger.net", "unapproved source URL domain")
        require(isinstance(wdsource, dict) and
                type(wdsource.get("entity_revision")) is int and
                wdsource["entity_revision"] > 0 and
                wdsource.get("rank") == "normal", "source rank/revision missing")
        statement = wdsource.get("statement_id")
        require(isinstance(statement, str) and statement.casefold().startswith(
                (qid + "$").casefold()) and statement.casefold() not in claims,
                "Wikidata statement ID absent, foreign or duplicated")
        claims.add(statement.casefold())
        from_year, to_year = wd_date(wdsource["start"]), wd_date(wdsource["end"])
        require(from_year == row.get("recorded_start_year") and
                to_year == row.get("recorded_end_year") and
                from_year <= to_year and
                from_year <= end and to_year >= start,
                "source P39 period does not match reviewed claim or study window")
        require(row.get("verification") == "reference_checked" and
                row.get("confidence") == "not_assessed" and
                isinstance(row.get("caveat"), str) and len(row["caveat"]) >= 80,
                "source qualifiers are insufficient")
        require(isinstance(row.get("title"), str) and row["title"].strip(),
                "missing distinct legal crown title")
        enriched.append({
            **row,
            "window_start": max(from_year, start),
            "window_end": min(to_year, end),
            "left_censored": from_year < start,
            "right_censored": to_year > end,
            "live_comparison": live_review(row, live),
        })
    return seed, enriched


def import_roles(conn: sqlite3.Connection, root: Path, snapshot: dict,
                 live: dict | None = None) -> dict:
    seed, rows = validate_seed(root, snapshot, live)
    jurisdictions = read(root, P3_REGISTRY)
    sc = {x["id"]: x for x in jurisdictions["contexts"]
          if x["kind"] == "historic_crown"}
    statement_qids = sorted({row["person_qid"] for row in rows})
    src = {s["native_id"]: s for s in crosswalk.source_catalog(snapshot)}
    origin = snapshot["crosswalk"]["world_person_origin"]
    with conn:
        for scope_id in sorted(sc):
            item = sc[scope_id]
            conn.execute(
                "INSERT INTO v2_contexts(id,label,kind,note) VALUES(?,?,?,?)",
                (scope_id,item["label"],"other_context",
                 item["caveat"]+" Distinct historic crown, not a geographic polygon."))
            office = next(x for x in jurisdictions["offices"]
                          if x["context_id"] == scope_id and
                          x["position_kind"] == "legal_crown")
            conn.execute(
                """INSERT INTO v2_wikidata_crown_contexts
                   (context_id,related_parent_context_id,position_qid,kind,
                    relation,same_as_parent,geographic_boundaries_verified,
                    power_asserted,caveat)
                   VALUES(?,?,?,?,?,0,0,0,?)""",
                (scope_id,"ctx-world-hab",office["wikidata_qid"],
                 "historic_crown","related_not_equivalent",item["caveat"]))
        for qid in statement_qids:
            conn.execute(
                """INSERT INTO v2_sources
                   (id,origin,native_id,title,url,verification)
                   VALUES(?,?,?,?,?,?)""",
                ("p4:wikidata:"+qid,"wikidata-action-p39",qid,
                 "Wikidata P39 item "+qid+" (reviewed snapshot)",
                 "https://www.wikidata.org/wiki/"+qid,"imported_not_rechecked"))
        for row in rows:
            role_id = "v2-role-wd-"+row["id"]
            period_id = "v2-period-wd-"+row["id"]
            assertion_id = "v2-assert-wd-"+row["id"]
            begin = None if row["left_censored"] else {
                "value":str(row["window_start"]),"calendar":"unspecified",
                "precision":"year","qualifier":"as_recorded",
            }
            finish = None if row["right_censored"] else {
                "value":str(row["window_end"]),"calendar":"unspecified",
                "precision":"year","qualifier":"as_recorded",
            }
            caveat = (row["caveat"] +
                      " The displayed source scope is a year-filtering window. "
                      "Original P39 time precision and calendar preserved "
                      "separately, NOT asserted as an independently verified "
                      "accession/abdication day. " +
                      ("Left-censored at 1762. " if row["left_censored"] else "") +
                      ("Right-censored at 1800, not a reign end. "
                       if row["right_censored"] else "") +
                      ("Wikidata claim drift: manual review required. "
                       if row["live_comparison"] == "source_changed_review_required" else ""))
            conn.execute(
                """INSERT INTO v2_periods
                   (id,start_year,end_year,start_date_json,end_date_json,meaning,note)
                   VALUES(?,?,?,?,?,'role_window',?)""",
                (period_id,row["window_start"],row["window_end"],
                 roles.dump(begin) if begin else None,
                 roles.dump(finish) if finish else None,caveat))
            conn.execute(
                """INSERT INTO v2_assertions
                   (id,category,statement,caveat,confidence,verification)
                   VALUES(?,'legal',?,?,'not_assessed','reference_checked')""",
                (assertion_id,row["title"],caveat))
            role_src = src[row["source_id"]]
            wd_src = "p4:wikidata:"+row["person_qid"]
            conn.execute(
                "INSERT INTO v2_assertion_sources(assertion_id,source_id,pinpoint) "
                "VALUES(?,?,?)",
                (assertion_id,role_src["key"],
                 "data/atlas/world-pilots/"+row["source_dataset"]+"#"+row["source_id"]))
            conn.execute(
                "INSERT INTO v2_assertion_sources(assertion_id,source_id,pinpoint) "
                "VALUES(?,?,?)",
                (assertion_id,wd_src,row["wikidata"]["statement_id"]))
            conn.execute(
                """INSERT INTO v2_roles
                   (id,context_id,external_person_origin,external_person_id,
                    title,role_kind,period_id,assertion_id,origin,native_id)
                   VALUES(?,?,?,?,?,'sovereign',?,?,?,?)""",
                (role_id,row["context_id"],origin,row["world_person_id"],
                 row["title"],period_id,assertion_id,ORIGIN,row["id"]))
            conn.execute(
                """INSERT INTO v2_wikidata_crown_claims
                   (role_id,context_id,external_person_origin,external_person_id,
                    person_qid,position_qid,statement_id,original_revid,
                    original_start_year,original_end_year,
                    candidate_start_year,candidate_end_year,
                    left_censored,right_censored,live_comparison,
                    original_start_json,original_end_json,
                    official_source_id,wikidata_source_id,
                    independent_primary_act_checked,territorial_power_inferred,
                    source_record_json)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,0,?)""",
                (role_id,row["context_id"],origin,row["world_person_id"],
                 row["person_qid"],row["position_qid"],
                 row["wikidata"]["statement_id"],row["wikidata"]["entity_revision"],
                 row["recorded_start_year"],row["recorded_end_year"],
                 row["window_start"],row["window_end"],
                 int(row["left_censored"]),int(row["right_censored"]),
                 row["live_comparison"],roles.dump(row["wikidata"]["start"]),
                 roles.dump(row["wikidata"]["end"]),role_src["key"],wd_src,
                 roles.dump({k:v for k,v in row.items() if k not in
                             {"window_start","window_end","left_censored",
                              "right_censored","live_comparison"}})))
    require(conn.execute("PRAGMA integrity_check").fetchone()[0]=="ok",
            "SQLite integrity check failed")
    require(conn.execute("PRAGMA foreign_key_check").fetchall()==[],
            "SQLite foreign keys broken")
    require(conn.execute("SELECT count(*) FROM v2_assertions_without_sources").fetchone()[0]==0,
            "claims without sources")
    require(conn.execute("PRAGMA user_version").fetchone()[0]==1,
            "never migrate canonical v1 in-place")
    require(conn.execute("SELECT count(*) FROM v2_wikidata_crown_claims").fetchone()[0]
            ==len(rows), "not all source roles were preserved")
    counts = {status:sum(r["live_comparison"]==status for r in rows)
              for status in ("not_checked","matches_reviewed_snapshot",
                             "source_changed_review_required")}
    return {
        "source_role_count":len(rows),
        "typed_crown_contexts":len(sc),
        "distinct_people":len({row["world_person_id"] for row in rows}),
        "reference_links":len(rows)*2,
        "left_censored":sum(row["left_censored"] for row in rows),
        "right_censored":sum(row["right_censored"] for row in rows),
        "source_comparison":counts,
        "historical_truth_verified_by_ci":False,
        "actual_power_inferred":False,
    }


def preview(root: Path = ROOT, live: dict | None = None) -> tuple[sqlite3.Connection, dict]:
    snapshot = crosswalk.load_snapshot(root)
    snapshot["root"] = root
    conn, parent = roles.preview(snapshot)
    try:
        conn.executescript((root / SQL).read_text(encoding="utf-8"))
        info = import_roles(conn,root,snapshot,live)
        return conn, {"p1_p2":parent,"wikidata_p4":info}
    except BaseException:
        conn.close()
        raise


def year_candidates(conn: sqlite3.Connection, year: int,
                    context_id: str | None = None) -> list[dict]:
    require(type(year) is int and 1 <= year <= 9999,
            "invalid timeline year")
    sql = """SELECT * FROM v2_wikidata_crown_year_candidates
             WHERE start_year<=? AND end_year>=?"""
    params = [year,year]
    if context_id is not None:
        require(isinstance(context_id,str) and bool(context_id),
                "invalid context filter")
        sql += " AND context_id=?"
        params.append(context_id)
    sql += " ORDER BY context_id,world_person_id"
    cursor = conn.execute(sql,params)
    return [dict(zip([c[0] for c in cursor.description],row))
            for row in cursor.fetchall()]


def report(conn: sqlite3.Connection, info: dict, *,
           year: int = 1790) -> dict:
    rows = conn.execute(
        """SELECT c.role_id,c.external_person_id,c.person_qid,c.position_qid,
                  c.statement_id,c.context_id,c.original_start_year,
                  c.original_end_year,c.candidate_start_year,c.candidate_end_year,
                  c.left_censored,c.right_censored,c.live_comparison,
                  c.source_record_json
           FROM v2_wikidata_crown_claims c ORDER BY c.context_id,c.candidate_start_year"""
    ).fetchall()
    return {
        "schema_version":"wikidata-curated-v2-world-role-pilot-v1",
        "research_status":"source_reviewed_experimental",
        "historical_truth_verified_by_ci":False,
        "claim_of_actual_power":False,
        "geographic_boundaries_verified":False,
        "counts":info["wikidata_p4"],
        "sqlite_integrity":conn.execute("PRAGMA integrity_check").fetchone()[0],
        "sqlite_user_version":conn.execute("PRAGMA user_version").fetchone()[0],
        "roles":[{
            "role_id":row[0],"world_person_id":row[1],"person_qid":row[2],
            "position_qid":row[3],"statement_id":row[4],"context_id":row[5],
            "original_start_year":row[6],"original_end_year":row[7],
            "window_start_year":row[8],"window_end_year":row[9],
            "left_censored":bool(row[10]),"right_censored":bool(row[11]),
            "source_status":row[12],"source_record":json.loads(row[13])
        } for row in rows],
        "sample_year":year,
        "year_candidates":year_candidates(conn,year),
        "method":("Crown/royal offices are distinct source-qualified juridical "
                  "roles, not a count of fully independent rulers. Multiple roles "
                  "may belong to one person; same-year overlaps are not same-day "
                  "co-rule or factual territorial control. 1762/1800 may be "
                  "a research clip, not actual accession or office termination."),
    }


def to_markdown(result: dict) -> str:
    n=result["counts"]
    lines=["# Wikidata P4 — juridical crown roles in Atlas v2","",
           "Experimental source-reviewed timeline, **not** verified practical authority.",
           "The original v1 canon, poster and production Pages were not changed.","",
           f"Added **{n['source_role_count']}** crown-role assertions for "
           f"**{n['distinct_people']}** separately identified world-pilot people.",
           f"Distinct crowns: **{n['typed_crown_contexts']}**; "
           f"left-censored: **{n['left_censored']}**; "
           f"right-censored: **{n['right_censored']}**.","",
           "| Person ID | Crown | Observed source term | Pilot year window | Live source |",
           "| --- | --- | --- | --- | --- |"]
    for row in result["roles"]:
        lines.append(
            f"| {row['world_person_id']} | {row['context_id']} | "
            f"{row['original_start_year']}–{row['original_end_year']} | "
            f"{row['window_start_year']}–{row['window_end_year']} | "
            f"{row['source_status']} |")
    lines += ["",
              f"## Year {result['sample_year']} — **candidates**, not proven concurrent rule",""]
    for x in result["year_candidates"]:
        lines.append(f"- {x['actor_label']}: {x['context_label']} "
                     f"({x['start_year']}–{x['end_year']})")
    lines += ["","Each claim has a source-scoped museum reference plus a pinned "
              "Wikidata P39 statement/revision. Wikidata day dates remain "
              "source evidence, not a guaranteed legal day of accession.",
              "No personal union, dynasty, ethnicity, geography, or factual "
              "power is deduced from multiple legal titles.",""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=ROOT)
    parser.add_argument("--wikidata-report",type=Path,
                        help="optional latest.json to detect changing P39 claims")
    parser.add_argument("--year",type=int,default=1790)
    parser.add_argument("--context",type=str)
    parser.add_argument("--json-output",type=Path,
                        default=Path("reports/wikidata/curated-crowns.json"))
    parser.add_argument("--markdown-output",type=Path,
                        default=Path("reports/wikidata/curated-crowns.md"))
    parser.add_argument("--sqlite-output",type=Path,
                        help="write disposable v2 SQLite preview; never canonical atlas.sqlite")
    args=parser.parse_args(argv)
    live = json.loads(args.wikidata_report.read_text(encoding="utf-8")
                      ) if args.wikidata_report else None
    conn,info=preview(args.root,live)
    try:
        result=report(conn,info,year=args.year)
        if args.context:
            result["year_candidates"]=year_candidates(conn,args.year,args.context)
        for filename,payload in (
            (args.json_output,json.dumps(result,ensure_ascii=False,
                                         sort_keys=True,indent=2)+"\n"),
            (args.markdown_output,to_markdown(result)),
        ):
            filename.parent.mkdir(parents=True,exist_ok=True)
            filename.write_text(payload,encoding="utf-8")
        if args.sqlite_output is not None:
            args.sqlite_output.parent.mkdir(parents=True,exist_ok=True)
            require(args.sqlite_output.name!="atlas.sqlite",
                    "cannot overwrite canonical atlas.sqlite")
            require(not args.sqlite_output.exists(), "refusing to overwrite SQLite")
            destination=sqlite3.connect(args.sqlite_output)
            try:
                conn.backup(destination)
                require(destination.execute("PRAGMA integrity_check").fetchone()[0]
                        =="ok", "backed-up SQLite failed integrity check")
            finally:
                destination.close()
        print(json.dumps(result["counts"],ensure_ascii=False,sort_keys=True))
    finally:
        conn.close()
    return 0


if __name__=="__main__":
    raise SystemExit(main())
