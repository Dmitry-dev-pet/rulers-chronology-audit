# Wikidata P6 — five source-checked person identities across epochs

**13 October 2026.** Follow-up to [issue #46](https://github.com/Dmitry-dev-pet/rulers-chronology-audit/issues/46), after the verified and merged [P5 PR #51](https://github.com/Dmitry-dev-pet/rulers-chronology-audit/pull/51).

Five existing canonical people gain **only** an explicit `external_ids.wikidata` identity reference.
No sourced historic reign, dates, political assessments, calendars, nationalities,
institutional records, original poster, or world-pilot row changes.

| Canonical identity | Reviewed QID | Independent identity context (not a blanket verification of dates) | Wrong join to avoid |
| --- | --- | --- | --- |
| `person-518c301e51f1510b` Василий I Дмитриевич | [Q272156](https://www.wikidata.org/wiki/Q272156) | [BРЭ — Vasily I, scholarly monograph](https://bigenc.ru/b/vasilii-i-dmitrievich-veli-f4325f): son of Dmitry Donskoy, Grand Prince of Moscow 1389–1425 | Vasily **II** [Q210359](https://www.wikidata.org/wiki/Q210359) is his son and a separate person |
| `person-17f5e2c4755255cf` Дмитрий Юрьевич Шемяка | [Q1282778](https://www.wikidata.org/wiki/Q1282778) | [Большая российская энциклопедия](https://bigenc.ru/c/dmitrii-iur-evich-velikii-kniaz-moskovskii-624f7f): son of Yuri Dmitrievich, Grand Prince 1446–1447 | This identity link does **not** resolve different source interpretations of 1445/1446 political authority |
| `person-064d44a263475033` Елена Глинская | [Q240150](https://www.wikidata.org/wiki/Q240150) | [Historical encyclopedia record](https://www.hrono.info/biograf/bio_ye/elna_glinska.php): wife of Vasily III, mother of Ivan IV, regent 1533–1538 | Wife / regent ≠ independent crowned grand prince or sovereign in the same office |
| `person-498f36e1a791592b` Леонид Брежнев | [Q765165](https://www.wikidata.org/wiki/Q765165) | [FRUS, U.S. State Department, 1976 diplomatic meeting](https://history.state.gov/historicaldocuments/frus1969-76v16/d251): Leonid I. Brezhnev, General Secretary of the CPSU | Do not equate party role, the separate Supreme Soviet post and all practical power; Wikidata search false positive [Q274924](https://www.wikidata.org/wiki/Q274924) is a **ship**, not Brezhnev |
| `person-8183e0ee65675a44` Никита Хрущёв | [Q35314](https://www.wikidata.org/wiki/Q35314) | [FRUS, U.S. State Department, 15 October 1964](https://history.state.gov/historicaldocuments/frus1964-68v14/d51): Khrushchev replaced as Soviet party First Secretary and Council of Ministers Chairman | Namesake Soviet journalist [Q4501920](https://www.wikidata.org/wiki/Q4501920) is a different human |

All Wikidata QIDs were examined individually for **person vs object**, named
role, historical time window and contextual identity. This is a
person-identity reconciliation, **not** confirmation of every Wikidata
P39 claim, office's legal interval, regency status, factual authority,
ethnicity or borders.

**Expected when merged:** 83 canonical persons, **30** reviewed canonical
QIDs and **53** canonical persons remaining to review; international 27/27
linked people remain independent; combined explicitly reviewed QIDs **57/110**.
These are expected *after-merge* counts, not a 13 October live Wikidata
audit report. The earlier P5 **195** P39 statements and **128** unmatched
across P2/P3 are a dated baseline and must be recomputed after this PR.

Regression tests check all five explicit identities, correct role separation,
rejected homonyms and unique person QIDs. No fuzzy joins; the original
`biography_status=incomplete` for each person remains unchanged.
