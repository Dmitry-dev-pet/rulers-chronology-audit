-- HPM P2: ephemeral derived overlay of existing P3 evidence, NOT a v1 migration.
-- This file is loaded only into the disposable in-memory Atlas v2 preview.
-- The original SQLite user_version remains 1; canonical Git data are read-only.
PRAGMA foreign_keys=ON;
CREATE TABLE hpm_transfer_candidates (
  id TEXT PRIMARY KEY,
  relation_id TEXT NOT NULL UNIQUE REFERENCES v2_relationships(id),
  period_id TEXT NOT NULL REFERENCES v2_periods(id),
  assertion_id TEXT NOT NULL REFERENCES v2_assertions(id),
  event_year INTEGER NOT NULL CHECK(event_year BETWEEN 1 AND 9999),
  kind TEXT NOT NULL CHECK(kind IN (
    'succession','imperial_succession','regime_change','institutional_change')),
  review_status TEXT NOT NULL CHECK(review_status IN ('candidate','reviewed_linkage')),
  accession_mechanism TEXT NOT NULL DEFAULT 'unknown'
      CHECK(accession_mechanism='unknown'),
  historical_truth_verified_by_ci INTEGER NOT NULL DEFAULT 0
      CHECK(historical_truth_verified_by_ci=0)
);
CREATE TABLE hpm_transfer_roles (
  transfer_id TEXT NOT NULL REFERENCES hpm_transfer_candidates(id),
  direction TEXT NOT NULL CHECK(direction IN ('outgoing','incoming')),
  role_id TEXT NOT NULL REFERENCES v2_roles(id),
  review_dimension TEXT NOT NULL CHECK(review_dimension='source_record_role_identity_only'),
  caveat TEXT NOT NULL,
  PRIMARY KEY(transfer_id,direction,role_id)
);
CREATE INDEX hpm_transfer_event_year ON hpm_transfer_candidates(event_year);

-- An assertion may have several sources. Preserve source namespaces and
-- original pinpoints; joining through this view is a documentary trace.
CREATE VIEW hpm_transfer_event_evidence AS
SELECT t.id AS transfer_id, t.relation_id, s.id AS source_id,
       s.origin AS source_namespace, s.native_id AS source_native_id,
       s.title AS source_title, s.url AS source_url, es.pinpoint
FROM hpm_transfer_candidates t
JOIN v2_assertion_sources es ON es.assertion_id=t.assertion_id
JOIN v2_sources s ON s.id=es.source_id;

CREATE VIEW hpm_transfer_role_evidence AS
SELECT tr.transfer_id, tr.direction, tr.role_id,
       a.id AS role_assertion_id, s.id AS source_id,
       s.origin AS source_namespace, s.native_id AS source_native_id,
       s.title AS source_title, s.url AS source_url, es.pinpoint
FROM hpm_transfer_roles tr
JOIN v2_roles r ON r.id=tr.role_id
JOIN v2_assertions a ON a.id=r.assertion_id
JOIN v2_assertion_sources es ON es.assertion_id=a.id
JOIN v2_sources s ON s.id=es.source_id;
