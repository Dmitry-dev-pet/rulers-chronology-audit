"""Offline integration tests of the three accessible site representations."""
import csv
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import scripts.soviet_audit as audit


class SiteViewsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for path in ("data", "data/atlas/world-pilots", "research", "site", "assets/original"):
            (self.root / path).mkdir(parents=True, exist_ok=True)
        source = Path(audit.__file__).resolve().parents[1] / "site"
        for f in ("site.css", "site.js", "year-view.js", "transition-view.js", "universal-atlas.js", "mobile-atlas.js", "world-atlas.js", "dynasty-atlas.js"):
            shutil.copyfile(source / f, self.root / "site" / f)
        shutil.copyfile(source.parent / "data/atlas/world-pilots/1762.json",
                        self.root / "data/atlas/world-pilots/1762.json")
        shutil.copyfile(source.parent / "data/atlas/world-pilots/dynasty-1762-1780.json",
                        self.root / "data/atlas/world-pilots/dynasty-1762-1780.json")
        shutil.copyfile(source.parent / "data/atlas/world-pilots/extension-1781-1800.json",
                        self.root / "data/atlas/world-pilots/extension-1781-1800.json")
        shutil.copyfile(source.parent / "data/atlas/world-pilots/dynasty-footprints-1762-1800.json",
                        self.root / "data/atlas/world-pilots/dynasty-footprints-1762-1800.json")
        shutil.copyfile(source.parent / "data/atlas/world-pilots/coverage-1762-1800.json",
                        self.root / "data/atlas/world-pilots/coverage-1762-1800.json")
        shutil.copyfile(source.parent / "data/atlas/world-pilots/geographic-context-1762-1800.json",
                        self.root / "data/atlas/world-pilots/geographic-context-1762-1800.json")
        self.transcript = self.root / "data/poster-transcription.tsv"
        self.review = self.root / "data/soviet-period-review.csv"
        with self.transcript.open("w", encoding="utf-8", newline="") as fp:
            writer = csv.writer(fp, delimiter="\t")
            writer.writerow(["row_id", "poster_side", "reign_as_printed", "person_as_printed",
                             "printed_qualifier", "lifespan_as_printed", "visual_reading_confidence"])
            for i in range(1, 107):
                writer.writerow([f"{i:03}", "R" if i >= 54 else "L", "1917–1923", "Человек",
                                 "", "1870–1924", "high"])
        with self.review.open("w", encoding="utf-8", newline="") as fp:
            writer = csv.writer(fp)
            writer.writerow(["row_id", "printed_name", "printed_reign", "printed_life", "category",
                             "verified_role_dates", "corrected_life", "assessment", "source_ids"])
            for i in range(97, 107):
                writer.writerow([f"{i:03}", "Человек", "1917–1923", "1870–1924",
                                 "soviet_party", "Уточнение <текст>", "1870–1924",
                                 "Вопрос о власти", "SV01;SV02"])
        self.data = {
            "schema_version": 1,
            "as_of": "2026-10-10",
            "title": "Test",
            "scope": "1917–1991",
            "method": "Должности могут пересекаться",
            "calendar": "Gregorian",
            "source_index": audit.SOURCE_PATH,
            "primary_acts_for_every_appointment_verified": False,
            "synchronized_examples": [{"date": "1970-07-01", "party": "Партия", "government": "Правительство", "state": "Государство"}],
            "open_verification_items": ["Протокол 1991 года"],
        }
        for prefix, track in zip("PGSX", audit.TRACKS):
            self.data[track] = [{"id": prefix + "01", "from": "1917", "to": "1923-12-31",
                                 "person": "Фигура <script>alert(1)</script>",
                                 "role": "Должность <ошибка>", "status": "formal_office",
                                 "sources": ["PC01"], "note": "Пример <сверка>"}]
        (self.root / audit.DATA_PATH).write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
        (self.root / audit.SOURCE_PATH).write_text(
            "| ID | Источник | Примечания |\n|---|---|---|\n| PC01 | [Акт](https://example.org/act) | Проверить документ |\n",
            encoding="utf-8",
        )

    def test_poster_preserves_original_printed_columns(self):
        rows = audit.poster_data(self.transcript, self.review)
        self.assertEqual(len(rows), 10)
        self.assertEqual(rows[0]["row_id"], "097")
        self.assertEqual(rows[0]["reign_as_printed"], "1917–1923")
        self.assertEqual(rows[0]["verified_role_dates"], "Уточнение <текст>")

    def test_source_mismatch_fails_closed(self):
        original = self.review.read_text(encoding="utf-8")
        self.review.write_text(original.replace("1917–1923", "1918–1923", 1), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "does not match"):
            audit.poster_data(self.transcript, self.review)

    def test_three_modes_and_xss_safe_markup(self):
        sources = audit.source_index((self.root / audit.SOURCE_PATH).read_text(encoding="utf-8"))
        result = audit.validate(self.data, sources)
        markup = audit.render(self.data, sources, result, "revision-test", audit.poster_data(self.transcript, self.review))
        self.assertIn("id='panel-poster'", markup)
        self.assertIn("id='panel-timeline'", markup)
        self.assertIn("id='panel-research'", markup)
        self.assertIn("Плакат</button>", markup)
        self.assertIn("href='#/people'", markup)
        self.assertIn("href='#/timeline/1685'", markup)
        self.assertIn("site.js?v=revision-tes", markup)
        self.assertIn("year-view.js?v=revision-tes", markup)
        self.assertIn("transition-view.js?v=revision-tes", markup)
        self.assertIn("universal-atlas.js?v=revision-tes", markup)
        self.assertIn("mobile-atlas.js?v=revision-tes", markup)
        self.assertIn("world-atlas.js?v=revision-tes", markup)
        self.assertIn("dynasty-atlas.js?v=revision-tes", markup)
        self.assertIn("site.css?v=revision-tes", markup)
        self.assertIn("aria-selected='true'", markup)
        self.assertIn("&lt;script&gt;", markup)
        self.assertNotIn("<script>alert(1)</script>", markup)
        self.assertIn("\\u003cscript\\u003e", markup)
        self.assertIn("id='source-PC01'", markup)
        self.assertIn("id='poster-097'", markup)
        self.assertNotIn("drive.google.com", markup)
        self.assertNotIn("1000428575.jpg", markup)

    def test_integrated_build_uses_only_expected_public_files(self):
        raw = self.transcript.read_bytes()
        original_blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\x00" + raw).hexdigest()
        with patch.object(audit, "TRANSCRIPT_BLOB", original_blob):
            result = audit.build(self.root, self.root / "dist", "revision-test")
        self.assertFalse(result["historical_truth_verified_by_ci"])
        self.assertEqual(result["records"], 4)
        files = {p.name for p in (self.root / "dist").iterdir()}
        self.assertEqual(files, {"index.html", "site.css", "site.js", "year-view.js", "transition-view.js", "universal-atlas.js", "mobile-atlas.js", "world-atlas.js", "world-1762.json", "dynasty-atlas.js", "world-dynasty-18c.json", "world-extension-1800.json", "world-house-footprints.json", "world-coverage-1800.json", "world-geographic-1800.json", "README.md", "SHA256SUMS",
                                 "chronology.json", "sources.json", "validation.json", "party.csv",
                                 "government.csv", "state_institutions.csv", "separate_records.csv"})
        for p in (self.root / "dist").iterdir():
            self.assertNotIn("drive.google.com", p.read_text(encoding="utf-8-sig"))
            self.assertNotIn("1000428575.jpg", p.read_text(encoding="utf-8-sig"))
        sums = (self.root / "dist/SHA256SUMS").read_text(encoding="utf-8")
        self.assertIn("site.js", sums)
        self.assertIn("site.css", sums)
        self.assertIn("year-view.js", sums)
        self.assertIn("transition-view.js", sums)
        self.assertIn("universal-atlas.js", sums)
        self.assertIn("mobile-atlas.js", sums)
        self.assertIn("world-atlas.js", sums)
        self.assertIn("world-1762.json", sums)
        self.assertIn("dynasty-atlas.js", sums)
        self.assertIn("world-dynasty-18c.json", sums)
        self.assertIn("world-extension-1800.json", sums)
        self.assertIn("world-house-footprints.json", sums)
        self.assertIn("world-coverage-1800.json", sums)
        self.assertEqual(len(sums.strip().splitlines()), len(files) - 1)


if __name__ == '__main__':
    unittest.main()
