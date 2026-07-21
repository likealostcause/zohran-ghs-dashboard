# Project Plan

## Current State

The live dashboard runs on ArcGIS Dashboards and is actively used by the campaign. This repo is the data processing layer: Jupyter notebooks process raw source data and produce `master_schools.geojson`, which is manually uploaded to ArcGIS Online.

There are two sources of drift between this repo and the live dashboard:
1. **André's processing** — a set of new data layers and geometry fixes applied directly in ArcGIS that are not yet reflected in the notebooks (documented in `docs/Andre Processing Notes.md`)
2. **Hotfixes** — manual edits made directly in ArcGIS Online by André and others that need to be backported into the processing code

The primary risk this creates: if data in ArcGIS were accidentally deleted or corrupted, we could not quickly reproduce it from this repo.

Data sharing with colleagues is also a pain point — all data is currently shared via manual uploads to Google Drive, which is confusing and unreliable.

## North Star

The long-term goal is to replace the current manual workflow with:
1. **Pure Python data pipelines** — one script per data layer, organized in a `pipelines/` folder, running on a schedule or triggered by source data updates
2. **Custom JS-based map dashboard** — replacing ArcGIS Dashboards with an open-source solution that supports automated data delivery

The ArcGIS workflow has a fundamental ergonomic problem that makes the long-term goal necessary: ArcGIS Online does not support bulk replacement of `master_schools.geojson`, so every new column must be uploaded individually. Automated, live data updates are not feasible under this constraint.

The move to pure Python pipelines also improves: version control of data transformations, data quality testing, reproducibility, and the ergonomics of adding new data layers.

## Guiding Principles

- **Do one thing at a time.** Don't backport parity work and refactor simultaneously — pick one and finish it.
- **Each pipeline script should have a clear "contract" with the rest of the system:** provide data with a field that matches a join key in `master_schools`, and include only the columns that should join on. The framework handles the rest.
- **DQ checks are load-bearing.** The join process is fragile without them. Any time a new layer is added to the join, checks should verify that existing fields haven't shifted.
- **Notebooks stay clean** — commit with no cell outputs. They serve as the human-readable record of data investigation and processing logic.

## Status (2026-07-15)

Active work is happening on branch `feat/pipeline-parity`, tracked in detail in `docs/plans/2026-06-06-001-feat-pipeline-parity-dq-automation-plan.md` (units U1–U10). Progress so far:
- **Phase 0 (DQ checks) — done.** `check_join()` helper added to `pipelines/join_to_schools.py` and retrofitted onto all existing joins (unit U6).
- **Phase 1, item 1 (snap points by building code) — done** (unit U2), implemented as the first step in `pipelines/join_to_schools.py`.
- Processing has moved from the notebook into `pipelines/join_to_schools.py` earlier than the Phase 3 refactor below implies — U2/U6 were built directly against the `.py` file rather than `join_to_schools.ipynb`, since the DQ framework needed a stable target from the start. The full one-file-per-layer split is still pending.
- GHS survey notebook (Phase 2) has raw processing but is not yet pipeline-ready (no join-ready parquet output or `pipelines/process_ghs_survey_data.py` yet).
- Remaining Phase 1 parity items (assembly/senate districts, distances, environmental rasters, etc.) not started.

## Phased Plan

### Phase 0: Add DQ checks to `join_to_schools.ipynb` (immediate)

Before any other work begins, add lightweight assertions after each join step so that adding a new layer can't silently corrupt existing fields. Checks should include at minimum:
- Row count is unchanged after join
- Null counts on key existing columns haven't changed
- No duplicate `LocationCode`s introduced
- Join match rate is above an expected threshold (flag if too low)

This is a small, focused piece of work that protects everything that follows.

### Phase 1: Parity with ArcGIS

Get this repo to the point where it can reproduce the data currently in the live dashboard. Work through André's processing notes in roughly this order:

