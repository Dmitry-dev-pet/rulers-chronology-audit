#!/usr/bin/env python3
"""Versioned Git data -> validated SQLite + static JSON. Python standard library only.

`migrate` is a one-time, non-overwriting import. `build` NEVER migrates or edits
canonical data. Historic accuracy is not established by either operation.
"""
from __future__ import annotations

import argparse
import calendar
import csv
import hashlib
import html
import json
import re
import shutil
import sqlite3
import tempfile
import uuid
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
BASELINE = 'e8888fc51c7b06366d24e20c05cdb8f2e50cd6e1'
LAYERS = (
    ('muscovy', 'data/muscovy-chronology.json', 'research/muscovy-sources.md'),
    ('romanov', 'data/early-romanov-chronology.json', 'research/early-romanov-sources.md'),
    ('imperial', 'data/imperial-chronology.json', 'research/imperial-sources.md'),
    ('soviet', 'data/soviet-parallel-chronology.json', 'research/soviet-parallel-sources.md'),
)
COLLECTIONS = ('states', 'offices', 'bodies', 'tenures', 'power_assessments',
               'institution_periods', 'events', 'sources', 'person_facts', 'provenance')
BIO_REVIEWS = ('data/muscovy-period-review.csv', 'data/early-romanov-period-review.csv',
               'data/imperial-period-review.csv', 'data/soviet-period-review.csv')
POSTER_IDS = dict(zip(range(59,107), (
    'M01 M20 M02 M07 M08 M09 M10 M21 M22 M12 M23 M12 M13 M14 M15 M16 M17 M26 M27 '
    'R01 R02 R03 R22 R05 R06 R07 R08 R09 R10 R11 R12 R13 '
    'I01 I41 I02 I03 I04 I05 I20 I21 P01 P02 G07 P05 P06 P08 P09 P10').split()))
ALIASES = {
    'Василий II Васильевич Тёмный': 'Василий II Васильевич',
    'Иван IV Васильевич Грозный': 'Иван IV Васильевич',
    'Борис Годунов': 'Борис Фёдорович Годунов',
}
POWER_STATUSES = {
    'political_leadership', 'formal_office_and_political_leadership',
    'collective_transition', 'nominal_due_to_illness', 'collective_acting_functions',
    'patriarch_political_co_ruler', 'regent', 'guardian_influence_approx',
    'factional_governance', 'nominal_grand_prince', 'de_facto_political_leader',
    'collective_interregnum', 'informal_circle', 'infant_emperor',
}
POWER_ONLY = {'political_leadership','collective_transition','collective_acting_functions',
              'patriarch_political_co_ruler','guardian_influence_approx','factional_governance',
              'de_facto_political_leader','collective_interregnum','informal_circle'}
FACT_KINDS = {'birth', 'death', 'lifespan_text', 'ethnic_origin', 'citizenship', 'dynasty'}
VERIFICATIONS = {'imported_not_rechecked', 'reference_checked', 'primary_checked', 'disputed'}
STATES = {
    'moscow': 'Московское великое княжество', 'tsardom': 'Русское царство',
    'empire': 'Российская империя', 'russia-1917': 'Россия при Временном правительстве',
    'rsfsr': 'Советская Россия / РСФСР', 'ussr': 'СССР',
}
OFFICE_TITLES = {
    'moscow-grand-prince': 'Великий князь московский', 'all-rus-grand-prince': 'Великий князь всея Руси',
    'tsar': 'Царь Русского государства', 'emperor': 'Император / императрица России',
    'regent': 'Регент / правитель при государе',
    'general-secretary': 'Генеральный секретарь ЦК', 'first-secretary': 'Первый секретарь ЦК',
    'secretary': 'Секретарь ЦК', 'snk-rsfsr': 'Председатель СНК советской России / РСФСР',
    'snk-ussr': 'Председатель СНК СССР', 'cm-ussr': 'Председатель Совета Министров СССР',
    'vtsik': 'Председатель ВЦИК', 'presidium-vs': 'Председатель Президиума Верховного Совета СССР',
    'vs-ussr': 'Председатель Верховного Совета СССР', 'president-ussr': 'Президент СССР',
    'cm-imperial': 'Председатель Совета министров Российской империи',
    'provisional-govt': 'Министр-председатель Временного правительства',
}

