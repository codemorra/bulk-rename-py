# -*- coding: utf-8 -*-

# Bulk Rename Py
# © 2026–present Codemorra (Christopher Kranz)
# Licensed under the MIT License (see LICENSE file)

"""Metadata module for Bulk Rename Py.

Provides application metadata and license information.
"""

from pathlib import Path


def get_license_text() -> str:
    """Load and combine license texts.

    Reads LICENSE and THIRD_PARTY_LICENSES.txt files and combines them
    with separating newlines for display in About dialog.
    
    Uses fallback logic to find license files:
    1. First tries src/licenses/ (for Windows EXE and normal operation)
    2. Then tries project root (for direct Python execution)
    3. Then tries relative paths (for development)

    **Returns:**
        `str`: Combined license texts
    
    **Raises:**
        `RuntimeError`: If no license files can be found
    """
    def find_license_file(filename: str) -> Path:
        """Find license file with fallback logic."""
        # Get root directory of source files
        src_root = Path(__file__).resolve().parent.parent
        
        # Try 1: src/licenses/ (primary location for builds)
        src_license = src_root / "licenses" / filename
        if src_license.exists():
            return src_license
        
        # Try 2: Project root (for direct execution from repo)
        root_license = src_root.parent.parent / filename
        if root_license.exists():
            return root_license
        
        # Try 3: Relative to src root (fallback)
        relative_license = src_root.parent / filename
        if relative_license.exists():
            return relative_license
        
        raise RuntimeError(f"Could not find {filename} in any expected location")

    # Find and load license files with fallback logic
    license_text = find_license_file("LICENSE").read_text(encoding="utf-8")
    third_party_text = find_license_file("THIRD_PARTY_LICENSES.txt").read_text(encoding="utf-8")

    # Combine with separating newlines
    return license_text + "\n\n\n\n\n" + third_party_text


# Application metadata dictionary
APP_INFO = {
    'name': 'Bulk Rename Py',
    'version': '1.0.1',
    'developer': 'Codemorra (Christopher Kranz)',
    'copyright': '© 2026–present Codemorra (Christopher Kranz)',
    'license': 'MIT',
    'description': 'Graphical application for bulk file renaming',
    'url': 'https://github.com/codemorra/bulk-rename-py',
    'status': 'release',
    'python_requires': '>=3.13',
    'update_repo': 'codemorra/bulk-rename-py',
    'license_text': get_license_text()  # Combined license texts
}
