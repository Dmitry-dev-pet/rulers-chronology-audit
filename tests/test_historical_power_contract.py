"""Historical Power Model P1: contract tests, never historical verification."""
from __future__ import annotations

import copy
import hashlib
import json
import unittest

from scripts import historical_power_contract as hpm


class SyntheticPowerTransitionContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sample = hpm.fixture()
        cls.by_id = {t["id"]: t for t in cls.sample["transitions"]}

    def change_rejected(self, mutation, pattern):
        doc = copy.deepcopy(self.sample)
        mutation(doc)
        with self.assertRaisesRegex(ValueError, pattern):
            hpm.validate(doc)

    def test_is_test_only_and_does_not_attest_history(self):
        doc = self.sample
        self.assertEqual(doc["schema_version"], "hpm-synthetic-v1")
        self.assertTrue(doc["synthetic_only"])
        self.assertIs(doc["historical_truth_verified_by_ci"], False)
        self.assertEqual(doc["scope"], {
            "id": "fixture:scope", "unit": "transition", "coverage": "synthetic_only"})
        self.assertTrue(all(a["id"].startswith("fixture:") for a in doc["actors"]))
        self.assertEqual(len(doc["transitions"]), 7)

    def test_same_year_does_not_equate_two_events_or_calendars(self):
        seq = self.by_id["fixture:sequence"]
        self.assertEqual(seq["event_refs"], ["fixture:event-exit", "fixture:event-entry"])
        events = {e["id"]: e for e in self.sample["events"]}
        a, b = (events[x]["date"] for x in seq["event_refs"])
        self.assertEqual((a["value"], a["calendar"]), ("1762-01-02", "julian"))
        self.assertEqual((b["value"], b["calendar"]), ("1762-03-01", "gregorian"))
        self.assertNotEqual(a, b)

    def test_two_new_office_holders_are_not_one_actor(self):
        co = self.by_id["fixture:co-regents"]
        self.assertEqual(len(co["incoming_role_refs"]), 2)
        self.assertEqual(co["outgoing_role_refs"], [])
        self.assertEqual(co["absence"]["outgoing"], "unknown")
        actors = [p["actor_id"] for p in co["participants"]]
        self.assertEqual(actors, ["fixture:actor-c", "fixture:actor-d"])

    def test_one_person_can_have_two_offices_in_separate_contexts(self):
        uni = self.by_id["fixture:personal-union"]
        roles = {r["id"]: r for r in self.sample["roles"]}
        entries = [roles[r] for r in uni["incoming_role_refs"]]
        self.assertEqual(len({r["actor_id"] for r in entries}), 1)
        self.assertEqual({r["context_id"] for r in entries},
                         {"fixture:alpha", "fixture:beta"})
        self.assertEqual(hpm.claims_for(self.sample, uni["id"], "dynastic_continuity")
                         ["state"], "not_studied")

    def test_collective_institution_is_not_a_person(self):
        roles = {r["id"]: r for r in self.sample["roles"]}
        actors = {a["id"]: a for a in self.sample["actors"]}
        inst = self.by_id["fixture:institutional"]
        actor = actors[roles[inst["incoming_role_refs"][0]]["actor_id"]]
        self.assertEqual(actor["kind"], "institution")
        self.assertEqual(roles[inst["incoming_role_refs"][0]]["kind"], "institutional")
        self.assertEqual(hpm.claims_for(self.sample, inst["id"],
                                        "accession_mechanism")["values"],
                         ["institutional_reform"])

    def test_competing_classifications_are_preserved_without_winner(self):
        outcome = hpm.claims_for(self.sample, "fixture:contested", "accession_mechanism")
        self.assertEqual(outcome["state"], "competing_claims")
        self.assertEqual(outcome["values"], ["coup", "election"])
        self.assertEqual(len(outcome["claim_ids"]), 2)
        self.assertEqual(len(outcome["source_refs"]), 2)
        self.assertTrue(all(e["pinpoint"] for e in outcome["source_refs"]))

    def test_not_studied_unknown_and_observed_are_distinct(self):
        self.assertEqual(hpm.claims_for(self.sample, "fixture:co-regents", "violence")
                         ["state"], "not_studied")
        self.assertEqual(hpm.claims_for(self.sample, "fixture:unknown", "accession_mechanism")
                         ["state"], "unknown")
        self.assertEqual(hpm.claims_for(self.sample, "fixture:contested", "violence")
                         ["state"], "classified")

    def test_transition_can_have_no_personal_transfer_if_institutional(self):
        item = self.by_id["fixture:no-roles"]
        self.assertEqual(item["incoming_role_refs"], [])
        self.assertEqual(item["outgoing_role_refs"], [])
        self.assertEqual(item["absence"], {
            "outgoing": "institutional_change", "incoming": "institutional_change"})
        self.assertEqual(hpm.claims_for(self.sample, item["id"], "accession_mechanism")
                         ["state"], "not_studied")

    def test_missing_roles_cannot_be_silently_explained_as_no_ruler(self):
        self.change_rejected(lambda d: d["transitions"][1]["absence"].update(outgoing=None),
                             "empty outgoing roles require reason")
        self.change_rejected(lambda d: d["transitions"][0]["absence"].update(incoming="unknown"),
                             "populated roles require null")

    def test_orphan_and_wrong_scope_links_are_rejected(self):
        self.change_rejected(lambda d: d["transitions"][0]["incoming_role_refs"]
                             .__setitem__(0, "fixture:missing"), "dangling reference")
        self.change_rejected(lambda d: d["roles"][0].update(actor_id="fixture:missing"),
                             "actor/context reference missing")
        self.change_rejected(lambda d: d["transitions"][0].update(scope_ref="fixture:other"),
                             "research scope")
        self.change_rejected(lambda d: d["transitions"][0]["context_refs"]
                             .__setitem__(0, "fixture:beta"), "role context")

    def test_claims_require_precise_source_and_locator(self):
        self.change_rejected(lambda d: d["transitions"][0]["classification_claims"][0]
                             .update(source_refs=[]), "source provenance")
        self.change_rejected(lambda d: d["transitions"][0]["classification_claims"][0]
                             ["source_refs"][0].update(source_id="fixture:missing"),
                             "source.?pinpoint")
        self.change_rejected(lambda d: d["transitions"][0]["classification_claims"][0]
                             ["source_refs"][0].update(pinpoint=""), "source.?pinpoint")

    def test_rejects_auto_inference_and_false_primary_verification(self):
        self.change_rejected(lambda d: d["transitions"][0]["classification_claims"][0]
                             .update(verification="primary_checked"), "historical verification")
        self.change_rejected(lambda d: d["transitions"][0].update(real_ruler=True),
                             "required fields differ")
        self.change_rejected(lambda d: d.update(historical_truth_verified_by_ci=True),
                             "synthetic-only")
        self.change_rejected(lambda d: d.update(synthetic_only=False), "synthetic-only")

    def test_rejects_bad_actor_type_and_personified_institution(self):
        self.change_rejected(lambda d: d["actors"][0].update(kind="government"), "invalid kind")
        self.change_rejected(lambda d: d["roles"][5].update(kind="sovereign"),
                             "institution cannot")
        self.change_rejected(lambda d: d["transitions"][3]["participants"][1]
                             .update(actor_id="fixture:actor-a"), "role occupant")

    def test_rejects_unattributed_or_invalid_classification(self):
        self.change_rejected(lambda d: d["transitions"][0]["classification_claims"][0]
                             .update(value="always_peaceful"), "unsupported classification")
        self.change_rejected(lambda d: d["transitions"][0]["classification_claims"][0]
                             .update(confidence=0.97), "required fields differ")
        self.change_rejected(lambda d: d["transitions"][0]["classification_claims"][0]
                             .update(dimension="real_ruler"), "unsupported classification")

    def test_preserves_original_calendar_precision_and_rejects_impossible_days(self):
        self.change_rejected(lambda d: d["events"][0]["date"].update(precision="year"),
                             "precision or year")
        self.change_rejected(lambda d: d["events"][0]["date"].update(calendar="autoconverted"),
                             "precision/calendar")
        self.change_rejected(lambda d: d["events"][0]["date"].update(value="1762-02-30"),
                             "impossible day")
        self.change_rejected(lambda d: d["events"][0]["date"].update(value="0000-01-01"),
                             "precision or year")
        j = copy.deepcopy(self.sample)
        j["events"][0]["date"].update(value="1700-02-29", calendar="julian")
        hpm.validate(j)
        j["events"][0]["date"]["calendar"] = "gregorian"
        with self.assertRaisesRegex(ValueError, "impossible day"):
            hpm.validate(j)

    def test_duplicate_identity_and_unsupported_undated_role_free_event(self):
        self.change_rejected(lambda d: d["roles"][0].update(id="fixture:alpha-b"), "duplicate ID")
        self.change_rejected(lambda d: d["transitions"][6].update(
            event_refs=["fixture:event-unknown"]), "institutional event")

    def test_input_not_modified_by_validation(self):
        doc = copy.deepcopy(self.sample)
        before = hashlib.sha256(json.dumps(doc, sort_keys=True).encode()).hexdigest()
        self.assertIs(hpm.validate(doc), doc)
        hpm.claims_for(doc, "fixture:contested", "accession_mechanism")
        after = hashlib.sha256(json.dumps(doc, sort_keys=True).encode()).hexdigest()
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
