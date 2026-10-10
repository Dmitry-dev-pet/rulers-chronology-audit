import copy
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from scripts.soviet_audit import (
    SOURCE_PATH, TRACKS, date_bounds, no_duplicate_keys,
    person_label, render, source_index, validate, validate_transcription,
)


def fixture():
    data = {"schema_version": 1, "as_of": "2026-10-10", "title": "Test <title>",
            "scope": "Test", "method": "Overlaps allowed", "calendar": "Gregorian",
            "source_index": SOURCE_PATH, "primary_acts_for_every_appointment_verified": False,
            "synchronized_examples": [], "open_verification_items": ["Still to verify"]}
    for n, key in enumerate(TRACKS):
        data[key] = [{"id": "PGSX"[n] + "01", "from": "1923", "to": "1924-01",
                      "person": None, "role": "Role <script>alert(1)</script>",
                      "status": "collective_transition", "sources": ["PC01"]}]
    sources = source_index("| PC01 | [Example](https://example.org/act_(1)) | Secondary reference |")
    return data, sources


class AuditTests(unittest.TestCase):
    def test_year_precision(self):
        self.assertEqual(date_bounds("1923"), (date(1923, 1, 1), date(1923, 12, 31)))

    def test_month_precision(self):
        self.assertEqual(date_bounds("1924-02"), (date(1924, 2, 1), date(1924, 2, 29)))

    def test_invalid_dates(self):
        for value in ("1923-02-29", "1923-13", "1923-1", "abc", 1923):
            with self.subTest(value=value), self.assertRaises(ValueError):
                date_bounds(value)

    def test_duplicate_json_key(self):
        with self.assertRaises(ValueError):
            json.loads('{"a":1,"a":2}', object_pairs_hook=no_duplicate_keys)

    def test_duplicate_source(self):
        row = "| PC01 | [X](https://example.org) | Note |\n"
        with self.assertRaises(ValueError):
            source_index(row + row)

    def test_unsafe_source(self):
        for url in ("javascript:alert(1)", "https://user:pass@example.org", "https://drive.google.com/file/d/example", "http://example.org"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                source_index(f"| PC01 | [X]({url}) | Note |")

    def test_valid_collective_overlap_and_partial_dates(self):
        data, sources = fixture()
        data["party"].append(dict(data["party"][0], id="P02"))
        self.assertEqual(validate(data, sources)["records"], 5)

    def test_duplicate_record(self):
        data, sources = fixture()
        data["party"].append(copy.deepcopy(data["party"][0]))
        with self.assertRaises(ValueError):
            validate(data, sources)

    def test_unknown_reference(self):
        data, sources = fixture()
        data["party"][0]["sources"] = ["PC99"]
        with self.assertRaises(ValueError):
            validate(data, sources)

    def test_reversed_range(self):
        data, sources = fixture()
        data["party"][0]["from"] = "1925"
        with self.assertRaises(ValueError):
            validate(data, sources)

    def test_multiple_cochairs_preserved(self):
        row = {"person": None, "initial_cochairs": ["One", "Two"]}
        self.assertEqual(person_label(row), "One; Two")

    def test_no_historical_verification_claim(self):
        data, sources = fixture()
        self.assertIs(validate(data, sources)["historical_truth_verified_by_ci"], False)

    def test_html_escape_and_source_anchor(self):
        data, sources = fixture()
        report = render(data, sources, validate(data, sources), "<revision>")
        self.assertNotIn("<script>", report)
        self.assertIn("&lt;script&gt;", report)
        self.assertIn("id='source-PC01'", report)
        self.assertNotIn("drive.google.com", report)

    def test_changed_transcription_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "transcription.tsv"
            path.write_text("altered", encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_transcription(path)


if __name__ == "__main__":
    unittest.main()
