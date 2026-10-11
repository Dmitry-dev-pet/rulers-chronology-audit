"""Offline tests for read-only Wikidata synchronization and no-fuzzy-join contract."""
import json
import tempfile
import unittest
from pathlib import Path
from scripts import wikidata_sync as wd


def stamp(value, calendar, precision=11):
    return {"snaktype": "value", "datavalue": {
        "type": "time", "value": {
            "time": value, "calendarmodel": calendar,
            "precision": precision, "before": 0, "after": 0, "timezone": 0,
        }}}


def entity_value(qid):
    return {"snaktype": "value", "datavalue": {
        "type": "wikibase-entityid", "value": {"id": qid}}}


class FakeAtlas(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        p = self.root / "data/atlas/people"
        p.mkdir(parents=True)
        (p / "p1.json").write_text(json.dumps({
            "id": "p1", "name": "Павел I", "aliases": [],
            "external_ids": {"wikidata": "Q15189"},
        }), encoding="utf8")
        (p / "p2.json").write_text(json.dumps({
            "id": "p2", "name": "Другой человек", "aliases": [],
            "external_ids": {},
        }), encoding="utf8")
        base = self.root / "data/atlas"
        (base / "person_facts.jsonl").write_text(json.dumps({
            "id": "f1", "person_id": "p1", "kind": "birth",
            "value": {"value": "1700-01-01", "calendar": "julian",
                      "precision": "day"},
        }) + "\n", encoding="utf8")
        w = base / "world-pilots"
        w.mkdir()
        (w / "1762.json").write_text(json.dumps({"persons": [
            {"id": "world-p1", "canonical_person_id": "p1", "name": None},
            {"id": "world-new", "name": "Павел I"},
        ]}), encoding="utf8")
        (w / "dynasty-1762-1780.json").write_text(
            json.dumps({"additional_persons": [
                {"id": "world-new", "name": "Павел I"}]}), encoding="utf8")
        (w / "extension-1781-1800.json").write_text(
            json.dumps({"additional_persons": []}), encoding="utf8")

    def api(self, params):
        if params["action"] == "wbsearchentities":
            return {"search": [
                {"id": "Q999", "label": params["search"],
                 "description": "unverified candidate"}]}
        assert params["action"] == "wbgetentities"
        return {"entities": {"Q15189": {
            "id": "Q15189", "lastrevid": 12,
            "labels": {"ru": {"value": "Павел I"}},
            "claims": {
                "P569": [
                    {"id": "Q15189$valid", "rank": "normal",
                     "mainsnak": stamp("+1700-01-01T00:00:00Z",
                                       "http://www.wikidata.org/entity/Q1985786"),
                     "references": [{"hash": "ref-hash", "snaks": {
                         "P248": [entity_value("Q42")],
                         "P854": [{"snaktype": "value", "datavalue":
                                   {"type": "string",
                                    "value": "https://example.org/archive"}}],
                     }}]},
                    {"id": "Q15189$old", "rank": "deprecated",
                     "mainsnak": stamp("+1701-01-01T00:00:00Z",
                                       "http://www.wikidata.org/entity/Q1985786")},
                ],
                "P39": [
                    {"id": "Q15189$office", "rank": "normal",
                     "mainsnak": entity_value("Q123"),
                     "qualifiers": {
                         "P580": [stamp("+1796-11-06T00:00:00Z",
                                        "http://www.wikidata.org/entity/Q1985786")],
                         "P582": [{"snaktype": "somevalue"}],
                         "P1366": [entity_value("Q99")],
                     }},
                ],
                "P172": [{"id": "ethnic", "rank": "normal",
                          "mainsnak": entity_value("Q100")}],
            },
        }}}

    def test_full_pipeline_does_not_edit_any_source(self):
        originals = {p: p.read_bytes()
                     for p in (self.root / "data/atlas").rglob("*") if p.is_file()}
        report = wd.run(self.root, api=self.api, discover=True,
                        max_searches=1, request_delay=0)
        self.assertEqual(report["summary"]["canonical_people"], 2)
        self.assertEqual(report["summary"]["unlinked_world_people"], 1)
        self.assertEqual(report["summary"]["confirmed_qids"], 1)
        self.assertEqual(report["summary"]["candidate_searches"], 1)
        self.assertEqual({p: p.read_bytes() for p in originals}, originals)
        records = {row["subject_id"]: row for row in report["records"]}
        self.assertEqual(records["p1"]["date_review"]["birth"]["status"],
                         "same_recorded_date")
        self.assertEqual(records["p2"]["status"], "candidate_search_unverified")
        self.assertEqual(records["world:world-new"]["status"], "not_searched")
        self.assertIsNone(records["world:world-new"]["wikidata_id"])
        self.assertNotIn("ethnic_group", records["p1"]["wikidata"]["statements"])
        self.assertFalse(report["historical_truth_verified"])

    def test_deprecated_is_preserved_but_not_compared_as_active(self):
        report = wd.run(self.root, api=self.api, request_delay=0)
        subject = next(p for p in report["records"] if p["subject_id"] == "p1")
        self.assertEqual(subject["date_review"]["birth"]["status"], "same_recorded_date")
        claims = subject["wikidata"]["statements"]["birth"]
        self.assertEqual([c["rank"] for c in claims], ["normal", "deprecated"])
        self.assertEqual(claims[0]["references"][0]["stated_in"], ["Q42"])
        self.assertEqual(claims[0]["references"][0]["urls"],
                         ["https://example.org/archive"])

    def test_office_qualifiers_do_not_create_real_ruler(self):
        report = wd.run(self.root, api=self.api, request_delay=0)
        subject = next(p for p in report["records"] if p["subject_id"] == "p1")
        positions = subject["wikidata"]["statements"]["position_held"]
        self.assertEqual(positions[0]["qualifiers"]["P580"][0]["time"]["calendar"],
                         "julian")
        self.assertEqual(positions[0]["qualifiers"]["P582"][0]["snaktype"],
                         "somevalue")
        self.assertNotIn("real_ruler", subject)
        self.assertFalse(report["mutated_canonical_data"])

    def test_duplicate_confirmed_qids_are_rejected(self):
        path = self.root / "data/atlas/people/p2.json"
        data = json.loads(path.read_text())
        data["external_ids"]["wikidata"] = "Q15189"
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "multiple people"):
            wd.roster(self.root)

    def test_world_is_not_joined_just_because_name_matches(self):
        subjects = wd.roster(self.root)
        ids = {p["subject_id"] for p in subjects}
        self.assertEqual(ids, {"p1", "p2", "world:world-new"})
        self.assertEqual(next(p for p in subjects if p["subject_id"] ==
                              "world:world-new")["name"], "Павел I")


