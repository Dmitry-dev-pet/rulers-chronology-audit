"""European 1781–1800 extension: roles, institutions and sourced identities."""
import json
import unittest
from pathlib import Path
from scripts import atlas_db

ROOT=Path(__file__).resolve().parents[1]
PILOT=json.loads((ROOT/'data/atlas/world-pilots/1762.json').read_text())
ORIGINAL=json.loads((ROOT/'data/atlas/world-pilots/dynasty-1762-1780.json').read_text())
EXT=json.loads((ROOT/'data/atlas/world-pilots/extension-1781-1800.json').read_text())


class European1800Contract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db=atlas_db.load(ROOT)
        cls.persons={p['id']:p for p in [
            *PILOT['persons'],*ORIGINAL['additional_persons'],*EXT['additional_persons']]}
        cls.roles=[*ORIGINAL['roles'],*EXT['additional_roles']]
        cls.states={p['id']:p for p in [
            *PILOT['countries'],*ORIGINAL['additional_polities'],*EXT['additional_polities']]}
        cls.sources={s['id']:s for s in [
            *PILOT['sources'],*ORIGINAL['sources'],*EXT['sources'],*cls.db['sources']]}

    def at(self,year):
        return [r for r in self.roles if r['start_year']<=year<=r['end_year']]

    def institutions_at(self,year):
        return [r for r in EXT['institutions'] if r['start_year']<=year<=r['end_year']]

    def test_append_only_scope_and_counts(self):
        self.assertEqual(EXT['schema_version'],'dynasty-extension-v1')
        self.assertEqual(EXT['base_pilot'],'dynasty-network-v1')
        self.assertEqual(EXT['full_period'],{'start':1762,'end':1800})
        self.assertEqual(EXT['additional_coverage'],{'start':1781,'end':1800})
        self.assertFalse(EXT['historical_truth_verified_by_ci'])
        self.assertFalse(EXT['historical_borders_verified'])
        self.assertEqual(len(EXT['additional_polities']),5)
        self.assertEqual(len(EXT['additional_persons']),16)
        self.assertEqual(len(EXT['additional_roles']),22)
        self.assertEqual(len(EXT['institutions']),3)
        self.assertEqual(len(EXT['additional_relations']),16)
        self.assertEqual(len(EXT['sources']),17)
        self.assertEqual(len(EXT['milestones']),11)
        self.assertEqual(len(self.states),13)
        self.assertEqual(len(self.persons),28)
        self.assertEqual(len(self.roles),40)
        self.assertEqual(len(self.db['people']),83)
        self.assertEqual(len(self.db['tenures']),97)
        self.assertEqual(len(self.db['provenance']),150)
        self.assertEqual(set(p['id'] for p in PILOT['countries']),{'ru','fr','pr'})
        self.assertEqual(ORIGINAL['period']['end'],1780)
        self.assertEqual(ORIGINAL['schema_version'],'dynasty-network-v1')

    def test_not_backfill_unknown_states_before_1781(self):
        self.assertTrue(all(p['introduced_from']>=1781
                            for p in EXT['additional_polities']))
        self.assertTrue(all(r['start_year']>=1781
                            for r in EXT['additional_roles']))
        self.assertTrue(all(i['start_year']>=1792
                            for i in EXT['institutions']))
        earlier=[r for r in self.at(1762) if r in EXT['additional_roles']]
        self.assertEqual(earlier,[])
        self.assertEqual({p['id'] for p in EXT['additional_polities']},
                         {'es','pt','sw','tusc','frrep'})
        self.assertEqual(self.states['frrep']['introduced_from'],1792)
        self.assertEqual(self.states['tusc']['kind'],'grand_duchy')

    def test_id_and_source_references(self):
        for array in (EXT['additional_persons'],EXT['additional_roles'],
                      EXT['additional_relations'],EXT['institutions']):
            ids=[r['id'] for r in array]
            self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual(len(self.persons),28)
        self.assertEqual(len(self.states),13)
        for row in EXT['additional_roles']:
            self.assertIn(row['person_id'],self.persons)
            self.assertIn(row['polity_id'],self.states)
            self.assertLessEqual(row['start_year'],row['end_year'])
            self.assertTrue(row['source_ids'])
            self.assertLessEqual(set(row['source_ids']),set(self.sources))
        for row in [*EXT['institutions'],*EXT['additional_relations'],
                    *EXT['milestones'],*EXT['additional_polities']]:
            self.assertTrue(row['source_ids'])
            self.assertLessEqual(set(row['source_ids']),set(self.sources))
        for row in EXT['additional_relations']:
            self.assertLessEqual(set(row['subjects']),set(self.persons))
        self.assertTrue(all(s['url'].startswith('https://') and
                            s['verification']=='reference_checked'
                            for s in EXT['sources']))

    def test_russian_paul_uses_canonical_ids(self):
        paul=self.persons['ru-paul1']
        self.assertEqual(paul['canonical_person_id'],'person-14b51b51093f55ce')
        self.assertEqual(paul['canonical_tenure_id'],'tenure-r13')
        row=next(r for r in self.db['tenures'] if r['id']=='tenure-r13')
        self.assertEqual(row['person_id'],paul['canonical_person_id'])
        self.assertIn('Павел',next(p['name'] for p in self.db['people']
                                  if p['id']==paul['canonical_person_id']))
        russian={r['person_id'] for r in self.at(1796) if r['polity_id']=='ru'}
        self.assertEqual(russian,{'ru-catherine2','ru-paul1'})

    def test_monarchy_and_republic_are_separate_entities(self):
        self.assertEqual(self.states['frrep']['kind'],'republic')
        self.assertEqual(self.states['fr']['id'],'fr')
        self.assertEqual({r['person_id'] for r in self.at(1791) if r['polity_id']=='fr'
                          and r['role_kind']=='sovereign'},{'fr-louis16'})
        self.assertTrue(any(r['id']=='dn-fr-louis16' for r in self.at(1792)))
        self.assertFalse(any(r['polity_id']=='fr' for r in self.at(1793)))
        self.assertEqual({x['name'] for x in self.institutions_at(1792)},
                         {'Национальный конвент'})
        self.assertEqual({x['name'] for x in self.institutions_at(1795)},
                         {'Национальный конвент','Директория'})
        self.assertEqual({x['name'] for x in self.institutions_at(1799)},
                         {'Директория','Консульство'})
        self.assertEqual({x['name'] for x in self.institutions_at(1800)},
                         {'Консульство'})
        napoleon=[r for r in self.at(1800) if r['person_id']=='fr-napoleon']
        self.assertEqual({r['role_kind'] for r in napoleon},{'first_consul'})
        self.assertFalse(any(r['role_kind']=='emperor' for r in napoleon))

    def test_swedish_regent_and_portuguese_consorts(self):
        sw92=[r for r in self.at(1792) if r['polity_id']=='sw']
        self.assertEqual({r['person_id'] for r in sw92},
                         {'sw-gustav3','sw-gustav4','sw-charles'})
        self.assertEqual({r['role_kind'] for r in sw92},
                         {'sovereign','regent'})
        self.assertFalse(any(r['person_id']=='sw-charles'
                             for r in self.at(1797)))
        pt85=[r for r in self.at(1785) if r['polity_id']=='pt']
        self.assertTrue(any(r['person_id']=='pt-maria1' and
                            r['role_kind']=='sovereign' for r in pt85))
        self.assertTrue(any(r['person_id']=='pt-pedro3' and
                            r['role_kind']=='consort' for r in pt85))
        self.assertTrue(any(r['person_id']=='pt-carlota' and
                            r['role_kind']=='consort' for r in pt85))
        pt99=[r for r in self.at(1799) if r['polity_id']=='pt']
        self.assertTrue(any(r['person_id']=='pt-joao' and
                            r['role_kind']=='regent' for r in pt99))
        self.assertFalse(any(r['person_id']=='pt-pedro3' for r in pt99))
        self.assertIn('1799',next(r['note'] for r in pt99
                           if r['person_id']=='pt-joao'))

    def test_habsburg_imperial_titles_not_austria_after_1792(self):
        hre90={r['person_id'] for r in self.at(1790)
               if r['polity_id']=='hre'}
        self.assertEqual(hre90,{'hre-joseph','hab-leopold'})
        hre92={r['person_id'] for r in self.at(1792)
               if r['polity_id']=='hre'}
        self.assertEqual(hre92,{'hab-leopold','hab-francis2'})
        self.assertEqual({r['person_id'] for r in self.at(1800)
                          if r['polity_id']=='hre'},{'hab-francis2'})
        self.assertFalse(any(r['polity_id']=='hre' and r['person_id']=='hab-maria'
                             for r in self.roles))
        self.assertIn('1804',next(r['note'] for r in self.at(1800)
                                 if r['id']=='ex-hab-francis'))
        self.assertTrue(any(r['person_id']=='hab-maria-luisa'
                            for r in self.at(1788)))

    def test_no_ethnicity_inference_from_dynasty_state_or_birth(self):
        self.assertTrue(all(p['ethnic_origin_fact_id'] is None
                            for p in EXT['additional_persons']))
        self.assertTrue(all(not p.get('citizenship')
                            for p in EXT['additional_persons']))
        names={p['id']:p['name'] for p in EXT['additional_persons']}
        self.assertEqual(names['pt-carlota'],'Карлота Жоакина')
        self.assertEqual(next(r for r in EXT['additional_roles']
                              if r['id']=='ex-pt-carlota')['role_kind'],'consort')
        self.assertTrue(any(r['kind']=='regime_change'
                            for r in EXT['additional_relations']))
        self.assertFalse(self.db['metadata']['historical_truth_verified_by_ci'])

    def test_build_and_client_contract(self):
        js=(ROOT/'site/dynasty-atlas.js').read_text(encoding='utf-8')
        gen=(ROOT/'scripts/soviet_audit.py').read_text(encoding='utf-8')
        css=(ROOT/'site/site.css').read_text(encoding='utf-8')
        for snippet in ('world-extension-1800.json','dynasty-extension-v1',
                        'activeInstitutions','introduced_from',
                        'institutional_change','regime_change',
                        'first_consul','dynYear','1800'):
            self.assertIn(snippet,js)
        self.assertIn('world-extension-1800.json',gen)
        self.assertIn('.dynasty-institution',css)
        self.assertNotIn('1000428575.jpg',js)
        self.assertNotIn('drive.google.com/file/d/',js)
        import shutil,subprocess
        if shutil.which('node'):
            subprocess.run(['node','--check',str(ROOT/'site/dynasty-atlas.js')],
                           capture_output=True,check=True)


if __name__=='__main__':
    unittest.main()