def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def digest(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def dump(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def unique_keys(pairs: list) -> dict:
    result = {}
    for k,v in pairs:
        require(k not in result, f'Duplicate JSON key: {k}')
        result[k] = v
    return result


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding='utf-8-sig'), object_pairs_hook=unique_keys)


def ident(kind: str, name: str) -> str:
    # Mint once on import; later label edits MUST NOT regenerate this stored ID.
    return kind + '-' + uuid.uuid5(uuid.NAMESPACE_URL, 'rulers-atlas/' + kind + '/' + name).hex[:16]


def historical_date(value: str, cal: str = 'unspecified', qualifier: str = 'as_recorded') -> dict:
    out = {'value': value, 'calendar': cal, 'precision': {1:'year',2:'month',3:'day'}[len(value.split('-'))],
           'qualifier': qualifier}
    validate_date(out)
    return out


def validate_date(x: dict) -> None:
    require(isinstance(x,dict) and set(x)=={'value','calendar','precision','qualifier'}, 'Malformed historical date')
    require(x['calendar'] in {'gregorian','julian','unspecified'}, 'Unsupported calendar')
    require(x['qualifier'] in {'as_recorded','exact','approximate','uncertain'}, 'Unsupported date qualifier')
    require(isinstance(x['value'],str) and re.fullmatch(r'\d{4}(?:-\d{2}){0,2}',x['value']), 'Invalid date string')
    parts=list(map(int,x['value'].split('-')))
    require(1<=parts[0]<=9999, 'v1 supports CE 0001–9999; BCE requires a schema migration')
    require(x['precision']=={1:'year',2:'month',3:'day'}[len(parts)], 'Precision mismatch')
    if len(parts)>1:
        require(1<=parts[1]<=12, 'Invalid month')
    if len(parts)>2:
        year,month,day=parts
        leap = year%4==0 if x['calendar']!='gregorian' else calendar.isleap(year)
        maxday=29 if month==2 and leap else (28 if month==2 else [31,0,31,30,31,30,31,31,30,31,30,31][month-1])
        require(1<=day<=maxday,'Invalid day')


def gregorian_bounds(x: dict) -> tuple[date,date] | None:
    validate_date(x)
    if x['calendar']=='unspecified' or x['qualifier'] in {'approximate','uncertain'}:
        return None
    parts=list(map(int,x['value'].split('-'))); y=parts[0]
    lo=(y,parts[1] if len(parts)>1 else 1,parts[2] if len(parts)>2 else 1)
    m=parts[1] if len(parts)>1 else 12
    leap = y%4==0 if x['calendar']=='julian' else calendar.isleap(y)
    lastday=29 if m==2 and leap else (28 if m==2 else [31,0,31,30,31,30,31,31,30,31,30,31][m-1])
    hi=(y,m,parts[2] if len(parts)>2 else lastday)
    def convert(t: tuple) -> date:
        if x['calendar']=='gregorian': return date(*t)
        yy,mm,dd=t; a=(14-mm)//12; yy+=4800-a; mm+=12*a-3
        jdn=dd+(153*mm+2)//5+365*yy+yy//4-32083
        return date(1,1,1)+timedelta(days=jdn-1721426)
    return convert(lo),convert(hi)


def age_range(birth: dict, at: dict) -> dict:
    """Completed proleptic-Gregorian years; no invented calendar or birth day."""
    try: b,t=gregorian_bounds(birth),gregorian_bounds(at)
    except (OverflowError,ValueError): return {'available':False,'reason':'invalid_or_out_of_range_date'}
    if b is None or t is None: return {'available':False,'reason':'calendar_or_uncertainty_unresolved'}
    def years(start: date,end: date) -> int:
        return end.year-start.year-((end.month,end.day)<(start.month,start.day))
    low,high=years(b[1],t[0]),years(b[0],t[1])
    if low<0: return {'available':False,'reason':'date_may_precede_birth'}
    return {'available':True,'min_years':low,'max_years':high,'exact':low==high}


