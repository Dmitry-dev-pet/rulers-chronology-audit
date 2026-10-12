-- EXPERIMENTAL additive overlay for schema v1, not a production migration.
-- Run only against a disposable v1 SQLite copy. No changes to schema/user_version=1.
-- Editable historical truth remains Git-tracked data/atlas; SQLite is derived.
PRAGMA foreign_keys=ON;

-- A political CONTEXT need not be a sovereign state: HRE imperial office is not
-- a German national government, Habsburg lands are a composite monarchy, etc.
CREATE TABLE v2_contexts (
  id TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  kind TEXT NOT NULL CHECK(kind IN (
    'polity', 'polity_regime', 'composite_monarchy',
    'elective_office_context', 'birthplace_context', 'other_context')),
  note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE v2_context_refs (
  origin TEXT NOT NULL,
  native_id TEXT NOT NULL,
  context_id TEXT NOT NULL REFERENCES v2_contexts(id),
  mapping TEXT NOT NULL CHECK(mapping IN ('equivalent', 'related_context')),
  note TEXT NOT NULL DEFAULT '',
  PRIMARY KEY(origin, native_id)
);
CREATE INDEX v2_context_refs_context ON v2_context_refs(context_id);

-- External pilot IDs are NOT canonical person identities until explicitly linked.
CREATE TABLE v2_external_people (
  origin TEXT NOT NULL,
  native_id TEXT NOT NULL,
  display_label TEXT NOT NULL,
  canonical_person_id TEXT REFERENCES people(id),
  resolution TEXT NOT NULL CHECK(resolution IN ('linked', 'unresolved')),
  PRIMARY KEY(origin, native_id),
  CHECK((resolution='linked' AND canonical_person_id IS NOT NULL) OR
        (resolution='unresolved' AND canonical_person_id IS NULL))
);
CREATE INDEX v2_external_people_canonical ON v2_external_people(canonical_person_id);

-- Periods retain the original date object (calendar, precision, qualifier).
-- start/end_year are candidate year filters, not proof of a day-level overlap.
CREATE TABLE v2_periods (
  id TEXT PRIMARY KEY,
  start_year INTEGER NOT NULL,
  end_year INTEGER NOT NULL,
  start_date_json TEXT,
  end_date_json TEXT,
  meaning TEXT NOT NULL CHECK(meaning IN ('term', 'event', 'observation', 'research_window', 'role_window', 'relation_evidence_window')),
  note TEXT NOT NULL DEFAULT '',
  CHECK(start_year BETWEEN 1 AND 9999 AND end_year BETWEEN 1 AND 9999),
  CHECK(start_year <= end_year),
  CHECK(start_date_json IS NULL OR json_valid(start_date_json)),
  CHECK(end_date_json IS NULL OR json_valid(end_date_json))
);
CREATE INDEX v2_period_years ON v2_periods(start_year, end_year);

-- World-pilot and canonical source IDs live in explicit namespaces.
CREATE TABLE v2_sources (
  id TEXT PRIMARY KEY,
  origin TEXT NOT NULL,
  native_id TEXT NOT NULL,
  title TEXT NOT NULL,
  url TEXT NOT NULL CHECK(url LIKE 'https://%'),
  canonical_source_id TEXT REFERENCES sources(id),
  verification TEXT NOT NULL CHECK(verification IN (
    'imported_not_rechecked', 'reference_checked', 'primary_checked', 'unverified')),
  UNIQUE(origin, native_id)
);
CREATE TABLE v2_assertions (
  id TEXT PRIMARY KEY,
  category TEXT NOT NULL CHECK(category IN (
    'legal', 'practical', 'claim', 'institutional',
    'dynastic', 'biographical', 'geographic', 'chronology', 'coverage')),
  statement TEXT NOT NULL,
  caveat TEXT NOT NULL,
  confidence TEXT NOT NULL CHECK(confidence IN ('not_assessed', 'low', 'medium', 'high')),
  verification TEXT NOT NULL CHECK(verification IN (
    'imported_not_rechecked', 'reference_checked', 'primary_checked', 'unverified'))
);
CREATE TABLE v2_assertion_sources (
  assertion_id TEXT NOT NULL REFERENCES v2_assertions(id),
  source_id TEXT NOT NULL REFERENCES v2_sources(id),
  pinpoint TEXT NOT NULL DEFAULT '',
  PRIMARY KEY(assertion_id, source_id)
);

CREATE TABLE v2_institutions (
  id TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  kind TEXT NOT NULL CHECK(kind IN ('collective', 'collegial_executive', 'executive_system', 'other')),
  canonical_body_id TEXT REFERENCES bodies(id),
  note TEXT NOT NULL DEFAULT ''
);

-- Exactly one actor: canonical person, canonical body, externally referenced
-- person, or explicitly collective international institution.
CREATE TABLE v2_roles (
  id TEXT PRIMARY KEY,
  context_id TEXT NOT NULL REFERENCES v2_contexts(id),
  person_id TEXT REFERENCES people(id),
  body_id TEXT REFERENCES bodies(id),
  external_person_origin TEXT,
  external_person_id TEXT,
  institution_id TEXT REFERENCES v2_institutions(id),
  office_id TEXT REFERENCES offices(id),
  title TEXT NOT NULL,
  role_kind TEXT NOT NULL CHECK(role_kind IN (
    'sovereign', 'elector', 'emperor', 'regent', 'co_regent',
    'consort', 'heir', 'dynastic_person', 'first_consul', 'institutional', 'other')),
  period_id TEXT NOT NULL REFERENCES v2_periods(id),
  assertion_id TEXT NOT NULL REFERENCES v2_assertions(id),
  canonical_tenure_id TEXT REFERENCES entries(id),
  origin TEXT NOT NULL,
  native_id TEXT NOT NULL,
  FOREIGN KEY(external_person_origin, external_person_id)
    REFERENCES v2_external_people(origin, native_id),
  UNIQUE(origin, native_id),
  CHECK((external_person_origin IS NULL) = (external_person_id IS NULL)),
  CHECK((person_id IS NOT NULL) + (body_id IS NOT NULL) +
        (external_person_origin IS NOT NULL) + (institution_id IS NOT NULL) = 1)
);
CREATE INDEX v2_roles_context_kind ON v2_roles(context_id, role_kind);
CREATE INDEX v2_roles_period ON v2_roles(period_id);

CREATE TABLE v2_houses (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE v2_house_affiliations (
  id TEXT PRIMARY KEY,
  house_id TEXT NOT NULL REFERENCES v2_houses(id),
  person_id TEXT REFERENCES people(id),
  external_person_origin TEXT,
  external_person_id TEXT,
  affiliation TEXT NOT NULL CHECK(affiliation IN (
    'by_birth', 'official_dynasty', 'by_marriage',
    'branch_lineage', 'dynastic_union', 'documented_house', 'other_documented')),
  branch_label TEXT NOT NULL DEFAULT '',
  period_id TEXT REFERENCES v2_periods(id),
  assertion_id TEXT NOT NULL REFERENCES v2_assertions(id),
  FOREIGN KEY(external_person_origin, external_person_id)
    REFERENCES v2_external_people(origin, native_id),
  CHECK((external_person_origin IS NULL)=(external_person_id IS NULL)),
  CHECK((person_id IS NOT NULL)+(external_person_origin IS NOT NULL)=1)
);
CREATE INDEX v2_house_affiliations_house ON v2_house_affiliations(house_id);

CREATE TABLE v2_context_relations (
  id TEXT PRIMARY KEY,
  context_a TEXT NOT NULL REFERENCES v2_contexts(id),
  context_b TEXT NOT NULL REFERENCES v2_contexts(id),
  kind TEXT NOT NULL CHECK(kind IN (
    'personal_union', 'composite_component', 'successor_regime',
    'vassalage', 'treaty', 'other_documented')),
  person_id TEXT REFERENCES people(id),
  external_person_origin TEXT,
  external_person_id TEXT,
  period_id TEXT NOT NULL REFERENCES v2_periods(id),
  assertion_id TEXT NOT NULL REFERENCES v2_assertions(id),
  FOREIGN KEY(external_person_origin, external_person_id)
    REFERENCES v2_external_people(origin, native_id),
  CHECK(context_a <> context_b),
  CHECK((external_person_origin IS NULL)=(external_person_id IS NULL)),
  CHECK((person_id IS NOT NULL)+(external_person_origin IS NOT NULL)<=1),
  CHECK(kind<>'personal_union' OR
        (person_id IS NOT NULL)+(external_person_origin IS NOT NULL)=1)
);

CREATE TABLE v2_person_relations (
  id TEXT PRIMARY KEY,
  person_a TEXT NOT NULL REFERENCES people(id),
  person_b TEXT NOT NULL REFERENCES people(id),
  kind TEXT NOT NULL CHECK(kind IN ('parent', 'spouse', 'sibling', 'other_documented')),
  period_id TEXT REFERENCES v2_periods(id),
  assertion_id TEXT NOT NULL REFERENCES v2_assertions(id),
  CHECK(person_a<>person_b)
);
CREATE TABLE v2_house_relations (
  id TEXT PRIMARY KEY,
  house_a TEXT NOT NULL REFERENCES v2_houses(id),
  house_b TEXT NOT NULL REFERENCES v2_houses(id),
  kind TEXT NOT NULL CHECK(kind IN ('branch_of', 'dynastic_union', 'documented_lineage')),
  period_id TEXT REFERENCES v2_periods(id),
  assertion_id TEXT NOT NULL REFERENCES v2_assertions(id),
  CHECK(house_a<>house_b)
);

-- Research windows record WHAT was searched, not historical existence.
CREATE TABLE v2_research_scopes (
  id TEXT PRIMARY KEY,
  context_id TEXT NOT NULL REFERENCES v2_contexts(id),
  domain TEXT NOT NULL CHECK(domain IN (
    'formal_offices', 'institutions', 'political_influence',
    'dynasties', 'biography', 'territorial_evidence')),
  period_id TEXT NOT NULL REFERENCES v2_periods(id),
  assertion_id TEXT NOT NULL REFERENCES v2_assertions(id),
  note TEXT NOT NULL DEFAULT ''
);

-- No automatic historical control polygons or invented borders.
CREATE TABLE v2_places (
  id TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  kind TEXT NOT NULL CHECK(kind IN ('city', 'vicinity_of_city', 'region', 'republic', 'other')),
  note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE v2_territorial_observations (
  id TEXT PRIMARY KEY,
  place_id TEXT NOT NULL REFERENCES v2_places(id),
  context_id TEXT REFERENCES v2_contexts(id),
  nature TEXT NOT NULL CHECK(nature IN ('law', 'practice', 'claim', 'military')),
  authority TEXT NOT NULL,
  period_id TEXT NOT NULL REFERENCES v2_periods(id),
  assertion_id TEXT NOT NULL REFERENCES v2_assertions(id),
  geometry_verified INTEGER NOT NULL DEFAULT 0 CHECK(geometry_verified=0)
);

-- Structural validator inputs, NOT historical attestations.
CREATE VIEW v2_assertions_without_sources AS
  SELECT a.id FROM v2_assertions a
  WHERE NOT EXISTS (SELECT 1 FROM v2_assertion_sources s WHERE s.assertion_id=a.id);

CREATE VIEW v2_personal_unions_without_role_candidates AS
  SELECT rel.id FROM v2_context_relations rel
  JOIN v2_periods rp ON rp.id=rel.period_id
  WHERE rel.kind='personal_union' AND NOT EXISTS (
    SELECT 1 FROM v2_roles a
    JOIN v2_roles b ON b.context_id=rel.context_b
    JOIN v2_periods ap ON ap.id=a.period_id
    JOIN v2_periods bp ON bp.id=b.period_id
    WHERE a.context_id=rel.context_a
      AND a.role_kind IN ('sovereign','elector','emperor')
      AND b.role_kind IN ('sovereign','elector','emperor')
      AND ((rel.person_id IS NOT NULL AND a.person_id=rel.person_id AND b.person_id=rel.person_id)
           OR (rel.external_person_origin IS NOT NULL
               AND a.external_person_origin=rel.external_person_origin
               AND a.external_person_id=rel.external_person_id
               AND b.external_person_origin=rel.external_person_origin
               AND b.external_person_id=rel.external_person_id))
      AND ap.start_year<=rp.end_year AND ap.end_year>=rp.start_year
      AND bp.start_year<=rp.end_year AND bp.end_year>=rp.start_year
      AND ap.start_year<=bp.end_year AND bp.start_year<=ap.end_year
  );

-- A validated export additionally requires each assertion to have a source;
-- calendar-qualified temporal semantics; role-kind consistency; no unverified
-- identity matches; no leap from claim to control; and scoped research coverage.


-- P2 provenance: exact pilot JSON payload for every imported role/institution,
-- independent of the already immutable canonical v1 provenance.
CREATE TABLE v2_world_imports (
  origin TEXT NOT NULL,
  native_id TEXT NOT NULL,
  dataset TEXT NOT NULL CHECK(dataset IN ('dynasty-1762-1780.json', 'extension-1781-1800.json')),
  kind TEXT NOT NULL CHECK(kind IN ('person_role', 'institution')),
  role_id TEXT UNIQUE REFERENCES v2_roles(id),
  institution_id TEXT UNIQUE REFERENCES v2_institutions(id),
  raw_json TEXT NOT NULL CHECK(json_valid(raw_json)),
  PRIMARY KEY(origin, native_id),
  CHECK((role_id IS NOT NULL)+(institution_id IS NOT NULL)=1),
  CHECK((kind='person_role' AND role_id IS NOT NULL)
     OR (kind='institution' AND institution_id IS NOT NULL))
);

-- UNION gives a READ-ONLY candidate chronology, NOT a historical certainty.
-- v1 canonical tenure records come first. World role imports that already
-- resolve to a canonical tenure are excluded to avoid duplicate Russian rulers.
-- Entry/state fan-out can produce multiple CONTEXT rows for one v1 tenure.
-- Each year overlap is a CANDIDATE only: consult calendar/precision/raw payload.
CREATE VIEW v2_timeline_year_candidates AS
SELECT 'v1-tenure' AS origin_layer, e.id AS item_id,
       'canonical_tenure' AS item_kind, cr.context_id,
       e.person_id AS person_id,
       NULL AS external_person_origin, NULL AS external_person_id,
       e.body_id AS body_id, NULL AS institution_id,
       e.office_id AS role_kind, e.status AS legacy_status,
       e.start_year, e.end_year, e.record_id AS legacy_record_id,
       NULL AS imported_record_id
FROM entries e
JOIN entry_states es ON es.entry_id=e.id
JOIN v2_context_refs cr ON cr.origin='atlas-state-v1' AND cr.native_id=es.state_id
WHERE e.kind='tenures'
UNION ALL
SELECT CASE WHEN r.origin='wikidata-curated-crowns'
            THEN 'wikidata-curated'
            ELSE 'world-pilot' END AS origin_layer, r.id AS item_id,
       CASE WHEN r.role_kind='institutional' THEN 'world_institution'
            ELSE 'world_person_role' END AS item_kind,
       r.context_id, r.person_id,
       r.external_person_origin, r.external_person_id,
       r.body_id, r.institution_id, r.role_kind,
       NULL AS legacy_status, p.start_year, p.end_year,
       NULL AS legacy_record_id, r.native_id AS imported_record_id
FROM v2_roles r
JOIN v2_periods p ON p.id=r.period_id
WHERE r.canonical_tenure_id IS NULL
UNION ALL
SELECT 'v1-institution' AS origin_layer, e.id AS item_id,
       'canonical_institution' AS item_kind, cr.context_id,
       e.person_id, NULL, NULL,
       e.body_id, NULL, 'institutional', e.status,
       e.start_year, e.end_year, e.record_id, NULL
FROM entries e
JOIN entry_states es ON es.entry_id=e.id
JOIN v2_context_refs cr ON cr.origin='atlas-state-v1' AND cr.native_id=es.state_id
WHERE e.kind='institution_periods';

-- Does not certify completeness or actual uninterrupted control of territory.
-- Duplicates within a calendar year are not automatically same-day coexistence.
CREATE INDEX v2_world_import_kind ON v2_world_imports(kind,dataset);


-- P3 typed, source-qualified international relationship graph.
-- The time range of a parent or marriage relationship is an observed SOURCE
-- window, not an assertion about when parenthood began or when a marriage ended.
-- One-off succession/treaty/regime changes are represented by event-year periods.
CREATE TABLE v2_relationships (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL CHECK(kind IN (
    'personal_union', 'marriage', 'parent', 'imperial_succession',
    'co_regency', 'succession', 'regency', 'treaty',
    'regime_change', 'institutional_change')),
  domain TEXT NOT NULL CHECK(domain IN (
    'kinship', 'political_roles', 'interstate', 'institutional')),
  period_id TEXT NOT NULL REFERENCES v2_periods(id),
  event_year INTEGER CHECK(event_year IS NULL OR event_year BETWEEN 1 AND 9999),
  assertion_id TEXT NOT NULL REFERENCES v2_assertions(id),
  title TEXT NOT NULL,
  note TEXT NOT NULL,
  origin TEXT NOT NULL,
  native_id TEXT NOT NULL,
  UNIQUE(origin,native_id)
);

CREATE TABLE v2_relationship_people (
  relation_id TEXT NOT NULL REFERENCES v2_relationships(id),
  position INTEGER NOT NULL CHECK(position>=1),
  person_id TEXT REFERENCES people(id),
  external_person_origin TEXT,
  external_person_id TEXT,
  FOREIGN KEY(external_person_origin,external_person_id)
    REFERENCES v2_external_people(origin,native_id),
  PRIMARY KEY(relation_id,position),
  CHECK((external_person_origin IS NULL)=(external_person_id IS NULL)),
  CHECK((person_id IS NOT NULL)+(external_person_origin IS NOT NULL)=1)
);
CREATE INDEX v2_rel_people_person ON v2_relationship_people(person_id);
CREATE INDEX v2_rel_people_external ON v2_relationship_people(external_person_origin,external_person_id);

CREATE TABLE v2_relationship_contexts (
  relation_id TEXT NOT NULL REFERENCES v2_relationships(id),
  position INTEGER NOT NULL CHECK(position>=1),
  context_id TEXT NOT NULL REFERENCES v2_contexts(id),
  PRIMARY KEY(relation_id,position)
);
CREATE INDEX v2_rel_contexts_context ON v2_relationship_contexts(context_id);

-- Every source JSON relation is retained, including the two explicitly
-- reconciled duplicate pilot records. 'Normalized' does NOT mean historical
-- verification. One normalized relationship may have two raw records.
CREATE TABLE v2_relationship_imports (
  origin TEXT NOT NULL,
  native_id TEXT NOT NULL,
  dataset TEXT NOT NULL CHECK(dataset IN (
    '1762.json', 'dynasty-1762-1780.json', 'extension-1781-1800.json')),
  relationship_id TEXT NOT NULL REFERENCES v2_relationships(id),
  raw_json TEXT NOT NULL CHECK(json_valid(raw_json)),
  alias_of TEXT REFERENCES v2_relationships(id),
  PRIMARY KEY(origin,native_id),
  CHECK(alias_of IS NULL OR alias_of=relationship_id)
);
CREATE INDEX v2_relationship_imports_rel ON v2_relationship_imports(relationship_id);

-- v2_houses / v2_house_affiliations above are typed house data; these P3 audit
-- rows keep both source family and each source membership losslessly.
CREATE TABLE v2_house_imports (
  origin TEXT NOT NULL,
  native_id TEXT NOT NULL,
  house_id TEXT NOT NULL REFERENCES v2_houses(id),
  assertion_id TEXT NOT NULL REFERENCES v2_assertions(id),
  raw_json TEXT NOT NULL CHECK(json_valid(raw_json)),
  PRIMARY KEY(origin,native_id)
);
CREATE TABLE v2_affiliation_imports (
  origin TEXT NOT NULL,
  native_id TEXT NOT NULL,
  affiliation_id TEXT NOT NULL UNIQUE REFERENCES v2_house_affiliations(id),
  raw_json TEXT NOT NULL CHECK(json_valid(raw_json)),
  PRIMARY KEY(origin,native_id)
);

-- Ruling candidates, not proof of continuous or same-day reigns.
-- Consorts, heirs, regents, merely genealogical branch relations and
-- elective imperial office context are excluded from 'ruling house' counts.
-- A composite monarchy (Habsburg lands) remains explicitly typed as such:
-- client analyses must never count it as an ordinary independent state.
CREATE VIEW v2_house_ruling_year_candidates AS
SELECT h.id AS house_id, h.name AS house_name,
       a.id AS affiliation_id, a.branch_label,
       r.id AS role_id, r.context_id, c.label AS context_label, c.kind AS context_kind,
       r.role_kind, r.person_id, r.external_person_origin, r.external_person_id,
       p.start_year, p.end_year
FROM v2_house_affiliations a
JOIN v2_houses h ON h.id=a.house_id
JOIN v2_roles r ON (
    (a.person_id IS NOT NULL AND a.person_id=r.person_id)
    OR (a.external_person_origin IS NOT NULL AND
        a.external_person_origin=r.external_person_origin AND
        a.external_person_id=r.external_person_id))
JOIN v2_periods p ON p.id=r.period_id
JOIN v2_contexts c ON c.id=r.context_id
WHERE a.affiliation='documented_house'
  AND r.role_kind IN ('sovereign','elector')
  AND c.kind NOT IN ('elective_office_context','birthplace_context');


-- P5: authority IS NOT ONE SINGLE HIERARCHY. A legal title, imperial
-- constitutional membership, local seizure, military intervention,
-- fiscal jurisdiction and diplomatic tributary link must not be conflated.
-- This is an additive RESEARCH candidate over a DISPOSABLE v1 SQLite.
CREATE TABLE v2_authority_nodes (
  id TEXT PRIMARY KEY,
  region_id TEXT NOT NULL CHECK(region_id IN ('hre','india','qing','eng','jp','mughal','et')),
  kind TEXT NOT NULL CHECK(kind IN (
    'person','polity','constitutional_framework','imperial_title_context',
    'collective_institution','locality','fiscal_jurisdiction')),
  label TEXT NOT NULL,
  note TEXT NOT NULL,
  p3_context_id TEXT REFERENCES v2_contexts(id),
  p3_person_origin TEXT,
  p3_person_id TEXT,
  assertion_id TEXT NOT NULL REFERENCES v2_assertions(id),
  FOREIGN KEY(p3_person_origin,p3_person_id)
    REFERENCES v2_external_people(origin,native_id),
  CHECK((p3_person_origin IS NULL)=(p3_person_id IS NULL)),
  CHECK((p3_context_id IS NULL) OR (p3_person_id IS NULL))
);

CREATE TABLE v2_authority_edges (
  id TEXT PRIMARY KEY,
  region_id TEXT NOT NULL CHECK(region_id IN ('hre','india','qing','eng','jp','mughal','et')),
  from_node TEXT NOT NULL REFERENCES v2_authority_nodes(id),
  to_node TEXT NOT NULL REFERENCES v2_authority_nodes(id),
  kind TEXT NOT NULL CHECK(kind IN (
    'elective_imperial_office','constitutional_membership','electoral_office',
    'sovereign_office','imperial_title','local_military_seizure',
    'military_restoration','fiscal_administration','tributary_diplomacy',
    'military_intervention','shogunate_office','cabinet_office',
    'cabinet_transition','formal_overlordship')),
  dimension TEXT NOT NULL CHECK(dimension IN (
    'legal','practical','military','diplomatic','institutional')),
  period_id TEXT NOT NULL REFERENCES v2_periods(id),
  assertion_id TEXT NOT NULL REFERENCES v2_assertions(id),
  label TEXT NOT NULL,
  explanation TEXT NOT NULL,
  caveat TEXT NOT NULL,
  CHECK(from_node<>to_node)
);
CREATE INDEX v2_authority_edges_dimension ON v2_authority_edges(dimension,region_id);

-- Source-qualified candidates only. Research windows do not infer duration.
CREATE VIEW v2_authority_year_candidates AS
SELECT e.id,e.region_id,e.from_node,e.to_node,e.kind,e.dimension,
       e.label,e.explanation,e.caveat,p.start_year,p.end_year,p.meaning,
       e.assertion_id
FROM v2_authority_edges e JOIN v2_periods p ON p.id=e.period_id;
