"""Third biography source pass: archive dates, competing records and preservation."""
import unittest
from scripts.atlas_db import ROOT, age_range, historical_date, load, validate
from scripts.biography_coverage import coverage

class ThirdBiographyPass(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db=load(ROOT)
        cls.people={p["name"]:p["id"] for p in cls.db["people"]}
        cls.report=coverage(cls.db)

    def facts_for(self,name,kind):
        pid=self.people[name]
        return [x for x in self.db["person_facts"] if x["person_id"]==pid and x["kind"]==kind]

    def test_seven_new_identified_people_have_births(self):
        researched={
            "Василий II Васильевич","Борис Фёдорович Годунов",
            "Алексей Косыгин","Владимир Ивашко","Константин Черненко",
            "Геннадий Янаев","Иван Силаев",
        }
        # Assert exact canonical spelling before changing the historical source.
        names={p["name"] for p in self.db["people"]}
        self.assertTrue(researched <= names,researched-names)
        for name in researched:
            self.assertTrue(self.facts_for(name,"birth"),name)
            self.assertTrue(self.facts_for(name,"death"),name)
        self.assertEqual(self.report["total_people"],83)
        self.assertGreaterEqual(self.report["with_any_birth_fact"],42)
        self.assertLessEqual(self.report["missing_birth_fact"],41)
        self.assertGreaterEqual(len(self.db["person_facts"]),114)

    def test_chernenko_primary_description_and_old_official_conflict(self):
        facts=self.facts_for("Константин Черненко","birth")
        self.assertEqual(len(facts),2)
        by_date={x["value"]["value"]:x for x in facts}
        self.assertEqual(set(by_date),{"1911-09-11","1912-09-18"})
        archived=by_date["1912-09-18"]
        traditional=by_date["1911-09-11"]
        self.assertEqual((archived["value"]["calendar"],archived["verification"]),("julian","reference_checked"))
        self.assertIn("TP308",archived["sources"])
        self.assertEqual(traditional["verification"],"disputed")
        self.assertEqual(traditional["value"]["qualifier"],"uncertain")
        self.assertIn("TP309",traditional["sources"])
        self.assertFalse(age_range(traditional["value"],historical_date("1984","gregorian"))["available"])
        estimate=age_range(archived["value"],historical_date("1984","gregorian"))
        self.assertEqual((estimate["min_years"],estimate["max_years"]),(71,72))

    def test_no_forged_calendar_for_medieval_births(self):
        vas=self.facts_for("Василий II Васильевич","birth")[0]
        bor=self.facts_for("Борис Фёдорович Годунов","birth")[0]
        self.assertEqual((vas["value"]["value"],vas["value"]["precision"],vas["value"]["calendar"]),
                         ("1415-03-10","day","unspecified"))
        self.assertEqual(bor["value"]["value"],"1552")
        self.assertEqual(bor["verification"],"disputed")
        self.assertEqual(bor["value"]["qualifier"],"uncertain")
        for row in (vas,bor):
            self.assertFalse(age_range(row["value"],historical_date("1600","gregorian"))["available"])

    def test_archival_and_institutional_dates(self):
        expected=[
            ("Алексей Косыгин","1904-02-08","julian"),
            ("Владимир Ивашко","1932-10-28","gregorian"),
            ("Геннадий Янаев","1937-08-26","gregorian"),
            ("Иван Силаев","1930-10-21","gregorian"),
        ]
        for name,date,style in expected:
            with self.subTest(person=name):
                row=self.facts_for(name,"birth")[0]
                self.assertEqual((row["value"]["value"],row["value"]["calendar"]),(date,style))
                self.assertEqual(row["verification"],"reference_checked")

    def test_new_data_remain_linked_and_no_old_evidence_rewritten(self):
        novel=[f for f in self.db["person_facts"] if f["id"].startswith("fact-research-20261010-")]
        self.assertEqual(len(novel),15)
        self.assertTrue(all(f["evidence"]["path"]=="research/biographies-third-pass-2026-10-10.md" for f in novel))
        source_ids={s["id"] for s in self.db["sources"]}
        self.assertTrue(all(set(f["sources"])<=source_ids for f in novel))
        self.assertEqual({s["id"] for s in self.db["sources"] if s["id"].startswith("TP3")},
                         {f"TP3{i:02}" for i in range(1,14)})
        self.assertEqual(len(self.db["provenance"]),150)
        self.assertFalse(self.db["metadata"]["historical_truth_verified_by_ci"])
        self.assertFalse(any(f["verification"]=="primary_checked" for f in novel))
        validate(self.db)

if __name__=="__main__":
    unittest.main()
