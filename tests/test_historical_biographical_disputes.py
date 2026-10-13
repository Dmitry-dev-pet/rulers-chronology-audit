"""Biography extension to historical disputes — no automatic age, birth or power edits."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from scripts import historical_disputes as h
from scripts import historical_biographical_disputes as bio


class ChernenkoBiographyDispute(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = h.load_json(h.ROOT / bio.REGISTRY)

    def sandbox(self, folder: str, altered: dict) -> Path:
        root = Path(folder)
        for rel in (bio.FACTS, bio.SOURCES):
            dest = root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(h.ROOT / rel, dest)
        directory = root / "data/atlas/people"
        directory.mkdir(parents=True, exist_ok=True)
        pid = altered["cases"][0]["person_id"]
        for path in (h.ROOT / "data/atlas/people").glob("*.json"):
            person = h.load_json(path)
            if person["id"] == pid:
                shutil.copyfile(path, directory / path.name)
        target = root / bio.REGISTRY
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(altered, ensure_ascii=False), encoding="utf-8")
        return root

    def reject(self, mutate, reason):
        document = copy.deepcopy(self.original)
        mutate(document)
        with tempfile.TemporaryDirectory() as folder:
            root = self.sandbox(folder, document)
            with self.assertRaisesRegex(ValueError, reason):
                bio.registry(root)

    def test_chernenko_has_two_competing_birth_dates_in_canon(self):
        doc = bio.registry()
        self.assertEqual(doc["schema_version"], "historical-biographical-dispute-registry-v1")
        self.assertEqual(bio.summary(doc)["case_count"], 1)
        case = doc["cases"][0]
        self.assertEqual((case["id"], case["person_name"], case["kind"]),
                         ("HC-0005", "Константин Черненко", "birth_date_disagreement"))
        self.assertEqual(case["person_id"], "person-654bc370814d5452")
        self.assertEqual(case["review_status"], "open")
        self.assertIsNone(case["resolution"])
        self.assertFalse(case["reviewed_primary_acts"])
        self.assertFalse(case["historical_truth_verified_by_ci"])
        self.assertFalse(case["actual_power_inferred"])
        by_source = {x["source_id"]: x for x in case["observations"]}
        self.assertEqual(set(by_source), {"TP308", "TP309"})
        self.assertEqual(by_source["TP308"]["source_kind"], "archival_register_description")
        self.assertEqual(by_source["TP308"]["verification"], "reference_checked")
        self.assertEqual(by_source["TP309"]["verification"], "disputed")
        for source, old, new in (
            ("TP308", "1912-09-18", "1912-10-01"),
            ("TP309", "1911-09-11", "1911-09-24"),
        ):
            with self.subTest(source=source):
                obs = by_source[source]
                self.assertEqual(obs["claim_type"], "birth_date")
                self.assertEqual((obs["value"]["old_style"]["value"],
                                  obs["value"]["old_style"]["calendar"]),
                                 (old, "julian"))
                self.assertEqual((obs["value"]["new_style"]["value"],
                                  obs["value"]["new_style"]["calendar"]),
                                 (new, "gregorian"))
                self.assertEqual(obs["value"]["old_style"]["precision"], "day")
                self.assertFalse(obs["independent_primary_checked"])
                self.assertEqual(obs["pinned_canonical_fact"]["kind"], "birth")

    def test_unified_overview_includes_bio_without_changing_legacy_p9_cases(self):
        old = h.registry()
        merged = h.registry_all()
        self.assertEqual((len(old["cases"]), len(merged["cases"])), (4, 5))
        self.assertEqual(h.summary(merged)["distinct_people"], 4)
        self.assertEqual(h.summary(merged)["source_observations"], 10)
        self.assertEqual(h.summary(merged)["by_status"], {"open": 5})
        self.assertEqual(h.summary(merged)["by_type"]["birth_date_disagreement"], 1)
        self.assertEqual({x["id"] for x in old["cases"]},
                         {"HC-0001", "HC-0002", "HC-0003", "HC-0004"})
        self.assertEqual({x["id"] for x in merged["cases"]},
                         {"HC-0001", "HC-0002", "HC-0003", "HC-0004", "HC-0005"})
        report = h.render_markdown(merged)
        self.assertIn("Константин Черненко", report)
        self.assertIn("HC-0001", report)
        self.assertIn("HC-0005", report)

    def test_read_only_biography_validation_never_changes_source_facts(self):
        original_files = [h.ROOT / bio.FACTS, h.ROOT / bio.SOURCES,
                          h.ROOT / bio.REGISTRY, h.ROOT / h.REGISTRY]
        before = [hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in original_files]
        bio.registry()
        h.registry_all()
        after = [hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in original_files]
        self.assertEqual(before, after)

    def test_rejects_wrong_person_or_fact_provenance_drift(self):
        self.reject(lambda d: d["cases"][0].update(
            person_id="person-010d69ee64b3599c"), "identity-bound")
        self.reject(lambda d: d["cases"][0]["observations"][0]
                    ["pinned_canonical_fact"]["value"].update(value="1913-09-18"),
                    "fact/source drift")
        self.reject(lambda d: d["cases"][0]["observations"][1]
                    ["pinned_source_record"].update(url="https://example.org/forged"),
                    "fact/source drift")
        self.reject(lambda d: d["cases"][0]["observations"][0].update(
            source_id="TP309"), "fact/source drift")
        self.reject(lambda d: d["cases"][0].update(
            canonical_fact_ids=["fact-wrong", "fact-research-20261010-chernenko-birth-legacy"]),
            "fact/source drift")

    def test_rejects_invented_dates_calendars_and_missing_evidence(self):
        self.reject(lambda d: d["cases"][0]["observations"][0]
                    ["value"]["old_style"].update(value="1913-09-18"),
                    "date.*does not match canon")
        self.reject(lambda d: d["cases"][0]["observations"][0]
                    ["value"]["new_style"].update(precision="month"),
                    "precision does not match")
        self.reject(lambda d: d["cases"][0]["observations"][0]
                    ["value"]["new_style"].update(calendar="unspecified"),
                    "Source birth date")
        self.reject(lambda d: d["cases"][0]["observations"][0].update(
            source_url="https://drive.google.com/file/d/private"),
            "Missing historical source")
        self.reject(lambda d: d["cases"][0]["observations"].pop(),
                    "two verified identity-bound")
        self.reject(lambda d: d["cases"][0]["observations"][0].update(
            source_locator=""), "Missing historical source")
        self.reject(lambda d: d["cases"][0]["observations"][0].update(
            corroborating_url="https://site.com/?token=not-for-publication"),
            "Missing historical source")

    def test_no_auto_resolution_or_false_primary_attestation(self):
        self.reject(lambda d: d.update(historical_truth_verified_by_ci=True),
                    "nonattesting")
        self.reject(lambda d: d["cases"][0].update(
            review_status="resolved"), "manual biographical resolution")
        self.reject(lambda d: d["cases"][0].update(
            resolution={"winner": "1912"}), "cannot carry an automatic")
        self.reject(lambda d: d["cases"][0]["observations"][0].update(
            independent_primary_checked=True), "unsafe biography attestation")
        self.reject(lambda d: d["cases"][0].update(
            reviewed_primary_acts=True), "two verified identity-bound")

    def test_manual_resolution_requires_named_review_and_two_distinct_sources(self):
        doc = copy.deepcopy(self.original)
        case = doc["cases"][0]
        case["review_status"] = "resolved"
        case["resolution"] = {
            "reviewer": "Named research reviewer",
            "reason": "The review compared the original and older biographies.",
            "evidence_urls": ["https://culture19.ru/contents/587-7-metricheskaya-zapis.html",
                              "https://nbdrx.ru/arh3470.aspx"],
        }
        with tempfile.TemporaryDirectory() as folder:
            root = self.sandbox(folder, doc)
            checked = bio.registry(root)
            self.assertEqual(bio.summary(checked)["by_status"], {"resolved": 1})
        # This is a schema-level acceptance test; no such scholarly resolution was made.
        case["resolution"]["evidence_urls"][1] = case["resolution"]["evidence_urls"][0]
        with tempfile.TemporaryDirectory() as folder:
            root = self.sandbox(folder, doc)
            with self.assertRaisesRegex(ValueError, "manual biographical resolution"):
                bio.registry(root)

    def test_global_case_id_cannot_collide_with_p9_id(self):
        from unittest.mock import patch
        with patch.object(h, "registry", return_value={"cases": [{"id": "HC-0001"}]}), \
             patch.object(bio, "registry", return_value={"cases": [{"id": "HC-0001"}]}):
            with self.assertRaisesRegex(ValueError, "Duplicate stable historical dispute case ID"):
                h.registry_all()


if __name__ == "__main__":
    unittest.main()
