---
date: 2026-06-06
topic: pipeline-parity-and-automation
---

## Summary

Get the GHS dashboard pipeline to a state where monthly data refreshes are practical and low-friction. Four phases: achieve parity between the repo and the live ArcGIS dashboard (field names and data layers), add DQ checks that make updates trustworthy, validate the upload workflow with already-processed layers, then automate the end-to-end pipeline so a refresh requires a single command.

---

## Problem Frame

The repo and the live ArcGIS dashboard have drifted. André's processing added roughly a dozen new fields directly in ArcGIS that are not in the notebooks or pipeline script, and field names between the repo's output and the ArcGIS feature service don't match. Local analysis work and the live dashboard are not directly comparable, which makes every proposed update feel risky.

The ArcGIS upload process compounds this: adding new columns requires column-by-column manual uploads. The result is a backlog of fully-processed data that hasn't been uploaded (lead paint, GHS survey) and reluctance to start new work because shipping it is painful.

---

## Key Decisions

**Parity before new features.** Field name mismatches and missing André layers make local analysis untrustworthy. Parity must come first even though it delivers no new campaign-facing value.

**ArcGIS stays as the deployment target.** The dashboard's filtering capabilities have no comparable alternative given current JS skills and bandwidth. Upload automation — not dashboard replacement — is the lever to reduce friction.

**`pipelines/join_to_schools.py` is the canonical join.** No new join work goes into `notebooks/join_to_schools.ipynb`. The notebook stays for reference; the pipeline script is where all future development happens.

**GHS survey branch closes before parity work begins.** The branch is 90% done. Closing it removes one open thread and produces a layer ready for the upload validation phase.

---

## Requirements

**Parity**

R1. All layers from `docs/Andre Processing Notes.md` are implemented in `pipelines/join_to_schools.py`: snap points by building code (geometry fix), school districts (verify if already present), assembly districts, state senate districts, subway walking distance, peaker plant distance, hurricane evac zone / heat exposure index / evac center distance / cooling center distance, air pollution (PM2.5 and NO2), stormwater flood risk, open street flag, and percentile/quartile conversions for LL84 energy fields and air pollution fields.

R2. Column names in the pipeline's output match the field names in the live ArcGIS feature service. A field list export from ArcGIS establishes the target schema; mismatches surface as errors, not silent renames.

R3. The snap-points-by-building-code geometry fix is applied to school points before any spatial joins run.

**DQ checks**

R4. After each join in `pipelines/join_to_schools.py`, assertions verify: row count is unchanged, null counts on key existing columns haven't increased, and no duplicate `LocationCode` values are present.

R5. Join match rate is logged for each layer; a match rate below an expected threshold triggers an error and halts export.

R6. Before export, a final assertion compares the output field list against a pinned expected schema, catching unintended column additions or drops.

**GHS survey completion**

R7. `notebooks/process_ghs_survey_data.ipynb` is finalized. The only field added to the join is a count of respondents per school who expressed willingness to get involved; no raw or identifying survey data is included.

R8. The GHS survey field is added to `pipelines/join_to_schools.py` and the `process-ghs-survey-data` branch is merged and closed.

**Upload validation**

R9. Lead paint data (`notebooks/schools_lead_paint.ipynb` — already processed) is added to the join and uploaded to ArcGIS, validating the upload workflow end-to-end before further new layers are added.

R10. GHS survey data (from R7–R8) is uploaded to ArcGIS as a second upload validation exercise.

**Pipeline automation**

R11. A single command (e.g., `just update`) runs all individual processing scripts in sequence and produces an updated `data/processed_data/master_schools.geojson`.

R12. The `just update` command includes the DQ checks from R4–R6 and aborts with a clear error message if any check fails.

**Upload automation**

R13. A scripted column-by-column upload reduces the manual ArcGIS update process to a single command. Full-service overwrite is not a viable approach: the ArcGIS setup has three layers (hosted feature service → web map → dashboard), and replacing the feature service in place breaks all dashboard widget and filter field mappings. New columns must be added to the existing service to preserve those mappings.

