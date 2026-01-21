# -*- coding: utf-8 -*-

# Bulk Rename Py
# © 2026–present Codemorra
# Licensed under the MIT License (see LICENSE file)

"""
Import module for Bulk Rename Py.

Contains the main logic for creating preview names, applying
placeholders, counters, search/replace functions, and case transformations.

Also included: conflict checking, undo, and execution of renames.
"""

from __future__ import annotations
import re
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from datetime import datetime


# --- constants ---
ILLEGAL_WIN_CHARS = set("<>:'/\\|?*")
RESERVED_WIN_NAMES = {
    'CON', 'PRN', 'AUX', 'NUL',
    *{f'COM{i}' for i in range(1, 10)},
    *{f'LPT{i}' for i in range(1, 10)},
}
_LITERAL_BRACES_PATTERN = re.compile(r'\{\{\}([^{}]+)\{\}\}')
_TOKEN_PATTERN = re.compile(r'\{([^\{\}]+)\}')


# --- Dataclasses ---
@dataclass
class DateTimeCfg:
    """
    Configuration structure for formatting the placeholders {date} and {time}.

    **Attributes:**
        `date_format` (str): Date format (e.g., “YYYYMMDD”)
        `date_sep` (str): Separator in the date (e.g., “-”, ‘_’, “none”)
        `time_format` (str): Time format (e.g., “HHMMSS”)
        `time_sep` (str): Separator in the time
        `date_type` (str): Source of the date (“current” or “change”)
    """
    date_format: str
    date_sep: str
    time_format: str
    time_sep: str
    date_type: str

@dataclass
class CounterCfg:
    """
    Configuration for the placeholder {counter}.

    **Attributes:**
        `start` (int): Starting value of the counter
        `step` (int): Step size between values
        `digits` (int): Number of leading zeros
        `dupes_only` (bool): Apply only to duplicates
    """
    start: int
    step: int
    digits: int
    dupes_only: bool

