"""Coverage matrix contract: missing DATA ≠ historical absence of authority."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import unittest

from scripts import atlas_v2_coverage as coverage

ROOT=coverage.ROOT


class WorldAuthorityCoverage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=coverage.build()
        cls.cells={(x["year"],x["scope_id"]):x for x in cls.data["cells"]}

    def test_matrix_is_explicitly_research_limited(self):
        d=self.data
        self.assertEqual(d["schema_version"],"world-authority-coverage-v1")
        self.assertFalse(d["historical_truth_verified_by_ci"])
        self.assertFalse(d["worldwide_coverage_verified"])
        self.assertFalse(d["geographic_boundaries_verified"])
        self.assertEqual(d["years"],[1688,1788,1888])
        self.assertEqual(len(d["areas"]),7)
        self.assertEqual(len(d["cells"]),21)
        self.assertEqual((d["summary"]["partial_samples"],
                          d["summary"]["not_researched"]), (8,13))
        self.assertEqual(d["summary"]["documented_links"],24)

    def test_exact_sourced_observation_counts_only_for_sampled_years(self):
        expected=coverage.EXPECTED
        self.assertEqual(set(self.cells),
                         {(year,a) for year in coverage.YEARS for a in coverage.AREA_IDS})
        for (year,area),cell in self.cells.items():
            with self.subTest(year=year,area=area):
                count=expected.get(year,{}).get(area)
                if count is None:
                    self.assertEqual(cell["status"],"not_researched")
                    self.assertEqual(cell["edge_count"],0)
                    self.assertEqual(cell["node_count"],0)
                    self.assertEqual(cell["source_ids"],[])
                    self.assertEqual(cell["evidence"],[])
                else:
                    self.assertEqual(cell["status"],"partial_sample")
                    self.assertEqual(cell["edge_count"],count)
                    self.assertTrue(cell["source_ids"])
                    self.assertEqual(len(cell["evidence"]),count)
                self.assertEqual(sum(cell["dimension_counts"].values()),
                                 cell["edge_count"])

    def test_same_scope_japan_1688_1888_is_not_interpolated_to_1788(self):
        self.assertEqual(self.cells[1688,"jp"]["edge_count"],2)
        self.assertEqual(self.cells[1788,"jp"]["status"],"not_researched")
        self.assertEqual(self.cells[1888,"jp"]["edge_count"],4)
        self.assertEqual(self.cells[1788,"jp"]["source_ids"],[])

    def test_mughal_title_is_not_all_of_india_1688(self):
        self.assertEqual(self.cells[1688,"mughal"]["edge_count"],1)
        self.assertEqual(self.cells[1688,"india"]["status"],"not_researched")
        self.assertEqual(self.cells[1788,"india"]["edge_count"],5)
        self.assertEqual(self.cells[1788,"mughal"]["status"],"not_researched")

    def test_filtered_type_empty_is_not_empty_historical_region(self):
        q=self.cells[1788,"qing"]
        self.assertEqual(q["status"],"partial_sample")
        self.assertEqual(q["dimension_counts"]["diplomatic"],1)
        self.assertEqual(q["dimension_counts"]["military"],0)
        self.assertEqual(self.cells[1688,"eng"]["dimension_counts"]["military"],1)
        self.assertEqual(self.cells[1788,"india"]["dimension_counts"]["practical"],1)
        self.assertEqual(self.cells[1888,"jp"]["dimension_counts"]["institutional"],3)
        self.assertIn("не доказывает",self.data["methodology"]["dimension"])

    def test_scope_names_do_not_claim_modern_territorial_boundaries(self):
        self.assertEqual({a["id"] for a in self.data["areas"]},
                         {"eng","hre","mughal","india","jp","qing","et"})
        self.assertIn("неизменные границы",self.data["methodology"]["regions"])
        self.assertIn("НЕ свидетельство отсутствия",self.data["methodology"]["unobserved"])
        self.assertTrue(self.data["methodology"]["observed"])

    def test_each_cited_link_has_namespace_and_public_https(self):
        sources=self.data["sources"]
        for cell in self.data["cells"]:
            if cell["status"]=="not_researched":
                self.assertFalse(cell["source_ids"])
                continue
            for src in cell["source_ids"]:
                with self.subTest(cell=cell["id"],source=src):
                    self.assertIn(src,sources)
                    self.assertTrue(src.startswith("authority-"+str(cell["year"])+":"))
                    self.assertTrue(coverage.authority.source_url(sources[src]["url"]))
                    self.assertEqual(sources[src]["verification"],"reference_checked")
            for evidence in cell["evidence"]:
                self.assertTrue(evidence["caveat"])
                self.assertTrue(set(evidence["source_ids"])<=set(cell["source_ids"]))

    def test_source_ambiguity_same_short_id_across_years_is_separate(self):
        sources=self.data["sources"]
        self.assertIn("authority-1688:E01",sources)
        self.assertIn("authority-1888:E01",sources)
        self.assertNotEqual(sources["authority-1688:E01"]["url"],
                            sources["authority-1888:E01"]["url"])

    def test_distinct_events_stay_event_scoped_without_daily_co_rule(self):
        by_id={e["id"]:e for c in self.data["cells"] for e in c["evidence"]}
        self.assertEqual(by_id["e1688-william-arrival"]["meaning"],"event")
        self.assertEqual(by_id["e1888-cabinet-transition"]["meaning"],"event")
        self.assertEqual(by_id["i-e2"]["meaning"],"event")
        self.assertNotEqual(by_id["e1888-cabinet-transition"]["meaning"],
                            by_id["e1888-ito-cabinet"]["meaning"])
        self.assertIn("не доказывает",self.data["methodology"]["time"])

    def test_all_scoped_year_totals_are_source_derived(self):
        totals=self.data["summary"]["by_year"]
        self.assertEqual([totals[str(y)]["documented_links"] for y in coverage.YEARS],
                         [5,12,7])
        self.assertEqual([totals[str(y)]["partial_samples"] for y in coverage.YEARS],
                         [3,3,2])
        self.assertEqual([totals[str(y)]["not_researched"] for y in coverage.YEARS],
                         [4,4,5])

    def test_client_is_accessible_without_historical_facts_in_javascript(self):
        code=(ROOT/"site/world-coverage.js").read_text(encoding="utf-8")
        for token in ("world-authority-coverage.json","coverage-cell-button",
                      "data","aria-pressed","not_researched","partial_sample",
                      "worldwide_coverage_verified","popstate","history[push?"):
            self.assertIn(token,code)
        self.assertNotIn("innerHTML",code)
        self.assertNotIn("eval(",code)
        if shutil.which("node"):
            subprocess.run(["node","--check",str(ROOT/"site/world-coverage.js")],
                           check=True,capture_output=True)

    def test_does_not_change_v1_canonical_or_public_original(self):
        paths=[ROOT/"data/atlas/tenures.jsonl",
               ROOT/"data/atlas/sources.jsonl",
               ROOT/"schemas/atlas.sql",
               ROOT/"design/atlas-v2/authority-world-sample-1788.json",
               ROOT/"design/atlas-v2/authority-world-sample-1688.json",
               ROOT/"design/atlas-v2/authority-world-sample-1888.json"]
        before=[hashlib.sha256(x.read_bytes()).hexdigest() for x in paths]
        result=coverage.build()
        self.assertEqual(result,self.data)
        self.assertEqual(before,[hashlib.sha256(x.read_bytes()).hexdigest()
                                for x in paths])


if __name__=="__main__":
    unittest.main()
