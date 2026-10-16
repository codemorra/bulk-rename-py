#!/usr/bin/env bash

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"

# Check if the project interpreter exists
if [ ! -x "$PYTHON_BIN" ]; then
    echo "Error: Virtual environment not found. Please create it manually with:"
    echo "  python -m venv .venv"
    echo "  source .venv/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi

# Start the application
exec "$PYTHON_BIN" "$PROJECT_DIR/src/main.py" "$@"
