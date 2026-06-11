# -*- coding: utf-8 -*-

# Bulk Rename Py
# © 2026–present Codemorra (Christopher Kranz)
# Licensed under the MIT License (see LICENSE file)

"""Settings module for Bulk Rename Py.

Handles application configuration including automatic file creation,
validation, sanitization, and persistent storage of user preferences.
Ensures configuration is always valid with missing or invalid values
automatically reset to defaults. Supports platform-specific handling
for Windows and Linux systems.
"""

from __future__ import annotations
import os
import configparser
from pathlib import Path
from PySide6.QtCore import QLocale

# Constants
if os.name == 'nt':  # Windows
    base_dir = Path(os.getenv('APPDATA', Path.home() / 'AppData' / 'Roaming'))
    CONFIG_DIR = base_dir / 'BulkRenamePy'
else:  # Linux
    _XDG = os.environ.get('XDG_CONFIG_HOME')
    CONFIG_DIR = Path(_XDG) / 'BulkRenamePy' if _XDG else Path.home() / '.config' / 'BulkRenamePy'

CONFIG_FILE = CONFIG_DIR / 'config.ini'

# Default configuration
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

# Permitted values
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

# Number ranges
MAX_COUNTER_START = 10000
MAX_COUNTER_STEP = 1000
MAX_COUNTER_DIGITS = 10

RANGES = {
    ('counter', 'start'): (0, MAX_COUNTER_START),
    ('counter', 'step'): (1, MAX_COUNTER_STEP),
    ('counter', 'digits'): (1, MAX_COUNTER_DIGITS),
}

# Automatically derive Boolkeys from DEFAULTS
BOOL_KEYS = {
    (sec, key)
    for sec, kv in DEFAULTS.items()
    for key, val in kv.items()
    if isinstance(val, bool)
}


######################
# MAIN FUNCTIONALITY #
######################
def ensure_config_file() -> None:
    """Ensure configuration file exists, create with defaults if missing.

    Creates the configuration directory and file if they don't exist.
    Uses system language detection for initial language setting.

    **Returns:**
        `None`
    """
    # Create configuration directory if it doesn't exist
    if not CONFIG_DIR.exists():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # Create default configuration file if missing
    if not CONFIG_FILE.exists():
        lang = _detect_system_language()
        cfg = _build_cfg_from_defaults(override_language=lang)
        _save_config(cfg)

def get_config() -> configparser.ConfigParser:
    """Load and validate configuration.

    Ensures configuration file exists, loads it, validates all values,
    and corrects invalid entries using defaults.

    **Returns:**
        `configparser.ConfigParser`: Validated configuration object
    """
    # Ensure configuration file exists
    ensure_config_file()

    # Load configuration from disk
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_FILE, encoding='utf-8')

    # Validate and sanitize configuration
    if _sanitize_config(cfg):
        _save_config(cfg)

    return cfg

def get_language_from_config() -> str:
    """Get current language from configuration.

    **Returns:**
        `str`: Language code (e.g., 'en', 'de')
    """
    return get_config().get('general', 'language')

def set_cfg(section: str, key: str, value) -> None:
    """Set configuration value with validation.

    Sets a configuration value, validates it, and persists changes.
    Enforces Windows-specific rules automatically.

    **Parameters:**
        `section` (str): Configuration section
        `key` (str): Configuration key
        `value` (Any): Value to set

    **Returns:**
        `None`

    **Raises:**
        `RuntimeError`: If configuration cannot be saved
    """
    # Force Windows-specific rule
    if section == 'advanced' and key == 'windows_names' and os.name == 'nt':
        value = True

    # Get current configuration
    cfg = get_config()

    # Ensure section exists
    if not cfg.has_section(section):
        cfg.add_section(section)

    # Set value and save
    cfg.set(section, key, _to_str(value))
    _save_config(cfg)

def set_language_in_config(lang_code: str) -> None:
    """Set language in configuration.

    Validates the language code and updates configuration.

    **Parameters:**
        `lang_code` (str): Language code to set

    **Returns:**
        `None`
    """
    # Validate language code
    if lang_code not in ALLOWED['general']['language']:
        lang_code = DEFAULTS['general']['language']

    # Update configuration
    cfg = get_config()
    cfg.set('general', 'language', lang_code)
    _save_config(cfg)

