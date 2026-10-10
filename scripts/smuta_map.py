#!/usr/bin/env python3
"""Build a local, dependency-free place explorer; never infer historical borders.

Run AFTER scripts.atlas_db build. Coordinates are contemporary orientation
references in a separate v1 cartographic contract, not geometry for old evidence.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import math
import re
import shutil
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = Path('data/cartography/smuta-places-v1.json')
HYDROGRAPHY = Path('data/cartography/smuta-hydrography-v1.json')
FORMAL_STATUSES = {'tsar','elected_tsar','tsar_brief','tsar_contested_identity','reigning_tsar'}
ASSETS = ('smuta-map.js', 'smuta-map.css')

def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)

def safe_url(value: str) -> bool:
    if not isinstance(value, str):
        return False
    u = urlsplit(value)
    return u.scheme == 'https' and bool(u.hostname) and not u.username and not u.password and u.hostname not in {'drive.google.com', 'docs.google.com'}

def validate_hydrography(hydro: dict) -> dict:
    """Only publicly sourced modern river polylines, never old river courses."""
    require(hydro.get('schema_version')==1 and hydro.get('kind')=='modern_hydrography_reference',
            'Unsupported hydrological reference')
    require(hydro.get('historical_borders_verified') is False
            and hydro.get('historical_hydrography_verified') is False,
            'Modern rivers cannot certify historical watercourses/borders')
    require(hydro.get('coordinate_system')=='EPSG:4326'
            and hydro.get('bounds_wsen')==[34,51.7,46,59.3],
            'Unreviewed hydrographic extent/projection')
    source=hydro.get('source',{})
    require(source.get('repository')=='nvkelso/natural-earth-vector'
            and source.get('commit_sha')=='ca96624a56bd078437bca8184e78163e5039ad19'
            and source.get('git_blob_sha')=='61a0d7137a6ff1113cc259525e7479c63d5fec86',
            'Source must remain pinned to reviewed Natural Earth version')
    require(source.get('license')=='public domain' and safe_url(source.get('url')),
            'Hydrography needs open and public source')
    rivers=hydro.get('rivers')
    require(isinstance(rivers,list) and 5<=len(rivers)<=75,
            'Missing or excessive water geometry')
    seen=set()
    names=set()
    points=0
    for river in rivers:
        rid=river.get('id')
        require(isinstance(rid,str) and re.fullmatch(r'ne10m-\d+',rid)
                and rid not in seen,'Bad/duplicate Natural Earth feature')
        seen.add(rid)
        require(isinstance(river.get('rank'),int) and 0<=river['rank']<=10,
                'Unqualified river scale')
        require(type(river.get('modern_lake_centerline')) is bool,
                'Waterways crossing modern reservoirs require label')
        require(river.get('name') is None or isinstance(river['name'],str),
                'Invalid river name')
        require(river.get('label_ru') is None or isinstance(river['label_ru'],str),
                'Unreviewed river label')
        names.add(river.get('name'))
        paths=river.get('paths')
        require(isinstance(paths,list) and paths,'River missing paths')
        for path in paths:
            require(isinstance(path,list) and 2<=len(path)<=3000,'Invalid water path')
            for xy in path:
                require(isinstance(xy,list) and len(xy)==2
                        and all(type(v) in (int,float) and math.isfinite(v) for v in xy),
                        'Invalid river point')
                lon,lat=xy
                require(33.9999<=lon<=46.0001 and 51.6999<=lat<=59.3001,
                        'Water geometry outside approved extent')
                points+=1
    require({'Volga','Oka'}<=names and points<=5000,
            'Primary Russian rivers not present or geometry too heavy')
    return hydro


def prepare(registry: dict, dossier: dict, atlas: dict, hydrography: dict | None = None) -> dict:
    """Validate explicit mappings; every observation is mapped OR unlocated."""
    require(registry.get('schema_version') == 1, 'Unsupported cartographic contract')
    require(registry.get('coordinate_kind') == 'modern_reference_only', 'Not historical geometry')
    for flag in ('historical_borders_verified', 'historical_truth_verified_by_ci'):
        require(registry.get(flag) is False, 'Do not claim verified historical borders or truth')
    require(dossier.get('historical_truth_verified_by_ci') is False, 'Dossier must retain research caveat')
    cases = [c for c in dossier['cases'] if c['id'] == registry['case_id']]
    require(len(cases) == 1 and cases[0]['id'] == 'smuta-1598-1613', 'Unresolved Smuta case')
    case = cases[0]
    hydrography=validate_hydrography(hydrography if hydrography is not None
                                    else json.loads((ROOT/HYDROGRAPHY).read_text(encoding='utf-8')))
    evidence = {e['id']: e for e in case['territorial_evidence']}
    persons = {p['id']: p for p in atlas['people']}
    sources = {s['id']: s for s in dossier['sources']}
    seen: set[str] = set()
    mapped: set[str] = set()
    require(isinstance(registry.get('places'), list) and registry['places'], 'No places')
    for place in registry['places']:
        pid = place.get('id')
        require(isinstance(pid, str) and re.fullmatch('[a-z0-9-]+', pid) and pid not in seen, 'Invalid/duplicate place ID')
        seen.add(pid)
        require(place.get('point_semantics') == 'modern_place_reference_not_historic_boundary', 'Ambiguous point semantics')
        require(isinstance(place.get('name'), str) and place['name'].strip() and isinstance(place.get('note'), str) and place['note'].strip(), 'Missing place label/caveat')
        require(not {'polygon','geometry','borders'} & place.keys(), 'Historical geometry forbidden')
        point = place.get('reference_point', {})
        require(set(point) == {'lat','lon'}, 'Expected reference point, not a polygon')
        lat, lon = point['lat'], point['lon']
        require(all(type(x) in (int,float) and math.isfinite(x) for x in (lat,lon)), 'Non-finite coordinate')
        require(50 <= lat <= 60 and 30 <= lon <= 48, 'Outside reviewed Smuta reference window')
        src = place.get('coordinate_source', {})
        require(safe_url(src.get('url')), 'Unsafe coordinate source')
        require(isinstance(src.get('title'), str) and src['title'].strip(), 'Missing coordinate source title')
        require(re.fullmatch(r'\d{4}-\d{2}-\d{2}', src.get('checked_on','')) is not None, 'Missing coordinate review date')
        for field, numeric in [('latitude_dms',lat), ('longitude_dms',lon)]:
            d = src.get(field)
            require(isinstance(d,list) and len(d)==3 and all(type(v) in (int,float) and math.isfinite(v) for v in d), 'Unreviewed DMS coordinate')
            require(0 <= d[1] < 60 and 0 <= d[2] < 60, 'Invalid DMS minutes/seconds')
            require(abs(d[0]+d[1]/60+d[2]/3600-numeric)<0.000001, 'DMS conversion mismatch')
        refs=place.get('evidence_ids')
        require(isinstance(refs,list) and refs and len(refs)==len(set(refs)) and set(refs)<=evidence.keys(), 'Unknown/duplicate evidence mapping')
        require(not set(refs)&mapped, 'One observation must not become multiple territorial claims')
        mapped.update(refs)
    unlocated=registry.get('unlocated')
    require(isinstance(unlocated,list), 'Unlocated evidence must be explicit')
    unlocated_ids=[]
    for item in unlocated:
        require(item.get('evidence_id') in evidence and isinstance(item.get('reason'),str) and item['reason'].strip(), 'Unexplained unmapped evidence')
        unlocated_ids.append(item['evidence_id'])
    require(len(unlocated_ids)==len(set(unlocated_ids)) and not set(unlocated_ids)&mapped, 'Duplicate mapped/unlocated evidence')
    require(mapped|set(unlocated_ids)==evidence.keys(), 'Dropped evidence')
    for e in evidence.values():
        require(e['geometry_verified'] is False and e['sources'] and set(e['sources'])<=sources.keys(), 'Unqualified evidence')
    require(all(safe_url(s['url']) for s in sources.values()), 'Unsafe historical citation')
    require(all(e.get('person_id') is None or e['person_id'] in persons for e in case['records']), 'Unknown biography')
    # Tenures intersect the selected YEAR only. The display never turns this
    # coarse overlap into a day-level or geographically uniform authority.
    legal=[]
    for tenure in atlas['tenures']:
        if (tenure['status'] not in FORMAL_STATUSES
                or tenure['office_id']!='tsar'
                or 'tsardom' not in tenure['state_ids']):
            continue
        a,b=int(tenure['start']['value'][:4]),int(tenure['end']['value'][:4])
        if a<=1613 and b>=1598:
            require(tenure['person_id'] in persons and set(tenure['sources']) <=
                    {x['id'] for x in atlas['sources']},'Unknown formal tenure source/person')
            legal.append({'id':tenure['id'],'person_id':tenure['person_id'],
                          'name':persons[tenure['person_id']]['name'],
                          'start':copy.deepcopy(tenure['start']),
                          'end':copy.deepcopy(tenure['end']),
                          'status':tenure['status'],'description':tenure['description'],
                          'sources':list(tenure['sources']),
                          'verification':tenure['verification']})
    all_sources={r['id']:r for r in atlas['sources']}
    added_ids={sid for tenure in legal for sid in tenure['sources']}
    merged_sources={item['id']:item for item in dossier['sources']}
    for sid in added_ids:
        if sid not in merged_sources:
            src=all_sources[sid]
            require(safe_url(src['url']),'Unsafe formal tenure source URL')
            merged_sources[sid]={'id':sid,'url':src['url'],'title':src['title'],
                                 'verification':src['verification']}
    # Copy existing claims verbatim. No new actor or territorial conclusion.
    return {
        'schema_version':1, 'historical_borders_verified':False,
        'historical_truth_verified_by_ci':False, 'coordinate_kind':'modern_reference_only',
        'title':'Смута · карта свидетельств', 'start_year':1598, 'end_year':1613,
        'places':copy.deepcopy(registry['places']), 'unlocated':copy.deepcopy(unlocated),
        'evidence':list(copy.deepcopy(evidence).values()), 'events':copy.deepcopy(case['records']),
        'formal_year_overlaps':legal,
        'hydrography':copy.deepcopy(hydrography),
        'sources':[copy.deepcopy(x) for x in merged_sources.values()],
        'people':[{'id':p['id'],'name':p['name']} for p in persons.values()],
        'method':'Точки — современные ориентиры мест. Фильтр года показывает датированные свидетельства, а не длительность контроля. Границы, маршруты и непрерывные царствования из этих точек не выводятся.'
    }

def build(root: Path = ROOT, revision: str = 'local') -> dict:
    out=root/'dist'
    require(out.is_dir() and (out/'index.html').is_file(), 'Build the full atlas first')
    registry=json.loads((root/REGISTRY).read_text(encoding='utf-8'))
    hydrography=json.loads((root/HYDROGRAPHY).read_text(encoding='utf-8'))
    dossier=json.loads((out/'transition-cases.json').read_text(encoding='utf-8'))
    atlas=json.loads((out/'atlas.json').read_text(encoding='utf-8'))
    data=prepare(registry,dossier,atlas,hydrography=hydrography)
    data['input_sha256']={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [root/REGISTRY,root/HYDROGRAPHY,out/'transition-cases.json']}
    payload=json.dumps(data,ensure_ascii=False,indent=2)+'\n'
    require('drive.google.com' not in payload and '1000428575.jpg' not in payload, 'Private content in public map')
    (out/'smuta-map.json').write_text(payload,encoding='utf-8')
    for name in ASSETS:
        shutil.copyfile(root/'site'/name,out/name)
    page=(out/'index.html').read_text(encoding='utf-8')
    require('</head>' in page and '</body>' in page,'Missing document mount')
    version=hashlib.sha256(''.join((out/name).read_text(encoding='utf-8') for name in ASSETS).encode()).hexdigest()[:12]
    # Idempotent build supports validation/rebuild without multiplying mounts.
    mounts = [
        (r'<link data-smuta-map[^>]*>',
         f"<link data-smuta-map rel='stylesheet' href='./smuta-map.css?v={version}'>", '</head>'),
        (r'<script data-smuta-map[^>]*></script>',
         f"<script data-smuta-map defer src='./smuta-map.js?v={version}'></script>", '</body>'),
    ]
    for pattern, tag, boundary in mounts:
        if re.search(pattern, page):
            page = re.sub(pattern, lambda _: tag, page)
        else:
            page = page.replace(boundary, tag + '\n' + boundary)
    (out/'index.html').write_text(page,encoding='utf-8')
    (out/'SHA256SUMS').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in sorted(out.iterdir()) if p.is_file() and p.name!='SHA256SUMS'),encoding='utf-8')
    return {'places':len(data['places']),'mapped_evidence':sum(len(p['evidence_ids']) for p in data['places']), 'unlocated':len(data['unlocated']), 'rivers':len(data['hydrography']['rivers']), 'formal_year_overlaps':len(data['formal_year_overlaps']), 'historical_borders_verified':False,'revision':revision}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--revision',default='local')
    a=parser.parse_args()
    print(json.dumps(build(a.root,a.revision),ensure_ascii=False))
