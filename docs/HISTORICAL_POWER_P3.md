# Historical Power Model · P3 (opt-in source audit UI)

**Status:** review gate, 13 October 2026 · [Issue #61](https://github.com/Dmitry-dev-pet/rulers-chronology-audit/issues/61). Research-only pilot; not a new canon, full European history, or migration. P0–P2 remain the documented method in [HPM v1](HISTORICAL_POWER_MODEL_V1.md) and [P2](HISTORICAL_POWER_P2.md).

## Entry, scope and denominator

After review and merge, the **existing** GitHub Pages site hosts one additional research surface:

[Open HPM P3 lab](https://dmitry-dev-pet.github.io/rulers-chronology-audit/v2.html?hpm=pilot#/timeline/1762)

The URL parameter `hpm=pilot` activates the source lab inside the existing `v2.html` SPA. Removing the flag closes the lab and preserves the normal app; `index.html`, its scripts, and the public homepage remain unmodified. A link in the opt-in v2 page enters the same mode. Supported reproducible filters:

- `hpmYear=1774` — an **event-year index** within 1762–1800; not day-precision or proof of simultaneous reigns.
- `hpmCtx=ctx-world-fr` — only a source-linked historical context already present in P3; **not** a modern national polygon.
- `hpmLink=reviewed_linkage` or `candidate` — whether original relation and two role IDs have passed the narrow crosswalk check.

For every chosen filter, display `N` in the source **sample**, unknown accession mechanisms `unknown/N` and ID-crosswalks `linked/N`. Relation-category bars refer solely to the **labels of the original source relationships**, not inheritance/election/coup/violence. `0 / 0` means no qualifying source record in this specific set, **never** that a region had no ruler or no political transfers. The answer to “How did power pass in Europe over 1000 years?” remains “the researched sample cannot support that inference.”

The **full currently reviewed P2 sample** contains 10 source event candidates, 3 narrow role-ID linkages, 7 candidate-only relations, and 10 unknown accession mechanisms. These are not ten complete historical power transfers nor a representative population. Explicitly traced examples are **1765 Holy Roman Empire elective imperial dignity**, **1774 France**, and **1799 French republic collective institutions**. No personal ruler is invented for the latter.

## Reproducible source chain

`scripts/historical_power_pages.py` calls the existing `scripts/historical_power_sqlite.py` preview and derives `hpm-pilot.json` from its **in-memory, query-only** SQLite. It enriches P2 records with existing context labels, relation statements, reviewed role titles, original record SHA-256 and source pinpoints. It adds **no fact**, historical inference, external fetch, or database migration.

The detail panel exposes:

`source relation event → historical context(s) → v2 assertion and caveat → source namespace/native ID + document + pinpoint → original relation ID, dataset and SHA-256`.

For 3 events with crosswalks, the separate outgoing/incoming typed role IDs and their documentary sources are shown. Each record still has `accession_mechanism = unknown`; source verification is not archival authentication. No new research on 1598–1613 and no territorial border geometry. A one-click route into the existing v2 graph allows examining surrounding source links, independently of HPM's unknown classifications.

Only `v2.html`, `hpm-pilot.json`, `historical-power-lab.js`, and `historical-power-lab.css` change in the v2 published output; the new P3 files are flat and covered by `SHA256SUMS` and the Pages allowlist. The public report rejects unsafe/non-public source URLs, including private Google Drive; the original poster remains outside Pages.

## Acceptance

- `python3 -m unittest discover -s tests -p 'test_historical_power_pages.py' -v` (P2-derived counts, role-ID direction, trace, explicit unknown, privacy and deterministic projection).
- `python3 -m scripts.atlas_v2_pages --dist dist` after the standard chronological and SQLite build stages; unchanged root index SHA-256, no extra files outside allowlist.
- `python3 tests/browser_historical_power_p3.py --dist dist --output browser-evidence/hpm-p3` in Chromium/Playwright at 1440×960, 390×844, 320×640 and 844×390.
- Default v2 without `hpm=pilot` shows no lab. With flag: sample counts, safe HTTPS links and pinpoints, all event-year filters including 0-result caveat, institution/role disambiguation, accessible buttons and Escape/close/history navigation.
- Full historical-atlas CI and old v2 graph, mobile SPA and page-regression tests must also pass. A green CI validates **software and references only**: `historical_truth_verified_by_ci = false`.

## Explicitly out of scope

A complete `PowerTransition` population, source-reviewed historical mechanisms, day-level simultaneity, confidence probabilities, political violence classifications, competing historical interpretation adjudication, newly reconstructed borders, broad percentages and Atlas/SQLite v1 schema migration. P4 requires **another** explicit decision; P3 is not migration approval.
