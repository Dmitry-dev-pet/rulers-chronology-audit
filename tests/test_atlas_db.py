"""Contract tests: normalization, provenance, safe export, calendars and referential integrity."""
import copy
import hashlib
import importlib.util
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

CODE_ROOT=Path(__file__).resolve().parents[1]
ROOT=Path(os.environ.get('ATLAS_TEST_ROOT',CODE_ROOT))
spec=importlib.util.spec_from_file_location('atlas_db',CODE_ROOT/'scripts/atlas_db.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)


class DateTests(unittest.TestCase):
    def test_full_years(self):
        b=a.historical_date('2000-05-10','gregorian')
        self.assertEqual(a.age_range(b,a.historical_date('2020-05-09','gregorian'))['min_years'],19)
        self.assertEqual(a.age_range(b,a.historical_date('2020-05-10','gregorian'))['min_years'],20)

    def test_year_only_is_a_range(self):
        r=a.age_range(a.historical_date('2000','gregorian'),a.historical_date('2020-06-01','gregorian'))
        self.assertEqual((r['min_years'],r['max_years'],r['exact']),(19,20,False))

    def test_julian_conversion(self):
        b=a.gregorian_bounds(a.historical_date('1700-02-29','julian'))
        self.assertEqual(str(b[0]),'1700-03-11')

    def test_invalid_gregorian_leap_day(self):
        with self.assertRaises(ValueError):a.historical_date('1700-02-29','gregorian')

    def test_unspecified_calendar_never_invents_age(self):
        self.assertFalse(a.age_range(a.historical_date('1672'),a.historical_date('1682','gregorian'))['available'])

    def test_approximate_birth_never_becomes_exact(self):
        self.assertFalse(a.age_range(a.historical_date('2000','gregorian','approximate'),a.historical_date('2020','gregorian'))['available'])

    def test_before_birth(self):
        self.assertFalse(a.age_range(a.historical_date('2000','gregorian'),a.historical_date('1900','gregorian'))['available'])

    def test_invalid_dates_and_precision(self):
        for value in ['0000','2020-13','2020-04-31','-0044','2020-01-00']:
            with self.subTest(value=value),self.assertRaises(ValueError):a.historical_date(value)
        d=a.historical_date('2000');d['precision']='day'
        with self.assertRaises(ValueError):a.validate_date(d)


class AtlasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.db=a.load(ROOT)

    def test_every_legacy_record_preserved(self):
        original={}
        for _,path,_ in a.LAYERS:
            for value in a.read_json(ROOT/path).values():
                if isinstance(value,list):
                    for row in value:
                        if isinstance(row,dict) and 'id' in row:original[row['id']]=row
        self.assertEqual({r['id']:r['row'] for r in self.db['provenance'] if r['path'] in {p for _,p,_ in a.LAYERS}},original)
        self.assertEqual(len(original),150)

    def test_no_duplicate_people_for_known_aliases(self):
        for names in [('Борис Годунов','Борис Фёдорович Годунов'),('Иван IV Васильевич','Иван IV Васильевич Грозный'),('Василий II Васильевич','Василий II Васильевич Тёмный')]:
            people=[p for p in self.db['people'] if p['name'] in names or set(p['aliases'])&set(names)]
            self.assertEqual(len(people),1,names)

    def test_lenin_different_offices_one_person(self):
        p=next(p for p in self.db['people'] if p['name']=='Владимир Ленин')
        self.assertGreaterEqual(len([t for t in self.db['tenures'] if t['person_id']==p['id']]),2)
        self.assertTrue(any(t['person_id']==p['id'] for t in self.db['power_assessments']))

    def test_peter_has_three_linked_stages(self):
        terms=[t for t in self.db['tenures'] if t['record_id']=='R05']
        self.assertEqual(len(terms),3)
        self.assertEqual(len({t['person_id'] for t in terms}),1)
        self.assertEqual({(t['start']['value'],t['end']['value']) for t in terms},{('1682','1696'),('1696','1721'),('1721','1725')})
        self.assertTrue(all(t['start']['precision']=='year' for t in terms))
        self.assertEqual(next(t for t in terms if t['office_id']=='emperor')['state_ids'],['empire'])

    def test_collective_chairmen_are_initial_composition_only(self):
        memberships=[m for b in self.db['bodies'] for m in b['memberships'] if m['record_id']=='S05']
        self.assertEqual(len(memberships),4)
        self.assertTrue(all(m['relation']=='initial_composition_only' for m in memberships))
        self.assertFalse(any(t['record_id']=='S05' for t in self.db['tenures']))

    def test_constantine_not_an_emperor_tenure(self):
        self.assertFalse(any(t['record_id']=='I41' for t in self.db['tenures']))
        self.assertTrue(any(t['record_id']=='I41' for t in self.db['events']))

    def test_bodies_are_not_people(self):
        self.assertFalse(any(p['name'] in {'Комитет министров','Боярская дума','Семибоярщина'} for p in self.db['people']))

    def test_biographical_text_not_promoted_to_verified_dates(self):
        self.assertTrue(self.db['person_facts'])
        imported=[f for f in self.db['person_facts'] if f['id'].startswith('fact-poster-')]
        self.assertEqual(len(imported),46)
        self.assertTrue(all(f['kind']=='lifespan_text' and f['verification']=='imported_not_rechecked' for f in imported))

    def test_power_claims_keep_qualifications(self):
        self.assertTrue(self.db['power_assessments'])
        self.assertTrue(all(x['note'] and x['sources'] and x['confidence'] in {'not_assessed','low','medium','high'} for x in self.db['power_assessments']))

    def test_missing_source_rejected(self):
        d=copy.deepcopy(self.db);d['tenures'][0]['sources']=['MISSING']
        with self.assertRaises(ValueError):a.validate(d)

    def test_orphan_person_rejected(self):
        d=copy.deepcopy(self.db);d['tenures'][0]['person_id']='missing'
        with self.assertRaises(ValueError):a.validate(d)

    def test_legacy_mutation_rejected(self):
        d=copy.deepcopy(self.db);d['provenance'][0]['row']['note']='changed'
        with self.assertRaises(ValueError):a.validate(d)

    def test_missing_mapping_rejected(self):
        d=copy.deepcopy(self.db)
        target=d['tenures'][0]['record_id']
        for kind in ['tenures','power_assessments','events','institution_periods']:
            d[kind]=[r for r in d[kind] if r['record_id']!=target]
        with self.assertRaises(ValueError):a.validate(d)

    def test_reversed_months_rejected_even_unknown_calendar(self):
        d=copy.deepcopy(self.db);d['tenures'][0]['start']=a.historical_date('1900-12');d['tenures'][0]['end']=a.historical_date('1900-01')
        with self.assertRaises(ValueError):a.validate(d)

    def test_unsafe_source_rejected(self):
        for value in ['http://example.org','javascript:alert(1)','https://drive.google.com/a','https://user:pass@example.org/a']:
            d=copy.deepcopy(self.db);d['sources'][0]['url']=value
            with self.subTest(value=value),self.assertRaises(ValueError):a.validate(d)

    def test_unreferenced_identity_claim_rejected(self):
        d=copy.deepcopy(self.db);d['person_facts'][0]['kind']='ethnic_origin';d['person_facts'][0]['sources']=[]
        with self.assertRaises(ValueError):a.validate(d)

    def test_html_is_escaped(self):
        d=copy.deepcopy(self.db);d['people'][0]['name']='<img src=x onerror=alert(1)>'
        page=a.database_page(d)
        self.assertNotIn('<img src=x',page);self.assertIn('&lt;img',page)

    def test_migration_refuses_overwrite(self):
        with self.assertRaises(ValueError):a.migrate(ROOT)

    def test_input_hashes_still_match(self):a.verify_inputs(self.db,ROOT)

    def test_reproducible_non_destructive_migration(self):
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'imported'
            a.migrate(ROOT,output)
            other=Path(temp)/'second-import'
            a.migrate(ROOT,other)
            for p in output.rglob('*'):
                if p.is_file():self.assertEqual(p.read_bytes(),(other/p.relative_to(output)).read_bytes())

    def test_sqlite_foreign_keys_and_views(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'atlas.sqlite'
            a.write_sqlite(self.db,path,(CODE_ROOT/'schemas/atlas.sql').read_text())
            con=sqlite3.connect(path)
            try:
                self.assertEqual(con.execute('PRAGMA user_version').fetchone()[0],1)
                self.assertEqual(con.execute('PRAGMA integrity_check').fetchone()[0],'ok')
                self.assertEqual(con.execute('PRAGMA foreign_key_check').fetchall(),[])
                self.assertGreaterEqual(con.execute('SELECT count(*) FROM provenance').fetchone()[0],150)
                self.assertEqual(con.execute("SELECT count(*) FROM person_tenures WHERE name='Пётр I Алексеевич'").fetchone()[0],3)
                con.execute('PRAGMA foreign_keys=ON')
                with self.assertRaises(sqlite3.IntegrityError):con.execute("INSERT INTO fact_sources VALUES ('missing','missing')")
                with self.assertRaises(sqlite3.IntegrityError):con.execute("INSERT INTO fact_sources VALUES (NULL,NULL)")
            finally:con.close()

    def test_build_outputs_and_roundtrip(self):
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)
            output.joinpath('index.html').write_text('<html><body>Existing atlas</body></html>')
            before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'data/atlas').rglob('*') if p.is_file()}
            a.build(ROOT,output)
            self.assertEqual(json.loads((output/'atlas.json').read_text()),self.db)
            expected={'index.html','database.html','atlas.json','atlas.sqlite','atlas-manifest.json','atlas-schema.sql','transition-cases.json','SHA256SUMS'}
            self.assertEqual({p.name for p in output.iterdir()},expected)
            self.assertTrue((output/'atlas.sqlite').read_bytes().startswith(b'SQLite format 3\x00'))
            for p in output.iterdir():
                self.assertNotIn(b'drive.google.com',p.read_bytes())
                self.assertNotIn(b'1000428575.jpg',p.read_bytes())
            for line in (output/'SHA256SUMS').read_text().splitlines():
                h,name=line.split('  ');self.assertEqual(h,hashlib.sha256((output/name).read_bytes()).hexdigest())
            manifest=json.loads((output/'atlas-manifest.json').read_text())
            self.assertIs(manifest['historical_truth_verified_by_ci'],False)
            a.build(ROOT,output)
            self.assertEqual((output/'index.html').read_text().count('data-atlas-database'),1)
            self.assertEqual(before,{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'data/atlas').rglob('*') if p.is_file()})

if __name__=='__main__':unittest.main()