@dataclass
class ReplaceCfg:
    """
    Configuration for search and replace functions.

    **Attributes:**
        `pattern` (str): Search pattern (regex or wildcard)
        `replace` (str): Replacement text
        `regex` (bool): Enable regular expressions
        `exact` (bool): Replace only exact matches
        `case_sensitive` (bool): Case sensitive
        `exclude_extension` (bool): Exclude file extension
        `first_only` (bool): Replace only the first occurrence
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
    """
    Configuration for spelling and Windows-compatible names.

    **Attributes:**
        `mode` (str): Writing mode (“unchanged,” “lowercase,” “uppercase,” “heading,” “mocking”)
        `windows_names` (bool): Automatically clean up invalid Windows characters
    """
    mode: str
    windows_names: bool

@dataclass
class MaskCfg:
    """
    Configuration of name and extension masks.

    **Attributes:**
        `name_mask` (str): Mask for the file name (e.g., “{name}_{counter}”)
        `ext_mask` (str): Mask for the extension (e.g., “{ext}”)
    """
    name_mask: str
    ext_mask: str

@dataclass
class RenameCfg:
    """
    Configuration structure for a renaming operation.

    **Attributes:**
        `dt` (DateTimeCfg): Settings for date/time format
        `counter` (CounterCfg): Counter configuration
        `repl` (ReplaceCfg | None): Search/replace configuration
        `case` (CaseCfg): Case and Windows options
        `mask` (MaskCfg): Name and extension masks
    """
    dt: DateTimeCfg
    counter: CounterCfg
    repl: Optional[ReplaceCfg]
    case: CaseCfg
    mask: MaskCfg


# --- Protected Functions ---
def _has_backref(s: str) -> bool:
    """
    Checks whether the string contains unescaped regex
    backreferences (e.g., “\\1” or “\\g<name>”).

    **Parameters:**
        `s` (str): Input string

    **Returns:**
        `bool`: True if backreferences were found; otherwise False
    """
    return bool(re.search(r'(?<!\\)\\(?:\d+|g<[^>]+>)', s))


def _split_name_ext(filename: str) -> tuple[str, str]:
    """
    Splits a filename into (name, extension), taking leading dots into account.

    **Parameters:**
        `filename` (str): File name (without path)

    **Returns:**
        `tuple[str, str]`: Tuple consisting of base name and extension (extension without dot)
    """
    # handle filenames starting with a dot
    if filename.startswith('.'):
        idx = filename[1:].rfind('.')  # search for next dot after the first
        if idx == -1:
            # no further dot -> no extension
            return filename, ''
        cut = 1 + idx
        return filename[:cut], filename[cut+1:]

    # handle normal filenames (without leading dot)
    idx = filename.rfind('.')  # find last dot
    if idx <= 0:
        # no extension or dot at start
        return filename, ''

    # split into name and extension
    return filename[:idx], filename[idx+1:]


def _slice_token(text: str, spec: str) -> str:
    """
    Cuts out a substring according to specifications such as “1-3,” “4-*,” or
    “*-5” (1-based, including end index).

    Supported formats:
    - “1-3” -> characters 1 to 3
    - “4-*” -> from character 4 to the end
    - “*-5” -> from the beginning to character 5
    - “*-*”, “-”, or invalid specifications -> no cut (Original text)

    **Parameters:**
        `text` (str): Source text
        `spec` (str): Range specification (“start-end”)

    **Returns:**
        `str`: Cut substring or original text
    """
    spec = spec.strip()

    # Matches: 1-3, *-5, 4-*, *-*
    m = re.fullmatch(r'(\d+|\*)-(\d+|\*)', spec)
    if not m:
        return text

    left, right = m.groups()

    # determine the beginning
    start = 1 if left == '*' else max(1, int(left))
    end = len(text) if right == '*' else int(right)

    # if mixed up
    if end < start:
        start, end = end, start

    return text[start - 1:end]


def _sep_value(val: str) -> str:
    """
    Converts symbolic separator values into effective characters.

    This helper translates user-friendly configuration values such as 'none' or 'space'
    into the corresponding characters that are used when constructing new filenames.
    Any other value is returned unchanged.

    **Parameters:**
        `val` (str): Symbolic value (“none,” “space,” or concrete character)

    **Returns:**
        `str`: Effective separator (“” for “none,” “ ” for “space,” otherwise `val`)
    """
    return '' if val == 'none' else (' ' if val == 'space' else val)


def _file_datetime(path: Path, date_type: str) -> datetime:
    """
    Determines a date/time object based on the source (“current” or change time “change”).

    **Parameters:**
        `path` (path): File path
        `date_type` (str): “current” for current time, “change” for mtime

    **Returns:**
        `datetime`: Determined timestamp (current time in case of errors)
    """
    # use current system time if requested directly
    if date_type == 'current':
        return datetime.now()

    # try to read the file's modification timestamp (mtime)
    try:
        ts = path.stat().st_mtime
        return datetime.fromtimestamp(ts)
    except FileNotFoundError:
        # fallback: file missing -> use current time instead
        return datetime.now()


def _format_datetime_for_file(path: Path, cfg: DateTimeCfg) -> tuple[str, str]:
    """
    Formats the date and time of a file according to `DateTimeCfg`.

    **Parameters:**
        `path` (Path): File path
        `cfg` (DateTimeCfg): Date/time formatting

    **Returns:**
        `tuple[str, str]`: (Date string, time string) according to configuration
    """
    d = _file_datetime(path, cfg.date_type)

    # Date
    if cfg.date_format == 'YYYYMMDD':
        date_core = f'{d:%Y}{_sep_value(cfg.date_sep)}{d:%m}{_sep_value(cfg.date_sep)}{d:%d}'
    elif cfg.date_format == 'DDMMYYYY':
        date_core = f'{d:%d}{_sep_value(cfg.date_sep)}{d:%m}{_sep_value(cfg.date_sep)}{d:%Y}'
    else:  # 'MMDDYYYY'
        date_core = f'{d:%m}{_sep_value(cfg.date_sep)}{d:%d}{_sep_value(cfg.date_sep)}{d:%Y}'

    # Time
    if cfg.time_format == 'HHMMSS':
        time_core = f'{d:%H}{_sep_value(cfg.time_sep)}{d:%M}{_sep_value(cfg.time_sep)}{d:%S}'
    elif cfg.time_format == 'HHMM':
        time_core = f'{d:%H}{_sep_value(cfg.time_sep)}{d:%M}'
    else:  # 'HH'
        time_core = f'{d:%H}'

    return date_core, time_core


def _apply_case(s: str, mode: str) -> str:
    """
    Converts the spelling of a string according to mode (lowercase, uppercase, heading, mocking).

    **Parameters:**
        `s` (str): Input string
        `mode` (str): Writing mode (“lowercase,” “uppercase,” “heading,” “mocking,” “unchanged”)

    **Returns:**
        `str`: Converted string
    """
    if mode == 'lowercase':
        return s.lower()

    if mode == 'uppercase':
        return s.upper()

    if mode == 'heading':
        def cap(m: re.Match) -> str:
            w = m.group(0)
            return w[:1].upper() + w[1:].lower()
        return re.sub(r'[A-Za-zÀ-ÖØ-öø-ÿÄÖÜäöüß]+', cap, s)

    if mode == 'mocking':
        res, up = [], True
        for ch in s:
            if ch.isalpha():
                res.append(ch.upper() if up else ch.lower())
                up = not up
            else:
                res.append(ch)
        return ''.join(res)

    return s


def _sanitize_linux(name: str) -> str:
    """
    Replaces forward slashes with the Unicode fraction slash
    to ensure compatibility with Linux file systems.

    **Parameters:**
        `name` (str): Candidate file name

    **Returns:**
        `str`: Linux-compatible file name (no '/' remains)
    """
    return name.replace('/', '\u2044')


def _sanitize_windows(name: str) -> str:
    """
    Cleans a file name of invalid Windows characters and extensions and avoids reserved names.

    **Parameters:**
        `name` (str): Original file name

    **Returns:**
        `str`: Windows-compatible file name
    """
    cleaned = []

    # replace illegal characters and control codes with underscores
    for char in name:
        if char in ILLEGAL_WIN_CHARS or ord(char) < 32:
            cleaned.append('_')
        else:
            cleaned.append(char)

    name = ''.join(cleaned)
    # Strip trailing dots or spaces (not allowed on Windows)

    name = name.rstrip('. ')

    # ensure the name is not empty
    if not name:
        name = '_'

    # split into base name and extension
    base, ext = _split_name_ext(name)

    # prefix reserved device names (e.g. CON, NUL) with underscore
    if base.upper() in RESERVED_WIN_NAMES:
        base = '_' + base

    # recombine base and extension (omit dot if no extension)
    return f'{base}.{ext}' if ext else base


def _escape_literal_braces(text: str) -> tuple[str, dict[int, str]]:
    """
    Replaces literal-brace blocks like `{{}name{}}` with opaque markers.

    **Parameters:**
    `text` (str): Input mask text that may contain `{{}...{}}`

    **Returns:**
        `tuple[str, dict[int, str]]`: (`escaped_text`, `mapping`)
        `escaped_text`: Text with `{{}...{}}` replaced by `__LITBRACE_i__`
        `mapping`: Index -> inner literal (e.g. 'name') for later restoration
    """
    mapping: dict[int, str] = {}
    idx = 0

    # replacement function for each regex match
    def _repl(m: re.Match) -> str:
        nonlocal idx
        mapping[idx] = m.group(1)
        token = f'__LITBRACE_{idx}__'
        idx += 1
        return token

    # replace all literal-brace blocks with placeholder tokens
    escaped = _LITERAL_BRACES_PATTERN.sub(_repl, text)

    # Return escaped text and mapping for later restoration
    return escaped, mapping


def _restore_literal_braces(text: str, mapping: dict[int, str]) -> str:
    """
    Restores literal-brace markers back to real braces.

    **Parameters:**
        `text` (str): Text containing `__LITBRACE_i__` markers
        `mapping` (dict[int, str]): Index -> inner literal returned by `_escape_literal_braces`

    **Returns:**
        `str`: Text where markers are replaced with `{<literal>}`
    """
    for i, val in mapping.items():
        text = text.replace(f'__LITBRACE_{i}__', f'{{{val}}}')

    return text


def _build_counter_values(count: int, start: int, step: int, digits: int) -> List[str]:
    """
    Generates a list of zero-filled counter values (e.g., “001,” “002,” etc.).

    **Parameters:**
        `count` (int): Number of values required
        `start` (int): Start value
        `step` (int): Step size
        `digits` (int): Number of digits (leading zeros)

    **Returns:**
        `list[str]`: Formatted counter values as strings
    """
    vals, cur = [], start

    for _ in range(count):
        vals.append(str(cur).zfill(digits))
        cur += step

    return vals


def _compile_search_replace_pattern(text: str, regex: bool, exact: bool, case_sensitive: bool) -> re.Pattern:
    """
    Creates a regex search pattern, alternatively supports wildcards (*, **, ?) when `regex=False`.

    **Parameters:**
        `text` (str): Search pattern (regex or wildcards)
        `regex` (bool): True = regex, False = wildcards
        `exact` (bool): Allow only whole word matches (word boundaries)
        `case_sensitive` (bool): Case sensitive

    **Returns:**
        `re.Pattern`: Compiled regex pattern (never matches if there are errors)
    """
    # use raw regex pattern if regex mode is enabled
    if regex:
        pat = text
    else:
        # escape all regex meta-characters first
        esc = re.escape(text)

        # convert wildcard symbols to regex equivalents
        esc = esc.replace(r'\*\*', '.*')  # '**' -> everything between the first and the next occurrence
        esc = esc.replace(r'\*', '.*?')   # '*'  -> everything between the first and last occurrence
        esc = esc.replace(r'\?', '.')     # '?'  -> single character

        pat = esc

    # enforce whole word match if exact is True
    if exact:
        pat = r'\b(?:%s)\b' % pat

    # apply case sensitivity flag
    flags = 0 if case_sensitive else re.IGNORECASE

    # compile pattern safely, fallback to non-matching regex if invalid
    try:
        return re.compile(pat, flags)
    except re.error:
        return re.compile(r'(?!x)x')


def _apply_search_replace(fullname: str, name_only: bool, pattern: re.Pattern,
                          repl: str, first_only: bool, *, literal_repl: bool = False) -> str:
    """
    Performs search/replace on file names.
    Optional literal replacement (without backref template).

    **Parameters:**
        `fullname` (str): Full name (with/without extension)
        `name_only` (bool): Change base name only (keep extension)
        `pattern` (re.Pattern): Compiled search pattern
        `repl` (str): Replacement text
        `first_only` (bool): Replace only the first occurrence
        `literal_repl` (bool): Treat replacement text strictly literally

    **Returns:**
        `str`: New name (unchanged if applicable)
    """
    # determine replacement count: 1 = only first match, 0 = all matches
    count = 1 if first_only else 0

    # enable literal replacement mode if requested or if no capture groups exist
    use_literal = literal_repl or (pattern.groups == 0 and _has_backref(repl))

    # inner helper to apply replacement safely
    def _sub(text: str) -> str:
        if use_literal:
            # perform literal substitution (ignore regex backreferences)
            return pattern.sub(lambda m: repl, text, count=count)
        else:
            # try normal regex replacement, fallback to literal if invalid
            try:
                return pattern.sub(repl, text, count=count)
            except re.error:
                return pattern.sub(lambda m: repl, text, count=count)

    # apply substitution only to the base name or the full string
    if name_only:
        n, e = _split_name_ext(fullname)
        new_n = _sub(n)
        return f'{new_n}.{e}' if e else new_n
    else:
        return _sub(fullname)


def _apply_name_mask(mask: str, oname: str, counter: str, date_str: str, time_str: str) -> str:
    """
    Applies placeholders in the name mask ({name}, {name1-3}, {counter}, {date}, {time}).
    Supports literal braces via `{{}...{}}` (e.g., `{{}name{}}` -> `{name}`).

    **Parameters:**
        `mask` (str): Name mask
        `oname` (str): Original base name
        `counter` (str): Formatted counter value
        `date_str` (str): Formatted date string
        `time_str` (str): Formatted time string

    **Returns:**
        `str`: Result name after applying the mask
    """
    # protect literal `{...}` segments like `{{}name{}}`
    esc_mask, litmap = _escape_literal_braces(mask)

    def repl(m: re.Match) -> str:
        tok = m.group(1)

        # exact {name}
        if tok == 'name':
            return oname

        # {name<slice>} e.g. {name1-3}, {name4-*}, {name*-5}, {name*-*}
        if tok.startswith('name'):
            spec = tok[4:]
            # only accept if spec complies with slicer format
            if spec and re.fullmatch(r'(\d+|\*)-(\d+|\*)', spec):
                return _slice_token(oname, spec)

            # invalid (e.g., {namename}) -> leave unchanged
            return '{' + tok + '}'

        # other permitted tokens
        if tok == 'counter':
            return counter
        if tok == 'date':
            return date_str
        if tok == 'time':
            return time_str

        # unknown -> leave unchanged
        return '{' + tok + '}'

    # apply token substitution across the escaped mask
    out = _TOKEN_PATTERN.sub(repl, esc_mask)

    # restore any previously escaped literal braces and return final result
    return _restore_literal_braces(out, litmap)


def _apply_ext_mask(mask: str, oext: str, counter: str) -> str:
    """
    Applies placeholders in the extension mask ({ext}, {ext1-3}, {counter}).
    Supports literal braces via `{{}...{}}` (e.g., `{{}ext{}}` -> `{ext}`).

    **Parameters:**
        `mask` (str): Extension mask
        `oext` (str): Original extension (without dot)
        `counter` (str): Formatted counter value

    **Returns:**
        `str`: Resulting extension after applying the mask (without dot)
    """
    # protect literal `{...}` segments like `{{}ext{}}`
    esc_mask, litmap = _escape_literal_braces(mask)

    # replacement callback for each placeholder match
    def repl(m: re.Match) -> str:
        tok = m.group(1)
        # handle {ext} and sliced variants like {ext1-3}
        if tok.startswith('ext'):
            if tok == 'ext':
                return oext
            # slice spec after 'ext'
            spec = tok[3:]
            # accept only numeric slice specs
            if spec and spec[0].isdigit():
                return _slice_token(oext, spec)
            # fallback: treat as {ext}
            return oext

        # handle {counter}
        if tok == 'counter':
            return counter

        # unknown token -> leave unchanged (reinsert braces)
        return '{' + tok + '}'

    # apply token substitution across the escaped mask
    out = _TOKEN_PATTERN.sub(repl, esc_mask)

    # restore previously escaped literal braces and return final extension
    return _restore_literal_braces(out, litmap)


def _linux_fs_limits(base_dir: Path) -> tuple[int, int]:
    """
    Determines the system-dependent limits (NAME_MAX, PATH_MAX)
    for the current file system under Linux.

    If no values are available, safe default values are used (255 / 4096).

    **Parameters**:
        `base_dir` (path): Base directory whose file system is checked.

    **Returns**:
        `tuple[int, int]`: (name_max, path_max) in bytes.
    """
    # try to read the maximum allowed file name length (NAME_MAX)
    try:
        name_max = os.pathconf(str(base_dir), 'PC_NAME_MAX')
    except Exception:
        # fallback to safe default
        name_max = 255

    # try to read the maximum allowed full path length (PATH_MAX)
    try:
        path_max = os.pathconf(str(base_dir), 'PC_PATH_MAX')
    except Exception:
        # fallback to safe default
        path_max = 4096

    # return sanitized limits with minimal guaranteed thresholds
    return max(int(name_max), 32), max(int(path_max), 512)


def _b_len(s: str) -> int:
    """
    Returns the byte length of a string in the file system encoding
    (typically UTF-8 on Linux).

    **Parameters**:
        `s` (str): Character string.

    **Returns**:
        `int`: Length in bytes.
    """
    return len(os.fsencode(s))


# --- Public Functions ---
def preview_names(paths: List[Path], cfg: RenameCfg) -> List[str]:
    """
    Generates preview target names according to configuration;
    optionally {counter} only for duplicates.

    **Parameters:**
        `paths` (list[Path]): Source paths
        `cfg` (RenameCfg): Complete renaming configuration

    **Returns:**
        `list[str]`: List of new file names (without path)
    """
    if not paths:
        return []

    # precompile replace-pattern (may be None)
    pattern: Optional[re.Pattern] = None
    if cfg.repl and cfg.repl.pattern:
        pattern = _compile_search_replace_pattern(
            cfg.repl.pattern, cfg.repl.regex, cfg.repl.exact, cfg.repl.case_sensitive
        )

    # builds the new file name from the original name, masks, and formatting.
    def render_for(p: Path, counter_str: str) -> str:
        # separate original name and extension
        oname, oext = _split_name_ext(p.name)

        # search and replace only in original name
        if pattern is not None:
            oname_full = p.name
            apply_on_name_only = bool(cfg.repl.exclude_extension)
            oname_full = _apply_search_replace(
                oname_full,
                name_only=apply_on_name_only,
                pattern=pattern,
                repl=cfg.repl.replace,
                first_only=bool(cfg.repl.first_only),
                literal_repl=not bool(cfg.repl.regex)
            )
            oname, oext = _split_name_ext(oname_full)

        # format date/time
        date_str, time_str = _format_datetime_for_file(p, cfg.dt)

        # apply masks
        name_res = _apply_name_mask(cfg.mask.name_mask, oname, counter_str, date_str, time_str)
        ext_res  = _apply_ext_mask(cfg.mask.ext_mask, oext, counter_str)

        # apply upper/lower case
        name_res = _apply_case(name_res, cfg.case.mode)

        # combine name and extension
        fullname = f'{name_res}.{ext_res}' if ext_res else name_res

        # replaces forward slashes with the Unicode fraction slash in Linux
        if os.name != 'nt':
            fullname = _sanitize_linux(fullname)

        # remove characters that are not compatible with Windows
        if cfg.case.windows_names:
            fullname = _sanitize_windows(fullname)

        return fullname

    # normal case -> apply counters everywhere
    if not cfg.counter.dupes_only:
        # group files by directory so each directory gets its own counter sequence
        from collections import defaultdict
        grouped: Dict[Path, List[Path]] = defaultdict(list)
        for p in paths:
            grouped[p.parent].append(p)

        # precompute counter strings per directory
        counters_by_dir: Dict[Path, List[str]] = {
            d: _build_counter_values(
                len(file_list),
                cfg.counter.start,
                cfg.counter.step,
                cfg.counter.digits
            )
            for d, file_list in grouped.items()
        }

        # keep a running index per directory as we iterate in the original order
        next_idx_by_dir: Dict[Path, int] = {d: 0 for d in grouped}

        result: List[str] = []
        for p in paths:
            d = p.parent
            i = next_idx_by_dir[d]
            counter_str = counters_by_dir[d][i]
            next_idx_by_dir[d] = i + 1
            result.append(render_for(p, counter_str))

        return result

    # only for duplicates, first render without counter and search for duplicates
    base_names = [render_for(p, '') for p in paths]

    # collect indexes by target name
    groups: Dict[str, List[int]] = {}
    for idx, name in enumerate(base_names):
        groups.setdefault(name, []).append(idx)

    # pre-fill result array (singles retain names without counters)
    result: List[str] = base_names[:]

    # assign a counter to each group with >1 element (restart per group)
    for name, indices in groups.items():
        if len(indices) <= 1:
            continue
        vals = _build_counter_values(len(indices), cfg.counter.start, cfg.counter.step, cfg.counter.digits)
        for j, idx in enumerate(indices):
            result[idx] = render_for(paths[idx], vals[j])

    return result


def plan_moves(paths: List[Path], new_names: List[str]) -> List[Tuple[Path, Path]]:
    """
    Generates (source, destination) pairs for the renaming plan.

    **Parameters:**
        `paths` (list[Path]): Old paths
        `new_names` (list[str]): New file names (without path)

    **Returns:**
        `list[tuple[Path, Path]]`: Mapping of old -> new paths
    """
    return [(p, p.with_name(n)) for p, n in zip(paths, new_names)]


def check_conflicts(plan: List[Tuple[Path, Path]]) -> List[str]:
    """
    Checks a plan for internal duplicates and collisions with existing target files.

    **Parameters:**
        `plan` (list[tuple[Path, Path]]): Renaming plan

    **Returns:**
        `list[str]`: Conflict messages (empty if none)
    """
    conflicts: List[str] = []
    per_dir: Dict[Path, Dict[str, Path]] = {}
    plan_src_set = {str(src) for src, _ in plan}

    # check for internal duplicates
    for src, dst in plan:
        d = dst.parent
        per_dir.setdefault(d, {})
        key = dst.name
        if key in per_dir[d] and per_dir[d][key] != src:
            conflicts.append(f'{src} -> {dst} (doppelter Zielname)')
        else:
            per_dir[d][key] = src

    # prepare mapping of planned destinations per directory
    plan_dst_by_dir: Dict[Path, set[str]] = {}
    for _, dst in plan:
        plan_dst_by_dir.setdefault(dst.parent, set()).add(dst.name)

    # check for external collisions
    for target_dir, names in plan_dst_by_dir.items():
        try:
            for entry in target_dir.iterdir():
                if entry.name in names:
                    if str(entry) not in plan_src_set:
                        conflicts.append(f'{entry} existiert bereits')
        except Exception:
            # ignore directories that cannot be read
            pass

    return conflicts


def perform_rename(plan: List[Tuple[Path, Path]]) -> List[str]:
    """
    Performs all renaming operations safely using a two-phase rename
    to avoid overwriting existing files and collects any errors that occur.

    **Parameters:**
        `plan` (list[tuple[Path, Path]]): Renaming plan

    **Returns:**
        `list[str]`: Error messages per entry (empty if successful)
    """
    errors: List[str] = []
    tmp_moves: List[Tuple[Path, Path]] = []

    # rename everything to temporary names
    for i, (src, _) in enumerate(plan):
        try:
            tmp = src.with_name(f'.__brp_tmp__{i}')
            os.rename(src, tmp)
            tmp_moves.append((tmp, src))
        except Exception as e:
            errors.append(f'{src}: {e}')
            return errors  # abort immediately

    # rename temporary files to final targets
    for (tmp, _), (_, dst) in zip(tmp_moves, plan):
        try:
            os.rename(tmp, dst)
        except Exception as e:
            errors.append(f'{tmp} -> {dst}: {e}')

    return errors


def undo_moves(moves: List[Tuple[Path, Path]]) -> Tuple[List[str], List[str]]:
    """
    Undoes renames based on an in-memory move list `(old, new)`.

    Reverts all renames in reverse order, verifying that new paths exist
    and that original names do not already exist before renaming back.

    **Parameters:**
        `moves` (list[tuple[Path, Path]]): List of `(old, new)` rename pairs

    **Returns:**
        `tuple[list[str], list[str]]`: (`missing`, `errors`) — missing targets and error messages
    """
    # check whether all “new” targets are present
    missing = [str(new) for (_, new) in moves if not new.exists()]
    if missing:
        return missing, []

    # check for collisions with existing “old”
    conflicts = []
    for old, new in moves:
        if old.exists() and str(old) != str(new):
            conflicts.append(f'{old} existiert bereits')
    if conflicts:
        return [], conflicts

    # rename backwards
    errors: List[str] = []
    for old, new in reversed(moves):
        try:
            os.rename(new, old)
        except Exception as e:
            errors.append(f'{e}')

    return [], errors


def validate_windows_length(base_dir: Path, new_name: str) -> bool:
    """
    Checks the maximum allowed length of a file name and path
    under **Windows**.

    Rules:
    - Single file name ≤ 255 characters
    - Total path ≤ 260 characters (MAX_PATH)

    **Parameters**:
        `base_dir` (Path): Target directory
        `new_name` (str): New file name (without path)

    **Returns**:
        `bool`: True if valid; False if too long
    """
    full = str(base_dir / new_name)

    if len(new_name) > 255:
        return False

    if len(full) > 260:
        return False

    return True


def validate_linux_bytes(base_dir: Path, new_name: str) -> bool:
    """
    Checks whether a path and file name comply with the permissible limits
    under **Linux**.

    Rules:
    - Single file name ≤ NAME_MAX bytes
    - Total path ≤ PATH_MAX bytes
    (Default values: 255 / 4096)

    **Parameters**:
        `base_dir` (Path): Base directory
        `new_name` (str): New file name (without path)

    **Returns**:
        `bool`: True if valid; False if the byte limit is exceeded
    """
    name_max, path_max = _linux_fs_limits(base_dir)
    full_path = str(base_dir / new_name)

    if _b_len(new_name) > name_max:
        return False

    if _b_len(full_path) > path_max:
        return False

    return True
