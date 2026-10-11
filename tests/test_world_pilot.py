"""International 1762 pilot: explicit history, identity and source-link contracts."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

from scripts import atlas_db

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/atlas/world-pilots/1762.json'


class WorldPilotContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pilot=json.loads(SOURCE.read_text(encoding='utf-8'))
        cls.atlas=atlas_db.load(ROOT)
        cls.people={p['id']:p for p in cls.atlas['people']}
        cls.tenures={t['id']:t for t in cls.atlas['tenures']}
        cls.facts={f['id']:f for f in cls.atlas['person_facts']}
        cls.sources={s['id']:s for s in cls.atlas['sources']}
        cls.people_pilot={p['id']:p for p in cls.pilot['persons']}

    def test_exclusively_three_polities_four_persons_and_two_relations(self):
        p=self.pilot
        self.assertEqual(p['schema_version'],'world-pilot-v1')
        self.assertEqual(p['year'],1762)
        self.assertFalse(p['historical_truth_verified_by_ci'])
        self.assertFalse(p['geographic_boundaries_verified'])
        self.assertEqual({x['id'] for x in p['countries']},{'ru','fr','pr'})
        self.assertEqual(set(self.people_pilot),
                         {'ru-peter3','ru-catherine2','fr-louis15','pr-frederick2'})
        self.assertEqual({x['kind'] for x in p['relations']},{'marriage','treaty'})
        self.assertEqual(len(self.atlas['people']),83)
        self.assertEqual(len(self.atlas['tenures']),97)
        self.assertEqual(len(self.atlas['provenance']),150)
        self.assertEqual([x['id'] for x in p['countries'] if x['canonical_state_id']],
                         ['ru'])

    def test_russian_people_resolve_existing_canonical_records(self):
        for key,name,status in [
            ('ru-peter3','Пётр III Фёдорович','emperor'),
            ('ru-catherine2','Екатерина II Алексеевна','empress')
        ]:
            with self.subTest(person=key):
                row=self.people_pilot[key]
                person=self.people[row['canonical_person_id']]
                tenure=self.tenures[row['canonical_tenure_id']]
                self.assertEqual(person['name'],name)
                self.assertEqual(tenure['person_id'],person['id'])
                self.assertEqual(tenure['status'],status)
                self.assertEqual(tenure['state_ids'],['empire'])
                self.assertEqual(row['name'],None)
        # The original Elizabeth tenure is deliberately not inferred to be
        # contemporary with Peter/Catherine from an unspecified calendar year.
        self.assertNotIn('person-494d1e31134351ec',
                         {p['canonical_person_id'] for p in self.people_pilot.values()
                          if p['canonical_person_id']})

    def test_cross_country_birthplace_not_misread_as_ethnicity(self):
        p=self.people_pilot
        self.assertEqual(p['ru-catherine2']['birth']['country_id'],'pr')
        self.assertEqual(p['ru-peter3']['birth']['country_id'],None)
        self.assertEqual(p['fr-louis15']['birth']['country_id'],'fr')
        self.assertEqual(p['pr-frederick2']['birth']['country_id'],'pr')
        ethnic=[x for x in p.values() if x['ethnic_origin_fact_id']]
        self.assertEqual([x['id'] for x in ethnic],['ru-catherine2'])
        fact=self.facts[ethnic[0]['ethnic_origin_fact_id']]
        self.assertEqual(fact['person_id'],ethnic[0]['canonical_person_id'])
        self.assertEqual(fact['kind'],'ethnic_origin')
        self.assertEqual(fact['verification'],'reference_checked')
        self.assertIn('Немецкое',fact['value'])
        self.assertFalse(any(x.get('citizenship') for x in p.values()))
        self.assertNotEqual(p['ru-catherine2']['birth']['country_id'],
                            p['ru-catherine2']['country_id'])

    def test_1762_ranges_dated_evidence_and_no_forged_precision(self):
        self.assertIn('28 июня',self.people_pilot['ru-catherine2']['term']['label'])
        self.assertEqual(self.people_pilot['ru-catherine2']['term']['calendar'],'julian+gregorian')
        self.assertEqual(self.people_pilot['ru-peter3']['term']['precision'],'historical_event_notes')
        for id in ('fr-louis15','pr-frederick2'):
            term=self.people_pilot[id]['term']
            self.assertEqual(term['precision'],'year')
            self.assertEqual(term['calendar'],'unspecified')
            self.assertLessEqual(int(term['start']),1762)
            self.assertGreaterEqual(int(term['end']),1762)
        self.assertEqual(self.people_pilot['pr-frederick2']['role'],'Король в Пруссии')

    def test_every_assertion_and_relation_has_valid_https_sources(self):
        index={s['id']:s for s in self.pilot['sources']}
        ids=list(index)
        self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual(set(ids),{'WP%02d'%i for i in range(1,11)})
        for s in index.values():
            self.assertTrue(s['url'].startswith('https://'))
            self.assertNotIn('drive.google.com',s['url'])
            self.assertEqual(s['verification'],'reference_checked')
        available=set(index)|set(self.sources)
        for row in self.people_pilot.values():
            self.assertIn(row['country_id'],{'ru','fr','pr'})
            refs=row['sources']+row['birth']['sources']+row['dynasty']['sources']
            self.assertTrue(refs)
            self.assertLessEqual(set(refs),available)
            if row['canonical_person_id']:
                self.assertIn(row['canonical_person_id'],self.people)
        for relation in self.pilot['relations']:
            self.assertTrue(set(relation['sources'])<=set(index))
        self.assertEqual(len(set(self.people_pilot)),len(self.pilot['persons']))

    def test_js_markup_routing_and_reduced_mobile_surface(self):
        src=(ROOT/'site/world-atlas.js').read_text(encoding='utf-8')
        css=(ROOT/'site/site.css').read_text(encoding='utf-8')
        year=(ROOT/'site/year-view.js').read_text(encoding='utf-8')
        for s in ('world=1762','world-1762.json','atlas.json','ethnic_origin',
                  'reference_checked','canonical_person_id','canonical_tenure_id',
                  'dynasty','role','popstate','Escape','aria-modal',
                  'aria-pressed','safeUrl','atlas-world-country-grid'):
            if s=='world=1762':
                self.assertIn(s,year)
            else:
                self.assertIn(s,src)
        self.assertIn('.atlas-world-layer[hidden]{display:none!important}',css)
        self.assertIn('max-width:900px',css)
        self.assertNotIn('1000428575.jpg',src)
        self.assertNotIn('drive.google.com/file/d/',src)
        if shutil.which('node'):
            subprocess.run(['node','--check',str(ROOT/'site/world-atlas.js')],
                           check=True,capture_output=True)


if __name__=='__main__':
    unittest.main()