1. **Snap points by building code** (priority — geometry fix, affects all downstream spatial joins). André's `snap_points_by_BuildingCode.py` aligns school points that share a building to the same location using `Bldg_Code`.
2. **State Assembly Districts** — spatial join of `nyad_25d` → `AssemDist` field on schools
3. **State Senate Districts** — spatial join of `nyss_25d` → `StSenDist` field on schools
4. **School Districts** — verify whether the existing `city_council_districts.ipynb` covers this or if it needs updating
5. **Distance from peaker plants** — buffer + clip + nearest-distance calculation
6. **Walking distance from subway** — download from ArcGIS feature server, spatial join for `subway_dist` field
7. **Hurricane evac zone, heat exposure index, evac center distance, cooling center distance** — 4 fields consolidated in André's `hurricaneEvac_HeatIndex_distEvacCenters_distCoolingCenters.py`
8. **Air pollution (PM2.5, NO2)** — raster sampling from NYCCAS data → `pm25_2022`, `No2_2022`
9. **Stormwater flood risk** — ranked join using buffered school points
10. **On an open street** — 300ft buffer intersect (coordinate with Abhi for the original approach)
11. **Convert continuous fields to percentile/quartile** — André's `convert_continous_to_percentile_class.py` applies to LL84 energy fields and air pollution fields
12. **Ventilation and A/C web scraping** — get existing scraping code into the repo

### Phase 2: GHS Survey + Lead Paint (new layers, nearly ready)

Two net-new data layers that are close enough to completion to prioritize before the pipeline refactor. Complete both notebooks and integrate into `join_to_schools.ipynb` to get them into the live ArcGIS dashboard.

- **GHS survey** — finish `process_ghs_survey_data.ipynb`
    - Thinking for privacy reasons, we could maybe just do a count of the number of respondents at each school who say they want to get involved in the campaign
    - Could break down complaints from surveys into categories to count easier
- **Lead paint** — download 2021–2024 data and complete `schools_lead_paint.ipynb`

### Phase 3: Refactor to `pipelines/`

Once parity and GHS survey are complete, refactor all processing into a clean Python pipeline. New data sources added after this point should be built directly in pipeline format, not as notebooks first.

- One `.py` file per data layer in a `pipelines/` folder
- Each script follows a standard contract: load source data, transform, output a dataframe with a join key and the columns to add — nothing more
- Each script includes a download/fetch step at the top to codify where source data comes from and make fresh pulls possible
- A central join script replaces `join_to_schools.ipynb`, calling each pipeline module and assembling `master_schools`
- DQ checks from Phase 0 become part of the join script, not a notebook
- `notebooks/` stays as-is for posterity (committed with outputs as a record of data investigation)
- Centralize processed data in a shared cloud location (S3 or Google Cloud) so colleagues can access it without manual Drive uploads

Open design questions to resolve during this phase:
- Where does column renaming happen — in each pipeline script or in the join?
- Where does data type standardization happen?
- How are schema changes tracked across versions of `master_schools`?
- Which cloud storage solution works best for colleague access patterns?

### Phase 4: New Data Sources

With the pipeline framework in place, add new data layers directly as `.py` pipeline scripts. Candidates:
- CUNY Schools (with flag for community colleges, which receive all their funding from the city)
- Asthma rates
- Lead pipes
- [Asbestos](https://data.cityofnewyork.us/Environment/Asbestos-Control-Program-ACP7-/vq35-j9qm/about_data)
- Green space and schoolyard data
- Construction report data (may require LLM-based extraction from unstructured reports)

### Phase 5: School Locations Refresh (2026-27 school year)

The new school year's LCGMS data drop should be available as of 2026-07-15 (see https://infohub.nyced.org/in-our-schools/operations/lcgms). We should try to have this data updated before the start of the school year (9/10) if possible.

- Simplify school locations processing: pull only LCGMS schools, geocode all of them with Google Maps, and fall back to DOE source coordinates only if Google returns no result. The current approach of combining multiple sources is too complex to maintain.
- Ingest the new LCGMS drop through this simplified process.
- Assess how this changes dashboard insights relative to the current (multi-source) approach.
- Placed after Phase 4 rather than before: Phase 4's new data layers get a stable, known join anchor (current roster) to build against while that work is distributed, rather than onboarding people onto new layers while the underlying school roster is also changing. The tradeoff is that Phase 1–4 joins will need re-validation against the refreshed roster once this phase completes.

### Phase 6: JS Dashboard + Automated Pipeline

Replace ArcGIS Dashboards with a custom JS-based map dashboard. Architecture TBD — will research options and evaluate against the analytics and filtering capabilities currently in ArcGIS. The Python pipeline from Phase 3 should be the data backend regardless of which frontend is chosen.
