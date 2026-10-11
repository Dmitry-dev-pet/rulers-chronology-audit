"""Source-qualified prototype of different forms of authority in 1788.

Adds a disposable SQLite overlay to Atlas v2 P3 and exports only documented,
scoped candidates. NO inference of provinces from tribute, sovereignty from
military intervention, borders, nationalities, or uninterrupted daily rule.
The authored pilot is separate from immutable canonical atlas data.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit

from scripts import atlas_v2_relations as p3

ROOT = p3.ROOT
INPUT = "design/atlas-v2/authority-world-sample-1788.json"
SCHEMA = "authority-world-sample-v1"
ORIGIN = "authority-1788"
PUBLIC_SCHEMA = "authority-network-web-v1"
KINDS = {
    "elective_imperial_office":"legal",
    "constitutional_membership":"institutional",
    "electoral_office":"legal",
    "sovereign_office":"legal",
    "imperial_title":"legal",
    "local_military_seizure":"practical",
    "military_restoration":"military",
    "fiscal_administration":"institutional",
    "tributary_diplomacy":"diplomatic",
}
NODE_KINDS = {
    "person", "polity", "constitutional_framework", "imperial_title_context",
    "collective_institution", "locality", "fiscal_jurisdiction",
}
DIMENSIONS = ("legal", "practical", "institutional", "military", "diplomatic")
REGIONS = ("hre", "india", "qing")


def require(condition: bool, reason: str) -> None:
    p3.require(condition, "P5 authority: " + reason)


def pairs(obj) -> dict:
    result = {}
    for k, v in obj:
        require(k not in result, "duplicate JSON key " + k)
        result[k] = v
    return result


def load(root: Path = ROOT) -> dict:
    return json.loads((root / INPUT).read_text(encoding="utf-8"), object_pairs_hook=pairs)


def source_url(url: str) -> bool:
    try:
        p = urlsplit(url)
        return (p.scheme == "https" and bool(p.hostname) and not p.username and
                not p.password and p.hostname.lower() not in
                {"drive.google.com", "docs.google.com"} and
                p.port in (None, 443))
    except (ValueError, AttributeError):
        return False


def validate(data: dict, snapshot: dict) -> dict:
    require(data.get("schema_version") == SCHEMA, "unexpected world authority schema")
    require(data.get("status") == "research_pilot" and
            data.get("historical_truth_verified_by_ci") is False and
            data.get("geographic_boundaries_verified") is False and
            data.get("sample_covers_all_world") is False,
            "a partial research pilot must not claim complete or verified history")
    require(data.get("focus_year") == 1788, "this source set covers only 1788")
    require("year-only" in data.get("calendar_policy", "") or
            "day-level" in data.get("calendar_policy", ""),
            "calendar precision disclaimer missing")
    require(bool(data.get("methodology")), "research method missing")

    expected_regions={r["id"] for r in data["regions"]}
    require(expected_regions == set(REGIONS) and len(data["regions"]) == len(REGIONS),
            "HRE, India and Qing/Joseon pilot regions required")
    require(all(isinstance(r.get("warning"), str) and r["warning"].strip() and
                r.get("explanation") for r in data["regions"]),
            "every region needs method/caveat")

    sources={}
    for s in data["sources"]:
        sid=s.get("id")
        require(isinstance(sid, str) and bool(re.fullmatch(r"[A-Z][0-9]{2}", sid))
                and sid not in sources, "duplicate or invalid source ID")
        require(bool(s.get("title")) and isinstance(s.get("url"), str)
                and source_url(s["url"]) and
                s.get("verification") == "reference_checked",
                "source must be public HTTPS and qualified")
        sources[sid]=s
    require(len(sources)==8, "source inventory drift requires review")

    existing_people={p["world_id"] for p in snapshot["crosswalk"]["people"]}
    existing_contexts={p["id"] for p in snapshot["crosswalk"]["contexts"]}
    nodes={}
    for node in data["nodes"]:
        nid=node.get("id")
        require(isinstance(nid,str) and bool(re.fullmatch(r"[a-z][a-z0-9-]+", nid))
                and nid not in nodes,"duplicate/bad node ID")
        require(node.get("region") in expected_regions and node.get("kind") in NODE_KINDS
                and isinstance(node.get("label"),str) and node["label"].strip()
                and isinstance(node.get("note"),str) and node["note"].strip(),
                "invalid node "+str(nid))
        require(isinstance(node.get("source_ids"),list) and node["source_ids"] and
                len(set(node["source_ids"]))==len(node["source_ids"]) and
                all(sid in sources for sid in node["source_ids"]),
                "node missing source "+str(nid))
        person=node.get("p3_person_id")
        context=node.get("p3_context_id")
        require(not (person and context), "node cannot combine person and context")
        require(not person or (node["kind"]=="person" and person in existing_people),
                "unreviewed identity link "+str(nid))
        require(not context or (node["kind"]!="person" and context in existing_contexts),
                "unreviewed political context link "+str(nid))
        nodes[nid]=node
    require(len(nodes)==18, "node inventory drift requires review")

    edges={}
    for edge in data["edges"]:
        eid=edge.get("id")
        require(isinstance(eid,str) and bool(re.fullmatch(r"[a-z][a-z0-9-]+",eid))
                and eid not in edges, "duplicate/bad authority assertion ID")
        frm=nodes.get(edge.get("from"))
        to=nodes.get(edge.get("to"))
        require(frm is not None and to is not None and frm is not to and
                frm["region"]==to["region"]==edge.get("region"),
                "missing/mismatched directed endpoints "+str(eid))
        require(edge.get("kind") in KINDS and
                edge.get("dimension")==KINDS[edge["kind"]],
                "different authority kinds must not be conflated "+str(eid))
        require(isinstance(edge.get("label"),str) and edge["label"].strip() and
                isinstance(edge.get("explanation"),str) and edge["explanation"].strip() and
                isinstance(edge.get("caveat"),str) and edge["caveat"].strip(),
                "authority assertion lacks caveat "+str(eid))
        period=edge.get("period")
        require(isinstance(period,dict) and type(period.get("start_year")) is int
                and type(period.get("end_year")) is int
                and period["start_year"]==1788==period["end_year"] and
                period.get("calendar")=="unspecified" and period.get("precision")=="year"
                and period.get("meaning") in {"sampled_year","event_in_year"},
                "unknown or false precision / future period "+str(eid))
        if edge["kind"] in {"local_military_seizure","military_restoration"}:
            require(period["meaning"]=="event_in_year",
                    "local military events cannot assert continuous control")
        else:
            require(period["meaning"]=="sampled_year",
                    "an office/diplomatic relation is a scoped sample")
        refs=edge.get("source_ids")
        require(isinstance(refs,list) and bool(refs) and
                len(set(refs))==len(refs) and all(s in sources for s in refs),
                "authority assertion missing source "+str(eid))
        edges[eid]=edge
    require(len(edges)==12, "relationship inventory drift requires review")
    dims={x["dimension"] for x in edges.values()}
    require(dims==set(DIMENSIONS), "formal/practical/diplomatic/military distinctions lost")
    require(next(x for x in edges.values() if x["id"]=="h-e2")["kind"] ==
            "constitutional_membership", "imperial framework cannot become conquest")
    require(next(x for x in edges.values() if x["id"]=="q-e3")["kind"] ==
            "tributary_diplomacy", "Joseon is NOT a Qing province")
    require(next(x for x in edges.values() if x["id"]=="i-e2")["kind"] ==
            "local_military_seizure", "local event cannot be continuous sovereignty")
    return {
        "year": 1788, "regions":len(expected_regions),
        "nodes":len(nodes),"links":len(edges),
        "sources":len(sources),"dimensions":sorted(dims),
        "historical_truth_verified_by_ci": False,
        "geographic_boundaries_verified":False,
        "sample_covers_all_world":False,
    }


def assertion(conn:sqlite3.Connection,aid:str,category:str,statement:str,
              caveat:str,refs:list[str]) -> None:
    conn.execute("""INSERT INTO v2_assertions
       (id,category,statement,caveat,confidence,verification)
       VALUES(?,?,?,?,?,?)""",
       (aid,category,statement,caveat,"not_assessed","reference_checked"))
    for sid in refs:
        conn.execute("""INSERT INTO v2_assertion_sources
           (assertion_id,source_id,pinpoint) VALUES(?,?,?)""",
           (aid,ORIGIN+":"+sid,INPUT+"#"+aid))


def populate(conn:sqlite3.Connection,data:dict,snapshot:dict)->dict:
    summary=validate(data,snapshot)
    with conn:
        for src in data["sources"]:
            conn.execute("""INSERT INTO v2_sources
                (id,origin,native_id,title,url,canonical_source_id,verification)
                VALUES(?,?,?,?,?,NULL,?)""",
                (ORIGIN+":"+src["id"],ORIGIN,src["id"],src["title"],
                 src["url"],src["verification"]))
        for node in data["nodes"]:
            aid="v2-auth-node-"+node["id"]
            assertion(conn,aid,"biographical" if node["kind"]=="person" else "institutional",
                      node["label"],node["note"]+
                      " Sample node; identity and political status are not a complete historical record.",
                      node["source_ids"])
            person_id=node.get("p3_person_id")
            person_origin="world-pilots-1762-1800" if person_id else None
            conn.execute("""INSERT INTO v2_authority_nodes
                (id,region_id,kind,label,note,p3_context_id,
                 p3_person_origin,p3_person_id,assertion_id)
                VALUES(?,?,?,?,?,?,?,?,?)""",
                (node["id"],node["region"],node["kind"],node["label"],
                 node["note"],node.get("p3_context_id"),
                 person_origin,person_id,aid))
        category={"legal":"legal","practical":"practical","institutional":"institutional",
                  "military":"practical","diplomatic":"institutional"}
        for edge in data["edges"]:
            aid="v2-auth-edge-"+edge["id"]
            period_id="v2-auth-period-"+edge["id"]
            meaning = ("event" if edge["period"]["meaning"]=="event_in_year"
                       else "research_window")
            caveat=edge["caveat"]+" Research slice only; no day-level or territorial inference."
            conn.execute("""INSERT INTO v2_periods
                (id,start_year,end_year,start_date_json,end_date_json,meaning,note)
                VALUES(?,?,?,NULL,NULL,?,?)""",
                (period_id,1788,1788,meaning,caveat))
            assertion(conn,aid,category[edge["dimension"]],
                      edge["explanation"],caveat,edge["source_ids"])
            conn.execute("""INSERT INTO v2_authority_edges
                (id,region_id,from_node,to_node,kind,dimension,period_id,
                 assertion_id,label,explanation,caveat)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (edge["id"],edge["region"],edge["from"],edge["to"],
                 edge["kind"],edge["dimension"],period_id,aid,
                 edge["label"],edge["explanation"],caveat))
    require(conn.execute("PRAGMA integrity_check").fetchone()[0]=="ok",
            "SQLite integrity_check failure")
    require(conn.execute("PRAGMA foreign_key_check").fetchall()==[],
            "SQLite foreign_key_check failure")
    require(conn.execute("SELECT id FROM v2_assertions_without_sources").fetchall()==[],
            "authority fact lacks source")
    return summary


