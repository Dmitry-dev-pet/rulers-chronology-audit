"""Research contracts for the two new transition dossiers and public citations."""
import copy
import json
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import atlas_db, transition_cases

ROOT = atlas_db.ROOT


class TransitionResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = atlas_db.load(ROOT)
        cls.data = transition_cases.load(ROOT, cls.db)
        cls.cases = {c["id"]: c for c in cls.data["cases"]}

    def test_two_periods_and_26_sourced_records(self):
        self.assertEqual(set(self.cases), {"smuta-1598-1613", "ussr-1991"})
        self.assertEqual((len(self.cases["smuta-1598-1613"]["records"]),
                          len(self.cases["ussr-1991"]["records"])), (12, 14))
        self.assertEqual(self.cases["smuta-1598-1613"]["focus_year"], 1610)
        self.assertEqual(self.cases["ussr-1991"]["focus_year"], 1991)
        self.assertIs(self.data["historical_truth_verified_by_ci"], False)

    def test_four_distinct_kinds_and_no_created_person(self):
        ids = {x["id"] for x in self.db["people"]}
        for case in self.cases.values():
            rows = case["records"]
            self.assertEqual({x["category"] for x in rows}, transition_cases.CATEGORIES)
            self.assertTrue(all(x["sources"] and x["verification"] == "reference_checked" for x in rows))
            self.assertTrue(all(x["person_id"] is None or x["person_id"] in ids for x in rows))
        # Russia's president and organs appear as a different political center
        # without minting a fabricated USSR-presidential tenure for Yeltsin.
        russian = next(x for x in self.cases["ussr-1991"]["records"] if x["id"] == "ussr-1991d")
        self.assertEqual(russian["category"], "practical")
        self.assertIsNone(russian["person_id"])

    def test_1610_does_not_crown_vladislav_or_erase_semiboyarshchina(self):
        rows = {x["id"]: x for x in self.cases["smuta-1598-1613"]["records"]}
        self.assertEqual(rows["smuta-1610a"]["category"], "practical")
        self.assertIn("реально", rows["smuta-1610a"]["summary"])
        self.assertEqual(rows["smuta-1610b"]["category"], "claim")
        self.assertEqual(rows["smuta-1610b"]["date"]["value"], "1610-08-17")
        self.assertEqual(rows["smuta-1610b"]["date"]["calendar"], "julian")
        self.assertIn("не был венчан", rows["smuta-1610b"]["caveat"])
        self.assertEqual(rows["smuta-1612a"]["date"]["precision"], "month")
        self.assertEqual(rows["smuta-1612a"]["date"]["calendar"], "unspecified")
        self.assertEqual(rows["smuta-1613a"]["date"]["value"], "1613-02-21")
        self.assertEqual(rows["smuta-1613b"]["date"]["value"], "1613-07-11")

    def test_1991_coup_cabinet_reorganization_and_union_end_are_separate(self):
        rows = {x["id"]: x for x in self.cases["ussr-1991"]["records"]}
        self.assertEqual(rows["ussr-1991c"]["category"], "claim")
        self.assertEqual(rows["ussr-1991c"]["date"]["value"], "1991-08-19")
        self.assertEqual(rows["ussr-1991g"]["date"]["value"], "1991-08-28")
        self.assertEqual(rows["ussr-1991h"]["date"]["value"], "1991-08-28")
        self.assertNotEqual(rows["ussr-1991g"]["sources"], rows["ussr-1991h"]["sources"])
        for name,date in [
            ("ussr-1991j","1991-09-05"),
            ("ussr-1991k","1991-12-08"),
            ("ussr-1991l","1991-12-21"),
            ("ussr-1991m","1991-12-25"),
            ("ussr-1991n","1991-12-26")]:
            self.assertEqual(rows[name]["date"]["value"],date)
        self.assertIn("не прекратил", rows["ussr-1991j"]["caveat"])
        self.assertEqual(rows["ussr-1991n"]["category"],"institutional")

    def test_all_sources_are_canonical_and_public(self):
        sources={s["id"]:s for s in self.db["sources"]}
        refs={id for case in self.data["cases"] for x in case["records"] for id in x["sources"]}
        self.assertEqual(refs,{s["id"] for s in self.data["sources"]})
        self.assertLessEqual(refs,sources.keys())
        self.assertTrue(all(s["url"].startswith("https://") for s in self.data["sources"]))
        self.assertTrue(all(s["verification"] for s in self.data["sources"]))
        raw=json.dumps(self.data,ensure_ascii=False)
        self.assertNotIn("1000428575.jpg",raw)
        self.assertNotIn("drive.google.com",raw)

    def test_reject_unknown_source_actor_and_invented_date(self):
        original=atlas_db.read_json(ROOT/transition_cases.SOURCE)
        choices=[
            ("unresolved", lambda d:d["cases"][0]["records"][0]["sources"].append("TR99")),
            ("unknown-person", lambda d:d["cases"][0]["records"][0].__setitem__("person_id","person-fake")),
            ("bad-date", lambda d:d["cases"][0]["records"][0]["date"].__setitem__("value","1610-99-99")),
            ("false-historical-certainty",lambda d:d.__setitem__("historical_truth_verified_by_ci",True))
        ]
        for name,change in choices:
            with self.subTest(name=name):
                fake=copy.deepcopy(original)
                change(fake)
                with patch.object(transition_cases.atlas_db,"read_json",return_value=fake):
                    with self.assertRaises(ValueError):
                        transition_cases.load(ROOT,self.db)

    def test_spa_contract_and_js_syntax(self):
        js=(ROOT/"site/transition-view.js").read_text(encoding="utf-8")
        css=(ROOT/"site/site.css").read_text(encoding="utf-8")
        for snippet in ("fetch('./transition-cases.json'",
                        "atlas-transition-sheet",
                        "atlas-transition-source",
                        "atlas-transition-jump",
                        "atlas-transition-filter",
                        "atlas:route",
                        "slider.dispatchEvent(new Event('input'",
                        "aria-modal"):
            self.assertIn(snippet,js)
        self.assertIn(".atlas-transition-sheet[hidden]{display:none!important}",css)
        if shutil.which("node"):
            subprocess.run(["node","--check",str(ROOT/"site/transition-view.js")],
                           check=True,capture_output=True)

if __name__=="__main__":
    unittest.main()
