"""Main renaming logic and operations.

Provides functionality for generating preview names, planning rename operations,
checking for conflicts, and executing file renaming.
"""

import os
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from .file_operations import MoveExecutor
from .tokens import TokenProcessor
from .types import CaseCfg, DateTimeCfg, RenameCfg, RenameResult, ReplaceCfg
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
    def preview_names(paths: list[Path], cfg: RenameCfg) -> list[str]:
        """Generate preview names for file paths.

        **Parameters:**
            `paths` (list[Path]): Source file paths
            `cfg` (RenameCfg): Renaming configuration

        **Returns:**
            `list[str]`: Generated preview names
        """
        compiled = Renamer.validate_replace(cfg.repl)
        if not paths:
            return []

        # Resolve time once per preview and modification time once per file
        now = datetime.now()
        timestamps = [TokenProcessor.get_datetime(p, cfg.dt.date_type, now) for p in paths]
        formatted = [(timestamp, Renamer._format_date(cfg.dt, timestamp),
                      Renamer._format_time(cfg.dt, timestamp)) for timestamp in timestamps]

        def generate(index: int, counter: str) -> str:
            timestamp, date_str, time_str = formatted[index]
            return Renamer._generate_single_name(
                paths[index], cfg, counter, date_str, time_str, timestamp, compiled
            )

        if not cfg.counter.dupes_only:
            return [generate(i, f"{cfg.counter.start + i * cfg.counter.step:0{cfg.counter.digits}d}")
                    for i in range(len(paths))]

        # Group fully transformed names by destination directory
        base_names = [generate(i, '') for i in range(len(paths))]
        parents = {parent: os.path.normcase(str(parent.resolve()))
                   for parent in {p.parent for p in paths}}
        keys = [(parents[p.parent], os.path.normcase(name)) for p, name in zip(paths, base_names)]
        counts = Counter(keys)
        counters = defaultdict(int)
        results = []
        for i, key in enumerate(keys):
            if counts[key] == 1:
                results.append(base_names[i])
                continue
            value = cfg.counter.start + counters[key] * cfg.counter.step
            counters[key] += 1
            results.append(generate(i, f"{value:0{cfg.counter.digits}d}"))
        return results

    @staticmethod
    def plan_moves(paths: list[Path], new_names: list[str], *,
                   windows_safe: bool = False) -> list[tuple[Path, Path]]:
        """Plan rename operations.

        **Parameters:**
            `paths` (list[Path]): Source file paths
            `new_names` (list[str]): New filenames
            `windows_safe` (bool): Enforce Windows rules on every platform

        **Returns:**
            `list[tuple[Path, Path]]`: Source-destination pairs

        **Raises:**
            `ValueError`: If lengths differ or a destination name is invalid
        """
        if len(paths) != len(new_names):
            raise ValueError("Paths and new_names must have the same length")
        platform = 'windows' if os.name == 'nt' else 'linux'
        for path, name in zip(paths, new_names):
            if not Validator.validate_filename(name, windows_safe=windows_safe or os.name == 'nt'):
                raise ValueError(f"Invalid destination filename: {name!r}")
            if not Validator.validate_path_length(path.parent, name, platform=platform):
                raise ValueError(f"Destination name or path is too long: {name!r}")
        return [(p, p.with_name(n)) for p, n in zip(paths, new_names)]

    @staticmethod
    def perform_rename(moves: list[tuple[Path, Path]]) -> RenameResult:
        """Execute rename operations.

        **Parameters:**
            `moves` (list[tuple[Path, Path]]): Rename operations to execute

        **Returns:**
            `RenameResult`: Actual path changes, missing sources, and errors
        """
        return MoveExecutor.execute(moves)

    @staticmethod
    def undo_moves(moves: list[tuple[Path, Path]]) -> RenameResult:
        """Undo executed rename operations.

        **Parameters:**
            `moves` (list[tuple[Path, Path]]): Original rename operations

        **Returns:**
            `RenameResult`: Actual undo changes, missing sources, and errors
        """
        return MoveExecutor.execute([(dst, src) for src, dst in reversed(moves)])


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
        timestamp: datetime,
        compiled: re.Pattern | None,
    ) -> str:
        """Generate single filename from configuration.

        **Parameters:**
            `p` (Path): Source file path
            `cfg` (RenameCfg): Renaming configuration
            `counter_str` (str): Counter string
            `date_str` (str): Formatted date
            `time_str` (str): Formatted time
            `timestamp` (datetime): Shared file timestamp for custom tokens
            `compiled` (re.Pattern | None): Prepared search pattern

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
            ext_stem,
            counter_str,
            date_str,
            time_str,
            p,
            cfg.dt.date_type,
            timestamp
        )

        if cfg.mask.ext_mask == '{ext}':
            # Preserve the original suffix, including a lone dot on Unix
            new_ext = ext
        else:
            new_ext = TokenProcessor.apply_name_mask(
                cfg.mask.ext_mask,
                ext_stem,
                ext_stem,
                counter_str,
                date_str,
                time_str,
                p,
                cfg.dt.date_type,
                timestamp
            )
        if new_ext and not new_ext.startswith('.'):
            new_ext = f".{new_ext}"

        # Apply search/replace if configured
        if cfg.repl and cfg.repl.pattern:
            new_name = Renamer._apply_replace(new_name, cfg.repl, compiled)
            if not cfg.repl.exclude_extension:
                new_ext = Renamer._apply_replace(new_ext, cfg.repl, compiled)

        # Apply case transformation
        new_name = Renamer._apply_case(new_name, cfg.case)
        # Keep extension case unchanged

        # Sanitize the complete name before duplicate grouping and validation
        return Validator.sanitize_filename(
            f"{new_name}{new_ext}", windows_safe=cfg.case.windows_names or os.name == 'nt',
            linux_safe=os.name != 'nt'
        )

#########################################
# HELPER METHODS - Date/time formatting #
#########################################
    @staticmethod
    def _format_date(cfg: DateTimeCfg, timestamp: datetime) -> str:
        """Format a shared timestamp according to date configuration.

        **Parameters:**
            `cfg` (DateTimeCfg): Date/time configuration
            `timestamp` (datetime): Timestamp resolved for the source file

        **Returns:**
            `str`: Formatted date string
        """
        formats = {
            'YYYYMMDD': ('%Y', '%m', '%d'),
            'DDMMYYYY': ('%d', '%m', '%Y'),
            'MMDDYYYY': ('%m', '%d', '%Y'),
            'YYYYMM': ('%Y', '%m'),
            'MMYYYY': ('%m', '%Y'),
            'YYYY': ('%Y',)
        }
        if cfg.date_format not in formats:
            raise ValueError(f"Unknown date format: {cfg.date_format}")
        return timestamp.strftime(Renamer._sep_value(cfg.date_sep).join(formats[cfg.date_format]))

    @staticmethod
    def _format_time(cfg: DateTimeCfg, timestamp: datetime) -> str:
        """Format a shared timestamp according to time configuration.

        **Parameters:**
            `cfg` (DateTimeCfg): Date/time configuration
            `timestamp` (datetime): Timestamp resolved for the source file

        **Returns:**
            `str`: Formatted time string
        """
        formats = {'HHMMSS': ('%H', '%M', '%S'), 'HHMM': ('%H', '%M'), 'HH': ('%H',)}
        if cfg.time_format not in formats:
            raise ValueError(f"Unknown time format: {cfg.time_format}")
        return timestamp.strftime(Renamer._sep_value(cfg.time_sep).join(formats[cfg.time_format]))


#########################################
# HELPER METHODS - Text transformations #
#########################################
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
    def validate_replace(cfg: ReplaceCfg | None) -> re.Pattern | None:
        """Prepare a search pattern and validate regex replacement references.

        **Parameters:**
            `cfg` (ReplaceCfg | None): Search and replacement settings

        **Returns:**
            `re.Pattern | None`: Compiled pattern or None if search is disabled

        **Raises:**
            `ValueError`: If the search pattern or regex replacement is invalid
        """
        if cfg is None or not cfg.pattern:
            return None
        try:
            compiled = Renamer._compile_search_replace_pattern(
                cfg.pattern, cfg.regex, cfg.exact, cfg.case_sensitive
            )
            if cfg.regex:
                compiled.sub(cfg.replace, '')
            return compiled
        except (re.PatternError, IndexError) as e:
            raise ValueError(f"Invalid search or replacement pattern: {e}") from e

    @staticmethod
    def _apply_replace(text: str, cfg: ReplaceCfg, compiled: re.Pattern | None = None) -> str:
        """Apply search options using a prepared regex or wildcard pattern.

        **Parameters:**
            `text` (str): Text to process
            `cfg` (ReplaceCfg): Search and replacement settings
            `compiled` (re.Pattern | None): Pattern prepared for the entire preview

        **Returns:**
            `str`: Text with replacements applied
        """
        if not cfg.pattern:
            return text
        if compiled is None:
            compiled = Renamer.validate_replace(cfg)
        count = 1 if cfg.first_only else 0
        if cfg.regex:
            return compiled.sub(cfg.replace, text, count=count)
        # Treat replacement text literally outside regex mode
        return compiled.sub(lambda match: cfg.replace, text, count=count)

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
            esc = esc.replace(r'\*\*', '.*')  # '**' -> everything between the first and last occurrence
            esc = esc.replace(r'\*', '.*?')   # '*'  -> everything between the first and next occurrence
            esc = esc.replace(r'\?', '.')     # '?'  -> single character

            pat = esc

        # Enforce whole word match if exact is True
        if exact:
            pat = rf'\b(?:{pat})\b'

        # Apply case sensitivity flag
        flags = 0 if case_sensitive else re.IGNORECASE

        return re.compile(pat, flags)


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
