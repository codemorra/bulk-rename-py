# -*- coding: utf-8 -*-

# Bulk Rename Py
# © 2026–present Codemorra
# Licensed under the MIT License (see LICENSE file)

"""
Settings module for Bulk Rename Py.

Creates ‘config.ini’ if necessary, loads and checks whether it is
complete and valid, corrects incorrect entries, and writes changes.
"""


from __future__ import annotations
import os
import configparser
from pathlib import Path
from PySide6.QtCore import QLocale


# --- Constants ---
# path to the directory containing config.ini
if os.name == 'nt':  # Windows
    base_dir = Path(os.getenv('APPDATA', Path.home() / 'AppData' / 'Roaming'))
    CONFIG_DIR = base_dir / 'BulkRenamePy'
else:  # Linux
    _XDG = os.environ.get('XDG_CONFIG_HOME')
    CONFIG_DIR = Path(_XDG) / 'BulkRenamePy' if _XDG else Path.home() / '.config' / 'BulkRenamePy'

CONFIG_FILE = CONFIG_DIR / 'config.ini'

# default configuration
DEFAULTS = {
    'general': {
        'language': 'en',
        'hidden_files': False,
    },
    'rename': {
        'date_format': 'YYYYMMDD',
        'date_seperator': '-',
        'time_format': 'HHMM',
        'time_seperator': '-',
        'date_type': 'current',
    },
    'replace': {
        'regex': False,
        'only_first_match': False,
        'exact_match': False,
        'case_sensitive': False,
        'exclude_extension': True,
    },
    'counter': {
        'start': 1,
        'step': 1,
        'digits': 2,
        'dupes_only': False,
    },
    'advanced': {
        'case': 'unchanged',
        'windows_names': False,
    }
}

# permitted values
ALLOWED = {
    'general': {
        'language': {'de', 'en'},
    },
    'rename': {
        'date_format': {'YYYYMMDD', 'DDMMYYYY', 'MMDDYYYY'},
        'date_seperator': {'-', '_', '.', ':', ';', 'none', 'space'},
        'time_format': {'HHMMSS', 'HHMM', 'HH'},
        'time_seperator': {'-', '_', '.', ':', ';', 'none', 'space'},
        'date_type': {'change', 'current'},
    },
    'advanced': {
        'case': {'unchanged', 'lowercase', 'uppercase', 'heading', 'mocking'}
    }
}

# number ranges
RANGES = {
    ('counter', 'start'): (0, 10000),
    ('counter', 'step'): (1, 1000),
    ('counter', 'digits'): (1, 10),
}

# automatically derive Boolkeys from DEFAULTS
BOOL_KEYS = {
    (sec, key)
    for sec, kv in DEFAULTS.items()
    for key, val in kv.items()
    if isinstance(val, bool)
}


# --- Protected Functions ---
def _detect_system_language() -> str:
    """
    Detects the system language using Qt's locale system.

    **Returns:**
        `str`: `'de'` if a German locale is detected, otherwise `'en'`
    """
    bcp47 = QLocale.system().bcp47Name().lower()  # e.g. 'de-de', 'en-us'
    if bcp47.startswith('de'):
        return 'de'

    return 'en'


def _build_cfg_from_defaults(*, override_language: str | None = None) -> configparser.ConfigParser:
    """
    Creates a new :class:`ConfigParser` object based on the default values
    from ``DEFAULTS`` and optionally overrides the language.

    **Parameters:**
        `override_language` (str | None): If specified = language identifier, else None

    **Returns:**
        :class:`configparser.ConfigParser`: Fully constructed configuration object with all default values
    """
    # create a new empty configuration object
    cfg = configparser.ConfigParser()

    # populate all sections and keys from DEFAULTS
    for sec, kv in DEFAULTS.items():
        cfg[sec] = {}
        for k, v in kv.items():
            cfg[sec][k] = _to_str(v)

    # apply optional language override if provided
    if override_language is not None:
        cfg.set('general', 'language', override_language)

    return cfg


def _to_str(v) -> str:
    """
    Converts a value to a string.

    Boolean values are returned as “True”/“False”, all other
    types are converted using `str()`.

    **Parameters:**
        `v` (Any): Input value of any type

    **Returns:**
        `str`: String representation of the value
    """
    if isinstance(v, bool):
        return 'True' if v else 'False'

    return str(v)


def _parse_bool(s: str) -> bool | None:
    """
    Converts a string to a Boolean value.

    Accepts various notations (e.g., “true”, “1”, “yes”).
    Returns None if no clear interpretation is possible.

    **Parameters:**
        `s` (str): Input string

    **Returns:**
        `bool | None`: True or False if the value is valid, otherwise None
    """
    if s is None:
        return None

    low = s.strip().lower()

    if low in {'true', '1', 'yes', 'y', 'on'}:
        return True

    if low in {'false', '0', 'no', 'n', 'off'}:
        return False

    return None


