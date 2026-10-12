-- P4: independent Wikidata-linked crown-office research layer.
-- Apply ONLY to a disposable v1 + v2 in-memory SQLite preview.
-- The existing v1 schema, source poster, published Pages and canonical facts
-- are not changed by this SQL. Distinct crowns != Habsburg composite lands.
CREATE TABLE v2_wikidata_crown_contexts (
 context_id TEXT PRIMARY KEY REFERENCES v2_contexts(id),
 related_parent_context_id TEXT NOT NULL REFERENCES v2_contexts(id),
 position_qid TEXT NOT NULL UNIQUE CHECK(position_qid GLOB 'Q[1-9]*'),
 kind TEXT NOT NULL CHECK(kind='historic_crown'),
 relation TEXT NOT NULL CHECK(relation='related_not_equivalent'),
 same_as_parent INTEGER NOT NULL CHECK(same_as_parent=0),
 geographic_boundaries_verified INTEGER NOT NULL CHECK(geographic_boundaries_verified=0),
 power_asserted INTEGER NOT NULL CHECK(power_asserted=0),
 caveat TEXT NOT NULL
);

-- Every new legal role must have original P39 revision, statement ID, original
-- date payload, source reference, and the explicit 1762-1800 clipping flags.
CREATE TABLE v2_wikidata_crown_claims (
 role_id TEXT PRIMARY KEY REFERENCES v2_roles(id),
 context_id TEXT NOT NULL REFERENCES v2_wikidata_crown_contexts(context_id),
 external_person_origin TEXT NOT NULL,
 external_person_id TEXT NOT NULL,
 person_qid TEXT NOT NULL CHECK(person_qid GLOB 'Q[1-9]*'),
 position_qid TEXT NOT NULL CHECK(position_qid GLOB 'Q[1-9]*'),
 statement_id TEXT NOT NULL UNIQUE,
 original_revid INTEGER NOT NULL CHECK(original_revid > 0),
 original_start_year INTEGER NOT NULL CHECK(original_start_year > 0),
 original_end_year INTEGER NOT NULL CHECK(original_end_year >= original_start_year),
 candidate_start_year INTEGER NOT NULL,
 candidate_end_year INTEGER NOT NULL,
 left_censored INTEGER NOT NULL CHECK(left_censored IN (0,1)),
 right_censored INTEGER NOT NULL CHECK(right_censored IN (0,1)),
 live_comparison TEXT NOT NULL CHECK(live_comparison IN (
   'not_checked', 'matches_reviewed_snapshot', 'source_changed_review_required')),
 original_start_json TEXT NOT NULL CHECK(json_valid(original_start_json)),
 original_end_json TEXT NOT NULL CHECK(json_valid(original_end_json)),
 official_source_id TEXT NOT NULL REFERENCES v2_sources(id),
 wikidata_source_id TEXT NOT NULL REFERENCES v2_sources(id),
 independent_primary_act_checked INTEGER NOT NULL CHECK(independent_primary_act_checked=0),
 territorial_power_inferred INTEGER NOT NULL CHECK(territorial_power_inferred=0),
 source_record_json TEXT NOT NULL CHECK(json_valid(source_record_json)),
 FOREIGN KEY(external_person_origin,external_person_id)
   REFERENCES v2_external_people(origin,native_id),
 CHECK(candidate_start_year <= candidate_end_year),
 CHECK(candidate_start_year >= original_start_year),
 CHECK(candidate_end_year <= original_end_year),
 CHECK(left_censored=0 OR candidate_start_year > original_start_year),
 CHECK(right_censored=0 OR candidate_end_year < original_end_year)
);
CREATE INDEX v2_wikidata_crown_span
 ON v2_wikidata_crown_claims(context_id,candidate_start_year,candidate_end_year);

-- Only a read-only candidate chronology. A matching YEAR is not an
-- independently established overlap on a particular DAY.
CREATE VIEW v2_wikidata_crown_year_candidates AS
SELECT c.role_id, r.title, r.role_kind,
       c.external_person_id AS world_person_id,
       ep.display_label AS actor_label,
       c.person_qid, c.position_qid, c.statement_id,
       c.context_id, cx.label AS context_label,
       c.candidate_start_year AS start_year,
       c.candidate_end_year AS end_year,
       c.original_start_year, c.original_end_year,
       c.left_censored,c.right_censored,c.live_comparison,
       p.start_date_json,p.end_date_json,
       a.caveat AS interpretation_caveat
FROM v2_wikidata_crown_claims c
JOIN v2_roles r ON r.id=c.role_id
JOIN v2_contexts cx ON cx.id=c.context_id
JOIN v2_periods p ON p.id=r.period_id
JOIN v2_assertions a ON a.id=r.assertion_id
JOIN v2_external_people ep
 ON ep.origin=c.external_person_origin
 AND ep.native_id=c.external_person_id;
