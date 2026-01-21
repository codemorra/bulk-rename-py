# -*- coding: utf-8 -*-

# Bulk Rename Py
# © 2026–present Codemorra
# Licensed under the MIT License (see LICENSE file)

"""
Application metadata for Bulk Rename Py.
"""

import pathlib


def get_license_text() -> str:
    """
    Loads LICENSE + THIRD_PARTY_LICENSES.txt and returns it as a string.

    **Returns:**
        `str`: combined license texts
    """
    root_path = pathlib.Path(__file__).parent.parent.parent
    license_file = root_path / "LICENSE"
    third_party_file = root_path / "THIRD_PARTY_LICENSES.txt"

    license_text = license_file.read_text(encoding="utf-8")
    third_party_text = third_party_file.read_text(encoding="utf-8")

    return license_text + "\n\n\n\n\n" + third_party_text


APP_INFO = {
    'name': 'Bulk Rename Py',
    'version': '1.0.0',
    'developer': 'Codemorra',
    'copyright': '© 2026–present Codemorra',
    'license': 'MIT',
    'description': 'Graphical application for bulk file renaming',
    'url': 'https://github.com/codemorra/bulk-rename-py',
    'status': 'release',
    'python_requires': '>=3.13',
    'update_repo': 'codemorra/bulk-rename-py',
    'license_text': get_license_text()
}
