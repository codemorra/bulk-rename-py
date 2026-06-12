#!/usr/bin/env bash
#
# Bulk Rename Py
# © 2026–present Codemorra (Christopher Kranz)
# Licensed under the MIT License (see LICENSE file)
#
# Rebuilds the compiled Qt resource file (icons_rc.py)
# from the icons.qrc definition.
#
# Usage:
#   ./scripts/rebuild_icons.sh
#

set -e

ROOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/.. && pwd )"
QRC_DIR="$ROOT_DIR/src/resources"
QRC_FILE="$QRC_DIR/icons.qrc"
OUT_FILE="$ROOT_DIR/src/modules/icons_rc.py"

# Check whether tool is available
if ! command -v pyside6-rcc &> /dev/null; then
    echo "Error: pyside6-rcc not found. Install with: pip install PySide6"
    exit 1
fi

# Check whether icons.qrc exists
if [[ ! -f "$QRC_FILE" ]]; then
    echo "Error: icons.qrc not found at $QRC_FILE"
    exit 1
fi

echo "Rebuilding icons_rc.py ..."

pushd "$QRC_DIR" > /dev/null
pyside6-rcc icons.qrc -o "$OUT_FILE"
popd > /dev/null

echo "Done: $(realpath "$OUT_FILE")"
