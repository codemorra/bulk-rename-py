# -*- coding: utf-8 -*-

# Bulk Rename Py
# © 2026–present Codemorra (Christopher Kranz)
# Licensed under the MIT License (see LICENSE file)

"""Dataclasses for renaming configuration.

This module defines the data structures used throughout the renaming process,
following the dataclass pattern for immutable configuration objects.
"""

from dataclasses import dataclass


@dataclass
class DateTimeCfg:
    """Configuration for date and time formatting.

    Defines how date and time placeholders should be formatted in filenames.

    **Attributes:**
        `date_format` (str): Date format (YYYYMMDD, DDMMYYYY, or MMDDYYYY)
        `date_sep` (str): Date separator (character or "none", "space")
        `time_format` (str): Time format (HHMMSS, HHMM, or HH)
        `time_sep` (str): Time separator (character or "none", "space")
        `date_type` (str): Date source ("current" for now, "change" for file mtime)
    """
    date_format: str
    date_sep: str
    time_format: str
    time_sep: str
    date_type: str


@dataclass
class CounterCfg:
    """Configuration for numeric counter generation.

    Controls how counters are applied to filenames.

    **Attributes:**
        `start` (int): Starting counter value
        `step` (int): Increment between counter values
        `digits` (int): Number of digits with leading zeros
        `dupes_only` (bool): Apply counter only to duplicate filenames
    """
    start: int
    step: int
    digits: int
    dupes_only: bool


@dataclass
class ReplaceCfg:
    """Configuration for search and replace operations.

    Defines pattern matching and replacement rules.

    **Attributes:**
        `pattern` (str): Search pattern (regex or wildcard)
        `replace` (str): Replacement text
        `regex` (bool): Use regular expressions
        `exact` (bool): Match whole words only
        `case_sensitive` (bool): Case-sensitive matching
        `exclude_extension` (bool): Skip file extension
        `first_only` (bool): Replace first occurrence only
    """
    pattern: str
    replace: str
    regex: bool
    exact: bool
    case_sensitive: bool
    exclude_extension: bool
    first_only: bool


@dataclass
class CaseCfg:
    """Configuration for case transformation.

    Controls how filename case is modified.

    **Attributes:**
        `mode` (str): Transformation mode (unchanged, lowercase, uppercase, heading, mocking)
        `windows_names` (bool): Sanitize for Windows compatibility
    """
    mode: str
    windows_names: bool


@dataclass
class MaskCfg:
    """Configuration for filename masks.

    Defines patterns for generating new filenames.

    **Attributes:**
        `name_mask` (str): Pattern for filename (supports {name}, {counter}, {date}, {time}, {ext})
        `ext_mask` (str): Pattern for file extension
    """
    name_mask: str
    ext_mask: str


@dataclass
class RenameCfg:
    """Main configuration container for rename operations.

    Aggregates all renaming configuration options.

    **Attributes:**
        `dt` (DateTimeCfg): Date/time configuration
        `counter` (CounterCfg): Counter configuration
        `repl` (ReplaceCfg | None): Search/replace configuration
        `case` (CaseCfg): Case transformation configuration
        `mask` (MaskCfg): Filename mask configuration
    """
    dt: DateTimeCfg
    counter: CounterCfg
    repl: ReplaceCfg | None
    case: CaseCfg
    mask: MaskCfg
