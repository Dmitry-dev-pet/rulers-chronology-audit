"""Structural regression tests of the 1417–1617 Moscow historical layer."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import scripts.soviet_audit as sov
import scripts.extend_century as century
import scripts.extend_romanovs as romanovs
import scripts.extend_muscovy as muscovy

ROOT = Path(__file__).resolve().parents[1]


class MuscovyExtensionTests(unittest.TestCase):
    def test_exact_original_rows_and_source_registry(self):
        data, sources, notes = muscovy.validated_input()
        self.assertEqual([row["row_id"] for row in notes],
                         [f"{x:03d}" for x in range(59, 78)])
        self.assertEqual(data["boundary_from"], "1417-01-01")
        self.assertEqual(data["boundary_to"], "1617-01-01")
        self.assertEqual(len(sources), 20)
        self.assertFalse(data["primary_acts_for_every_appointment_verified"])
        self.assertEqual(sum(len(data[k]) for k in muscovy.TRACKS), 46)

    def test_title_continuity_and_moscow_usobitsa(self):
        data, _, notes = muscovy.validated_input()
        rulers = data["muscovy_rulers"]
        self.assertTrue(any(r["person"].startswith("Василий I") and r["from"] == "1389" for r in rulers))
        self.assertTrue(any(r["person"].startswith("Василий II") and r["from"] == "1425" for r in rulers))
        self.assertTrue(any(r["person"].startswith("Иван IV") and r["from"] == "1533" for r in rulers))
        self.assertTrue(any(r["person"].startswith("Иван IV") and r["from"] == "1547" for r in rulers))
        self.assertFalse(any(r["person"].startswith("Михаил Фёдорович") for r in rulers))
        self.assertEqual(next(r for r in notes if r["row_id"] == "069")["printed_reign"], "1574–1576")

    def test_multiple_distinct_claimants_and_de_facto_leaders(self):
        data, _, notes = muscovy.validated_input()
        regents = {row["person"]: row for row in data["muscovy_regents"]}
        self.assertEqual(regents["Симеон Бекбулатович"]["from"], "1575")
        self.assertEqual(regents["Симеон Бекбулатович"]["to"], "1576")
        self.assertEqual(regents["Борис Годунов"]["from"], "1587")
        self.assertEqual(next(row for row in data["muscovy_rulers"]
                              if row["person"].startswith("Фёдор Иванович"))["to"], "1598")
        self.assertEqual(next(row for row in data["muscovy_rulers"]
                              if row["person"].startswith("Борис Фёдорович"))["from"], "1598")
        self.assertIn("nominal_grand_prince",
                      [row["status"] for row in data["muscovy_regents"]])
        self.assertIn("collective_interregnum",
                      [row["status"] for row in data["muscovy_regents"]])

    def test_disallowed_private_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "citations.md"
            file.write_text("| MS01 | [Private](https://drive.google.com/file/d/x) | secret |\n",
                            encoding="utf-8")
            with patch.object(muscovy, "SOURCES", file):
                with self.assertRaisesRegex(ValueError, "Unsafe source URL"):
                    muscovy.source_index()

    def test_poster_escapes_markup(self):
        row = {"row_id": "059", "printed_name": "Василий <script>alert(1)</script>",
               "printed_reign": "1389–1425", "printed_life": "1371–1425",
               "assessment": "<img src=x>", "verified_role_dates": "<iframe>",
               "corrected_life": "1371–1425", "source_ids": "MS01"}
        html = muscovy.poster_rows([row])
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertNotIn("<img src=x>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("href='#source-MS01'", html)

    def test_complete_four_stage_build_and_source_privacy(self):
        poster_before = (ROOT / "data/poster-transcription.tsv").read_bytes()
        sov.build(ROOT, ROOT / "dist", "test-four-stage")
        century.build()
        romanovs.build()
        report = muscovy.build()
        self.assertEqual(poster_before, (ROOT / "data/poster-transcription.tsv").read_bytes())
        self.assertEqual(report["original_poster_rows"], 48)
        self.assertEqual(report["range"], "1417–1991")
        html = (ROOT / "dist/index.html").read_text(encoding="utf-8")
        for term in ("Правители государства · 1417–1991", "poster-059", "poster-077",
                     "poster-078", "poster-106", "data-era='muscovy'",
                     "data-era='tsardom'", "source-MS01"):
            self.assertIn(term, html)
        payload = json.loads(html.split("<script id='chronology-data' type='application/json'>",1)[1].split("</script>",1)[0])
        self.assertEqual(len(payload["muscovy_rulers"]), 17)
        self.assertEqual(len(payload["party"]), 10)
        self.assertTrue(any(p["person"].startswith("Михаил Фёдорович") for p in payload["early_monarchy"]))
        check = json.loads((ROOT / "dist/validation.json").read_text(encoding="utf-8"))
        self.assertEqual(check["poster_rows"], 48)
        self.assertEqual(check["muscovy_records"], 46)
        self.assertFalse(check["historical_truth_verified_by_ci"])
        self.assertFalse(check["muscovy_primary_acts_verified"])
        self.assertTrue((ROOT / "dist/muscovy.csv").is_file())
        self.assertEqual(len(list((ROOT / "dist").iterdir())), 17)
        for artifact in (ROOT / "dist").iterdir():
            content = artifact.read_text(encoding="utf-8-sig")
            self.assertNotIn("drive.google.com", content)
            self.assertNotIn("1000428575.jpg", content)


if __name__ == "__main__":
    unittest.main()
