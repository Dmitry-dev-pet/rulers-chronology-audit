"""Safety contract for pruning only duplicate successful browser evidence."""

import unittest
from datetime import datetime, timedelta, timezone

from scripts.maintenance.prune_browser_evidence import select_deletions

NOW = datetime(2026, 10, 13, 18, 0, tzinfo=timezone.utc)


def item(idx, run_id, hours=10, name="smuta-browser-evidence"):
    return {
        "id": idx,
        "name": name,
        "created_at": (NOW - timedelta(hours=hours)).isoformat(),
        "workflow_run": {"id": run_id},
        "expired": False,
        "size_in_bytes": 1024,
    }


def run(branch, event="push", conclusion="success", status="completed"):
    return {
        "head_branch": branch, "event": event,
        "conclusion": conclusion, "status": status,
    }


class TestBrowserEvidenceSelection(unittest.TestCase):
    def test_protect_open_pr_failures_and_recent_main(self):
        artifacts = [
            item(1, 1, 12), item(2, 2, 11), item(3, 3, 10),
            item(4, 4, 9), item(5, 5, 8), item(6, 6, 7),
            item(7, 7, 6), item(8, 8, 6), item(9, 9, 6),
            item(10, 10, 1), item(11, 11, 9, "soviet-chronology-report"),
        ]
        runs = {i: run("main") for i in range(1, 5)}
        runs.update({
            5: run("closed-pr", "pull_request"),
            6: run("open-pr", "pull_request"),
            7: run("failed-pr", "pull_request", "failure"),
            8: run("unknown", "workflow_dispatch"),
            9: run("pending-pr", "pull_request", None, "in_progress"),
            10: run("closed-pr", "pull_request"),
            11: run("main"),
        })
        chosen, reasons = select_deletions(artifacts, runs, {"open-pr"}, NOW)
        self.assertEqual([a["id"] for a in chosen], [1, 5])
        self.assertEqual(reasons["last_three_main_successes"], 3)
        self.assertEqual(reasons["open_or_unknown_pr"], 1)
        self.assertEqual(reasons["non_success_or_unfinished"], 2)
        self.assertEqual(reasons["newer_than_3_hours"], 1)
        self.assertEqual(reasons["unknown_event_or_branch"], 1)
        self.assertEqual(reasons["other_name"], 1)

    def test_missing_run_metadata_fails_closed(self):
        with self.assertRaises(KeyError):
            select_deletions([item(1, 99)], {}, set(), NOW)


if __name__ == "__main__":
    unittest.main()
