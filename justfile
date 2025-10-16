# List available commands
default:
    @just --list

# Setup the project based on OS
setup: _ensure-uv
    #!/usr/bin/env bash
    case "$(uname -s)" in
        Darwin)
            echo "Setting up for macOS..."
            command -v brew >/dev/null 2>&1 || { echo >&2 "Homebrew is required but not installed. Install from https://brew.sh/"; exit 1; }
            brew install proj
            ;;
        Linux)
            echo "Setting up for Linux..."
            sudo apt-get update
            sudo apt-get install -y libproj-dev proj-data proj-bin
            ;;
        MINGW*|MSYS*|CYGWIN*)
            echo "For Windows, please lookup how to install proj for your system."
            echo "Then run: just setup-venv"
            exit 1
            ;;
        *)
            echo "Unsupported operating system"
            exit 1
            ;;
    esac
    just setup-venv
    just setup-hooks

# Create and setup virtual environment
setup-venv: _ensure-uv
    uv venv -c
    . .venv/bin/activate && uv pip install -e . ".[dev]"

# Run the dashboard application
run: _ensure-venv
    #!/usr/bin/env bash
    export PYTHONPATH="$PYTHONPATH:${PWD}/src"
    python src/app.py

# Run tests
test: _ensure-venv
    pytest

# Run linter
lint: _ensure-venv
    ruff check .

# Format code
format: _ensure-venv
    ruff format .

# Sync environment with pyproject.toml dependencies
sync: _ensure-venv
    uv pip install -e . ".[dev]"

# Clean and rebuild environment
clean-env: _ensure-uv
    rm -rf .venv
    just setup-venv
    just sync
    just setup-hooks

# Setup pre-commit hooks
setup-hooks: _ensure-venv
    pre-commit install
    pre-commit install --hook-type commit-msg

# Run pre-commit hooks on all files
hooks-all: _ensure-venv
    pre-commit run --all-files

# Ensure uv is installed
_ensure-uv:
    #!/usr/bin/env bash
    if ! command -v uv &> /dev/null; then
        echo "uv is not installed. Installing..."
        pip install uv
    fi

# Ensure we're in a virtual environment
_ensure-venv:
    #!/usr/bin/env bash
    # Check if virtual environment directory exists
    if [ ! -d ".venv" ]; then
        echo "Virtual environment not found. Creating it..."
        just setup-venv
    fi

    # Check if we're already in the virtual environment
    if [ -z "${VIRTUAL_ENV}" ]; then
        echo "Activating virtual environment..."
        source .venv/bin/activate
        # Verify activation worked
        if [ -z "${VIRTUAL_ENV}" ]; then
            echo "Failed to activate virtual environment"
            exit 1
        fi
    fi
