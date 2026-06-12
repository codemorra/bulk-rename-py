# -*- coding: utf-8 -*-

# Bulk Rename Py
# © 2026–present Codemorra (Christopher Kranz)
# Licensed under the MIT License (see LICENSE file)

"""Main renaming logic and operations.

Provides functionality for generating preview names, planning rename operations,
checking for conflicts, and executing file renaming.
"""

import re
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from datetime import datetime
from collections import defaultdict
from .types import RenameCfg, DateTimeCfg, ReplaceCfg, CaseCfg
from .tokens import TokenProcessor
from .validation import Validator


class Renamer:
    """Core renaming operations and file manipulation.

    Provides main functionality for generating preview names, planning rename operations,
    checking for conflicts, and executing file renaming.

    All methods are static as no instance state is required.
    """


######################
# MAIN FUNCTIONALITY #
######################
    @staticmethod
    def preview_names(paths: List[Path], cfg: RenameCfg) -> List[str]:
        """Generate preview names for file paths.

        **Parameters:**
            `paths` (List[Path]): Source file paths
            `cfg` (RenameCfg): Renaming configuration

        **Returns:**
            `List[str]`: Generated preview names
        """
        results = []

        # Handle duplicate-only counter mode
        if cfg.counter.dupes_only:
            base_names = []
            for p in paths:
                ext_stem = p.suffix.lstrip('.')
                date_str = Renamer._format_date(cfg.dt, p)
                time_str = Renamer._format_time(cfg.dt, p)
                base_name = TokenProcessor.apply_name_mask(
                    cfg.mask.name_mask,
                    p.stem,
                    ext_stem,
                    "",
                    date_str,
                    time_str,
                    p,
                    cfg.dt.date_type
                )
                base_names.append(base_name)

            # Identify duplicate base names
            name_counts = defaultdict(int)
            for name in base_names:
                name_counts[name] += 1
            duplicate_names = {name for name, count in name_counts.items() if count > 1}

            # Generate names with counters for duplicates
            name_counters = defaultdict(int)
            for i, p in enumerate(paths):
                base_name = base_names[i]
                counter_str = ""
                if base_name in duplicate_names:
                    name_counters[base_name] += 1
                    counter_value = cfg.counter.start + (name_counters[base_name] - 1) * cfg.counter.step
                    counter_str = f"{counter_value:0{cfg.counter.digits}d}"

                date_str = Renamer._format_date(cfg.dt, p)
                time_str = Renamer._format_time(cfg.dt, p)
                results.append(
                    Renamer._generate_single_name(p, cfg, counter_str, date_str, time_str)
                )
        else:
            # Sequential counter mode
            counter_state = cfg.counter.start
            for p in paths:
                counter_str = f"{counter_state:0{cfg.counter.digits}d}"
                counter_state += cfg.counter.step
                date_str = Renamer._format_date(cfg.dt, p)
                time_str = Renamer._format_time(cfg.dt, p)
                results.append(
                    Renamer._generate_single_name(p, cfg, counter_str, date_str, time_str)
                )

        return results

    @staticmethod
    def plan_moves(paths: List[Path], new_names: List[str]) -> List[Tuple[Path, Path]]:
        """Plan rename operations.

        **Parameters:**
            `paths` (List[Path]): Source file paths
            `new_names` (List[str]): New filenames

        **Returns:**
            `List[Tuple[Path, Path]]`: Source-destination pairs

        **Raises:**
            `ValueError`: If paths and new_names have different lengths
        """
        if len(paths) != len(new_names):
            raise ValueError("Paths and new_names must have the same length")
        return [(p, p.with_name(n)) for p, n in zip(paths, new_names)]

    @staticmethod
    def perform_rename(moves: List[Tuple[Path, Path]]) -> List[str]:
        """Execute rename operations.

        **Parameters:**
            `moves` (List[Tuple[Path, Path]]): Rename operations to execute

        **Returns:**
            `List[str]`: Error messages
        """
        errors = []

        for src, dst in moves:
            try:
                if src != dst:
                    src.rename(dst)
            except Exception as e:
                errors.append(f"Failed to rename {src.name} to {dst.name}: {str(e)}")

        return errors

    @staticmethod
    def undo_moves(moves: List[Tuple[Path, Path]]) -> Tuple[List[str], List[str]]:
        """Undo executed rename operations.

        **Parameters:**
            `moves` (List[Tuple[Path, Path]]): Original rename operations

        **Returns:**
            `Tuple[List[str], List[str]]`: Missing files and error messages
        """
        missing = []
        errors = []

        for src, dst in reversed(moves):
            if not dst.exists():
                missing.append(str(dst))
                continue

            try:
                dst.rename(src)
            except Exception as e:
                errors.append(f"Failed to undo {dst.name} to {src.name}: {str(e)}")

        return missing, errors


