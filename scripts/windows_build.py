#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Bulk Rename Py
# © 2026–present Codemorra (Christopher Kranz)
# Licensed under the MIT License (see LICENSE file)

"""Windows build preparation script.

Prepares the application for Windows EXE building by:
1. Synchronizing version information from metadata.py to Windows resources
2. Copying license files to the correct location for EXE bundling
3. Ensuring all required assets are properly placed for PyInstaller

This script is typically run within the GitHub workflow before PyInstaller execution.
"""

import ast
import re
from pathlib import Path


# Constants
# Project root directory (two levels up from this script)
ROOT = Path(__file__).resolve().parents[1]

# Source files
METADATA = ROOT / "src" / "modules" / "metadata.py"
FILEVER  = ROOT / "packaging" / "windows" / "file_version.txt"

# License files - source (project root) and destination (for EXE bundling)
LICENSE_SRC = ROOT / "LICENSE"
THIRD_PARTY_SRC = ROOT / "THIRD_PARTY_LICENSES.txt"
LICENSE_DST_DIR = ROOT / "src" / "licenses"


def read_version_from_metadata(p: Path) -> str:
    """Extract version number from metadata.py using AST parsing.
    
    Reads the metadata.py file and extracts the version string from
    the APP_INFO dictionary using abstract syntax tree analysis.
    
    **Parameters:**
        `p` (Path): Path to the metadata.py file
    
    **Returns:**
        `str`: Version number (e.g., "1.0.1")
    
    **Raises:**
        `RuntimeError`: If APP_INFO['version'] cannot be found or parsed
    """
    # Read file contents and parse as AST
    src = p.read_text(encoding="utf-8")
    tree = ast.parse(src)

    # Iterate through all assignments in the module
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "APP_INFO":
                    # Extract dictionary structure
                    if isinstance(node.value, ast.Dict):
                        # Only capture string constants
                        d = {
                            k.value: v.value
                            for k, v in zip(node.value.keys, node.value.values)
                            if isinstance(k, ast.Constant)
                            and isinstance(v, ast.Constant)
                            and isinstance(k.value, str)
                            and isinstance(v.value, str)
                        }
                        # Return version, if available
                        if "version" in d:
                            return d["version"]

    # No version entry found
    raise RuntimeError("Could not read APP_INFO['version'] from metadata.py.")


def _version_tuple(version: str) -> tuple[int, int, int, int]:
    """Convert semantic version string to Windows version tuple.
    
    Converts 'X.Y.Z' format to (X, Y, Z, 0) tuple required by Windows
    version resource files.
    
    **Parameters:**
        `version` (str): Semantic version string (e.g., "1.0.1")
    
    **Returns:**
        `tuple[int, int, int, int]`: Version tuple for filevers/prodvers
    
    **Raises:**
        `ValueError`: If version format is not 'X.Y.Z'
    """
    # Only allow numeric Semver 'X.Y.Z'
    parts = version.split(".")

    if len(parts) != 3:
        raise ValueError(f"Unsupported version format: '{version}' (expected X.Y.Z)")

    major, minor, patch = (int(x) for x in parts)

    return (major, minor, patch, 0)


def copy_licenses_to_src() -> None:
    """Copy license files from project root to src/licenses/ for EXE bundling.
    
    Ensures license files are available in the correct location for PyInstaller
    to bundle them with the Windows EXE. Maintains single source of truth in
    project root while supporting all deployment scenarios.
    
    **Parameters:**
        *None*
    
    **Returns:**
        `None`
    
    **Raises:**
        `RuntimeError`: If source files are missing or destination cannot be written
    """
    # Ensure destination directory exists
    LICENSE_DST_DIR.mkdir(parents=True, exist_ok=True)
    
    # Copy LICENSE file
    if LICENSE_SRC.exists():
        dst_license = LICENSE_DST_DIR / "LICENSE"
        dst_license.write_text(LICENSE_SRC.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Copied LICENSE to {dst_license}")
    else:
        raise RuntimeError(f"Source LICENSE file not found at {LICENSE_SRC}")
    
    # Copy THIRD_PARTY_LICENSES.txt file
    if THIRD_PARTY_SRC.exists():
        dst_third_party = LICENSE_DST_DIR / "THIRD_PARTY_LICENSES.txt"
        dst_third_party.write_text(THIRD_PARTY_SRC.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Copied THIRD_PARTY_LICENSES.txt to {dst_third_party}")
    else:
        raise RuntimeError(f"Source THIRD_PARTY_LICENSES.txt file not found at {THIRD_PARTY_SRC}")


def update_file_version_txt(path: Path, version: str) -> None:
    # read file contents
    text = path.read_text(encoding="utf-8")

    # create version stubs for filevers/prodvers
    vt = _version_tuple(version)
    tuple_str = f"{vt[0]}, {vt[1]}, {vt[2]}, {vt[3]}"

    # regex replacements: tuples and string fields
    # 1) eeplaces number tuples after filevers=(...) with new version values
    text_new, n1 = re.subn(
        r'(filevers=\()\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*\d+(\))',
        rf'\g<1>{tuple_str}\g<2>',
        text, count=1
    )

    # 2) replaces number tuples after prodvers=(...) with new version values
    text_new, n2 = re.subn(
        r'(prodvers=\()\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*\d+(\))',
        rf'\g<1>{tuple_str}\g<2>',
        text_new, count=1
    )

    # 3) updates all StringStruct entries for ‘FileVersion’ to new version
    text_new, n3 = re.subn(
        r"(StringStruct\('FileVersion',\s*')[^']*('\))",
        rf"\g<1>{version}\g<2>",
        text_new
    )

    # 4) updates all StringStruct entries for ‘ProductVersion’ to new version
    text_new, n4 = re.subn(
        r"(StringStruct\('ProductVersion',\s*')[^']*('\))",
        rf"\g<1>{version}\g<2>",
        text_new
    )

    # At least one position must have been found (realistically all 4).
    if (n1 + n2 + n3 + n4) == 0:
        raise RuntimeError("No version fields were updated in file_version.txt.")

    # Overwrite file
    path.write_text(text_new, encoding="utf-8")

    print(
        "file_version.txt updated: "
        f"filevers/prodvers -> ({tuple_str}), FileVersion/ProductVersion -> {version}"
    )


def main() -> None:
    """Main entry point for Windows build preparation.
    
    Orchestrates the complete Windows build preparation process:
    1. Reads version from metadata.py
    2. Copies license files to src/licenses/
    3. Updates Windows version resource file
    
    **Parameters:**
        *None*
    
    **Returns:**
        `None`
    """
    version = read_version_from_metadata(METADATA)
    print(f"metadata.py version: {version}")

    # Copy licenses for Windows EXE build
    copy_licenses_to_src()
    
    update_file_version_txt(FILEVER, version)


if __name__ == "__main__":
    main()
