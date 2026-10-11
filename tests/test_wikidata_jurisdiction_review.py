"""Wikidata P3: independently typed jurisdictions, offices and identity safety."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts import wikidata_jurisdiction_review as jurisdictions
from scripts import wikidata_office_review as offices
from scripts import wikidata_sync as wd


def date(year, precision=11):
    return {"time": f"+{year:04d}-01-01T00:00:00Z",
            "precision": precision, "calendar": "gregorian"}


def office(qid, start=None, end=None, rank="normal"):
    q = {}
    if start is not None:
        q["P580"] = [{"snaktype": "value", "time": date(start)}]
    if end is not None:
        q["P582"] = [{"snaktype": "value", "time": date(end)}]
    return {"statement_id": "test$" + qid, "rank": rank,
            "value": {"snaktype": "value", "qid": qid},
            "qualifiers": q, "references": [{"hash": "test-reference"}]}


def subject(sid, *claims):
    p = next(p for p in wd.roster(wd.ROOT) if p["subject_id"] == sid)
    return {**p, "wikidata": {
        "qid": p["wikidata_id"],
        "statements": {"position_held": list(claims)},
    }}


def report(*subjects):
    return {"schema_version": "wikidata-reconciliation-v1",
            "mutated_canonical_data": False,
            "historical_truth_verified": False,
            "records": list(subjects)}


class ReviewedIdentities(unittest.TestCase):
    def test_all_world_only_people_have_reviewed_noncanonical_qids(self):
        roster = wd.roster(wd.ROOT)
        self.assertEqual(sum(x["kind"] == "world_unlinked" for x in roster), 24)
        self.assertTrue(all(x["wikidata_id"] for x in roster
                            if x["kind"] == "world_unlinked"))
        self.assertEqual(len({x["wikidata_id"] for x in roster if x["wikidata_id"]}),
                         len([x for x in roster if x["wikidata_id"]]))
        self.assertEqual(next(x["wikidata_id"] for x in roster
                              if x["subject_id"] == "world:pt-maria1"), "Q773874")
        self.assertEqual(next(x["wikidata_id"] for x in roster
                              if x["subject_id"] == "world:hre-francis"), "Q151075")
        self.assertEqual(next(x["wikidata_id"] for x in roster
                              if x["subject_id"] == "world:sw-charles"), "Q52928")

    def test_conservative_rejected_regnal_homonyms_remain_excluded(self):
        r = wd.read_json(wd.ROOT / "design/wikidata/reviewed-world-links-v1.json")
        rejects = {(x["world_id"], x["wikidata_qid"])
                   for x in r["rejected_candidates"]}
        self.assertIn(("pr-frederick2", "Q130221"), rejects)
        self.assertIn(("hab-leopold", "Q12967"), rejects)
        self.assertEqual(len(r["links"]), 24)
        self.assertTrue(all((x["world_id"], x["wikidata_qid"]) not in rejects
                            for x in r["links"]))


class TypedJurisdictions(unittest.TestCase):
    def test_registry_has_unique_qids_and_explicit_nonidentical_contexts(self):
        contexts, roles, window = jurisdictions.registry(wd.ROOT)
        self.assertEqual(window, (1762, 1800))
        self.assertEqual(len(contexts), 9)
        self.assertEqual(len(roles), 9)
        self.assertEqual(roles["Q45341328"]["context_id"],
                         "ctx-hab-crown-bohemia")
        self.assertEqual(roles["Q6412254"]["context_id"],
                         "ctx-hab-crown-hungary")
        self.assertNotEqual(roles["Q45341328"]["context_id"],
                            roles["Q6412254"]["context_id"])
        self.assertEqual(contexts["ctx-cpsu-politburo"]["kind"],
                         "political_party_institution")
        self.assertFalse(any(row["same_as_canonical_state"] for row in
                             contexts.values()))
        self.assertFalse(any(row["geographic_boundaries_verified"] for row in
                             contexts.values()))

    def test_habsburg_crowns_dont_merge_or_prove_personal_union(self):
        data = report(subject("world:hre-joseph",
                       office("Q45341328", 1765, 1790),
                       office("Q6412254", 1765, 1790),
                       office("Q22722", 1765, 1790)))
        result = jurisdictions.review(wd.ROOT, data)
        self.assertEqual(result["summary"]["typed_claims"], 3)
        self.assertEqual(result["summary"]["multi_context_subjects_to_review"], 1)
        self.assertEqual(len(result["multi_context_candidates"][0]["context_ids"]), 3)
        self.assertFalse(result["actual_power_inferred"])
        self.assertFalse(result["historical_borders_verified"])
        self.assertFalse(result["mutated_canonical_data"])
        self.assertTrue(all(p["pilot_window_relation"] ==
                            "year_overlap_candidate_not_day_verified"
                            for p in result["subjects"][0]["positions"]))

    def test_andorra_is_not_a_french_department_or_single_sovereign(self):
        result = jurisdictions.review(wd.ROOT, report(subject(
            "world:fr-louis16", office("Q19808845", 1774, 1792),
            office("Q3439798", 1774, 1791))))
        scopes = {p["jurisdiction_context_id"]
                  for p in result["subjects"][0]["positions"]}
        self.assertEqual(scopes,
                         {"ctx-andorra-co-principality", "ctx-crown-france-navarre"})
        self.assertEqual(result["summary"]["multi_context_subjects_to_review"], 1)
        self.assertEqual(next(p for p in result["subjects"][0]["positions"]
                              if p["wikidata_office_qid"] == "Q19808845")
                         ["legal_role_classification"], "co_head_of_state")

    def test_politburo_membership_is_institutional_not_sovreign(self):
        result = jurisdictions.review(wd.ROOT, report(subject(
            "person-e88112738c1054f5",
            office("Q108495011", 1919, 1953))))
        p = result["subjects"][0]["positions"][0]
        self.assertEqual(p["legal_role_classification"], "institutional_membership")
        self.assertEqual(p["jurisdiction_context_kind"], "political_party_institution")
        self.assertFalse(p["actual_power_verified"])

    def test_1804_napoleonic_emperor_does_not_appear_in_1799_pilot(self):
        result = jurisdictions.review(wd.ROOT, report(subject(
            "world:fr-napoleon", office("Q5373953", 1804, 1814))))
        self.assertEqual(result["subjects"][0]["positions"][0]
                         ["pilot_window_relation"], "after_world_pilot_window")
        self.assertEqual(result["subjects"][0]["positions"][0]
                         ["jurisdiction_context_id"], "ctx-first-french-empire")

    def test_unknown_time_is_not_false_absence(self):
        result = jurisdictions.review(wd.ROOT, report(subject(
            "world:sw-gustav3", office("Q1268572", 1771, None))))
        self.assertEqual(result["subjects"][0]["positions"][0]
                         ["pilot_window_relation"], "incomplete_year_bounds_not_an_absence")

    def test_later_sweden_monarch_office_not_conflated_with_1790_duke(self):
        result = jurisdictions.review(wd.ROOT, report(subject(
            "world:sw-charles", office("Q1268572", 1809, 1818))))
        self.assertEqual(result["subjects"][0]["positions"][0]
                         ["pilot_window_relation"], "after_world_pilot_window")

    def test_deprecated_and_unmapped_claims_create_no_new_roles(self):
        data = report(subject("world:hre-joseph",
                      office("Q45341328", rank="deprecated"),
                      office("Q99999999", 1762, 1763)))
        result = jurisdictions.review(wd.ROOT, data)
        self.assertEqual(result["summary"]["deprecated_skipped"], 1)
        self.assertEqual(result["summary"]["not_in_jurisdiction_overlay"], 1)
        self.assertEqual(result["summary"].get("typed_claims", 0), 0)
        self.assertEqual(result["subjects"], [])

    def test_identity_spoof_in_external_report_is_rejected(self):
        raw = subject("world:pr-frederick2", office("Q22722"))
        raw["wikidata_id"] = "Q130221"
        raw["wikidata"]["qid"] = "Q130221"
        with self.assertRaisesRegex(ValueError, "unreviewed identity"):
            jurisdictions.review(wd.ROOT, report(raw))

    def test_year_boundary_negative_or_ancient_cannot_claim_overlap(self):
        claim = office("Q45341328")
        claim["qualifiers"]["P580"] = [{"snaktype": "value", "time": {
            "time": "-0044-01-01T00:00:00Z",
            "precision": 11}}]
        self.assertEqual(jurisdictions.window_review(claim, (1762, 1800)),
                         "incomplete_year_bounds_not_an_absence")

    def test_registry_rejects_world_context_identity_collapse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in [
                "data/atlas/offices.jsonl", "data/atlas/states.jsonl",
                "data/atlas/world-pilots/1762.json",
                "data/atlas/world-pilots/dynasty-1762-1780.json",
                "data/atlas/world-pilots/extension-1781-1800.json",
                "design/wikidata/office-crosswalk-v1.json",
                jurisdictions.REGISTRY,
            ]:
                dest = root / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes((wd.ROOT / rel).read_bytes())
            filename = root / jurisdictions.REGISTRY
            data = json.loads(filename.read_text(encoding="utf-8"))
            data["contexts"][0]["same_as_canonical_state"] = True
            filename.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Invalid/merging"):
                jurisdictions.registry(root)

    def test_russian_snk_office_is_not_post1946_ministers(self):
        crosswalk = offices.reviewed_offices(wd.ROOT)
        self.assertEqual(crosswalk["Q4376682"]["office_id"], "snk-ussr")
        self.assertEqual(crosswalk["Q4376674"]["office_id"], "cm-ussr")
        self.assertNotEqual(crosswalk["Q4376682"]["office_id"],
                            crosswalk["Q4376674"]["office_id"])


if __name__ == "__main__":
    unittest.main()
