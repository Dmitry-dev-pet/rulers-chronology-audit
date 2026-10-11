"""Contract tests for safe atlas MCP queries and independent Archigos statistics."""
from __future__ import annotations

import asyncio
import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts import atlas_db
from scripts.archigos_returnees import calculate_returnees
from scripts.atlas_mcp_query import AtlasQuery

ROOT = Path(__file__).resolve().parents[1]
HAS_MCP = importlib.util.find_spec("mcp") is not None


class ReadOnlyAtlasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.sqlite = Path(cls.tmp.name) / "atlas.sqlite"
        atlas_db.write_sqlite(
            atlas_db.load(ROOT), cls.sqlite, (ROOT / "schemas" / "atlas.sql").read_text(encoding="utf-8")
        )
        cls.query = AtlasQuery(cls.sqlite)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_source_of_truth_and_explicit_scope(self):
        info = self.query.dataset_info()
        self.assertEqual(info["dataset"], "canonical-rulers-atlas-v1")
        self.assertGreaterEqual(info["canonical_persons"], 83)
        self.assertFalse(info["historical_truth_verified_by_ci"])

    def test_find_by_cyrillic_and_year(self):
        found = self.query.search_rulers("пётр")
        self.assertTrue(any("Пётр" in p["name"] for p in found["results"]))
        self.assertGreaterEqual(found["count"], 1)
        self.assertEqual(self.query.search_rulers("no-such-person")["count"], 0)
        with self.assertRaises(ValueError):
            self.query.search_rulers("x", limit=1001)

    def test_cannot_write_to_canonical_sqlite(self):
        with self.query._connect() as db:
            with self.assertRaises(sqlite3.OperationalError):
                db.execute("DELETE FROM people")

    def test_timeline_preserves_caveats_and_sources(self):
        result = self.query.get_timeline(1953, limit=100)
        self.assertTrue(result["entries"])
        self.assertIn("not prove", result["precision_warning"])
        self.assertFalse(result["historical_truth_verified_by_ci"])
        ids = [r["entry_id"] for r in result["entries"]]
        self.assertEqual(len(ids), len(set(ids)))
        source_record = next((r for r in result["entries"] if r["source_ids"]), None)
        self.assertIsNotNone(source_record)
        evidence = self.query.get_evidence(source_record["entry_id"])
        self.assertTrue(evidence["found"])
        self.assertTrue(evidence["sources"])
        self.assertTrue(all(x["url"].startswith("https://") and
                            "drive.google.com" not in x["url"] for x in evidence["sources"]))

    def test_person_comparison_and_unknown_identity(self):
        person = self.query.search_rulers("Владимир Ленин")["results"][0]
        result = self.query.compare_rulers([person["person_id"]])
        self.assertEqual(result["persons"][0]["person_id"], person["person_id"])
        self.assertTrue(result["persons"][0]["roles_and_assessments"])
        with self.assertRaises(ValueError):
            self.query.compare_rulers(["person-does-not-exist"])
        with self.assertRaises(ValueError):
            self.query.compare_rulers([person["person_id"]] * 2)


def spell(idacr, leadid, obsid, leader, startdate, enddate, yrborn):
    return dict(idacr=idacr, leadid=leadid, obsid=obsid, leader=leader,
                startdate=startdate, enddate=enddate, yrborn=yrborn)


class ArchigosMethodTests(unittest.TestCase):
    @staticmethod
    def sample():
        return [
            spell("USA", "cleveland", "USA-1885", "Cleveland", "1885-03-04", "1889-03-04", 1837),
            spell("USA", "cleveland", "USA-1893", "Cleveland", "1893-03-04", "1897-03-04", 1837),
            spell("USA", "other", "USA-1900", "Other", "1900-01-01", "1901-01-01", 1850),
            # Deliberate corrupt identity reuse: two different people, same leadid.
            spell("SWD", "bildt", "SWD-1888", "Bildt", "1888-02-06", "1889-10-12", 1820),
            spell("SWD", "bildt", "SWD-1991", "Bildt", "1991-10-30", "1994-10-07", 1949),
        ]

    def test_valid_return_and_invalid_sweden_join(self):
        result = calculate_returnees(self.sample(), limit=100)
        self.assertEqual(result["return_events"], 1)
        self.assertEqual(result["unique_returning_country_person_keys"], 1)
        self.assertEqual(result["mean_gap_days"], 1461)
        self.assertEqual(result["events"][0]["previous_obsids"], ["USA-1885"])
        self.assertEqual(result["events"][0]["return_obsids"], ["USA-1893"])
        self.assertEqual(result["excluded_conflicting_identity_groups"][0]["country_code"], "SWD")
        self.assertEqual(result["excluded_conflicting_identity_groups"][0]["conflicting_birth_years"], [1820, 1949])
        self.assertFalse(result["historical_truth_verified_by_ci"])

    def test_country_filter_and_zero_day_gap(self):
        rows = self.sample() + [
            spell("XYZ", "same", "XYZ-1", "Same", "1990-01-01", "1991-01-01", 1950),
            spell("XYZ", "same", "XYZ-2", "Same", "1991-01-01", "1992-01-01", 1950),
        ]
        self.assertEqual(calculate_returnees(rows, country_code="XYZ")["return_events"], 0)
        self.assertEqual(calculate_returnees(rows, country_code="USA")["return_events"], 1)
        self.assertEqual(calculate_returnees(rows, min_gap_days=1500)["return_events"], 0)

    def test_input_validation(self):
        with self.assertRaises(ValueError):
            calculate_returnees(self.sample(), start_year=2016)
        with self.assertRaises(ValueError):
            calculate_returnees(self.sample(), country_code="Russia")
        with self.assertRaises(ValueError):
            calculate_returnees(self.sample(), limit=999)


@unittest.skipUnless(HAS_MCP, "The optional MCP Python SDK v2 is not installed")
class ProtocolTests(unittest.TestCase):
    def test_sdk_in_memory_tools_roundtrip(self):
        from mcp import Client
        from scripts.atlas_mcp import create_server
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "atlas.sqlite"
            atlas_db.write_sqlite(
                atlas_db.load(ROOT), path, (ROOT / "schemas" / "atlas.sql").read_text(encoding="utf-8")
            )

            async def exercise():
                server = create_server(path, archigos_path="")
                async with Client(server, raise_exceptions=True) as client:
                    info = await client.call_tool("dataset_info", {})
                    self.assertFalse(info.is_error)
                    self.assertIn("canonical_persons", str(info))
                    years = await client.call_tool("get_timeline", {"year": 1953})
                    self.assertFalse(years.is_error)
                    self.assertIn("precision_warning", str(years))
                    arch = await client.call_tool("archigos_returnees", {})
                    self.assertFalse(arch.is_error)
                    self.assertIn("not configured", str(arch))
            asyncio.run(exercise())


if __name__ == "__main__":
    unittest.main()
