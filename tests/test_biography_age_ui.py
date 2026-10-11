"""Contract tests for biographical enrichment and the static year inspector."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

from scripts import atlas_db

ROOT=Path(__file__).resolve().parents[1]

class BiographyContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.atlas=atlas_db.load(ROOT)
        cls.names={p['id']:p['name'] for p in cls.atlas['people']}
        cls.sources={s['id'] for s in cls.atlas['sources']}
        cls.facts=cls.atlas['person_facts']

    def test_researched_births_from_four_centuries(self):
        names={self.names[f['person_id']] for f in self.facts if f['kind']=='birth'}
        self.assertGreaterEqual(len(names),42)
        for name in ('Иван III Васильевич','Иван IV Васильевич','Михаил Фёдорович',
                     'Пётр I Алексеевич','Екатерина II Алексеевна','Николай II',
                     'Владимир Ленин','Иосиф Сталин','Никита Хрущёв','Михаил Горбачёв'):
            self.assertIn(name,names)

    def test_births_preserve_calendar_provenance(self):
        for row in self.facts:
            if row['kind'] not in {'birth','death'}: continue
            atlas_db.validate_date(row['value'])
            self.assertIn(row['value']['calendar'],{'julian','gregorian','unspecified'})
            if row['value']['calendar']=='unspecified':
                # Exact-looking medieval civil days may still have unknown calendar style.
                self.assertIn(row['value']['precision'],{'year','month','day'})
                self.assertFalse(atlas_db.age_range(row['value'], atlas_db.historical_date('2000','gregorian'))['available'])
            else:
                self.assertEqual(row['value']['precision'],'day')
            self.assertTrue(row['sources'])
            self.assertTrue(set(row['sources'])<=self.sources)
            self.assertIn(row['verification'],{'disputed','reference_checked','imported_not_rechecked'})
            if row['verification']=='imported_not_rechecked':
                self.assertTrue(row['value']['calendar']=='unspecified' or row['value']['qualifier'] in {'uncertain','as_recorded'})

    def test_ivan_and_peter_ages_reconciled_with_julian_calendar(self):
        for name,dob,year,minage,maxage in [
            ('Иван IV Васильевич','1530-08-25','1533',2,3),
            ('Пётр I Алексеевич','1672-05-30','1685',12,13)]:
            p=next(p for p in self.atlas['people'] if p['name']==name)
            row=next(f for f in self.facts if f['person_id']==p['id'] and f['kind']=='birth')
            self.assertEqual(row['value']['value'],dob)
            value=atlas_db.age_range(row['value'],atlas_db.historical_date(year,'gregorian'))
            self.assertEqual((value['min_years'],value['max_years']),(minage,maxage))

    def test_stalin_alternative_sources_not_collapsed(self):
        id=next(p['id'] for p in self.atlas['people'] if p['name']=='Иосиф Сталин')
        births=[f for f in self.facts if f['person_id']==id and f['kind']=='birth']
        self.assertEqual({f['value']['value'] for f in births},{'1878-12-06','1879-12-21'})
        self.assertEqual({f['verification'] for f in births},{'reference_checked','disputed'})

    def test_no_unproved_ethnicity(self):
        origins=[f for f in self.facts if f['kind']=='ethnic_origin']
        self.assertEqual({self.names[f['person_id']] for f in origins},{'Иосиф Сталин','Екатерина II Алексеевна'})
        self.assertTrue(all(f['sources'] for f in origins))

    def test_public_database_has_birth_and_sources(self):
        page=atlas_db.database_page(self.atlas)
        self.assertIn('Дата рождения',page)
        self.assertIn('спорная',page)
        self.assertIn('1878-12-06',page)
        self.assertIn('https://archive.gov.ge',page)
        self.assertNotIn('drive.google.com',page)

    def test_timeline_has_distinct_power_and_office_groups(self):
        code=(ROOT/'site/site.js').read_text(encoding='utf-8')
        self.assertIn("fetch('./atlas.json'",code)
        self.assertIn('Фактическая и коллективная власть',code)
        self.assertIn('Номинальные роли и ограничения',code)
        self.assertIn('Юридические должности',code)
        self.assertIn('atlas-year-cursor',code)
        if shutil.which('node'):
            subprocess.run(['node','--check',str(ROOT/'site/site.js')],check=True,capture_output=True)

if __name__=='__main__': unittest.main()
