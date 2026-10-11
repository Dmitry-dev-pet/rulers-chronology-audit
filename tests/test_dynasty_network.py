"""Source-only international Europe 1762–1780 roles and dynasty network contracts."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path
from scripts import atlas_db

ROOT=Path(__file__).resolve().parents[1]
MODEL=ROOT/'data/atlas/world-pilots/dynasty-1762-1780.json'
PILOT=ROOT/'data/atlas/world-pilots/1762.json'


class DynastyNetworkContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db=atlas_db.load(ROOT)
        cls.model=json.loads(MODEL.read_text(encoding='utf-8'))
        cls.base=json.loads(PILOT.read_text(encoding='utf-8'))
        cls.persons={p['id']:p for p in cls.base['persons']+cls.model['additional_persons']}
        cls.states={x['id']:x for x in cls.base['countries']+cls.model['additional_polities']}
        cls.roles=cls.model['roles']
        cls.relations=cls.model['relations']

    def at(self,y):
        return [r for r in self.roles if r['start_year']<=y<=r['end_year']]

    def test_scope_and_previous_russian_source_unchanged(self):
        d=self.model
        self.assertEqual(d['schema_version'],'dynasty-network-v1')
        self.assertEqual(d['base_pilot'],'world-1762.json')
        self.assertEqual(d['period'],{
            'start':1762,'end':1780,'initial':1762,'presets':[1762,1765,1770,1774,1780]})
        self.assertFalse(d['historical_truth_verified_by_ci'])
        self.assertFalse(d['historical_borders_verified'])
        self.assertEqual(len(self.states),8)
        self.assertEqual(len(self.persons),12)
        self.assertEqual(len(self.roles),18)
        self.assertEqual(len(self.relations),11)
        self.assertEqual(len(self.db['people']),83)
        self.assertEqual(len(self.db['tenures']),97)
        self.assertEqual(len(self.db['provenance']),150)
        self.assertEqual(len(self.base['persons']),4)
        self.assertEqual(len(self.base['countries']),3)
        self.assertEqual(len(self.base['relations']),2)
        self.assertEqual(self.states['hre']['kind'],'imperial_office_context')
        self.assertEqual(self.states['meck']['kind'],'birthplace_context_only')
        self.assertEqual(self.states['hab']['kind'],'composite_monarchy')

    def test_existing_canonical_ids_not_duplicated(self):
        identity={p['id']:p for p in self.db['people']}
        terms={r['id']:r for r in self.db['tenures']}
        for p in self.persons.values():
            if p.get('canonical_person_id'):
                with self.subTest(person=p['id']):
                    self.assertIn(p['canonical_person_id'],identity)
                    self.assertEqual(terms[p['canonical_tenure_id']]['person_id'],
                                     p['canonical_person_id'])
        self.assertEqual(self.persons['ru-elizabeth']['canonical_tenure_id'],'tenure-r10')
        self.assertEqual(self.persons['ru-peter3']['canonical_tenure_id'],'tenure-r11')
        self.assertEqual(self.persons['ru-catherine2']['canonical_tenure_id'],'tenure-r12')

    def test_1762_three_sequential_russian_reigns_and_no_false_same_day(self):
        y=self.at(1762)
        russian={r['person_id'] for r in y if r['polity_id']=='ru'}
        self.assertEqual(russian,{'ru-elizabeth','ru-peter3','ru-catherine2'})
        elizabeth=next(r for r in y if r['person_id']=='ru-elizabeth')
        self.assertEqual(elizabeth['end_gregorian'],'1762-01-05')
        self.assertIn('Не является одновременным',elizabeth['note'])
        self.assertEqual({r['person_id'] for r in y if r['polity_id']=='hre'},
                         {'hre-francis'})
        self.assertEqual({r['person_id'] for r in y if r['polity_id']=='hab'},
                         {'hab-maria','hre-francis'})
        self.assertEqual({r['person_id'] for r in y if r['polity_id']=='gb'},
                         {'gb-george3','gb-charlotte'})
        self.assertEqual({r['person_id'] for r in y if r['polity_id']=='han'},
                         {'gb-george3'})
        self.assertEqual(len(set(r['person_id'] for r in y)),9)
        self.assertFalse(any(r['person_id']=='fr-antoinette' for r in y))
        self.assertFalse(any(r['person_id']=='fr-louis16' for r in y))

    def test_1765_1770_1774_1780_institutional_and_marriage_transitions(self):
        y65=self.at(1765)
        self.assertEqual({r['person_id'] for r in y65 if r['polity_id']=='hre'},
                         {'hre-francis','hre-joseph'})
        self.assertTrue(any(r['role_kind']=='co_regent' and
                            r['person_id']=='hre-joseph' for r in y65))
        y70=self.at(1770)
        self.assertTrue(any(r['person_id']=='fr-louis16' and
                            r['role_kind']=='heir' for r in y70))
        self.assertFalse(any(r['person_id']=='fr-louis16' and
                             r['role_kind']=='sovereign' for r in y70))
        self.assertTrue(any(r['person_id']=='fr-antoinette' and
                            r['role_kind']=='consort' for r in y70))
        self.assertEqual({r['person_id'] for r in self.at(1774)
                          if r['polity_id']=='fr' and r['role_kind']=='sovereign'},
                         {'fr-louis15','fr-louis16'})
        y80=self.at(1780)
        self.assertEqual({r['person_id'] for r in y80 if r['polity_id']=='hre'},
                         {'hre-joseph'})
        self.assertTrue(any(r['person_id']=='hab-maria' and
                            r['role_kind']=='sovereign' for r in y80))
        self.assertTrue(any(r['person_id']=='hre-joseph' and
                            r['role_kind']=='sovereign' for r in y80))
        self.assertFalse(any(r['person_id']=='hre-francis' for r in y80))
        self.assertFalse(any(r['person_id']=='fr-louis15' for r in y80))
        self.assertEqual({x['year'] for x in self.model['milestones']},
                         {1762,1765,1770,1774,1780})

    def test_personal_union_one_human_two_polity_roles(self):
        x=[r for r in self.roles if r['person_id']=='gb-george3']
        self.assertEqual({r['polity_id'] for r in x},{'gb','han'})
        self.assertEqual({r['role_kind'] for r in x},{'sovereign','elector'})
        self.assertEqual(self.persons['gb-george3']['ethnic_origin_fact_id'],None)
        personal=next(r for r in self.relations if r['kind']=='personal_union')
        self.assertEqual(personal['subjects'],['gb-george3'])
        self.assertEqual(set(personal['polity_ids']),{'gb','han'})
        self.assertIn('не объединение',personal['note'])
        self.assertEqual(self.states['han']['kind'],'electorate')

    def test_sourced_origins_not_guessed_from_birthplace_or_dynasty(self):
        referenced=[p for p in self.persons.values() if p.get('ethnic_origin_fact_id')]
        self.assertEqual([x['id'] for x in referenced],['ru-catherine2'])
        facts={f['id']:f for f in self.db['person_facts']}
        for p in referenced:
            row=facts[p['ethnic_origin_fact_id']]
            self.assertEqual(row['kind'],'ethnic_origin')
            self.assertEqual(row['verification'],'reference_checked')
            self.assertEqual(row['person_id'],p['canonical_person_id'])
        self.assertEqual(self.persons['gb-charlotte']['birthplace']['polity_id'],'meck')
        self.assertEqual(self.persons['fr-antoinette']['birthplace']['polity_id'],'hab')
        self.assertFalse(any(r['polity_id']=='meck' for r in self.roles))
        self.assertFalse(any('citizenship' in p for p in self.persons.values()))
        self.assertEqual({r['role_kind'] for r in self.roles
                          if r['person_id']=='fr-antoinette'},{'consort'})
        self.assertFalse(any(r['person_id']=='hab-maria' and r['polity_id']=='hre'
                             for r in self.roles))

    def test_every_source_exists_and_nonempty(self):
        idx={x['id']:x for x in self.base['sources']+self.model['sources']+self.db['sources']}
        for element in [*self.roles,*self.relations,*self.model['milestones'],
                        *self.model['additional_polities']]:
            with self.subTest(item=element.get('id',element.get('year'))):
                self.assertTrue(element['source_ids'])
                self.assertLessEqual(set(element['source_ids']),set(idx))
        for p in self.persons.values():
            if p.get('source_ids'):
                self.assertLessEqual(set(p['source_ids']),set(idx))
            for h in p.get('houses',[]):
                self.assertTrue(h['source_ids'])
                self.assertTrue(set(h['source_ids'])<=set(idx))
        for r in self.roles:
            self.assertIn(r['person_id'],self.persons)
            self.assertIn(r['polity_id'],self.states)
            self.assertLessEqual(r['start_year'],r['end_year'])
        for r in self.relations:
            self.assertLessEqual(set(r['subjects']),set(self.persons))
        for s in self.model['sources']:
            self.assertTrue(s['url'].startswith('https://'))
            self.assertEqual(s['verification'],'reference_checked')
        self.assertEqual(len(self.model['sources']),10)

    def test_static_bundle_and_accessible_network_contract(self):
        code=(ROOT/'site/dynasty-atlas.js').read_text(encoding='utf-8')
        css=(ROOT/'site/site.css').read_text(encoding='utf-8')
        site=(ROOT/'site/world-atlas.js').read_text(encoding='utf-8')
        for token in ('dynasty18','dynYear','world-dynasty-18c.json',
                      'world-1762.json','atlas.json','canonical_person_id',
                      'person_facts','ethnic_origin','reference_checked',
                      'personal_union','co_regency','imperial_succession',
                      'popstate','Escape','aria-modal','aria-pressed',
                      'history[push?', 'dynasty-year-range','dynasty-graph-scroll',
                      'role_kind','colorMode'):
            self.assertIn(token,code)
        self.assertIn('dynasty-atlas.js', (ROOT/'scripts/soviet_audit.py').read_text())
        self.assertIn('world-dynasty-18c.json', (ROOT/'scripts/soviet_audit.py').read_text())
        self.assertIn('.dynasty-layer[hidden]{display:none!important}',css)
        self.assertIn('atlas-world-network-link',site)
        self.assertNotIn('1000428575.jpg',code)
        self.assertNotIn('drive.google.com',code)
        if shutil.which('node'):
            subprocess.run(['node','--check',str(ROOT/'site/dynasty-atlas.js')],
                           check=True,capture_output=True)


if __name__=='__main__':
    unittest.main()
