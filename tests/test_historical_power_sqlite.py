"""HPM P2: exact sourced source-record crosswalks, NEVER historical truth tests."""
from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
import unittest

from scripts import historical_power_sqlite as hpm


class HistoricalPowerP2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn, cls.base = hpm.preview(hpm.ROOT)
        cls.out = hpm.report(cls.conn)
        cls.mapping = hpm.mapping()

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_real_source_sample_inventory_not_a_european_population(self):
        self.assertEqual(self.out["schema_version"], "hpm-derived-sqlite-p2-v1")
        self.assertIs(self.out["historical_truth_verified_by_ci"], False)
        self.assertIs(self.out["historical_region_wide_inference_supported"], False)
        self.assertIsNone(self.out["accession_mechanism_rates"])
        self.assertEqual(self.out["research_scope"]["unit"],
                         "normalized sourced relationship-event")
        self.assertEqual(self.out["research_scope"]["coverage"],
                         "partial_pilot_not_population")
        counts = self.out["counts"]
        self.assertEqual(counts["candidate_events"], 10)
        self.assertEqual(counts["reviewed_role_linkages"], 3)
        self.assertEqual(counts["candidate_only"], 7)
        self.assertEqual(counts["accession_mechanism_unknown"], 10)
        self.assertEqual(counts["classified_mechanisms"], 0)
        self.assertEqual(counts["relation_kinds"], {
            "succession": 5,
            "imperial_succession": 3,
            "regime_change": 1,
            "institutional_change": 1,
        })

    def test_identity_review_is_not_inheritance_or_violence_classification(self):
        for t in self.out["evidence"]:
            self.assertEqual(t["accession_mechanism"], "unknown")
            self.assertIn(t["review_status"], ("candidate", "reviewed_linkage"))
        self.assertEqual(sum(x["review_status"] == "reviewed_linkage"
                             for x in self.out["evidence"]), 3)

    def test_reuses_exact_existing_source_relationships(self):
        names = {x["relation_id"] for x in self.out["evidence"]}
        self.assertEqual(names, {
            "v2-p3-rel-dn-hre-change-1765",
            "v2-p3-rel-dn-france-change-1774",
            "v2-p3-rel-ex-pr-succ-1786",
            "v2-p3-rel-ex-pr-succ-1797",
            "v2-p3-rel-ex-es-succ-1788",
            "v2-p3-rel-ex-hab-succ-1790",
            "v2-p3-rel-ex-hab-succ-1792",
            "v2-p3-rel-ex-sw-succ-1792",
            "v2-p3-rel-ex-fr-revolution",
            "v2-p3-rel-ex-fr-1799",
        })
        self.assertEqual(len(set(x["id"] for x in self.out["evidence"])), 10)
        for t in self.out["evidence"]:
            self.assertEqual(len(t["original_observations"]), 1)
            self.assertTrue(t["original_observations"][0]["raw_sha256"])
            self.assertTrue(t["documentary_sources"])
            self.assertTrue(all(hpm.public_url(s["source_url"])
                                and s["source_namespace"] and s["pinpoint"]
                                for s in t["documentary_sources"]))

    def test_french_transfer_is_explicit_two_real_source_roles(self):
        t = next(x for x in self.out["evidence"] if
                 x["relation_id"] == "v2-p3-rel-dn-france-change-1774")
        self.assertEqual(t["event_year"], 1774)
        self.assertEqual(t["review_status"], "reviewed_linkage")
        self.assertEqual({(x["direction"], x["role_id"]) for x in t["role_links"]}, {
            ("outgoing", "v2-role-dn-fr-louis15"),
            ("incoming", "v2-role-dn-fr-louis16"),
        })
        self.assertTrue(any(x["source_native_id"] == "DN08"
                            and x["source_namespace"] == "world-dynasty"
                            for x in t["documentary_sources"]))
        self.assertTrue(t["role_documentary_sources"])
        self.assertEqual(t["accession_mechanism"], "unknown")

    def test_elective_hre_context_does_not_equal_inherited_german_states(self):
        t = next(x for x in self.out["evidence"] if
                 x["relation_id"] == "v2-p3-rel-dn-hre-change-1765")
        self.assertEqual(t["event_year"], 1765)
        self.assertEqual(t["kind"], "imperial_succession")
        self.assertEqual({x["role_id"] for x in t["role_links"]}, {
            "v2-role-dn-hre-francis", "v2-role-dn-hre-joseph"})
        self.assertEqual(t["accession_mechanism"], "unknown")
        self.assertIn("elective", t["role_links"][0]["caveat"])

    def test_institution_does_not_become_fake_person_or_new_monarch(self):
        t = next(x for x in self.out["evidence"] if
                 x["relation_id"] == "v2-p3-rel-ex-fr-1799")
        self.assertEqual(t["event_year"], 1799)
        self.assertEqual(t["kind"], "institutional_change")
        self.assertEqual({(x["direction"], x["role_id"]) for x in t["role_links"]}, {
            ("outgoing", "v2-role-ex-fr-directory"),
            ("incoming", "v2-role-ex-fr-consulate"),
        })
        role_ids = [x["role_id"] for x in t["role_links"]]
        for role_id in role_ids:
            role = self.conn.execute(
                "SELECT role_kind,person_id,institution_id FROM v2_roles WHERE id=?",
                (role_id,)).fetchone()
            self.assertEqual(role[0], "institutional")
            self.assertIsNone(role[1])
            self.assertIsNotNone(role[2])
        self.assertEqual(t["accession_mechanism"], "unknown")

    def test_unreviewed_candidates_do_not_gain_roles_by_year_proximity(self):
        for t in self.out["evidence"]:
            if t["review_status"] == "candidate":
                self.assertEqual(t["role_links"], [])
                self.assertEqual(t["role_documentary_sources"], [])
        t = next(x for x in self.out["evidence"] if
                 x["relation_id"] == "v2-p3-rel-ex-fr-revolution")
        self.assertEqual(t["review_status"], "candidate")
        self.assertEqual(t["event_year"], 1792)
        self.assertEqual(t["kind"], "regime_change")

    def test_readonly_in_memory_sqlite_preserves_version_and_foreign_keys(self):
        self.assertEqual(self.conn.execute("PRAGMA user_version").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        self.assertEqual(self.conn.execute("PRAGMA foreign_key_check").fetchall(), [])
        self.assertEqual(self.conn.execute("PRAGMA query_only").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("PRAGMA database_list").fetchone()[2], "")
        with self.assertRaises(sqlite3.OperationalError):
            self.conn.execute("INSERT INTO hpm_transfer_candidates(id) VALUES('bad')")

    def test_year_filter_has_honest_scoped_denominator(self):
        y = hpm.report(self.conn, 1774)
        self.assertEqual(y["counts"]["candidate_events"], 1)
        self.assertEqual(y["counts"]["reviewed_role_linkages"], 1)
        self.assertEqual(y["counts"]["accession_mechanism_unknown"], 1)
        self.assertEqual(y["research_scope"]["filter_event_year"], 1774)
        no_records = hpm.report(self.conn, 1200)
        self.assertEqual(no_records["counts"]["candidate_events"], 0)
        self.assertIsNone(no_records["accession_mechanism_rates"])
        with self.assertRaisesRegex(ValueError, "invalid filter year"):
            hpm.report(self.conn, -1)

    def test_mappings_reject_relabeling_and_unapproved_inference(self):
        def fail(changer, reason):
            doc = copy.deepcopy(self.mapping)
            changer(doc)
            with self.assertRaisesRegex(ValueError, reason):
                hpm.verify_manifest(self.conn, doc)
        fail(lambda d: d.update(historical_truth_verified_by_ci=True),
             "promote crosswalks")
        fail(lambda d: d.update(auto_classify_mechanism=True), "promote crosswalks")
        fail(lambda d: d["reviewed_links"][0].update(
            accession_mechanism="inheritance"), "unsupported fields")
        fail(lambda d: d["reviewed_links"][0].update(context_id="ctx-world-hre"),
             "pinned source-person-role crosswalk")
        fail(lambda d: d["reviewed_links"][0].update(
            outgoing_role_id="v2-role-dn-fr-louis16"), "pinned source-person-role crosswalk")
        fail(lambda d: d["reviewed_links"][0].update(
            review_dimension="primary_historical_verification"), "narrow evidence")
        fail(lambda d: d["reviewed_links"].pop(), "inventory changed")
        fail(lambda d: d["reviewed_links"].append(copy.deepcopy(d["reviewed_links"][0])),
             "inventory changed")

    def test_source_urls_cannot_be_private_or_credentials(self):
        for u in ("https://drive.google.com/file/d/private",
                  "https://token:secret@example.com/", "http://example.org/",
                  "https://example.org/?token=hidden", "https://localhost/secret",
                  "https://127.0.0.1/source", "https://169.254.169.254/latest",
                  "https://foo.localhost/path", "https://10.0.0.1/"):
            self.assertFalse(hpm.public_url(u))
        self.assertTrue(hpm.public_url("https://www.wikidata.org/wiki/Q1"))

    def test_snapshot_inputs_have_not_changed_after_preview(self):
        # Running this new module does not write canonical input files.
        files = ("data/atlas/tenures.jsonl", "data/atlas/events.jsonl",
                 "schemas/atlas.sql", "docs/SCHEMA_V2_RFC.md",
                 str(hpm.MAPPING_FILE))
        before = {p:hashlib.sha256((hpm.ROOT / p).read_bytes()).hexdigest()
                  for p in files}
        other = hpm.build(hpm.ROOT, 1799)
        self.assertEqual(other["counts"]["candidate_events"], 1)
        after = {p:hashlib.sha256((hpm.ROOT / p).read_bytes()).hexdigest()
                 for p in files}
        self.assertEqual(before, after)

    def test_output_is_deterministic_and_source_traceable(self):
        self.assertEqual(self.out, hpm.report(self.conn))
        for t in self.out["evidence"]:
            self.assertTrue(t["assertion_id"].startswith("v2-p3-claim-rel-"))
            for src in t["documentary_sources"]:
                self.assertNotIn("drive.google.com", src["source_url"])
                self.assertTrue(src["source_title"])
            for row in t["role_documentary_sources"]:
                self.assertTrue(row["role_assertion_id"].startswith("v2-assert-"))
                self.assertTrue(row["pinpoint"])


if __name__ == "__main__":
    unittest.main()
