# Wikidata reconciliation — first external synchronization stage

**Status:** experimental read-only research stage. External evidence feed only: not a migration, proof of historical truth, real-power assessment, or GitHub Pages feature.

## Scope (11 October 2026)

- The canonical source remains data/atlas/people/*.json and data/atlas/person_facts.jsonl: 83 distinct people.
- The supplemental discovery scope contains the 24 additional world-pilot people without an explicit canonical_person_id. These are **not** 24 automatically verified sovereign rulers.
- Three source-checked Wikidata links are recorded in external_ids.wikidata:
  - person-010d69ee64b3599c — Sophia Alekseyevna — [Q233987](https://www.wikidata.org/wiki/Q233987)
  - person-14b51b51093f55ce — Paul I — [Q15189](https://www.wikidata.org/wiki/Q15189)
  - person-a4d0a7000e965592 — Catherine II — [Q36450](https://www.wikidata.org/wiki/Q36450)
- The remaining people are a **discovery queue**. A Wikidata name-search candidate never becomes a confirmed identity join, even if its spelling is identical. New links require explicit verification and a reviewed Git PR. World-only ID association needs an explicit v2 crosswalk.
- This workflow does not read private Google Drive assets or Archigos/PLAD files.

## Running the importer

From repository root, Python 3.11+ and only the standard library:

    python3 -m unittest tests.test_wikidata_sync -v
    python3 -m scripts.wikidata_sync --discover --max-searches 107

The outputs are reports/wikidata/latest.json and reports/wikidata/latest.md.
Without --discover only confirmed QIDs are fetched; for a five-person
sample use --discover --max-searches 5. Requests are sequential, with a
0.4-second courtesy pause and a Retry-After policy for HTTP 429. The
user-agent identifies this repository. An API failure stops the run rather
than writing a misleading partial report. No login, secrets, LLM, or server
database is required.

The JSON holds: source entity lastrevid, QID, labels, statement IDs, ranks
(including deprecated), Gregorian/Julian calendarmodel, precision, raw time,
qualifiers, and reference pointers. Fields include P569 (birth), P570
(death), P39 (position held) with P580/P582/P1365/P1366 qualifiers, P19
(birthplace), P27 (citizenship), P53 (family), P22/P25 (parents) and P26
(spouse). Source pointers are P248 (stated in), P854 (reference URL), P813
(retrieved). Historical lifespan_text is not converted to a verified birth.
Ethnic group P172 is **not imported**; family, citizenship, birthplace and
language are not proxies for ethnicity. No images or image binaries are copied.

### Review status

- same_recorded_date: same value, precision and calendar; not independent historical verification.
- compatible_lower_precision: one date is only a coarse representation.
- calendar_review: calendar differs or is unspecified; **no automatic old-style/new-style conversion**.
- date_disagreement_candidate: possibly conflicting dates within the same known calendar.
- review_multiple_wikidata_claims: several active Wikidata date statements coexist.
- no_canonical_fact: no existing canonical fact for a Wikidata date.
- wikidata_date_missing: no non-deprecated time-valued Wikidata date.
- candidate_search_unverified: QIDs from a text search, **not** verified person links.
- not_searched: search disabled, unavailable name, or search cap reached.

Deprecated claims remain in the JSON but do not participate as active date
claims. Disputed canonical facts are retained unchanged. P39 does not show
de-facto control, and political context is not identical to geography or
citizenship. Names never merge people, historic polities or dynastic houses.

## GitHub automation and permissions

Workflow: [wikidata-sync.yml](../.github/workflows/wikidata-sync.yml).

- Each Monday at 04:17 UTC, GitHub Actions creates a read-only external
  reconciliation report as a 30-day artifact, with a job summary.
- Manual workflow_dispatch also performs a read-only run by default.
- Only a manual dispatch on main with open_report_pr=true can run the
  second, write-enabled job, opening a **review-only PR** with the generated
  external-data JSON and Markdown. No auto-merge, no canonical assertions,
  no schema, SQLite, SPA or Pages mutation.
- The regular audit job has contents:read; the optional proposal job is the
  only one with contents:write and pull-requests:write. Untrusted fetched
  text is data only; no network-sourced text is executed.
- Pull requests made by the workflow GITHUB_TOKEN may not automatically
  trigger other PR workflows. Review the audit job and rerun independent
  tests when necessary.
- Normal atlas_db validate/build and the site release are offline and
  independent of the availability or quality of Wikidata.

Reference operational guidance: [Wikimedia rate limits](https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits),
[API etiquette](https://www.mediawiki.org/wiki/API:Etiquette) and
[Wikidata data access](https://www.wikidata.org/wiki/Wikidata:Data_access).

## Later milestones — not part of this read-only implementation

1. Resolve the canonical/world candidate queue with explicit QID review.
2. Map office QIDs and separately typed historic state contexts: a P39
   property is not our office_id, and historic polities are not modern states.
3. Propose source-reviewed external roles and dynastic relations to v2,
   preserving mixed calendars, uncertainty, disagreement and collective power.
4. Publish selected data in the worldwide SPA only after historical review
   and measurement of derived SQLite/JSON size versus the 100 MB target.
