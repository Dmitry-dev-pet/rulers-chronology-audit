"""House-by-state timelines: only sourced dynasty membership can create bars."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

from scripts import atlas_db

ROOT=Path(__file__).resolve().parents[1]
def read(name):
    return json.loads((ROOT/'data/atlas/world-pilots'/name).read_text(encoding='utf-8'))

class HouseFootprintsContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.houses=read('dynasty-footprints-1762-1800.json')
        cls.base=read('1762.json')
        cls.old=read('dynasty-1762-1780.json')
        cls.ext=read('extension-1781-1800.json')
        cls.atlas=atlas_db.load(ROOT)
        cls.people={x['id']:x for x in (
            cls.base['persons']+cls.old['additional_persons']+
            cls.ext['additional_persons'])}
        cls.roles=cls.old['roles']+cls.ext['additional_roles']
        cls.families={h['id']:h for h in cls.houses['families']}

    def role_states(self,house,year,include_lineage=False,include_secondary=False):
        out=[]
        for member in self.families[house]['members']:
            if member['membership']=='branch_lineage' and not include_lineage:continue
            if member['membership']=='dynastic_union' and not include_secondary:continue
            for role in self.roles:
                if role['person_id']!=member['person_id'] or not role['start_year']<=year<=role['end_year']:continue
                if role['role_kind'] not in ({'sovereign','elector','emperor','co_regent','consort','regent','heir','dynastic_person'} if include_secondary else {'sovereign','elector'}):continue
                if not include_secondary and role['polity_id'] in {'hre','meck','frrep'}:continue
                out.append((role['polity_id'],role['person_id'],role['role_kind']))
        return out

    def test_source_data_completeness_and_scope(self):
        self.assertEqual(self.houses['schema_version'],'dynasty-footprints-v1')
        self.assertEqual(self.houses['period'],{'start':1762,'end':1800})
        self.assertFalse(self.houses['historical_truth_verified_by_ci'])
        self.assertEqual(set(self.families),
                         {'bourbon','habsburg-lorraine','hanover','holstein-gottorp'})
        self.assertEqual([len(h['members']) for h in self.houses['families']],[6,6,1,5])
        self.assertEqual(len(self.atlas['people']),83)
        self.assertEqual(len(self.atlas['tenures']),97)
        self.assertEqual(len(self.atlas['provenance']),150)
        self.assertEqual(self.houses['role_policy']['ruling'],['sovereign','elector'])
        self.assertEqual(self.houses['role_policy']['context_excluded_from_states'],
                         ['hre','meck','frrep'])
        all_sources={s['id'] for s in (self.base['sources']+self.old['sources']+
            self.ext['sources']+self.houses['sources']+self.atlas['sources'])}
        for family in self.houses['families']:
            self.assertTrue(set(family['source_ids'])<=all_sources)
            for member in family['members']:
                self.assertIn(member['person_id'],self.people)
                self.assertTrue(member['branch'])
                self.assertTrue(member['source_ids'])
                self.assertTrue(set(member['source_ids'])<=all_sources)
                self.assertTrue(any(r['person_id']==member['person_id'] for r in self.roles))
                self.assertIn(member['membership'],{'house','dynastic_union','branch_lineage'})
        for source in self.houses['sources']:
            self.assertTrue(source['url'].startswith('https://'))
            self.assertEqual(source['verification'],'reference_checked')

    def test_1788_house_overlaps_are_different_relationships(self):
        bourbon=self.role_states('bourbon',1788)
        self.assertEqual({r[0] for r in bourbon},{'fr','es'})
        self.assertEqual({r[1] for r in bourbon},
                         {'fr-louis16','es-carlos3','es-carlos4'})
        habsburg=self.role_states('habsburg-lorraine',1788)
        self.assertEqual({r[0] for r in habsburg},{'hab','tusc'})
        self.assertEqual({r[1] for r in habsburg},{'hre-joseph','hab-leopold'})
        hanover=self.role_states('hanover',1788)
        self.assertEqual({x[0] for x in hanover},{'gb','han'})
        self.assertEqual({x[1] for x in hanover},{'gb-george3'})
        # One physical monarch in two jurisdictions is a PERSONAL UNION, not
        # two rulers of the same dynasty.
        self.assertEqual(len(hanover),2)

    def test_russian_swedish_branch_source_not_fake_house_or_ethnicity(self):
        paul=next(m for m in self.families['holstein-gottorp']['members']
                  if m['person_id']=='ru-paul1')
        self.assertEqual(paul['membership'],'branch_lineage')
        self.assertIn('Романов',paul['branch'])
        original_houses=self.people['ru-paul1']['houses']
        self.assertEqual([x['id'] for x in original_houses],['romanov'])
        self.assertEqual([x['person_id'] for x in self.houses['families'][3]['members']
                          if x['membership']=='branch_lineage'],['ru-paul1'])
        self.assertEqual({r[0] for r in self.role_states('holstein-gottorp',1798)},
                         {'sw'})
        self.assertEqual({r[0] for r in self.role_states('holstein-gottorp',1798,
                                                       include_lineage=True)},
                         {'sw','ru'})
        self.assertEqual({r[0] for r in self.role_states('holstein-gottorp',1795,
                                                       include_lineage=True)},
                         {'sw'})
        self.assertTrue(all(not p.get('ethnic_origin_fact_id')
                        for p in (self.people['ru-paul1'],self.people['sw-gustav4'])))

    def test_consorts_not_political_control_and_after_1792_france_changes(self):
        self.assertEqual({x[0] for x in self.role_states('bourbon',1795)}, {'es'})
        self.assertEqual({x[0] for x in self.role_states('habsburg-lorraine',1780)},
                         {'hab'})
        with_secondary=self.role_states('habsburg-lorraine',1788,include_secondary=True)
        self.assertTrue(any(p=='fr-antoinette' and kind=='consort'
                            for _,p,kind in with_secondary))
        self.assertNotIn('fr',{x[0] for x in self.role_states('habsburg-lorraine',1788)})
        extra_bourbons=self.role_states('bourbon',1798,include_secondary=True)
        self.assertTrue(any(state=='pt' and role=='consort'
                            for state,_,role in extra_bourbons))
        self.assertNotIn('pt',{x[0] for x in self.role_states('bourbon',1798)})
        # The Holy Roman Imperial office never counts as another sovereign
        # country in the primary comparison.
        self.assertNotIn('hre',{x[0] for x in self.role_states('habsburg-lorraine',1788)})

    def test_technical_contract_and_privacy(self):
        code=(ROOT/'site/dynasty-atlas.js').read_text(encoding='utf-8')
        css=(ROOT/'site/site.css').read_text(encoding='utf-8')
        builder=(ROOT/'scripts/soviet_audit.py').read_text(encoding='utf-8')
        for term in ('dynView','houses','segmentsForHouse','summaryForHouse',
                     'dynasty-footprint-scroll','world-house-footprints.json',
                     'branch_lineage','dynastic_union','showSecondary','footprintDetail',
                     'renderFootprints','source_ids','FOOTPRINT_YEARS'):
            self.assertIn(term,code)
        for term in ('.dynasty-person-graph-panel[hidden]',
                     '.dynasty-house-bar[data-category="lineage"]',
                     '.dynasty-house-sticky-label'):
            self.assertIn(term,css)
        self.assertIn('world-house-footprints.json',builder)
        self.assertNotIn('1000428575.jpg',code)
        self.assertNotIn('drive.google.com',code)
        if shutil.which('node'):
            subprocess.run(['node','--check',str(ROOT/'site/dynasty-atlas.js')],
                           check=True,capture_output=True)

if __name__=='__main__':unittest.main()
