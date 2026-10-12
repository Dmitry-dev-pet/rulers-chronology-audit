"""Deterministic A/B harness scoring, without calling a model or accessing tokens."""
from __future__ import annotations

import json
import unittest

from benchmarks.run_agy_ab import parse_run, score


GOLD = {
    "expected": {
        "return_events": 597,
        "unique_country_person_keys": 449,
        "mean_gap_days": 1798.382,
        "excluded_conflicting_identity_groups": 7,
    }
}


def result(with_tool=False, abstain=False):
    answer = {
        "return_events": -1 if abstain else 597,
        "unique_country_person_keys": -1 if abstain else 449,
        "mean_gap_days": -1.0 if abstain else 1798.382,
        "excluded_conflicting_identity_groups": -1 if abstain else 7,
        "anomaly_example": "SWD-1888 and SWD-1991",
        "methodology_note": "Checked source ID plus birth years",
        "insufficient_data": abstain,
    }
    return {
        "status": "SUCCESS", "answer": answer,
        "used_tool_names": ["mcp__historical-atlas__archigos_returnees"] if with_tool else [],
    }


class BenchmarkScoringTests(unittest.TestCase):
    def test_baseline_without_tools_can_be_scored_for_accuracy(self):
        s = score(result(), GOLD, with_mcp=False)
        self.assertTrue(s["exact_aggregate_match"])
        self.assertFalse(s["used_archigos_mcp"])

    def test_with_mcp_requires_observed_invocation(self):
        s = score(result(with_tool=False), GOLD, with_mcp=True)
        self.assertFalse(s["exact_aggregate_match"])
        self.assertTrue(s["protocol_failed_or_mcp_not_used"])

    def test_verified_aggregate_requires_correct_counts(self):
        s = score(result(with_tool=True), GOLD, with_mcp=True)
        self.assertTrue(s["exact_aggregate_match"])
        changed = result(with_tool=True)
        changed["answer"]["return_events"] += 1
        self.assertFalse(score(changed, GOLD, with_mcp=True)["exact_aggregate_match"])

    def test_honest_abstention_separate_from_accuracy(self):
        s = score(result(abstain=True), GOLD, with_mcp=False)
        self.assertTrue(s["honest_abstention"])
        self.assertFalse(s["exact_aggregate_match"])

    def test_stream_json_tool_audit(self):
        lines = [
            {"event": "init", "init": {"model": "test-model", "tools": ["archigos_returnees"]}},
            {"event": "step_update", "step_update": {
                "state": "DONE", "step_type": "tool", "tool_name": "archigos_returnees"
            }},
            {"event": "result", "result": {
                "status": "SUCCESS", "structured_output": result()["answer"],
                "usage": {"total_tokens": 250},
            }},
        ]
        parsed = parse_run("\n".join(json.dumps(row) for row in lines))
        self.assertEqual(parsed["used_tool_names"], ["archigos_returnees"])
        self.assertEqual(parsed["model_requested"], "test-model")
        self.assertEqual(parsed["usage"]["total_tokens"], 250)


if __name__ == "__main__":
    unittest.main()
