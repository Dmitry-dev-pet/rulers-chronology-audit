"""Draft-only crosswalk between Atlas v1 and international 1762–1800 pilots.

This program never writes Git-tracked canonical data or publication artifacts.
It builds the proposed v2 extension in a disposable in-memory SQLite database.
Source-based identity only: no fuzzy aliases, dynasty or birthplace inference.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import tempfile
from collections import Counter
from pathlib import Path

from scripts import atlas_db

ROOT = Path(__file__).resolve().parents[1]
CROSSWALK = "design/atlas-v2/crosswalk-proposal.json"
WORLD_DIR = "data/atlas/world-pilots"
WORLD_FILES = (
    "1762.json",
    "dynasty-1762-1780.json",
    "extension-1781-1800.json",
    "coverage-1762-1800.json",
    "dynasty-footprints-1762-1800.json",
)
CANON_SOURCE = "data/atlas/sources.jsonl"
ALLOWED_KINDS = {
    "polity", "polity_regime", "composite_monarchy", "elective_office_context",
    "birthplace_context", "other_context",
}


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError("atlas-v2 crosswalk: " + reason)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_snapshot(root: Path = ROOT) -> dict:
    canonical = atlas_db.load(root)
    world = {name: read_json(root / WORLD_DIR / name) for name in WORLD_FILES}
    config = read_json(root / CROSSWALK)
    return {"canonical": canonical, "world": world, "crosswalk": config}


def source_catalog(snapshot: dict) -> list[dict]:
    config = snapshot["crosswalk"]
    namespaces = config["source_namespaces"]
    require(set(namespaces) == {CANON_SOURCE, *WORLD_FILES},
            "source namespace inventory is incomplete")
    require(len(set(namespaces.values())) == len(namespaces),
            "two source datasets share a namespace")

    sources = []
    for filename, source_rows in [(CANON_SOURCE, snapshot["canonical"]["sources"])] + [
        (name, snapshot["world"][name]["sources"]) for name in WORLD_FILES
    ]:
        origin = namespaces[filename]
        for item in source_rows:
            require(item["id"] and item["title"] and item["url"].startswith("https://"),
                    "source record invalid in " + filename)
            require("drive.google.com" not in item["url"].lower(),
                    "private Drive URL cannot enter public source registry")
            sources.append({
                "key": origin + ":" + item["id"],
                "origin": origin,
                "native_id": item["id"],
                "title": item["title"],
                "url": item["url"],
                "canonical_source_id": item["id"] if filename == CANON_SOURCE else None,
                "verification": item.get("verification", "unverified"),
            })
    require(len({(s["origin"], s["native_id"]) for s in sources}) == len(sources),
            "source namespace collision")

    # References in the older pilots use bare IDs. Refuse an ambiguous bare ID,
    # even though the SQL storage itself supports multiple namespaces.
    names_by_bare_id = Counter(s["native_id"] for s in sources)
    require(max(names_by_bare_id.values(), default=0) == 1,
            "bare source ID is ambiguous; introduce explicit source crosswalk")
    return sources


def source_references(node):
    """Find references, not the root list of source record objects."""
    if isinstance(node, list):
        for child in node:
            yield from source_references(child)
    elif isinstance(node, dict):
        for key, value in node.items():
            if key in ("sources", "source_ids") and isinstance(value, list) and all(
                    isinstance(v, str) for v in value):
                yield from value
            elif key == "source_id" and isinstance(value, str):
                yield value
            else:
                yield from source_references(value)


def validate(snapshot: dict) -> dict:
    db = snapshot["canonical"]
    w = snapshot["world"]
    x = snapshot["crosswalk"]
    require(x["schema_version"] == "v2-crosswalk-proposal-1", "unsupported schema version")
    require(x["status"] == "draft_not_canonical", "a draft cannot be promoted silently")
    require(x["historical_truth_verified_by_ci"] is False,
            "structural checks do not prove historical accuracy")
    canonical_origin = x["canonical_context_origin"]
    world_origin = x["world_context_origin"]

    canonical_states = {s["id"]: s for s in db["states"]}
    original_polities = (w["1762.json"]["countries"] +
                         w["dynasty-1762-1780.json"]["additional_polities"] +
                         w["extension-1781-1800.json"]["additional_polities"])
    world_polities = {p["id"]: p for p in original_polities}
    require(len(world_polities) == len(original_polities), "duplicate world polity ID")
    coverage_polities = {p["polity_id"] for p in w["coverage-1762-1800.json"]["polities"]}
    require(set(world_polities) == coverage_polities,
            "world polity set differs from coverage policy")

    ref_to_context = {}
    context_ids = set()
    for context in x["contexts"]:
        cid = context["id"]
        require(cid not in context_ids, "duplicate context ID " + cid)
        context_ids.add(cid)
        require(context["label"] and context["kind"] in ALLOWED_KINDS,
                "invalid context " + cid)
        require(context["refs"], "context without reference " + cid)
        canonical_refs = []
        world_refs = []
        for ref in context["refs"]:
            key = (ref["origin"], ref["native_id"])
            require(ref["mapping"] == "equivalent", "unsupported context mapping: " + str(key))
            require(key not in ref_to_context, "duplicate source context reference " + str(key))
            require((ref["origin"] == canonical_origin and ref["native_id"] in canonical_states)
                    or (ref["origin"] == world_origin and ref["native_id"] in world_polities),
                    "unknown source context " + str(key))
            ref_to_context[key] = cid
            (canonical_refs if ref["origin"] == canonical_origin else world_refs).append(
                ref["native_id"])
        # The only approved cross-dataset equivalence is an explicit pilot
        # canonical_state_id. Do not treat unrelated contexts as identical.
        require(len(canonical_refs) <= 1 and len(world_refs) <= 1,
                "many-to-one historical context merge is not approved")
        if canonical_refs and world_refs:
            world_record = world_polities[world_refs[0]]
            require(world_record.get("canonical_state_id") == canonical_refs[0],
                    "cross-dataset equivalence lacks explicit canonical_state_id")
        if world_refs and not canonical_refs:
            require(world_polities[world_refs[0]].get("canonical_state_id") is None,
                    "known canonical state link was omitted")

    expected_refs = ({(canonical_origin, state) for state in canonical_states} |
                     {(world_origin, state) for state in world_polities})
    require(set(ref_to_context) == expected_refs,
            "incomplete or unexpected world/canonical state coverage")

    # Special classifications are deliberate safety guardrails.
    expected_types = {
        "hre": "elective_office_context",
        "hab": "composite_monarchy",
        "meck": "birthplace_context",
        "fr": "polity_regime",
        "frrep": "polity_regime",
    }
    context_by_id = {c["id"]: c for c in x["contexts"]}
    for world_id, expected_type in expected_types.items():
        require(context_by_id[ref_to_context[(world_origin, world_id)]]["kind"] == expected_type,
                "incorrect type for world context " + world_id)
    require(ref_to_context[(world_origin, "ru")] ==
            ref_to_context[(canonical_origin, "empire")],
            "Russian Empire explicit link lost")

    for pair in x["must_remain_distinct"]:
        a = pair["left"]; b = pair["right"]
        left = ref_to_context.get((a["origin"], a["native_id"]))
        right = ref_to_context.get((b["origin"], b["native_id"]))
        require(left is not None and right is not None and left != right,
                "forbidden merge: " + str(pair))
        require(bool(pair["reason"]), "unexplained distinctness rule")

    world_person_rows = {}
    for filename, key in (("1762.json", "persons"),
                          ("dynasty-1762-1780.json", "additional_persons"),
                          ("extension-1781-1800.json", "additional_persons")):
        for person in w[filename][key]:
            require(person["id"] not in world_person_rows,
                    "duplicate world person " + person["id"])
            world_person_rows[person["id"]] = (filename, person)
    canonical_people = {p["id"]: p for p in db["people"]}
    canonical_tenures = {t["id"]: t for t in db["tenures"]}

    person_links = {}
    for link in x["people"]:
        wid = link["world_id"]
        require(wid in world_person_rows and wid not in person_links,
                "duplicate or unknown crosswalk person " + wid)
        filename, original = world_person_rows[wid]
        require(link["dataset"] == filename, "incorrect person origin " + wid)
        expected_person = original.get("canonical_person_id")
        expected_tenure = original.get("canonical_tenure_id")
        if expected_person is not None:
            require(link["resolution"] == "linked" and
                    link.get("canonical_person_id") == expected_person and
                    link.get("canonical_tenure_id") == expected_tenure and
                    link["basis"] == "explicit-existing-canonical-person-id",
                    "unapproved canonical identity change " + wid)
            require(expected_person in canonical_people and expected_tenure in canonical_tenures
                    and canonical_tenures[expected_tenure]["person_id"] == expected_person,
                    "pilot canonical identity / tenure is invalid: " + wid)
        else:
            require(link["resolution"] == "unresolved" and
                    "canonical_person_id" not in link and "canonical_tenure_id" not in link and
                    link["basis"] == "no-canonical-id-in-pilot" and bool(original.get("name")),
                    "unresolved identity was guessed or has no label: " + wid)
        person_links[wid] = link
    require(set(person_links) == set(world_person_rows), "missing world person crosswalk")

    world_roles = (w["dynasty-1762-1780.json"]["roles"] +
                   w["extension-1781-1800.json"]["additional_roles"])
    for role in world_roles:
        require(role["person_id"] in person_links and role["polity_id"] in world_polities,
                "unknown world role reference: " + role["id"])
        if "canonical_tenure_id" in role:
            ident = person_links[role["person_id"]]
            require(ident["resolution"] == "linked" and
                    ident["canonical_tenure_id"] == role["canonical_tenure_id"],
                    "role does not match explicit canonical tenure " + role["id"])

    sources = source_catalog(snapshot)
    source_ids = {s["native_id"] for s in sources}
    for filename in WORLD_FILES:
        for source_id in source_references(w[filename]):
            require(source_id in source_ids,
                    "missing source " + source_id + " in " + filename)
    linked = [p for p in person_links.values() if p["resolution"] == "linked"]
    return {
        "schema_version": x["schema_version"],
        "status": x["status"],
        "historical_truth_verified_by_ci": False,
        "canonical_contexts": len(canonical_states),
        "world_contexts": len(world_polities),
        "unified_contexts": len(context_ids),
        "context_refs": len(ref_to_context),
        "world_people": len(world_person_rows),
        "linked_people": len(linked),
        "unresolved_people": len(world_person_rows) - len(linked),
        "world_roles_with_person_refs": len(world_roles),
        "namespaced_sources": len(sources),
        "explicit_context_equivalences": [
            {"canonical": c, "world": w["id"]}
            for w in original_polities
            if (c := w.get("canonical_state_id")) is not None
        ],
        "linked_world_ids": sorted(p["world_id"] for p in linked),
    }


def populate_preview(conn: sqlite3.Connection, snapshot: dict) -> dict:
    """Write only disposable v2 overlay rows, on a v1 SQLite snapshot."""
    summary = validate(snapshot)
    config = snapshot["crosswalk"]
    db = snapshot["canonical"]
    canon_names = {p["id"]: p["name"] for p in db["people"]}
    originals = {}
    for filename, key in (("1762.json", "persons"),
                          ("dynasty-1762-1780.json", "additional_persons"),
                          ("extension-1781-1800.json", "additional_persons")):
        for p in snapshot["world"][filename][key]:
            originals[p["id"]] = p
    conn.execute("PRAGMA foreign_keys=ON")
    with conn:
        for c in config["contexts"]:
            conn.execute("INSERT INTO v2_contexts(id,label,kind,note) VALUES(?,?,?,?)",
                         (c["id"], c["label"], c["kind"], c["note"]))
            for r in c["refs"]:
                conn.execute(
                    "INSERT INTO v2_context_refs(origin,native_id,context_id,mapping,note)"
                    " VALUES(?,?,?,?,?)",
                    (r["origin"], r["native_id"], c["id"], r["mapping"], c["basis"]))
        for link in config["people"]:
            original = originals[link["world_id"]]
            canonical = link.get("canonical_person_id")
            label = canon_names[canonical] if canonical else original["name"]
            conn.execute(
                "INSERT INTO v2_external_people(origin,native_id,display_label,"
                "canonical_person_id,resolution) VALUES(?,?,?,?,?)",
                (config["world_person_origin"], link["world_id"], label, canonical,
                 link["resolution"]))
        for source in source_catalog(snapshot):
            conn.execute("INSERT INTO v2_sources VALUES(?,?,?,?,?,?,?)",
                         tuple(source[k] for k in ("key","origin","native_id","title",
                                                   "url","canonical_source_id","verification")))
    require(conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok",
            "SQLite integrity check failed")
    require(not conn.execute("PRAGMA foreign_key_check").fetchall(),
            "SQLite foreign keys invalid")
    return summary


def in_memory_preview(snapshot: dict) -> tuple[sqlite3.Connection, dict]:
    """Build v1 on disk inside an auto-deleted temporary directory; return RAM v2."""
    root = snapshot.get("root", ROOT)
    with tempfile.TemporaryDirectory(prefix="atlas-v2-crosswalk-") as temp:
        source_path = Path(temp) / "v1.sqlite"
        atlas_db.write_sqlite(snapshot["canonical"], source_path,
                              (root / "schemas/atlas.sql").read_text(encoding="utf-8"))
        base = sqlite3.connect(source_path)
        preview = sqlite3.connect(":memory:")
        try:
            base.backup(preview)
        finally:
            base.close()
    try:
        preview.executescript((root / "schemas/atlas_v2_candidate.sql").read_text(encoding="utf-8"))
        summary = populate_preview(preview, snapshot)
        require(preview.execute("PRAGMA user_version").fetchone()[0] == 1,
                "preview cannot alter v1 version")
        return preview, summary
    except Exception:
        preview.close()
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT,
                        help="checkout root, used only as read-only input")
    args = parser.parse_args()
    snapshot = load_snapshot(args.root)
    snapshot["root"] = args.root
    preview, result = in_memory_preview(snapshot)
    try:
        result["sqlite"] = {
            "integrity": preview.execute("PRAGMA integrity_check").fetchone()[0],
            "v1_user_version": preview.execute("PRAGMA user_version").fetchone()[0],
            "v2_context_rows": preview.execute("SELECT COUNT(*) FROM v2_contexts").fetchone()[0],
            "v2_external_people_rows": preview.execute(
                "SELECT COUNT(*) FROM v2_external_people").fetchone()[0],
            "v2_source_rows": preview.execute("SELECT COUNT(*) FROM v2_sources").fetchone()[0],
        }
    finally:
        preview.close()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
