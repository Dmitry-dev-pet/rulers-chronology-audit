# Wikidata P2 — identity crosswalk and legal-office review

**Status:** source-scoped research projection, 11 October 2026. No automatic historical import, person merges, territorial assertions, de-facto leadership, or public SPA changes.

## Scope and audited QIDs

P1 had three confirmed Russian QIDs. P2 adds **six** manually reviewed canonical identity references in the existing person's `external_ids.wikidata` field:

| Person | QID | Historical role used in identity review |
| --- | --- | --- |
| Peter I | [Q8479](https://www.wikidata.org/wiki/Q8479) | tsar and emperor; multiple distinct legal stages |
| Vladimir Lenin | [Q1394](https://www.wikidata.org/wiki/Q1394) | chairman of Soviet Russian/Union government |
| Joseph Stalin | [Q855](https://www.wikidata.org/wiki/Q855) | party secretary; Council of People's Commissars / Ministers |
| Mikhail Gorbachev | [Q30487](https://www.wikidata.org/wiki/Q30487) | party secretary; Soviet state posts; USSR president |
| Mikhail Kalinin | [Q229828](https://www.wikidata.org/wiki/Q229828) | Russian/Soviet state institutions, not a film director |
| Georgy Lvov | [Q297032](https://www.wikidata.org/wiki/Q297032) | first minister-chairman of the 1917 Provisional Government |

The world pilot receives **17** independently reviewed Wikidata identity QIDs via [reviewed-world-links-v1.json](../design/wikidata/reviewed-world-links-v1.json). All **24** world-only identities remain *outside* canonical v1. The 17 QIDs mean individual reference links only; they DO NOT make those people one of the 83 canon people, assert sovereignty, or automatically populate legal tenure tables.

A review compares available pilot name, historical role, era, polity/context and the Wikidata entity description. The registry retains both local source paths and external entity URLs. A QID review is **identity-level**, not proof of the historical truth of every source statement. A match on a single name is not sufficient.

Two rejected name-search matches are explicitly recorded:

| World-pilot person | Rejected QID | Reviewed person QID | Reason |
| --- | --- | --- | --- |
| Frederick II of Prussia | [Q130221](https://www.wikidata.org/wiki/Q130221) | [Q33550](https://www.wikidata.org/wiki/Q33550) | medieval HRE emperor ≠ 18th-century Prussian monarch |
| Leopold II, Holy Roman Emperor | [Q12967](https://www.wikidata.org/wiki/Q12967) | [Q151321](https://www.wikidata.org/wiki/Q151321) | Belgian king ≠ Habsburg elector/emperor |

These rejections prevent a crawler from trusting first search hits.

## P39 positions: legal office vs factual control

Our manually reviewed [office-crosswalk-v1.json](../design/wikidata/office-crosswalk-v1.json) maps **Wikidata position item QIDs**, not strings or modern state labels.

| Wikidata position | Our reference | Decision |
| --- | --- | --- |
| [Q2618625](https://www.wikidata.org/wiki/Q2618625) Emperor of all the Russias | `emperor`, imperial context | exact *office-item* candidate (not tenure equality) |
| [Q1255261](https://www.wikidata.org/wiki/Q1255261) USSR president | `president-ussr`, Soviet Union | exact office-item candidate |
| [Q4376657](https://www.wikidata.org/wiki/Q4376657) Chairman of Supreme Soviet | `vs-ussr`, Soviet Union | exact office-item candidate |
| [Q4376674](https://www.wikidata.org/wiki/Q4376674) Chairman of USSR Council of Ministers | `cm-ussr`, Soviet Union | exact office-item candidate, **not** former SNK USSR |
| [Q1048744](https://www.wikidata.org/wiki/Q1048744) General Secretary of CPSU | `general-secretary` and separately `first-secretary` | **office_family_only**: changes of role title and historic 1934/1953 distinctions cannot be flattened |
| [Q3240735](https://www.wikidata.org/wiki/Q3240735) King of Prussia | world context `pr` | external_only, no v1 office |
| [Q181765](https://www.wikidata.org/wiki/Q181765) Holy Roman Emperor | world context `hre` | external_only, not a modern German sovereign state |

An `exact_office` mapping is merely a **proposal** for comparing a Wikidata P39 *type* with our canonical office type. It does not validate a person's whole reign or political authority. A P39 claim and a v1 tenure must still have matching confirmed **person ID**, office ID, and source-scoped political context. We compare P580/P582 qualifiers with the retained calendar and precision; unknown or different calendars yield `calendar_review`. Deprecated assertions do not support matching. We retain all raw statement IDs and reference pointers.

**Conspicuous tests:** Stalin's 1946 Council of Ministers position must *not* silently map into v1 composite `legacy-g06`. Peter I's 1721 start is known only to a year with unspecified calendar in the canon, so a day-accurate Julian date from Wikidata cannot become an automatic exact match. Neither title nor party office grants a `real_ruler` boolean.

## Commands and delivery

```bash
python3 -m unittest tests.test_wikidata_sync tests.test_wikidata_office_review -v
python3 -m scripts.wikidata_sync --discover
python3 -m scripts.wikidata_office_review --input reports/wikidata/latest.json
```

P2 adds outputs `reports/wikidata/offices.json` and `reports/wikidata/offices.md` alongside the existing identity/date report. The same weekly GitHub Actions job uploads all four files as a review artifact. A **manual opt-in** `open_report_pr=true` can propose the four external-only reports for review. It never edits canon, provenance, underlying poster, v2 geometry, SQLite, actual-power assessments or GitHub Pages. There are no API calls from the SPA.

**Next gate:** independently verify source-level terms for proposed legal-office matches; only then design new v2 entries with date-qualified assertions. The P2 read-only report itself creates zero new world tenure records.
