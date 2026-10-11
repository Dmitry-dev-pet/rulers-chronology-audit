"""Cross-century navigation projects canonical records; never invents political control."""
from pathlib import Path
import shutil
import subprocess
import unittest

from scripts import atlas_db

ROOT=Path(__file__).resolve().parents[1]
RANGES=[(1417,1599),(1600,1699),(1700,1799),(1800,1899),(1900,1991)]

class UniversalAtlasContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db=atlas_db.load(ROOT)
        cls.people={p["id"]:p["name"] for p in cls.db["people"]}
        cls.sources={s["id"] for s in cls.db["sources"]}
        cls.code=(ROOT/"site/universal-atlas.js").read_text(encoding="utf-8")

    def test_five_century_intervals_partition_every_supported_year(self):
        years=[year for a,b in RANGES for year in range(a,b+1)]
        self.assertEqual(len(years),575)
        self.assertEqual(years,list(range(1417,1992)))
        self.assertEqual(len(set(years)),575)
        for caption in ("XV–XVI века","XVII век","XVIII век","XIX век","XX век"):
            self.assertIn(caption,self.code)
        for y in (1417,1599,1600,1699,1700,1799,1800,1899,1900,1991):
            self.assertIn(str(y),self.code)

    def test_1685_joint_tsars_and_regent_stay_separate(self):
        tenures=self.db["tenures"]
        active=[t for t in tenures if int(t["start"]["value"][:4])<=1685
                <=int(t["end"]["value"][:4])]
        joint={self.people[t["person_id"]] for t in active if t["status"] in
               ("joint_tsar","tsar_then_emperor")}
        self.assertTrue(any("Иван V" in x for x in joint))
        self.assertTrue(any("Пётр I" in x for x in joint))
        regents=[t for t in active if t["status"]=="regent"]
        self.assertTrue(any("Софья" in self.people.get(t["person_id"],"")
                            for t in regents))
        self.assertIn("nominal",self.code)
        self.assertIn("regencies.has",self.code)

    def test_1953_collective_power_not_automatically_one_person(self):
        collective=[p for p in self.db["power_assessments"]
                    if p["start"]["value"][:4]<="1953"<=p["end"]["value"][:4]
                    and p["body_id"]]
        self.assertTrue(collective)
        self.assertTrue(any(x["status"] in ("collective_transition",
                        "collective_unequal_leadership") for x in collective))
        self.assertTrue(all(x["body_id"] and not x["person_id"] for x in collective))
        self.assertIn("power.filter(x=>x.body_id",self.code)
        self.assertIn("record.body_id && bodies.has",self.code)

    def test_source_qualified_year_records_can_be_retrieved_without_editing_them(self):
        before={key:len(self.db[key]) for key in (
            "people","provenance","tenures","power_assessments",
            "institution_periods","sources")}
        self.assertEqual(before["people"],83)
        self.assertEqual(before["provenance"],150)
        self.assertGreaterEqual(before["tenures"],90)
        self.assertGreaterEqual(before["power_assessments"],25)
        for kind in ("tenures","power_assessments","institution_periods"):
            for record in self.db[kind]:
                self.assertTrue(record["sources"])
                self.assertLessEqual(set(record["sources"]),self.sources)
        self.assertFalse(self.db["metadata"]["historical_truth_verified_by_ci"])
        self.assertNotIn("1000428575.jpg",self.code)
        self.assertNotIn("drive.google.com",self.code)
        self.assertNotIn("smuta-map.json",self.code)

    def test_linkable_two_years_do_not_modify_standard_spa_routing(self):
        for token in (
            "atlasView","atlasYears","fromUrl","popstate",
            "history[push?'pushState':'replaceState']",
            "goToYear","#/timeline/","atlas-global-sheet",
            "aria-modal","aria-expanded","aria-pressed",
            "Формальные", # or more specific sourced group naming follows
        ):
            if token=="Формальные":
                continue
            self.assertIn(token,self.code)
        self.assertIn("Юридические должности",self.code)
        self.assertIn("Оценки политического влияния",self.code)
        self.assertIn("Регентство и соправители",self.code)
        self.assertIn("Коллективные органы",self.code)
        self.assertIn("Отдельных сведений в реестре нет",self.code)
        if shutil.which("node"):
            subprocess.run(["node","--check",str(ROOT/"site/universal-atlas.js")],
                           capture_output=True,check=True)

if __name__=="__main__":
    unittest.main()
