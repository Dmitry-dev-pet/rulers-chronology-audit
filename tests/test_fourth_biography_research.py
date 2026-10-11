"""Fourth biography source pass: three dated, calendar-qualified births."""
import unittest
from scripts.atlas_db import ROOT, load, validate
from scripts.biography_coverage import coverage

class FourthBiographyPass(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = load(ROOT)
        cls.people = {p["name"]:p["id"] for p in cls.db["people"]}

    def test_births_have_specific_days_and_published_evidence(self):
        expected = [
            ("Александр Керенский","1881-04-22","TP401"),
            ("Георгий Львов","1861-10-21","TP402"),
            ("Иван VI Антонович","1740-08-12","TP403"),
        ]
        sources = {s["id"]:s for s in self.db["sources"]}
        for name,date,ref in expected:
            with self.subTest(name=name):
                person_id=self.people[name]
                facts=[f for f in self.db["person_facts"] if f["person_id"]==person_id and f["kind"]=="birth"]
                self.assertEqual(len(facts),1)
                record=facts[0]
                self.assertEqual(record["value"],{
                    "value":date,"calendar":"julian","precision":"day","qualifier":"as_recorded"
                })
                self.assertEqual(record["verification"],"reference_checked")
                self.assertEqual(record["confidence"],"high")
                self.assertEqual(record["sources"],[ref])
                self.assertEqual(record["evidence"]["path"],"research/biographies-fourth-pass-2026-10-11.md")
                self.assertIn(ref,sources)
                self.assertEqual(sources[ref]["verification"],"reference_checked")
                self.assertTrue(sources[ref]["url"].startswith("https://"))

    def test_sources_do_not_resolve_conflicts_without_documents(self):
        for name in ("Николай Подгорный","Георгий Маленков"):
            person_id=self.people[name]
            self.assertEqual([f for f in self.db["person_facts"]
                              if f["person_id"]==person_id and f["kind"]=="birth"],[])

    def test_counts_source_integrity_and_unchanged_provenance(self):
        report=coverage(self.db)
        self.assertEqual(report["total_people"],83)
        self.assertEqual(report["with_any_birth_fact"],45)
        self.assertEqual(report["missing_birth_fact"],38)
        reviewed={f["person_id"] for f in self.db["person_facts"]
                  if f["kind"]=="birth" and f["verification"]=="reference_checked"}
        self.assertEqual(len(reviewed),40)
        self.assertEqual(len(self.db["person_facts"]),117)
        self.assertEqual(len(self.db["provenance"]),150)
        self.assertFalse(self.db["metadata"]["historical_truth_verified_by_ci"])
        validate(self.db)

if __name__=="__main__":
    unittest.main()