R14. New columns are first tested against a duplicate (staging) dashboard before being applied to the live public-facing dashboard.

---

## Scope Boundaries

**Deferred for later**
- Net-new data layers (green schoolyard, lead pipes, asbestos, etc.) — start after pipeline automation is in place and the upload workflow is validated with lead paint and GHS survey
- Ventilation/A/C web scraping — requires getting the existing scraping code into the repo first (separate workstream)
- Simplifying school locations processing (LCGMS-only + Google Maps geocode) — deferred until before the next LCGMS data drop, expected later in 2026

**Out of scope**
- ArcGIS dashboard replacement — filtering requirements have no comparable open-source alternative; remains a long-term aspiration only

---

## Dependencies / Assumptions

- A field list export from the live ArcGIS feature service is required before column name reconciliation (R2) can be scoped. Without it, the mismatch is not estimable.
- André's working scripts in `notebooks/andre_working/` are the reference implementation for the parity layers in R1.
- The `arcgis` Python package can add new columns to an existing hosted feature service without a full overwrite (assumed; if false, upload automation takes a different scripted approach).

---

## Outstanding Questions

**Resolve before planning**

*(None remaining)*

**Deferred to planning**

- Does the snap-points-by-building-code geometry fix need to be applied once and saved back to `data/processed_data/school_points_with_lcgms.*`, or re-run at the start of each pipeline execution? (Determine from André's `notebooks/andre_working/snap_points_by_BuildingCode.py`.)
- Full column name reconciliation: compare `pipelines/join_to_schools.py` output schema against the 179-field ArcGIS schema to identify all mismatches (not just the confirmed `ZohranFirstRoundFrac` → `ZohrPrimR1` one).
- IBO School Barriers fields: determine whether they were ever uploaded to ArcGIS, need to be uploaded, or should be dropped from the pipeline.
- What is the remaining 10% of work on the GHS survey notebook?
- What is `docs/join_to_schools.py`? Is it André's version, an older copy, or something else? Should it be moved to `pipelines/` or deleted?
- What join match rate thresholds (R5) are acceptable for each layer? Some layers like subway distance will have near-100% coverage; others may legitimately have gaps.

---

## Sources

- André's processing notes and reference scripts: `docs/Andre Processing Notes.md`, `notebooks/andre_working/`
- Existing pipeline script (covers boroughs, DACs, election results, A/C, ventilation, capacity/utilization, BAP, IBO barriers, solar readiness, city council + school districts, LL84): `pipelines/join_to_schools.py`
- Project plan and phased overview: `docs/plan.md`
- Live ArcGIS feature service (179 fields, queryable via REST): `https://services7.arcgis.com/2QFP7OYxiYK7rWSP/arcgis/rest/services/master_schools_v2/FeatureServer/0?f=json`
- ArcGIS dashboard item: `https://ecosocialists.maps.arcgis.com/home/item.html?id=b16342d504e04a9a9320637906fed6f1`
- Confirmed field name mismatch (at minimum): `ZohranFirstRoundFrac` (pipeline) → `ZohrPrimR1` (ArcGIS). A full comparison of pipeline output columns against the 179-field ArcGIS schema is needed during planning.
- André's layers are confirmed present in ArcGIS (`hurricane_evacZone`, `OHEI`, `evacCenters_distance_mi`, `cooling_centers_distance_mi`, `subway_dist`, `on_open_street`, `NY_State_Senate_District`, `NY_State_Assembly_District`, `pm25_2022`, `no2_2022`, `Flood_Scenario`, `Stormwater_Flood_Risk`, `peaker_mi`, percentile fields). Parity work adds these to the pipeline script so local output matches what is live.
- IBO School Barriers fields appear in `pipelines/join_to_schools.py` but are not in the ArcGIS field list — status unknown (never uploaded, or dropped).
- Lead paint and GHS survey fields are not in ArcGIS — confirmed upload backlog items for R9–R10.
