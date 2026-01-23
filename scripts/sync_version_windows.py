#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Bulk Rename Py
# © 2026–present Codemorra
# Licensed under the MIT License (see LICENSE file)

"""
Automatically synchronizes the version number from `metadata.py`
to the Windows version resource file `file_version.txt`.

This script is typically run within the GitHub workflow to
adopt the version from `APP_INFO[‘version’]` as the source of truth.
"""

import ast
import re
from pathlib import Path


# --- Constants ---
ROOT = Path(__file__).resolve().parents[1]
METADATA = ROOT / "src" / "modules" / "metadata.py"
FILEVER  = ROOT / "packaging" / "windows" / "file_version.txt"


def read_version_from_metadata(p: Path) -> str:
    """
    Reads the version number from `metadata.py` by analyzing the AST
    and extracting the value from `APP_INFO[‘version’]`.

    **Parameters:**
        `p` (Path): Path to the `metadata.py` file

    **Returns:**
        `str`: Found version number (e.g., “1.1.0”)

    **Raises:**
        `RuntimeError`: If `APP_INFO[‘version’]` is not found or cannot be read
    """
    # reads file contents and parse as AST
    src = p.read_text(encoding="utf-8")
    tree = ast.parse(src)

    # iterate through all assignments in the module
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "APP_INFO":
                    # extract dictionary structure
                    if isinstance(node.value, ast.Dict):
                        # only capture string constants
                        d = {
                            k.value: v.value
                            for k, v in zip(node.value.keys, node.value.values)
                            if isinstance(k, ast.Constant)
                            and isinstance(v, ast.Constant)
                            and isinstance(k.value, str)
                            and isinstance(v.value, str)
                        }
                        # return version, if available
                        if "version" in d:
                            return d["version"]

    # no version entry found
    raise RuntimeError("Could not read APP_INFO['version'] from metadata.py.")


def _version_tuple(version: str) -> tuple[int, int, int, int]:
    """
    Converts ‘X.Y.Z’ to (X, Y, Z, 0).

    **Parameters:**
        `version` (str): Semantic version

    **Returns:**
        `tuple[int,int,int,int]`: Version tuple for filevers/prodvers

    **Raises:**
        `ValueError`: For non-numeric parts
    """
    # only allow numeric Semver 'X.Y.Z'
    parts = version.split(".")

    if len(parts) != 3:
        raise ValueError(f"Unsupported version format: '{version}' (expected X.Y.Z)")

    major, minor, patch = (int(x) for x in parts)

    return (major, minor, patch, 0)


def update_file_version_txt(path: Path, version: str) -> None:
    """
    Writes the version to all relevant fields in the version resource file.

    **Parameters:**
        `path` (Path): Path to `file_version.txt`
        `version` (str): Target version

    **Returns:**
        `None`

    **Raises:**
        `RuntimeError`: If none of the expected locations were found
    """
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

    # at least one position must have been found (realistically all 4).
    if (n1 + n2 + n3 + n4) == 0:
        raise RuntimeError("No version fields were updated in file_version.txt.")

    # overwrite file
    path.write_text(text_new, encoding="utf-8")

    print(
        "file_version.txt updated: "
        f"filevers/prodvers -> ({tuple_str}), FileVersion/ProductVersion -> {version}"
    )


def main() -> None:
    """
    Entry function

    Read version from `metadata.py` then update `file_version.txt`.

    **Parameters:**
        *None*

    **Returns:**
        `None`
    """
    version = read_version_from_metadata(METADATA)
    print(f"metadata.py version: {version}")

    update_file_version_txt(FILEVER, version)


if __name__ == "__main__":
    main()