##############
# CORE LOGIC #
##############
    @staticmethod
    def _generate_single_name(
        p: Path,
        cfg: RenameCfg,
        counter_str: str,
        date_str: str,
        time_str: str,
    ) -> str:
        """Generate single filename from configuration.

        **Parameters:**
            `p` (Path): Source file path
            `cfg` (RenameCfg): Renaming configuration
            `counter_str` (str): Counter string
            `date_str` (str): Formatted date
            `time_str` (str): Formatted time

        **Returns:**
            `str`: Generated filename
        """
        # Extract filename components
        oname = p.stem
        ext = p.suffix
        ext_stem = ext.lstrip('.')

        # Apply name mask to generate new name and extension
        new_name = TokenProcessor.apply_name_mask(
            cfg.mask.name_mask,
            oname,
            ext,
            counter_str,
            date_str,
            time_str,
            p,
            cfg.dt.date_type
        )

        new_ext = TokenProcessor.apply_name_mask(
            cfg.mask.ext_mask,
            ext_stem,
            ext,
            counter_str,
            date_str,
            time_str,
            p,
            cfg.dt.date_type
        )
        if new_ext and not new_ext.startswith('.'):
            new_ext = f".{new_ext}"

        # Apply search/replace if configured
        if cfg.repl and cfg.repl.pattern:
            new_name = Renamer._apply_replace(new_name, cfg.repl, name_only=True)
            if not cfg.repl.exclude_extension:
                new_ext = Renamer._apply_replace(new_ext, cfg.repl, name_only=False)

        # Apply case transformation
        new_name = Renamer._apply_case(new_name, cfg.case)
        # Keep extension case unchanged

        # Sanitize for Windows compatibility if enabled
        if cfg.case.windows_names:
            new_name = Validator.sanitize_filename(new_name, windows_safe=True)
            new_ext = Validator.sanitize_filename(new_ext, windows_safe=True)

        return f"{new_name}{new_ext}"


#########################################
# HELPER METHODS - Date/time formatting #
#########################################
    @staticmethod
    def _format_date(cfg: DateTimeCfg, path: Path) -> str:
        """Format date according to configuration.

        **Parameters:**
            `cfg` (DateTimeCfg): Date/time configuration
            `path` (Path): File path

        **Returns:**
            `str`: Formatted date string
        """
        # Get datetime based on configuration
        dt = Renamer._get_datetime(cfg, path)

        # Format date according to specified format
        if cfg.date_format == 'YYYYMMDD':
            date_str = dt.strftime("%Y%m%d")
        elif cfg.date_format == 'DDMMYYYY':
            date_str = dt.strftime("%d%m%Y")
        elif cfg.date_format == 'MMDDYYYY':
            date_str = dt.strftime("%m%d%Y")
        elif cfg.date_format == 'YYYYMM':
            date_str = dt.strftime("%Y%m")
        elif cfg.date_format == 'MMYYYY':
            date_str = dt.strftime("%m%Y")
        else:  # YYYY
            date_str = dt.strftime("%Y")

        # Get separator character
        sep = Renamer._sep_value(cfg.date_sep)

        # Define format parts for each date format
        format_parts = {
            'YYYYMMDD': (4, 6),
            'DDMMYYYY': (2, 4),
            'MMDDYYYY': (2, 4),
            'YYYYMM': (4,),
            'MMYYYY': (2,),
            'YYYY': ()
        }

        # Insert separators at appropriate positions
        parts = format_parts[cfg.date_format]
        if cfg.date_format in ['YYYYMMDD', 'DDMMYYYY', 'MMDDYYYY']:
            start1, start2 = parts
            return f"{date_str[:start1]}{sep}{date_str[start1:start2]}{sep}{date_str[start2:]}"
        elif cfg.date_format in ['YYYYMM', 'MMYYYY']:
            start1 = parts[0]
            return f"{date_str[:start1]}{sep}{date_str[start1:]}"
        else:  # YYYY
            return date_str

    @staticmethod
    def _format_time(cfg: DateTimeCfg, path: Path) -> str:
        """Format time according to configuration.

        **Parameters:**
            `cfg` (DateTimeCfg): Date/time configuration
            `path` (Path): File path

        **Returns:**
            `str`: Formatted time string
        """
        # Get datetime based on configuration
        dt = Renamer._get_datetime(cfg, path)

        # Format time according to specified format
        if cfg.time_format == 'HHMMSS':
            time_str = dt.strftime("%H%M%S")
        elif cfg.time_format == 'HHMM':
            time_str = dt.strftime("%H%M")
        else:
            time_str = dt.strftime("%H")

        # Get separator character
        sep = Renamer._sep_value(cfg.time_sep)

        # Define format parts for each time format
        format_parts = {
            'HHMMSS': (2, 4),
            'HHMM': (2,),
            'HH': ()
        }

        # Insert separators at appropriate positions based on format
        parts = format_parts[cfg.time_format]
        if cfg.time_format == 'HHMMSS':
            return f"{time_str[:parts[0]]}{sep}{time_str[parts[0]:parts[1]]}{sep}{time_str[parts[1]:]}"
        elif cfg.time_format == 'HHMM':
            return f"{time_str[:parts[0]]}{sep}{time_str[parts[0]:]}"
        else:
            return time_str

    @staticmethod
    def _get_datetime(cfg: DateTimeCfg, path: Path) -> datetime:
        """Get datetime object based on configuration.

        **Parameters:**
            `cfg` (DateTimeCfg): Date/time configuration
            `path` (Path): File path

        **Returns:**
            `datetime`: Datetime object
        """
        if cfg.date_type == 'change':
            return Renamer._file_datetime(path, cfg.date_type)
        return datetime.now()


