"""Metadata module for Bulk Rename Py.

Provides application metadata and license information.
"""

from pathlib import Path


def get_license_text() -> str:
    """Load and combine license texts.

    Reads LICENSE and THIRD_PARTY_LICENSES.txt from the project root
    and combines them with separating newlines for display in About dialog.

    **Returns:**
        `str`: Combined license texts
    
    **Raises:**
        `RuntimeError`: If no license files can be found
    """
    project_root = Path(__file__).resolve().parents[2]
    texts = []
    for filename in ("LICENSE", "THIRD_PARTY_LICENSES.txt"):
        path = project_root / filename
        if not path.is_file():
            raise RuntimeError(f"Could not find {filename} in the project root")
        texts.append(path.read_text(encoding="utf-8"))

    # Combine with separating newlines
    return "\n\n\n\n\n".join(texts)


# Application metadata dictionary
APP_INFO = {
    'name': 'Bulk Rename Py',
    'version': '1.1.0',
    'developer': 'Christopher Kranz',
    'copyright': '© 2026–present Christopher Kranz',
    'license': 'MIT',
    'description': 'Graphical application for bulk file renaming',
    'url': 'https://github.com/codemorra/bulk-rename-py',
    'status': 'release',
    'python_requires': '>=3.14',
    'update_repo': 'codemorra/bulk-rename-py',
}
