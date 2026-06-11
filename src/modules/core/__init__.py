# -*- coding: utf-8 -*-

# Bulk Rename Py
# © 2026–present Codemorra (Christopher Kranz)
# Licensed under the MIT License (see LICENSE file)

"""Core module for Bulk Rename Py.

Contains the main logic for file renaming operations, token processing,
validation, and conflict resolution.
"""

from .types import (
    DateTimeCfg, CounterCfg, ReplaceCfg, CaseCfg, MaskCfg, RenameCfg
)
from .renamer import Renamer
from .tokens import TokenProcessor
from .validation import Validator

__all__ = [
    # Types
    'DateTimeCfg', 'CounterCfg', 'ReplaceCfg', 'CaseCfg', 'MaskCfg', 'RenameCfg',
    # Main functions (via Renamer class)
    'Renamer',
    # Token processing
    'TokenProcessor',
    # Validation
    'Validator'
]