def _sanitize_config(cfg: configparser.ConfigParser) -> bool:
    """
    Checks all configuration values for completeness and validity.

    Missing or invalid entries are reset to default values from `DEFAULTS`.
    Additionally checks allowed value ranges and enum fields.

    **Parameters:**
        `cfg` (configparser.ConfigParser): ConfigParser instance to be checked

    **Returns:**
        `bool`: True if changes have been made and need to be saved
    """
    changed = False

    # ensure all sections and default keys exist
    for sec, kv in DEFAULTS.items():
        for key, default_val in kv.items():
            if not cfg.has_section(sec):
                cfg.add_section(sec)
                changed = True
            if not cfg.has_option(sec, key):
                cfg.set(sec, key, _to_str(default_val))
                changed = True

    # normalize boolean values
    for (sec, key) in BOOL_KEYS:
        raw = cfg.get(sec, key, fallback=None)
        parsed = _parse_bool(raw) if raw is not None else None
        if parsed is None:
            parsed = DEFAULTS[sec][key]
        if raw != _to_str(parsed):
            cfg.set(sec, key, _to_str(parsed))
            changed = True

    # validate enum fields (allowed string values)
    for sec, keys in ALLOWED.items():
        for key, allowed in keys.items():
            val = cfg.get(sec, key, fallback=None)
            if val not in allowed:
                cfg.set(sec, key, _to_str(DEFAULTS[sec][key]))
                changed = True

    # validate numeric ranges and clamp out-of-range values
    for (sec, key), (lo, hi) in RANGES.items():
        raw = cfg.get(sec, key, fallback=None)
        try:
            n = int(raw)
        except (TypeError, ValueError):
            n = DEFAULTS[sec][key]
        clamped = max(lo, min(hi, n))
        if str(clamped) != raw:
            cfg.set(sec, key, str(clamped))
            changed = True

    return changed


# --- Public Functions ---
def ensure_config_file() -> None:
    """
    Creates the `config.ini` file with default values if it does not already exist.

    **Returns:**
        `None`
    """
    # ensure the configuration directory exists
    if not CONFIG_DIR.exists():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # create a new config.ini file using defaults if missing
    if not CONFIG_FILE.exists():
        lang = _detect_system_language()
        cfg = _build_cfg_from_defaults(override_language=lang)
        with CONFIG_FILE.open('w', encoding='utf-8') as f:
            cfg.write(f)


def reset_config(*, autodetect_language: bool = True) -> None:
    """
    Resets `config.ini` to the default values from `DEFAULTS`.

    The system language is automatically detected and entered accordingly
    under `[general] -> language`.

    **Parameters:**
        `autodetect_language` (bool): Specifies whether the system language should be automatically
        detected and applied when resetting.

    **Return:**
        `None`
    """
    # detect system language if enabled
    lang = _detect_system_language() if autodetect_language else None

    # build a new configuration with defaults and optional language override
    cfg = _build_cfg_from_defaults(override_language=lang)

    # ensure the configuration directory exists
    if not CONFIG_DIR.exists():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # overwrite existing config.ini with default values
    with CONFIG_FILE.open('w', encoding='utf-8') as f:
        cfg.write(f)


def get_config() -> configparser.ConfigParser:
    """
    Loads and checks the current `config.ini`.

    Creates the file if necessary, corrects invalid values using
    `_sanitize_config()`, and writes it back if necessary.

    **Returns:**
        `configparser.ConfigParser`: Loaded and validated ConfigParser instance
    """
    # ensure the configuration file exists (create with defaults if missing)
    ensure_config_file()

    # load the configuration from disk
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_FILE, encoding='utf-8')

    # validate and sanitize configuration, rewrite if corrections were made
    if _sanitize_config(cfg):
        with CONFIG_FILE.open('w', encoding='utf-8') as f:
            cfg.write(f)

    return cfg


def get_language_from_config() -> str:
    """
    Reads the currently set language from the configuration.

    **Returns:**
        `str`: Language code (e.g., “en” or “de”)
    """
    cfg = get_config()

    return cfg.get('general', 'language')


def set_language_in_config(lang_code: str) -> None:
    """
    Sets the display language in the configuration and saves the change.

    Validates the language code based on the allowed values.
    Invalid entries are reset to the default value.

    **Parameters:**
        `lang_code` (str): Language code (e.g., “de” or “en”)

    **Returns:**
        `None`
    """
    # validate the provided language code, fallback to default if invalid
    if lang_code not in ALLOWED['general']['language']:
        lang_code = DEFAULTS['general']['language']

    cfg = get_config()

    # update the language entry
    cfg.set('general', 'language', lang_code)

    # save updated configuration back to file
    with CONFIG_FILE.open('w', encoding='utf-8') as f:
        cfg.write(f)


def sanitize_and_save(cfg: configparser.ConfigParser) -> None:
    """
    Public helper function to validate and save an existing configuration.

    Executes `_sanitize_config()` and rewrites `config.ini` if changes are necessary.

    **Parameters:**
        `cfg` (configparser.ConfigParser): ConfigParser instance to check

    **Returns:**
        `None`
    """
    if _sanitize_config(cfg):
        with CONFIG_FILE.open('w', encoding='utf-8') as f:
            cfg.write(f)


def set_cfg(section: str, key: str, value) -> None:
    """
    Writes a configuration value to the .ini file and ensures
    that all values are valid and normalized.

    Under Windows, the entry “windows_names” is automatically set to True.

    **Parameters:**
        `section` (str): Name of the configuration section
        `key` (str): Key within the section
        `value` (Any): New value (any type, converted to string)

    **Returns:**
        `None`
    """
    # force Windows-specific rule -> 'windows_names' must always be True
    if section == 'advanced' and key == 'windows_names' and os.name == 'nt':
        value = True

    cfg = get_config()

    # ensure the target section exists
    if not cfg.has_section(section):
        cfg.add_section(section)

    # convert the value to string and set it in the configuration
    val_str = _to_str(value)
    cfg.set(section, key, val_str)

    sanitize_and_save(cfg)

    # write updated configuration to disk
    with CONFIG_FILE.open('w', encoding='utf-8') as f:
        cfg.write(f)
