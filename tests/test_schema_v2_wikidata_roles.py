"""Contract tests for eight source-qualified, dated Wikidata v2 crown offices."""
from __future__ import annotations

import copy
import json
import sqlite3
import unittest
from pathlib import Path

from scripts import atlas_v2_wikidata_roles as p4
from scripts import atlas_v2_crosswalk as crosswalk

ROOT = Path(__file__).resolve().parents[1]


class CrownRolePreview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn, cls.info = p4.preview(ROOT)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def scalar(self, q, params=()):
        return self.conn.execute(q, params).fetchone()[0]

    def test_exactly_eight_new_roles_and_four_independent_world_people(self):
        p = self.info["wikidata_p4"]
        self.assertEqual((p["source_role_count"],p["typed_crown_contexts"],
                          p["distinct_people"],p["reference_links"]), (8,2,4,16))
        self.assertEqual(self.scalar("SELECT count(*) FROM v2_wikidata_crown_claims"),8)
        self.assertEqual(self.scalar("SELECT count(*) FROM v2_roles"),51)
        self.assertEqual(self.scalar("SELECT count(*) FROM v2_world_imports"),43)
        self.assertEqual(self.scalar("SELECT count(*) FROM v2_wikidata_crown_contexts"),2)
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM v2_timeline_year_candidates "
            "WHERE origin_layer='wikidata-curated'"),8)
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM v2_timeline_year_candidates "
            "WHERE origin_layer='world-pilot'"),39)

    def test_v1_canonical_and_provenance_remain_unchanged(self):
        self.assertEqual(self.scalar("SELECT count(*) FROM people"),83)
        self.assertEqual(self.scalar("SELECT count(*) FROM provenance"),150)
        self.assertEqual(self.scalar("SELECT count(*) FROM entries WHERE kind='tenures'"),97)
        self.assertEqual(self.scalar("PRAGMA user_version"),1)
        self.assertEqual(self.scalar("PRAGMA integrity_check"),"ok")
        self.assertEqual(self.conn.execute("PRAGMA foreign_key_check").fetchall(),[])
        self.assertEqual(self.scalar("SELECT count(*) FROM v2_assertions_without_sources"),0)

    def test_every_import_has_two_explicit_sources(self):
        source_counts=self.conn.execute(
            """SELECT r.native_id, count(a.source_id)
               FROM v2_roles r
               JOIN v2_assertion_sources a ON a.assertion_id=r.assertion_id
               WHERE r.origin='wikidata-curated-crowns'
               GROUP BY r.native_id ORDER BY r.native_id""").fetchall()
        self.assertEqual(len(source_counts),8)
        self.assertTrue(all(n==2 for _,n in source_counts))
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM v2_wikidata_crown_claims "
            "WHERE independent_primary_act_checked=0 AND territorial_power_inferred=0"),8)
        self.assertTrue(all(self.scalar("SELECT count(*) FROM v2_sources WHERE id=?",
            ("p4:wikidata:"+qid,))==1
            for qid in ["Q131706","Q76555","Q151321","Q130834"]))

    def test_separate_bohemian_and_hungarian_crowns_not_habsburg_state(self):
        scopes=self.conn.execute(
            """SELECT context_id,related_parent_context_id,relation,same_as_parent,
                      geographic_boundaries_verified,power_asserted
               FROM v2_wikidata_crown_contexts ORDER BY context_id""").fetchall()
        self.assertEqual({x[0] for x in scopes},
                         {"ctx-hab-crown-bohemia","ctx-hab-crown-hungary"})
        self.assertTrue(all(row[1]=="ctx-world-hab" and row[2]=="related_not_equivalent"
                            and tuple(row[3:])==(0,0,0) for row in scopes))
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM v2_contexts WHERE id='ctx-world-hab'"),1)

    def test_year_1790_is_two_succession_candidates_not_four_joint_rulers(self):
        candidates=p4.year_candidates(self.conn,1790)
        self.assertEqual(len(candidates),4)
        self.assertEqual({c["world_person_id"] for c in candidates},
                         {"hre-joseph","hab-leopold"})
        self.assertEqual({c["context_id"] for c in candidates},
                         {"ctx-hab-crown-bohemia","ctx-hab-crown-hungary"})
        self.assertTrue(all(c["role_kind"]=="sovereign" for c in candidates))
        self.assertTrue(all("same" not in c["interpretation_caveat"].lower() or
                            "day" in c["interpretation_caveat"].lower()
                            for c in candidates))
        self.assertEqual(len(p4.year_candidates(
            self.conn,1790,"ctx-hab-crown-bohemia")),2)
        self.assertEqual(len(p4.year_candidates(self.conn,1791)),2)

    def test_1762_is_left_censored_maria_theresa(self):
        candidates=p4.year_candidates(self.conn,1762)
        self.assertEqual(len(candidates),2)
        self.assertEqual({x["world_person_id"] for x in candidates},{"hab-maria"})
        self.assertEqual(self.info["wikidata_p4"]["left_censored"],2)
        records=self.conn.execute(
            """SELECT p.start_date_json
               FROM v2_roles r JOIN v2_periods p ON p.id=r.period_id
               JOIN v2_wikidata_crown_claims e ON e.role_id=r.id
               WHERE e.external_person_id='hab-maria'""").fetchall()
        self.assertTrue(all(x[0] is None for x in records))
        self.assertEqual(p4.year_candidates(self.conn,1761),[])

    def test_1799_is_right_censored_francis_without_1800_abdication(self):
        candidates=p4.year_candidates(self.conn,1799)
        self.assertEqual(len(candidates),2)
        self.assertEqual({x["world_person_id"] for x in candidates},{"hab-francis2"})
        self.assertEqual(self.info["wikidata_p4"]["right_censored"],2)
        records=self.conn.execute(
            """SELECT p.end_date_json,c.original_end_year
               FROM v2_roles r JOIN v2_periods p ON p.id=r.period_id
               JOIN v2_wikidata_crown_claims c ON c.role_id=r.id
               WHERE c.external_person_id='hab-francis2'""").fetchall()
        self.assertEqual(records,[(None,1835),(None,1835)])
        self.assertEqual(p4.year_candidates(self.conn,1801),[])

    def test_pilot_1788_does_not_include_bohemian_leopold(self):
        self.assertEqual({x["world_person_id"] for x in
                          p4.year_candidates(self.conn,1788)},{"hre-joseph"})
        self.assertEqual(len(p4.year_candidates(self.conn,1800)),2)
        self.assertFalse(self.info["wikidata_p4"]["actual_power_inferred"])
        self.assertFalse(self.info["wikidata_p4"]["historical_truth_verified_by_ci"])

    def test_curated_source_record_and_p39_dates_are_preserved(self):
        rows=self.conn.execute(
            """SELECT original_start_json,original_end_json,source_record_json,
                      statement_id
               FROM v2_wikidata_crown_claims""").fetchall()
        self.assertEqual(len(rows),8)
        for begin,end,raw,statement in rows:
            self.assertIn("time",json.loads(begin))
            self.assertIn("time",json.loads(end))
            item=json.loads(raw)
            self.assertEqual(item["wikidata"]["statement_id"],statement)
            self.assertIn("independent_reference_url",item)

    def test_regencies_and_collective_bodies_remain_distinct_after_crown_import(self):
        kinds=dict(self.conn.execute(
            "SELECT native_id,role_kind FROM v2_roles WHERE native_id IN "
            "('ex-pt-joao-regent','ex-sw-charles','ex-fr-convention',"
            "'ex-fr-directory')").fetchall())
        self.assertEqual(kinds["ex-pt-joao-regent"],"regent")
        self.assertEqual(kinds["ex-sw-charles"],"regent")
        self.assertEqual(kinds["ex-fr-convention"],"institutional")
        self.assertEqual(kinds["ex-fr-directory"],"institutional")
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM v2_assertions WHERE id LIKE 'v2-assert-wd-%' "
            "AND category='legal'"),8)
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM v2_context_relations"),0)
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM v2_person_relations"),0)

    def test_structural_report_disclaims_practical_power(self):
        result=p4.report(self.conn,self.info,year=1790)
        self.assertEqual(result["sqlite_integrity"],"ok")
        self.assertEqual(result["sqlite_user_version"],1)
        self.assertFalse(result["claim_of_actual_power"])
        self.assertFalse(result["historical_truth_verified_by_ci"])
        self.assertFalse(result["geographic_boundaries_verified"])
        self.assertEqual(len(result["roles"]),8)
        self.assertEqual(len(result["year_candidates"]),4)


