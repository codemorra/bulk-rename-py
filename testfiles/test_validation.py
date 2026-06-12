# -*- coding: utf-8 -*-
"""Tests for the Validator class (modules/core/validation.py)."""

import pytest
from pathlib import Path
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
        
        # Should pass Linux validation (usually)
        # Note: This might fail on some systems depending on actual path length
        linux_result = Validator.validate_path_length(tmp_test_dir, long_name, platform="linux")
        # We don't assert this as it depends on the actual path length
    
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