class DateComparison(unittest.TestCase):
    def setUp(self):
        self.canonical = {"value": "1729-04-21",
                          "precision": "day", "calendar": "julian"}
        self.julian = {"time": "+1729-04-21T00:00:00Z",
                       "precision": 11, "calendar": "julian"}

    def test_exact_same_style(self):
        self.assertEqual(wd.calendar_comparison(self.julian, self.canonical),
                         "same_recorded_date")

    def test_different_calendars_require_review(self):
        self.assertEqual(wd.calendar_comparison(
            dict(self.julian, calendar="gregorian"), self.canonical),
            "calendar_review")

    def test_year_is_not_exact_day(self):
        self.assertEqual(wd.calendar_comparison(
            dict(self.julian, time="+1729-00-00T00:00:00Z", precision=9),
            self.canonical), "compatible_lower_precision")

    def test_same_calendar_different_day_is_candidate_conflict(self):
        self.assertEqual(wd.calendar_comparison(
            dict(self.julian, time="+1729-04-22T00:00:00Z"),
            self.canonical), "date_disagreement_candidate")

    def test_ancient_date_never_forced_into_4digit_year(self):
        self.assertEqual(wd.calendar_comparison(
            dict(self.julian, time="-0044-03-15T00:00:00Z"),
            self.canonical), "needs_review")


class RepositoryRosterContract(unittest.TestCase):
    def test_real_repository_counts_and_confirmed_links(self):
        subjects = wd.roster(wd.ROOT)
        canonical = [s for s in subjects if s["kind"] == "canonical"]
        world = [s for s in subjects if s["kind"] == "world_unlinked"]
        expected = len(list((wd.ROOT / "data/atlas/people").glob("*.json")))
        self.assertEqual(len(canonical), expected)
        self.assertEqual(len({s["subject_id"] for s in subjects}), len(subjects))
        self.assertGreater(len(world), 0)
        links = {s["wikidata_id"] for s in subjects if s["wikidata_id"]}
        self.assertTrue({"Q15189", "Q233987", "Q36450"} <= links)


if __name__ == "__main__":
    unittest.main()
