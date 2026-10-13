"""Partial facsimile viewing must never silently prove the complete manuscript."""
from __future__ import annotations
import copy
import json
import unittest
from scripts import chernenko_facsimile_review as v
from scripts import historical_biographical_disputes as bio
from scripts import historical_disputes as h


class FacsimileReview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.real = v.verify()
        cls.biography = bio.registry()
        cls.facts = h.read_jsonl(h.ROOT / "data/atlas/person_facts.jsonl")

    def rejects(self, change, pattern):
        report = copy.deepcopy(self.real)
        change(report)
        with self.assertRaisesRegex(ValueError, pattern):
            v.validate(report, self.biography, self.facts)

    def test_exact_source_and_open_dispute(self):
        d = self.real
        self.assertEqual(d["related_case_id"], "HC-0005")
        self.assertEqual(d["official_catalog"]["record_number"], "32")
        self.assertEqual(d["official_catalog"]["year_stated_by_catalog"], 1912)
        self.assertEqual(d["catalog_birth_date_julian"], "1912-09-18")
        self.assertEqual(d["catalog_baptism_date_julian"], "1912-09-23")
        self.assertFalse(d["official_full_pages_visually_inspected"])
        self.assertFalse(d["original_manuscript_independently_authenticated"])
        self.assertFalse(d["independent_primary_checked"])
        self.assertTrue(d["case_remains_open"])
        self.assertEqual(bio.summary(self.biography)["by_status"], {"open": 1})

    def test_one_author_crop_is_not_two_independent_manuscripts(self):
        images = {x["id"]: x for x in self.real["images"]}
        self.assertEqual(len(images), 4)
        self.assertEqual(images["HC5-PHOTO-AUTHOR"]["origin_group"],
                         images["HC5-PHOTO-REPRINT"]["origin_group"])
        self.assertTrue(images["HC5-PHOTO-AUTHOR"]["viewed_as_pixels"])
        self.assertTrue(images["HC5-PHOTO-REPRINT"]["viewed_as_pixels"])
        self.assertFalse(images["HC5-PAGE-LINK-1"]["viewed_as_pixels"])
        self.assertFalse(images["HC5-PAGE-LINK-26"]["viewed_as_pixels"])
        self.assertFalse(self.real["birth_year_visually_verified_from_crop"])

    def test_only_specific_observed_crop_markers_are_recorded(self):
        actual = {x["field"]: x["transcription"]
                  for x in self.real["visible_markers_from_cropped_photo"]}
        self.assertEqual(actual, v.EXPECTED_MARKERS)
        self.assertNotIn("year", actual)
        self.assertNotIn("month", actual)

    def test_prohibits_false_primary_verification_or_resolution(self):
        for field in ("original_manuscript_independently_authenticated",
                      "official_full_pages_visually_inspected",
                      "independent_primary_checked",
                      "birth_year_visually_verified_from_crop",
                      "dispute_resolution_proposed",
                      "source_images_copied_to_repository"):
            with self.subTest(field=field):
                self.rejects(lambda d, f=field: d.__setitem__(f, True),
                             "Unverified manuscript")

    def test_full_page_links_must_not_claim_visual_access(self):
        self.rejects(lambda d: d["images"][3].update(viewed_as_pixels=True),
                     "Image provenance")
        self.rejects(lambda d: d["images"][2].update(
            url="https://evil.invalid/fake.JPG"), "Image provenance")
        self.rejects(lambda d: d["images"][0].update(
            origin_group="independent-new-manuscript"), "Image provenance")

    def test_cannot_rewrite_birth_or_record_number_by_research(self):
        self.rejects(lambda d: d["official_catalog"].update(
            year_stated_by_catalog=1911), "catalog provenance")
        self.rejects(lambda d: d["official_catalog"].update(
            record_number="99"), "catalog provenance")
        self.rejects(lambda d: d.update(
            catalog_birth_date_julian="1911-09-11"), "catalog day")
        self.rejects(lambda d: d["visible_markers_from_cropped_photo"][0].update(
            transcription="33"), "transcription drifted")
        self.rejects(lambda d: d.update(
            case_remains_open=False), "Cannot close")

    def test_legacy_biography_and_historical_cases_unchanged(self):
        older = h.registry()
        bio_doc = bio.registry()
        self.assertEqual(len(older["cases"]), 4)
        self.assertEqual(len(bio_doc["cases"]), 1)
        self.assertEqual(len(h.registry_all()["cases"]), 5)
        self.assertIsNone(bio_doc["cases"][0]["resolution"])
        self.assertFalse(bio_doc["cases"][0]["reviewed_primary_acts"])


if __name__ == "__main__":
    unittest.main()