def reset_config(*, autodetect_language: bool = True) -> None:
    """Reset configuration to default values.

    Overwrites existing configuration with default values.
    Can optionally detect and use system language.

    **Parameters:**
        `autodetect_language` (bool): Whether to detect system language

    **Returns:**
        `None`
    """
    # Detect system language if enabled
    lang = _detect_system_language() if autodetect_language else None

    # Build new configuration with defaults
    cfg = _build_cfg_from_defaults(override_language=lang)
    _save_config(cfg)


####################
# HELPER FUNCTIONS #
####################
def _build_cfg_from_defaults(*, override_language: str | None = None) -> configparser.ConfigParser:
    """Build configuration from default values.

    Creates a new ConfigParser with all default values.
    Optionally overrides the language setting.

    **Parameters:**
        `override_language` (str | None): Language code override

    **Returns:**
        `configparser.ConfigParser`: Configured ConfigParser instance
    """
    # Create new configuration
    cfg = configparser.ConfigParser()

    # Populate with defaults
    for sec, kv in DEFAULTS.items():
        cfg[sec] = {}
        for k, v in kv.items():
            cfg[sec][k] = _to_str(v)

    # Apply language override if provided
    if override_language is not None:
        cfg.set('general', 'language', override_language)

    return cfg

def _sanitize_config(cfg: configparser.ConfigParser) -> bool:
    """Validate and correct configuration values.

    Ensures all sections and keys exist, normalizes boolean values,
    validates enum fields, and clamps numeric values to allowed ranges.
    Missing or invalid values are reset to defaults.

    **Parameters:**
        `cfg` (configparser.ConfigParser): Configuration to sanitize

    **Returns:**
        `bool`: True if changes were made, False otherwise
    """
    changed = False

    # Ensure all sections and default keys exist
    for sec, kv in DEFAULTS.items():
        for key, default_val in kv.items():
            if not cfg.has_section(sec):
                cfg.add_section(sec)
                changed = True
            if not cfg.has_option(sec, key):
                cfg.set(sec, key, _to_str(default_val))
                changed = True

    # Normalize boolean values
    for (sec, key) in BOOL_KEYS:
        raw = cfg.get(sec, key, fallback=None)
        parsed = _parse_bool(raw) if raw is not None else None
        if parsed is None:
            parsed = DEFAULTS[sec][key]
        if raw != _to_str(parsed):
            cfg.set(sec, key, _to_str(parsed))
            changed = True

    # Validate enum fields
    for sec, keys in ALLOWED.items():
        for key, allowed in keys.items():
            val = cfg.get(sec, key, fallback=None)
            if val not in allowed:
                cfg.set(sec, key, _to_str(DEFAULTS[sec][key]))
                changed = True

    # Validate numeric ranges
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

def _detect_system_language() -> str:
    """Detect system language.

    Attempts to detect system language using Qt's locale system.
    Falls back to English if detection is unreliable or fails.

    **Returns:**
        `str`: Detected language code ('de' or 'en')
    """
    try:
        bcp47 = QLocale.system().bcp47Name().lower()
        # Only return 'de' if we're very confident it's a German system
        if bcp47.startswith('de') or bcp47 == 'de':
            return 'de'
    except Exception:
        pass
    
    # Default to English for reliability
    return 'en'

def _to_str(v) -> str:
    """Convert value to string representation.

    Converts booleans to 'True'/'False', other types to string.

    **Parameters:**
        `v` (Any): Value to convert

    **Returns:**
        `str`: String representation
    """
    if isinstance(v, bool):
        return 'True' if v else 'False'
    return str(v)

def _parse_bool(s: str) -> bool | None:
    """Parse string to boolean.

    Accepts various boolean representations (true/false, 1/0, yes/no).

    **Parameters:**
        `s` (str): String to parse

    **Returns:**
        `bool | None`: Parsed boolean or None if invalid
    """
    if s is None:
        return None

    low = s.strip().lower()
    if low in {'true', '1', 'yes', 'y', 'on'}:
        return True
    if low in {'false', '0', 'no', 'n', 'off'}:
        return False
    return None

def _save_config(cfg: configparser.ConfigParser) -> None:
    """Safely save configuration to file.

    Creates directory if needed and handles file operation errors.

    **Parameters:**
        `cfg` (configparser.ConfigParser): Configuration to save

    **Returns:**
        `None`

    **Raises:**
        `RuntimeError`: If configuration cannot be saved
    """
    try:
        # Ensure directory exists
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        # Write configuration file
        with CONFIG_FILE.open('w', encoding='utf-8') as f:
            cfg.write(f)
    except (OSError, IOError) as e:
        raise RuntimeError(f"Failed to save configuration: {e}") from e
