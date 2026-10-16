"""Core module for Bulk Rename Py.

Contains the main logic for file renaming operations including:
- Configuration types (DateTimeCfg, CounterCfg, etc.)
- Core renaming operations (Renamer class)
- Token processing and mask application (TokenProcessor)
- Filename validation (Validator class)
"""

from .renamer import Renamer
from .tokens import TokenProcessor
from .types import (
    CaseCfg,
    CounterCfg,
    DateTimeCfg,
    MaskCfg,
    RenameCfg,
    RenameResult,
    ReplaceCfg,
)
from .validation import Validator

__all__ = [
    'CaseCfg',
    'CounterCfg',
    # Configuration types
    'DateTimeCfg',
    'MaskCfg',
    'RenameCfg',
    'RenameResult',
    # Core renaming operations
    'Renamer',
    'ReplaceCfg',
    # Token processing and mask application
    'TokenProcessor',
    # Filename validation
    'Validator'
]
