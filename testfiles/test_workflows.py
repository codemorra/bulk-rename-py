# -*- coding: utf-8 -*-
"""Integration tests for complete rename workflows."""

import pytest
from pathlib import Path
from modules.core.renamer import Renamer
from modules.core.validation import Validator
from modules.core.types import RenameCfg, DateTimeCfg, CounterCfg, MaskCfg, CaseCfg, ReplaceCfg


class TestIntegration:
    """Integration tests for complete rename workflows."""
    
    def test_full_rename_workflow(self, tmp_test_dir):
        """Test complete rename workflow with sample files."""
        # Create test files
        sample_files = ["file1.txt", "file2.txt", "file3.txt"]
        paths = []
        for filename in sample_files:
            filepath = tmp_test_dir / filename
            filepath.write_text(f"Content for {filename}")
            paths.append(filepath)
        
        # Create configuration
        cfg = RenameCfg(
            mask=MaskCfg(name_mask="document_{counter}", ext_mask="{ext}"),
            dt=DateTimeCfg(
                date_format="YYYYMMDD",
                date_sep="none",
                time_format="HHMMSS",
                time_sep="none",
                date_type="current"
            ),
            counter=CounterCfg(start=1, step=1, digits=2, dupes_only=False),
            repl=ReplaceCfg(pattern="", replace="", regex=False, exact=False, case_sensitive=False, first_only=False, exclude_extension=False),
            case=CaseCfg(mode="lowercase", windows_names=False)
        )
        
        # Generate preview names
        preview_names = Renamer.preview_names(paths, cfg)
        
        # Plan moves
        moves = Renamer.plan_moves(paths, preview_names)
        
        # Check for conflicts
        conflicts = Validator.check_conflicts(moves)
        assert len(conflicts) == 0
        
        # Execute rename
        errors = Renamer.perform_rename(moves)
        assert len(errors) == 0
        
        # Verify files were renamed
        expected_files = ["document_01.txt", "document_02.txt", "document_03.txt"]
        for expected_file in expected_files:
            assert (tmp_test_dir / expected_file).exists()
        
        # Undo the rename
        missing, undo_errors = Renamer.undo_moves(moves)
        assert len(undo_errors) == 0
        assert len(missing) == 0
        
        # Verify original files are restored
        for original_file in sample_files:
            assert (tmp_test_dir / original_file).exists()
    
    def test_special_character_sanitization_workflow(self, tmp_test_dir):
        """Test complete workflow with special character sanitization."""
        # Create file with special characters (if system allows)
        original_name = "test<file>:special.txt"
        try:
            filepath = tmp_test_dir / original_name
            filepath.write_text("Content with special characters")
        except (OSError, ValueError):
            pytest.skip("Cannot create files with special characters on this system")
        
        # Create configuration with Windows-safe names
        cfg = RenameCfg(
            mask=MaskCfg(name_mask="{name}_clean", ext_mask="{ext}"),
            dt=DateTimeCfg(
                date_format="YYYYMMDD",
                date_sep="none",
                time_format="HHMMSS",
                time_sep="none",
                date_type="current"
            ),
            counter=CounterCfg(start=1, step=1, digits=2, dupes_only=False),
            repl=None,
            case=CaseCfg(mode="unchanged", windows_names=True)
        )
        
        # Generate preview name
        preview_names = Renamer.preview_names([filepath], cfg)
        
        # Verify sanitization
        assert "<" not in preview_names[0]
        assert ":" not in preview_names[0]
        
        # Execute rename
        moves = Renamer.plan_moves([filepath], preview_names)
        errors = Renamer.perform_rename(moves)
        
        assert len(errors) == 0
        
        # Verify sanitized file exists
        sanitized_path = tmp_test_dir / preview_names[0]
        assert sanitized_path.exists()
        assert sanitized_path.read_text() == "Content with special characters"
    
    def test_large_batch_rename(self, tmp_test_dir):
        """Test renaming of a large number of files."""
        # Create many test files
        num_files = 50
        paths = []
        for i in range(num_files):
            filename = f"file_{i:03d}.txt"
            filepath = tmp_test_dir / filename
            filepath.write_text(f"Content for file {i}")
            paths.append(filepath)
        
        # Create configuration
        cfg = RenameCfg(
            mask=MaskCfg(name_mask="doc_{counter}", ext_mask="{ext}"),
            dt=DateTimeCfg(
                date_format="YYYYMMDD",
                date_sep="none",
                time_format="HHMMSS",
                time_sep="none",
                date_type="current"
            ),
            counter=CounterCfg(start=100, step=1, digits=3, dupes_only=False),
            repl=None,
            case=CaseCfg(mode="uppercase", windows_names=False)
        )
        
        # Generate preview names
        preview_names = Renamer.preview_names(paths, cfg)
        
        # Verify all names are unique
        assert len(set(preview_names)) == len(preview_names)
        
        # Execute rename
        moves = Renamer.plan_moves(paths, preview_names)
        errors = Renamer.perform_rename(moves)
        
        assert len(errors) == 0
        
        # Verify all files were renamed
        for i, expected_name in enumerate(preview_names):
            expected_path = tmp_test_dir / expected_name
            assert expected_path.exists()
            assert expected_path.read_text() == f"Content for file {i}"
    
    def test_complex_token_workflow(self, tmp_test_dir):
        """Test workflow with complex token patterns."""
        # Create test file
        filepath = tmp_test_dir / "test_image.jpg"
        filepath.write_text("Test image content")
        
        # Create configuration with complex tokens
        cfg = RenameCfg(
            mask=MaskCfg(
                name_mask="{name1-4}_{counter}_{date}", 
                ext_mask="{ext}"
            ),
            dt=DateTimeCfg(
                date_format="YYYYMMDD",
                date_sep="-",
                time_format="HHMMSS",
                time_sep="none",
                date_type="current"
            ),
            counter=CounterCfg(start=1, step=1, digits=2, dupes_only=False),
            repl=None,
            case=CaseCfg(mode="heading", windows_names=False)
        )
        
        # Generate preview name
        preview_names = Renamer.preview_names([filepath], cfg)
        
        # Verify token processing
        preview_name = preview_names[0]
        assert "Test_" in preview_name  # {name1-4} with heading case
        assert "_01_" in preview_name  # {counter}
        assert "_" in preview_name and len(preview_name.split("_")) >= 3  # Should have multiple parts
        
        # Execute rename
        moves = Renamer.plan_moves([filepath], preview_names)
        errors = Renamer.perform_rename(moves)
        
        assert len(errors) == 0
        
        # Verify renamed file exists
        renamed_path = tmp_test_dir / preview_name
        assert renamed_path.exists()
        assert renamed_path.read_text() == "Test image content"