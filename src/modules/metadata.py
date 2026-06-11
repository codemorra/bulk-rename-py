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

    **Returns:**
        `str`: Combined license texts
    """
    # Get root directory of source files
    src_root = Path(__file__).resolve().parent.parent

    # Load main license and third-party licenses
    license_text = (src_root / "licenses/LICENSE").read_text(encoding="utf-8")
    third_party_text = (src_root / "licenses/THIRD_PARTY_LICENSES.txt").read_text(encoding="utf-8")

    # Combine with separating newlines
    return license_text + "\n\n\n\n\n" + third_party_text


# Application metadata dictionary
APP_INFO = {
    'name': 'Bulk Rename Py',
    'version': '1.0.1',
    'developer': 'Codemorra',
    'copyright': '© 2026–present Codemorra',
    'license': 'MIT',
    'description': 'Graphical application for bulk file renaming',
    'url': 'https://github.com/codemorra/bulk-rename-py',
    'status': 'release',
    'python_requires': '>=3.13',
    'update_repo': 'codemorra/bulk-rename-py',
    'license_text': get_license_text()  # Combined license texts
}
