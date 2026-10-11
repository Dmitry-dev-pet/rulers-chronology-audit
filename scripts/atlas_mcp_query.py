"""Safe, read-only query layer over the derived canonical atlas.sqlite.

No arbitrary SQL tool is exposed. All inputs are bound parameters or
validated bounded scalars. Year intersections identify candidate periods,
not exact overlap on a day or proof of de-facto control.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from contextlib import contextmanager


class AtlasQuery:
    def __init__(self, sqlite_path: str | Path):
        self.path = Path(sqlite_path).expanduser().resolve(strict=True)
        if not self.path.is_file():
            raise FileNotFoundError("Atlas SQLite is not a file")
        with self._connect() as db:
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            required = {"people", "entries", "person_facts", "sources", "entry_sources", "entry_states", "states"}
            if not required <= tables or db.execute("PRAGMA user_version").fetchone()[0] != 1:
                raise ValueError("Not canonical atlas.sqlite schema v1")

    @contextmanager
    def _connect(self):
        con = sqlite3.connect(self.path.as_uri() + "?mode=ro&immutable=1", uri=True, timeout=2)
        try:
            con.row_factory = sqlite3.Row
            con.execute("PRAGMA query_only=ON")
            yield con
        finally:
            con.close()

    @staticmethod
    def _limit(n: int, maximum: int = 100) -> int:
        if not isinstance(n, int) or not 1 <= n <= maximum:
            raise ValueError(f"limit must be 1..{maximum}")
        return n

    @staticmethod
    def _year(year: int) -> int:
        if not isinstance(year, int) or not 1 <= year <= 9999:
            raise ValueError("year must be a valid CE year")
        return year

    @staticmethod
    def _data(row: sqlite3.Row) -> dict:
        return json.loads(row["data_json"])

    @staticmethod
    def _safe_source(row: sqlite3.Row) -> dict | None:
        link = row["url"]
        if not isinstance(link, str) or not link.startswith("https://") or "drive.google.com" in link.lower():
            return None
        return {"id": row["id"], "title": row["title"], "url": link}

    def _sources(self, db: sqlite3.Connection, keys: list[str]) -> list[dict]:
        keys = list(dict.fromkeys(keys))[:50]
        if not keys:
            return []
        q = ",".join("?" for _ in keys)
        found = {s["id"]: s for row in db.execute(
            f"SELECT id,title,url FROM sources WHERE id IN ({q})", keys
        ) if (s := self._safe_source(row)) is not None}
        return [found[key] for key in keys if key in found]

    def dataset_info(self) -> dict:
        with self._connect() as db:
            counts = {kind: count for kind, count in db.execute(
                "SELECT kind,COUNT(*) FROM entries GROUP BY kind ORDER BY kind"
            )}
            years = db.execute("SELECT MIN(start_year),MAX(end_year) FROM entries").fetchone()
            return {
                "dataset": "canonical-rulers-atlas-v1",
                "canonical_persons": db.execute("SELECT COUNT(*) FROM people").fetchone()[0],
                "entries_by_kind": counts,
                "earliest_recorded_start_year": years[0],
                "latest_recorded_end_year": years[1],
                "scope_note": "Canonical Russian atlas, not all rulers globally; international world pilots are separate.",
                "historical_truth_verified_by_ci": False,
            }

    def search_rulers(self, text: str = "", year: int | None = None, limit: int = 20) -> dict:
        """Search canonical people by names and aliases, optionally active in a year."""
        self._limit(limit)
        if len(text) > 120:
            raise ValueError("Search query exceeds 120 characters")
        if year is not None:
            self._year(year)
        needle = text.strip().casefold()
        with self._connect() as db:
            allowed = None
            if year is not None:
                allowed = {r[0] for r in db.execute(
                    "SELECT DISTINCT person_id FROM entries WHERE person_id IS NOT NULL "
                    "AND start_year <= ? AND end_year >= ?", (year, year)
                )}
            found = []
            for row in db.execute("SELECT id,name,data_json FROM people ORDER BY name"):
                record = json.loads(row["data_json"])
                names = [row["name"]] + list(record.get("aliases", []))
                if (not needle or any(needle in name.casefold() for name in names)) and (
                    allowed is None or row["id"] in allowed
                ):
                    found.append({"person_id": row["id"], "name": row["name"], "aliases": record.get("aliases", [])})
            return {
                "query": text, "year": year, "count": len(found), "results": found[:limit],
                "truncated": len(found) > limit,
                "note": "Name and alias search is within the canonical dataset only; year overlap is not day-level concurrency.",
            }

    def get_timeline(self, year: int, state_id: str = "", limit: int = 40, offset: int = 0) -> dict:
        """Formal terms and separate interpretations of influence in a year."""
        self._year(year)
        self._limit(limit)
        if not isinstance(offset, int) or not 0 <= offset <= 100000:
            raise ValueError("offset must be 0..100000")
        if len(state_id) > 64:
            raise ValueError("state_id exceeds 64 characters")
        where = "e.start_year <= ? AND e.end_year >= ?"
        params: list = [year, year]
        if state_id:
            where += " AND EXISTS (SELECT 1 FROM entry_states es WHERE es.entry_id=e.id AND es.state_id=?)"
            params.append(state_id)
        with self._connect() as db:
            count = db.execute("SELECT COUNT(*) FROM entries e WHERE " + where, params).fetchone()[0]
            sql = (
                "SELECT e.*,p.name person_name,b.name body_name,o.title office_title "
                "FROM entries e LEFT JOIN people p ON p.id=e.person_id "
                "LEFT JOIN bodies b ON b.id=e.body_id "
                "LEFT JOIN offices o ON o.id=e.office_id "
                "WHERE " + where + " ORDER BY e.kind,e.start_year,e.id LIMIT ? OFFSET ?"
            )
            rows = db.execute(sql, [*params, limit, offset]).fetchall()
            results = []
            for row in rows:
                detail = self._data(row)
                results.append({
                    "entry_id": row["id"], "kind": row["kind"],
                    "person_id": row["person_id"], "person_name": row["person_name"],
                    "body_id": row["body_id"], "body_name": row["body_name"],
                    "office_id": row["office_id"], "office_title": row["office_title"],
                    "start": detail.get("start"), "end": detail.get("end"),
                    "status": row["status"], "description": row["description"],
                    "verification": detail.get("verification", "not_assessed"),
                    "confidence": detail.get("confidence", "not_assessed"),
                    "source_ids": detail.get("sources", []),
                })
        return {
            "year": year, "state_id": state_id or None, "total_candidate_entries": count,
            "offset": offset, "limit": limit, "entries": results,
            "has_more": offset + limit < count,
            "precision_warning": "Year intersection only; does not prove same-day overlap or factual control.",
            "historical_truth_verified_by_ci": False,
        }

    def compare_rulers(self, person_ids: list[str]) -> dict:
        """Compare a small set of stable canonical person IDs without guessing links."""
        if not isinstance(person_ids, list) or not 1 <= len(person_ids) <= 5:
            raise ValueError("Provide between 1 and 5 person IDs")
        if len(set(person_ids)) != len(person_ids) or any(not isinstance(k, str) or len(k) > 90 for k in person_ids):
            raise ValueError("IDs must be distinct bounded strings")
        with self._connect() as db:
            people = []
            for person_id in person_ids:
                row = db.execute("SELECT id,name FROM people WHERE id=?", (person_id,)).fetchone()
                if row is None:
                    raise ValueError("Unknown canonical person_id: " + person_id)
                terms = [self._data(r) for r in db.execute(
                    "SELECT data_json FROM entries WHERE person_id=? ORDER BY start_year,id", (person_id,)
                )]
                facts = [self._data(r) for r in db.execute(
                    "SELECT data_json FROM person_facts WHERE person_id=? ORDER BY kind,id", (person_id,)
                )]
                people.append({
                    "person_id": row["id"], "name": row["name"],
                    "roles_and_assessments": [{
                        "id": item["id"], "record_type": (
                            "historical_assessment" if item["id"].startswith("power-") else "source_record"
                        ), "start": item["start"], "end": item["end"],
                        "description": item["description"], "status": item["status"],
                        "source_ids": item.get("sources", []),
                        "verification": item.get("verification", "not_assessed"),
                    } for item in terms],
                    "biographical_facts": [{
                        "kind": item["kind"], "value": item["value"],
                        "verification": item["verification"], "source_ids": item["sources"],
                    } for item in facts if item["kind"] != "lifespan_text"],
                })
            return {
                "persons": people,
                "warning": "Roles, assessed influence and conflicting biographical facts are not interchangeable.",
                "historical_truth_verified_by_ci": False,
            }

    def get_evidence(self, record_id: str) -> dict:
        """Look up a canonical source-linked entry or biographical fact."""
        if not isinstance(record_id, str) or len(record_id) > 100:
            raise ValueError("record_id must be a bounded string")
        with self._connect() as db:
            entry = db.execute("SELECT kind,data_json FROM entries WHERE id=?", (record_id,)).fetchone()
            fact = None if entry else db.execute(
                "SELECT kind,data_json FROM person_facts WHERE id=?", (record_id,)
            ).fetchone()
            record = entry or fact
            if record is None:
                return {"found": False, "record_id": record_id}
            detail = self._data(record)
            return {
                "found": True, "record_id": record_id, "kind": record["kind"],
                "start": detail.get("start"), "end": detail.get("end"),
                "source_ids": detail.get("sources", []),
                "sources": self._sources(db, detail.get("sources", [])),
                "verification": detail.get("verification", "not_assessed"),
                "confidence": detail.get("confidence", "not_assessed"),
                "note": detail.get("note", detail.get("evidence", "")),
                "historical_truth_verified_by_ci": False,
            }
