# -*- coding: utf-8 -*-
"""Edge case tests for Bulk Rename Py."""

import pytest
from pathlib import Path
from modules.core.renamer import Renamer
from modules.core.validation import Validator
from modules.core.types import RenameCfg, DateTimeCfg, CounterCfg, MaskCfg, CaseCfg, ReplaceCfg
from modules.core.tokens import TokenProcessor


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_file_list(self):
        """Test behavior with empty file list."""
        cfg = RenameCfg(
            mask=MaskCfg(name_mask="{name}", ext_mask="{ext}"),
            dt=DateTimeCfg(
                date_format="YYYYMMDD",
                date_sep="none",
                time_format="HHMMSS",
                time_sep="none",
                date_type="current"
            ),
            counter=CounterCfg(start=1, step=1, digits=2, dupes_only=False),
            repl=None,
            case=CaseCfg(mode="unchanged", windows_names=False)
        )
        
        # Should handle empty list gracefully
        result = Renamer.preview_names([], cfg)
        assert result == []
    
    def test_mismatched_lengths_in_plan_moves(self):
        """Test error handling for mismatched path/name lengths."""
        paths = [Path("file1.txt"), Path("file2.txt")]
        new_names = ["new1.txt"]  # Mismatched length
        
        with pytest.raises(ValueError):
            Renamer.plan_moves(paths, new_names)
    
    def test_invalid_token_patterns(self):
        """Test handling of invalid token patterns."""
        mask = "{invalid_token}"
        result = TokenProcessor.apply_name_mask(
            mask, "test", "txt", "001", "20240101", "120000", None, "current"
        )
        
        # Should return original token if invalid
        assert "{invalid_token}" in result
    
    def test_very_long_filenames(self, tmp_test_dir):
        """Test handling of very long filenames."""
        # Create a file with a very long name
        long_name = "a" * 300 + ".txt"
        try:
            filepath = tmp_test_dir / long_name
            filepath.write_text("test")
        except (OSError, ValueError):
            pytest.skip("Cannot create very long filenames on this system")
        
        # Test validation
        # Should fail Windows validation (MAX_PATH = 260)
        assert not Validator.validate_path_length(tmp_test_dir, long_name, platform="windows")
        
        # Test sanitization
        sanitized = Validator.sanitize_filename(long_name)
        assert len(sanitized) > 0