#########################################
# HELPER METHODS - Text transformations #
#########################################
    # Text-Tranformation
    @staticmethod
    def _apply_case(text: str, cfg: CaseCfg) -> str:
        """Apply case transformation.

        **Parameters:**
            `text` (str): Text to transform
            `cfg` (CaseCfg): Case configuration

        **Returns:**
            `str`: Text with case transformation
        """
        if cfg.mode == 'unchanged':
            return text
        return TokenProcessor.apply_case_transform(text, cfg.mode)

    @staticmethod
    def _apply_replace(text: str, cfg: ReplaceCfg, name_only: bool) -> str:
        """Apply search/replace operation.

        **Parameters:**
            `text` (str): Text to process
            `cfg` (ReplaceCfg): Search/replace configuration
            `name_only` (bool): Exclude extension

        **Returns:**
            `str`: Text with replacements applied
        """
        # Return unchanged if no pattern specified
        if not cfg.pattern:
            return text

        # Apply search/replace based on configuration
        pattern = cfg.pattern
        repl = cfg.replace

        try:
            # Use regex mode if enabled
            if cfg.regex:
                compiled = re.compile(pattern)
                count = 1 if cfg.first_only else 0
                result = compiled.sub(repl, text, count=count)
            else:
                # Compile pattern with search options
                compiled = Renamer._compile_search_replace_pattern(
                    pattern, False, cfg.exact, cfg.case_sensitive
                )
                count = 1 if cfg.first_only else 0
                result = compiled.sub(repl, text, count=count)
        except re.error:
            # Return unchanged text if regex is invalid
            return text

        return result

    @staticmethod
    def _compile_search_replace_pattern(text: str, regex: bool, exact: bool, case_sensitive: bool) -> re.Pattern:
        """Create regex pattern from search configuration.

        **Parameters:**
            `text` (str): Search pattern
            `regex` (bool): Use regex mode
            `exact` (bool): Whole word matching
            `case_sensitive` (bool): Case sensitive

        **Returns:**
            `re.Pattern`: Compiled regex pattern
        """
        # Use raw regex pattern if regex mode is enabled
        if regex:
            pat = text
        else:
            # Escape all regex meta-characters first
            esc = re.escape(text)

            # Convert wildcard symbols to regex equivalents
            esc = esc.replace(r'\*\*', '.*')  # '**' -> everything between the first and the next occurrence
            esc = esc.replace(r'\*', '.*?')   # '*'  -> everything between the first and last occurrence
            esc = esc.replace(r'\?', '.')     # '?'  -> single character

            pat = esc

        # Enforce whole word match if exact is True
        if exact:
            pat = r'\b(?:%s)\b' % pat

        # Apply case sensitivity flag
        flags = 0 if case_sensitive else re.IGNORECASE

        # Compile pattern safely, fallback to non-matching regex if invalid
        try:
            return re.compile(pat, flags)
        except re.error:
            return re.compile(r'(?!x)x')


######################################
# HELPER METHODS - Utility functions #
######################################
    @staticmethod
    def _sep_value(val: str) -> str:
        """Convert symbolic separator to actual character.

        **Parameters:**
            `val` (str): Symbolic value (none, space, or character)

        **Returns:**
            `str`: Actual separator character
        """
        separator_map = {
            'none': '',
            'space': ' '
        }
        return separator_map.get(val, val)

    @staticmethod
    def _file_datetime(path: Path, date_type: str) -> datetime:
        """Get datetime based on source type.

        **Parameters:**
            `path` (Path): File path
            `date_type` (str): Source type (current or change)

        **Returns:**
            `datetime`: Timestamp from current time or file mtime
        """
        if date_type == 'current':
            return datetime.now()

        try:
            ts = path.stat().st_mtime
            return datetime.fromtimestamp(ts)
        except (FileNotFoundError, OSError, PermissionError):
            return datetime.now()
