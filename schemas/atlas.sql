-- Schema v1. SQLite is derived; edit Git-tracked JSON, never this database file.
PRAGMA foreign_keys=ON;
PRAGMA user_version=1;
CREATE TABLE metadata(key TEXT PRIMARY KEY,value_json TEXT NOT NULL);
CREATE TABLE people(id TEXT PRIMARY KEY,name TEXT NOT NULL,search_name TEXT NOT NULL,data_json TEXT NOT NULL);
CREATE TABLE states(id TEXT PRIMARY KEY,name TEXT NOT NULL,data_json TEXT NOT NULL);
CREATE TABLE offices(id TEXT PRIMARY KEY,title TEXT NOT NULL,data_json TEXT NOT NULL);
CREATE TABLE bodies(id TEXT PRIMARY KEY,name TEXT NOT NULL,data_json TEXT NOT NULL);
CREATE TABLE sources(id TEXT PRIMARY KEY,title TEXT NOT NULL,url TEXT NOT NULL,data_json TEXT NOT NULL);
CREATE TABLE provenance(id TEXT PRIMARY KEY,path TEXT NOT NULL,track TEXT NOT NULL,position INTEGER NOT NULL,row_sha256 TEXT NOT NULL,row_json TEXT NOT NULL);
CREATE TABLE record_sources(record_id TEXT NOT NULL REFERENCES provenance(id),source_id TEXT NOT NULL REFERENCES sources(id),PRIMARY KEY(record_id,source_id));
CREATE TABLE entries(
 id TEXT PRIMARY KEY,
 kind TEXT NOT NULL CHECK(kind IN ('tenures','power_assessments','institution_periods','events')),
 record_id TEXT NOT NULL REFERENCES provenance(id),
 person_id TEXT REFERENCES people(id),body_id TEXT REFERENCES bodies(id),office_id TEXT REFERENCES offices(id),
 start_value TEXT NOT NULL,end_value TEXT NOT NULL,start_year INTEGER NOT NULL,end_year INTEGER NOT NULL,
 status TEXT NOT NULL,description TEXT NOT NULL,data_json TEXT NOT NULL,
 CHECK(person_id IS NULL OR body_id IS NULL),CHECK(start_year<=end_year),
 CHECK(kind='events' OR person_id IS NOT NULL OR body_id IS NOT NULL),
 CHECK(kind!='tenures' OR office_id IS NOT NULL)
);
CREATE TABLE entry_states(entry_id TEXT NOT NULL REFERENCES entries(id),state_id TEXT NOT NULL REFERENCES states(id),PRIMARY KEY(entry_id,state_id));
CREATE TABLE entry_sources(entry_id TEXT NOT NULL REFERENCES entries(id),source_id TEXT NOT NULL REFERENCES sources(id),PRIMARY KEY(entry_id,source_id));
CREATE TABLE memberships(body_id TEXT NOT NULL REFERENCES bodies(id),person_id TEXT NOT NULL REFERENCES people(id),record_id TEXT NOT NULL REFERENCES provenance(id),relation TEXT NOT NULL CHECK(relation IN ('initial_composition_only','shared_functions')),PRIMARY KEY(body_id,person_id,record_id,relation));
CREATE TABLE person_facts(id TEXT PRIMARY KEY,person_id TEXT NOT NULL REFERENCES people(id),kind TEXT NOT NULL CHECK(kind IN ('birth','death','lifespan_text','ethnic_origin','citizenship','dynasty')),value_json TEXT NOT NULL,verification TEXT NOT NULL,data_json TEXT NOT NULL);
CREATE TABLE fact_sources(fact_id TEXT NOT NULL REFERENCES person_facts(id),source_id TEXT NOT NULL REFERENCES sources(id),PRIMARY KEY(fact_id,source_id));
CREATE INDEX people_search ON people(search_name);
CREATE INDEX entry_period ON entries(start_year,end_year);
CREATE INDEX entry_person ON entries(person_id,kind);
CREATE INDEX entry_body ON entries(body_id,kind);
CREATE INDEX facts_person ON person_facts(person_id,kind);
CREATE VIEW person_tenures AS SELECT p.id person_id,p.name,e.id tenure_id,o.title office,e.start_value,e.end_value,e.status,e.description,e.record_id,e.data_json FROM entries e JOIN people p ON p.id=e.person_id JOIN offices o ON o.id=e.office_id WHERE e.kind='tenures';
-- Year filtering gives candidates, NOT certain day-level overlap. Inspect date precision and calendar in data_json.
CREATE VIEW power_assessments AS SELECT * FROM entries WHERE kind='power_assessments';
CREATE VIEW events AS SELECT * FROM entries WHERE kind='events';
