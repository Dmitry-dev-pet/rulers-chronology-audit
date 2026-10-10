"""Jurisdiction evidence distinguishes local action, occupation, and mere claims."""
import copy
import json
import shutil
import subprocess
import unittest
from unittest.mock import patch

from scripts import atlas_db, transition_cases

ROOT = atlas_db.ROOT


class JurisdictionResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.atlas = atlas_db.load(ROOT)
        cls.data = transition_cases.load(ROOT, cls.atlas)
        cls.cases = {case["id"]: case for case in cls.data["cases"]}

    def test_places_are_local_evidence_not_political_border_polygons(self):
        case_a = self.cases["smuta-1598-1613"]
        case_b = self.cases["ussr-1991"]
        self.assertEqual(len(case_a["territorial_evidence"]), 15)
        self.assertEqual(len(case_b["territorial_evidence"]), 9)
        self.assertEqual(sum(len(c["territorial_evidence"]) for c in self.data["cases"]), 24)
        for case in self.data["cases"]:
            self.assertIn("не реконструированы", case["geography_policy"])
            event_ids = {r["id"] for r in case["records"]}
            for p in case["territorial_evidence"]:
                self.assertIs(p["geometry_verified"], False)
                self.assertFalse(set(p) & transition_cases.FORBIDDEN_GEOMETRY_KEYS)
                self.assertTrue(set(p["related_event_ids"]) <= event_ids)
                self.assertTrue(p["sources"])
                self.assertIn(p["nature"], transition_cases.GEO_NATURES)
                self.assertIn(p["place_kind"], transition_cases.GEO_PLACE_KINDS)
                self.assertIn(p["verification"], transition_cases.VERIFICATIONS)
                self.assertIn(p["confidence"], transition_cases.CONFIDENCES)
                atlas_db.validate_date(p["date"])

    def test_original_claim_in_charter_not_turned_into_control_of_smolensk(self):
        site = next(p for p in self.cases["smuta-1598-1613"]["territorial_evidence"]
                    if p["id"] == "local-smuta-severian-claim-1608")
        self.assertEqual(site["nature"], "claim")
        self.assertEqual(site["date"]["calendar"], "julian")
        self.assertIn("Смоленск", site["place"])
        self.assertIn("не свидетельствует", site["limitation"])
        self.assertEqual(site["sources"], ["TJ02"])
        self.assertFalse(site["geometry_verified"])

    def test_same_city_can_have_different_authority_over_time(self):
        observations = self.cases["smuta-1598-1613"]["territorial_evidence"]
        self.assertTrue(any("Ярославль" in p["place"] and p["date"]["value"] == "1608"
                            for p in observations))
        self.assertTrue(any("Ярославль" in p["place"] and p["date"]["value"] == "1612-04"
                            for p in observations))
        self.assertTrue(any(p["id"] == "local-smuta-nizhny-resistance-1608" and
                            "нельзя изображать" in p["limitation"] for p in observations))
        moscow=[p for p in observations if p["place"].startswith("Москва")]
        self.assertGreaterEqual(len(moscow),3)
        self.assertTrue(any(p["nature"]=="military" for p in moscow))

    def test_1991_republics_not_assumed_under_single_union_control(self):
        data = {p["id"]:p for p in self.cases["ussr-1991"]["territorial_evidence"]}
        self.assertEqual(data["local-ussr-rsfsr-decree-aug19"]["nature"], "law")
        self.assertEqual(data["local-ussr-rsfsr-decree-aug19"]["date"]["value"],"1991-08-19")
        self.assertIn("TJ08",data["local-ussr-rsfsr-decree-aug19"]["sources"])
        self.assertEqual(data["local-ussr-ukraine-independence-aug24"]["date"]["value"],"1991-08-24")
        self.assertIn("TJ09",data["local-ussr-ukraine-independence-aug24"]["sources"])
        self.assertEqual(data["local-ussr-ukraine-conditional-sep12"]["date"]["value"],"1991-09-12")
        self.assertIn("TJ10",data["local-ussr-ukraine-conditional-sep12"]["sources"])
        self.assertEqual(data["local-ussr-union-law-sep05"]["place_kind"], "union_level")
        self.assertIn("TJ11",data["local-ussr-union-law-sep05"]["sources"])
        self.assertTrue(all("не" in p["limitation"].lower() for p in data.values()))
        self.assertFalse(any(p.get("geometry_verified") is True for p in data.values()))

    def test_1991_law_filter_count_and_stable_controls(self):
        records = self.cases["ussr-1991"]["territorial_evidence"]
        counts = {nature: sum(p["nature"] == nature for p in records)
                  for nature in transition_cases.GEO_NATURES}
        self.assertEqual(counts["law"], 7)
        self.assertEqual(counts["military"], 1)
        self.assertEqual(counts["practice"], 1)
        self.assertEqual(counts["claim"], 0)
        js = (ROOT/"site/transition-view.js").read_text(encoding="utf-8")
        self.assertIn("button.dataset.filter = kind", js)
        self.assertIn("peer.dataset.filter === kind", js)
        self.assertIn("tabs.querySelectorAll('button[data-filter]')", js)
        filter_handler = js.split("button.dataset.filter = kind", 1)[1].split("tabs.appendChild(button)", 1)[0]
        self.assertNotIn("renderFilters();", filter_handler)

    def test_invalid_polygons_false_provenance_and_orphan_events_rejected(self):
        input_data=atlas_db.read_json(ROOT / transition_cases.SOURCE)
        changes=[
          lambda d:d["cases"][0]["territorial_evidence"][0].__setitem__(
              "polygon", [[1.0,2.0],[2.0,3.0],[1.0,2.0]]),
          lambda d:d["cases"][0]["territorial_evidence"][0].__setitem__("geometry_verified", True),
          lambda d:d["cases"][0]["territorial_evidence"][0].__setitem__("sources",["UNKNOWN"]),
          lambda d:d["cases"][0]["territorial_evidence"][0].__setitem__("related_event_ids",["smuta-invented"]),
          lambda d:d["cases"][0]["territorial_evidence"][0]["date"].__setitem__("value","1608-13-01"),
        ]
        for change in changes:
            with self.subTest(change=changes.index(change)):
                modified = copy.deepcopy(input_data)
                change(modified)
                with patch.object(transition_cases.atlas_db,"read_json",return_value=modified):
                    with self.assertRaises(ValueError):
                        transition_cases.load(ROOT,self.atlas)

    def test_frontend_supports_geography_tab_source_links_and_no_border_warning(self):
        js=(ROOT/"site/transition-view.js").read_text(encoding="utf-8")
        css=(ROOT/"site/site.css").read_text(encoding="utf-8")
        for snippet in ("География власти", "territorial_evidence",
                        "selected.geography_policy", "Не доказывает: ",
                        "hrefs(refs, record)", "viewMode = mode",
                        "atlas-transition-section", "dateLabel(record)"):
            self.assertIn(snippet, js)
        self.assertIn("точные границы не реконструированы",js)
        self.assertIn(".atlas-transition-section[aria-pressed=\"true\"]",css)
        self.assertIn(".atlas-geo-disclaimer",css)
        if shutil.which("node"):
            subprocess.run(["node","--check",str(ROOT/"site/transition-view.js")],
                           check=True,capture_output=True)

if __name__=="__main__":
    unittest.main()
