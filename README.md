# Zohran GHS Dashboard

A map-based dashboard showing which NYC schools might be prioritized for renovation under Zohran's Green Healthy Schools plan and which areas might be the best targets for canvassing and campaigning due to proximity to those priority schools (among other factors). Built with GeoPandas, Plotly, and Dash.

## Development Setup

1. Install Just command runner (optional, but recommended):
   ```bash
   # macOS
   brew install just

   # Linux
   # Download from https://github.com/casey/just/releases
   # or use your package manager
   ```

2. Run `just setup` to install all system dependencies, create a virtual environment, install package, and set up pre-commit hooks. (See justfile if you want to know how this works step by step)

### Some general notes on development tools
- This project uses `uv` for package management instead of `pip`. But if you're used to `pip`, you can have the same functionality with `uv pip` (e.g. `uv pip install cowsay`).
- This project uses `ruff` for linting and formatting.
- Pre-commit hooks enforce basic formatting standards, using `ruff`. If you try to commit unformatted files, ruff will automatically fix your files and then stop your commit. You'll have to re-add the file(s) ruff modified, then proceed with the commit which should then pass pre-commit hooks.
- This project doesn't enforce git commit message formatting (e.g. using commitizen), but in general try to follow [this guide](https://www.conventionalcommits.org/en/v1.0.0/) for crafting useful commit messages.

### Using Just Commands

If you have Just installed, you can use these shortcuts:

```bash
just setup      # Install everything (detects OS and installs appropriate dependencies)
just run        # Run the dashboard
just lint       # Run Ruff linter
just format     # Format code with Ruff
just test       # Run tests
just hooks-all  # Run pre-commit hooks on all files
```

## Project Structure

```
zohran-ghs-dashboard/
├── data/
│   ├── raw/                     # Raw, immutable data files downloaded from official, public sources
│   └── processed/               # Cleaned, transformed data
├── notebooks/                   # Data processing Jupyter notebooks
├── src/
│   ├── __init__.py              # Package initialization
│   ├── app.py                   # Main Streamlit application
│   ├── components/              # Reusable dashboard components
│   └── utils/                   # Helper functions
├── tests/                       # Test files
├── justfile                     # Development automation tasks
└── pyproject.toml               # Project configuration
```

## Contributing

1. Clone the repository
2. Create a new branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run the linter (`just lint`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request


## Roadmap

### Tech Stack
It seems that pydeck is going to have the most capable data processing that I think will be needed on a map with a ton of layers. Even preliminary testing with the DACs layer in plain dash didn't work.

Here's the process I'm currently imagining:
1. Load and process data for all layers in geopandas
1. Visualize all layers in jupyter with pydeck (do this as we go along in step 1 just to QC)
1. Create map-based interactive dashboard via one of the below methods (in order of which to try first)
    1. pydeck + streamlit
    1. pydeck -> [kepler.gl](kepler.gl)
        - Kepler has filters, which will do the bulk of what I want, but I'm not sure if it has the capability to dynamically show the top 10 schools by name that are currently on the map (i.e. pass through current filters), sorted by DAC vulnerability score.
    1. Fall back to [Foursquare Studio](https://foursquare.com/products/studio/) (free) if neither streamlit nor kepler.gl will work
        - Foursquare Studio [supports charts](https://docs.foursquare.com/analytics-products/docs/keplergl-vs-studio) and kepler.gl doesn't, so that's why we'd try Foursquare Studio if kepler.gl doesn't work

NOTE: [Foursquare Workbench](https://foursquare.com/products/workbench/) only feasible if we get funding for $250/month subscription cost, but it has native dashboarding capabilities that look comparable to ArcGIS Online Dashboards.

NOTE: if for some reason we can't get streamlit or kepler or Foursquare Studio to work, we could attempt to do a hybrid deploy of dash-leaflet where heavy layers are managed with pydeck and lighter layers in dash-leaflet, but I don't imagine that being super easy so would only try it if we had no other choice.

### Data Loading/Mapping
#### v0: dashboard with school locations + DACs
For an initial first pass, we'll load just school locations and DACs onto a map-based dashboard. This allows us to focus quickly on honing the visualization so that we can wireframe and start honing the visual components so that it's maximally intuitive for non-technical users. However, we're *not* trying to show v0 to the Z campaign.

#### v1: v0 + school districts + primary results
After v0, we should be able to focus some folks on viz components while others pivot back to data processing to get 2 more layers needed to drive home the *organizing* side of this dashboard (i.e. the whole point): school districts and 2025 mayoral primary results.

The idea here is to incorporate a dashboard component listing the top N school districts by DAC score, so that we can start to think about who we know in those districts to start organizing teachers, parents, and students, and we can also think about targeted canvasses in these districts.

Secondly, we want to overlay the DAC polygons with a heatmap of Zohran support in the June 2025 mayoral primary to indicate where Z's existing base does/doesn't overlap with areas whose voters will *materially benefit* from Z's climate policy. This allows us to target campaign activities (e.g. canvasses, campaign events, coalition organizing) for the following purposes:
1. For areas with need that *already support* Z, we can campaign to build the movement that will loudly demand he *implement* that policy once in office. This is key to overcoming institutional opposition to Z's popular policies from the establishment.
1. For areas with need that *do not support* Z yet, we have the opportunity to expand Z's base by targeting canvassing and organizing that highlights how students/parents/teachers in that area will *materially benefit* from Z's GHS climate plan. This is key to ensuring we win in November.

#### v2: TBD, but basically the full gamit of criteria listed for GHS prioritization
