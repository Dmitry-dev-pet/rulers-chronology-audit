"""HPM P3: opt-in Pages projection is derived and source-qualified, not canon."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import unittest

from scripts import historical_power_pages as pages
from scripts import historical_power_sqlite as p2


class HistoricalPowerP3(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = pages.projection()
        cls.source = p2.build()

    def test_counts_derive_from_same_p2_denominator(self):
        d = self.data
        self.assertEqual(d["schema_version"], "hpm-pages-p3-v1")
        self.assertIs(d["historical_truth_verified_by_ci"], False)
        self.assertIs(d["historical_region_wide_inference_supported"], False)
        self.assertIs(d["geographic_borders_verified"], False)
        self.assertIsNone(d["accession_mechanism_rates"])
        self.assertEqual(d["sample"]["years"], [1762, 1800])
        self.assertEqual(d["sample"]["unit"],
                         "normalized sourced relationship-event")
        self.assertEqual(d["sample"]["coverage"],
                         "partial_pilot_not_population")
        self.assertEqual(d["counts"], self.source["counts"])
        self.assertEqual(len(d["events"]), 10)
        self.assertEqual({e["id"] for e in d["events"]},
                         {e["id"] for e in self.source["evidence"]})
        self.assertEqual(sum(bool(e["roles"]) for e in d["events"]), 3)

    def test_every_experiment_is_source_qualified(self):
        for e in self.data["events"]:
            with self.subTest(id=e["id"]):
                self.assertEqual(e["year_resolution"], "year_index_only")
                self.assertEqual(e["accession_mechanism"], "unknown")
                self.assertTrue(e["assertion"]["statement"])
                self.assertEqual(e["assertion"]["id"],
                                 next(x for x in self.source["evidence"]
                                      if x["id"] == e["id"])["assertion_id"])
                self.assertTrue(e["sources"])
                self.assertTrue(e["raw_observations"])
                self.assertEqual(len(e["raw_observations"]), 1)
                for obs in e["raw_observations"]:
                    self.assertEqual(len(obs["raw_sha256"]), 64)
                for s in e["sources"]:
                    self.assertTrue(p2.public_url(s["source_url"]))
                    self.assertTrue(s["source_namespace"])
                    self.assertTrue(s["source_native_id"])
                    self.assertTrue(s["pinpoint"])

    def test_roles_are_explicitly_linked_never_guessed(self):
        expected = {
            "v2-p3-rel-dn-france-change-1774",
            "v2-p3-rel-dn-hre-change-1765",
            "v2-p3-rel-ex-fr-1799",
        }
        actual = {e["relation_id"] for e in self.data["events"] if e["roles"]}
        self.assertEqual(actual, expected)
        for event in self.data["events"]:
            if event["relation_id"] not in expected:
                self.assertEqual(event["roles"], [])
                self.assertEqual(event["review_status"], "candidate")
                continue
            self.assertEqual(event["review_status"], "reviewed_linkage")
            self.assertEqual({r["direction"] for r in event["roles"]},
                             {"outgoing", "incoming"})
            for r in event["roles"]:
                self.assertTrue(r["actor_label"])
                self.assertTrue(r["context_label"])
                self.assertTrue(r["sources"])
                self.assertEqual(r["review_dimension"],
                                 "source_record_role_identity_only")
                for s in r["sources"]:
                    self.assertTrue(p2.public_url(s["source_url"]))
                    self.assertEqual(s["role_id"], r["role_id"])
                    self.assertEqual(s["direction"], r["direction"])
        french_republic = next(e for e in self.data["events"]
                               if e["relation_id"] == "v2-p3-rel-ex-fr-1799")
        self.assertTrue(all(r["role_kind"] == "institutional"
                            for r in french_republic["roles"]))

    def test_safety_and_determinism(self):
        raw = json.dumps(self.data, ensure_ascii=False)
        self.assertNotIn("drive.google.com", raw)
        self.assertNotIn("docs.google.com", raw)
        self.assertNotIn("1000428575.jpg", raw)
        self.assertNotIn("ethnic_origin", raw)
        again = pages.projection()
        self.assertEqual(
            hashlib.sha256(raw.encode()).hexdigest(),
            hashlib.sha256(json.dumps(again, ensure_ascii=False).encode()).hexdigest())

    def test_frontend_enforces_gate_and_no_untrusted_markup(self):
        js = pages.ROOT / "site/historical-power-lab.js"
        css = pages.ROOT / "site/historical-power-lab.css"
        self.assertTrue(css.is_file())
        code = js.read_text(encoding="utf-8")
        for keyword in ("hpm-pilot.json", "hpmYear", "hpmCtx", "hpmLink",
                        "hpm-pages-p3-v1", "aria-modal", "historical_truth_verified_by_ci",
                        "source_namespace", "raw_observations", "history.pushState",
                        "hpm=pilot"):
            self.assertIn(keyword, code)
        self.assertNotIn("innerHTML", code)
        self.assertNotIn("eval(", code)
        if shutil.which("node"):
            subprocess.run(["node", "--check", str(js)], check=True,
                           capture_output=True)


if __name__ == "__main__":
    unittest.main()
