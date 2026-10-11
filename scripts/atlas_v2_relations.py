"""P3: lossless historical relationship/house graph over disposable P2 SQLite.

All historical assertions are sourced, candidate-level and time-qualified.
Keeps raw pilot relationship evidence (29 records) while 2 aliases explicitly
resolve to earlier repeated events, yielding 27 typed normalized relations.
No mutation of canonical data, generated v1 SQLite, Pages, or original image.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path

from scripts import atlas_v2_crosswalk as p1
from scripts import atlas_v2_roles as p2

ROOT = p1.ROOT
BASE = "1762.json"
DYNASTY = "dynasty-1762-1780.json"
EXTENSION = "extension-1781-1800.json"
FOOTPRINTS = "dynasty-footprints-1762-1800.json"
REL_DATASETS = (BASE, DYNASTY, EXTENSION)
ALIAS_FILE = "design/atlas-v2/relationship-aliases.json"

KINSHIP = frozenset({"marriage", "parent"})
POLITICAL = frozenset({"imperial_succession", "co_regency", "succession", "regency"})
INTERSTATE = frozenset({"personal_union", "treaty"})
INSTITUTIONAL = frozenset({"regime_change", "institutional_change"})
EVENTS = frozenset({"imperial_succession", "succession", "treaty",
                    "regime_change", "institutional_change"})
AFFILIATIONS = {
    "house": "documented_house",  # NOT automatically official dynasty
    "dynastic_union": "dynastic_union",  # NOT birth affiliation
    "branch_lineage": "branch_lineage",  # NOT an official house change
}
CAVEAT = (
    "This is a cited pilot assertion, NOT verified historical truth. "
    "Relation periods are source-evidence windows, never automatically entire "
    "lifespans or full reigns. Shared house or marriage does not demonstrate "
    "ethnicity, same-day co-rule, political jurisdiction or actual control."
)


def require(value: bool, why: str) -> None:
    p1.require(value, "P3: " + why)


def encoded(value) -> str:
    return p2.dump(value)


def alias_config(snapshot: dict) -> dict:
    return snapshot.get("relation_aliases") or p1.read_json(
        snapshot.get("root", ROOT) / ALIAS_FILE)


def source_map(snapshot: dict) -> dict:
    source_rows = p1.source_catalog(snapshot)
    return {r["native_id"]: r for r in source_rows}


def source_ids_ok(ids, source_lookup: dict) -> bool:
    return (isinstance(ids, list) and len(ids) > 0
            and all(isinstance(s, str) and s in source_lookup for s in ids)
            and len(ids) == len(set(ids)))


def world_relations(snapshot: dict) -> tuple[list[tuple[str, dict]],
                                              list[tuple[str, dict]]]:
    w = snapshot["world"]
    all_records = [(BASE, r) for r in w[BASE]["relations"]]
    all_records += [(DYNASTY, r) for r in w[DYNASTY]["relations"]]
    all_records += [(EXTENSION, r) for r in w[EXTENSION]["additional_relations"]]
    authoritative = [(d,r) for d,r in all_records if d != BASE]
    return all_records, authoritative


def raw_participants(relation: dict, dataset: str) -> tuple[list[str], list[str]]:
    if dataset == BASE:
        k = relation["kind"]
        if k == "marriage":
            return [relation["from"],relation["to"]], []
        if k == "treaty":
            return [], [relation["from"],relation["to"]]
        raise ValueError("P3: unknown base relationship type " + k)
    return relation.get("subjects",[]), relation.get("polity_ids",[])


def relation_domain(kind: str) -> str:
    if kind in KINSHIP:
        return "kinship"
    if kind in POLITICAL:
        return "political_roles"
    if kind in INTERSTATE:
        return "interstate"
    if kind in INSTITUTIONAL:
        return "institutional"
    raise ValueError("P3: unexpected relationship kind " + str(kind))


def normalized_relation(alias: dict, dataset: str, native_id: str) -> str:
    entry = next((x for x in alias["aliases"]
                  if x["dataset"] == dataset and x["native_id"] == native_id), None)
    return entry["canonical_id"] if entry else native_id


def relations_validate(snapshot: dict) -> dict:
    p2.validate_records(snapshot)
    w = snapshot["world"]
    alias = alias_config(snapshot)
    require(alias["schema_version"] == "p3-explicit-aliases-v1"
            and alias["status"] == "draft_not_canonical"
            and alias["historical_truth_verified_by_ci"] is False,
            "invalid alias contract")
    sources = source_map(snapshot)
    known_people = {p["world_id"] for p in snapshot["crosswalk"]["people"]}
    known_polities = {p["id"] for p in w[BASE]["countries"]}
    known_polities |= {p["id"] for p in w[DYNASTY]["additional_polities"]}
    known_polities |= {p["id"] for p in w[EXTENSION]["additional_polities"]}

    all_rel, normalized = world_relations(snapshot)
    registry = {}
    for dataset,r in all_rel:
        rid = r.get("id")
        require(isinstance(rid,str) and re.fullmatch(r"[a-z0-9-]+",rid) is not None,
                "invalid relation identifier")
        require(rid not in registry, "duplicate relation ID " + rid)
        registry[rid] = (dataset,r)
        kind=r.get("kind")
        domain=relation_domain(kind)
        people,political_contexts = raw_participants(r,dataset)
        require(isinstance(people,list) and isinstance(political_contexts,list)
                and all(isinstance(p,str) and p in known_people for p in people)
                and all(isinstance(c,str) and c in known_polities
                        for c in political_contexts),
                "relationship subject/context references unknown for " + rid)
        require(len(set(people))==len(people)
                and len(set(political_contexts))==len(political_contexts),
                "repeated relationship participant in " + rid)
        expected = {
            "personal_union":(1,2),"marriage":(2,0),"parent":(2,0),
            "co_regency":(2,0),"regency":(2,0),
            "succession":(2,0),"imperial_succession":(2,0),
            "treaty":(0,2),"regime_change":(0,2),
            "institutional_change":(0,1),
        }[kind]
        require((len(people),len(political_contexts))==expected,
                "relationship kind/participant mismatch for "+rid)
        require(source_ids_ok(r.get("sources" if dataset==BASE else "source_ids"),sources),
                "relationship evidence absent or duplicated for "+rid)
        note = r.get("detail") if dataset==BASE else r.get("note")
        title = r.get("label") if dataset==BASE else r.get("title")
        require(isinstance(title,str) and bool(title.strip())
                and isinstance(note,str) and bool(note.strip()),
                "relationship title/caveat missing "+rid)
        if dataset != BASE:
            lo,hi = r.get("start_year"),r.get("end_year")
            require(type(lo) is int and type(hi) is int and 1<=lo<=hi<=9999,
                    "invalid relation evidence year-window "+rid)
            event=r.get("event_year")
            require(event is None or
                    (type(event) is int and 1<=event<=9999 and
                     (event<=hi or kind in KINSHIP)),
                    "event year invalid "+rid)
            if kind in EVENTS:
                require(event is not None or lo==hi,
                        "one-time event without event year "+rid)

    declared_aliases=alias["aliases"]
    require(len(declared_aliases)==2, "unexpected set of duplicate source records")
    require(set((a["dataset"],a["native_id"],a["canonical_id"])
                for a in declared_aliases)=={
                (BASE,"wp-marriage-1745","dn-ru-marriage"),
                (BASE,"wp-petersburg-peace","dn-ru-pr-peace"),
            }, "unreviewed relation alias change")
    for entry in declared_aliases:
        src=registry.get(entry["native_id"])
        dst=registry.get(entry["canonical_id"])
        require(src is not None and dst is not None and
                src[0]==entry["dataset"] and dst[0]==entry["canonical_dataset"]
                and src[1]["kind"]==dst[1]["kind"]==entry["kind"]
                and bool(entry["reason"]),
                "invalid explicit alias "+entry["native_id"])
        a_people,a_context=raw_participants(src[1],src[0])
        b_people,b_context=raw_participants(dst[1],dst[0])
        require(a_people==b_people and a_context==b_context
                and set(src[1]["sources"])==set(dst[1]["source_ids"]),
                "alias evidence or participants differ "+entry["native_id"])
    require(len(normalized) + len(declared_aliases) == len(all_rel),
            "some original relationship observations missing")
    require(set(r["id"] for _,r in normalized) ==
            set(r["id"] for _,r in all_rel) -
            {a["native_id"] for a in declared_aliases},
            "normalization contains unexpected relation")

    footprints = w[FOOTPRINTS]
    require(footprints["historical_truth_verified_by_ci"] is False,
            "family footprint set claims historical truth")
    house_ids=set()
    seen_aff=set()
    affiliations=0
    for family in footprints["families"]:
        fid=family.get("id")
        require(isinstance(fid,str) and fid not in house_ids and
                bool(family.get("name")) and bool(family.get("description")),
                "invalid or duplicate house")
        house_ids.add(fid)
        require(source_ids_ok(family.get("source_ids"),sources),
                "house without evidence: "+fid)
        for member in family["members"]:
            pid=member.get("person_id")
            require(pid in known_people, "unknown house member "+str(pid))
            pair=(fid,pid)
            require(pair not in seen_aff, "duplicate house affiliation")
            seen_aff.add(pair)
            require(member.get("membership") in AFFILIATIONS,
                    "unrecognized house membership: "+str(pid))
            require(source_ids_ok(member.get("source_ids"),sources)
                    and bool(member.get("branch")),
                    "house member missing evidence or qualifier "+str(pid))
            affiliations+=1

    # The relations are samples from a research pilot, not the whole history of
    # all marriages/parenthood. Additional historical links are NOT inferred.
    return {
        "historical_truth_verified_by_ci":False,
        "world_relationship_evidence":len(all_rel),
        "normalized_relationships":len(normalized),
        "explicit_relation_aliases":len(declared_aliases),
        "relation_kinds":dict(sorted({k:sum(r["kind"]==k for _,r in normalized)
                                   for k in set(r["kind"] for _,r in normalized)}.items())),
        "houses":len(house_ids),
        "documented_house_memberships":affiliations,
        "birthplace_or_nationality_inferred":False,
    }


def assertion(conn: sqlite3.Connection, snapshot: dict, name: str, label: str,
              note: str, category: str, ids: list[str], pinpoint: str):
    catalog=source_map(snapshot)
    require(source_ids_ok(ids,catalog), "assertion without evidence "+name)
    order={"unverified":0,"imported_not_rechecked":1,"reference_checked":2,"primary_checked":3}
    verification=min((catalog[i]["verification"] for i in ids),key=lambda k:order[k])
    conn.execute(
        """INSERT INTO v2_assertions
           (id,category,statement,caveat,confidence,verification)
           VALUES (?,?,?,?,?,?)""",
        (name,category,label,note.strip()+" "+CAVEAT,"not_assessed",verification))
    for sid in ids:
        conn.execute("""INSERT INTO v2_assertion_sources
                     (assertion_id,source_id,pinpoint) VALUES(?,?,?)""",
                     (name,catalog[sid]["key"],pinpoint))


def relation_period(relation: dict) -> dict:
    kind=relation["kind"]
    lo,hi=relation["start_year"],relation["end_year"]
    ev=relation.get("event_year")
    if kind in EVENTS:
        # Change events are not 'active' for the remainder of a research window.
        year=ev if ev is not None else lo
        start=end=year
        meaning="event"
        note=("Dated ONE-TIME event candidate. Original observation window "
              f"{lo}–{hi} is preserved separately, not treated as continuing "
              "succession/war/constitutional transition.")
    else:
        start,end=lo,hi
        meaning="relation_evidence_window"
        note=("Source-scoped evidence window, NOT the birth year of a child, "
              "not proven entire marital lifetime and not continuous political "
              "control. No day-level inference.")
    return {
        "id":"v2-p3-period-"+relation["id"],
        "start_year":start,"end_year":end,
        "start_date_json":None,"end_date_json":None,
        "meaning":meaning,"note":note,
    }


def import_relations(conn: sqlite3.Connection, snapshot: dict) -> dict:
    summary=relations_validate(snapshot)
    config=snapshot["crosswalk"]
    world_origin=config["world_context_origin"]
    person_origin=config["world_person_origin"]
    house_origin=config["source_namespaces"][FOOTPRINTS]
    context_ids={r["native_id"]:c["id"] for c in config["contexts"]
                 for r in c["refs"] if r["origin"]==world_origin}
    people={p["world_id"]:p for p in config["people"]}
    all_rel,norm_rel=world_relations(snapshot)
    aliases=alias_config(snapshot)
    with conn:
        # Four curated and sourced house footprints; not a complete genealogical index.
        for house in snapshot["world"][FOOTPRINTS]["families"]:
            house_id="v2-house-"+house["id"]
            conn.execute("INSERT INTO v2_houses(id,name,note) VALUES(?,?,?)",
                         (house_id,house["name"],house["description"]))
            claim="v2-p3-claim-house-"+house["id"]
            assertion(conn,snapshot,claim,house["name"],house["description"],
                      "dynastic",house["source_ids"],FOOTPRINTS+"#"+house["id"])
            conn.execute("""INSERT INTO v2_house_imports
                (origin,native_id,house_id,assertion_id,raw_json)
                VALUES(?,?,?,?,?)""",
                (house_origin,house["id"],house_id,claim,encoded(house)))
            for member in house["members"]:
                pid=member["person_id"]
                affiliation_id="v2-p3-aff-"+house["id"]+"-"+pid
                claim="v2-p3-claim-aff-"+house["id"]+"-"+pid
                assertion(conn,snapshot,claim,
                          house["name"]+": "+pid,
                          member["branch"],
                          "dynastic",member["source_ids"],
                          FOOTPRINTS+"#"+house["id"]+"."+pid)
                canon=people[pid].get("canonical_person_id")
                conn.execute("""INSERT INTO v2_house_affiliations
                    (id,house_id,person_id,external_person_origin,external_person_id,
                     affiliation,branch_label,period_id,assertion_id)
                    VALUES(?,?,?,?,?,?,?,?,?)""",
                    (affiliation_id,house_id,canon,
                     None if canon else person_origin,
                     None if canon else pid,
                     AFFILIATIONS[member["membership"]],
                     member["branch"],None,claim))
                conn.execute("""INSERT INTO v2_affiliation_imports
                    (origin,native_id,affiliation_id,raw_json)
                    VALUES(?,?,?,?)""",
                    (house_origin,house["id"]+":"+pid,affiliation_id,encoded(member)))

        # Create 27 normalized facts: no fanout through duplicate source entries.
        for dataset,record in norm_rel:
            native=record["id"]
            kind=record["kind"]
            domain=relation_domain(kind)
            period=relation_period(record)
            p2.period_insert(conn,period)
            claim="v2-p3-claim-rel-"+native
            evidence=record["source_ids"]
            assertion(conn,snapshot,claim,record["title"],record["note"],
                      "dynastic" if domain=="kinship" else
                      "institutional" if domain=="institutional" else
                      "legal" if domain=="political_roles" else "chronology",
                      evidence,dataset+"#"+native)
            rel_id="v2-p3-rel-"+native
            origin=config["source_namespaces"][dataset]
            conn.execute(
                """INSERT INTO v2_relationships
                 (id,kind,domain,period_id,event_year,assertion_id,title,
                  note,origin,native_id) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (rel_id,kind,domain,period["id"],record.get("event_year"),
                 claim,record["title"],record["note"],origin,native))
            subjects,contexts=raw_participants(record,dataset)
            for position,pid in enumerate(subjects,1):
                canon=people[pid].get("canonical_person_id")
                conn.execute("""INSERT INTO v2_relationship_people
                    (relation_id,position,person_id,external_person_origin,external_person_id)
                    VALUES(?,?,?,?,?)""",
                    (rel_id,position,canon,None if canon else person_origin,
                     None if canon else pid))
            for position,cid in enumerate(contexts,1):
                conn.execute("""INSERT INTO v2_relationship_contexts
                    (relation_id,position,context_id) VALUES(?,?,?)""",
                    (rel_id,position,context_ids[cid]))
            if kind=="personal_union":
                sole=subjects[0]
                canon=people[sole].get("canonical_person_id")
                conn.execute("""INSERT INTO v2_context_relations
                  (id,context_a,context_b,kind,person_id,external_person_origin,
                   external_person_id,period_id,assertion_id)
                  VALUES(?,?,?,?,?,?,?,?,?)""",
                  ("v2-p3-union-"+native,context_ids[contexts[0]],
                   context_ids[contexts[1]],kind,
                   canon,None if canon else person_origin,None if canon else sole,
                   period["id"],claim))

        # Preserve ALL 29 raw relation records. Two base relations share a
        # normalized relation with the already documented dynasty pilot;
        # neither source row, its source links nor its content is thrown away.
        for dataset,record in all_rel:
            alias=next((a for a in aliases["aliases"]
                        if a["dataset"]==dataset and a["native_id"]==record["id"]),None)
            target=alias["canonical_id"] if alias else record["id"]
            origin=config["source_namespaces"][dataset]
            conn.execute("""INSERT INTO v2_relationship_imports
                (origin,native_id,dataset,relationship_id,raw_json,alias_of)
                VALUES(?,?,?,?,?,?)""",
                (origin,record["id"],dataset,"v2-p3-rel-"+target,encoded(record),
                 "v2-p3-rel-"+target if alias else None))

    require(conn.execute("PRAGMA integrity_check").fetchone()[0]=="ok",
            "SQLite integrity_check failed")
    require(not conn.execute("PRAGMA foreign_key_check").fetchall(),
            "SQLite FK check failed")
    require(not conn.execute("SELECT id FROM v2_assertions_without_sources").fetchall(),
            "a source-less P3 assertion was created")
    require(not conn.execute(
        "SELECT id FROM v2_personal_unions_without_role_candidates").fetchall(),
        "a personal union lacks two qualifying overlapping political roles")
    require(conn.execute("SELECT count(*) FROM v2_relationship_imports").fetchone()[0]
            ==summary["world_relationship_evidence"],"missing original relationship evidence")
    require(conn.execute("SELECT count(*) FROM v2_house_affiliations").fetchone()[0]
            ==summary["documented_house_memberships"],"loss of house memberships")
    return summary


