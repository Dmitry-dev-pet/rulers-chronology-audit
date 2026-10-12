"""Coverage counts mean database entries, NEVER complete historical research."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

from scripts import atlas_db, europe_coverage

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'data/atlas/world-pilots'
def load(name):
    return json.loads((SOURCE/name).read_text(encoding='utf-8'))


class CoverageMatrixContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy=load('coverage-1762-1800.json')
        cls.base=load('1762.json')
        cls.old=load('dynasty-1762-1780.json')
        cls.ext=load('extension-1781-1800.json')
        cls.patch=load('coverage-backfill-1762-1800.json')
        cls.people=atlas_db.load(ROOT)
        cls.policies={p['polity_id']:p for p in cls.policy['polities']}
        cls.roles=cls.old['roles']+cls.ext['additional_roles']+cls.patch['role_additions']
        cls.institutions=cls.ext['institutions']

    @classmethod
    def classify(cls,polity_id,year):
        p=cls.policies[polity_id]
        roles=[r for r in cls.roles if r['polity_id']==polity_id and
               r['start_year']<=year<=r['end_year']]
        inst=[x for x in cls.institutions if x['polity_id']==polity_id and
              x['start_year']<=year<=x['end_year']]
        if p.get('display_only')=='birthplace_context':
            return 'birthplace_context'
        if (p.get('historical_start') and year<p['historical_start']) or (
                p.get('historical_end') and year>p['historical_end']):
            return 'historically_not_in_force'
        if (year<p['researched_from'] or year>p['researched_through']) and not roles and not inst:
            return 'outside_sample'
        if any(r['role_kind'] in {'sovereign','elector','emperor'} for r in roles):
            return 'office'
        if inst:return 'institution'
        if roles:return 'supplementary'
        return 'research_gap'

    def test_thirteen_unique_contexts_and_source_qualified_windows(self):
        p=self.policy
        self.assertEqual(p['schema_version'],'coverage-matrix-v1')
        self.assertFalse(p['historical_truth_verified_by_ci'])
        self.assertFalse(p['historical_borders_verified'])
        self.assertEqual(p['period'],{'start':1762,'end':1800})
        self.assertEqual(len(p['polities']),13)
        self.assertEqual(len(self.policies),13)
        previous={x['id'] for x in self.base['countries']+
            self.old['additional_polities']+self.ext['additional_polities']}
        self.assertEqual(set(self.policies),previous)
        self.assertEqual(len(self.people['people']),83)
        self.assertEqual(len(self.people['tenures']),97)
        self.assertEqual(len(self.people['provenance']),150)
        sources={x['id'] for x in self.base['sources']+
            self.old['sources']+self.ext['sources']+
            p['sources']+self.patch['source_records']+self.people['sources']}
        for row in p['polities']:
            self.assertTrue(1762<=row['researched_from']<=row['researched_through']<=1800)
            self.assertTrue(row['source_ids'])
            self.assertLessEqual(set(row['source_ids']),sources)
            self.assertIn('note',row)
        for task in p['known_research_tasks']:
            self.assertIn(task['polity_id'],self.policies)
            self.assertLessEqual(set(task['source_ids']),sources)
            self.assertLessEqual(task['start_year'],task['end_year'])
        for source in p['sources']:
            self.assertTrue(source['url'].startswith('https://'))
            self.assertEqual(source['verification'],'reference_checked')

    def test_historical_end_is_not_research_gap(self):
        self.assertEqual(self.policies['fr']['historical_end'],1792)
        self.assertEqual(self.policies['frrep']['historical_start'],1792)
        self.assertEqual(self.classify('fr',1792),'office')
        self.assertEqual(self.classify('frrep',1792),'institution')
        self.assertEqual(self.classify('fr',1793),'historically_not_in_force')
        self.assertEqual(self.classify('fr',1800),'historically_not_in_force')
        self.assertEqual(self.classify('frrep',1762),'historically_not_in_force')
        self.assertEqual(self.classify('frrep',1791),'historically_not_in_force')
        self.assertEqual(self.classify('frrep',1799),'institution')
        self.assertEqual(self.classify('frrep',1800),'institution')
        self.assertTrue(any(x['id']=='ex-fr-consulate' for x in self.institutions))
        self.assertFalse(any(r['role_kind']=='emperor' and
                    r['polity_id']=='frrep' for r in self.roles))

    def test_research_scope_not_historical_absence(self):
        for key in ('es','pt','sw','tusc'):
            self.assertEqual(self.policies[key]['researched_from'],1762)
            for y in (1762,1774,1780):
                self.assertEqual(self.classify(key,y),'office')
        self.assertEqual(self.classify('es',1781),'office')
        self.assertEqual(self.classify('es',1788),'office')
        self.assertEqual(self.classify('pt',1799),'office')
        self.assertEqual(self.classify('sw',1792),'office')
        self.assertEqual(self.classify('meck',1795),'birthplace_context')
        self.assertNotEqual(self.policies['meck']['classification'],'королевство')
        self.assertEqual(self.classify('han',1800),'office')
        self.assertEqual(self.classify('hre',1800),'office')

    def test_tuscany_gap_cannot_be_misrepresented_as_no_ruler(self):
        self.assertEqual(self.classify('tusc',1790),'office')
        for year in range(1791,1800):
            self.assertEqual(self.classify('tusc',year),'office')
        self.assertEqual(self.classify('tusc',1800),'research_gap')
        self.assertIn('Фердинанд',self.policies['tusc']['note'])
        gap=next(x for x in self.policy['known_research_tasks']
                 if x['id']=='coverage-tuscany-1800')
        self.assertEqual(gap['priority'],'high')
        self.assertIn('CV02',gap['source_ids'])
        self.assertEqual((gap['start_year'],gap['end_year']),(1800,1800))
        self.assertIn('ferdinand-iii-tuscany',
                      next(s['url'] for s in self.policy['sources'] if s['id']=='CV02'))
        # Separate sourced early roles do not assert continuous rule in 1800.
        self.assertTrue(any(x['person_id']=='tusc-ferdinand3' for x in self.roles))
        self.assertFalse(any(x['person_id']=='tusc-ferdinand3' and
                             x['end_year']>=1800 for x in self.roles))

    def test_exact_status_totals_and_no_false_completeness_metric(self):
        counts={}
        gaps=[]
        for key in self.policies:
            for year in range(1762,1801):
                status=self.classify(key,year)
                counts[status]=counts.get(status,0)+1
                if status=='research_gap':
                    gaps.append((key,year))
        self.assertEqual(sum(counts.values()),13*39)
        self.assertEqual(counts,{
            'office':420,'historically_not_in_force':38,
            'institution':9,'research_gap':1,'birthplace_context':39
        })
        self.assertEqual(gaps,[('tusc',1800)])
        self.assertIn('не измеряют полноту',
           (ROOT/'site/dynasty-atlas.js').read_text(encoding='utf-8'))

    def test_python_audit_agrees_with_cell_classification(self):
        projection=europe_coverage.coverage()
        self.assertEqual(projection['schema_version'],'europe-coverage-v2')
        self.assertFalse(projection['completeness_established'])
        self.assertFalse(projection['historical_truth_verified_by_ci'])
        self.assertEqual(len(projection['states']),13)
        self.assertEqual(projection['status_counts'],{
            'office':420,'institution':9,'research_gap':1,
            'historically_not_in_force':38,
            'birthplace_context':39
        })
        for state in projection['states']:
            self.assertEqual(len(state['years']),39)
            for cell in state['years']:
                self.assertEqual(cell['status'],
                    self.classify(state['polity_id'],cell['year']))
                self.assertTrue(cell['source_ids'])
        tusc=next(s for s in projection['states'] if s['polity_id']=='tusc')
        self.assertEqual([x['year'] for x in tusc['years']
                          if x['status']=='research_gap'],
                         [1800])
        # Unit test does not write the derived projection back to sources.

    def test_spa_deep_link_mobile_privacy_and_existing_modes(self):
        script=(ROOT/'site/dynasty-atlas.js').read_text(encoding='utf-8')
        css=(ROOT/'site/site.css').read_text(encoding='utf-8')
        build=(ROOT/'scripts/soviet_audit.py').read_text(encoding='utf-8')
        for part in ('dynView','coverage','coverageFor','renderCoverage',
                     'renderCoverageDetail','world-coverage-1800.json',
                     'historically_not_in_force','research_gap',
                     'birthplace_context','researched_from','source_ids',
                     'coverageScroll','history[push?', 'renderFootprints'):
            self.assertIn(part,script)
        self.assertIn('.dynasty-coverage-scroll',css)
        self.assertIn('.dynasty-coverage-sticky',css)
        self.assertIn('world-coverage-1800.json',build)
        self.assertNotIn('drive.google.com',script)
        self.assertNotIn('1000428575.jpg',script)
        if shutil.which('node'):
            subprocess.run(['node','--check',str(ROOT/'site/dynasty-atlas.js')],
                           capture_output=True,check=True)


if __name__=='__main__':
    unittest.main()
