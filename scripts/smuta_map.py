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
ASSETS = ('smuta-map.js', 'smuta-map.css')

def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)

def safe_url(value: str) -> bool:
    if not isinstance(value, str):
        return False
    u = urlsplit(value)
    return u.scheme == 'https' and bool(u.hostname) and not u.username and not u.password and u.hostname not in {'drive.google.com', 'docs.google.com'}

def prepare(registry: dict, dossier: dict, atlas: dict) -> dict:
    """Validate explicit mappings; every observation is mapped OR unlocated."""
    require(registry.get('schema_version') == 1, 'Unsupported cartographic contract')
    require(registry.get('coordinate_kind') == 'modern_reference_only', 'Not historical geometry')
    for flag in ('historical_borders_verified', 'historical_truth_verified_by_ci'):
        require(registry.get(flag) is False, 'Do not claim verified historical borders or truth')
    require(dossier.get('historical_truth_verified_by_ci') is False, 'Dossier must retain research caveat')
    cases = [c for c in dossier['cases'] if c['id'] == registry['case_id']]
    require(len(cases) == 1 and cases[0]['id'] == 'smuta-1598-1613', 'Unresolved Smuta case')
    case = cases[0]
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
    # Copy existing claims verbatim. No new actor or territorial conclusion.
    return {
        'schema_version':1, 'historical_borders_verified':False,
        'historical_truth_verified_by_ci':False, 'coordinate_kind':'modern_reference_only',
        'title':'Смута · карта свидетельств', 'start_year':1598, 'end_year':1613,
        'places':copy.deepcopy(registry['places']), 'unlocated':copy.deepcopy(unlocated),
        'evidence':list(copy.deepcopy(evidence).values()), 'events':copy.deepcopy(case['records']),
        'sources':copy.deepcopy(dossier['sources']),
        'people':[{'id':p['id'],'name':p['name']} for p in persons.values()],
        'method':'Точки — современные ориентиры мест. Фильтр года показывает датированные свидетельства, а не длительность контроля. Границы, маршруты и непрерывные царствования из этих точек не выводятся.'
    }

def build(root: Path = ROOT, revision: str = 'local') -> dict:
    out=root/'dist'
    require(out.is_dir() and (out/'index.html').is_file(), 'Build the full atlas first')
    registry=json.loads((root/REGISTRY).read_text(encoding='utf-8'))
    dossier=json.loads((out/'transition-cases.json').read_text(encoding='utf-8'))
    atlas=json.loads((out/'atlas.json').read_text(encoding='utf-8'))
    data=prepare(registry,dossier,atlas)
    data['input_sha256']={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [root/REGISTRY,out/'transition-cases.json']}
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
    return {'places':len(data['places']),'mapped_evidence':sum(len(p['evidence_ids']) for p in data['places']), 'unlocated':len(data['unlocated']), 'historical_borders_verified':False,'revision':revision}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--revision',default='local')
    a=parser.parse_args()
    print(json.dumps(build(a.root,a.revision),ensure_ascii=False))
