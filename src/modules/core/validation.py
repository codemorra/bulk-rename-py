# -*- coding: utf-8 -*-

# Bulk Rename Py
# © 2026–present Codemorra (Christopher Kranz)
# Licensed under the MIT License (see LICENSE file)

"""Filename validation and sanitization.

Provides platform-specific validation and sanitization functions
to ensure filenames comply with operating system requirements.
"""

import re
import os
from pathlib import Path
from typing import Tuple


# Constants
ILLEGAL_WIN_CHARS = set("<>:'/\\|?*")
RESERVED_WIN_NAMES = {
    'CON', 'PRN', 'AUX', 'NUL',
    *{f'COM{i}' for i in range(1, 10)},
    *{f'LPT{i}' for i in range(1, 10)},
}


class Validator:
    """Filename validation and sanitization operations.

    Provides platform-specific validation and sanitization for filenames.

    All methods are static as no instance state is required.
    """


######################
# MAIN FUNCTIONALITY #
######################
    @staticmethod
    def sanitize_filename(name: str, *, windows_safe: bool = False, linux_safe: bool = False) -> str:
        """Sanitize filename for platform compatibility.

        **Parameters:**
            `name` (str): Original filename
            `windows_safe` (bool): Enforce Windows rules
            `linux_safe` (bool): Replace '/' for Linux

        **Returns:**
            `str`: Sanitized filename

        **Behavior:**
            Windows: Replaces illegal chars, wraps reserved names
            Linux: Replaces '/' with Unicode fraction slash
            Always: Removes null bytes, handles empty names
        """
        # Replace illegal Windows characters with underscores
        if windows_safe:
            name = ''.join(ch if ch not in ILLEGAL_WIN_CHARS else '_' for ch in name)
            if Validator._is_reserved_win_name(name):
                name = f"_{name}"

        # Replace '/' with Unicode fraction slash for Linux compatibility
        if linux_safe:
            name = name.replace('/', '\u2044')

        # Remove null bytes and handle empty names
        name = name.strip().replace('\x00', '')
        if not name:
            name = '_'

        return name

    @staticmethod
    def validate_filename(name: str, *, windows_safe: bool = False) -> bool:
        """Validate filename content for platform compatibility.

        **Parameters:**
            `name` (str): Filename to validate
            `windows_safe` (bool): Apply Windows validation rules

        **Returns:**
            `bool`: True if valid
        """
        if not name or name.isspace():
            return False

        if windows_safe:
            # Windows-specific validation (illegal chars, reserved names)
            if Validator._is_reserved_win_name(name):
                return False
            if Validator._contains_illegal_win_chars(name):
                return False
        else:
            # Linux/Unix: only null byte is forbidden
            if '\x00' in name:
                return False

        return True

    @staticmethod
    def validate_path_length(base_dir: Path, name: str, *, platform: str = 'auto') -> bool:
        """Validate path length for platform limits.

        **Parameters:**
            `base_dir` (Path): Base directory
            `name` (str): Filename
            `platform` (str): Target platform (windows, linux, or auto)

        **Returns:**
            `bool`: True if within platform limits

        **Limits:**
            Windows: MAX_PATH=260 chars, NAME_MAX=255 chars
            Linux: PATH_MAX=4096 bytes, NAME_MAX=255 bytes
        """
        try:
            full_path = base_dir / name

            # Auto-detect platform if not specified
            if platform == 'auto':
                platform = 'windows' if os.name == 'nt' else 'linux'

            # Windows path length validation (character count)
            if platform == 'windows':
                if len(str(full_path)) > 260:
                    return False
                if len(name) > 255:
                    return False
                return True

            # Linux path length validation (byte count with UTF-8 encoding)
            elif platform == 'linux':
                try:
                    name_bytes = len(name.encode('utf-8'))
                    path_bytes = len(str(full_path).encode('utf-8'))

                    if name_bytes > 255:
                        return False
                    if path_bytes > 4096:
                        return False
                    return True
                except UnicodeEncodeError:
                    return False

            return False
        except (OSError, UnicodeEncodeError, ValueError):
            # Handle any path construction or encoding errors
            return False

    @staticmethod
    def check_conflicts(moves: List[Tuple[Path, Path]]) -> List[str]:
        """Check for naming conflicts in planned rename operations.

        Identifies cases where multiple source files would be renamed to
        the same destination filename, which would cause data loss.

        **Parameters:**
            `moves` (List[Tuple[Path, Path]]): List of planned (source, destination) pairs

        **Returns:**
            `List[str]`: List of conflict descriptions (empty if no conflicts)
        """
        conflicts = []
        seen = {}

        for src, dst in moves:
            dst_str = str(dst)
            if dst_str in seen:
                conflicts.append(f"Conflict: {dst_str} (from {seen[dst_str]}) and {src}")
            else:
                seen[dst_str] = src

        return conflicts


################################################
# HELPER METHODS - Windows-specific validation #
################################################
    @staticmethod
    def _is_reserved_win_name(name: str) -> bool:
        """Check if filename is Windows reserved name.

        **Parameters:**
            `name` (str): Filename to check

        **Returns:**
            `bool`: True if reserved name
        """
        # Extract base name (remove extension) and convert to uppercase for comparison
        base = name.upper()
        if '.' in base:
            base = base.split('.')[0]
        return base in RESERVED_WIN_NAMES

    @staticmethod
    def _contains_illegal_win_chars(name: str) -> bool:
        """Check for illegal Windows characters.

        **Parameters:**
            `name` (str): Filename to check

        **Returns:**
            `bool`: True if contains illegal characters
        """
        return any(ch in ILLEGAL_WIN_CHARS for ch in name)
