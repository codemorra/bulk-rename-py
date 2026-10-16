"""Edge case tests for Bulk Rename Py."""

from pathlib import Path

import pytest

from modules.core.renamer import Renamer
from modules.core.tokens import TokenProcessor
from modules.core.types import (
    CaseCfg,
    CounterCfg,
    DateTimeCfg,
    MaskCfg,
    RenameCfg,
)


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
        """Test rejection of very long filenames before filesystem operations."""
        long_name = "a" * 300 + ".txt"
        source = tmp_test_dir / 'source.txt'

        with pytest.raises(ValueError, match='Destination name or path is too long'):
            Renamer.plan_moves([source], [long_name])
