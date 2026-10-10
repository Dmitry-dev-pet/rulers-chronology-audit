# Cartographic orientation registry, version 1

Read ../../docs/SMUTA_PILOT.md before editing. The user approved a city-point pilot, not reconstruction of historical borders.

- This directory is independent of data/atlas/territorial_evidence. Coordinates are contemporary reference anchors for named places, never automatically historical control geometry.
- Keep coordinate_kind=modern_reference_only, historical_borders_verified=false, historical_truth_verified_by_ci=false.
- Each point requires a source URL/title, review date, original latitude/longitude DMS, the decimal conversion, and a readable limitation distinguishing the place anchor from an exact historic building/camp site.
- Reference existing evidence IDs explicitly. Every authored geographic observation must remain mapped once or listed as unlocated with an explanation; multi-city claims must not become fabricated single points or polygons.
- Do not add historical borders, routes, continuous control periods, new rulers, biographies, or unsourced factual interpretations through this registry.
- Geographic source accuracy is independent of historical evidence accuracy. Never use a modern coordinate source as proof of political control.
- Run unittest, all legacy build stages, atlas_db build, smuta_map build and the Chromium browser acceptance suite before publishing. Preserve old data/provenance and private-photo exclusion.
