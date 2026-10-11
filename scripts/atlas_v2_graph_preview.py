"""P4 experimental SPA graph preview, completely separate from published atlas.

Read the validated P3 in-memory SQL graph, create a JSON-only public-safe
projection, and copy an existing dist into a *separate* preview directory.
No canonical data, old dist, original JPEG or GitHub Pages is modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit

from scripts import atlas_v2_relations as p3

ROOT=p3.ROOT
SCHEMA="atlas-v2-graph-preview-1"
MIN_YEAR,MAX_YEAR=1762,1800
FRONTEND=("atlas-v2-graph.js","atlas-v2-graph.css")
PREVIEW_FILES=("atlas-v2-graph.json",*FRONTEND)
WARNING=("Documented source windows and year intersections, not continuous "
         "effective political control, day-level simultaneity, ethnic origin, "
         "a complete history of European states or verified historical borders.")


def require(ok:bool,message:str)->None:
    p3.require(ok,"P4: "+message)


def rows(conn:sqlite3.Connection,statement:str,params=())->list[dict]:
    cursor=conn.execute(statement,params)
    fields=[c[0] for c in cursor.description]
    return [dict(zip(fields,row)) for row in cursor.fetchall()]


def sha256(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def projection(snapshot:dict)->dict:
    conn,report=p3.preview(snapshot)
    try:
        context_rows=rows(conn,"""SELECT c.id,c.label,c.kind,cr.native_id AS world_id
            FROM v2_contexts c JOIN v2_context_refs cr ON cr.context_id=c.id
            WHERE cr.origin='world-pilots-1762-1800' ORDER BY cr.native_id""")
        contexts=[{"id":c["id"],"name":c["label"],"kind":c["kind"],
                   "world_id":c["world_id"]} for c in context_rows]
        world_ids={c["id"] for c in contexts}

        people=rows(conn,"""SELECT native_id AS id,display_label AS name,
            resolution,canonical_person_id
            FROM v2_external_people ORDER BY native_id""")
        person_ids={p["id"] for p in people}

        sources=rows(conn,"""SELECT id,title,url,verification
            FROM v2_sources ORDER BY id""")
        catalog={s["id"]:s for s in sources}
        cited=set()
        def citations(assertion_id):
            ids=[r["source_id"] for r in rows(conn,
                "SELECT source_id FROM v2_assertion_sources WHERE assertion_id=? "
                "ORDER BY source_id",(assertion_id,))]
            require(len(ids)>0,"source-less assertion "+assertion_id)
            require(all(sid in catalog for sid in ids),"missing source")
            cited.update(ids)
            return ids

        house_rows=rows(conn,"""SELECT h.id,h.name,h.note,i.assertion_id
            FROM v2_houses h JOIN v2_house_imports i ON i.house_id=h.id
            ORDER BY h.id""")
        houses=[{"id":h["id"],"name":h["name"],"note":h["note"],
                 "sources":citations(h["assertion_id"])}
                for h in house_rows]
        house_ids={h["id"] for h in houses}

        member_rows=rows(conn,"""SELECT a.id,a.house_id,a.affiliation,a.branch_label,
            a.assertion_id,i.raw_json
            FROM v2_house_affiliations a
            JOIN v2_affiliation_imports i ON i.affiliation_id=a.id
            ORDER BY a.id""")
        affiliations=[]
        for member in member_rows:
            origin=json.loads(member["raw_json"])
            require(origin["person_id"] in person_ids,"unrecognized house member")
            require(member["house_id"] in house_ids,"missing house")
            affiliations.append({
                "id":member["id"],"house_id":member["house_id"],
                "person_id":origin["person_id"],"kind":member["affiliation"],
                "branch":member["branch_label"],
                "sources":citations(member["assertion_id"]),
                "time_qualified":False,
            })

        inst_rows=rows(conn,"SELECT id,label AS name,kind FROM v2_institutions ORDER BY id")
        inst_ids={i["id"] for i in inst_rows}
        role_rows=rows(conn,"""SELECT r.id,r.context_id,r.institution_id,r.title,
            r.role_kind,r.assertion_id,r.canonical_tenure_id,
            p.start_year,p.end_year,p.start_date_json,p.end_date_json,p.note,
            i.raw_json
            FROM v2_roles r JOIN v2_periods p ON p.id=r.period_id
            JOIN v2_world_imports i ON i.role_id=r.id OR i.institution_id=r.institution_id
            ORDER BY r.id""")
        roles=[]
        for role in role_rows:
            # An institution's P2 role is not exposed from the P2 raw record
            # as a person. P2's raw JSON preserves its type and provenance.
            original=json.loads(role["raw_json"])
            person_id=original.get("person_id")
            require(role["context_id"] in world_ids,"role references unknown world context")
            require((person_id in person_ids) if person_id is not None
                    else (role["institution_id"] in inst_ids),"invalid role actor")
            roles.append({
                "id":role["id"],"context_id":role["context_id"],
                "person_id":person_id,"institution_id":role["institution_id"],
                "title":role["title"],"kind":role["role_kind"],
                "start_year":role["start_year"],"end_year":role["end_year"],
                "start_date":json.loads(role["start_date_json"]) if role["start_date_json"] else None,
                "end_date":json.loads(role["end_date_json"]) if role["end_date_json"] else None,
                "note":role["note"],
                "canonical_tenure_id":role["canonical_tenure_id"],
                "sources":citations(role["assertion_id"]),
            })

        relation_rows=rows(conn,"""SELECT r.id,r.kind,r.domain,r.title,r.note,
            r.event_year,r.assertion_id,p.start_year,p.end_year,p.meaning
            FROM v2_relationships r JOIN v2_periods p ON p.id=r.period_id
            ORDER BY r.id""")
        all_imports=rows(conn,"SELECT native_id,relationship_id FROM v2_relationship_imports")
        imported={x["native_id"]:x["relationship_id"] for x in all_imports}
        rels=[]
        for rel in relation_rows:
            people_nodes=rows(conn,"""SELECT pos.position,e.native_id AS external,
                p.canonical_person_id FROM v2_relationship_people pos
                LEFT JOIN v2_external_people e
                  ON e.origin=pos.external_person_origin AND e.native_id=pos.external_person_id
                LEFT JOIN v2_external_people p ON p.canonical_person_id=pos.person_id
                WHERE pos.relation_id=? ORDER BY pos.position""",(rel["id"],))
            participants=[n["external"] if n["external"] is not None else
                          next((p["id"] for p in people
                                if p["canonical_person_id"]==n["canonical_person_id"]),None)
                          for n in people_nodes]
            ctx=[x["context_id"] for x in rows(conn,
                "SELECT context_id FROM v2_relationship_contexts WHERE relation_id=? ORDER BY position",
                (rel["id"],))]
            require(all(x in person_ids for x in participants) and
                    all(x in world_ids for x in ctx),"orphan relation endpoints")
            rels.append({
                "id":rel["id"],"kind":rel["kind"],"domain":rel["domain"],
                "title":rel["title"],"note":rel["note"],
                "people":participants,"contexts":ctx,
                "start_year":rel["start_year"],"end_year":rel["end_year"],
                "time_kind":rel["meaning"],"event_year":rel["event_year"],
                "sources":citations(rel["assertion_id"]),
                "raw_record_ids":sorted([native for native,target in imported.items()
                                         if target==rel["id"]]),
            })

        selected_sources={s:c for s,c in catalog.items() if s in cited}
        for ident,s in selected_sources.items():
            parsed=urlsplit(s["url"])
            require(parsed.scheme=="https" and parsed.hostname and
                    not parsed.username and not parsed.password and
                    parsed.hostname not in {"drive.google.com","docs.google.com"},
                    "unsafe source URL "+ident)

        output={
            "schema_version":SCHEMA,
            "historical_truth_verified_by_ci":False,
            "scope":{"start_year":MIN_YEAR,"end_year":MAX_YEAR,
                     "description":"European research pilot with Russian crosswalk, 1762–1800",
                     "not_complete":True},
            "warning":WARNING,
            "counts":{"contexts":len(contexts),"people":len(people),
                      "houses":len(houses),"affiliations":len(affiliations),
                      "roles":len(roles),"institutions":len(inst_rows),
                      "relations":len(rels),"source_records":len(selected_sources)},
            "contexts":contexts,"people":people,"houses":houses,
            "affiliations":affiliations,"roles":roles,
            "institutions":inst_rows,"relations":rels,
            "sources":selected_sources,
        }
        require((len(contexts),len(people),len(houses),len(affiliations),
                 len(roles),len(inst_rows),len(rels))==(13,28,4,18,43,3,27),
                "P3/P4 inventory changed unexpectedly")
        require(report["p3"]["world_relationship_evidence"]==29,
                "raw relationship provenance mismatch")
        require(conn.execute("PRAGMA foreign_key_check").fetchall()==[],
                "bad source graph FKs")
        require(not conn.execute("SELECT id FROM v2_assertions_without_sources").fetchall(),
                "unsourced graph evidence")
        return output
    finally:
        conn.close()


def preview_build(root:Path,dist:Path,output:Path)->dict:
    """Creates a standalone *testing* preview, leaves dist and source unchanged."""
    require(dist.is_dir(),"canonical dist missing; run existing build first")
    require(output.resolve()!=dist.resolve(),"refuse to overwrite canonical dist")
    require(not output.exists(),"preview output must not already exist")
    require((dist/"index.html").is_file() and (dist/"atlas.json").is_file(),
            "must receive the complete ordinary SPA dist")
    original_hash={p.name:sha256(p) for p in dist.iterdir() if p.is_file()}
    require(all(p.is_file() for p in dist.iterdir()),"dist contains non-file artifacts")
    require(not set(PREVIEW_FILES) & set(original_hash),"preview files already in published dist")

    snap=p3.p1.load_snapshot(root)
    snap["root"]=root
    payload=projection(snap)
    output.mkdir(parents=True,exist_ok=False)
    for path in sorted(dist.iterdir()):
        shutil.copy2(path,output/path.name)
    for filename in FRONTEND:
        source=root/"site"/filename
        require(source.is_file(),"P4 frontend missing "+filename)
        shutil.copy2(source,output/filename)
    (output/"atlas-v2-graph.json").write_text(
        json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+"\n",
        encoding="utf-8")

    page=(output/"index.html").read_text(encoding="utf-8")
    require("</body>" in page and "id='chronology-data'" in page,
            "unrecognized SPA app shell")
    page=page.replace("</body>",
        "<link rel='stylesheet' href='./atlas-v2-graph.css'>\n"
        "<script defer src='./atlas-v2-graph.js'></script>\n</body>")
    (output/"index.html").write_text(page,encoding="utf-8")
    sums="".join(
        sha256(p)+"  "+p.name+"\n" for p in sorted(output.iterdir())
        if p.is_file() and p.name!="SHA256SUMS"
    )
    (output/"SHA256SUMS").write_text(sums,encoding="utf-8")
    require({p.name:sha256(p) for p in dist.iterdir() if p.is_file()}==original_hash,
            "canonical dist was unexpectedly modified")
    # Preview files follow the same privacy restrictions as Pages, but do NOT
    # become part of production Pages allowlist.
    for item in output.iterdir():
        raw=item.read_bytes()
        require(b"drive.google.com" not in raw and b"1000428575.jpg" not in raw,
                "private original asset leaked in "+item.name)
    return {"status":"experimental_preview_only","historical_truth_verified_by_ci":False,
            "output":str(output),"entry":"?atlasV2=graph&v2Year=1788#/timeline/1762",
            "counts":payload["counts"],"canonical_dist_unchanged":True}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=ROOT)
    parser.add_argument("--dist",type=Path,default=ROOT/"dist")
    parser.add_argument("--output",type=Path,default=ROOT/"p4-preview")
    args=parser.parse_args()
    print(json.dumps(preview_build(args.root,args.dist,args.output),
                     ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
