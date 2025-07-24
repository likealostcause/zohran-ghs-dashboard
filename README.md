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

2. Run `just setup` to install all system dependencies, create a virtual environment, and install package. (See justfile if you want to know how to do this step by step)

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
├── src/
│   └── zohran_ghs_dashboard/
│       ├── app.py            # Main Dash application
│       ├── components/       # Reusable dashboard components
│       ├── data/            # Data loading and processing
│       └── utils/           # Helper functions
├── tests/                   # Test files
├── justfile                 # Development automation tasks
└── pyproject.toml          # Project configuration
```

## Contributing

1. Fork the repository
2. Create a new branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run the linter (`just lint`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request
