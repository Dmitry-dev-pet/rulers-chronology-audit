"""P5 world authority pilot: no false subordination or unsourced control."""
from __future__ import annotations

import copy
import hashlib
import shutil
import subprocess
import unittest

from scripts import atlas_v2_authority as model
from scripts import atlas_v2_relations as p3


class WorldAuthority1788(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=model.load()
        cls.snapshot=p3.p1.load_snapshot()
        cls.snapshot["root"]=model.ROOT
        cls.result=model.projection()
        cls.nodes={n["id"]:n for n in cls.result["nodes"]}
        cls.edges={e["id"]:e for e in cls.result["edges"]}

    def test_conservative_inventory_and_scope(self):
        d=self.result
        self.assertEqual(d["schema_version"],model.PUBLIC_SCHEMA)
        self.assertEqual(d["focus_year"],1788)
        self.assertFalse(d["historical_truth_verified_by_ci"])
        self.assertFalse(d["sample_covers_all_world"])
        self.assertFalse(d["geographic_boundaries_verified"])
        self.assertEqual((len(d["regions"]),len(d["nodes"]),
                          len(d["edges"]),len(d["sources"])),(3,18,12,8))
        self.assertEqual({r["id"] for r in d["regions"]},{"hre","india","qing"})
        self.assertEqual({e["dimension"] for e in d["edges"]},
                         {"legal","practical","military","diplomatic","institutional"})

    def test_claims_are_sql_derived_not_javascript_hardcoded(self):
        self.assertEqual(model.validate(self.data,self.snapshot)["links"],12)
        con,_=p3.preview(self.snapshot)
        try:
            counts=model.populate(con,self.data,self.snapshot)
            self.assertEqual(counts["nodes"],18)
            self.assertEqual(con.execute("SELECT count(*) FROM v2_authority_nodes").fetchone()[0],18)
            self.assertEqual(con.execute("SELECT count(*) FROM v2_authority_edges").fetchone()[0],12)
            self.assertEqual(con.execute("PRAGMA foreign_key_check").fetchall(),[])
            self.assertEqual(con.execute("PRAGMA integrity_check").fetchone()[0],"ok")
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0],1)
            self.assertEqual(con.execute("SELECT count(*) FROM v2_assertions_without_sources").fetchone()[0],0)
            self.assertEqual(con.execute("SELECT count(*) FROM people").fetchone()[0],83)
        finally:
            con.close()

    def test_world_refs_only_explicit_existing_identity(self):
        people={p["world_id"] for p in self.snapshot["crosswalk"]["people"]}
        contexts={c["id"] for c in self.snapshot["crosswalk"]["contexts"]}
        self.assertEqual(self.nodes["h-george"]["p3_person_id"],"gb-george3")
        self.assertEqual(self.nodes["h-joseph"]["p3_person_id"],"hre-joseph")
        self.assertEqual(self.nodes["h-hanover"]["p3_context_id"],"ctx-world-han")
        for n in self.result["nodes"]:
            if n["p3_person_id"]:self.assertIn(n["p3_person_id"],people)
            if n["p3_context_id"]:self.assertIn(n["p3_context_id"],contexts)

    def test_german_emperor_is_not_direct_hanover_governor(self):
        edge=self.edges["h-e2"]
        self.assertEqual((edge["kind"],edge["dimension"]),
                         ("constitutional_membership","institutional"))
        self.assertEqual((edge["from"],edge["to"]),("h-hanover","h-empire"))
        self.assertEqual(self.edges["h-e3"]["to"],"h-hanover")
        self.assertEqual(self.edges["h-e4"]["to"],"h-britain")
        self.assertEqual(self.edges["h-e3"]["from"],self.edges["h-e4"]["from"])
        self.assertNotEqual(self.edges["h-e3"]["to"],self.edges["h-e4"]["to"])

    def test_mughal_formal_title_vs_local_army(self):
        self.assertEqual(self.edges["i-e1"]["dimension"],"legal")
        self.assertEqual(self.edges["i-e2"]["dimension"],"practical")
        self.assertEqual(self.edges["i-e2"]["meaning"],"event")
        self.assertEqual(self.edges["i-e3"]["dimension"],"military")
        self.assertEqual(self.edges["i-e3"]["meaning"],"event")
        self.assertEqual(self.edges["i-e2"]["to"],"i-delhi")
        self.assertEqual(self.edges["i-e3"]["to"],"i-delhi")
        self.assertEqual(self.edges["i-e4"]["kind"],"fiscal_administration")
        self.assertEqual(self.edges["i-e5"]["to"],"i-mysore")
        self.assertFalse(any(e["from"]=="i-mughal" and e["to"]=="i-mysore"
                             for e in self.result["edges"]))

    def test_qing_diplomatic_hierarchy_is_not_provincial_rule(self):
        e=self.edges["q-e3"]
        self.assertEqual((e["from"],e["to"]),("q-joseon","q-qing"))
        self.assertEqual((e["dimension"],e["kind"]),
                         ("diplomatic","tributary_diplomacy"))
        self.assertIn("не доказывает прямое",e["caveat"])
        self.assertEqual(self.edges["q-e2"]["from"],"q-jeongjo")
        self.assertEqual(self.edges["q-e1"]["from"],"q-qianlong")

    def test_every_node_and_edge_has_public_qualified_sources(self):
        d=self.result
        for x in [*d["nodes"],*d["edges"]]:
            with self.subTest(id=x["id"]):
                self.assertTrue(x["source_ids"])
                for sid in x["source_ids"]:
                    self.assertIn(sid,d["sources"])
                    self.assertTrue(model.source_url(d["sources"][sid]["url"]))
        for edge in d["edges"]:
            self.assertEqual(edge["start_year"],1788)
            self.assertEqual(edge["end_year"],1788)
            self.assertIn("Источниковый срез",edge["caveat"])

    def test_prohibits_unsupported_world_completeness(self):
        for key in ("historical_truth_verified_by_ci",
                    "sample_covers_all_world","geographic_boundaries_verified"):
            bad=copy.deepcopy(self.data)
            bad[key]=True
            with self.assertRaises(ValueError):
                model.validate(bad,self.snapshot)

    def test_prohibits_collapse_of_qing_tributary_relation(self):
        bad=copy.deepcopy(self.data)
        e=next(x for x in bad["edges"] if x["id"]=="q-e3")
        e.update(kind="sovereign_office",dimension="legal")
        with self.assertRaises(ValueError):
            model.validate(bad,self.snapshot)

    def test_prohibits_local_military_event_as_continuous_control(self):
        bad=copy.deepcopy(self.data)
        e=next(x for x in bad["edges"] if x["id"]=="i-e2")
        e["period"]["meaning"]="sampled_year"
        with self.assertRaises(ValueError):
            model.validate(bad,self.snapshot)

    def test_prohibits_unknown_persons_and_false_subordinate(self):
        bad=copy.deepcopy(self.data)
        n=next(x for x in bad["nodes"] if x["id"]=="h-joseph")
        n["p3_person_id"]="not-in-world-pilot"
        with self.assertRaises(ValueError):
            model.validate(bad,self.snapshot)

    def test_unchanged_source_files_and_no_ai_political_guesses(self):
        original=[
            model.ROOT/"data/atlas/tenures.jsonl",
            model.ROOT/"data/atlas/sources.jsonl",
            model.ROOT/"data/atlas/world-pilots/dynasty-1762-1780.json",
            model.ROOT/"schemas/atlas.sql"
        ]
        before=[hashlib.sha256(p.read_bytes()).hexdigest() for p in original]
        model.validate(self.data,self.snapshot)
        after=[hashlib.sha256(p.read_bytes()).hexdigest() for p in original]
        self.assertEqual(before,after)
        code=(model.ROOT/"site/world-authority.js").read_text(encoding="utf-8")
        self.assertIn("world-authority-1788.json",code)
        self.assertIn("source_ids",code)
        self.assertNotIn("innerHTML",code)
        self.assertNotIn("eval(",code)
        if shutil.which("node"):
            subprocess.run(["node","--check",str(model.ROOT/"site/world-authority.js")],
                           check=True,capture_output=True)


if __name__ == "__main__":
    unittest.main()
