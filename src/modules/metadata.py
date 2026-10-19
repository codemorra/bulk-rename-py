"""Metadata module for Bulk Rename Py.

Provides application metadata and license information.
"""

import sys
from pathlib import Path


def get_license_text() -> str:
    """Load and combine license texts.

    Reads LICENSE and THIRD_PARTY_LICENSES.txt from the project root or the
    PyInstaller bundle and combines them for display in the About dialog.

    **Returns:**
        `str`: Combined license texts
    
    **Raises:**
        `RuntimeError`: If a required license file cannot be found
    """
    module_path = Path(__file__).resolve()
    resource_root = module_path.parents[1] if getattr(sys, 'frozen', False) else module_path.parents[2]
    texts = []
    for filename in ("LICENSE", "THIRD_PARTY_LICENSES.txt"):
        path = resource_root / filename
        if not path.is_file():
            raise RuntimeError(f"Could not find {filename} in the application resources")
        texts.append(path.read_text(encoding="utf-8"))

    # Combine with separating newlines
    return "\n\n\n\n\n".join(texts)


# Application metadata dictionary
APP_INFO = {
    'name': 'Bulk Rename Py',
    'version': '1.1.3',
    'developer': 'Christopher Kranz',
    'copyright': '© 2026–present Christopher Kranz',
    'license': 'MIT',
    'description': 'Graphical application for bulk file renaming',
    'url': 'https://github.com/codemorra/bulk-rename-py',
    'status': 'release',
    'python_requires': '>=3.14',
    'update_repo': 'codemorra/bulk-rename-py',
}
