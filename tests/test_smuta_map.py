"""Modern place anchors must never become historical territorial geometry."""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from scripts import atlas_db, transition_cases, smuta_map

ROOT=atlas_db.ROOT

class SmutaMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry=json.loads((ROOT/smuta_map.REGISTRY).read_text(encoding='utf-8'))
        cls.hydro=json.loads((ROOT/smuta_map.HYDROGRAPHY).read_text(encoding='utf-8'))
        cls.atlas=atlas_db.load(ROOT)
        cls.dossier=transition_cases.load(ROOT,cls.atlas)

    def test_five_places_ten_mapped_and_one_unlocated(self):
        d=smuta_map.prepare(self.registry,self.dossier,self.atlas)
        self.assertEqual(len(d['places']),5)
        self.assertEqual(sum(len(p['evidence_ids']) for p in d['places']),10)
        self.assertEqual(len(d['unlocated']),1)
        self.assertEqual(d['unlocated'][0]['evidence_id'],'local-smuta-severian-claim-1608')
        self.assertIs(d['historical_borders_verified'],False)
        self.assertEqual(len(d['events']),12)
        self.assertEqual(len(d['evidence']),11)
        self.assertEqual(d['hydrography']['kind'],'modern_hydrography_reference')
        self.assertGreaterEqual(len(d['hydrography']['rivers']),15)
        self.assertEqual({r['name'] for r in d['hydrography']['rivers']
                          if r['name'] in {'Volga','Oka'}},{'Volga','Oka'})
        self.assertTrue(all(x.get('geometry_verified') is False for x in d['evidence']))
        self.assertIn('formal_year_overlaps',d)

    def test_coordinates_are_explicit_modern_references_not_old_geometry(self):
        d=smuta_map.prepare(self.registry,self.dossier,self.atlas)
        self.assertEqual(d['coordinate_kind'],'modern_reference_only')
        for p in d['places']:
            self.assertEqual(p['point_semantics'],'modern_place_reference_not_historic_boundary')
            self.assertTrue(p['coordinate_source']['url'].startswith('https://'))
        original=self.dossier['cases'][0]['territorial_evidence']
        self.assertEqual(d['evidence'],original)
        for e in d['evidence']:
            self.assertNotIn('reference_point',e)
            self.assertIs(e['geometry_verified'],False)

    def test_mutations_rejected_without_silently_dropping_evidence(self):
        mutations=[
            lambda r:r.__setitem__('historical_borders_verified',True),
            lambda r:r['places'][0]['reference_point'].__setitem__('lat',float('nan')),
            lambda r:r['places'][0]['reference_point'].__setitem__('lat',12),
            lambda r:r['places'][0]['reference_point'].__setitem__('lon',37.5),
            lambda r:r['places'][0].__setitem__('polygon',[[1,2],[3,4]]),
            lambda r:r['places'][0]['coordinate_source'].__setitem__('url','javascript:alert(1)'),
            lambda r:r['places'][0]['evidence_ids'].append('unknown-evidence'),
            lambda r:r['places'][0]['evidence_ids'].pop(),
            lambda r:r['unlocated'].clear(),
            lambda r:r['places'][1]['evidence_ids'].append(r['places'][0]['evidence_ids'][0]),
        ]
        for change in mutations:
            with self.subTest(change=mutations.index(change)):
                registry=copy.deepcopy(self.registry);change(registry)
                with self.assertRaises(ValueError):smuta_map.prepare(registry,self.dossier,self.atlas)

    def test_modern_rivers_are_source_pinned_and_can_never_be_historical_borders(self):
        data=smuta_map.prepare(self.registry,self.dossier,self.atlas,self.hydro)
        hydro=data['hydrography']
        self.assertIs(hydro['historical_borders_verified'],False)
        self.assertIs(hydro['historical_hydrography_verified'],False)
        self.assertEqual(hydro['coordinate_system'],'EPSG:4326')
        self.assertEqual(hydro['source']['git_blob_sha'],
                         '61a0d7137a6ff1113cc259525e7479c63d5fec86')
        total=sum(len(p) for f in hydro['rivers'] for p in f['paths'])
        self.assertGreater(total,500)
        self.assertLess(total,5000)
        for mutation in [
            lambda d:d.__setitem__('historical_borders_verified',True),
            lambda d:d.__setitem__('historical_hydrography_verified',True),
            lambda d:d['source'].__setitem__('commit_sha','latest'),
            lambda d:d['rivers'][0]['paths'][0][0].__setitem__(0,100),
            lambda d:d['rivers'][0]['paths'][0][0].__setitem__(0,float('nan')),
            lambda d:d['rivers'][0].__setitem__('id',d['rivers'][1]['id']),
        ]:
            with self.subTest(mutator=str(mutation)):
                edited=copy.deepcopy(self.hydro)
                mutation(edited)
                with self.assertRaises(ValueError):
                    smuta_map.validate_hydrography(edited)

    def test_parallel_ruler_years_are_preliminary_not_claimed_daily_or_local(self):
        data=smuta_map.prepare(self.registry,self.dossier,self.atlas,self.hydro)
        terms=data['formal_year_overlaps']
        self.assertGreaterEqual(len(terms),5)
        for t in terms:
            self.assertIn(t['status'],smuta_map.FORMAL_STATUSES)
            self.assertEqual(t['person_id'].split('-')[0],'person')
            self.assertTrue(t['sources'])
            self.assertIn('verification',t)
            self.assertIn('start',t)
            self.assertIn('end',t)
        names_1605=[t['name'] for t in terms if int(t['start']['value'][:4])<=1605<=int(t['end']['value'][:4])]
        self.assertGreaterEqual(len(names_1605),2)
        # 1610 claimant Vladislav remains in history as a CLAIM, not a tsar.
        self.assertFalse(any('Владислав' in t['name'] for t in terms))

    def test_source_records_are_not_modified(self):
        before=json.dumps([self.registry,self.dossier,self.atlas,self.hydro],sort_keys=True,ensure_ascii=False)
        smuta_map.prepare(self.registry,self.dossier,self.atlas,self.hydro)
        after=json.dumps([self.registry,self.dossier,self.atlas,self.hydro],sort_keys=True,ensure_ascii=False)
        self.assertEqual(before,after)

    def test_build_is_idempotent_versioned_and_source_is_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'dist').mkdir();(root/'site').mkdir();(root/'data/cartography').mkdir(parents=True)
            shutil.copyfile(ROOT/smuta_map.REGISTRY,root/smuta_map.REGISTRY)
            shutil.copyfile(ROOT/smuta_map.HYDROGRAPHY,root/smuta_map.HYDROGRAPHY)
            for name in smuta_map.ASSETS:shutil.copyfile(ROOT/'site'/name,root/'site'/name)
            (root/'dist/atlas.json').write_text(json.dumps(self.atlas),encoding='utf-8')
            (root/'dist/transition-cases.json').write_text(json.dumps(self.dossier),encoding='utf-8')
            (root/'dist/index.html').write_text('<html><head></head><body>Atlas</body></html>')
            before=(root/smuta_map.REGISTRY).read_bytes()
            receipt=smuta_map.build(root,'fixture')
            snapshot={p.name:p.read_bytes() for p in (root/'dist').iterdir()}
            smuta_map.build(root,'fixture')
            self.assertEqual(snapshot,{p.name:p.read_bytes() for p in (root/'dist').iterdir()})
            self.assertEqual(before,(root/smuta_map.REGISTRY).read_bytes())
            self.assertEqual(receipt['places'],5)
            self.assertGreaterEqual(receipt['rivers'],15)
            published=json.loads((root/'dist/smuta-map.json').read_text())
            self.assertEqual(published['hydrography']['source']['git_blob_sha'],
                             self.hydro['source']['git_blob_sha'])
            page=(root/'dist/index.html').read_text()
            self.assertEqual(page.count('<script data-smuta-map'),1)
            self.assertEqual(page.count('<link data-smuta-map'),1)
            self.assertIn('smuta-map.js?v=',page)

if __name__=='__main__':unittest.main()
