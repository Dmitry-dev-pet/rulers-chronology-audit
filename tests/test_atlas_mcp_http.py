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


if __name__ == "__main__":
    unittest.main()
