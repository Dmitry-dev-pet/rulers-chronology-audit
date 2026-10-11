"""Geographic view: modern place points are NOT historical borders."""
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=json.loads((ROOT/'data/atlas/world-pilots/geographic-context-1762-1800.json').read_text(encoding='utf-8'))
BASE=json.loads((ROOT/'data/atlas/world-pilots/1762.json').read_text(encoding='utf-8'))
NET=json.loads((ROOT/'data/atlas/world-pilots/dynasty-1762-1780.json').read_text(encoding='utf-8'))
EXT=json.loads((ROOT/'data/atlas/world-pilots/extension-1781-1800.json').read_text(encoding='utf-8'))

class GeographicReferenceContract(unittest.TestCase):
    def test_sources_not_political_borders(self):
        self.assertEqual(DATA['schema_version'],'europe-geographic-reference-v1')
        self.assertEqual(DATA['period'],{'start':1762,'end':1800})
        self.assertFalse(DATA['historical_borders_verified'])
        self.assertFalse(DATA['historical_truth_verified_by_ci'])
        self.assertIn('no historic capitals',DATA['geography_semantics'])
        self.assertEqual(DATA['physical_outline']['dataset'],'Natural Earth 1:110m coastlines')
        self.assertEqual(DATA['physical_outline']['license'],'public domain')
        self.assertEqual(len(DATA['physical_outline']['source_blob_sha']),40)
        self.assertEqual(len(DATA['reference_cities']['source_blob_sha']),40)
        self.assertGreater(sum(map(len,DATA['physical_outline']['paths'])),350)
        self.assertGreater(len(DATA['physical_outline']['paths']),8)
        e=DATA['extent']
        for line in DATA['physical_outline']['paths']:
            self.assertGreaterEqual(len(line),2)
            for lon,lat in line:
                self.assertTrue(e['west']<=lon<=e['east'])
                self.assertTrue(e['south']<=lat<=e['north'])

    def test_references_cover_known_polities_without_territorial_inference(self):
        polities={p['id'] for p in [
            *BASE['countries'],*NET['additional_polities'],*EXT['additional_polities']]}
        anchors={p['polity_id']:p for p in DATA['anchors']}
        self.assertEqual(set(anchors),polities)
        self.assertEqual(len(DATA['anchors']),13)
        self.assertEqual(len([p for p in DATA['anchors'] if p['lon'] is not None]),12)
        self.assertIsNone(anchors['hre']['lon'])
        self.assertIsNone(anchors['hre']['lat'])
        self.assertEqual(anchors['fr']['place_id'],anchors['frrep']['place_id'])
        self.assertEqual(anchors['fr']['place_name'],'Париж')
        self.assertEqual(anchors['ru']['place_name'],'Санкт-Петербург')
        self.assertEqual(anchors['meck']['place_name'],'Шверин')
        self.assertTrue(all(
            p['source_url'].startswith('https://') and 'drive.google.com' not in p['source_url']
            for p in DATA['anchors'] if p['source_url']))
        for anchor in DATA['anchors']:
            if anchor['lon'] is None:
                self.assertIsNone(anchor['lat'])
                self.assertTrue(anchor.get('note'))
            else:
                self.assertTrue(-13<=anchor['lon']<=44)
                self.assertTrue(34<=anchor['lat']<=64)

    def test_spa_deep_link_sourced_roles_no_silent_backfill(self):
        script=(ROOT/'site/dynasty-atlas.js').read_text(encoding='utf-8')
        year=(ROOT/'site/year-view.js').read_text(encoding='utf-8')
        build=(ROOT/'scripts/soviet_audit.py').read_text(encoding='utf-8')
        publish=(ROOT/'.github/workflows/publish-pages.yml').read_text(encoding='utf-8')
        for token in ('world-geographic-1800.json','dynasty-geo-marker',
                      'renderGeography','renderGeoDetails','geoRelationArcs',
                      "return ['houses','coverage','map']",
                      'historical_borders_verified===false','alignMainYear',
                      'atlas:year-cards-ready','role_kind'):
            self.assertIn(token,script)
        self.assertIn("dynView=map#/timeline/",year)
        self.assertIn("atlas:world-open",year)
        self.assertIn('world-geographic-1800.json',build)
        self.assertIn('world-geographic-1800.json',publish)
        self.assertNotIn('guessNationality',script)
        self.assertEqual(len(NET['roles'])+len(EXT['additional_roles']),40)

if __name__=='__main__':
    unittest.main()
