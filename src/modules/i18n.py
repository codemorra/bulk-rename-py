# -*- coding: utf-8 -*-

# Bulk Rename Py
# © 2026–present Codemorra (Christopher Kranz)
# Licensed under the MIT License (see LICENSE file)

"""Internationalization (i18n) module for Bulk Rename Py.

Provides translation functionality using JSON language files.
Supports nested translation keys with dot notation.
"""

from __future__ import annotations
import json
from pathlib import Path


# Path to directory containing language JSON files
LOCALE_DIR = Path(__file__).parent.parent / 'locale'


class Translator:
    """Translation management and access.

    Provides simple translation functions via dot notation,
    e.g., `translator.t("sections.import.title")`.
    """
    def __init__(self, lang_code: str) -> None:
        """Initialize translator with specified language.

        **Parameters:**
            `lang_code` (str): Language code (e.g., 'de', 'en')

        **Returns:**
            `None`
        """
        self.lang_code = lang_code
        self.lang = self._load_language(lang_code)

    def _load_language(self, lang_code: str) -> dict:
        """Load language file from disk.

        **Parameters:**
            `lang_code` (str): Language code to load

        **Returns:**
            `dict`: Loaded language dictionary

        **Raises:**
            `FileNotFoundError`: If language file doesn't exist
        """
        lang_file = LOCALE_DIR / f'{lang_code}.json'

        if not lang_file.exists():
            raise FileNotFoundError(f'Language file not found: {lang_file}')

        with lang_file.open('r', encoding='utf-8') as f:
            return json.load(f)

    def t(self, key: str) -> str:
        """Get translation for specified key.

        Uses dot notation to traverse nested dictionaries.
        Returns key in brackets if not found.

        **Parameters:**
            `key` (str): Dot-separated translation key

        **Returns:**
            `str`: Translated string or [key] if not found

        **Example:**
            `t("sections.import.title")` → "File Import"
        """
        data = self.lang

        # Traverse nested keys using dot notation
        for part in key.split('.'):
            if isinstance(data, dict):
                data = data.get(part, f'[{part}]')
            else:
                return f'[{key}]'

        # Ensure final value is a string
        if isinstance(data, str):
            return data
        return f'[{key}]'

    def switch_language(self, lang_code: str) -> None:
        """Switch to different language.

        **Parameters:**
            `lang_code` (str): New language code

        **Returns:**
            `None`
        """
        self.lang_code = lang_code
        self.lang = self._load_language(lang_code)
