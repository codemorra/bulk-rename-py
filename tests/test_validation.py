"""Tests for the Validator class (modules/core/validation.py)."""

from pathlib import Path

import pytest

from modules.core.renamer import Renamer
from modules.core.validation import Validator


class TestValidator:
    """Test cases for Validator class."""
    
    def test_windows_sanitization(self):
        """Test Windows filename sanitization."""
        invalid_name = "test<file>:special.txt"
        sanitized = Validator.sanitize_filename(invalid_name, windows_safe=True)
        
        assert "<" not in sanitized
        assert ":" not in sanitized
        assert sanitized != ""
    
    def test_reserved_names(self):
        """Test handling of Windows reserved names."""
        reserved = "CON.txt"
        sanitized = Validator.sanitize_filename(reserved, windows_safe=True)
        
        assert sanitized.startswith("_")
        assert Validator.validate_filename(reserved, windows_safe=True) == False
    
    def test_path_length_validation(self, tmp_test_dir):
        """Test path length validation."""
        # Create a very long filename
        long_name = "a" * 300 + ".txt"
        
        # Should fail Windows validation
        assert Validator.validate_path_length(tmp_test_dir, long_name, platform="windows") == False
        
        # Should fail Linux validation because the filename exceeds 255 bytes
        assert not Validator.validate_path_length(tmp_test_dir, long_name, platform="linux")
    
    def test_conflict_detection(self):
        """Test conflict detection in rename operations."""
        # Create moves that would cause conflicts
        moves = [
            (Path("file1.txt"), Path("result.txt")),
            (Path("file2.txt"), Path("result.txt")),  # Conflict!
        ]
        
        conflicts = Validator.check_conflicts(moves)
        assert len(conflicts) == 1
        assert "Conflict" in conflicts[0]

    @pytest.mark.parametrize('name', [
        '', ' ', '.', '..', 'a/b', 'a\x00b',
        'a"b', 'a<b', 'a>b', 'a:b', 'a\\b', 'a|b', 'a?b', 'a*b',
        'a\x01b', 'a\x1fb', 'name.', 'name ',
        'CON.txt', 'con', 'NUL', 'COM1', 'LPT9.log', 'COM¹.txt', 'LPT²', 'CON .txt',
    ])
    def test_invalid_windows_filename_components(self, name):
        """Test Windows character, device-name, and filename component restrictions."""
        assert not Validator.validate_filename(name, windows_safe=True)

    @pytest.mark.parametrize('name', ["O'Brien.txt", '.hidden', '_CON.txt', 'COM10.txt', 'a b.txt', 'ä.txt'])
    def test_valid_windows_filename_components(self, name):
        """Test that valid apostrophes, Unicode, and device-like names are retained."""
        assert Validator.validate_filename(name, windows_safe=True)
        assert Validator.sanitize_filename(name, windows_safe=True) == name

    @pytest.mark.parametrize('original, expected', [
        ('a"b.txt', 'a_b.txt'), ('a\x01b.txt', 'a_b.txt'),
        ('CON .txt', '_CON .txt'), ('COM¹.txt', '_COM¹.txt'),
        ('name.txt. ', 'name.txt'), ('..', '_'), ('\x00', '_'),
    ])
    def test_windows_sanitization_produces_valid_names(self, original, expected):
        """Test sanitization of complete Windows filenames and invalid endings."""
        result = Validator.sanitize_filename(original, windows_safe=True)

        assert result == expected
        assert Validator.validate_filename(result, windows_safe=True)

    def test_unix_sanitization_preserves_filename_spaces(self):
        """Test that valid leading and trailing Unix filename spaces are preserved."""
        name = ' a.txt '

        assert Validator.sanitize_filename(name, linux_safe=True) == name
        assert Validator.validate_filename(name)

    @pytest.mark.parametrize('name', ['', ' ', '.', '..', 'a/b', 'a\x00b'])
    def test_invalid_names_are_rejected_during_planning(self, tmp_path, name):
        """Test validation before constructing destination paths or moving files."""
        with pytest.raises(ValueError, match='Invalid destination filename'):
            Renamer.plan_moves([tmp_path / 'source.txt'], [name])

    def test_optional_windows_rules_are_enforced_during_planning(self, tmp_path):
        """Test Windows compatibility checks independently of the host platform."""
        with pytest.raises(ValueError, match='Invalid destination filename'):
            Renamer.plan_moves([tmp_path / 'source.txt'], ['CON.txt'], windows_safe=True)

    @pytest.mark.parametrize('name, valid', [('a' * 255, True), ('a' * 256, False),
                                            ('ä' * 127 + 'a', True), ('ä' * 128, False)])
    def test_linux_filename_byte_limit(self, tmp_path, name, valid):
        """Test the 255-byte component boundary with ASCII and multibyte text."""
        assert Validator.validate_path_length(tmp_path, name, platform='linux') is valid

    def test_windows_utf16_component_limit(self):
        """Test UTF-16 units for Unicode characters represented by surrogate pairs."""
        root = Path('/').absolute()

        assert Validator.validate_path_length(root, '😀' * 127, platform='windows')
        assert not Validator.validate_path_length(root, '😀' * 128, platform='windows')

    def test_windows_path_limit_includes_terminating_null(self):
        """Test that a path must leave one UTF-16 unit for its terminating null."""
        base = Path('/base').absolute()
        name = 'a' * (259 - len(str(base)) - 1)

        assert Validator.validate_path_length(base, name, platform='windows')
        assert not Validator.validate_path_length(base, name + 'a', platform='windows')