def source_rows(root: Path, paths: list[str]) -> list[dict]:
    result={}
    pattern=r'^\|\s*([A-Z]+\d+)\s*\|\s*\[([^\]]+)\]\((https://[^\s]+?)\)\s*\|([^\n]*)'
    for path in paths:
        for code,title,url,note in re.findall(pattern,(root/path).read_text(encoding='utf-8'),re.M):
            require(code not in result,f'Duplicate bibliography ID {code}')
            result[code]={'id':code,'title':title,'url':url,'note':note.strip(' |'),
                          'imported_from':path,'verification':'imported_not_rechecked'}
    return sorted(result.values(),key=lambda r:r['id'])


def context(layer: str, row: dict) -> list[str]:
    entity=row.get('entity','')
    if entity.startswith('USSR'): return ['ussr']
    if entity: return ['rsfsr']
    if layer=='soviet':
        return ['rsfsr','ussr'] if row['from']<'1922-12-30' else ['ussr']
    if layer=='imperial': return ['russia-1917'] if row['id'] in {'I20','I21'} else ['empire']
    if layer=='romanov':
        if row['to']<'1721': return ['tsardom']
        if row['from']>'1721': return ['empire']
        return ['tsardom','empire']
    if row['to']<'1547': return ['moscow']
    if row['from']>'1547': return ['tsardom']
    return ['moscow','tsardom']


def office_key(row: dict, track: str) -> str:
    rid=row['id']; status=row['status']
    if track=='muscovy_rulers': return 'moscow-grand-prince' if int(rid[1:])<=8 else ('all-rus-grand-prince' if int(rid[1:])<=11 else 'tsar')
    if track=='early_monarchy': return 'tsar' if int(rid[1:])<=5 else 'emperor'
    if track=='imperial_monarchy': return 'emperor'
    if status=='regent': return 'regent'
    if track=='party': return 'secretary' if rid=='P03' else ('first-secretary' if rid in {'P05','P06'} else 'general-secretary')
    if track=='government':
        if rid=='G01': return 'snk-rsfsr'
        if rid in {'G02','G04','G05'}: return 'snk-ussr'
        if rid in {'G07','G08','G09','G10','G11','G12'}: return 'cm-ussr'
    if track=='state_institutions':
        if rid in {'S01','S02','S03','S04'}: return 'vtsik'
        if rid=='S20': return 'vs-ussr'
        if rid=='S21': return 'president-ussr'
        return 'presidium-vs'
    if track=='imperial_government': return 'provisional-govt' if rid in {'I20','I21'} else 'cm-imperial'
    # Unsplit compound and disputed roles retain their original wording.
    return 'legacy-'+rid.lower()


