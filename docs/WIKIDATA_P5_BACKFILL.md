# Wikidata P5: reconcile European backfill and three Soviet-era identities

**13 October 2026.** Incremental source-checked *identity* linkage for issue #46,
following the merge of Europe backfill PR #34. No person is merged by string
similarity; no office, actual-power, ethnicity, territorial border, calendar date,
historical tenure or public SPA record is imported from Wikidata.

## Why this change was necessary

PR #34 added three new people to
`data/atlas/world-pilots/coverage-backfill-1762-1800.json`. The read-only
`scripts.wikidata_sync.roster` still enumerated only the three older
world source files, so the new European persons were absent from weekly identity
checks. P5 includes the distinct `person_additions` input, then reviews
and explicitly links the three new world-only IDs. Previous 24 international
people remain separate from all 83 canonical Russian persons.

| Registry / canonical ID | QID | Distinguishing evidence | Important restriction |
| --- | --- | --- | --- |
| `world:pt-jose1` | [Q1058391](https://www.wikidata.org/wiki/Q1058391) | [Portugal's Parliament](https://www.parlamento.pt/VisitaParlamento/Paginas/BiogDJose.aspx), `BG02` | José I of Portugal, 1750–1777, **not** Joseph I of HRE; do not turn Pombal's influence into a royal office |
| `world:sw-adolf-fredrik` | [Q52931](https://www.wikidata.org/wiki/Q52931) | [Swedish Royal Court](https://www.kungligaslotten.se/english/list-of-swedish-monarchs/adolf-fredrik.html), `BG05` | Swedish sovereign 1751–1771; legal kingship does not establish practical dominance |
| `world:tusc-ferdinand3` | [Q309605](https://www.wikidata.org/wiki/Q309605) | [Habsburg history](https://www.habsburger.net/en/chapter/grand-duke-ferdinand-iii-tuscany-regent-times-change), `BG09` | Grand Duke of Tuscany from 1790, expelled in 1799; years alone do not prove later territorial control |
| `person-0157c71b66e75976` (Николай Подгорный) | [Q295781](https://www.wikidata.org/wiki/Q295781) | [Presidium of Supreme Soviet historical survey](https://www.encyclopedia.com/history/encyclopedias-almanacs-transcripts-and-maps/presidium-supreme-soviet), canonical `tenure-s11` | USSR Presidium chair 1965–1977; not the **actor** Nikolai Podgorny [Q4367385](https://www.wikidata.org/wiki/Q4367385) |
| `person-036c05d6218659ca` (Нариман Нариманов) | [Q1956360](https://www.wikidata.org/wiki/Q1956360) | [Azerbaijan Ministry of Foreign Affairs biography](https://www.mfa.gov.az/en/news/neriman-necef-oglu-nerimanov), canonical `body-08ccf4e4f276522d` | Joint CEC USSR membership is not sole headship; birth date variants in the external source are **not** imported |
| `person-0ee596fb65215c40` (Григорий Петровский) | [Q2620906](https://www.wikidata.org/wiki/Q2620906) | [Encyclopedia of Modern Ukraine](https://esu.com.ua/article-890013), canonical `body-08ccf4e4f276522d` | Collective CEC role, not individual tenure; reported birth-place/date disagreements are left untouched |

The separate world registry rejects **artwork** [Q106378947](https://www.wikidata.org/wiki/Q106378947)
(Adolf Fredrik portrait) and [Q117829867](https://www.wikidata.org/wiki/Q117829867)
(Ferdinand III painting). A named depiction is not a person.

## Exact limits and expected report

- Canonical people: **83**, reviewed QIDs **22 → 25**; **58** identities still need review.
- Separate world-only people: **24 → 27**, with **27 reviewed QIDs**.
- Total roster: **107 → 110** entries, **46 → 52** identity links.
- No world-to-canonical merges or new v1 tenure/biography/power facts.
- Counts of Wikidata P39 statements, typed/unmapped legal offices and calendar
  disagreements require a **new live audit**; the P3 figures (179 P39,
  115 unmapped) describe 11 October only, and cannot be copied as current.

Validation: `python3 -m unittest tests.test_wikidata_sync
tests.test_wikidata_office_review tests.test_wikidata_jurisdiction_review -v`.
Then run the usual full CI and a manual or scheduled read-only Wikidata audit.
No automatic historical import or merge of this research PR.

## Live research gate passed — 13 October 2026

A branch-isolated no-write Wikidata reconciliation completed successfully in
[workflow run #38377773382](https://github.com/Dmitry-dev-pet/rulers-chronology-audit/actions/runs/38377773382).
The complete dated methodology and measured counts are preserved in
[the P5 receipt](../research/wikidata/p5-live-2026-10-13.md).

The live run confirmed **110** distinct roster entries, **52** reviewed identity
QIDs, **58** candidate-only name searches, and **195** P39 position statements.
Of these, 171 lack a mapping in the *P2 legal-office registry alone*; 43 of
those are classified in the disjoint P3 jurisdiction registry. Therefore
**128 P39 statements remain without either kind of reviewed classification**
(after accounting separately for 1 deprecated, 14 exact canonical, 7 external,
2 office-family and 43 P3-typed statements). All **eight** P4 vetted crown
claims matched their known source statements without drift.

All **55** targeted offline tests passed; the run did not edit canonical
history, inferred power, source provenance or Pages inputs. The one-time
branch-only live-audit workflow was removed after running; weekly/manual
read-only reconciliation policy remains unchanged.
