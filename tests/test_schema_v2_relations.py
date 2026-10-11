"""Contracts for P3 genealogy, ruling-house candidates and sourced relations."""
from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path

from scripts import atlas_v2_relations as p3

ROOT=Path(__file__).resolve().parents[1]


class RelationsV2Contract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot=p3.p1.load_snapshot(ROOT)
        cls.snapshot["root"]=ROOT
        cls.snapshot["relation_aliases"]=p3.alias_config(cls.snapshot)
        cls.con,cls.report=p3.preview(cls.snapshot)

    @classmethod
    def tearDownClass(cls):
        cls.con.close()

    def query(self,sql,args=()):
        return self.con.execute(sql,args).fetchall()

    def test_faithful_counts_and_integrity(self):
        self.assertEqual(self.report["p1"]["unified_contexts"],18)
        self.assertEqual(self.report["p2"]["person_roles"],40)
        self.assertEqual(self.report["p3"]["houses"],4)
        self.assertEqual(self.report["p3"]["documented_house_memberships"],18)
        self.assertEqual(self.report["p3"]["world_relationship_evidence"],29)
        self.assertEqual(self.report["p3"]["normalized_relationships"],27)
        self.assertEqual(self.report["p3"]["explicit_relation_aliases"],2)
        for table,n in (
            ("v2_houses",4),("v2_house_affiliations",18),
            ("v2_house_imports",4),("v2_affiliation_imports",18),
            ("v2_relationships",27),("v2_relationship_imports",29),
            ("v2_context_relations",1),
        ):
            with self.subTest(table=table):
                self.assertEqual(self.query("SELECT count(*) FROM "+table),[(n,)])
        self.assertEqual(self.query("SELECT count(*) FROM v2_assertions"),[(92,)])
        self.assertEqual(self.query("SELECT * FROM v2_assertions_without_sources"),[])
        self.assertEqual(self.query("PRAGMA foreign_key_check"),[])
        self.assertEqual(self.query("PRAGMA integrity_check"),[("ok",)])
        self.assertEqual(self.query("PRAGMA user_version"),[(1,)])

    def test_lossless_house_member_and_relation_source_payloads(self):
        expected={}
        for d,r in p3.world_relations(self.snapshot)[0]:
            expected[r["id"]]=r
        imports=self.query("SELECT native_id,raw_json FROM v2_relationship_imports")
        self.assertEqual(len(imports),29)
        for name,payload in imports:
            with self.subTest(relation=name):
                self.assertEqual(json.loads(payload),expected[name])
        families=self.snapshot["world"][p3.FOOTPRINTS]["families"]
        source_families={f["id"]:f for f in families}
        for name,payload in self.query("SELECT native_id,raw_json FROM v2_house_imports"):
            self.assertEqual(json.loads(payload),source_families[name])
        member_index={(f["id"]+":"+m["person_id"]):m
                      for f in families for m in f["members"]}
        for native,payload in self.query("SELECT native_id,raw_json FROM v2_affiliation_imports"):
            self.assertEqual(json.loads(payload),member_index[native])

    def test_two_base_aliases_are_one_normalized_marriage_and_treaty(self):
        alias_rows=self.query("""SELECT native_id,relationship_id,alias_of
            FROM v2_relationship_imports WHERE dataset='1762.json'
            ORDER BY native_id""")
        self.assertEqual(alias_rows,[
            ("wp-marriage-1745","v2-p3-rel-dn-ru-marriage",
             "v2-p3-rel-dn-ru-marriage"),
            ("wp-petersburg-peace","v2-p3-rel-dn-ru-pr-peace",
             "v2-p3-rel-dn-ru-pr-peace"),
        ])
        self.assertEqual(self.query(
            "SELECT count(*) FROM v2_relationships WHERE native_id IN "
            "('wp-marriage-1745','wp-petersburg-peace')"),[(0,)])
        self.assertEqual(self.query(
            "SELECT kind,domain FROM v2_relationships WHERE native_id='dn-ru-pr-peace'"),
            [("treaty","interstate")])

    def test_personal_union_requires_two_distinct_qualifying_roles(self):
        union=self.query("""SELECT id,context_a,context_b,kind,
                  external_person_id FROM v2_context_relations""")
        self.assertEqual(union,[(
            "v2-p3-union-dn-union-gb-han",
            "ctx-world-gb","ctx-world-han","personal_union","gb-george3",
        )])
        self.assertEqual(self.query(
            "SELECT id FROM v2_personal_unions_without_role_candidates"),[])
        self.assertEqual(self.query(
            "SELECT id,kind FROM v2_contexts "
            "WHERE id IN ('ctx-world-gb','ctx-world-han') ORDER BY id"),
            [("ctx-world-gb","polity"),("ctx-world-han","polity")])
        george=self.query("SELECT context_id,role_kind FROM v2_roles "
                          "WHERE external_person_id='gb-george3' ORDER BY context_id")
        self.assertIn(("ctx-world-gb","sovereign"),george)
        self.assertIn(("ctx-world-han","elector"),george)

    def test_union_cannot_be_created_from_spousal_relation(self):
        bad=copy.deepcopy(self.snapshot)
        rel=next(r for r in bad["world"][p3.DYNASTY]["relations"]
                 if r["id"]=="dn-union-gb-han")
        rel["subjects"]=["gb-charlotte"]
        with self.assertRaisesRegex(ValueError,"personal union"):
            c,_=p3.preview(bad)
            c.close()

    def test_year_1788_documented_houses_across_polities(self):
        rows=p3.house_year_candidates(self.con,1788)
        by_house={}
        for r in rows:
            by_house.setdefault(r["house_id"],[]).append(r)
        bourbon=by_house["v2-house-bourbon"]
        self.assertEqual({r["context_id"] for r in bourbon},
                         {"ctx-world-fr","ctx-world-es"})
        self.assertTrue(all(r["role_kind"]=="sovereign" for r in bourbon))
        hab=by_house["v2-house-habsburg-lorraine"]
        self.assertEqual({r["context_id"] for r in hab},
                         {"ctx-world-hab","ctx-world-tusc"})
        self.assertNotIn("ctx-world-hre",{r["context_id"] for r in hab})
        hanover=by_house["v2-house-hanover"]
        self.assertEqual({r["context_id"] for r in hanover},
                         {"ctx-world-gb","ctx-world-han"})
        self.assertEqual({r["external_person_id"] for r in hanover},{"gb-george3"})
        self.assertTrue(all(r["role_kind"] in {"sovereign","elector"}
                            for r in rows))
        with self.assertRaises(ValueError):
            p3.house_year_candidates(self.con,0)

    def test_1798_pauls_branch_is_not_official_dominant_house(self):
        row=self.query("""SELECT affiliation,person_id,external_person_id
            FROM v2_house_affiliations WHERE house_id='v2-house-holstein-gottorp'
              AND person_id='person-14b51b51093f55ce'""")
        self.assertEqual(row,[("branch_lineage","person-14b51b51093f55ce",None)])
        self.assertFalse(any(r["person_id"]=="person-14b51b51093f55ce"
                             for r in p3.house_year_candidates(self.con,1798)))
        rus=self.query("SELECT id FROM v2_roles "
                       "WHERE native_id='ex-ru-paul'")
        self.assertEqual(len(rus),1)

    def test_consort_does_not_make_her_birth_house_rule_host_state(self):
        ruling=p3.house_year_candidates(self.con,1788)
        self.assertFalse(any(r["external_person_id"]=="fr-antoinette"
                             for r in ruling))
        self.assertFalse(any(r["external_person_id"]=="pt-carlota"
                             for r in ruling))
        # Maria Theresa recorded only as 'dynastic_union' in the curated
        # Habsburg-Lorraine footprint; not silently reclassified by marriage.
        self.assertEqual(self.query(
            "SELECT affiliation FROM v2_house_affiliations "
            "WHERE house_id='v2-house-habsburg-lorraine' "
            "AND external_person_id='hab-maria'"),[("dynastic_union",)])
        self.assertFalse(any(r["external_person_id"]=="hab-maria"
                             for r in ruling))

    def test_intermarriage_does_not_merge_polities_or_ethnicities(self):
        france=self.query("SELECT id FROM v2_contexts "
                          "WHERE id IN ('ctx-world-fr','ctx-world-frrep')")
        self.assertEqual(len(france),2)
        self.assertEqual(self.query(
            "SELECT count(*) FROM v2_personal_unions_without_role_candidates"),[(0,)])
        self.assertEqual(self.query("SELECT count(*) FROM v2_person_relations"),[(0,)])
        self.assertFalse(self.report["p3"]["birthplace_or_nationality_inferred"])

    def test_event_succession_is_not_active_through_research_window(self):
        p=self.query("""SELECT r.kind,p.meaning,p.start_year,p.end_year,r.event_year
            FROM v2_relationships r JOIN v2_periods p ON p.id=r.period_id
            WHERE r.native_id='dn-france-change-1774'""")
        self.assertEqual(p,[("succession","event",1774,1774,1774)])
        imperial=self.query("""SELECT kind,domain FROM v2_relationships
            WHERE native_id='dn-hre-change-1765'""")
        self.assertEqual(imperial,[("imperial_succession","political_roles")])

    def test_parent_evidence_is_not_birth_or_start_of_parenthood(self):
        r=self.query("""SELECT r.kind,p.meaning,p.start_year,p.end_year,
                               p.start_date_json
            FROM v2_relationships r JOIN v2_periods p ON p.id=r.period_id
            WHERE r.native_id='ex-ru-catherine-paul'""")
        self.assertEqual(r,[("parent","relation_evidence_window",1796,1796,None)])
        self.assertEqual(self.query(
            "SELECT count(*) FROM v2_houses WHERE id='v2-house-bourbon'"),[(1,)])

    def test_marriage_event_can_predate_study_window(self):
        r=self.query("""SELECT r.event_year,p.meaning,p.start_year,p.end_year
            FROM v2_relationships r JOIN v2_periods p ON p.id=r.period_id
            WHERE r.native_id='ex-pt-maria-pedro'""")
        self.assertEqual(r,[(1760,"relation_evidence_window",1781,1786)])

    def test_regency_does_not_make_regent_the_sovereign(self):
        self.assertEqual(self.query("""SELECT kind,domain FROM v2_relationships
            WHERE native_id='ex-sw-regency'"""),[("regency","political_roles")])
        rows=self.query("""SELECT role_kind,external_person_id
            FROM v2_roles WHERE native_id IN ('ex-sw-gustav4','ex-sw-charles')""")
        self.assertEqual(set(rows),{("sovereign","sw-gustav4"),
                                    ("regent","sw-charles")})
        self.assertNotIn("sw-charles",{r["external_person_id"]
                     for r in p3.house_year_candidates(self.con,1793)})

    def test_every_normalized_relationship_has_sources(self):
        self.assertEqual(self.query(
            "SELECT count(DISTINCT r.id) FROM v2_relationships r "
            "JOIN v2_assertion_sources a ON a.assertion_id=r.assertion_id"),[(27,)])
        self.assertEqual(self.query(
            "SELECT count(DISTINCT house_id) FROM v2_house_imports"),[(4,)])
        self.assertEqual(self.query(
            "SELECT count(DISTINCT affiliation_id) FROM v2_affiliation_imports"),[(18,)])
        self.assertEqual(self.query(
            "SELECT DISTINCT confidence FROM v2_assertions"),[("not_assessed",)])
        self.assertFalse(self.report["p3"]["historical_truth_verified_by_ci"])

    def test_invalid_house_member_rejected(self):
        bad=copy.deepcopy(self.snapshot)
        bad["world"][p3.FOOTPRINTS]["families"][0]["members"][0]["person_id"]="invented"
        with self.assertRaisesRegex(ValueError,"unknown house member"):
            p3.relations_validate(bad)

    def test_empty_house_source_rejected(self):
        bad=copy.deepcopy(self.snapshot)
        bad["world"][p3.FOOTPRINTS]["families"][0]["source_ids"]=[]
        with self.assertRaisesRegex(ValueError,"house without evidence"):
            p3.relations_validate(bad)

    def test_regency_as_marriage_rejected(self):
        bad=copy.deepcopy(self.snapshot)
        rel=next(r for r in bad["world"][p3.EXTENSION]["additional_relations"]
                 if r["id"]=="ex-sw-regency")
        rel["kind"]="marriage"  # two people, but historically a different relation
        with self.assertRaisesRegex(ValueError,"relation kind drift"):
            p3.relations_validate(bad)

    def test_false_alias_rejected(self):
        bad=copy.deepcopy(self.snapshot)
        bad["relation_aliases"]["aliases"][0]["canonical_id"]="dn-marriage-gb"
        with self.assertRaisesRegex(ValueError,"unreviewed relation alias"):
            p3.relations_validate(bad)

    def test_duplicate_relationship_source_rejected(self):
        bad=copy.deepcopy(self.snapshot)
        r=bad["world"][p3.EXTENSION]["additional_relations"][0]
        r["source_ids"].append(r["source_ids"][0])
        with self.assertRaisesRegex(ValueError,"evidence absent or duplicated"):
            p3.relations_validate(bad)

    def test_invalid_parent_unknown_subject_rejected(self):
        bad=copy.deepcopy(self.snapshot)
        rel=next(r for r in bad["world"][p3.EXTENSION]["additional_relations"]
                 if r["id"]=="ex-hab-leopold-francis")
        rel["subjects"][1]="not-an-actor"
        with self.assertRaisesRegex(ValueError,"references unknown"):
            p3.relations_validate(bad)

    def test_invalid_one_time_event_window_rejected(self):
        bad=copy.deepcopy(self.snapshot)
        rel=next(r for r in bad["world"][p3.DYNASTY]["relations"]
                 if r["id"]=="dn-france-change-1774")
        del rel["event_year"]
        with self.assertRaisesRegex(ValueError,"one-time event without event year"):
            p3.relations_validate(bad)

    def test_house_and_relation_drafts_do_not_write_source_files(self):
        files=[ROOT/"data/atlas/tenures.jsonl",
               ROOT/"data/atlas/person_facts.jsonl",
               ROOT/"data/atlas/world-pilots/1762.json",
               ROOT/"data/atlas/world-pilots/dynasty-footprints-1762-1800.json",
               ROOT/"schemas/atlas.sql"]
        before=[hashlib.sha256(p.read_bytes()).hexdigest() for p in files]
        self.assertEqual(p3.relations_validate(self.snapshot),self.report["p3"])
        after=[hashlib.sha256(p.read_bytes()).hexdigest() for p in files]
        self.assertEqual(before,after)


if __name__=="__main__":
    unittest.main()
