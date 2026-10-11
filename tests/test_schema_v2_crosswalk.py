"""Regression contract for an explicit, read-only v2 identity crosswalk."""
from __future__ import annotations

import copy
import hashlib
import unittest
from pathlib import Path

from scripts import atlas_v2_crosswalk as m

ROOT = Path(__file__).resolve().parents[1]


class CrosswalkContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = m.load_snapshot(ROOT)
        cls.snapshot["root"] = ROOT
        cls.preview, cls.report = m.in_memory_preview(cls.snapshot)

    @classmethod
    def tearDownClass(cls):
        cls.preview.close()

    def merged(self, origin, native_id):
        row = self.preview.execute(
            "SELECT context_id FROM v2_context_refs WHERE origin=? AND native_id=?",
            (origin,native_id),
        ).fetchone()
        self.assertIsNotNone(row)
        return row[0]

    def test_inventory_comes_from_existing_source_files(self):
        result = self.report
        self.assertEqual(result["canonical_contexts"],6)
        self.assertEqual(result["world_contexts"],13)
        self.assertEqual(result["unified_contexts"],18)
        self.assertEqual(result["context_refs"],19)
        self.assertEqual(result["world_people"],28)
        self.assertEqual(result["linked_people"],4)
        self.assertEqual(result["unresolved_people"],24)
        self.assertEqual(result["namespaced_sources"],237)
        self.assertFalse(result["historical_truth_verified_by_ci"])
        self.assertEqual(result["status"],"draft_not_canonical")

    def test_only_one_explicit_equivalence_across_world_and_canon(self):
        self.assertEqual(self.report["explicit_context_equivalences"],
                         [{"canonical":"empire","world":"ru"}])
        self.assertEqual(self.merged("atlas-state-v1","empire"),
                         self.merged("world-pilots-1762-1800","ru"))
        canonical_ids={p[0] for p in self.preview.execute(
            "SELECT context_id FROM v2_context_refs WHERE origin='atlas-state-v1'")}
        foreign_ids={p[0] for p in self.preview.execute(
            "SELECT context_id FROM v2_context_refs WHERE origin='world-pilots-1762-1800'")}
        self.assertEqual(canonical_ids & foreign_ids,{self.merged("atlas-state-v1","empire")})

    def test_critical_entities_must_not_merge(self):
        for left_origin,left_id,right_origin,right_id in [
            ("world-pilots-1762-1800","fr","world-pilots-1762-1800","frrep"),
            ("world-pilots-1762-1800","gb","world-pilots-1762-1800","han"),
            ("world-pilots-1762-1800","hab","world-pilots-1762-1800","hre"),
            ("atlas-state-v1","tsardom","atlas-state-v1","empire"),
            ("atlas-state-v1","rsfsr","atlas-state-v1","ussr"),
        ]:
            with self.subTest(left=left_id,right=right_id):
                self.assertNotEqual(self.merged(left_origin,left_id),
                                    self.merged(right_origin,right_id))

    def test_type_guardrails_for_hre_habsburg_birthplace(self):
        expected={
            "hre":"elective_office_context",
            "hab":"composite_monarchy",
            "meck":"birthplace_context",
            "fr":"polity_regime",
            "frrep":"polity_regime",
        }
        for wid,kind in expected.items():
            cid=self.merged("world-pilots-1762-1800",wid)
            self.assertEqual(self.preview.execute(
                "SELECT kind FROM v2_contexts WHERE id=?", (cid,)).fetchone()[0],kind)

    def test_unresolved_people_remain_unresolved(self):
        linked = {r[0]:r[1] for r in self.preview.execute(
            "SELECT native_id,canonical_person_id FROM v2_external_people "
            "WHERE resolution='linked'")}
        self.assertEqual(set(linked),{"ru-peter3","ru-catherine2","ru-elizabeth","ru-paul1"})
        self.assertTrue(all(linked.values()))
        self.assertIsNone(self.preview.execute(
            "SELECT canonical_person_id FROM v2_external_people "
            "WHERE native_id='fr-louis15'").fetchone()[0])
        self.assertIsNone(self.preview.execute(
            "SELECT canonical_person_id FROM v2_external_people "
            "WHERE native_id='gb-george3'").fetchone()[0])
        self.assertEqual(self.preview.execute(
            "SELECT COUNT(*) FROM v2_external_people WHERE resolution='unresolved'"
        ).fetchone()[0],24)

    def test_tenure_links_are_existing_person_tenure_pairs(self):
        origin={p["id"]:p for p in self.snapshot["canonical"]["people"]}
        tenures={t["id"]:t for t in self.snapshot["canonical"]["tenures"]}
        for row in self.snapshot["crosswalk"]["people"]:
            if row["resolution"] == "linked":
                with self.subTest(id=row["world_id"]):
                    self.assertIn(row["canonical_person_id"],origin)
                    self.assertEqual(
                        tenures[row["canonical_tenure_id"]]["person_id"],
                        row["canonical_person_id"])

    def test_sources_are_namespaced_and_not_inferred_equal(self):
        self.assertEqual(self.preview.execute(
            "SELECT COUNT(*) FROM v2_sources WHERE canonical_source_id IS NOT NULL"
        ).fetchone()[0],194)
        self.assertEqual(self.preview.execute(
            "SELECT COUNT(*) FROM v2_sources WHERE canonical_source_id IS NULL"
        ).fetchone()[0],43)
        self.assertEqual(self.preview.execute(
            "SELECT COUNT(*) FROM v2_sources WHERE origin='world-coverage'"
        ).fetchone()[0],2)
        self.assertEqual(self.preview.execute(
            "SELECT COUNT(*) FROM v2_sources WHERE origin='world-footprints'"
        ).fetchone()[0],4)

    def test_preview_only_adds_v2_metadata_not_historical_claims(self):
        self.assertEqual(self.preview.execute("PRAGMA user_version").fetchone()[0],1)
        self.assertEqual(self.preview.execute("PRAGMA integrity_check").fetchone()[0],"ok")
        self.assertEqual(self.preview.execute("PRAGMA foreign_key_check").fetchall(),[])
        for table in ("v2_assertions","v2_roles","v2_house_affiliations",
                      "v2_context_relations","v2_territorial_observations"):
            self.assertEqual(self.preview.execute(
                "SELECT COUNT(*) FROM "+table).fetchone()[0],0)
        self.assertEqual(self.preview.execute(
            "SELECT COUNT(*) FROM people").fetchone()[0],83)
        self.assertEqual(self.preview.execute(
            "SELECT COUNT(*) FROM provenance").fetchone()[0],150)

    def test_no_normalization_from_historical_title_or_dynasty(self):
        network = self.snapshot["world"]["dynasty-1762-1780.json"]
        georges = [r for r in network["roles"] if r["person_id"]=="gb-george3"]
        self.assertEqual({r["polity_id"] for r in georges},{"gb","han"})
        mapping = {p["world_id"]:p for p in self.snapshot["crosswalk"]["people"]}
        self.assertEqual(mapping["gb-george3"]["resolution"],"unresolved")
        families = self.snapshot["world"]["dynasty-footprints-1762-1800.json"]["families"]
        self.assertIn("fr-louis16",
                      {mbr["person_id"] for fam in families for mbr in fam["members"]
                       if fam["id"]=="bourbon"})
        self.assertEqual(mapping["fr-louis16"]["resolution"],"unresolved")

    def test_false_canonical_person_link_is_rejected(self):
        wrong = copy.deepcopy(self.snapshot)
        row = next(p for p in wrong["crosswalk"]["people"] if p["world_id"]=="fr-louis15")
        row.update(resolution="linked",
                   canonical_person_id="person-a4d0a7000e965592",
                   canonical_tenure_id="tenure-r12",
                   basis="explicit-existing-canonical-person-id")
        with self.assertRaisesRegex(ValueError,"unapproved|unresolved"):
            m.validate(wrong)

    def test_false_context_merge_is_rejected(self):
        wrong = copy.deepcopy(self.snapshot)
        france=next(c for c in wrong["crosswalk"]["contexts"]
                    if c["id"]=="ctx-world-fr")
        ru=next(c for c in wrong["crosswalk"]["contexts"]
                if c["id"]=="ctx-empire")
        ru["refs"].extend(france["refs"])
        france["refs"]=[]
        with self.assertRaises(ValueError):
            m.validate(wrong)

    def test_missing_source_is_rejected(self):
        wrong = copy.deepcopy(self.snapshot)
        wrong["world"]["dynasty-1762-1780.json"]["roles"][0]["source_ids"]=["NO-SUCH-SOURCE"]
        with self.assertRaisesRegex(ValueError,"missing source"):
            m.validate(wrong)

    def test_source_namespace_collision_rejected(self):
        wrong = copy.deepcopy(self.snapshot)
        wrong["crosswalk"]["source_namespaces"]["1762.json"]="world-dynasty"
        with self.assertRaisesRegex(ValueError,"share a namespace"):
            m.validate(wrong)

    def test_draft_cannot_claim_historical_truth(self):
        wrong = copy.deepcopy(self.snapshot)
        wrong["crosswalk"]["historical_truth_verified_by_ci"]=True
        with self.assertRaisesRegex(ValueError,"historical"):
            m.validate(wrong)

    def test_no_existing_data_changed_by_second_validation(self):
        paths=[
            ROOT/"data/atlas/states.jsonl",
            ROOT/"data/atlas/tenures.jsonl",
            ROOT/"data/atlas/provenance.jsonl",
            ROOT/"data/atlas/world-pilots/1762.json",
            ROOT/"data/atlas/world-pilots/dynasty-1762-1780.json",
        ]
        before=[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
        self.assertEqual(m.validate(self.snapshot),self.report)
        after=[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
        self.assertEqual(before,after)


if __name__ == "__main__":
    unittest.main()
