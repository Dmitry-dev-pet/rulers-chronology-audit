"""Regression tests for the source-preserving 1817–1917 extension."""
import json
import unittest
from pathlib import Path

import scripts.extend_century as ext
import scripts.soviet_audit as sov

ROOT = Path(__file__).resolve().parents[1]


class ImperialCenturyTests(unittest.TestCase):
    def test_source_index_and_reigns(self):
        data, sources, rows = ext.validated_input()
        self.assertEqual(len(data["imperial_monarchy"]), 5)
        self.assertEqual(len(rows), 6)
        self.assertEqual([r["row_id"] for r in rows], ["091","092","093","094","095","096"])
        self.assertIn("IM02", sources)
        self.assertEqual(data["boundary_from"], "1817-01-01")
        self.assertIn("1825-12", [r["from"] for r in data["imperial_events"]])

    def test_provisional_government_not_labelled_emperor(self):
        data, _, _ = ext.validated_input()
        monarchs = {r["person"] for r in data["imperial_monarchy"]}
        self.assertNotIn("Константин Павлович", monarchs)
        self.assertEqual(data["imperial_monarchy"][0]["person"], "Александр I")
        self.assertTrue(any(r["person"]=="Александр Керенский"
                            for r in data["imperial_government"]))
        self.assertTrue(any("Комитет министров" in r["person"]
                            for r in data["imperial_government"]))

    def test_html_escapes_untrusted_notes(self):
        bad = [{"row_id":"091","printed_reign":"1801–1825",
                "printed_name":"Александр <script>alert(1)</script>",
                "printed_life":"1777–1825","assessment":"<img src=x>",
                "verified_role_dates":"<script>bad</script>",
                "corrected_life":"1777–1825","source_ids":"IM01"}]
        rendered = ext.poster_rows(bad)
        self.assertNotIn("<script>", rendered)
        self.assertNotIn("<img src=x>", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertIn("href='#source-IM01'", rendered)

    def test_complete_site_overlay_and_original_data(self):
        poster = ROOT / "data/poster-transcription.tsv"
        prior = poster.read_bytes()
        sov.build(ROOT, ROOT / "dist", "test-imperial")
        report = ext.build()
        rendered = (ROOT / "dist/index.html").read_text(encoding="utf-8")
        self.assertEqual(prior, poster.read_bytes())
        self.assertEqual(report["poster_rows"], 16)
        self.assertIn("poster-091", rendered)
        self.assertIn("poster-092", rendered)
        self.assertIn("poster-106", rendered)
        self.assertIn("1817–1991", rendered)
        self.assertIn("<b>16</b> строк плаката", rendered)
        self.assertIn("Монархия / партия", rendered)
        self.assertIn("data-era='imperial'", rendered)
        self.assertIn("source-IM01", rendered)
        self.assertNotIn("drive.google.com", rendered)
        self.assertNotIn("1000428575.jpg", rendered)
        start = "<script id='chronology-data' type='application/json'>"
        payload = json.loads(rendered.split(start, 1)[1].split("</script>", 1)[0])
        self.assertEqual(len(payload["imperial_monarchy"]), 5)
        self.assertEqual(len(payload["party"]), len(json.loads(
            (ROOT / "data/soviet-parallel-chronology.json").read_text(encoding="utf-8"))["party"]))
        check = json.loads((ROOT / "dist/validation.json").read_text(encoding="utf-8"))
        self.assertFalse(check["historical_truth_verified_by_ci"])
        self.assertFalse(check["imperial_primary_acts_verified"])
        self.assertTrue((ROOT / "dist/imperial.csv").is_file())
        self.assertEqual(len(list((ROOT / "dist").iterdir())), 19)  # world pilot: JS + sourced JSON
        for path in (ROOT / "dist").iterdir():
            self.assertNotIn("drive.google.com", path.read_text(encoding="utf-8-sig"))

if __name__ == "__main__":
    unittest.main()
