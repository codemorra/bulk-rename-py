# -*- coding: utf-8 -*-
"""Tests for the TokenProcessor class (modules/core/tokens.py)."""

import pytest
from modules.core.tokens import TokenProcessor


class TestTokenProcessor:
    """Test cases for TokenProcessor."""
    
    def test_basic_token_replacement(self):
        """Test basic token replacement."""
        mask = "{name}_{counter}.{ext}"
        result = TokenProcessor.apply_name_mask(
            mask, "testfile", "txt", "001", "20240101", "120000", None, "current"
        )
        assert result == "testfile_001.txt"
    
    def test_token_slicing(self):
        """Test token slicing functionality."""
        mask = "{name1-3}_{ext1-2}"
        result = TokenProcessor.apply_name_mask(
            mask, "testfile", "txt", "001", "20240101", "120000", None, "current"
        )
        assert result == "tes_tx"
    
    def test_case_transformations(self):
        """Test case transformation methods."""
        test_cases = [
            ("TestFile", "lowercase", "testfile"),
            ("TestFile", "uppercase", "TESTFILE"),
            ("test file", "heading", "Test file"),
            ("hello", "mocking", "HeLlO"),
        ]
        
        for text, mode, expected in test_cases:
            result = TokenProcessor.apply_case_transform(text, mode)
            assert result == expected