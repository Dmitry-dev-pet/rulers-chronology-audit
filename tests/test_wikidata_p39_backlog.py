"""P8: historical position-QID backlog only, never imported tenures or power."""
import copy
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest

from scripts import wikidata_p39_backlog as q


class FrozenP7Research(unittest.TestCase):
    def test_full_frequency_ledger_is_exact_and_read_only(self):
        result=q.baseline()
        m=q.measures(result)
        self.assertEqual((m["distinct_qids"],m["unclassified_claims"],
                          m["qids_seen_once"],m["qids_seen_more_than_once"]),
                         (80,122,56,24))
        self.assertEqual(m["statements_with_explicit_references"],26)
        self.assertEqual(m["statements_with_both_date_qualifiers"],88)
        self.assertEqual(m["frequencies"],{1:56,2:10,3:11,4:2,5:1})
        self.assertFalse(m["historical_truth_verified"])
        self.assertFalse(m["effective_power_inferred"])
        self.assertEqual(result["Q27491113"]["claims"],5)
        self.assertEqual(result["Q27491113"]["with_references"],0)
        self.assertEqual(result["Q477406"]["with_references"],3)
        self.assertEqual(result["Q842386"]["claims"],3)

    def test_human_priority_is_not_a_verified_historical_mapping(self):
        proposed=q.queue(known=q.baseline())
        self.assertEqual(sum(x["status"]=="first" for x in proposed.values()),8)
        self.assertEqual(sum(x["status"]=="quarantine" for x in proposed.values()),1)
        self.assertEqual(sum(x["status"]=="later" for x in proposed.values()),7)
        self.assertEqual(proposed["Q842386"]["status"],"quarantine")
        self.assertEqual(proposed["Q27491113"]["status"],"later")
        self.assertTrue(all("office_id" not in item and "power_score" not in item
                            for item in proposed.values()))

    def test_invalid_frequency_ledger_is_rejected(self):
        old=q.BASELINE.read_text(encoding="utf8")
        samples=[
            old+old.splitlines()[1]+"\n",
            old.replace("Q27491113,5,5,0,0","Q27491113,5,6,0,0"),
            old.replace("Q27491113,5,5,0,0","WRONG,5,5,0,0"),
            old.replace("Q27491113,5,5,0,0","Q27491113,five,5,0,0"),
        ]
        for bad in samples:
            with self.subTest(bad=bad[-65:]),tempfile.TemporaryDirectory() as tmp:
                p=Path(tmp)/"bad.csv"
                p.write_text(bad,encoding="utf8")
                with self.assertRaises(ValueError):
                    q.baseline(p)

    def test_unknown_and_authoritative_priority_hints_are_rejected(self):
        plan=json.loads(q.QUEUE.read_text(encoding="utf8"))
        for key, value in (("qid","Q9999999999999999"),("office_id","tsar"),
                           ("status","historical_power_confirmed")):
            p=copy.deepcopy(plan)
            p["items"][0][key]=value
            with self.subTest(key=key),tempfile.TemporaryDirectory() as tmp:
                file=Path(tmp)/"plan.json"
                file.write_text(json.dumps(p),encoding="utf8")
                with self.assertRaises(ValueError):
                    q.queue(file,q.baseline())


class ReviewSourcesMustBeDisjoint(unittest.TestCase):
    @staticmethod
    def fixture():
        def claim(qid,statement,rank="normal"):
            return {"statement_id":statement,"rank":rank,
                    "value":{"qid":qid},"qualifiers":{"P580":[{"time":{"time":"+1900-01-01"}}],
                                                    "P582":[{"time":{"time":"+1903-01-01"}}]},
                    "references":[{"hash":"source"}]}
        claims=[claim("Q101","Q123$s1"),claim("Q102","Q123$s2"),
                claim("Q103","Q123$s3"),claim("Q104","Q123$s4","deprecated")]
        source={"schema_version":"wikidata-reconciliation-v1",
                "historical_truth_verified":False,"mutated_canonical_data":False,
                "records":[{"subject_id":"p1","wikidata_id":"Q123",
                            "wikidata":{"qid":"Q123","statements":{"position_held":claims}}}]}
        decisions=["unmapped_wikidata_office","exact_office","unmapped_wikidata_office",
                   "deprecated_statement_not_used"]
        mapped=[]
        for c,d in zip(claims,decisions):
            mapped.append({"wikidata_statement_id":c["statement_id"],
                "wikidata_office_qid":c["value"]["qid"],"rank":c["rank"],
                "qualifiers":copy.deepcopy(c["qualifiers"]),
                "references":copy.deepcopy(c["references"]),"decision":d})
        p2={"schema_version":"wikidata-office-review-v1","historical_truth_verified":False,
            "mutated_canonical_data":False,"asserted_real_power":False,
            "subjects":[{"subject_id":"p1","wikidata_qid":"Q123","positions":mapped}],
            "summary":{"position_statements":4,"unmapped":2}}
        p3={"schema_version":"wikidata-jurisdiction-review-v1",
            "historical_truth_verified":False,"mutated_canonical_data":False,
            "actual_power_inferred":False,"historical_borders_verified":False,
            "subjects":[{"subject_id":"p1","wikidata_qid":"Q123","positions":[{
                "wikidata_statement_id":"Q123$s3","wikidata_office_qid":"Q103",
                "qualifiers":copy.deepcopy(claims[2]["qualifiers"]),
                "references":copy.deepcopy(claims[2]["references"])}]}],
            "summary":{"typed_claims":1}}
        return source,p2,p3

    def test_same_run_crosswalk_leaves_only_exact_unknown_statements(self):
        found,people=q.from_live_reports(*self.fixture())
        self.assertEqual(people,1)
        self.assertEqual(found,{"Q101":{"claims":1,"people":1,
            "with_references":1,"with_both_boundaries":1}})
        self.assertEqual(q.compare(found,found),
            {"added_qids":[],"removed_qids":[],"changed_qids":[]})

    def test_rejects_altered_claim_time_or_duplicate_mapping(self):
        for mutation in ("date","overlap","authority"):
            args=copy.deepcopy(self.fixture())
            if mutation=="date":
                args[1]["subjects"][0]["positions"][0]["qualifiers"]["P580"][0]["time"]["time"]="+1901-01-01"
            elif mutation=="overlap":
                args[2]["subjects"][0]["positions"][0]["wikidata_statement_id"]="Q123$s2"
                args[2]["subjects"][0]["positions"][0]["wikidata_office_qid"]="Q102"
                args[2]["subjects"][0]["positions"][0]["qualifiers"]=copy.deepcopy(
                    args[0]["records"][0]["wikidata"]["statements"]["position_held"][1]["qualifiers"])
            else:
                args[0]["historical_truth_verified"]=True
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                q.from_live_reports(*args)


if __name__=="__main__":
    unittest.main()
