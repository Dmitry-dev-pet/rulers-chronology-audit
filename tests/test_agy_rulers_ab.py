"""Deterministic AGY rulers A/B safety tests; no Gemini, OAuth or live MCP calls."""
from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from benchmarks.run_agy_rulers_ab import (
    DENIED, TOOLS, atlas_tool, evaluate, install_lane, load_questions,
    parse_events, QUESTIONS,
)


class RulersTrialTests(unittest.TestCase):
    def test_ten_frozen_questions(self):
        spec = load_questions(QUESTIONS)
        self.assertEqual(spec["id"], "russian_rulers_10_v1")
        self.assertEqual(len(spec["questions"]), 10)
        self.assertEqual(len({x["id"] for x in spec["questions"]}), 10)

    def test_two_isolated_profiles_and_local_stdio_only(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            auth = root / "dedicated-authorization"
            auth.write_text("test-only-token", encoding="utf-8")
            os.chmod(auth, 0o600)
            atlas = root / "atlas"
            (atlas / "scripts").mkdir(parents=True)
            (atlas / "scripts" / "atlas_mcp_rulers.py").write_text("# fixture")
            sqlite = root / "atlas.sqlite"
            sqlite.write_bytes(b"fixture")
            python = root / "python"
            python.write_text("fixture")
            a, ah = install_lane(root / "run-a", "baseline", auth, atlas, sqlite, python)
            b, bh = install_lane(root / "run-b", "with_mcp", auth, atlas, sqlite, python)
            cfg_a = json.loads((a / ".agents/mcp_config.json").read_text())
            cfg_b = json.loads((b / ".agents/mcp_config.json").read_text())
            self.assertEqual(cfg_a, {"mcpServers": {}})
            self.assertEqual(sorted(cfg_b["mcpServers"]), ["historical-atlas"])
            srv = cfg_b["mcpServers"]["historical-atlas"]
            self.assertEqual(srv["args"], [str(atlas / "scripts/atlas_mcp_rulers.py")])
            self.assertEqual(srv["env"], {"ATLAS_SQLITE_PATH": str(sqlite)})
            self.assertNotIn("url", srv)
            self.assertNotIn("ATLAS_ARCHIGOS_PATH", srv["env"])
            aa = json.loads((ah / ".gemini/antigravity-cli/settings.json").read_text())
            bb = json.loads((bh / ".gemini/antigravity-cli/settings.json").read_text())
            self.assertIn("mcp(*)", aa["permissions"]["deny"])
            self.assertNotIn("mcp(*)", bb["permissions"]["deny"])
            self.assertEqual(aa["permissions"]["allow"], [])
            self.assertEqual(bb["permissions"]["allow"], [
                f"mcp(historical-atlas/{name})" for name in TOOLS
            ])
            self.assertIn("run_command(*)", DENIED)
            self.assertIn("read_url(*)", DENIED)
            self.assertNotEqual(ah, bh)
            self.assertEqual(
                (bh / ".gemini/antigravity-cli/antigravity-oauth-token").read_bytes(),
                b"test-only-token",
            )

    def fixture_run(self, calls=(), advertised=()):
        return {
            "status": "SUCCESS", "exit_code": 0, "diagnostic": "ok",
            "model_reported": "gemini-test",
            "answer": {"answer": "Разделим юридическую и фактическую власть.", "uncertainty": "", "source_refs": []},
            "structured_output_valid": True,
            "available_tools": list(advertised),
            "tool_events": [{"name": name, "state": "DONE"} for name in calls],
        }

    def test_baseline_refuses_any_tools_and_advertised_mcp(self):
        self.assertTrue(evaluate(self.fixture_run(), "gemini-test", False)["trial_valid"])
        self.assertFalse(evaluate(self.fixture_run(
            advertised=["mcp__historical-atlas__get_timeline"],
        ), "gemini-test", False)["trial_valid"])
        self.assertFalse(evaluate(self.fixture_run(
            calls=["mcp__historical-atlas__get_timeline"],
        ), "gemini-test", False)["trial_valid"])

    def test_powered_needs_real_successful_canonical_tool(self):
        self.assertFalse(evaluate(self.fixture_run(), "gemini-test", True)["trial_valid"])
        good = self.fixture_run(calls=["mcp__historical-atlas__get_timeline"])
        self.assertTrue(evaluate(good, "gemini-test", True)["trial_valid"])
        good["tool_events"][0]["state"] = "FAILED"
        self.assertFalse(evaluate(good, "gemini-test", True)["trial_valid"])
        good["tool_events"][0] = {"name": "mcp__historical-atlas__get_timeline", "state": "DONE", "error": True}
        self.assertFalse(evaluate(good, "gemini-test", True)["trial_valid"])

    def test_no_extra_tools_and_no_model_substitution(self):
        r = self.fixture_run(calls=[
            "mcp__historical-atlas__get_evidence", "run_command",
        ])
        self.assertFalse(evaluate(r, "gemini-test", True)["trial_valid"])
        r = self.fixture_run(calls=["mcp__historical-atlas__get_timeline"])
        self.assertFalse(evaluate(r, "gemini-other", True)["trial_valid"])
        r["model_reported"] = None
        self.assertFalse(evaluate(r, "gemini-test", True)["trial_valid"])

    def test_known_tool_names(self):
        self.assertEqual(atlas_tool("mcp__historical_atlas__get_timeline"), "get_timeline")
        self.assertEqual(atlas_tool("historical-atlas/get_evidence"), "get_evidence")
        self.assertIsNone(atlas_tool("mcp__other-server__get_timeline"))

    def test_parser_preserves_only_structured_answer_and_tool_metadata(self):
        stream = "\n".join(json.dumps(item) for item in [
            {"event": "init", "init": {
                "model": "gemini-test", "tools": [
                    "mcp__historical-atlas__get_timeline",
                ],
            }},
            {"event": "step_update", "step_update": {
                "step_type": "tool", "state": "DONE",
                "tool_name": "mcp__historical-atlas__get_timeline",
            }},
            {"event": "result", "result": {
                "status": "SUCCESS",
                "structured_output": {
                    "answer": "Тест", "uncertainty": "Годы приблизительны",
                    "source_refs": ["SOURCE-1"],
                },
                "usage": {"total_tokens": 123},
            }},
        ])
        parsed = parse_events(stream)
        self.assertEqual(parsed["model_reported"], "gemini-test")
        self.assertEqual(parsed["answer"]["answer"], "Тест")
        self.assertEqual(parsed["answer"]["source_refs"], ["SOURCE-1"])
        self.assertEqual(parsed["usage"]["total_tokens"], 123)
        self.assertTrue(parsed["structured_output_valid"])
        self.assertTrue(evaluate(
            {**parsed, "exit_code": 0, "diagnostic": "ok"}, "gemini-test", True,
        )["trial_valid"])


if __name__ == "__main__":
    unittest.main()