def preview(snapshot: dict) -> tuple[sqlite3.Connection, dict]:
    """Transient P1 → P2 → P3; close the connection to discard all data."""
    connection, previous=p2.preview(snapshot)
    try:
        result=import_relations(connection,snapshot)
        return connection, {**previous,"p3":result}
    except Exception:
        connection.close()
        raise


def house_year_candidates(conn: sqlite3.Connection, year: int) -> list[dict]:
    """Read-only country/house candidates, not actual simultaneous rule."""
    require(type(year) is int and 1<=year<=9999,"invalid year")
    cursor=conn.execute("""SELECT house_id,house_name,context_id,context_label,
                  context_kind,role_id,role_kind,person_id,
                  external_person_id,branch_label,start_year,end_year
                FROM v2_house_ruling_year_candidates
                WHERE start_year<=? AND end_year>=?
                ORDER BY house_id,context_id,role_id""",(year,year))
    columns=[c[0] for c in cursor.description]
    return [dict(zip(columns,row)) for row in cursor.fetchall()]


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=ROOT)
    parser.add_argument("--year",type=int,help="Candidate ruling houses for a year")
    args=parser.parse_args()
    snapshot=p1.load_snapshot(args.root)
    snapshot["root"]=args.root
    connection,result=preview(snapshot)
    try:
        result["sqlite"]={
            "integrity":connection.execute("PRAGMA integrity_check").fetchone()[0],
            "fk_violations":len(connection.execute("PRAGMA foreign_key_check").fetchall()),
            "v1_user_version":connection.execute("PRAGMA user_version").fetchone()[0],
            "house_rows":connection.execute("SELECT count(*) FROM v2_houses").fetchone()[0],
            "house_memberships":connection.execute(
                "SELECT count(*) FROM v2_house_affiliations").fetchone()[0],
            "normalized_relationships":connection.execute(
                "SELECT count(*) FROM v2_relationships").fetchone()[0],
            "raw_relation_records":connection.execute(
                "SELECT count(*) FROM v2_relationship_imports").fetchone()[0],
            "recorded_personal_unions":connection.execute(
                "SELECT count(*) FROM v2_context_relations"
                " WHERE kind='personal_union'").fetchone()[0],
        }
        if args.year is not None:
            result["house_year_candidates"]={
                "year":args.year,
                "caveat":"Year-overlap only; no day-level simultaneity,"
                         " complete dynastic coverage or inferred national origin.",
                "rows":house_year_candidates(connection,args.year),
            }
    finally:
        connection.close()
    print(json.dumps(result,indent=2,sort_keys=True,ensure_ascii=False))


if __name__=="__main__":
    main()
