"""Regression tests for confirmed rename and validation issues."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from modules.core.renamer import Renamer
from modules.core.types import ReplaceCfg
from modules.core.validation import Validator
from modules.gui.rename_manager import RenameManager


class TestRenameSafety:
    """Test preservation of file contents during rename and undo."""

    def test_existing_destination_preserves_contents(self, tmp_path):
        """Test that an occupied destination is rejected without data loss."""
        src = tmp_path / "source.txt"
        dst = tmp_path / "destination.txt"
        src.write_text("source content", encoding="utf-8")
        dst.write_text("destination content", encoding="utf-8")

        result = Renamer.perform_rename([(src, dst)])

        assert dst.read_text(encoding="utf-8") == "destination content"
        assert src.read_text(encoding="utf-8") == "source content"
        assert result.errors

    def test_name_swap_preserves_contents(self, tmp_path):
        """Test that swapping names preserves both files and supports undo."""
        first = tmp_path / "first.txt"
        second = tmp_path / "second.txt"
        first.write_text("first content", encoding="utf-8")
        second.write_text("second content", encoding="utf-8")
        moves = [(first, second), (second, first)]

        result = Renamer.perform_rename(moves)

        assert not result.errors
        assert not result.missing
        assert first.read_text(encoding="utf-8") == "second content"
        assert second.read_text(encoding="utf-8") == "first content"

        result = Renamer.undo_moves(moves)

        assert not result.errors
        assert not result.missing
        assert first.read_text(encoding="utf-8") == "first content"
        assert second.read_text(encoding="utf-8") == "second content"

    def test_undo_preserves_new_file_at_original_path(self, tmp_path):
        """Test that undo preserves files created after the rename."""
        src = tmp_path / "source.txt"
        dst = tmp_path / "destination.txt"
        src.write_text("original content", encoding="utf-8")
        assert not Renamer.perform_rename([(src, dst)]).errors
        src.write_text("new content", encoding="utf-8")

        result = Renamer.undo_moves([(src, dst)])

        assert src.read_text(encoding="utf-8") == "new content"
        assert dst.read_text(encoding="utf-8") == "original content"
        assert not result.missing
        assert result.errors


class TestNameGeneration:
    """Test configuration options affecting generated destination names."""

    def test_duplicates_after_case_transform(self, basic_rename_config):
        """Test duplicate numbering after converting names to lowercase."""
        cfg = basic_rename_config
        cfg.mask.name_mask = "{name}{counter}"
        cfg.counter.dupes_only = True
        cfg.case.mode = "lowercase"

        names = Renamer.preview_names([Path("A.txt"), Path("a.txt")], cfg)

        assert names == ["a001.txt", "a002.txt"]

    def test_regex_case_insensitive(self, basic_rename_config):
        """Test case-insensitive replacement in regex mode."""
        cfg = basic_rename_config
        cfg.mask.name_mask = "{name}"
        cfg.repl = ReplaceCfg(
            pattern="abc", replace="changed", regex=True, exact=False,
            case_sensitive=False, exclude_extension=True, first_only=False
        )

        assert Renamer.preview_names([Path("ABC.txt")], cfg) == ["changed.txt"]


class TestFilenameValidation:
    """Test invalid filename components before move planning."""

    @pytest.mark.parametrize("name", ['a"b.txt', "name.", "name.txt ", "a\x01.txt"])
    def test_invalid_windows_names(self, name):
        """Test rejection of invalid Windows filename characters and endings."""
        assert not Validator.validate_filename(name, windows_safe=True)

    @pytest.mark.parametrize("name", [".", "..", "a/b"])
    def test_invalid_unix_names(self, name):
        """Test rejection of names that are not individual file components."""
        assert not Validator.validate_filename(name)


class TestGUIValidation:
    """Test preflight validation without opening application dialogs."""

    def test_windows_preflight_valid_name(self, tmp_path):
        """Test that Windows preflight accepts a valid short filename."""
        manager = RenameManager.__new__(RenameManager)
        manager.helpers = SimpleNamespace(is_windows=lambda: True)

        assert manager._validate_name_length(tmp_path, "valid.txt")
