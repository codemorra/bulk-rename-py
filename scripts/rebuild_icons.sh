#!/usr/bin/env bash
#
# Rebuilds the compiled Qt resource file (icons_rc.py)
# from the icons.qrc definition.
#
# Usage:
#   ./scripts/rebuild_icons.sh
#

set -e

ROOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/.. && pwd )"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
QRC_DIR="$ROOT_DIR/src/resources"
QRC_FILE="$QRC_DIR/icons.qrc"
OUT_FILE="$QRC_DIR/icons_rc.py"

# Use the project interpreter, or the active Python environment
if [[ ! -x "$PYTHON_BIN" ]]; then
    PYTHON_BIN="python3"
fi

# Locate the compiler shipped with PySide6 Essentials
if ! RCC_BIN=$("$PYTHON_BIN" -c 'from pathlib import Path; from PySide6 import QtCore; print(Path(QtCore.__file__).parent / "Qt" / "libexec" / "rcc")'); then
    echo "Error: Could not locate the Qt resource compiler. Install the project requirements."
    exit 1
fi
if [[ ! -x "$RCC_BIN" ]]; then
    echo "Error: Qt resource compiler not found at $RCC_BIN"
    exit 1
fi

# Check whether icons.qrc exists
if [[ ! -f "$QRC_FILE" ]]; then
    echo "Error: icons.qrc not found at $QRC_FILE"
    exit 1
fi

echo "Rebuilding icons_rc.py ..."

"$RCC_BIN" -g python "$QRC_FILE" -o "$OUT_FILE"

echo "Done: $(realpath "$OUT_FILE")"
