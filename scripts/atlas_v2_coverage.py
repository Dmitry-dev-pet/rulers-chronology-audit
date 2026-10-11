"""Source-derived coverage MATRIX for the tiny 1688/1788/1888 authority pilots.

Seven named research scopes, three *sampled* calendar years, 21 cells.
Cells with sourced relationships are PARTIAL_SAMPLES only; every other cell
means NOT_RESEARCHED in these files. Never mark the existence, absence,
sovereignty or completeness of any historical state based on an empty cell.

Derive rows from ONE disposable P1 -> P2 -> P3 -> authority SQLite overlay.
This is a static export for GitHub Pages, not a new runtime database/API.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from scripts import atlas_v2_authority as authority
from scripts import atlas_v2_epochs as epochs
from scripts import atlas_v2_relations as p3

ROOT = authority.ROOT
SCHEMA = "world-authority-coverage-v1"
YEARS = (1688, 1788, 1888)
DIMENSIONS = ("legal", "practical", "institutional", "military", "diplomatic")
AREA_LABELS = (
    ("eng", "Англия", "Именно английский политический кризис, не все владения британской короны."),
    ("hre", "Священная Римская империя", "Имперская должность и курфюршество — не карта всех германских княжеств."),
    ("mughal", "Могольский престол", "Тематический титульный срез, не целостная территория Южной Азии."),
    ("india", "Индия (исследовательская группа)", "Несколько разных центров власти, а не одно государство."),
    ("jp", "Япония", "Двор, сёгунат и кабинет относятся к разным историческим институциональным системам."),
    ("qing", "Цин и Чосон", "Два политических образования с дипломатическими отношениями."),
    ("et", "Эфиопия и Шоа", "Императорская и региональная власти, без проверки границ."),
)
AREA_IDS = {a[0] for a in AREA_LABELS}
EXPECTED = {
    1688: {"eng":2,"jp":2,"mughal":1},
    1788: {"hre":4,"india":5,"qing":3},
    1888: {"jp":4,"et":3},
}
STATUS_SAMPLE = "partial_sample"
STATUS_MISSING = "not_researched"
EMPTY_NOTE = (
    "В этих исследовательских файлах нет записей для такого сочетания "
    "года и темы. Это НЕ свидетельство отсутствия государств, людей, "
    "юридических должностей или фактической власти."
)


def require(condition: bool, reason: str) -> None:
    authority.require(condition, "coverage: " + reason)


def rows(conn: sqlite3.Connection, query: str, params=()) -> list[dict]:
    cur = conn.execute(query, params)
    names = [c[0] for c in cur.description]
    return [dict(zip(names, item)) for item in cur.fetchall()]


def get_sources(conn: sqlite3.Connection, assertion_id: str) -> list[str]:
    values = rows(conn, "SELECT source_id FROM v2_assertion_sources "
                        "WHERE assertion_id=? ORDER BY source_id", (assertion_id,))
    require(bool(values), "source-free observation " + assertion_id)
    return [item["source_id"] for item in values]


def build(root: Path = ROOT) -> dict:
    snapshot = p3.p1.load_snapshot(root)
    snapshot["root"] = root
    first = authority.load(root)
    others = {year: epochs.load(root, year) for year in epochs.YEARS}
    data_by_year = {1688: others[1688], 1788: first, 1888: others[1888]}

    # One SQLite instance combines all years, but DOES NOT invent intervals
    # between the three observation years.
    conn, _ = p3.preview(snapshot)
    try:
        authority.populate(conn, first, snapshot)
        for year in epochs.YEARS:
            epochs.add(conn, snapshot, others[year])
        require(conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok",
                "SQLite integrity failure")
        require(conn.execute("PRAGMA foreign_key_check").fetchall() == [],
                "foreign key failure")

        raw_areas = {year: {item["id"]:item for item in data_by_year[year]["regions"]}
                     for year in YEARS}
        require(set().union(*(set(a) for a in raw_areas.values())) == AREA_IDS,
                "unapproved research scope identity")
        cells = []
        referenced_sources = set()
        for scope_id, label, caveat in AREA_LABELS:
            for year in YEARS:
                region = raw_areas[year].get(scope_id)
                claim_rows = rows(conn,
                    """SELECT e.id,e.kind,e.dimension,e.label,e.explanation,e.caveat,
                              e.from_node,e.to_node,e.assertion_id,p.meaning
                       FROM v2_authority_edges e
                       JOIN v2_periods p ON p.id=e.period_id
                       WHERE e.region_id=? AND p.start_year=? AND p.end_year=?
                       ORDER BY e.id""", (scope_id,year,year))
                if region is None:
                    require(not claim_rows, "unresearched scope has evidence: " +
                            str((year,scope_id)))
                else:
                    require(len(claim_rows)==EXPECTED[year][scope_id],
                            "pilot source graph mismatch: "+str((year,scope_id)))
                dimensions = {dimension:0 for dimension in DIMENSIONS}
                evidence = []
                source_ids = set()
                distinct_node_ids = set()
                for claim in claim_rows:
                    require(claim["dimension"] in dimensions,"unsupported dimension")
                    dimensions[claim["dimension"]] += 1
                    distinct_node_ids.update((claim["from_node"],claim["to_node"]))
                    refs = get_sources(conn,claim["assertion_id"])
                    require(all(s.startswith("authority-"+str(year)+":") for s in refs),
                            "cross-year assertion source leak")
                    source_ids.update(refs)
                    evidence.append({
                        "id":claim["id"],
                        "label":claim["label"],
                        "kind":claim["kind"],
                        "dimension":claim["dimension"],
                        "meaning":claim["meaning"],
                        "explanation":claim["explanation"],
                        "caveat":claim["caveat"],
                        "source_ids":refs,
                    })
                for node_id in distinct_node_ids:
                    candidates = rows(conn,
                        "SELECT id,region_id,assertion_id FROM v2_authority_nodes "
                        "WHERE id=?", (node_id,))
                    require(len(candidates)==1 and candidates[0]["region_id"]==scope_id,
                            "orphan or mismatched node")
                    node_sources=get_sources(conn,candidates[0]["assertion_id"])
                    require(all(s.startswith("authority-"+str(year)+":")
                                for s in node_sources),
                            "cross-year node source leak")
                    source_ids.update(node_sources)
                sampled = bool(claim_rows)
                require(sampled == (region is not None),
                        "documented source category without assertion")
                cell={
                    "id":str(year)+":"+scope_id,
                    "year":year,
                    "scope_id":scope_id,
                    "status":STATUS_SAMPLE if sampled else STATUS_MISSING,
                    "edge_count":len(claim_rows),
                    "node_count":len(distinct_node_ids),
                    "dimension_counts":dimensions,
                    "source_ids":sorted(source_ids),
                    "evidence":evidence,
                    "research_warning":region["warning"] if region else EMPTY_NOTE,
                    "scope_description":region["subtitle"] if region else "",
                }
                if sampled:
                    require(bool(source_ids), "researched cell missing source links")
                    referenced_sources.update(source_ids)
                else:
                    require(cell["edge_count"]==cell["node_count"]==0
                            and not source_ids and not evidence
                            and not any(dimensions.values()),
                            "not-researched cell fabricated data")
                cells.append(cell)

        sources={}
        for ref_id in sorted(referenced_sources):
            refs=rows(conn,
                "SELECT id,title,url,verification FROM v2_sources WHERE id=?",
                (ref_id,))
            require(len(refs)==1 and refs[0]["verification"]=="reference_checked"
                    and authority.source_url(refs[0]["url"]),
                    "public evidence unavailable or unsafe: "+ref_id)
            sources[ref_id]=refs[0]
        sampled_count=sum(x["status"]==STATUS_SAMPLE for x in cells)
        untouched_count=sum(x["status"]==STATUS_MISSING for x in cells)
        year_totals={str(year):{
            "partial_samples":sum(c["year"]==year and c["status"]==STATUS_SAMPLE for c in cells),
            "not_researched":sum(c["year"]==year and c["status"]==STATUS_MISSING for c in cells),
            "documented_links":sum(c["edge_count"] for c in cells if c["year"]==year),
        } for year in YEARS}
        require((len(cells),sampled_count,untouched_count)==(21,8,13),
                "source coverage cells incorrectly classified")
        require([year_totals[str(y)]["documented_links"] for y in YEARS]==[5,12,7],
                "authority assertions should not be interpolated")
        require(all(sum(c["dimension_counts"].values())==c["edge_count"]
                    for c in cells), "dimension totals mismatch")
        return {
            "schema_version":SCHEMA,
            "title":"Матрица исследовательского покрытия мировой власти",
            "historical_truth_verified_by_ci":False,
            "worldwide_coverage_verified":False,
            "geographic_boundaries_verified":False,
            "years":list(YEARS),
            "dimensions":list(DIMENSIONS),
            "areas":[{"id":id,"label":label,"scope_caveat":note}
                     for id,label,note in AREA_LABELS],
            "methodology":{
                "observed":"partial_sample означает лишь наличие конкретных "
                           "ссылочных записей внутри исследовательской темы и года; "
                           "не означает полного изучения эпохи.",
                "unobserved":EMPTY_NOTE,
                "time":"Исследованы ровно 1688, 1788 и 1888 годы, "
                       "не все годы между ними. Наличие двух записей в одном "
                       "году не доказывает одновременную власть в один день.",
                "regions":"Строка обозначает тематическую исследовательскую область, "
                          "не неизменные границы или единое национальное государство.",
                "dimension":"Отсутствие связей выбранного типа в уже исследованной "
                            "ячейке не доказывает исторического отсутствия такого вида власти.",
            },
            "summary":{
                "area_count":len(AREA_LABELS),
                "year_count":len(YEARS),
                "cell_count":len(cells),
                "partial_samples":sampled_count,
                "not_researched":untouched_count,
                "documented_links":sum(c["edge_count"] for c in cells),
                "distinct_cited_sources":len(sources),
                "by_year":year_totals,
            },
            "cells":cells,
            "sources":sources,
        }
    finally:
        conn.close()


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=ROOT)
    parser.add_argument("--out",type=Path)
    args=parser.parse_args()
    result=build(args.root)
    if args.out:
        require(not args.out.exists(), "refuse overwrite of existing export")
        args.out.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n",
                            encoding="utf-8")
    print(json.dumps(result["summary"],ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
