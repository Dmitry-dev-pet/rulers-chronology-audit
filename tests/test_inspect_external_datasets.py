"""The external research inspection is read-only and does not infer history."""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.inspect_external_datasets import inspect_file, inspect_rows


class ExternalDatasetInspectionTests(unittest.TestCase):
    def test_csv_is_identified_but_not_merged(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "archigos.csv"
            path.write_text("obsid,leadid,leader\n1,AA,Alpha\n2,AA,Beta\n", encoding="utf-8")
            before = path.read_bytes()
            result = inspect_file("archigos", path)
            self.assertEqual(result["rows"], 2)
            self.assertEqual(result["candidate_identifiers_present"], ["obsid", "leadid"])
            self.assertEqual(result["repeated_identifier_values"], {"obsid": 0, "leadid": 1})
            self.assertEqual(result["sha256"], hashlib.sha256(before).hexdigest())
            self.assertFalse(result["canonical_data_modified"])
            self.assertFalse(result["historical_truth_verified_by_ci"])
            self.assertNotIn("Alpha", str(result))
            self.assertEqual(path.read_bytes(), before)

    def test_tsv_keeps_original_headers_and_missingness(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plad.tsv"
            path.write_text("plad_id\tarchigos_id\tplace\n1\tA\t\n2\tB\tCity\n", encoding="utf-8")
            result = inspect_file("plad", path)
            self.assertEqual(result["missing_values_by_column"]["place"], 1)
            self.assertEqual(result["rows"], 2)

    def test_empty_and_duplicate_columns_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate column"):
            inspect_rows(["leader", "leader"], [{"leader": "x"}], [])
        with self.assertRaisesRegex(ValueError, "no data rows"):
            inspect_rows(["leader"], [], [])

    def test_unknown_input_format_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.zip"
            path.write_bytes(b"placeholder")
            with self.assertRaisesRegex(ValueError, "Unsupported file"):
                inspect_file("plad", path)


if __name__ == "__main__":
    unittest.main()
