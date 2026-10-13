# Wikidata P7 — three distinct Soviet institutional P39 office types

**13 October 2026, for [issue #46](https://github.com/Dmitry-dev-pet/rulers-chronology-audit/issues/46).**
A small **read-only classification** step following [P6's live research](../research/wikidata/p6-live-2026-10-13.md).
The 1977 Soviet Constitution, historical reference literature and live Wikidata
office items were checked for **office type only**, not for each person's
legal tenure, political influence or territory.

## Three source QIDs, three different legal meanings

| Wikidata P39 office item | P7 registry decision | Independent context and barrier |
| --- | --- | --- |
| [Q15628644](https://www.wikidata.org/wiki/Q15628644) deputy of Supreme Soviet of USSR | **P3** `legislative_membership`, `ctx-ussr-supreme-soviet` (new, independent `legislative_institution` context) | Legislative deputy **≠** Supreme Soviet chair; **≠** chair of its Presidium; **≠** regional/republican legislature. |
| [Q115135185](https://www.wikidata.org/wiki/Q115135185) candidate for Politburo | **P3** `party_candidate_membership`, existing `ctx-cpsu-politburo` | A candidate has a different status from a full member [Q108495011](https://www.wikidata.org/wiki/Q108495011). It is not a state office. |
| [Q135215773](https://www.wikidata.org/wiki/Q135215773) chair of Presidium of Supreme Soviet of USSR | **P2** `exact_office` *office-type candidate* for existing `presidium-vs` / `ussr` | Separate from [Q4376657](https://www.wikidata.org/wiki/Q4376657), the **Chairman of the Supreme Soviet** (canonical `vs-ussr`, especially 1989–1991); formal duty **≠** practical dominance. |

The “exact_office” label is strictly a **crosswalk of office *types***,
not a statement that every P39 position held (or every externally recorded
date) is independently verified. A canonical person, office and USSR
jurisdiction must already agree before a *candidate* tenure can be reported.
The P7 code creates **no new canonical tenure**. Only documentary/source
review could later promote a statement to a historical assertion.

A new separate `ctx-ussr-supreme-soviet` context represents the **all-Union
legislature**. It is neither an alias for `ussr` nor an imported modern
sovereign state. Its `same_as_canonical_state=false`,
`geographic_boundaries_verified=false` and
`related_not_equivalent` safeguards are enforced by regression tests.

## Evidence used (distinct from raw Wikidata references)

- [1977 USSR Constitution (arts. 107–120)](https://www.servat.unibe.ch/icl/r100000_.html):
  deputies elected to the Supreme Soviet; a standing Presidium, **elected
  from among the deputies**, with a separate chair and collective mandate.
- [USSR: A Country Study (Library of Congress, hosted by USMC)](https://www.marines.mil/Portals/1/Publications/Soviet%20Union%20Study_5.pdf):
  legal/symbolic Presidium chair and later changes around 1988–1989 are
  distinct from personal effective leadership.
- [Faust and colleagues, *Social Networks* 24 (2002)](https://sites.socsci.uci.edu/~kfaust/faust/research/articles/faust_et_al_soviet_sn_2002.pdf),
  pp. 232–234: the Politburo had **full voting members** and **candidate
  nonvoting members** (without treating formal voting as exhaustive of political power).
- [Archontology — Politburo chronological reference](https://archontology.org/nations/ussr/cpsu/politburo_hist.php):
  candidate status distinguished from full membership, including shifts in
  the Soviet period.

These independent texts establish **types**, not full Wikidata birth,
start/end-date or hierarchy accuracy. Source dates, P39 statement IDs,
references, rank and precision continue to be retained untouched by the
existing read-only reconciliation. **Do not promote unmatched day-level
dates or infer a ruler from a deputy/candidate status.**

## Pre-P7 reproducible source snapshot

The P6 [live artifact](https://github.com/Dmitry-dev-pet/rulers-chronology-audit/actions/runs/38379007147)
reported **214 total P39 claims** for 57 reviewed identities, with **143**
claims not classified in either P2 or P3. In the original source report,
each of the **three** P7 QIDs occurred **7 times** (21 *statements*,
not 21 unique persons). Example concrete source statements retained for
post-P7 regression/review:

- Deputy: `Q855$01504925-DC87-491B-B925-B94FD7C402F2`
  (Stalin's Wikidata P39 claim; *not* evidence of sole rulership).
- Politburo candidate: `Q765165$cf6db71a-4403-8a3a-664e-7dc2e694870a`
  (Brezhnev's candidate-period claim).
- Presidium chair: `Q295781$02c05a2a-413d-b444-9e61-ebb778785830`
  (Podgorny 1965–1977 P39 statement; matching pre-existing
  `tenure-s11` is a comparison, not an import).

**Expected after P7**, *if the Wikidata P39 source snapshot is unchanged*:
the 21 reviewed statements move from the unmapped queue into
7 canonical-office type candidates plus 14 separate P3 institutional types,
so **143 → 122** remain without either mapping. Exact current counts are
subject to a **new live read-only audit**; the fixture/citation counts above
are historical snapshots, not guaranteed API invariants.

### Acceptance

- Existing 83 canonical Russian people, 97 tenures, 150 provenance rows,
  and independent 27 world-only people remain unchanged.
- `Q135215773 → presidium-vs`; `Q4376657 → vs-ussr`; neither maps to
  `president-ussr` nor implies sole power.
- Politburo candidate and full member have distinct `position_kind`
  even though they share the *same* party institution context.
- The legislative and party membership types cannot be assigned to the
  wrong context; original 1762–1800 pilot selection semantics stay intact.
- No new real-power, borders, ethnicities, personal unions, historic
  dates, biographies, public Pages assets or SQL schema updates.
- CI passing verifies structure only; source history requires independent
  scholarly review.
