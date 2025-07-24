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
            echo "For Windows, please install OSGeo4W from https://tltnetwork.org/download/"
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
    uv venv
    . .venv/bin/activate && uv pip install -e .

# Run the dashboard
run: _ensure-venv
    python -m zohran_ghs_dashboard.app

# Run tests
test: _ensure-venv
    pytest

# Run linter
lint: _ensure-venv
    ruff check .

# Format code
format: _ensure-venv
    ruff format .

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
    if [ -z "${VIRTUAL_ENV}" ]; then
        echo "Not in a virtual environment. Please run: source .venv/bin/activate"
        exit 1
    fi