def migrate(root: Path = ROOT, output: Path | None = None) -> dict:
    output=output or root/'data/atlas'
    require(not output.exists(), 'Canonical data already exists. Migration NEVER overwrites it.')
    db={k:[] for k in COLLECTIONS}; db['people']=[]
    db['states']=[{'id':k,'name':v,'note':'Контекст записи, не гражданство лица и не утверждение о неизменных границах.'} for k,v in STATES.items()]
    paths=[p for _,p,_ in LAYERS]+[p for _,_,p in LAYERS]+list(BIO_REVIEWS)+[
        'data/poster-transcription.tsv','research/soviet-period-sources.md']
    db['sources']=source_rows(root,[p for _,_,p in LAYERS]+['research/soviet-period-sources.md'])
    people={}; bodies={}; offices={}; holders={}; legacy_metadata={}
    def person(name: str) -> str:
        canonical=ALIASES.get(name,name); pid=ident('person',canonical)
        if pid not in people: people[pid]={'id':pid,'name':canonical,'aliases':[], 'external_ids':{}, 'biography_status':'incomplete'}
        if name!=canonical and name not in people[pid]['aliases']: people[pid]['aliases'].append(name)
        return pid
    def body(name: str,kind: str='institution') -> str:
        bid=ident('body',name)
        bodies.setdefault(bid,{'id':bid,'name':name,'kind':kind,'memberships':[]})
        return bid
    for layer,path,_ in LAYERS:
        src=read_json(root/path)
        legacy_metadata[layer]={k:v for k,v in src.items() if not (isinstance(v,list) and v and isinstance(v[0],dict) and "id" in v[0])}
        for track,rows in src.items():
            if not isinstance(rows,list): continue
            for position,row in enumerate(rows):
                if not isinstance(row,dict) or not re.fullmatch(r'[A-Z]\d+',str(row.get('id',''))): continue
                rid=row['id']; status=row['status']; label=row.get('person') or row['role']
                event=track.endswith('_events') or status.endswith('_event') or status=='institutional_event'
                individual=(track in {'muscovy_rulers','muscovy_regents','early_monarchy','early_regency',
                    'imperial_monarchy','imperial_government','party','government','state_institutions','separate_records'}
                    and bool(row.get('person')) and rid not in {'M22','M26','I11'}) or rid in {'I41','M56'}
                pid=person(label) if individual else None
                bid=None if individual or event else body(label,'group' if status in POWER_ONLY else 'institution')
                holders[rid]=pid
                if bid:
                    for field,relation in [('persons','shared_functions'),('initial_cochairs','initial_composition_only')]:
                        for name in row.get(field,[]):
                            bodies[bid]['memberships'].append({'person_id':person(name),'record_id':rid,'relation':relation})
                cal='gregorian' if layer=='soviet' else 'unspecified'
                start,end=historical_date(row['from'],cal),historical_date(row['to'],cal)
                common={'record_id':rid,'person_id':pid,'body_id':bid,'state_ids':context(layer,row),
                        'start':start,'end':end,'status':status,'description':row['role'],
                        'note':row.get('note',''),'sources':list(row['sources']),
                        'verification':'imported_not_rechecked'}
                db['provenance'].append({'id':rid,'path':path,'track':track,'position':position,'row_sha256':digest(dump(row).encode()),'row':row})
                if event:
                    db['events'].append(dict(common,id='event-'+rid.lower(),title=label))
                elif status not in POWER_ONLY:
                    if pid:
                        key=office_key(row,track)
                        offices.setdefault(key,{'id':key,'title':OFFICE_TITLES.get(key,row['role']),
                                              'composite_or_unresolved':key.startswith('legacy-')})
                        tenure=dict(common,id='tenure-'+rid.lower(),office_id=key)
                        if rid=='R05':
                            # Only year boundaries explicitly stated in the legacy record; no 1 January accession.
                            for suffix,a,b,office,detail in [
                                ('joint','1682','1696','tsar','Царь-соправитель Ивана V'),
                                ('sole','1696','1721','tsar','Единоличный царь'),
                                ('emperor','1721','1725','emperor','Император')]:
                                offices.setdefault(office,{'id':office,'title':OFFICE_TITLES[office],'composite_or_unresolved':False})
                                db['tenures'].append(dict(tenure,id='tenure-r05-'+suffix,
                                    start=historical_date(a),end=historical_date(b),office_id=office,
                                    state_ids=['empire'] if office=='emperor' else ['tsardom'],
                                    description=detail,note=common['note']+' Границы разделения известны только до года.'))
                        else: db['tenures'].append(tenure)
                    else: db['institution_periods'].append(dict(common,id='institution-'+rid.lower()))
                if status in POWER_STATUSES:
                    # An assessment is NOT a continuous, certain reign. Keep the original qualification.
                    db['power_assessments'].append(dict(common,id='power-'+rid.lower(),
                        assessment_kind=status,confidence='not_assessed',
                        note=common['note']+' Интервал источниковой оценки, не доказанный срок единоличной власти.'))
    db['people']=list(people.values()); db['bodies']=list(bodies.values()); db['offices']=list(offices.values())
    for path in BIO_REVIEWS:
        with (root/path).open(encoding='utf-8-sig',newline='') as f:
            for row in csv.DictReader(f):
                n=int(row['row_id']); rid=POSTER_IDS[n]; pid=holders.get(rid)
                if pid is None: continue
                # Import the reviewed wording, NOT the photograph as a verified birth date.
                db['person_facts'].append({'id':f'fact-poster-{n:03}', 'person_id':pid,'kind':'lifespan_text',
                    'value':row['corrected_life'],'sources':row['source_ids'].split(';'),
                    'verification':'imported_not_rechecked','confidence':'not_assessed',
                    'evidence':{'path':path,'row_id':row['row_id']}})
    db['metadata']={'schema_version':1,'baseline_revision':BASELINE,'display_range':'1417–1991',
        'historical_truth_verified_by_ci':False,'canonical_source':'Git-tracked data/atlas','legacy_metadata':legacy_metadata,
        'identity_policy':'Explicit aliases only. IDs minted once; names are editable.',
        'date_policy':'Preserve calendar and precision. Unspecified calendar forbids exact age.',
        'input_sha256':{p:digest((root/p).read_bytes()) for p in paths},
        'open_items':['Birth/death dates require separate calendar-qualified facts.',
            'Ethnicity, citizenship and dynasty are distinct sourced assertions; not inferred.',
            'Compound offices except Peter I retain legacy granularity pending research.',
            'Power assessments are qualified source claims, not a complete de-facto chronology.',
            'Soviet birth/death wording comes from the earlier SV review; it is not re-verified.']}
    validate(db)
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent,prefix='.atlas-import-') as temp:
        stage=Path(temp)/'atlas'; (stage/'people').mkdir(parents=True)
        for p in sorted(db['people'],key=lambda r:r['id']):
            (stage/'people'/f"{p['id']}.json").write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        for kind in COLLECTIONS:
            (stage/f'{kind}.jsonl').write_text(''.join(dump(r)+'\n' for r in sorted(db[kind],key=lambda r:r['id'])),encoding='utf-8')
        (stage/'manifest.json').write_text(json.dumps(db['metadata'],ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        stage.rename(output)
    return counts(db)


def load(root: Path = ROOT) -> dict:
    base=root/'data/atlas'; db={'metadata':read_json(base/'manifest.json')}
    db['people']=[read_json(p) for p in sorted((base/'people').glob('*.json'))]
    for kind in COLLECTIONS:
        db[kind]=[json.loads(line,object_pairs_hook=unique_keys) for line in (base/f'{kind}.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    validate(db)
    return db


def validate(db: dict) -> None:
    require(db['metadata']['schema_version']==1,'Unsupported atlas schema')
    require(db['metadata']['historical_truth_verified_by_ci'] is False,'Do not claim historical proof')
    index={}
    for kind in ('people',)+COLLECTIONS:
        require(isinstance(db[kind],list),f'Not a list: {kind}')
        ids=[r['id'] for r in db[kind]]
        require(len(ids)==len(set(ids)),f'Duplicate {kind} ID')
        require(all(isinstance(i,str) and re.fullmatch(r'[A-Za-z0-9-]+',i) for i in ids),'Unsafe ID')
        index[kind]=set(ids)
    require(bool(index['people']) and bool(index['provenance']),'Empty migration')
    require(not index['people'] & index['bodies'],'Conflicting actor IDs')
    for p in db['people']:
        require(isinstance(p.get('name'),str) and bool(p['name'].strip()),'Empty person name')
        require(isinstance(p.get('aliases'),list) and all(isinstance(n,str) and n.strip() for n in p['aliases']),'Invalid aliases')
    for source in db['sources']:
        u=urlsplit(source['url'])
        require(u.scheme=='https' and u.hostname and not u.username and not u.password,'Unsafe source URL')
        require(u.hostname not in {'drive.google.com','docs.google.com'},'Private source URL')
    for p in db['provenance']:
        require(p['id']==p['row']['id'],'Legacy ID mismatch')
        require(digest(dump(p['row']).encode())==p['row_sha256'],'Legacy row changed')
        require(set(p['row']['sources'])<=index['sources'],'Missing provenance source')
    seen=set()
    for kind in ('tenures','power_assessments','institution_periods','events'):
        for row in db[kind]:
            rid=row['record_id']; seen.add(rid)
            require(rid in index['provenance'],'Orphan record')
            for k,entity in [('person_id','people'),('body_id','bodies')]:
                require(row[k] is None or row[k] in index[entity],f'Orphan {k}')
            require(not (row['person_id'] and row['body_id']),'Ambiguous holder')
            if kind!='events': require(bool(row['person_id'] or row['body_id']),'Missing holder')
            require(set(row['state_ids'])<=index['states'],'Unknown state')
            require(row['sources'] and set(row['sources'])<=index['sources'],'Unknown source')
            require(row['verification'] in VERIFICATIONS,'Unknown verification')
            validate_date(row['start']);validate_date(row['end'])
            a,b=gregorian_bounds(row['start']),gregorian_bounds(row['end'])
            if a and b: require(a[0]<=b[1],'Reversed period')
            else:
                def civil_bound(x: dict, upper: bool) -> tuple:
                    parts=list(map(int,x['value'].split('-')))
                    return tuple(parts+[12 if upper else 1,31 if upper else 1][len(parts)-1:])
                require(civil_bound(row['start'],False)<=civil_bound(row['end'],True),'Reversed civil-date range')
            if kind=='tenures': require(row['office_id'] in index['offices'],'Unknown office')
            if kind=='power_assessments': require(row['confidence'] in {'not_assessed','low','medium','high'},'Unknown confidence')
    require(seen==index['provenance'],'Unmapped legacy record')
    for body in db['bodies']:
        for member in body['memberships']:
            require(member['person_id'] in index['people'] and member['record_id'] in index['provenance'],'Orphan membership')
            require(member['relation'] in {'shared_functions','initial_composition_only'},'Unknown membership scope')
    for fact in db['person_facts']:
        require(fact['person_id'] in index['people'] and fact['kind'] in FACT_KINDS,'Invalid biography assertion')
        require(fact['sources'] and set(fact['sources'])<=index['sources'],'Biography needs sources')
        require(fact['verification'] in VERIFICATIONS,'Invalid biography verification')
        if fact['kind'] in {'birth','death'}: validate_date(fact['value'])
        else: require(isinstance(fact['value'],str) and fact['value'].strip(),'Empty biography assertion')
    text=dump(db)
    require('drive.google.com' not in text and '1000428575.jpg' not in text,'Private source in export')


def counts(db: dict) -> dict:
    return {k:len(db[k]) for k in ('people',)+COLLECTIONS}


def verify_inputs(db: dict, root: Path) -> None:
    for path,expected in db['metadata']['input_sha256'].items():
        require(digest((root/path).read_bytes())==expected,f'Legacy input changed after migration: {path}')


def write_sqlite(db: dict, path: Path, schema: str) -> None:
    require(not path.exists(),'Build SQLite into a fresh path')
    con=sqlite3.connect(path)
    try:
        con.execute('PRAGMA foreign_keys=ON');con.executescript(schema)
        with con:
            for key,value in sorted(db['metadata'].items()): con.execute('INSERT INTO metadata VALUES (?,?)',(key,dump(value)))
            for p in db['people']: con.execute('INSERT INTO people VALUES (?,?,?,?)',(p['id'],p['name'],p['name'].casefold(),dump(p)))
            for kind in ('states','offices','bodies'):
                for r in db[kind]: con.execute(f'INSERT INTO {kind} VALUES (?,?,?)',(r['id'],r.get('name',r.get('title')),dump(r)))
            for r in db['sources']:con.execute('INSERT INTO sources VALUES (?,?,?,?)',(r['id'],r['title'],r['url'],dump(r)))
            for r in db['provenance']:
                con.execute('INSERT INTO provenance VALUES (?,?,?,?,?,?)',(r['id'],r['path'],r['track'],r['position'],r['row_sha256'],dump(r['row'])))
                for sid in r['row']['sources']:con.execute('INSERT INTO record_sources VALUES (?,?)',(r['id'],sid))
            for kind in ('tenures','power_assessments','institution_periods','events'):
                for r in db[kind]:
                    con.execute('INSERT INTO entries VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',(
                        r['id'],kind,r['record_id'],r['person_id'],r['body_id'],r.get('office_id'),
                        r['start']['value'],r['end']['value'],int(r['start']['value'][:4]),int(r['end']['value'][:4]),
                        r['status'],r['description'],dump(r)))
                    for state in r['state_ids']:con.execute('INSERT INTO entry_states VALUES (?,?)',(r['id'],state))
                    for sid in r['sources']:con.execute('INSERT INTO entry_sources VALUES (?,?)',(r['id'],sid))
            for b in db['bodies']:
                for m in b['memberships']:con.execute('INSERT INTO memberships VALUES (?,?,?,?)',(b['id'],m['person_id'],m['record_id'],m['relation']))
            for f in db['person_facts']:
                con.execute('INSERT INTO person_facts VALUES (?,?,?,?,?,?)',(f['id'],f['person_id'],f['kind'],dump(f['value']),f['verification'],dump(f)))
                for sid in f['sources']:con.execute('INSERT INTO fact_sources VALUES (?,?)',(f['id'],sid))
        require(not con.execute('PRAGMA foreign_key_check').fetchall(),'SQLite foreign-key failure')
        require(con.execute('PRAGMA integrity_check').fetchone()[0]=='ok','SQLite integrity failure')
    finally: con.close()


def database_page(db: dict) -> str:
    e=html.escape; rows=[]
    facts={p['id']:[] for p in db['people']}
    for f in db['person_facts']: facts[f['person_id']].append(f)
    for p in sorted(db['people'],key=lambda p:p['name']):
        lives=[f['value'] for f in facts[p['id']] if f['kind']=='lifespan_text']
        origins=[f['value'] for f in facts[p['id']] if f['kind']=='ethnic_origin']
        terms=[t for t in db['tenures'] if t['person_id']==p['id']]
        birth_rows=[]
        for born in (f for f in facts[p['id']] if f['kind']=='birth'):
            cal='ст. ст.' if born['value']['calendar']=='julian' else 'н. ст.'
            mark=' · спорная версия' if born['verification']=='disputed' else ''
            refs=[]
            for sid in born['sources']:
                source=next((s for s in db['sources'] if s['id']==sid),None)
                if source: refs.append(f"<a target='_blank' rel='noopener noreferrer' href='{e(source['url'],quote=True)}'>{e(sid)}</a>")
            birth_rows.append(f"{e(born['value']['value'])} ({cal}{mark}) <small>{' '.join(refs)}</small>")
        born_html='<br>'.join(birth_rows) if birth_rows else 'Не исследовано'
        detail='<br>'.join(e(t['start']['value']+' — '+t['end']['value']+': '+t['description']) for t in terms)
        rows.append(f"<tr id='{e(p['id'])}'><td>{e(p['name'])}<small>{e(p['id'])}</small></td><td>{born_html}</td><td>{e('; '.join(dict.fromkeys(lives)) or 'Не заполнено')}</td><td>{e('; '.join(origins) or 'Не исследовано')}</td><td>{detail or 'Нет отдельной должностной записи'}</td></tr>")
    summary=' · '.join(e(k)+': '+str(v) for k,v in counts(db).items())
    return '''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>База атласа власти</title>
<style>body{font:17px/1.5 system-ui;max-width:1250px;margin:3rem auto;padding:0 1rem;color:#202b32;background:#faf9f6}h1{line-height:1.1}a{color:#215e76}nav{display:flex;gap:1rem;flex-wrap:wrap}table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #d0d6d8;padding:.8rem;text-align:left;vertical-align:top}small{display:block;font-size:11px;color:#62717a}input{font:inherit;padding:.6rem;width:min(90%,30rem)}.scroll{overflow-x:auto}th{white-space:nowrap}</style>
<nav><a href="index.html">← Атлас</a><a href="atlas.json">JSON</a><a href="atlas.sqlite">SQLite</a><a href="atlas-manifest.json">Проверки и контрольные суммы</a><a href="atlas-schema.sql">Схема SQL</a></nav>
<h1>Люди, должности и источники</h1><p>Одна личность — одна запись, независимо от числа должностей. Это структурированный импорт существующего исследования, не новая независимая проверка истории.</p>
<p>Годы жизни из прежней сверки сохранены. Для первых 14 личностей добавлены независимо источниковые даты рождения; остальные ещё не исследованы. У отдельных исторических дат есть конкурирующие версии, показанные раздельно. Возраст на выбранный год доступен во вкладке «Линии власти». Династия и происхождение — отдельные утверждения, не национальность по умолчанию. Оценки фактической власти не образуют доказанную непрерывную линию единоличных правителей.</p>
<details><summary>Состав базы</summary><p>'''+summary+'''</p></details><p><label>Найти человека или должность<br><input id="search" type="search" placeholder="Например, Пётр или председатель"></label></p>
<div class="scroll"><table><thead><tr><th>Личность</th><th>Дата рождения и источник</th><th>Годы жизни: прежняя сверка</th><th>Этнокультурное происхождение</th><th>Должности</th></tr></thead><tbody>'''+''.join(rows)+'''</tbody></table></div>
<script>document.getElementById('search').addEventListener('input',function(){const q=this.value.toLocaleLowerCase('ru');document.querySelectorAll('tbody tr').forEach(r=>r.hidden=!r.textContent.toLocaleLowerCase('ru').includes(q));});</script></html>'''


def build(root: Path = ROOT, output: Path | None = None, verify: bool = True) -> dict:
    db=load(root); output=output or root/'dist'
    if verify: verify_inputs(db,root)
    schema=(root/'schemas/atlas.sql').read_text(encoding='utf-8')
    output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='atlas-build-') as temp:
        stage=Path(temp)
        (stage/'atlas.json').write_text(json.dumps(db,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (stage/'atlas-schema.sql').write_text(schema,encoding='utf-8')
        write_sqlite(db,stage/'atlas.sqlite',schema)
        (stage/'database.html').write_text(database_page(db),encoding='utf-8')
        receipt={'schema_version':1,'structural_validation':'passed','historical_truth_verified_by_ci':False,
                 'baseline_revision':db['metadata']['baseline_revision'],'counts':counts(db),
                 'canonical_sha256':{str(p.relative_to(root)):digest(p.read_bytes()) for p in sorted((root/'data/atlas').rglob('*')) if p.is_file()},
                 'artifacts_sha256':{p.name:digest(p.read_bytes()) for p in sorted(stage.iterdir())}}
        (stage/'atlas-manifest.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        for p in stage.iterdir():shutil.copyfile(p,output/p.name)
    index=output/'index.html'
    if index.exists():
        page=index.read_text(encoding='utf-8')
        if 'data-atlas-database' not in page:
            require('</body>' in page,'Cannot add database navigation')
            page=page.replace('</body>',"<p data-atlas-database style='padding:1rem;text-align:center'><a href='database.html'>База людей и должностей · JSON / SQLite</a></p></body>")
            index.write_text(page,encoding='utf-8')
    (output/'SHA256SUMS').write_text(''.join(f'{digest(p.read_bytes())}  {p.name}\n' for p in sorted(output.iterdir()) if p.is_file() and p.name!='SHA256SUMS'),encoding='utf-8')
    return receipt


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['migrate','validate','build'])
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.command=='migrate':result=migrate(args.root,args.output)
    elif args.command=='validate':
        db=load(args.root);verify_inputs(db,args.root);result=counts(db)
    else:result=build(args.root,args.output)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
