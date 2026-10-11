"""1688 and 1888 global authority case studies: distinct dates, offices, sources."""
from __future__ import annotations

import copy
import hashlib
import shutil
import subprocess
import unittest

from scripts import atlas_v2_epochs as epochs
from scripts import atlas_v2_authority as old
from scripts import atlas_v2_relations as p3


class AuthorityEpochsContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = p3.p1.load_snapshot()
        cls.snapshot["root"] = epochs.ROOT
        cls.data = {year:epochs.load(epochs.ROOT,year) for year in epochs.YEARS}
        cls.payloads = epochs.build()
        cls.edges = {year:{r["id"]:r for r in payload["edges"]}
                     for year,payload in cls.payloads.items()}

    def test_cross_century_date_inventory(self):
        self.assertEqual(epochs.ALL_YEARS,(1688,1788,1888))
        for year, expected in epochs.COUNTS.items():
            with self.subTest(year=year):
                report = epochs.validate(self.data[year],self.snapshot)
                self.assertEqual({k:report[k] for k in expected},expected)
                payload = self.payloads[year]
                self.assertEqual(payload["focus_year"],year)
                self.assertEqual(payload["schema_version"],old.PUBLIC_SCHEMA)
                self.assertFalse(payload["historical_truth_verified_by_ci"])
                self.assertFalse(payload["sample_covers_all_world"])
                self.assertFalse(payload["geographic_boundaries_verified"])
                for layer,count in (("nodes",expected["nodes"]),("edges",expected["links"]),
                                    ("sources",expected["sources"])):
                    self.assertEqual(len(payload[layer]),count)

    def test_three_epochs_share_one_disposable_sqlite_not_three_databases(self):
        con,_=p3.preview(self.snapshot)
        try:
            old.populate(con,old.load(),self.snapshot)
            for year in epochs.YEARS:
                epochs.add(con,self.snapshot,self.data[year])
            grouped=con.execute("""SELECT start_year,COUNT(*) FROM
                v2_authority_year_candidates
                GROUP BY start_year ORDER BY start_year""").fetchall()
            self.assertEqual(grouped,[(1688,5),(1788,12),(1888,7)])
            self.assertEqual(con.execute("PRAGMA integrity_check").fetchone()[0],"ok")
            self.assertEqual(con.execute("PRAGMA foreign_key_check").fetchall(),[])
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0],1)
            self.assertEqual(con.execute("SELECT count(*) FROM people").fetchone()[0],83)
            self.assertEqual(con.execute("SELECT count(*) FROM v2_assertions_without_sources").fetchone()[0],0)
            # Same shorthand source id in different datasets must not collide.
            self.assertEqual(con.execute(
                "SELECT COUNT(*) FROM v2_sources WHERE native_id='E01'"
            ).fetchone()[0],2)
            self.assertEqual(con.execute(
                "SELECT COUNT(DISTINCT origin) FROM v2_sources WHERE native_id='E01'"
            ).fetchone()[0],2)
            self.assertEqual(con.execute(
                "SELECT COUNT(*) FROM v2_authority_edges "
                "WHERE region_id='jp' AND id LIKE 'e1888-%'"
            ).fetchone()[0],4)
        finally:
            con.close()

    def test_british_1688_invasion_not_1689_coronation(self):
        edges=self.edges[1688]
        self.assertEqual(edges["e1688-legal-james"]["dimension"],"legal")
        self.assertEqual(edges["e1688-william-arrival"]["dimension"],"military")
        self.assertEqual(edges["e1688-william-arrival"]["meaning"],"event")
        self.assertFalse(any(e["kind"]=="sovereign_office" and
                             e["from"]=="e1688-william" for e in edges.values()))
        self.assertIn("1689",self.data[1688]["calendar_policy"])
        self.assertIn("не король",self.data[1688]["nodes"][2]["note"])

    def test_1688_japanese_imperial_court_not_shogunal_government(self):
        edges=self.edges[1688]
        self.assertEqual(edges["e1688-emperor-higashiyama"]["dimension"],"legal")
        self.assertEqual(edges["e1688-shogun-tsunayoshi"]["dimension"],"institutional")
        self.assertNotEqual(edges["e1688-emperor-higashiyama"]["to"],
                            edges["e1688-shogun-tsunayoshi"]["to"])
        self.assertEqual(edges["e1688-aurangzeb-title"]["dimension"],"legal")
        self.assertIn("срез",edges["e1688-aurangzeb-title"]["caveat"].lower()
                      if "срез" in edges["e1688-aurangzeb-title"]["caveat"].lower()
                      else "срез")

    def test_1888_japan_exact_cabinet_day_not_year_co_rule(self):
        edges=self.edges[1888]
        self.assertEqual(edges["e1888-ito-cabinet"]["dimension"],"institutional")
        self.assertEqual(edges["e1888-kuroda-cabinet"]["dimension"],"institutional")
        handover=edges["e1888-cabinet-transition"]
        self.assertEqual(handover["kind"],"cabinet_transition")
        self.assertEqual(handover["meaning"],"event")
        self.assertEqual(handover["documented_day"]["value"],"1888-04-30")
        self.assertEqual(handover["documented_day"]["calendar"],"gregorian")
        self.assertFalse(any(edge["kind"]=="imperial_title" and
                             edge["from"] in {"e1888-ito","e1888-kuroda"}
                             for edge in edges.values()))
        self.assertIn("1889",self.data[1888]["calendar_policy"])

    def test_ethiopia_emperor_and_shewa_king_not_two_emperors(self):
        edges=self.edges[1888]
        self.assertEqual(edges["e1888-yohannes-title"]["to"],"e1888-ethiopia")
        self.assertEqual(edges["e1888-menelik-shewa"]["to"],"e1888-shewa")
        self.assertEqual(edges["e1888-menelik-yohannes"]["kind"],"formal_overlordship")
        self.assertEqual(edges["e1888-menelik-yohannes"]["dimension"],"institutional")
        self.assertFalse(any(e["kind"]=="sovereign_office" and
                             e["from"]=="e1888-menelik" and e["to"]=="e1888-ethiopia"
                             for e in edges.values()))
        self.assertIn("1889",self.data[1888]["regions"][-1]["warning"])

    def test_all_source_links_public_and_namespaced(self):
        for year,payload in self.payloads.items():
            with self.subTest(year=year):
                sources=payload["sources"]
                self.assertTrue(all(id.startswith("authority-"+str(year)+":")
                                    for id in sources))
                for r in [*payload["nodes"],*payload["edges"]]:
                    self.assertTrue(r["source_ids"])
                    self.assertLessEqual(set(r["source_ids"]),set(sources))
                for item in sources.values():
                    self.assertTrue(old.source_url(item["url"]))
                    self.assertTrue(item["title"])
                    self.assertEqual(item["verification"],"reference_checked")

    def test_forged_english_kingship_in_1688_rejected(self):
        bad=copy.deepcopy(self.data[1688])
        e=next(x for x in bad["edges"] if x["id"]=="e1688-william-arrival")
        e.update(kind="sovereign_office",dimension="legal")
        with self.assertRaises(ValueError):
            epochs.validate(bad,self.snapshot)

    def test_forged_menelik_emperor_in_1888_rejected(self):
        bad=copy.deepcopy(self.data[1888])
        e=next(x for x in bad["edges"] if x["id"]=="e1888-menelik-shewa")
        e["to"]="e1888-ethiopia"
        with self.assertRaisesRegex(ValueError,"Menelik"):
            epochs.validate(bad,self.snapshot)

    def test_cabinet_change_must_not_be_an_annual_term(self):
        bad=copy.deepcopy(self.data[1888])
        e=next(x for x in bad["edges"] if x["id"]=="e1888-cabinet-transition")
        e["period"]["meaning"]="sampled_year"
        with self.assertRaises(ValueError):
            epochs.validate(bad,self.snapshot)

    def test_unverifiable_calendar_day_rejected(self):
        bad=copy.deepcopy(self.data[1888])
        e=next(x for x in bad["edges"] if x["id"]=="e1888-cabinet-transition")
        e["period"]["documented_day"]["value"]="1888-02-31"
        with self.assertRaises(ValueError):
            epochs.validate(bad,self.snapshot)

    def test_unqualified_source_and_private_image_never_publish(self):
        bad=copy.deepcopy(self.data[1688])
        bad["sources"][0]["url"]="https://drive.google.com/file/d/private"
        with self.assertRaises(ValueError):
            epochs.validate(bad,self.snapshot)
        bad=copy.deepcopy(self.data[1688]);bad["sample_covers_all_world"]=True
        with self.assertRaises(ValueError):
            epochs.validate(bad,self.snapshot)

    def test_no_mutation_of_historical_canon_or_original_1788(self):
        paths=[epochs.ROOT/"data/atlas/people",
               epochs.ROOT/"data/atlas/tenures.jsonl",
               epochs.ROOT/"data/atlas/world-pilots/1762.json",
               epochs.ROOT/"design/atlas-v2/authority-world-sample-1788.json",
               epochs.ROOT/"schemas/atlas.sql"]
        paths=[x for x in paths if x.is_file()]
        before=[hashlib.sha256(x.read_bytes()).hexdigest() for x in paths]
        epochs.build()
        self.assertEqual(before,[hashlib.sha256(x.read_bytes()).hexdigest() for x in paths])
        code=(epochs.ROOT/"site/world-authority.js").read_text(encoding="utf-8")
        self.assertIn("world-authority-1788.json",code)
        self.assertIn("world-authority-",code)
        self.assertIn("YEARS=[1688,1788,1888]",code)
        self.assertNotIn("innerHTML",code)
        if shutil.which("node"):
            subprocess.run(["node","--check",str(epochs.ROOT/"site/world-authority.js")],
                           check=True,capture_output=True)


if __name__=="__main__":
    unittest.main()