def query_rows(conn:sqlite3.Connection,sql:str,params=())->list[dict]:
    cursor=conn.execute(sql,params)
    cols=[d[0] for d in cursor.description]
    return [dict(zip(cols,row)) for row in cursor.fetchall()]


def projection(root:Path=ROOT)->dict:
    snap=p3.p1.load_snapshot(root)
    snap["root"]=root
    data=load(root)
    con,_=p3.preview(snap)
    try:
        counts=populate(con,data,snap)
        def refs(assertion_id):
            ids=query_rows(con,"SELECT source_id FROM v2_assertion_sources "
                           "WHERE assertion_id=? ORDER BY source_id",(assertion_id,))
            require(bool(ids),"no citation for "+assertion_id)
            return [x["source_id"] for x in ids]
        sources=query_rows(con,"SELECT id,title,url,verification FROM v2_sources "
                              "WHERE origin=? ORDER BY id",(ORIGIN,))
        nodes=query_rows(con,"""SELECT id,region_id AS region,kind,label,note,
                                  p3_context_id,p3_person_id,assertion_id
                                  FROM v2_authority_nodes ORDER BY id""")
        for n in nodes:
            n["source_ids"]=refs(n.pop("assertion_id"))
        edges=query_rows(con,"""SELECT e.id,e.region_id AS region,e.from_node AS
                                "from",e.to_node AS "to",e.kind,e.dimension,e.label,
                                e.explanation,e.caveat,p.meaning,p.start_year,p.end_year,
                                e.assertion_id
                                FROM v2_authority_edges e
                                JOIN v2_periods p ON p.id=e.period_id
                                ORDER BY e.id""")
        for e in edges:
            e["source_ids"]=refs(e.pop("assertion_id"))
        require(len(nodes)==18 and len(edges)==12 and len(sources)==8,
                "loss of SQL-normalized pilot data")
        return {
            "schema_version":PUBLIC_SCHEMA,"focus_year":1788,
            "historical_truth_verified_by_ci":False,
            "sample_covers_all_world":False,
            "geographic_boundaries_verified":False,
            "methodology":data["methodology"],
            "calendar_policy":data["calendar_policy"],
            "regions":data["regions"],"nodes":nodes,"edges":edges,
            "sources":{s["id"]:s for s in sources},
            "counts":counts,
        }
    finally:
        con.close()


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=ROOT)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    result=projection(args.root)
    if args.output:
        require(not args.output.exists(),"refuse to overwrite generated output")
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",
                               encoding="utf-8")
    print(json.dumps(result["counts"],ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
