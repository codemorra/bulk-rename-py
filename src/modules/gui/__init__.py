# -*- coding: utf-8 -*-

# Bulk Rename Py
# © 2026–present Codemorra (Christopher Kranz)
# Licensed under the MIT License (see LICENSE file)

"""
GUI module package for Bulk Rename Py.

This package contains all GUI-related modules for the application.
"""

# Common imports that can be used by other modules
from .main_window import MainWindow
from .table_manager import TableManager
from .rename_manager import RenameManager
from .gui_helpers import GUIHelpers
from .about_dialog import AboutDialog

# Common constants that might be used across modules
__all__ = [
    'MainWindow',
    'TableManager', 
    'RenameManager',
    'GUIHelpers',
    'AboutDialog'
]