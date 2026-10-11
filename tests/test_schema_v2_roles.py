"""P2 contracts: no duplicate canonical rulers, honest scoped years and sources."""
from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
import unittest
from pathlib import Path

from scripts import atlas_v2_roles as roles

ROOT=Path(__file__).resolve().parents[1]


class InternationalRoleCandidate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot=roles.crosswalk.load_snapshot(ROOT)
        cls.snapshot["root"]=ROOT
        cls.conn,cls.report=roles.preview(cls.snapshot)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def q(self,statement,params=()):
        return self.conn.execute(statement,params).fetchall()

    def test_all_40_world_roles_and_3_institutions_are_preserved(self):
        p2=self.report["p2"]
        self.assertEqual((p2["person_roles"],p2["institutions"]),(40,3))
        self.assertEqual(self.q("SELECT count(*) FROM v2_roles"),[(43,)])
        self.assertEqual(self.q("SELECT count(*) FROM v2_institutions"),[(3,)])
        self.assertEqual(self.q("SELECT count(*) FROM v2_world_imports"),[(43,)])
        self.assertEqual(self.q("SELECT count(*) FROM v2_periods"),[(43,)])
        self.assertEqual(self.q("SELECT count(*) FROM v2_assertions"),[(43,)])
        self.assertGreaterEqual(self.q(
            "SELECT count(*) FROM v2_assertion_sources")[0][0],43)
        self.assertTrue(p2["source_links"]>=43)

    def test_sqlite_constraints_and_v1_untouched(self):
        self.assertEqual(self.q("PRAGMA integrity_check"),[("ok",)])
        self.assertEqual(self.q("PRAGMA foreign_key_check"),[])
        self.assertEqual(self.q("PRAGMA user_version"),[(1,)])
        self.assertEqual(self.q("SELECT count(*) FROM people"),[(83,)])
        self.assertEqual(self.q("SELECT count(*) FROM provenance"),[(150,)])
        self.assertEqual(self.q("SELECT count(*) FROM entries WHERE kind='tenures'"),[(97,)])
        self.assertEqual(self.q("SELECT count(*) FROM v2_assertions_without_sources"),[(0,)])
        self.assertFalse(self.report["p2"]["historical_truth_verified_by_ci"])

    def test_world_payload_is_byte_content_equivalent_after_json_decode(self):
        original={r["id"]:r for _,r in roles.world_records(self.snapshot)[0]}
        original.update({r["id"]:r for _,r in roles.world_records(self.snapshot)[1]})
        recorded=self.q("SELECT native_id,raw_json FROM v2_world_imports")
        self.assertEqual(len(recorded),len(original))
        for ident,payload in recorded:
            with self.subTest(ident=ident):
                self.assertEqual(json.loads(payload),original[ident])

    def test_linked_russian_people_do_not_duplicate_v1_tenures_in_union(self):
        linked=self.q("SELECT native_id,canonical_tenure_id,person_id FROM v2_roles "
                      "WHERE canonical_tenure_id IS NOT NULL")
        self.assertEqual({x[0] for x in linked},
                         {"dn-ru-elizabeth","dn-ru-peter3",
                          "dn-ru-catherine2","ex-ru-paul"})
        for native,tenure,person_id in linked:
            self.assertEqual(self.q("SELECT person_id FROM entries WHERE id=?",(tenure,)),
                             [(person_id,)])
            self.assertEqual(self.q(
                "SELECT count(*) FROM v2_timeline_year_candidates "
                "WHERE item_id=? AND origin_layer='world-pilot'",
                ("v2-role-"+native,)),[(0,)])
        russian=self.q(
            "SELECT item_id FROM v2_timeline_year_candidates "
            "WHERE context_id='ctx-empire' AND item_kind='canonical_tenure' "
            "AND start_year<=1762 AND end_year>=1762")
        self.assertTrue({"tenure-r10","tenure-r11","tenure-r12"}
                        .issubset({x[0] for x in russian}))
        # 40 world legal/supplementary roles - 4 canonical duplicates + 3 bodies.
        self.assertEqual(self.q(
            "SELECT count(*) FROM v2_timeline_year_candidates "
            "WHERE origin_layer='world-pilot'"),[(39,)])

    def test_international_roles_link_to_one_actor_and_right_context(self):
        linked=self.q(
            "SELECT native_id,person_id,external_person_id FROM v2_roles "
            "WHERE native_id='dn-ru-catherine2'")
        self.assertEqual(len(linked),1)
        self.assertIsNotNone(linked[0][1])
        self.assertIsNone(linked[0][2])
        george=self.q(
            "SELECT context_id,external_person_id,person_id FROM v2_roles "
            "WHERE native_id IN ('dn-gb-george','dn-han-george') ORDER BY context_id")
        self.assertEqual({x[0] for x in george},
                         {"ctx-world-gb","ctx-world-han"})
        self.assertTrue(all(x[1]=="gb-george3" and x[2] is None for x in george))

    def test_year_1788_not_equivalent_to_same_day_co_rule(self):
        spanish=self.q(
            "SELECT native_id,role_kind FROM v2_roles r "
            "JOIN v2_periods p ON p.id=r.period_id "
            "WHERE r.context_id='ctx-world-es' AND 1788 BETWEEN p.start_year AND p.end_year")
        self.assertEqual({x[0] for x in spanish},
                         {"ex-es-carlos3","ex-es-carlos4"})
        notes=self.q(
            "SELECT note FROM v2_periods WHERE id IN "
            "('v2-period-ex-es-carlos3','v2-period-ex-es-carlos4')")
        self.assertTrue(all("same-day" in x[0] for x in notes))
        french=self.q(
            "SELECT role_kind FROM v2_roles r "
            "JOIN v2_periods p ON p.id=r.period_id "
            "WHERE r.context_id='ctx-world-fr' "
            "AND 1788 BETWEEN p.start_year AND p.end_year")
        self.assertIn(("sovereign",),french)
        self.assertIn(("consort",),french)

    def test_1795_convention_directory_are_collective_not_people(self):
        rows=self.q(
            "SELECT r.native_id,r.person_id,r.external_person_id,r.institution_id,"
            "r.role_kind,p.start_year,p.end_year "
            "FROM v2_roles r JOIN v2_periods p ON p.id=r.period_id "
            "WHERE r.context_id='ctx-world-frrep' "
            "AND 1795 BETWEEN p.start_year AND p.end_year")
        self.assertEqual({x[0] for x in rows},
                         {"ex-fr-convention","ex-fr-directory"})
        self.assertTrue(all(r[1] is None and r[2] is None and r[3] is not None
                            and r[4]=="institutional" for r in rows))
        self.assertEqual(self.q(
            "SELECT count(*) FROM v2_roles WHERE institution_id IS NOT NULL"),[(3,)])

    def test_first_consul_not_emperor_or_future_napoleonic_monarch(self):
        self.assertEqual(self.q(
            "SELECT role_kind,context_id FROM v2_roles "
            "WHERE native_id='ex-fr-napoleon'"),
            [("first_consul","ctx-world-frrep")])
        self.assertEqual(self.q(
            "SELECT count(*) FROM v2_roles WHERE native_id='ex-fr-napoleon' "
            "AND role_kind IN ('emperor','sovereign')"),[(0,)])

    def test_dynastic_person_consort_heir_are_not_sovereign_counts(self):
        role=self.q("SELECT role_kind FROM v2_roles WHERE native_id='ex-pt-joao-infant'")
        self.assertEqual(role,[("dynastic_person",)])
        self.assertTrue(all(x[0] in {"consort","heir","dynastic_person"} for x in
                            self.q("SELECT role_kind FROM v2_roles r "
                                   "JOIN v2_assertions a ON a.id=r.assertion_id "
                                   "WHERE a.category='dynastic'")))
        self.assertEqual(self.q(
            "SELECT count(*) FROM v2_roles WHERE role_kind='sovereign' "
            "AND native_id IN ('dn-gb-charlotte','ex-pt-joao-infant','fr-antoinette')"),
            [(0,)])

    def test_elective_hre_is_not_an_independent_country_or_all_germany(self):
        self.assertEqual(self.q(
            "SELECT kind FROM v2_contexts WHERE id='ctx-world-hre'"),
            [("elective_office_context",)])
        self.assertTrue(all(r[0]=="emperor" for r in self.q(
            "SELECT role_kind FROM v2_roles WHERE context_id='ctx-world-hre'")))

    def test_year_precision_and_only_recorded_day_precision(self):
        data=self.q(
            "SELECT p.end_date_json,p.start_date_json,p.meaning FROM v2_roles r "
            "JOIN v2_periods p ON p.id=r.period_id WHERE r.native_id='dn-ru-elizabeth'")
        self.assertEqual(len(data),1)
        end=json.loads(data[0][0]);start=json.loads(data[0][1])
        self.assertEqual((end["value"],end["calendar"],end["precision"]),
                         ("1762-01-05","gregorian","day"))
        self.assertEqual((start["value"],start["calendar"],start["precision"]),
                         ("1741","unspecified","year"))
        self.assertEqual(data[0][2],"role_window")
        self.assertEqual(self.report["p2"]["day_precision_endpoints"],1)

    def test_scoped_year_1781_not_forged_actual_reign_start(self):
        p=self.q("SELECT p.start_date_json,p.note FROM v2_roles r "
                 "JOIN v2_periods p ON p.id=r.period_id "
                 "WHERE r.native_id='ex-es-carlos3'")[0]
        self.assertIsNone(p[0])
        self.assertIn("1759",p[1])
        self.assertIn("1781",p[1])
        source=json.loads(self.q(
            "SELECT raw_json FROM v2_world_imports WHERE native_id='ex-es-carlos3'")[0][0])
        self.assertEqual(source["actual_start_year"],1759)
        self.assertEqual(self.report["p2"]["known_original_start_years"],6)

    def test_study_horizon_1800_does_not_claim_office_ended(self):
        p=self.q("SELECT p.end_date_json,p.note FROM v2_roles r "
                 "JOIN v2_periods p ON p.id=r.period_id "
                 "WHERE r.native_id='ex-ru-paul'")[0]
        self.assertIsNone(p[0])
        self.assertIn("study horizon",p[1])
        self.assertTrue(self.report["p2"]["right_censored_at_1800"]>=3)

    def test_source_assertions_have_namespaces_and_not_assessed_confidence(self):
        refs=self.q(
            "SELECT s.id FROM v2_assertion_sources a "
            "JOIN v2_sources s ON s.id=a.source_id "
            "WHERE a.assertion_id='v2-assert-dn-ru-peter3' ORDER BY s.id")
        self.assertEqual(refs,[("world-1762:WP01",),("world-1762:WP02",)])
        no_sources=self.q("SELECT id FROM v2_assertions_without_sources")
        self.assertEqual(no_sources,[])
        confidences=self.q("SELECT DISTINCT confidence FROM v2_assertions")
        self.assertEqual(confidences,[("not_assessed",)])

    def test_canonical_sources_and_original_files_do_not_change(self):
        paths=[ROOT/"data/atlas/tenures.jsonl",ROOT/"data/atlas/provenance.jsonl",
               ROOT/"data/atlas/world-pilots/dynasty-1762-1780.json",
               ROOT/"data/atlas/world-pilots/extension-1781-1800.json",
               ROOT/"schemas/atlas.sql"]
        before=[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
        self.assertEqual(roles.validate_records(self.snapshot),self.report["p2"])
        self.assertEqual(before,[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths])

    def test_missing_world_person_fails_closed(self):
        bad=copy.deepcopy(self.snapshot)
        bad["world"]["dynasty-1762-1780.json"]["roles"][0]["person_id"]="not-a-person"
        with self.assertRaises(ValueError):
            roles.validate_records(bad)

    def test_invalid_role_kind_fails_closed(self):
        bad=copy.deepcopy(self.snapshot)
        bad["world"]["extension-1781-1800.json"]["additional_roles"][-1]["role_kind"]="king_of_everywhere"
        with self.assertRaisesRegex(ValueError,"invalid role kind"):
            roles.validate_records(bad)

    def test_forged_early_start_fails_closed(self):
        bad=copy.deepcopy(self.snapshot)
        r=next(r for r in bad["world"]["extension-1781-1800.json"]["additional_roles"]
               if r["id"]=="ex-es-carlos3")
        r["actual_start_year"]=1800
        with self.assertRaisesRegex(ValueError,"actual start"):
            roles.validate_records(bad)

    def test_invalid_exact_day_fails_closed(self):
        bad=copy.deepcopy(self.snapshot)
        r=next(r for r in bad["world"]["dynasty-1762-1780.json"]["roles"]
               if r["id"]=="dn-ru-elizabeth")
        r["end_gregorian"]="1762-02-31"
        with self.assertRaisesRegex(ValueError,"impossible Gregorian"):
            roles.validate_records(bad)

    def test_missing_evidence_fails_closed(self):
        bad=copy.deepcopy(self.snapshot)
        bad["world"]["extension-1781-1800.json"]["institutions"][0]["source_ids"]=[]
        with self.assertRaises(ValueError):
            roles.validate_records(bad)

    def test_new_role_on_birthplace_only_context_fails_closed(self):
        bad=copy.deepcopy(self.snapshot)
        bad["world"]["extension-1781-1800.json"]["additional_roles"][0]["polity_id"]="meck"
        with self.assertRaisesRegex(ValueError,"birthplace-only"):
            roles.validate_records(bad)

    def test_wrong_emperor_title_in_hre_fails_closed(self):
        bad=copy.deepcopy(self.snapshot)
        target=next(r for r in bad["world"]["dynasty-1762-1780.json"]["roles"]
                    if r["id"]=="dn-hre-joseph")
        target["role_kind"]="sovereign"
        with self.assertRaisesRegex(ValueError,"HRE elective"):
            roles.validate_records(bad)

    def test_no_historical_claim_in_validation_receipt(self):
        self.assertFalse(self.report["p1"]["historical_truth_verified_by_ci"])
        self.assertFalse(self.report["p2"]["historical_truth_verified_by_ci"])
        self.assertEqual(self.q("SELECT count(*) FROM v2_context_relations"),[(0,)])
        self.assertEqual(self.q("SELECT count(*) FROM v2_territorial_observations"),[(0,)])


if __name__=="__main__":
    unittest.main()
