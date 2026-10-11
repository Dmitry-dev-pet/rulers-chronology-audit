"""Append-only European 1762–1800 coverage repairs and historically honest gaps."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path
from scripts import atlas_db

ROOT=Path(__file__).resolve().parents[1]
DIR=ROOT/'data/atlas/world-pilots'


def load(name):
    return json.loads((DIR/name).read_text(encoding='utf-8'))


class CoverageBackfillContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db=atlas_db.load(ROOT)
        cls.pilot=load('1762.json')
        cls.old=load('dynasty-1762-1780.json')
        cls.late=load('extension-1781-1800.json')
        cls.houses=load('dynasty-footprints-1762-1800.json')
        cls.patch=load('coverage-backfill-1762-1800.json')
        cls.people={p['id']:p for p in (
            cls.pilot['persons']+cls.old['additional_persons']+
            cls.late['additional_persons']+cls.patch['person_additions'])}
        cls.roles=cls.old['roles']+cls.late['additional_roles']+cls.patch['role_additions']

    def at(self,year,polity=None):
        return [r for r in self.roles if r['start_year']<=year<=r['end_year'] and
                (polity is None or r['polity_id']==polity)]

    def test_stable_old_data_and_distinct_new_ids(self):
        x=self.patch
        self.assertEqual(x['schema_version'],'dynasty-coverage-backfill-v1')
        self.assertFalse(x['historical_truth_verified_by_ci'])
        self.assertFalse(x['historical_borders_verified'])
        self.assertEqual(x['coverage_window'],{'start':1762,'end':1800})
        self.assertEqual(set(x['covered_polity_ids']),{'es','pt','sw','tusc'})
        self.assertEqual(len(x['person_additions']),3)
        self.assertEqual(len(x['role_additions']),9)
        self.assertEqual(len(x['relation_additions']),5)
        self.assertEqual(len(x['source_records']),11)
        self.assertEqual(len(x['family_additions']),2)
        self.assertEqual(len(x['family_member_additions']),2)
        self.assertEqual(len(self.people),31)
        self.assertEqual(len(self.roles),49)
        self.assertEqual({m['id'] for m in x['person_additions']},
                         {'pt-jose1','sw-adolf-fredrik','tusc-ferdinand3'})
        self.assertEqual(len(self.db['people']),83)
        self.assertEqual(len(self.db['tenures']),97)
        self.assertEqual(len(self.db['provenance']),150)
        self.assertEqual(len(self.old['additional_persons']),8)
        self.assertEqual(len(self.late['additional_roles']),22)
        self.assertEqual(len(self.houses['families']),4)
        self.assertEqual(len(set(self.people)),len(self.people))
        self.assertEqual(len({r['id'] for r in self.roles}),len(self.roles))

    def test_independently_cited_memberships_and_roles(self):
        sources={x['id'] for x in (self.db['sources']+self.pilot['sources']+
            self.old['sources']+self.late['sources']+self.houses['sources']+
            self.patch['source_records'])}
        for group in ('role_additions','relation_additions','milestones'):
            for r in self.patch[group]:
                with self.subTest(item=r['id'] if 'id' in r else r['year']):
                    self.assertTrue(r['source_ids'])
                    self.assertTrue(set(r['source_ids'])<=sources)
        for row in self.patch['role_additions']:
            self.assertIn(row['person_id'],self.people)
            self.assertIn(row['polity_id'],self.patch['covered_polity_ids'])
            self.assertLessEqual(row['start_year'],row['end_year'])
            self.assertEqual(row['verification'],'reference_checked')
        for group in self.patch['family_additions']:
            self.assertTrue(set(group['source_ids'])<=sources)
            for m in group['members']:
                self.assertIn(m['person_id'],self.people)
                self.assertTrue(set(m['source_ids'])<=sources)
        for group in self.patch['family_member_additions']:
            self.assertIn(group['family_id'],
                {h['id'] for h in self.houses['families']})
            for m in group['members']:
                self.assertTrue(set(m['source_ids'])<=sources)
        for s in self.patch['source_records']:
            self.assertTrue(s['url'].startswith('https://'))
            self.assertEqual(s['verification'],'reference_checked')
        self.assertEqual({h['id'] for h in self.patch['family_additions']},
                         {'braganza','hohenzollern'})

    def test_spain_and_portugal_no_1781_research_gap(self):
        for y in range(1762,1801):
            self.assertTrue(self.at(y,'es'),f'Spain uncovered: {y}')
            self.assertTrue(self.at(y,'pt'),f'Portugal uncovered: {y}')
        self.assertEqual({x['person_id'] for x in self.at(1762,'es')},
                         {'es-carlos3'})
        self.assertEqual({x['person_id'] for x in self.at(1777,'pt')},
                         {'pt-jose1','pt-maria1','pt-pedro3'})
        self.assertEqual({x['role_kind'] for x in self.at(1777,'pt')},
                         {'sovereign','consort'})
        self.assertFalse(any(r['person_id']=='pt-pedro3' and
                             r['role_kind']=='sovereign' for r in self.roles))
        self.assertEqual({x['person_id'] for x in self.at(1781,'pt')},
                         {'pt-maria1','pt-pedro3'})
        for x in self.patch['role_additions']:
            self.assertFalse(x['start_year']>1780 and x['end_year']<1790,
                             'Do not duplicate existing 1781–1789 terms')

    def test_swedish_succession_and_nominal_vs_effective_separate(self):
        self.assertTrue(all(self.at(y,'sw') for y in range(1762,1801)))
        self.assertEqual({r['person_id'] for r in self.at(1771,'sw')},
                         {'sw-adolf-fredrik','sw-gustav3'})
        self.assertTrue(any('личное политическое влияние' in r['note'] for r in
                            self.at(1762,'sw')))
        self.assertIn('Гольштейн',self.people['sw-adolf-fredrik']['houses'][0]['name'])
        self.assertFalse(self.people['sw-adolf-fredrik']['ethnic_origin_fact_id'])
        self.assertTrue(any(r['role_kind']=='regent' for r in self.at(1792,'sw')))
        self.assertEqual({r['person_id'] for r in self.at(1800,'sw')},
                         {'sw-gustav4'})

    def test_tuscany_consider_formal_vs_territorial_control(self):
        self.assertEqual({x['person_id'] for x in self.at(1762,'tusc')},
                         {'hre-francis'})
        self.assertEqual({x['person_id'] for x in self.at(1765,'tusc')},
                         {'hre-francis','hab-leopold'})
        self.assertIn('Регентский совет',self.at(1762,'tusc')[0]['note'])
        self.assertEqual({x['person_id'] for x in self.at(1788,'tusc')},
                         {'hab-leopold','hab-maria-luisa'})
        self.assertEqual({x['person_id'] for x in self.at(1790,'tusc')},
                         {'hab-leopold','hab-maria-luisa','tusc-ferdinand3'})
        self.assertEqual({x['person_id'] for x in self.at(1798,'tusc')},
                         {'tusc-ferdinand3'})
        self.assertTrue(any('изгнали' in r['note'] for r in self.at(1799,'tusc')))
        self.assertFalse(self.at(1800,'tusc'))
        self.assertTrue(any('не утверждаем' in row['note'] for row in
            self.patch['polity_coverage_notes'] if row['id']=='tusc'))

    def test_houses_are_analytical_not_ethnic_labels(self):
        family={h['id']:h for h in self.patch['family_additions']}
        self.assertEqual({m['person_id'] for m in family['braganza']['members']},
                         {'pt-jose1','pt-maria1','pt-pedro3','pt-joao'})
        self.assertEqual({m['person_id'] for m in family['hohenzollern']['members']},
                         {'pr-frederick2','pr-fw2','pr-fw3'})
        self.assertEqual({x['family_id'] for x in
                          self.patch['family_member_additions']},
                         {'habsburg-lorraine','holstein-gottorp'})
        for p in self.patch['person_additions']:
            self.assertIsNone(p['ethnic_origin_fact_id'])
            self.assertIsNone(p['canonical_person_id'])
            self.assertFalse(p.get('citizenship'))
        self.assertEqual(self.patch['family_member_additions'][1]['members'][0]['person_id'],
                         'tusc-ferdinand3')
        self.assertEqual(self.people['ru-paul1']['houses'][0]['id'],'romanov')

    def test_ui_and_build_are_explicitly_additive(self):
        js=(ROOT/'site/dynasty-atlas.js').read_text(encoding='utf-8')
        build=(ROOT/'scripts/soviet_audit.py').read_text(encoding='utf-8')
        for key in ('coverage-backfill','covered_polity_ids','family_additions',
                    'family_member_additions','role_additions','dynView'):
            self.assertIn(key,js)
        self.assertIn('world-coverage-backfill.json',build)
        self.assertNotIn('drive.google.com',js)
        self.assertNotIn('1000428575.jpg',js)
        if shutil.which('node'):
            subprocess.run(['node','--check',str(ROOT/'site/dynasty-atlas.js')],
                           check=True,capture_output=True)

if __name__=='__main__':
    unittest.main()
