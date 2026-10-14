"""The network entrypoint is metadata-only; all domain data stays read-only."""
import asyncio
import importlib.util
import tempfile
import unittest
from pathlib import Path

from scripts import atlas_db

ROOT = Path(__file__).resolve().parents[1]
HAS_MCP = importlib.util.find_spec("mcp") is not None


@unittest.skipUnless(HAS_MCP, "MCP Python SDK optional in ordinary audit")
class HTTPProbeTests(unittest.TestCase):
    def test_probe_advertises_only_public_metadata(self):
        from mcp import Client
        from scripts.atlas_mcp import create_server

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "atlas.sqlite"
            atlas_db.write_sqlite(
                atlas_db.load(ROOT), db,
                (ROOT / "schemas" / "atlas.sql").read_text(encoding="utf-8")
            )

            async def exercise():
                # An unrelated configured Archigos path must not be exposed.
                async with Client(create_server(db, archigos_path="", probe_only=True),
                                  raise_exceptions=True) as client:
                    listed = await client.list_tools()
                    self.assertEqual([t.name for t in listed.tools], ["dataset_info"])
                    reply = await client.call_tool("dataset_info", {})
                    self.assertFalse(reply.is_error)
                    text = str(reply)
                    self.assertIn("canonical_persons", text)
                    self.assertIn("historical_truth_verified_by_ci", text)
                    self.assertIn("not all rulers globally", text)

            asyncio.run(exercise())



@unittest.skipUnless(HAS_MCP, "MCP Python SDK optional in ordinary audit")
class PrivateHTTPResearchTests(unittest.TestCase):
    """Only canonical source-bounded tools cross the private HTTP boundary."""

    def test_exact_remote_allowlist_and_live_read_queries(self):
        from mcp import Client
        from scripts.atlas_mcp import create_server
        from scripts.atlas_mcp_query import AtlasQuery

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "atlas.sqlite"
            atlas_db.write_sqlite(
                atlas_db.load(ROOT), db,
                (ROOT / "schemas" / "atlas.sql").read_text(encoding="utf-8"),
            )
            query = AtlasQuery(db)
            sample = query.search_rulers("Владимир Ленин", limit=1)["results"][0]
            timeline = query.get_timeline(1953, limit=50)
            evidential_record = next(
                entry["entry_id"] for entry in timeline["entries"] if entry["source_ids"]
            )

            async def exercise():
                # Even a passed explicit private path must be ignored in HTTP mode.
                server = create_server(
                    db, archigos_path="/private/never-read-archigos.dta",
                    http_read_only=True,
                )
                async with Client(server, raise_exceptions=True) as client:
                    listed = await client.list_tools()
                    self.assertEqual(
                        [tool.name for tool in listed.tools],
                        [
                            "dataset_info",
                            "search_rulers",
                            "get_timeline",
                            "compare_rulers",
                            "get_evidence",
                        ],
                    )

                    info = await client.call_tool("dataset_info", {})
                    self.assertFalse(info.is_error)
                    self.assertIn("canonical-rulers-atlas-v1", str(info))
                    self.assertIn("archigos_file_configured", str(info))
                    self.assertIn("False", str(info))

                    search = await client.call_tool(
                        "search_rulers", {"text": "Владимир Ленин", "limit": 3}
                    )
                    self.assertFalse(search.is_error)
                    self.assertIn(sample["person_id"], str(search))

                    year = await client.call_tool(
                        "get_timeline", {"year": 1953, "limit": 50}
                    )
                    self.assertFalse(year.is_error)
                    self.assertIn("precision_warning", str(year))
                    self.assertIn(evidential_record, str(year))

                    compared = await client.call_tool(
                        "compare_rulers", {"person_ids": [sample["person_id"]]}
                    )
                    self.assertFalse(compared.is_error)
                    self.assertIn(sample["person_id"], str(compared))
                    self.assertIn("historical_truth_verified_by_ci", str(compared))

                    evidence = await client.call_tool(
                        "get_evidence", {"record_id": evidential_record}
                    )
                    self.assertFalse(evidence.is_error)
                    self.assertIn(evidential_record, str(evidence))
                    self.assertIn("source_ids", str(evidence))
                    self.assertIn("historical_truth_verified_by_ci", str(evidence))
                    self.assertNotIn("drive.google.com", str(evidence).lower())

            asyncio.run(exercise())

    def test_network_transport_guards_conflicting_server_modes(self):
        from scripts.atlas_mcp import create_server

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "atlas.sqlite"
            atlas_db.write_sqlite(
                atlas_db.load(ROOT), db,
                (ROOT / "schemas" / "atlas.sql").read_text(encoding="utf-8"),
            )
            with self.assertRaisesRegex(ValueError, "mutually exclusive"):
                create_server(db, probe_only=True, http_read_only=True)



if __name__ == "__main__":
    unittest.main()
