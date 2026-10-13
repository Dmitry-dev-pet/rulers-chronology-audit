"""P10 — legal office names before/after 1946, RSFSR vs USSR, deputies."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from collections import Counter, defaultdict
from pathlib import Path

from scripts import wikidata_office_review as p2
from scripts import wikidata_jurisdiction_review as p3
from scripts import wikidata_sync as wd

ROOT = wd.ROOT
LEDGER = ROOT / "research/wikidata/p10-soviet-government-claims-2026-10-13.json"
TARGETS = {"Q134407102": 3, "Q134373912": 4, "Q5452917": 3, "Q56919889": 2}


def synthetic_snapshot(cases):
    """Construct report from a pinned source sample; NOT independently verified appointments."""
    people = {x["subject_id"]: x for x in wd.roster(ROOT)}
    grouped = defaultdict(list)
    for idx, case in enumerate(cases):
        sid = case["canonical_person_id"]
        assert sid in people and people[sid]["wikidata_id"] == case["person_qid"]
        def bound(stamp):
            return {"snaktype": "value", "time": stamp.copy()} if stamp else None
        claims = {
            "statement_id": case["statement_id"], "rank": case["rank"],
            "value": {"snaktype": "value", "qid": case["office_qid"]},
            "qualifiers": {
                "P580": [bound(case["start_time"])],
                "P582": [bound(case["end_time"])],
            },
            # Synthetic fixture preserves the COUNT; actual reference hashes
            # remain in the frozen P9 live audit artifact.
            "references": [{"hash": f"fixture-{idx}-{n}"}
                           for n in range(case["wikidata_reference_count"])],
        }
        grouped[sid].append(claims)
    rows = []
    for sid, claims in grouped.items():
        p = people[sid]
        rows.append({**p, "wikidata": {
            "qid": p["wikidata_id"], "statements": {"position_held": claims}}})
    return {"schema_version": "wikidata-reconciliation-v1",
            "historical_truth_verified": False, "mutated_canonical_data": False,
            "records": rows}


class GovernmentOfficeTypesP10(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        cls.cases = cls.ledger["cases"]

    def test_frozen_twelve_claims_keep_original_identity_time_and_rank(self):
        self.assertEqual(self.ledger["schema_version"],
                         "wikidata-p10-government-claim-sample-v1")
        self.assertFalse(self.ledger["historical_truth_verified_by_ci"])
        self.assertFalse(self.ledger["canonical_database_mutated"])
        self.assertEqual(len(self.cases), 12)
        self.assertEqual(dict(Counter(x["office_qid"] for x in self.cases)),
                         TARGETS)
        self.assertEqual(len({x["statement_id"] for x in self.cases}), 12)
        self.assertEqual(len({x["canonical_person_id"] for x in self.cases}), 5)
        self.assertEqual(sum(x["wikidata_reference_count"] for x in self.cases), 5)
        self.assertTrue(all(x["rank"] == "normal" and
                            x["start_time"]["precision"] == 11 and
                            x["end_time"]["precision"] == 11 and
                            not x["historical_dates_verified"] and
                            not x["individual_legal_appointment_verified"] and
                            not x["effective_personal_power_inferred"]
                            for x in self.cases))
        mixed = [c for c in self.cases
                 if c["start_time"]["calendar"] != c["end_time"]["calendar"]]
        self.assertEqual(len(mixed), 1)
        self.assertEqual(mixed[0]["person_qid"], "Q1394")  # Lenin
        self.assertEqual(mixed[0]["start_time"]["calendar"], "julian")
        self.assertEqual(mixed[0]["end_time"]["calendar"], "gregorian")

    def test_four_qids_remain_disjoint_from_government_chair_types(self):
        p2map = p2.reviewed_offices(ROOT)
        contexts, p3map, _ = p3.registry(ROOT)
        self.assertEqual(p2map["Q56919889"]["office_id"], "snk-rsfsr")
        self.assertEqual(p2map["Q56919889"]["context_ids"], ["rsfsr"])
        self.assertEqual(p2map["Q56919889"]["relation"], "exact_office")
        self.assertEqual(p2map["Q4376682"]["office_id"], "snk-ussr")
        self.assertEqual(p2map["Q4376674"]["office_id"], "cm-ussr")
        self.assertEqual(len({p2map[x]["office_id"] for x
                              in ("Q56919889", "Q4376682", "Q4376674")}), 3)
        self.assertNotIn("Q56919889", p3map)
        for qid in ("Q134407102", "Q134373912", "Q5452917"):
            self.assertNotIn(qid, p2map)
        self.assertEqual(len(contexts), 12)
        self.assertEqual(len(p3map), 14)
        self.assertEqual(p3map["Q134407102"]["office_rank"], "deputy")
        self.assertEqual(p3map["Q134373912"]["office_rank"], "deputy")
        self.assertEqual(p3map["Q5452917"]["office_rank"], "first_deputy")
        self.assertEqual(p3map["Q5452917"]["position_kind"],
                         "government_first_deputy")
        self.assertEqual(p3map["Q134407102"]["context_id"],
                         "ctx-ussr-snk-1923-1946")
        self.assertEqual(p3map["Q134373912"]["context_id"],
                         p3map["Q5452917"]["context_id"])
        self.assertEqual(p3map["Q134373912"]["context_id"],
                         "ctx-ussr-sovmin-1946-1991")
        self.assertNotEqual(p3map["Q134407102"]["context_id"],
                            p3map["Q134373912"]["context_id"])
        self.assertTrue(all(not c["same_as_canonical_state"] and
                            not c["geographic_boundaries_verified"] and
                            c["government_tier"] == "union"
                            for c in contexts.values()
                            if c["kind"] == "executive_institution"))
        self.assertEqual(contexts["ctx-ussr-snk-1923-1946"]
                         ["title_year_window"], {"start":1923,"end":1946})
        self.assertEqual(contexts["ctx-ussr-sovmin-1946-1991"]
                         ["title_year_window"], {"start":1946,"end":1991})
        self.assertTrue(all(c["legal_title_transition_date"] == "1946-03-15"
                            for c in contexts.values()
                            if c["kind"] == "executive_institution"))

    def test_twelve_source_statements_classify_without_new_historic_claims(self):
        sample=synthetic_snapshot(self.cases)
        old=p2.office_review(ROOT,sample)
        typed=p3.review(ROOT,sample)
        self.assertEqual(old["summary"]["exact_office"], 2)
        self.assertEqual(old["summary"]["unmapped"], 10)
        self.assertEqual(typed["summary"]["typed_claims"], 10)
        self.assertEqual(typed["summary"]["role_government_deputy"], 7)
        self.assertEqual(typed["summary"]["role_government_first_deputy"], 3)
        self.assertEqual(typed["summary"]["multi_context_subjects_to_review"], 2)
        by_id = {x["wikidata_statement_id"]:x
                 for subject in typed["subjects"] for x in subject["positions"]}
        self.assertEqual(len(by_id), 10)
        for entry in self.cases:
            if entry["office_qid"] == "Q56919889":
                self.assertNotIn(entry["statement_id"], by_id)
                continue
            x=by_id[entry["statement_id"]]
            self.assertFalse(x["actual_power_verified"])
            self.assertFalse(x["historical_borders_verified"])
            self.assertEqual(x["jurisdiction_context_kind"], "executive_institution")
            self.assertEqual(x["pilot_window_relation"], "after_world_pilot_window")
            self.assertTrue(x["government_title_era"].startswith(
                "pre_1946" if entry["office_qid"] == "Q134407102" else "post_1946"))
            self.assertEqual(x["office_rank"],
                "first_deputy" if entry["office_qid"] == "Q5452917" else "deputy")
            self.assertIn(x["executive_title_year_review"], {
                "1946_transition_requires_day_level_legal_review",
                "year_scoped_office_type_only_not_person_term_verified",
            })
        self.assertFalse(typed["actual_power_inferred"])
        self.assertFalse(typed["mutated_canonical_data"])
        self.assertFalse(old["asserted_real_power"])
        self.assertFalse(old["mutated_canonical_data"])

    def test_kosygin_two_scopes_without_fabricating_rsfsr_tenure(self):
        data=synthetic_snapshot(self.cases)
        r=p2.office_review(ROOT,data)
        by_id={x["wikidata_statement_id"]:x
               for person in r["subjects"] for x in person["positions"]}
        x=next(x for x in self.cases if
               x["person_qid"]=="Q202770" and x["office_qid"]=="Q56919889")
        self.assertEqual(by_id[x["statement_id"]]["decision"],"exact_office")
        self.assertEqual(by_id[x["statement_id"]]["candidate_canonical_tenures"],[])
        lenin=next(x for x in self.cases if
                   x["person_qid"]=="Q1394" and x["office_qid"]=="Q56919889")
        p=by_id[lenin["statement_id"]]
        self.assertEqual([c["canonical_tenure_id"]
                          for c in p["candidate_canonical_tenures"]],["tenure-g01"])
        self.assertEqual(p["candidate_canonical_tenures"][0]
                         ["start_comparison"],"calendar_review")
        self.assertEqual(p["candidate_canonical_tenures"][0]
                         ["end_comparison"],"same_recorded_date")
        # Stalin still has only the composite historic record, not two split posts.
        tenures=wd.read_jsonl(ROOT/"data/atlas/tenures.jsonl")
        stalin=[x for x in tenures if x["person_id"]=="person-e88112738c1054f5"
                and x["office_id"] in {"snk-ussr","cm-ussr","legacy-g06"}]
        self.assertEqual([x["office_id"] for x in stalin],["legacy-g06"])

    def test_wrong_era_rank_or_context_is_refused(self):
        original=wd.read_json(ROOT/p3.REGISTRY)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            needed=(
                "data/atlas/offices.jsonl","data/atlas/states.jsonl",
                "data/atlas/world-pilots/1762.json",
                "data/atlas/world-pilots/dynasty-1762-1780.json",
                "data/atlas/world-pilots/extension-1781-1800.json",
                p2.OFFICE_REGISTRY,
            )
            for rel in needed:
                dst=root/rel
                dst.parent.mkdir(parents=True,exist_ok=True)
                dst.write_bytes((ROOT/rel).read_bytes())
            target=root/p3.REGISTRY
            target.parent.mkdir(parents=True,exist_ok=True)
            for invalid in ("rank","wrong_era","window"):
                changed=copy.deepcopy(original)
                roles={x["wikidata_qid"]:x for x in changed["offices"]}
                contexts={x["id"]:x for x in changed["contexts"]}
                if invalid=="rank":
                    roles["Q5452917"]["office_rank"]="deputy"
                elif invalid=="wrong_era":
                    roles["Q134407102"]["context_id"]="ctx-ussr-sovmin-1946-1991"
                else:
                    contexts["ctx-ussr-snk-1923-1946"]["title_year_window"]["end"]=1947
                target.write_text(json.dumps(changed),encoding="utf-8")
                with self.subTest(invalid=invalid),self.assertRaises(ValueError):
                    p3.registry(root)

    def test_out_of_era_claim_is_flagged_not_imported(self):
        contexts,_,_=p3.registry(ROOT)
        pre=contexts["ctx-ussr-snk-1923-1946"]
        fake={"qualifiers":{
            "P580":[{"snaktype":"value","time":{
                "time":"+1975-01-01T00:00:00Z","calendar":"gregorian","precision":11}}],
            "P582":[{"snaktype":"value","time":{
                "time":"+1980-01-01T00:00:00Z","calendar":"gregorian","precision":11}}],
        }}
        self.assertEqual(p3.executive_title_year_review(fake,pre),
                         "outside_historical_government_title_era_review")
        self.assertEqual(p3.executive_title_year_review(
            {"qualifiers":{}},pre),"incomplete_external_years_not_an_absence")


if __name__ == "__main__":
    unittest.main()
