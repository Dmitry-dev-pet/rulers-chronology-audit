"""Mac MCP package: single-tool protocol and subscription-trial isolation tests."""
from __future__ import annotations

import asyncio
import importlib.util
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless
from unittest.mock import patch

from benchmarks.run_agy_mac_ab import DENIED, evaluate, install_lane
from scripts.archigos_returnees import calculate_returnees

HAS_MCP = importlib.util.find_spec("mcp") is not None


class MacTrialSafetyTests(TestCase):
    def test_isolated_homes_and_only_one_enabled_tool(self):
        with TemporaryDirectory() as name:
            root = Path(name)
            token = root / "session"
            token.write_bytes(b"synthetic-placeholder-only")
            os.chmod(token, 0o600)
            package = root / "package"
            package.mkdir()
            python = root / "python"
            python.write_text("not executable fixture")
            sqlite = root / "atlas.sqlite"
            sqlite.write_text("fixture")
            archigos = root / "archigos.dta"
            archigos.write_text("fixture")
            a, ah = install_lane(root / "work", "baseline", token, package, sqlite, archigos, python)
            b, bh = install_lane(root / "work", "with_mcp", token, package, sqlite, archigos, python)
            acfg = json.loads((a / ".agents/mcp_config.json").read_text())
            bcfg = json.loads((b / ".agents/mcp_config.json").read_text())
            self.assertFalse(acfg["mcpServers"])
            self.assertEqual(sorted(bcfg["mcpServers"]), ["historical-atlas"])
            self.assertEqual(bcfg["mcpServers"]["historical-atlas"]["args"], [
                str(package / "scripts" / "atlas_mcp_returnees.py")
            ])
            deny_a = json.loads((ah / ".gemini/antigravity-cli/settings.json").read_text())
            deny_b = json.loads((bh / ".gemini/antigravity-cli/settings.json").read_text())
            self.assertIn("mcp(*)", deny_a["permissions"]["deny"])
            self.assertNotIn("mcp(*)", deny_b["permissions"]["deny"])
            self.assertEqual(
                deny_b["permissions"]["allow"], ["mcp(historical-atlas/archigos_returnees)"]
            )
            self.assertIn("command(*)", DENIED)
            self.assertIn("write_file(*)", DENIED)
            self.assertNotEqual(ah, bh)
            self.assertEqual(
                (ah / ".gemini/antigravity-cli/antigravity-oauth-token").read_bytes(),
                b"synthetic-placeholder-only",
            )

    def test_never_claim_mcp_success_without_tool_call(self):
        expected = {
            "return_events": 597, "unique_country_person_keys": 449,
            "mean_gap_days": 1798.382, "excluded_conflicting_identity_groups": 7,
        }
        run = {
            "status": "SUCCESS", "exit_code": 0, "diagnostic": "ok",
            "tool_calls": [], "answer": {**expected, "insufficient_data": False}
        }
        self.assertFalse(evaluate(run, expected, powered=True)["trial_valid"])
        run["tool_calls"] = ["mcp__historical-atlas__archigos_returnees"]
        self.assertTrue(evaluate(run, expected, powered=True)["trial_valid"])
        run["tool_calls"].append("run_command")
        self.assertFalse(evaluate(run, expected, powered=True)["trial_valid"])


@skipUnless(HAS_MCP, "MCP SDK installed only in protocol smoke environment")
class SingleToolProtocolTests(TestCase):
    def test_only_returnees_is_visible_and_callable(self):
        from mcp import Client
        from scripts.atlas_mcp_returnees import create_server

        fixture = [
            {"idacr": "USA", "leadid": "person1", "obsid": "USA-1", "leader": "First",
             "startdate": "1980-01-01", "enddate": "1982-01-01", "yrborn": 1940},
            {"idacr": "USA", "leadid": "person1", "obsid": "USA-2", "leader": "First",
             "startdate": "1984-01-01", "enddate": "1986-01-01", "yrborn": 1940},
        ]
        with patch("scripts.atlas_mcp_returnees.read_archigos", return_value=(fixture, "dummy")):
            server = create_server("/not-a-real-source")
        async def exercise():
            async with Client(server, raise_exceptions=True) as client:
                tools = await client.list_tools()
                names = [t.name for t in (getattr(tools, "tools", tools))]
                self.assertEqual(names, ["archigos_returnees"])
                result = await client.call_tool("archigos_returnees", {})
                self.assertFalse(result.is_error)
                self.assertIn("return_events", str(result))
                self.assertIn("1", str(result))
        asyncio.run(exercise())
