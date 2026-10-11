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
  meaning TEXT NOT NULL CHECK(meaning IN ('term', 'event', 'observation', 'research_window')),
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
    'consort', 'heir', 'first_consul', 'institutional', 'other')),
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
    'branch_lineage', 'dynastic_union', 'other_documented')),
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
