"""Additional source-qualified world authority epochs: 1688 and 1888.

Three YEAR-filtered candidates (1688, 1788, 1888) coexist in one disposable
Atlas v2 SQLite overlay, but NEVER imply continuous rule between those years.
The established 1788 page stays unchanged; new JSONs use the same web schema.

Git-tracked research files remain immutable inputs. This module does NOT alter
canonical v1 people, tenures, facts, Pages homepage, or original photograph.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from datetime import date
from pathlib import Path

from scripts import atlas_v2_authority as old
from scripts import atlas_v2_relations as p3

ROOT = old.ROOT
YEARS = (1688, 1888)
ALL_YEARS = (1688, 1788, 1888)
RESEARCH_FILES = {
    y: f"design/atlas-v2/authority-world-sample-{y}.json"
    for y in YEARS
}
WEB_FILES = {
    y: f"world-authority-{y}.json"
    for y in YEARS
}
ORIGIN = lambda y: f"authority-{y}"
TYPE_DIMENSIONS = {
    **old.KINDS,
    "military_intervention": "military",
    "shogunate_office": "institutional",
    "cabinet_office": "institutional",
    "cabinet_transition": "institutional",
    "formal_overlordship": "institutional",
}
REGIONS = {
    1688: {"eng", "jp", "mughal"},
    1888: {"jp", "et"},
}
COUNTS = {
    1688: {"regions":3, "nodes":10, "links":5, "sources":6},
    1888: {"regions":2, "nodes":9, "links":7, "sources":5},
}
PINNED_TYPES = {
    "e1688-legal-james":"sovereign_office",
    "e1688-william-arrival":"military_intervention",
    "e1688-emperor-higashiyama":"imperial_title",
    "e1688-shogun-tsunayoshi":"shogunate_office",
    "e1688-aurangzeb-title":"imperial_title",
    "e1888-meiji-title":"sovereign_office",
    "e1888-ito-cabinet":"cabinet_office",
    "e1888-kuroda-cabinet":"cabinet_office",
    "e1888-cabinet-transition":"cabinet_transition",
    "e1888-yohannes-title":"sovereign_office",
    "e1888-menelik-shewa":"sovereign_office",
    "e1888-menelik-yohannes":"formal_overlordship",
}


def require(ok: bool, why: str) -> None:
    old.require(ok, "epoch slices: " + why)


def load(root: Path, year: int) -> dict:
    require(year in YEARS, "unexpected year")
    return json.loads(
        (root / RESEARCH_FILES[year]).read_text(encoding="utf-8"),
        object_pairs_hook=old.pairs,
    )


def qualify(year: int, native_id: str) -> str:
    return f"{ORIGIN(year)}:{native_id}"


def validate(data: dict, snap: dict) -> dict:
    year = data.get("focus_year")
    require(year in YEARS and data.get("schema_version")=="authority-epoch-sample-v1",
            "unsupported year/schema")
    require(data.get("status")=="research_pilot"
            and data.get("historical_truth_verified_by_ci") is False
            and data.get("geographic_boundaries_verified") is False
            and data.get("sample_covers_all_world") is False,
            "a tiny pilot must not claim full coverage or historical certainty")
    require(isinstance(data.get("methodology"),str) and data["methodology"].strip()
            and isinstance(data.get("calendar_policy"),str)
            and data["calendar_policy"].strip(), "missing scope/precision caveat")
    require(len(data["regions"]) == len(REGIONS[year]) and
            {r["id"] for r in data["regions"]}==REGIONS[year],
            "region list drift")
    require(all(isinstance(r.get("label"),str) and r["label"].strip()
                and isinstance(r.get("warning"),str) and r["warning"].strip()
                and isinstance(r.get("explanation"),str) and r["explanation"].strip()
                for r in data["regions"]), "region caveat missing")

    sources={}
    for ref in data["sources"]:
        sid=ref.get("id")
        require(isinstance(sid,str) and re.fullmatch(r"[A-Z][0-9]{2}",sid)
                and sid not in sources and ref.get("verification")=="reference_checked"
                and ref.get("title") and old.source_url(ref.get("url")),
                "invalid or private source")
        sources[sid]=ref

    person_ids={p["world_id"] for p in snap["crosswalk"]["people"]}
    context_ids={p["id"] for p in snap["crosswalk"]["contexts"]}
    nodes={}
    for n in data["nodes"]:
        nid=n.get("id")
        require(isinstance(nid,str) and
                re.fullmatch(f"e{year}-[a-z0-9-]+",nid) and nid not in nodes,
                "duplicate/unsafe node")
        require(n.get("kind") in old.NODE_KINDS and n.get("region") in REGIONS[year]
                and isinstance(n.get("label"),str) and n["label"].strip()
                and isinstance(n.get("note"),str) and n["note"].strip(),
                "unknown node kind or no caveat")
        src=n.get("source_ids")
        require(isinstance(src,list) and src and len(src)==len(set(src))
                and all(s in sources for s in src), "node missing evidence")
        canonical=n.get("p3_person_id")
        ctx=n.get("p3_context_id")
        require(not (canonical and ctx), "person/context cannot be merged")
        require(not canonical or canonical in person_ids,
                "no fuzzy personal identity linking")
        require(not ctx or ctx in context_ids,
                "unknown existing world context")
        nodes[nid]=n
    edges={}
    for e in data["edges"]:
        eid=e.get("id")
        require(isinstance(eid,str) and re.fullmatch(f"e{year}-[a-z0-9-]+",eid)
                and eid not in edges,"duplicate/unsafe relation")
        a=nodes.get(e.get("from"));b=nodes.get(e.get("to"))
        require(a is not None and b is not None and a is not b
                and a["region"]==b["region"]==e.get("region"),
                "a relation must join different nodes in the same context")
        require(e.get("kind") in TYPE_DIMENSIONS and
                e.get("dimension")==TYPE_DIMENSIONS[e["kind"]],
                "authority kinds cannot be relabeled or conflated")
        require(all(isinstance(e.get(k),str) and e[k].strip()
                    for k in ("label","explanation","caveat")),
                "relation missing source caveat")
        refs=e.get("source_ids")
        require(isinstance(refs,list) and refs and len(refs)==len(set(refs))
                and all(s in sources for s in refs), "relation missing source")
        period=e.get("period")
        require(isinstance(period,dict) and
                type(period.get("start_year")) is int and
                type(period.get("end_year")) is int and
                period["start_year"]==period["end_year"]==year and
                period.get("calendar")=="unspecified" and
                period.get("precision")=="year" and
                period.get("meaning") in {"event_in_year","sampled_year"},
                "invalid observation year or false exact date")
        if e["kind"] in {"military_intervention","cabinet_transition"}:
            require(period["meaning"]=="event_in_year",
                    "an event may not become a continuous year of control")
        if e["kind"] in {"imperial_title","sovereign_office","cabinet_office",
                         "shogunate_office","formal_overlordship"}:
            require(period["meaning"]=="sampled_year",
                    "a researched office is a sampled year, not an appointment")
        day=period.get("documented_day")
        if day is not None:
            require(eid=="e1888-cabinet-transition"
                    and day.get("value")=="1888-04-30"
                    and day.get("calendar")=="gregorian"
                    and day.get("precision")=="day"
                    and day.get("qualifier")=="as_recorded",
                    "day precision must be explicitly sourced and scoped")
            try:
                require(date.fromisoformat(day["value"]).year==year,
                        "event day/year mismatch")
            except ValueError as exc:
                raise ValueError("invalid Gregorian event day") from exc
        edges[eid]=e
    require(set(edges)=={k for k in PINNED_TYPES if k.startswith(f"e{year}-")},
            "one of the 12 reviewed historical relation IDs changed")
    require(all(e["kind"]==PINNED_TYPES[id] for id,e in edges.items()),
            "historical relationship type drift")
    count={"regions":len(data["regions"]),"nodes":len(nodes),
           "links":len(edges),"sources":len(sources)}
    require(count==COUNTS[year], "pilot inventory change requires review")
    if year==1688:
        require(edges["e1688-william-arrival"]["dimension"]=="military"
                and not any(e["kind"]=="sovereign_office" and
                            e["from"]=="e1688-william" for e in edges.values()),
                "William of Orange not English king until 1689")
    if year==1888:
        require(edges["e1888-menelik-yohannes"]["kind"]=="formal_overlordship"
                and not any(e["kind"]=="sovereign_office" and
                            e["from"]=="e1888-menelik" and
                            e["to"]=="e1888-ethiopia" for e in edges.values()),
                "Menelik did not become emperor until 1889")
        require(edges["e1888-cabinet-transition"]["period"]["documented_day"]["value"]=="1888-04-30",
                "Ito/Kuroda transition day lost")
    return {"year":year,**count,"historical_truth_verified_by_ci":False,
            "sample_covers_all_world":False,"geographic_boundaries_verified":False}


def sources_for(conn:sqlite3.Connection, assertion_id:str) -> list[str]:
    return [x[0] for x in conn.execute(
        "SELECT source_id FROM v2_assertion_sources WHERE assertion_id=? ORDER BY source_id",
        (assertion_id,))]


def insert_claim(conn:sqlite3.Connection,year:int,identifier:str,category:str,
                 statement:str,note:str,source_ids:list[str]) -> None:
    conn.execute(
        "INSERT INTO v2_assertions "
        "(id,category,statement,caveat,confidence,verification) VALUES(?,?,?,?,?,?)",
        (identifier,category,statement,note,"not_assessed","reference_checked"))
    for sid in source_ids:
        conn.execute(
            "INSERT INTO v2_assertion_sources(assertion_id,source_id,pinpoint) "
            "VALUES(?,?,?)", (identifier,qualify(year,sid),
                               RESEARCH_FILES[year]+"#"+identifier))


def add(conn:sqlite3.Connection,snapshot:dict,data:dict)->dict:
    result=validate(data,snapshot)
    year=result["year"]
    with conn:
        for src in data["sources"]:
            conn.execute(
                "INSERT INTO v2_sources"
                "(id,origin,native_id,title,url,canonical_source_id,verification)"
                "VALUES(?,?,?,?,?,NULL,?)",
                (qualify(year,src["id"]),ORIGIN(year),src["id"],
                 src["title"],src["url"],src["verification"]))
        for node in data["nodes"]:
            assertion=f"v2-epoch-{year}-node-{node['id']}"
            insert_claim(conn,year,assertion,
                         "biographical" if node["kind"]=="person" else "institutional",
                         node["label"],node["note"]+
                         " Документированный узел; принадлежность не подтверждает весь политический контроль.",
                         node["source_ids"])
            canon=node.get("p3_person_id")
            conn.execute(
                "INSERT INTO v2_authority_nodes"
                "(id,region_id,kind,label,note,p3_context_id,p3_person_origin,"
                "p3_person_id,assertion_id) VALUES(?,?,?,?,?,?,?,?,?)",
                (node["id"],node["region"],node["kind"],node["label"],node["note"],
                 node.get("p3_context_id"),
                 "world-pilots-1762-1800" if canon else None,
                 canon,assertion))
        for edge in data["edges"]:
            assertion=f"v2-epoch-{year}-edge-{edge['id']}"
            period=f"v2-epoch-{year}-period-{edge['id']}"
            day=edge["period"].get("documented_day")
            note=edge["caveat"]+" Только источниковое окно выбранного года."
            conn.execute(
                "INSERT INTO v2_periods(id,start_year,end_year,start_date_json,"
                "end_date_json,meaning,note) VALUES(?,?,?,?,NULL,?,?)",
                (period,year,year,
                 json.dumps(day,ensure_ascii=False) if day else None,
                 "event" if edge["period"]["meaning"]=="event_in_year"
                 else "research_window",note))
            category={"legal":"legal","institutional":"institutional",
                      "military":"practical","practical":"practical",
                      "diplomatic":"institutional"}[edge["dimension"]]
            insert_claim(conn,year,assertion,category,
                         edge["explanation"],note,edge["source_ids"])
            conn.execute(
                "INSERT INTO v2_authority_edges(id,region_id,from_node,to_node,"
                "kind,dimension,period_id,assertion_id,label,explanation,caveat)"
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (edge["id"],edge["region"],edge["from"],edge["to"],
                 edge["kind"],edge["dimension"],period,assertion,
                 edge["label"],edge["explanation"],note))
    require(conn.execute("PRAGMA integrity_check").fetchone()[0]=="ok",
            "SQLite integrity check failure")
    require(conn.execute("PRAGMA foreign_key_check").fetchall()==[],
            "broken SQLite foreign key")
    require(conn.execute("SELECT id FROM v2_assertions_without_sources").fetchall()==[],
            "unattributed historical claim")
    return result


def read_rows(conn:sqlite3.Connection,sql:str,params=())->list[dict]:
    cursor=conn.execute(sql,params)
    keys=[x[0] for x in cursor.description]
    return [dict(zip(keys,row)) for row in cursor.fetchall()]


def export_year(conn:sqlite3.Connection,data:dict)->dict:
    year=data["focus_year"]
    origin=ORIGIN(year)
    source_rows=read_rows(conn,
        "SELECT id,title,url,verification FROM v2_sources WHERE origin=? ORDER BY id",
        (origin,))
    nodes=read_rows(conn,
        "SELECT id,region_id AS region,kind,label,note,p3_context_id,p3_person_id,"
        "assertion_id FROM v2_authority_nodes WHERE id LIKE ? ORDER BY id",
        (f"e{year}-%",))
    for node in nodes:
        node["source_ids"]=sources_for(conn,node.pop("assertion_id"))
    edges=read_rows(conn,
        """SELECT e.id,e.region_id AS region,e.from_node AS "from",e.to_node AS "to",
                  e.kind,e.dimension,e.label,e.explanation,e.caveat,
                  p.meaning,p.start_year,p.end_year,p.start_date_json,
                  e.assertion_id
           FROM v2_authority_edges e JOIN v2_periods p ON p.id=e.period_id
           WHERE e.id LIKE ? ORDER BY e.id""",
        (f"e{year}-%",))
    for edge in edges:
        edge["source_ids"]=sources_for(conn,edge.pop("assertion_id"))
        day=edge.pop("start_date_json")
        if day:
            edge["documented_day"]=json.loads(day)
    require(len(nodes)==COUNTS[year]["nodes"] and
            len(edges)==COUNTS[year]["links"] and
            len(source_rows)==COUNTS[year]["sources"],
            "loss of sourced SQLite records")
    all_sources={s["id"] for s in source_rows}
    require(all(set(item["source_ids"])<=all_sources for item in [*nodes,*edges]),
            "public export source references do not resolve")
    return {"schema_version":old.PUBLIC_SCHEMA,"focus_year":year,
            "historical_truth_verified_by_ci":False,
            "sample_covers_all_world":False,
            "geographic_boundaries_verified":False,
            "methodology":data["methodology"],
            "calendar_policy":data["calendar_policy"],
            "regions":data["regions"],"nodes":nodes,"edges":edges,
            "sources":{s["id"]:s for s in source_rows},
            "counts":COUNTS[year]}


def build(root:Path=ROOT)->dict[int,dict]:
    snap=p3.p1.load_snapshot(root)
    snap["root"]=root
    originals={year:load(root,year) for year in YEARS}
    conn,_=p3.preview(snap)
    try:
        old.populate(conn,old.load(root),snap)
        for year in YEARS:
            add(conn,snap,originals[year])
        summaries=read_rows(conn,
            "SELECT start_year AS year, COUNT(*) AS edges "
            "FROM v2_authority_year_candidates GROUP BY start_year ORDER BY year")
        require({p["year"]:p["edges"] for p in summaries}==
                {1688:5,1788:12,1888:7},
                "world years have been conflated or source events duplicated")
        return {year:export_year(conn,originals[year]) for year in YEARS}
    finally:
        conn.close()


def main()->None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=ROOT)
    parser.add_argument("--out",type=Path,help="optional empty directory for JSON exports")
    args=parser.parse_args()
    results=build(args.root)
    if args.out:
        require(args.out.is_dir() and not any(args.out.iterdir()),
                "export directory must exist and be empty")
        for year,payload in results.items():
            (args.out/WEB_FILES[year]).write_text(
                json.dumps(payload,ensure_ascii=False,sort_keys=True,indent=2)+"\n",
                encoding="utf-8")
    print(json.dumps({"years":{year:payload["counts"] for year,payload in results.items()},
                      "old_1788_unchanged":True,"v1_user_version":1,
                      "historical_truth_verified_by_ci":False},
                     ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
