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

    def test_five_places_eighteen_mapped_and_one_unlocated(self):
        d=smuta_map.prepare(self.registry,self.dossier,self.atlas)
        self.assertEqual(len(d['places']),5)
        self.assertEqual(sum(len(p['evidence_ids']) for p in d['places']),18)
        self.assertEqual(len(d['unlocated']),1)
        self.assertEqual(d['unlocated'][0]['evidence_id'],'local-smuta-severian-claim-1608')
        self.assertIs(d['historical_borders_verified'],False)
        self.assertEqual(len(d['events']),16)
        self.assertEqual(len(d['evidence']),19)
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

    def test_city_by_year_coverage_counts_are_derived_from_sources(self):
        d=smuta_map.prepare(self.registry,self.dossier,self.atlas,self.hydro)
        coverage=d["research_coverage"]
        self.assertEqual(coverage["years"],list(range(1598,1614)))
        self.assertEqual(len(coverage["places"]),5)
        self.assertEqual(sum(len(place["cells"]) for place in coverage["places"]),80)
        self.assertEqual(coverage["filled_city_years"],12)
        self.assertEqual(coverage["research_gap_city_years"],68)
        self.assertEqual(coverage["mapped_evidence_count"],18)
        self.assertEqual(coverage["mapped_precise_month_count"],14)
        self.assertEqual(coverage["unlocated_evidence_ids"],
                         ["local-smuta-severian-claim-1608"])
        self.assertEqual(len(d["evidence"]),19)
        mapped_ids={id for place in coverage["places"]
                    for cell in place["cells"] for id in cell["evidence_ids"]}
        self.assertEqual(len(mapped_ids),18)
        original={e["id"]:e for e in d["evidence"]}
        for place in coverage["places"]:
            for cell in place["cells"]:
                self.assertEqual(cell["research_gap"],not bool(cell["evidence_ids"]))
                self.assertEqual(cell["known_months"],sorted({
                    int(original[eid]["date"]["value"][5:7])
                    for eid in cell["evidence_ids"]
                    if original[eid]["date"]["precision"] in {"month","day"}
                }))
                self.assertEqual(cell["year_only_ids"],[
                    eid for eid in cell["evidence_ids"]
                    if original[eid]["date"]["precision"]=="year"
                ])

    def test_1610_moscow_july_august_october_and_undated_years(self):
        d=smuta_map.prepare(self.registry,self.dossier,self.atlas,self.hydro)
        places={p["place_id"]:p for p in d["research_coverage"]["places"]}
        moscow=next(c for c in places["moscow"]["cells"] if c["year"]==1610)
        self.assertEqual(moscow["known_months"],[7,8,10])
        self.assertEqual(len(moscow["evidence_ids"]),3)
        self.assertEqual(moscow["year_only_ids"],[])
        april_1612=next(c for c in places["yaroslavl"]["cells"] if c["year"]==1612)
        self.assertEqual(april_1612["known_months"],[4])
        year_1608=next(c for c in places["yaroslavl"]["cells"] if c["year"]==1608)
        self.assertEqual(year_1608["known_months"],[])
        self.assertEqual(len(year_1608["year_only_ids"]),1)
        no_1611=next(c for c in places["yaroslavl"]["cells"] if c["year"]==1611)
        self.assertTrue(no_1611["research_gap"])
        self.assertFalse(no_1611["evidence_ids"])
        self.assertIn("не отсутствие власти",d["research_coverage"]["precision_policy"])

    def test_four_source_backed_city_years_are_newly_documented(self):
        data=smuta_map.prepare(self.registry,self.dossier,self.atlas,self.hydro)
        places={p["place_id"]:p for p in data["research_coverage"]["places"]}
        evidence={r["id"]:r for r in data["evidence"]}
        expected={
            ("yaroslavl",1609):("local-smuta-yaroslavl-uprising-1609","1609-04","julian","practice",["SL01","SL03"]),
            ("tushino",1609):("local-smuta-tushino-flight-1609","1609-12","julian","practice",["SL02","SL03"]),
            ("moscow",1611):("local-smuta-moscow-uprising-1611","1611-03","unspecified","military",["TJ15"]),
            ("nizhny-novgorod",1612):("local-smuta-nizhny-departure-1612","1612","unspecified","practice",["TJ06","TJ07","SL05"]),
        }
        for (place,year),(eid,date,calendar,nature,sources) in expected.items():
            with self.subTest(place=place,year=year):
                cell=next(c for c in places[place]["cells"] if c["year"]==year)
                self.assertFalse(cell["research_gap"])
                self.assertIn(eid,cell["evidence_ids"])
                fact=evidence[eid]
                self.assertEqual(fact["date"]["value"],date)
                self.assertEqual(fact["date"]["calendar"],calendar)
                self.assertEqual(fact["sources"],sources)
                self.assertEqual(fact["nature"],nature)
                self.assertIs(fact["geometry_verified"],False)
                self.assertTrue(fact["limitation"])
                self.assertTrue(fact["related_event_ids"])
        feb=next(c for c in places["nizhny-novgorod"]["cells"] if c["year"]==1612)
        self.assertEqual(feb["known_months"],[])
        self.assertEqual(feb["year_only_ids"],["local-smuta-nizhny-departure-1612"])
        self.assertIn("марта",evidence["local-smuta-nizhny-departure-1612"]["limitation"])
        self.assertEqual(data["research_coverage"]["research_gap_city_years"],68)
        self.assertEqual(data["research_coverage"]["filled_city_years"],12)
        self.assertEqual(len(data["unlocated"]),1)

    def test_1609_1611_detailed_month_sequence_without_claiming_whole_city(self):
        data=smuta_map.prepare(self.registry,self.dossier,self.atlas,self.hydro)
        coverage={p["place_id"]:p for p in data["research_coverage"]["places"]}
        facts={f["id"]:f for f in data["evidence"]}
        events={e["id"]:e for e in data["events"]}
        samples={
            ("yaroslavl",1609):([
                ("local-smuta-yaroslavl-exactions-1609","1609-01","unspecified","practice","smuta-1609-january","SL01"),
                ("local-smuta-yaroslavl-uprising-1609","1609-04","julian","practice",None,"SL01"),
                ("local-smuta-yaroslavl-posad-burning-1609","1609-05","julian","military","smuta-1609-may","SL01"),
            ],[1,4,5]),
            ("moscow",1611):([
                ("local-smuta-moscow-uprising-1611","1611-03","unspecified","military",None,"TJ15"),
                ("local-smuta-moscow-white-city-1611","1611-04","unspecified","military","smuta-1611-april","SS01"),
                ("local-smuta-moscow-opolchenie-judgment-1611","1611-06","unspecified","law","smuta-1611-june","SS02"),
            ],[3,4,6]),
        }
        for (city,year),(entries,months) in samples.items():
            with self.subTest(city=city,year=year):
                cell=next(c for c in coverage[city]["cells"] if c["year"]==year)
                self.assertEqual(cell["known_months"],months)
                self.assertEqual(len(cell["evidence_ids"]),3)
                self.assertEqual(cell["year_only_ids"],[])
                for eid,value,calendar,nature,event,source in entries:
                    fact=facts[eid]
                    self.assertEqual(fact["date"]["value"],value)
                    self.assertEqual(fact["date"]["calendar"],calendar)
                    self.assertEqual(fact["nature"],nature)
                    self.assertIn(source,fact["sources"])
                    self.assertIs(fact["geometry_verified"],False)
                    self.assertIn("не",fact["limitation"].lower())
                    if event:
                        self.assertIn(event,events)
                        self.assertIn(event,fact["related_event_ids"])
                        self.assertIn(source,events[event]["sources"])
        june=facts["local-smuta-moscow-opolchenie-judgment-1611"]
        self.assertEqual(june["place_kind"],"vicinity_of_city")
        self.assertIn("под Москвой",june["statement"])
        self.assertIn("не о функционировании",june["limitation"])
        self.assertIs(data["historical_borders_verified"],False)
        self.assertEqual(len(data["events"]),16)
        self.assertEqual(len(data["evidence"]),19)
        self.assertEqual(data["research_coverage"]["filled_city_years"],12)
        self.assertEqual(data["research_coverage"]["research_gap_city_years"],68)
        self.assertEqual(data["research_coverage"]["mapped_evidence_count"],18)
        self.assertEqual(data["research_coverage"]["mapped_precise_month_count"],14)
        self.assertEqual(len(data["unlocated"]),1)

    def test_calendar_ui_contract_does_not_promote_year_only_to_month(self):
        code=(ROOT/"site/smuta-map.js").read_text(encoding="utf-8")
        css=(ROOT/"site/smuta-map.css").read_text(encoding="utf-8")
        for phrase in (
            "smuta-month", "smuta-month-unknown", "Месяц не установлен",
            "year_only_ids", "smuta-mode-matrix", "smuta-matrix-cell",
            "research_gap_city_years", "monthKey(", "exactMonth(",
            "date.precision!=='year'", "monthNames[selectedMonth]",
            "aria-current", "research_gap"
        ):
            self.assertIn(phrase,code)
        self.assertIn(".smuta-matrix-scroll",css)
        self.assertIn(".smuta-month-select",css)

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
