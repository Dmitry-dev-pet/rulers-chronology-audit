"""Second source-research pass: provenance, uncertain dates and de-facto distinctions."""
import unittest
from scripts.atlas_db import ROOT, load, validate
from scripts.biography_coverage import coverage

class ResearchPass(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db=load(ROOT)
        cls.report=coverage(cls.db)

    def test_biography_coverage_accounts_for_every_person(self):
        self.assertEqual(self.report["total_people"],83)
        self.assertEqual(self.report["with_any_birth_fact"],35)
        self.assertEqual(self.report["missing_birth_fact"],48)
        self.assertEqual(len(self.report["rows"]),83)

    def test_year_only_dates_not_invented(self):
        ids={p["name"]:p["id"] for p in self.db["people"]}
        for who, date in [("Василий III Иванович","1479"),
                          ("Иван V Алексеевич","1666"),
                          ("Фёдор Алексеевич","1661")]:
            rows=[f for f in self.db["person_facts"] if f["person_id"]==ids[who] and f["kind"]=="birth"]
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]["value"]["value"],date)
            self.assertEqual(rows[0]["value"]["precision"],"year")
            self.assertEqual(rows[0]["value"]["calendar"],"unspecified")

    def test_biography_research_does_not_forge_old_transcript(self):
        self.assertEqual(len(self.db["provenance"]),150)
        self.assertTrue(all(f["sources"] for f in self.db["person_facts"]))

    def test_legal_and_actual_power_separate(self):
        new=[x for x in self.db["power_assessments"] if x["id"].startswith("power-hist-")]
        self.assertEqual(len(new),13)
        self.assertEqual(len(self.db["power_assessments"]),30)
        self.assertTrue(all(x["sources"] and x["verification"]=="reference_checked" for x in new))
        self.assertTrue(any(x["status"]=="collegial_governance" for x in new))
        self.assertTrue(any(x["status"]=="fragmenting_political_authority" for x in new))
        self.assertEqual(len(self.db["tenures"]),97)

    def test_nationality_is_not_inferred(self):
        self.assertEqual({f["person_id"] for f in self.db["person_facts"] if f["kind"]=="ethnic_origin"},
                         {"person-e88112738c1054f5","person-a4d0a7000e965592"})

    def test_calendar_dispute_preserved(self):
        id="person-14b51b51093f55ce"
        facts=[f for f in self.db["person_facts"] if f["person_id"]==id and f["kind"]=="birth"]
        self.assertEqual(len(facts),1)
        self.assertEqual(facts[0]["value"]["qualifier"],"uncertain")
        self.assertEqual(facts[0]["verification"],"imported_not_rechecked")

    def test_nominal_separated_in_ui(self):
        js=(ROOT/"site/site.js").read_text(encoding="utf-8")
        self.assertIn("Фактическая и коллективная власть",js)
        self.assertIn("Номинальные роли и ограничения",js)
        self.assertIn("infant_emperor",js)
        self.assertIn("nominal_due_to_illness",js)
        self.assertIn("Юридические должности",js)

if __name__=="__main__": unittest.main()
