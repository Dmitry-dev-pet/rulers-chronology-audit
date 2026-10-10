# Canonical atlas data

Read ../../docs/DATABASE.md before editing this directory.

- Git-tracked JSON/JSONL is the editable source for the normalized database. SQLite and dist/ are derived outputs; never edit them as the source of truth.
- One stored person ID per identity. Labels may change; IDs must not. Do not infer identity matches from surnames or fuzzy name similarity.
- Keep ethnicity, citizenship, dynasty and birthplace distinct. Do not infer any of them from a person's name or the state they governed. New assertions require sources and verification status.
- Existing lifespan_text facts preserve earlier review wording. They are NOT verified birth dates. Add separate calendar-qualified birth/death assertions; do not promote the import silently.
- Never infer actual political dominance from holding an office. Power assessments require evidence, interval qualifications and uncertainty. Collective bodies and initial memberships must stay collective and time-qualified.
- Every source record and its original ordering are preserved in provenance.jsonl. Do not rewrite imported raw rows, old research files or the original poster to agree with a new conclusion.
- New, corrected conclusions may be separate sourced assertions. Preserve conflicting evidence; do not overwrite a competing interpretation without documenting the decision.
- Ordinary validation/build must not rerun migrate. The migration refuses to overwrite existing data intentionally.
- Run python3 -m scripts.atlas_db validate, the full unittest suite, the four legacy build stages, then python3 -m scripts.atlas_db build.
- Do not update source hashes blindly to silence a mismatch. Coordinate intentional old/new source changes explicitly.
- Public exports must exclude the original image, private Drive URLs and secrets. Technical success is not historical attestation.

- Transition-case `territorial_evidence` entries are place-level documentary observations, **not continuous control polygons**. Preserve the distinction between an official claim, a locally documented allegiance, military presence, resistance, and actually operating government.
- Geography requires a sourced assertion, date with honest calendar/precision, a caveat about what it does *not* establish, linked event IDs, and `geometry_verified=false`. Do not add polygons or point coordinates without a separately reviewed cartographic procedure and versioned contract.
- Primary laws from 1991 determine jurisdiction *asserted by the issuing authority*, not automatic evidence of implementation across an entire republic. No automatic federal control coloring. Source methodology: `research/territorial-jurisdiction-1608-1612-1991.md`.
