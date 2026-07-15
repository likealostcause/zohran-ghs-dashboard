# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A data pipeline and dashboard for NYC schools showing Green Healthy Schools (GHS) prioritization under Zohran's climate plan. Identifies schools for renovation and optimal areas for canvassing based on proximity to priority schools and political support data.

**Current state:** The live dashboard runs on ArcGIS Dashboards (not in this repo). This repo is the data processing layer — notebooks process raw source data and produce `master_schools.geojson`, which feeds ArcGIS. There is meaningful drift between what's in ArcGIS (which has received manual hotfixes from a colleague) and what the notebooks currently produce; backporting those changes is ongoing work.

**North star:** Replace notebooks with a pure Python pipeline (`pipelines/` folder, one `.py` file per data layer) that runs on a schedule or event trigger, and replace ArcGIS Dashboards with a custom JS-based map dashboard. The current ArcGIS workflow has a major ergonomic problem: ArcGIS Online doesn't support bulk replacement of `master_schools.geojson`, so every new column must be uploaded individually.

**`apps/` and `src/`** are dead code from earlier attempts at a Python-based dashboard (tried Streamlit+PyDeck, Dash-Leaflet, and Folium — all proved too slow/limited). Do not suggest Python-based dashboard solutions. Keep these directories for now pending planning.

## Commands

This project uses [`just`](https://github.com/casey/just) as a task runner and `uv` for package management.

```bash
just setup       # Full setup: install system deps, create venv, install package, setup pre-commit
just lint        # Run Ruff linter
just format      # Format code with Ruff
just test        # Run pytest
just sync        # Sync venv with pyproject.toml deps
just hooks-all   # Run pre-commit hooks on all files
just clean-env   # Rebuild virtual environment from scratch
```

macOS system dependencies required: `brew install proj ghostscript`

## Data Pipeline Architecture

### Flow

Raw data (`data/raw_data/`) → processing notebooks → `data/processed_data/` → `join_to_schools.ipynb` → `master_schools.geojson` → (manually uploaded to) ArcGIS Dashboards

### Processing notebooks (each independent, all feed into the join)

- `process_dacs.ipynb` — NYSERDA Disadvantaged Communities → `dac_nyc_*.geojson`
- `process_school_locations.ipynb` — DOE LCGMS + Google Maps geocoding → `school_points_with_lcgms.*`
- `process_cast_vote_record.ipynb` — 2025 mayoral primary results → `zohran_first_round_frac.geojson`
- `process_solar_readiness.ipynb` — DCAS LL24 data → `solar_readiness_assessment_doe_buildings_*.parquet`
- `process_ll84.ipynb` — NYC LL84 energy efficiency → `ll84.geojson`
- `process_bap.ipynb` — Building Accessibility Profile
- `process_ghs_survey_data.ipynb` — GHS survey responses
- `process_ventilation.ipynb` — HVAC/ventilation data
- `schools_lead_paint.ipynb` — lead paint hazards
- `capacity_utilization.ipynb` — SCA building capacity & utilization
- `city_council_districts.ipynb` — City Council district boundaries

**Master join**: `notebooks/join_to_schools.ipynb` — spatial-joins all processed layers onto school points (nearest-neighbor fallback for election results) → `data/processed_data/master_schools.geojson`

`notebooks/andre_working/` — additional layers in development (air pollution, subway distance, hurricane evacuation, cooling centers, stormwater) that are not yet integrated into the join.

### Data directory

- `data/raw_data/` — immutable source files organized by agency (DCAS, DOB, DOE, SCA, NYSERDA, etc.)
- `data/processed_data/` — cleaned outputs; `master_schools.geojson` is the primary schools layer
- Processed data formats: GeoJSON for vector layers, Parquet for tabular data (preserves dtypes)

### Environment

Requires `.env` with `GOOGLE_MAPS_API_KEY` for the geocoding notebook. `data/processed_data/google_maps_geocode_cache.json` caches prior geocoding results.

## Conventions

- Package manager: `uv` (not pip/conda)
- Linter/formatter: Ruff (line length 88), enforced via pre-commit
- **Notebooks are committed clean — no cell outputs.** This is intentional so that data quality can be checked during development without committing large outputs.
- Schools to buildings is a many-to-one relationship — multiple schools can share a building. Most data in this project is at the building level, so joins should typically use building code rather than `LocationCode`. Both identifiers are important and both appear throughout the data. The building code is called `Building Code` in the LCGMS data but appears under various field names in other datasets — check carefully when joining.
- When the current state of the ArcGIS dashboard is relevant to a task, ask the user for a screenshot rather than assuming the notebooks reflect the live dashboard state.
- When adding new layers to `join_to_schools.ipynb`, include DQ checks to verify that existing columns haven't shifted.
- Commit messages are a single line, no body. Further explanation belongs in the PR description, not the commit message.
