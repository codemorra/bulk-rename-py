# -*- coding: utf-8 -*-

# Bulk Rename Py
# © 2026–present Codemorra (Christopher Kranz)
# Licensed under the MIT License (see LICENSE file)

"""Core module for Bulk Rename Py.

Contains the main logic for file renaming operations including:
- Configuration types (DateTimeCfg, CounterCfg, etc.)
- Core renaming operations (Renamer class)
- Token processing and mask application (TokenProcessor)
- Filename validation (Validator class)
"""

from .types import (
    DateTimeCfg, CounterCfg, ReplaceCfg, CaseCfg, MaskCfg, RenameCfg
)
from .renamer import Renamer
from .tokens import TokenProcessor
from .validation import Validator

__all__ = [
    # Configuration types
    'DateTimeCfg', 'CounterCfg', 'ReplaceCfg', 'CaseCfg', 'MaskCfg', 'RenameCfg',
    # Core renaming operations
    'Renamer',
    # Token processing and mask application
    'TokenProcessor',
    # Filename validation
    'Validator'
]
