# Historical Power Model · P2 (experimental, read-only source projection)

**Date:** 13 October 2026. **Status:** research prototype, **not** a migration or historical verdict. Tracks [#61](https://github.com/Dmitry-dev-pet/rulers-chronology-audit/issues/61) and extends [HPM P0/P1](HISTORICAL_POWER_MODEL_V1.md), not the existing Atlas v2 P2 role importer.

## What is actually connected

The existing Atlas v2/P3 builder already contains **dated, attributed `v2_relationships`**, lossless `v2_relationship_imports`, source-qualified `v2_assertions` / `v2_assertion_sources` and explicitly typed `v2_roles` / `v2_world_imports`. This prototype reuses these immutable Git-derived source records; no person is matched by name, and no new historical event is authored.

The inclusion rule is **every existing P3 relation** of the types `succession`, `imperial_succession`, `regime_change`, `institutional_change` whose period is a **one-time event**. The other P3 relations (kinship, marriage, personal union, treaty and time-windowed co-regency) **do not automatically count as power transfers**. The current source sample contains ten such recorded events, **not ten exhaustively researched power changes in Europe**.

Three events have an *explicit, source-to-role crosswalk* in [hpm-role-linkage-v1.json](../design/atlas-v2/hpm-role-linkage-v1.json):

| Event in existing pilot | Outgoing role | Incoming role | What is (and is not) reviewed |
|---|---|---|---|
| France **1774**, `dn-france-change-1774` | `dn-fr-louis15` | `dn-fr-louis16` | Person IDs, French legal offices, source-year window; **not** accession mechanism or independent archival authentication |
| Elective HRE imperial office **1765**, `dn-hre-change-1765` | `dn-hre-francis` | `dn-hre-joseph` | Separate office holder IDs, **not** hereditary control of all HRE territories |
| French republic **1799**, `ex-fr-1799` | `ex-fr-directory` | `ex-fr-consulate` | Two collective/institutional roles and their sources; **no fictitious personal successor** |

The remaining seven source events are **unlinked candidates**, not failures of historical reality. Missing role mapping is not absence of a ruler. `reviewed_linkage` is a **narrow data-crosswalk stage**, not `primary_checked`, proven transfer mechanics or `ReviewedPowerTransition` in the strong historical sense. Actual historical adjudication is separate manual research.

## Source trace and reproducible counts

The fixed, versioned [SQL overlay](../schemas/hpm_transition_candidate.sql) creates only new `hpm_*` tables/views on a **disposable `:memory:` copy** of the existing Atlas v2/P3 database. For each event, the report includes:

`hpm event → P3 relationship → original P3 raw relation (origin/native_id/dataset/SHA) → P3 assertion → source namespace + original source ID + pinpoint + public HTTPS URL`.

For each of the three linked samples it additionally includes:

`hpm outgoing/incoming role → P2 role → P2 assertion → source namespace + original source ID + pinpoint`.

SQL foreign keys and source existence are validated; case-specific IDs and role direction are **pinned** in the small review manifest. There is no automatic joining by matching names, same year, dynasty or geopolitical code. All ten *accession mechanisms* remain `unknown`, because a P3 `succession` relation alone does not prove inheritance, peaceful change, a coup or the reason for the predecessor's departure.

A report may give **10 source event candidates / 3 explicitly linked cases / 7 unlinked candidates / 0 mechanisms classified**, and the distribution of *source relation labels*. It **must not** convert these into percentages of the last millennium of European political history. For any `--year` slice the denominator is that year's sampled event relationships, including unknown mechanisms; a zero count means only zero qualifying **sample records**, never no transitions in the actual past.

## Reproduce (Python standard library)

```sh
python3 -m scripts.historical_power_sqlite
python3 -m scripts.historical_power_sqlite --year 1774
python3 -m unittest discover -s tests -p 'test_historical_power_sqlite.py' -v
```

The builder reads Git-tracked `data/atlas` and world-pilot source files through the existing v2 P3 preview, which uses a temporary copy of v1 SQLite and then `:memory:`. Its new `hpm_*` overlay remains in memory, is put into `PRAGMA query_only=ON` after validation, and is discarded when the process exits. No new `.sqlite`, `.json` report, build assets or historical assertions are written to the repository, publication pipeline, Pages or private Google Drive.

`PRAGMA integrity_check`, `foreign_key_check`, unchanged `user_version=1`, `query_only=ON`, public-URL checks and negative regression tests are mandatory. A green CI means **structural reproducibility**, not historical truth (`historical_truth_verified_by_ci=false`). The existing open cases in [#56](https://github.com/Dmitry-dev-pet/rulers-chronology-audit/issues/56) remain unresolved.

## Still outside P2

- No data mutation, source record additions, or new Smuta research.
- No scope inference about European countries or the world beyond a documented pilot.
- No published aggregation dashboard, map or new homepage navigation; those belong to **P3/UI** under a feature flag.
- No automatic historical mechanism or violence classifications, even where the source text suggests an interpretation. Those require explicit additional source claims and independent review.
- No generalization to 1066, 1917 or cases without reviewed source IDs.
