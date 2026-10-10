"""Source-preserving structural checks for the early Romanov 1617–1817 layer."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import scripts.extend_romanovs as early


class EarlyRomanovTests(unittest.TestCase):
    def test_source_rows_and_real_reigns(self):
        data, sources, review = early.validated_input()
        self.assertEqual([r["row_id"] for r in review],
                         [f"{i:03}" for i in range(78, 91)])
        self.assertEqual(len(data["early_monarchy"]), 13)
        self.assertEqual(data["boundary_from"], "1617-01-01")
        self.assertEqual(data["boundary_to"], "1817-01-01")
        self.assertEqual(len(sources), 18)
        self.assertFalse(data["primary_acts_for_every_appointment_verified"])

    def test_joint_crowning_and_regency_not_replaced(self):
        data, _, review = early.validated_input()
        rulers = {r["person"]: r for r in data["early_monarchy"]}
        peter = next(r for k,r in rulers.items() if k.startswith("Пётр I"))
        ivan = next(r for k,r in rulers.items() if k.startswith("Иван V"))
        self.assertEqual(peter["from"], "1682")
        self.assertEqual(ivan["from"], "1682")
        self.assertEqual(ivan["to"], "1696")
        sophia = next(r for r in data["early_regency"] if r["person"].startswith("Софья"))
        self.assertEqual((sophia["from"], sophia["to"]), ("1682", "1689"))
        self.assertEqual(review[4]["row_id"], "082")
        self.assertEqual(review[4]["printed_reign"], "1689–1725")
        self.assertNotIn("Александр I", list(rulers))

    def test_ivan_vi_pedigree_and_old_calendar_are_annotated(self):
        data, _, review = early.validated_input()
        ruler = next(r for r in data["early_monarchy"] if r["person"].startswith("Иван VI"))
        self.assertIn("Ивана V", ruler["note"])
        ivan = next(r for r in review if r["row_id"] == "086")
        self.assertIn("правнук Петра I", ivan["assessment"])
        elizabeth = next(r for r in review if r["row_id"] == "087")
        self.assertEqual(elizabeth["printed_reign"], "1741–1761")
        self.assertEqual(elizabeth["corrected_life"], "1709–1762")
        self.assertIn("стар", elizabeth["assessment"])

    def test_rendering_escapes_user_or_source_html(self):
        row = {
            "row_id": "078", "printed_reign": "1613–1645",
            "printed_name": "Михаил <script>alert(1)</script>",
            "printed_life": "1596–1645", "assessment": "<img src=x>",
            "source_ids": "RM01", "verified_role_dates": "<iframe>",
            "corrected_life": "1596–1645"
        }
        html = early.poster_rows([row])
        self.assertNotIn("<script>", html)
        self.assertNotIn("<img src=x>", html)
        self.assertNotIn("<iframe>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("source-RM01", html)

    def test_private_or_untrusted_bibliography_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sources.md"
            path.write_text("| RM01 | [Private](https://drive.google.com/file/d/123) | secret |\n",
                            encoding="utf-8")
            with patch.object(early, "ROMANOV_SOURCES", path):
                with self.assertRaisesRegex(ValueError, "Unsafe or private source"):
                    early.sources()
            path.write_text("| RM01 | [A](https://example.org) | good |\n"
                            "| RM01 | [B](https://example.org) | duplicate |\n",
                            encoding="utf-8")
            with patch.object(early, "ROMANOV_SOURCES", path):
                with self.assertRaisesRegex(ValueError, "Duplicate source"):
                    early.sources()

    def test_duplicate_record_id_fails_closed(self):
        data, _, _ = early.validated_input()
        data = copy.deepcopy(data)
        data["early_regency"][0]["id"] = data["early_monarchy"][0]["id"]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "romanov.json"
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            with patch.object(early, "ROMANOV_JSON", path):
                with self.assertRaisesRegex(ValueError, "Duplicate/bad"):
                    early.validated_input()


if __name__ == "__main__":
    unittest.main()
