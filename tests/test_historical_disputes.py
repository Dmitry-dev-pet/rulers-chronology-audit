"""Historical contradictions are source questions, NEVER implicit canon rewrites."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from scripts import historical_disputes as h

ROOT = h.ROOT


class HistoricalDisputeContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sample = json.loads((ROOT / h.REGISTRY).read_text(encoding="utf-8"))

    def get(self, ident):
        return next(c for c in self.sample["cases"] if c["id"] == ident)

    def temporary_root(self, root: Path, doc=None):
        """Minimal faithful on-disk fixture; real crossrefs, not fake strings."""
        for rel in (
            str(h.SOURCE_LEDGER),
            "data/atlas/offices.jsonl",
            "data/atlas/states.jsonl",
            "data/atlas/tenures.jsonl",
        ):
            dest = root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / rel, dest)
        directory = root / "data/atlas/people"
        directory.mkdir(parents=True, exist_ok=True)
        wanted = {c["person_id"] for c in (doc or self.sample)["cases"]}
        for p in (ROOT / "data/atlas/people").glob("*.json"):
            parsed = json.loads(p.read_text(encoding="utf-8"))
            if parsed["id"] in wanted:
                shutil.copyfile(p, directory / p.name)
        file = root / h.REGISTRY
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(json.dumps(doc if doc is not None else self.sample,
                                   ensure_ascii=False), encoding="utf-8")

    def assert_rejects(self, change, message):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            doc = copy.deepcopy(self.sample)
            change(doc)
            self.temporary_root(root, doc)
            with self.assertRaisesRegex(ValueError, message):
                h.registry(root)

    def test_pilot_is_four_open_cases_from_three_people_with_eight_sources(self):
        doc = h.registry()
        s = h.summary(doc)
        self.assertEqual(s["case_count"], 4)
        self.assertEqual(s["by_status"], {"open": 4})
        self.assertEqual(s["distinct_people"], 3)
        self.assertEqual(s["source_observations"], 8)
        self.assertEqual(s["by_type"], {
            "date_calendar_mismatch_candidate": 2,
            "office_period_disagreement": 1,
            "office_scope_anomaly": 1,
        })
        self.assertFalse(s["historical_truth_verified_by_ci"])
        self.assertFalse(s["changes_to_canonical_data"])
        self.assertFalse(s["auto_resolution_allowed"])
        self.assertTrue(all(c["resolution"] is None and
                            c["reviewed_primary_acts"] is False for c in doc["cases"]))

    def test_exact_original_wikidata_statement_is_still_available(self):
        original = json.loads((ROOT / h.SOURCE_LEDGER).read_text(encoding="utf-8"))
        pinned = {x["statement_id"]: x for x in original["cases"]}
        for item in h.registry()["cases"]:
            source = next(o for o in item["observations"]
                          if o["source_kind"] == "wikidata_p39")
            record = pinned[item["external_statement_id"]]
            self.assertEqual(source["source_locator"], record["statement_id"])
            self.assertEqual(item["person_qid"], record["wikidata_person_qid"])
            self.assertEqual(source["source_references_count"],
                             record["p39_reference_count"])
            self.assertFalse(source["independent_primary_checked"])

    def test_disagreement_and_distinct_event_semantics_survive(self):
        sh = self.get("HC-0001")
        raw, study = sh["observations"]
        self.assertEqual((raw["value"]["start"]["value"],
                          raw["value"]["end"]["value"]),
                         ("+1445-07-07T00:00:00Z", "+1445-10-26T00:00:00Z"))
        self.assertEqual((study["value"]["start"]["value"],
                          study["value"]["end"]["value"]),
                         ("1446-02", "1447-02"))
        self.assertEqual(study["value"]["start"]["calendar"], "unspecified")
        self.assertEqual(sh["comparison_relation"], "possibly_different_legal_events")
        for cid, raw_kind, institutional_kind, old, new in (
            ("HC-0002", "office_start", "election_event",
             "1598-02-17", "1598-02-27"),
            ("HC-0003", "office_end", "death_event",
             "1605-04-13", "1605-04-23"),
        ):
            with self.subTest(cid=cid):
                case = self.get(cid)
                wd, ref = case["observations"]
                self.assertEqual(wd["claim_type"], raw_kind)
                self.assertEqual(wd["value"]["date"]["calendar"], "gregorian")
                self.assertEqual(ref["claim_type"], institutional_kind)
                self.assertEqual(ref["value"]["old_style"]["value"], old)
                self.assertEqual(ref["value"]["old_style"]["calendar"], "julian")
                self.assertEqual(ref["value"]["new_style"]["value"], new)
                self.assertEqual(ref["value"]["new_style"]["calendar"], "gregorian")
                self.assertEqual(case["comparison_relation"], "different_event_not_equated")
                self.assertFalse(case["actual_power_inferred"])

    def test_aleksei_scope_anomaly_is_not_an_extra_moscow_reign(self):
        case = self.get("HC-0004")
        wd, institute = case["observations"]
        self.assertEqual(case["canonical_tenure_ids"], ["tenure-r02"])
        self.assertEqual(case["context_id"], "tsardom")
        self.assertEqual(case["office_id"], "tsar")
        self.assertEqual(wd["value"]["office_qid"], "Q12370487")
        self.assertEqual(institute["value"]["office_id"], "tsar")
        self.assertEqual(case["comparison_relation"], "non_equivalent_legal_contexts")

    def test_markdown_report_is_not_canonical_or_public_build(self):
        paths = [ROOT / h.REGISTRY, ROOT / h.SOURCE_LEDGER,
                 ROOT / "data/atlas/tenures.jsonl"]
        before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
        rendered = h.render_markdown(h.registry())
        self.assertIn("HC-0001", rendered)
        self.assertIn("HC-0004", rendered)
        after = [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
        self.assertEqual(before, after)

    def test_rejects_wrong_person_or_foreign_canonical_tenure(self):
        self.assert_rejects(lambda d: d["cases"][0].update(
            person_id="person-70e920e83c13510c"), "stable IDs")
        self.assert_rejects(lambda d: d["cases"][0].update(
            canonical_tenure_ids=["tenure-m14"]), "another person's")

    def test_rejects_source_statement_and_calendar_drift(self):
        self.assert_rejects(lambda d: d["cases"][0].update(
            external_statement_id="Q1282778$WRONG"), "P39 statement")
        self.assert_rejects(lambda d: d["cases"][1]["observations"][0]
                            ["value"]["date"].update(calendar="julian"),
                            "calendar drifted")
        self.assert_rejects(lambda d: d["cases"][0]["observations"][0]
                            ["value"]["start"].update(value="+1446-07-07T00:00:00Z"),
                            "P39 value")
        self.assert_rejects(lambda d: d["cases"][2]["observations"][0].update(
            source_references_count=13), "original evidence changed")

    def test_rejects_invented_date_precision_and_event_identity(self):
        self.assert_rejects(lambda d: d["cases"][0]["observations"][1]
                            ["value"]["start"].update(precision="day"),
                            "precision does not match")
        self.assert_rejects(lambda d: d["cases"][1]["observations"][1].update(
            claim_type="office_start"),
            "Institutional reference is not")
        self.assert_rejects(lambda d: d["cases"][1].update(
            comparison_relation="same_event_confirmed"),
            "typed historical question")
        self.assert_rejects(lambda d: d["cases"][3].update(
            office_id="moscow-grand-prince"),
            "another person's")

    def test_rejects_autoresolution_and_claims_of_archival_attestation(self):
        self.assert_rejects(lambda d: d.update(
            historical_truth_verified_by_ci=True), "non-attesting")
        self.assert_rejects(lambda d: d["cases"][0].update(
            review_status="resolved"), "Manual historical resolution")
        self.assert_rejects(lambda d: d["cases"][1].update(
            resolution={"decision": "accept-wikidata"}), "cannot auto-resolve")
        self.assert_rejects(lambda d: d["cases"][0].update(
            reviewed_primary_acts=True), "stable IDs")
        self.assert_rejects(lambda d: d["cases"][0].update(
            actual_power_inferred=True), "stable IDs")

    def test_rejects_private_links_missing_sources_and_duplicate_cases(self):
        self.assert_rejects(lambda d: d["cases"][0]["observations"][1].update(
            source_url="https://drive.google.com/file/d/secret"),
            "missing source")
        self.assert_rejects(lambda d: d["cases"][0]["observations"].pop(),
                            "independently attributable")
        self.assert_rejects(lambda d: d["cases"].append(
            copy.deepcopy(d["cases"][0])), "stable IDs")
        self.assert_rejects(lambda d: d["cases"][0]["observations"][1].update(
            source_url="https://archive.example.net/source?token=SECRET"),
            "missing source")

    def test_manual_resolution_requires_named_reviewer_and_independent_evidence(self):
        doc = copy.deepcopy(self.sample)
        doc["cases"][0]["review_status"] = "resolved"
        doc["cases"][0]["resolution"] = {
            "reviewer": "Named historian/curator",
            "reason": "Reviewed two independent sources with separate events.",
            "evidence_urls": ["https://bigenc.ru/c/dmitrii-iur-evich-velikii-kniaz-moskovskii-624f7f",
                              "https://www.prlib.ru/history/619062"],
        }
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.temporary_root(root, doc)
            self.assertEqual(h.summary(h.registry(root))["by_status"]["resolved"], 1)
        # Schema allows a documented human decision, not an automatic decision.
        # Such a decision is not evidence that the historian actually reviewed it.


if __name__ == "__main__":
    unittest.main()
