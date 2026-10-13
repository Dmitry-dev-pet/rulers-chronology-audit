"""P9: office-type QIDs must not promote disputed person dates or rule."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from scripts import wikidata_office_review as o
from scripts import wikidata_sync as wd

ROOT = wd.ROOT
CASES_FILE = ROOT / "research/wikidata/p9-office-claims-2026-10-13.json"
QS = {"Q477406", "Q12370487", "Q12370489"}


def sample_report(cases):
    roster = {v["subject_id"]: v for v in wd.roster(ROOT)}
    records=[]
    for entry in cases:
        local=roster[entry["canonical_person_id"]]
        assert local["kind"]=="canonical"
        assert local["wikidata_id"]==entry["wikidata_person_qid"]
        qualifiers={}
        for prop, key in (("P580","p39_start"),("P582","p39_end")):
            if entry[key] is not None:
                qualifiers[prop]=[{"snaktype":"value","time":{
                    "time":entry[key],"calendar":entry["calendar"],
                    "precision":entry["precision"]}}]
        claim={"statement_id":entry["statement_id"],"rank":entry["rank"],
               "value":{"snaktype":"value","qid":entry["p39_office_qid"]},
               "qualifiers":qualifiers,"references":[]}
        records.append({**local, "wikidata":{"qid":local["wikidata_id"],
                        "statements":{"position_held":[claim]}}})
    return {"schema_version":"wikidata-reconciliation-v1",
            "historical_truth_verified":False,"mutated_canonical_data":False,
            "records":records}


class P9HistoricalOffices(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger=json.loads(CASES_FILE.read_text(encoding="utf-8"))
        cls.cases=cls.ledger["cases"]

    def test_three_qids_are_only_office_type_mappings(self):
        rows=o.reviewed_offices(ROOT)
        self.assertEqual({qid:rows[qid]["relation"] for qid in QS},{
            "Q477406":"office_family_only",
            "Q12370487":"office_family_only",
            "Q12370489":"exact_office"})
        self.assertEqual({qid:rows[qid]["office_id"] for qid in QS},{
            "Q477406":"regent",
            "Q12370487":"moscow-grand-prince",
            "Q12370489":"tsar"})
        self.assertEqual(rows["Q477406"]["context_ids"],
                         ["moscow","tsardom","empire"])
        self.assertEqual(rows["Q12370487"]["context_ids"],["moscow"])
        self.assertEqual(rows["Q12370489"]["context_ids"],["tsardom"])
        self.assertNotIn("emperor", [rows[x]["office_id"] for x in QS])
        self.assertEqual(len(self.cases),8)
        self.assertEqual({x["p39_office_qid"] for x in self.cases},QS)
        self.assertEqual(len({x["statement_id"] for x in self.cases}),8)
        self.assertFalse(self.ledger["p39_historical_truth_verified"])
        self.assertFalse(self.ledger["canonical_data_mutated"])
        self.assertTrue(all(not x["independent_primary_act_verified"]
                            and not x["historical_dates_verified"]
                            and not x["power_inferred"]
                            and x["independent_source_url"].startswith("https://")
                            for x in self.cases))
        counts={qid:sum(x["p39_office_qid"]==qid for x in self.cases)
                for qid in QS}
        self.assertEqual(counts,{"Q477406":3,"Q12370487":3,"Q12370489":2})

    def test_snapshot_of_eight_claims_never_creates_a_new_tenure(self):
        report=o.office_review(ROOT,sample_report(self.cases))
        actual={}
        for subject in report["subjects"]:
            p=subject["positions"][0]
            actual[p["wikidata_statement_id"]]=p
        self.assertEqual(len(actual),8)
        mappings=o.reviewed_offices(ROOT)
        for entry in self.cases:
            p=actual[entry["statement_id"]]
            self.assertEqual(p["decision"],mappings[entry["p39_office_qid"]]["relation"])
            self.assertEqual(
                sorted(c["canonical_tenure_id"]
                       for c in p["candidate_canonical_tenures"]),
                sorted(entry["expected_existing_tenure_ids"]))
            self.assertEqual(p["qualifiers"].get("P580",[])[0]["time"]["time"]
                if entry["p39_start"] else None, entry["p39_start"])
            if entry["expected_existing_tenure_ids"]:
                expected=("no_wikidata_boundary" if entry["p39_start"] is None
                          else "calendar_review")
                self.assertTrue(all(c["start_comparison"]==expected
                         for c in p["candidate_canonical_tenures"]))
        self.assertFalse(report["asserted_real_power"])
        self.assertFalse(report["mutated_canonical_data"])

    def test_anomalous_aleksei_claim_cannot_join_moscow_tenure(self):
        x=next(c for c in self.cases if c["person_name"]=="Алексей Михайлович")
        p=o.office_review(ROOT,sample_report([x]))["subjects"][0]["positions"][0]
        self.assertEqual(p["decision"],"office_family_only")
        self.assertEqual(p["candidate_canonical_tenures"],[])
        self.assertEqual(x["interpretation_caveat"],"tsar_context_not_medieval_moscow_grand_prince")

    def test_shemyaka_1445_source_is_preserved_as_disagreement_not_reign(self):
        x=next(c for c in self.cases if "Шемяка" in c["person_name"])
        self.assertEqual((x["p39_start"][:5],x["p39_end"][:5]),("+1445","+1445"))
        self.assertEqual(x["expected_existing_tenure_ids"],["tenure-m07"])
        self.assertEqual(x["interpretation_caveat"],
                         "source_year_conflict_1445_vs_1446_1447")
        # This is NOT proof of a canonical 1445 accession.
        p=o.office_review(ROOT,sample_report([x]))["subjects"][0]["positions"][0]
        self.assertEqual(p["decision"],"office_family_only")
        self.assertEqual(p["candidate_canonical_tenures"][0]
                         ["start_comparison"],"calendar_review")

    def test_boris_election_date_source_calendar_conflict_is_not_auto_corrected(self):
        x=next(c for c in self.cases if c["wikidata_person_qid"]=="Q170172")
        self.assertEqual(x["p39_start"],"+1598-02-17T00:00:00Z")
        self.assertEqual(x["calendar"],"gregorian")
        self.assertEqual(x["independent_source_old_style_election_date"],"1598-02-17")
        self.assertEqual(x["independent_source_new_style_election_date"],"1598-02-27")
        self.assertEqual(x["p39_end"],"+1605-04-13T00:00:00Z")
        self.assertEqual(x["independent_source_old_style_death_date"],"1605-04-13")
        self.assertEqual(x["independent_source_new_style_death_date"],"1605-04-23")
        self.assertEqual(x["interpretation_caveat"],"calendar_disagreement_source_review")
        self.assertEqual(x["event_kind"],
                         "election_distinct_from_coronation_and_effective_rule")
        self.assertFalse(x["historical_dates_verified"])
        self.assertFalse(x["independent_primary_act_verified"])
        self.assertEqual(x["p39_reference_count"],0)
        p=o.office_review(ROOT,sample_report([x]))["subjects"][0]["positions"][0]
        self.assertEqual(p["decision"],"exact_office")
        self.assertEqual([c["canonical_tenure_id"]
                          for c in p["candidate_canonical_tenures"]],["tenure-m14"])
        self.assertEqual(p["candidate_canonical_tenures"][0]
                         ["start_comparison"],"calendar_review")

    def test_peter_two_tsar_terms_remain_distinct_from_emperor(self):
        x=next(c for c in self.cases if "Пётр I" in c["person_name"])
        p=o.office_review(ROOT,sample_report([x]))["subjects"][0]["positions"][0]
        ids={c["canonical_tenure_id"] for c in p["candidate_canonical_tenures"]}
        self.assertEqual(ids,{"tenure-r05-joint","tenure-r05-sole"})
        self.assertNotIn("tenure-r05-emperor",ids)
        self.assertEqual(x["p39_end"],"+1721-11-02T00:00:00Z")

    def test_source_ledger_immutably_rejects_unknown_p39_case(self):
        x=copy.deepcopy(self.cases[0])
        x["wikidata_person_qid"]="Q99999999999"
        with self.assertRaises(AssertionError):
            sample_report([x])


if __name__=="__main__":
    unittest.main()
