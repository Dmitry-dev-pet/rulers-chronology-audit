"""Offline regression tests for Wikidata P2 identity and legal-office review."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts import wikidata_office_review as offices
from scripts import wikidata_sync as wd


def statement(qid, start=None, end=None, rank="normal"):
    qualifiers = {}
    if start is not None:
        qualifiers["P580"] = [{"snaktype": "value", "time": start}]
    if end is not None:
        qualifiers["P582"] = [{"snaktype": "value", "time": end}]
    return {
        "statement_id": "Qtest$P39-" + qid,
        "rank": rank,
        "value": {"snaktype": "value", "qid": qid},
        "qualifiers": qualifiers,
        "references": [{"hash": "document-reference"}],
    }


def date(value, calendar="gregorian", precision=11):
    return {"time": value, "calendar": calendar, "precision": precision,
            "calendarmodel": ("http://www.wikidata.org/entity/Q1985727" if
                              calendar == "gregorian" else
                              "http://www.wikidata.org/entity/Q1985786")}


def record(subject, kind, wikidata, claims):
    return {
        "subject_id": subject, "kind": kind, "name": subject,
        "wikidata_id": wikidata,
        "wikidata": {"qid": wikidata,
                     "statements": {"position_held": claims}},
    }


def snapshot(*records):
    return {
        "schema_version": "wikidata-reconciliation-v1",
        "historical_truth_verified": False,
        "mutated_canonical_data": False,
        "records": list(records),
    }


class ReviewedWorldIdentities(unittest.TestCase):
    def test_registry_is_complete_and_keeps_world_ids_independent(self):
        subjects = wd.roster(wd.ROOT)
        by_id = {v["subject_id"]: v for v in subjects}
        self.assertEqual(len(by_id), len(subjects))
        self.assertEqual(by_id["world:pr-frederick2"]["wikidata_id"], "Q33550")
        self.assertEqual(by_id["world:hab-leopold"]["wikidata_id"], "Q151321")
        self.assertEqual(by_id["world:gb-george3"]["wikidata_id"], "Q127318")
        self.assertIsNone(by_id["world:pt-joao"]["wikidata_id"])
        self.assertEqual(by_id["person-e88112738c1054f5"]["wikidata_id"], "Q855")
        self.assertEqual(by_id["person-7720af2ff3445d9d"]["wikidata_id"], "Q229828")
        self.assertEqual(by_id["person-fccacd3aa737598e"]["wikidata_id"], "Q297032")
        registry = wd.read_json(wd.ROOT / "design/wikidata/reviewed-world-links-v1.json")
        self.assertEqual(len(registry["links"]), 17)
        banned = {(r["world_id"], r["wikidata_qid"])
                  for r in registry["rejected_candidates"]}
        self.assertIn(("pr-frederick2", "Q130221"), banned)
        self.assertIn(("hab-leopold", "Q12967"), banned)
        for item in registry["links"]:
            self.assertNotIn((item["world_id"], item["wikidata_qid"]), banned)

    def test_crosswalk_does_not_reinterpret_world_as_canonical(self):
        records = wd.roster(wd.ROOT)
        c = [r for r in records if r["kind"] == "canonical"]
        w = [r for r in records if r["kind"] == "world_unlinked"]
        self.assertEqual(len(c), len(list((wd.ROOT / "data/atlas/people").glob("*.json"))))
        self.assertEqual(len(w), 24)
        self.assertEqual(sum(bool(x["wikidata_id"]) for x in w), 17)
        qids = [r["wikidata_id"] for r in records if r["wikidata_id"]]
        self.assertEqual(len(qids), len(set(qids)))


class P39OfficeMapping(unittest.TestCase):
    def test_curated_mapping_has_real_fk_and_excluded_family(self):
        rows = offices.reviewed_offices(wd.ROOT)
        self.assertEqual(rows["Q2618625"]["office_id"], "emperor")
        self.assertEqual(rows["Q1255261"]["office_id"], "president-ussr")
        self.assertEqual(rows["Q1048744"]["relation"], "office_family_only")
        self.assertIn("first-secretary", rows["Q1048744"]["related_office_ids"])
        self.assertIsNone(rows["Q3240735"]["office_id"])

    def test_presidency_dates_are_candidates_not_power_assertions(self):
        snap = snapshot(record(
            "person-8ace0ae735b35ada", "canonical", "Q30487",
            [statement("Q1255261", date("+1990-03-15T00:00:00Z"),
                       date("+1991-12-25T00:00:00Z"))],
        ))
        report = offices.office_review(wd.ROOT, snap)
        s = report["subjects"][0]["positions"][0]
        self.assertEqual(s["decision"], "exact_office")
        self.assertEqual(len(s["candidate_canonical_tenures"]), 1)
        match = s["candidate_canonical_tenures"][0]
        self.assertEqual(match["canonical_tenure_id"], "tenure-s21")
        self.assertEqual(match["start_comparison"], "same_recorded_date")
        self.assertEqual(match["end_comparison"], "same_recorded_date")
        self.assertFalse(report["asserted_real_power"])
        self.assertFalse(report["mutated_canonical_data"])

    def test_party_secretary_remains_office_family_only(self):
        snap = snapshot(record(
            "person-8ace0ae735b35ada", "canonical", "Q30487",
            [statement("Q1048744", date("+1985-03-11T00:00:00Z"))],
        ))
        report = offices.office_review(wd.ROOT, snap)
        r = report["subjects"][0]["positions"][0]
        self.assertEqual(r["decision"], "office_family_only")
        self.assertIn("tenure-p10", [x["canonical_tenure_id"]
                                     for x in r["candidate_canonical_tenures"]])
        self.assertEqual(report["summary"]["exact_office_with_canonical_candidates"]
                         if "exact_office_with_canonical_candidates" in report["summary"]
                         else 0, 0)

    def test_stalin_1946_legal_reorganization_is_not_silently_equal(self):
        snap = snapshot(record(
            "person-e88112738c1054f5", "canonical", "Q855",
            [statement("Q4376674")],
        ))
        report = offices.office_review(wd.ROOT, snap)
        r = report["subjects"][0]["positions"][0]
        self.assertEqual(r["decision"], "exact_office")
        self.assertEqual(r["candidate_canonical_tenures"], [])
        self.assertEqual(report["summary"]["mapped_office_without_canonical_tenure"], 1)
        # v1 Stalin has a composite legacy-g06 office, not cm-ussr.
        # No automatic creation, period split or rewriting is permitted.

    def test_old_calendar_and_year_precision_must_not_be_treated_as_day_match(self):
        snap = snapshot(record(
            "person-d2dfcacb3d245849", "canonical", "Q8479",
            [statement("Q2618625", date("+1721-10-22T00:00:00Z", "julian"))],
        ))
        report = offices.office_review(wd.ROOT, snap)
        r = report["subjects"][0]["positions"][0]
        self.assertEqual(r["decision"], "exact_office")
        self.assertEqual(len(r["candidate_canonical_tenures"]), 1)
        self.assertEqual(r["candidate_canonical_tenures"][0]["start_comparison"],
                         "calendar_review")

    def test_foreign_office_does_not_create_canonical_tenure(self):
        snap = snapshot(record(
            "world:pr-frederick2", "world_unlinked", "Q33550",
            [statement("Q3240735", date("+1740-01-01T00:00:00Z"))],
        ))
        report = offices.office_review(wd.ROOT, snap)
        r = report["subjects"][0]["positions"][0]
        self.assertEqual(r["decision"], "external_only")
        self.assertEqual(r["mapping"]["context_ids"], ["world:pr"])
        self.assertEqual(r["candidate_canonical_tenures"], [])

    def test_deprecated_and_unmapped_stay_visible_without_matching(self):
        snap = snapshot(record(
            "person-8ace0ae735b35ada", "canonical", "Q30487",
            [statement("Q1255261", rank="deprecated"),
             statement("Q99999999")],
        ))
        report = offices.office_review(wd.ROOT, snap)
        entries = report["subjects"][0]["positions"]
        self.assertEqual(entries[0]["decision"], "deprecated_statement_not_used")
        self.assertEqual(entries[1]["decision"], "unmapped_wikidata_office")
        self.assertFalse(any(x["candidate_canonical_tenures"] for x in entries))
        self.assertEqual(report["summary"]["deprecated"], 1)
        self.assertEqual(report["summary"]["unmapped"], 1)

    def test_same_label_never_resolves_two_subjects(self):
        a = record("world:pr-frederick2", "world_unlinked", "Q33550", [])
        b = record("world:pr-frederick2", "world_unlinked", "Q33550", [])
        with self.assertRaisesRegex(ValueError, "Duplicate Wikidata report subject"):
            offices.office_review(wd.ROOT, snapshot(a, b))

    def test_rejects_tampered_attestation(self):
        sample = snapshot()
        sample["historical_truth_verified"] = True
        with self.assertRaisesRegex(ValueError, "read-only"):
            offices.office_review(wd.ROOT, sample)

    def test_validation_blocks_office_to_nonexistent_state(self):
        # Registry loader must not accept arbitrary textual country aliases.
        src = wd.read_json(wd.ROOT / offices.OFFICE_REGISTRY)
        assert src["mappings"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for rel in (
                "data/atlas/offices.jsonl", "data/atlas/states.jsonl",
                "data/atlas/world-pilots/1762.json",
                "data/atlas/world-pilots/dynasty-1762-1780.json",
                "data/atlas/world-pilots/extension-1781-1800.json",
            ):
                dest = root / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes((wd.ROOT / rel).read_bytes())
            bad = copy.deepcopy(src)
            bad["mappings"][0]["context_ids"] = ["modern-russia"]
            target = root / offices.OFFICE_REGISTRY
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps(bad), encoding="utf8")
            with self.assertRaisesRegex(ValueError, "Invalid"):
                offices.reviewed_offices(root)


if __name__ == "__main__":
    unittest.main()
