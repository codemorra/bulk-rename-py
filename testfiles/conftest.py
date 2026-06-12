# -*- coding: utf-8 -*-
"""Pytest configuration and fixtures for Bulk Rename Py tests."""

import pytest
from pathlib import Path
import sys
import os

# Add src to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


@pytest.fixture
def tmp_test_dir(tmp_path):
    """Create a temporary test directory for file operations."""
    return tmp_path


@pytest.fixture
def sample_files(tmp_test_dir):
    """Create sample test files for renaming tests."""
    files = ["test1.txt", "test2.txt", "test3.txt"]
    paths = []
    for filename in files:
        filepath = tmp_test_dir / filename
        filepath.write_text(f"Content for {filename}")
        paths.append(filepath)
    return paths


@pytest.fixture
def duplicate_files(tmp_test_dir):
    """Create files that would result in duplicates when renamed."""
    files = ["file_copy.txt", "file_backup.txt", "file_original.txt"]
    paths = []
    for filename in files:
        filepath = tmp_test_dir / filename
        filepath.write_text(f"Content for {filename}")
        paths.append(filepath)
    return paths


@pytest.fixture
def special_char_files(tmp_test_dir):
    """Create files with special characters for sanitization testing."""
    files = [
        "test<file>.txt",
        "document:report.pdf", 
        "image|photo.jpg"
    ]
    paths = []
    for filename in files:
        try:
            filepath = tmp_test_dir / filename
            filepath.write_text(f"Content for {filename}")
            paths.append(filepath)
        except (OSError, ValueError):
            # Skip files that can't be created on this system
            continue
    return paths


@pytest.fixture
def basic_rename_config():
    """Create a basic rename configuration."""
    from modules.core.types import RenameCfg, DateTimeCfg, CounterCfg, MaskCfg, CaseCfg, ReplaceCfg
    
    return RenameCfg(
        mask=MaskCfg(name_mask="{name}_{counter}", ext_mask="{ext}"),
        dt=DateTimeCfg(
            date_format="YYYYMMDD",
            date_sep="none",
            time_format="HHMMSS",
            time_sep="none",
            date_type="current"
        ),
        counter=CounterCfg(start=1, step=1, digits=3, dupes_only=False),
        repl=ReplaceCfg(pattern="", replace="", regex=False, exact=False, case_sensitive=False, first_only=False, exclude_extension=False),
        case=CaseCfg(mode="unchanged", windows_names=False)
    )


@pytest.fixture
def duplicate_config():
    """Create configuration for duplicate handling tests."""
    from modules.core.types import RenameCfg, DateTimeCfg, CounterCfg, MaskCfg, CaseCfg, ReplaceCfg
    
    return RenameCfg(
        mask=MaskCfg(name_mask="file", ext_mask="{ext}"),
        dt=DateTimeCfg(
            date_format="YYYYMMDD",
            date_sep="none",
            time_format="HHMMSS",
            time_sep="none",
            date_type="current"
        ),
        counter=CounterCfg(start=1, step=1, digits=2, dupes_only=True),
        repl=None,
        case=CaseCfg(mode="unchanged", windows_names=False)
    )