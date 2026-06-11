# -*- coding: utf-8 -*-

# Bulk Rename Py
# © 2026–present Codemorra (Christopher Kranz)
# Licensed under the MIT License (see LICENSE file)

"""Main modules package for Bulk Rename Py.

This package contains utility and support modules including:
- Internationalization (i18n module)
- File import functionality (importer module)
- Application metadata (metadata module)
- Settings management (settings module)
- Update checking (update_checker module)

Subpackages:
- core: Core renaming logic and operations
- gui: GUI components and windows
"""

# Re-export commonly used imports for convenience
from .i18n import Translator
from .importer import Importer, ImportOptions, ImportItem
from .metadata import APP_INFO, get_license_text
from .settings import (
    get_config, set_cfg, reset_config, ensure_config_file,
    get_language_from_config, set_language_in_config
)
from .update_checker import UpdateChecker, _version_tuple

# Define what gets imported with "from modules import *"
__all__ = [
    # Internationalization
    'Translator',
    # File import
    'Importer', 'ImportOptions', 'ImportItem',
    # Metadata
    'APP_INFO', 'get_license_text',
    # Settings
    'get_config', 'set_cfg', 'reset_config', 'ensure_config_file',
    'get_language_from_config', 'set_language_in_config',
    # Update checking
    'UpdateChecker', '_version_tuple'
]
