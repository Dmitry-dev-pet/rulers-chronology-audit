# Wikidata P3: distinct historical jurisdictions and remaining identity review

**Status:** additive research layer, 11 October 2026. No canonical source rewrites,
no invented sovereign countries, no geographic borders, no ethnicity and
**no inference of actual political control** from Wikidata position held (P39).

## 1. Person identity: all world-pilot people linked, but not merged

All 24 formerly unlinked persons from the 1762–1800 international pilots now
have an individually reviewed Wikidata QID in
[reviewed-world-links-v1.json](../design/wikidata/reviewed-world-links-v1.json).
This is an **external identity registry**. They remain outside the 83 canonical
v1 persons, and the world-pilot records, role dates, sources and names are
unchanged. A linked person is not necessarily a sovereign ruler.

Seven world-only identities newly reviewed in P3:

| World ID | Wikidata | Identity-specific caveat |
| --- | --- | --- |
| sw-charles | [Q52928](https://www.wikidata.org/wiki/Q52928) | Charles, Duke of Södermanland; **became King Charles XIII only in 1809**, outside the 1800 pilot |
| pt-joao | [Q676301](https://www.wikidata.org/wiki/Q676301) | future João VI; regency and later reign require distinct legal records |
| es-carlos3 | [Q36234](https://www.wikidata.org/wiki/Q36234) | Charles III of Spain; avoid identically numbered monarchs of other kingdoms |
| pt-maria1 | [Q773874](https://www.wikidata.org/wiki/Q773874) | Maria I of Portugal; sovereign, separate from regent or consort |
| hab-maria-luisa | [Q229826](https://www.wikidata.org/wiki/Q229826) | Maria Luisa of Spain, consort of Leopold II; not an independently elected emperor |
| pt-pedro3 | [Q964094](https://www.wikidata.org/wiki/Q964094) | Pedro III of Portugal; consort and co-monarch concepts must not be conflated |
| hre-francis | [Q151075](https://www.wikidata.org/wiki/Q151075) | Francis Stephen of Lorraine, Emperor Francis I (1745–1765), not Francis II |

Thirteen additional canonical-person identity references were reviewed against
the existing research names, positions and date context and inserted into
`data/atlas/people/*` → `external_ids.wikidata`:

| Canonical person | Wikidata | Identity note |
| --- | --- | --- |
| Alexander I | [Q15193](https://www.wikidata.org/wiki/Q15193) | Russian emperor 1801–1825 |
| Alexander II | [Q83171](https://www.wikidata.org/wiki/Q83171) | Russian emperor 1855–1881 |
| Alexander III | [Q120180](https://www.wikidata.org/wiki/Q120180) | Russian emperor 1881–1894 |
| Alexander Kerensky | [Q48211](https://www.wikidata.org/wiki/Q48211) | 1917 Russian Provisional Government |
| Alexander Trepov | [Q620555](https://www.wikidata.org/wiki/Q620555) | 1916/17 Russian imperial chairman |
| Alexei Kosygin | [Q202770](https://www.wikidata.org/wiki/Q202770) | USSR Council of Ministers |
| Alexis Mikhailovich | [Q7731](https://www.wikidata.org/wiki/Q7731) | Russian tsar 1645–1676 |
| Alexei Rykov | [Q294339](https://www.wikidata.org/wiki/Q294339) | head of RSFSR/USSR government |
| Anastas Mikoyan | [Q152738](https://www.wikidata.org/wiki/Q152738) | Soviet statesman; distinct state posts |
| Andrei Gromyko | [Q184267](https://www.wikidata.org/wiki/Q184267) | Soviet diplomat/state leader |
| Anna Ioannovna | [Q160165](https://www.wikidata.org/wiki/Q160165) | Russian empress 1730–1740 |
| Anna Leopoldovna | [Q159651](https://www.wikidata.org/wiki/Q159651) | Russian regent, not an empress-regnant |
| Boris Godunov | [Q170172](https://www.wikidata.org/wiki/Q170172) | political influence before formal tsarship in 1598 |

**Identity review does not verify each biography date, ethnic group, office or
power interpretation**. These links are not new historical facts. The
remaining canonical persons have unverified QID candidates only; search
ranking never sets `external_ids`.

## 2. Jurisdiction and P39 type crosswalk

See [jurisdiction-crosswalk-v1.json](../design/wikidata/jurisdiction-crosswalk-v1.json)
and [read-only validator/reporter](../scripts/wikidata_jurisdiction_review.py).

| P39 QID | Separate context | Classification |
| --- | --- | --- |
| [Q22722](https://www.wikidata.org/wiki/Q22722) | ctx-hre-electoral-college | Electoral dignity, not the sovereign emperor |
| [Q45341328](https://www.wikidata.org/wiki/Q45341328) | ctx-hab-crown-bohemia | Separate royal crown of Bohemia |
| [Q6412254](https://www.wikidata.org/wiki/Q6412254) | ctx-hab-crown-hungary | Separate Hungarian royal crown |
| [Q19808845](https://www.wikidata.org/wiki/Q19808845) | ctx-andorra-co-principality | French co-prince of Andorra, **not French territory** |
| [Q108495011](https://www.wikidata.org/wiki/Q108495011) | ctx-cpsu-politburo | Membership in a party institution, not a head-of-state office |
| [Q1268572](https://www.wikidata.org/wiki/Q1268572) | world:sw | Swedish monarch office, not prior duke |
| [Q3847454](https://www.wikidata.org/wiki/Q3847454) | world:es | Spanish monarch office |
| [Q3439798](https://www.wikidata.org/wiki/Q3439798) | ctx-crown-france-navarre | Compound royal office; not geographic union by assertion |
| [Q5373953](https://www.wikidata.org/wiki/Q5373953) | ctx-first-french-empire | *Emperor of the French* from 1804, **outside 1762–1800 pilot** |

Separate canonical-office crosswalk [office-crosswalk-v1.json](../design/wikidata/office-crosswalk-v1.json)
now also includes [Q4376682](https://www.wikidata.org/wiki/Q4376682):
the **USSR Council of People's Commissars chairman**, mapped to
`snk-ussr`, not the `snk-rsfsr` chair or the 1946+ `cm-ussr` chair.
Stalin's source composite `legacy-g06` remains intentionally unresolved.

This **does not create new State or office rows**. P3 contexts in a separate
registry can relate to older world contexts, but all relationships are
`related_not_equivalent`; `same_as_canonical_state=false` and
`geographic_boundaries_verified=false` are enforced by tests. In particular
the Kingdom of Hungary is not interchangeable with Habsburg lands; Bohemia,
Hanover, HRE electoral college and France/Navarre have independent rules.

The P3 report keeps all Wikidata P39 statement IDs, references, ranks and
boundary qualifiers. `P580/P582` produce *year overlap candidates* only,
not day-level co-rulership. An office entirely after 1800 is explicitly
`after_world_pilot_window`. Missing precision/date never implies missing
rule. A person with more than one mapped context enters the
`multi_context_candidates` research queue without a fabricated personal
union, continuous control or territorial geometry.

## 3. Execution and safeguards

```bash
python3 -m unittest tests.test_wikidata_sync tests.test_wikidata_office_review tests.test_wikidata_jurisdiction_review -v
python3 -m scripts.wikidata_sync --discover
python3 -m scripts.wikidata_office_review
python3 -m scripts.wikidata_jurisdiction_review
```

Weekly GitHub Actions (Monday 04:17 UTC) creates **six read-only files**
(`latest.{json,md}`, `offices.{json,md}`,
`jurisdictions.{json,md}`) inside the research artifact. Only manual opt-in
`open_report_pr=true` on main proposes these reports for review. Neither
the weekly job nor the optional report PR creates historical records,
publishes them into the atlas, or modifies its read-only SQLite, JSON, SPA,
original photo, 150 legacy provenance records, or power assessments.

Structural green CI is not historical source attestation. The ongoing
research backlog in [issue #46](https://github.com/Dmitry-dev-pet/rulers-chronology-audit/issues/46)
continues for unlinked canonical people and the large number of other P39
office types. Add sources and historical intervals individually only when
the role and political context have been independently checked.
