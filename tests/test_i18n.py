"""Tests for consistent translation fallback and failed language changes."""

import pytest

from modules.i18n import Translator


@pytest.mark.parametrize('key', ['missing', 'messages.missing', 'messages.errors.missing', 'app.child'])
def test_missing_keys_use_complete_key(key):
    """Test the documented fallback for missing keys at every nesting level."""
    translator = Translator('en')

    assert translator.t(key) == f'[{key}]'


def test_failed_language_change_keeps_previous_state():
    """Test that missing language files cannot leave the code and translations inconsistent."""
    translator = Translator('en')
    previous = translator.lang

    with pytest.raises(FileNotFoundError):
        translator.switch_language('missing')

    assert translator.lang_code == 'en'
    assert translator.lang is previous
