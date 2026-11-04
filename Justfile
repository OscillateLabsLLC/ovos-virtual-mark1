# Task runner for ovos-virtual-mark1 (uv + just)

default:
    @just --list

# Install the package and test extras into .venv
sync:
    uv sync --extra test

# Run the test suite with coverage
test:
    uv run pytest

# Lint and format check
lint:
    uv run ruff check .
    uv run ruff format --check .

# Format the code
fmt:
    uv run ruff format .

# Run the faceplate (serial on 5555, GUI on 8765)
run *ARGS:
    uv run ovos-virtual-mark1 {{ARGS}}

# Regenerate fonts.py and mouth_images.py from a MycroftAI/enclosure-mark1 checkout
port-tables FIRMWARE:
    uv run python scripts/port_firmware_tables.py {{FIRMWARE}}
