# -*- coding: utf-8 -*-

# Bulk Rename Py
# © 2026–present Codemorra
# Licensed under the MIT License (see LICENSE file)

"""
Translation module (i18n) for Bulk Rename Py.

Loads language files in JSON format and provides translation strings
that can be retrieved using dot notation (e.g., “sections.import.title”).
"""

from __future__ import annotations
import json
from pathlib import Path


LOCALE_DIR = Path(__file__).parent.parent / 'locale'


class Translator:
    """
    Management and access to language strings.

    Provides simple translation functions via dot notation,
    e.g., `translator.t(“sections.import.title”)`.
    """
    def __init__(self, lang_code: str) -> None:
        """
        Initializes the translator with the specified language.

        **Returns:**
            `None`
        """
        self.lang_code = lang_code
        self.lang = self._load_language(lang_code)

    def _load_language(self, lang_code: str) -> dict:
        """
        Initializes the translator with the specified language.

        **Parameters:**
            `lang_code` (str): Language code of the language to be loaded (e.g., “de,” “en”)

        **Returns:**
            `None`
        """
        lang_file = LOCALE_DIR / f'{lang_code}.json'

        if not lang_file.exists():
            raise FileNotFoundError(f'Language file not found: {lang_file}')

        with lang_file.open('r', encoding='utf-8') as f:
            return json.load(f)

    def t(self, key: str) -> str:
        """
        Returns the translation string for the specified dot path.

        Example:
        `t(“sections.import.title”)` -> “File Import”

        **Parameters:**
            `key` (str): Key path separated by periods in the language file

        **Returns:**
            `str`: Translation string found or `[key]` if not found
        """
        data = self.lang

        # resolve nested key via dot-notation, fallback to [key] if missing
        for part in key.split('.'):
            if isinstance(data, dict):
                data = data.get(part, f'[{part}]')
            else:
                return f'[{key}]'

        # ensure final value is a string
        if isinstance(data, str):
            return data
        return f'[{key}]'

    def switch_language(self, lang_code: str) -> None:
        """
        Changes the active language and reloads the corresponding language file.

        **Parameters:**
            `lang_code` (str): New language code (e.g., “de,” “en”)

        **Returns:**
            `None`
        """
        self.lang_code = lang_code
        self.lang = self._load_language(lang_code)