class SeedRejection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot=crosswalk.load_snapshot(ROOT)
        cls.snapshot["root"]=ROOT
        cls.seed=p4.read(ROOT,p4.CONFIG)

    def _mutate_and_validate(self, mutation):
        import tempfile
        import shutil
        with tempfile.TemporaryDirectory() as d:
            dst=Path(d)
            import os
            (dst/"design/wikidata").mkdir(parents=True)
            changed=copy.deepcopy(self.seed)
            mutation(changed)
            (dst/p4.CONFIG).write_text(json.dumps(changed),encoding="utf-8")
            # All other source files are from the real repo. Override only
            # the seed reader; do not risk changing user files.
            read=p4.read
            try:
                p4.read=lambda root,path: json.loads((dst/p4.CONFIG).read_text()) if path==p4.CONFIG else read(ROOT,path)
                return p4.validate_seed(ROOT,self.snapshot)
            finally:
                p4.read=read

    def test_wrong_person_qid_rejected(self):
        with self.assertRaisesRegex(ValueError,"QID is not"):
            self._mutate_and_validate(
                lambda data:data["roles"][0].update(person_qid="Q12967"))

    def test_jurisdiction_cannot_silently_change(self):
        with self.assertRaisesRegex(ValueError,"legal crown scope"):
            self._mutate_and_validate(
                lambda data:data["roles"][0].update(context_id="ctx-world-hab"))

    def test_duplicate_claim_rejected(self):
        def modify(data):
            data["roles"][1]["wikidata"]["statement_id"]=data["roles"][0]["wikidata"]["statement_id"]
        with self.assertRaises(ValueError):
            self._mutate_and_validate(modify)

    def test_altered_time_year_rejected(self):
        def modify(data):
            data["roles"][0]["wikidata"]["start"]["time"]="+1741-00-00T00:00:00Z"
        with self.assertRaisesRegex(ValueError,"does not match"):
            self._mutate_and_validate(modify)

    def test_unsupported_day_precision_rejected(self):
        def modify(data):
            data["roles"][0]["wikidata"]["start"]["precision"]=11
        with self.assertRaisesRegex(ValueError,"invented day|time has"):
            self._mutate_and_validate(modify)

    def test_source_disagreement_flagged_not_auto_corrected(self):
        item=self.seed["roles"][0]
        subject={
          "subject_id":"world:"+item["world_person_id"],
          "wikidata_id":item["person_qid"],
          "wikidata":{"statements":{"position_held":[{
              "statement_id":item["wikidata"]["statement_id"],
              "rank":"normal","value":{"qid":item["position_qid"]},
              "qualifiers":{
                "P580":[{"time":dict(item["wikidata"]["start"])}],
                "P582":[{"time":dict(item["wikidata"]["end"])}],
              },
          }]}}
        }
        live={"schema_version":"wikidata-reconciliation-v1",
              "historical_truth_verified":False,
              "mutated_canonical_data":False,
              "records":[subject]}
        self.assertEqual(p4.live_review(item,live),"matches_reviewed_snapshot")
        live["records"][0]["wikidata"]["statements"]["position_held"][0]["qualifiers"]["P580"][0]["time"]["time"]="+1741-00-00T00:00:00Z"
        self.assertEqual(p4.live_review(item,live),"source_changed_review_required")

    def test_ancient_date_is_explicitly_unsupported(self):
        with self.assertRaises(ValueError):
            p4.wd_date({"time":"-0044-00-00T00:00:00Z",
                        "precision":9,"calendar":"gregorian"})


if __name__=="__main__":
    unittest.main()
