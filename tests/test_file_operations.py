"""Tests for safe file renames, rollback, and recovery locations."""

import os

import pytest

from modules.core.file_operations import MoveExecutor
from modules.core.renamer import Renamer
from modules.core.validation import Validator


@pytest.fixture
def source_files(tmp_path):
    """Create three files with distinct contents for rename and rollback tests."""
    paths = [tmp_path / name for name in ('a.txt', 'b.txt', 'c.txt')]
    for index, path in enumerate(paths):
        path.write_text(f'content {index}', encoding='utf-8')
    return paths


class TestMoveExecution:
    """Test file preservation and source-destination dependencies."""

    def test_rename_chain_and_undo(self, source_files, tmp_path):
        """Test that a chain preserves file contents independent of move order."""
        a, b, c = source_files
        moves = [(a, b), (b, c), (c, tmp_path / 'd.txt')]

        result = Renamer.perform_rename(moves)

        assert not result.errors
        assert not result.missing
        assert result.moves == moves
        for index, (_, dst) in enumerate(moves):
            assert dst.read_text(encoding='utf-8') == f'content {index}'
        assert not a.exists()

        undone = Renamer.undo_moves(result.moves)

        assert not undone.errors
        assert not undone.missing
        for index, src in enumerate(source_files):
            assert src.read_text(encoding='utf-8') == f'content {index}'
        assert not list(tmp_path.glob('.bulkrename-*'))

    def test_case_only_rename_and_undo(self, tmp_path):
        """Test that case-only renames are not treated as unchanged paths."""
        src = tmp_path / 'Mixed.txt'
        dst = tmp_path / 'mixed.txt'
        src.write_text('content', encoding='utf-8')

        result = Renamer.perform_rename([(src, dst)])

        assert not result.errors
        assert not result.missing
        assert [(str(a), str(b)) for a, b in result.moves] == [(str(src), str(dst))]
        assert [p.name for p in tmp_path.iterdir()] == ['mixed.txt']
        assert dst.read_text(encoding='utf-8') == 'content'

        result = Renamer.undo_moves(result.moves)

        assert not result.errors
        assert [p.name for p in tmp_path.iterdir()] == ['Mixed.txt']
        assert src.read_text(encoding='utf-8') == 'content'

    def test_duplicate_destinations_block_entire_batch(self, source_files, tmp_path):
        """Test that duplicate destinations are rejected before any files move."""
        a, b, _ = source_files
        dst = tmp_path / 'result.txt'

        result = Renamer.perform_rename([(a, dst), (b, dst)])

        assert result.errors
        assert not result.moves
        assert not dst.exists()
        assert a.read_text(encoding='utf-8') == 'content 0'
        assert b.read_text(encoding='utf-8') == 'content 1'

    def test_duplicate_sources_block_entire_batch(self, source_files, tmp_path):
        """Test that a source cannot appear in two rename operations."""
        a, _, _ = source_files

        result = Renamer.perform_rename([
            (a, tmp_path / 'first.txt'), (a, tmp_path / 'second.txt')
        ])

        assert result.errors
        assert not result.moves
        assert a.read_text(encoding='utf-8') == 'content 0'
        assert len(list(tmp_path.iterdir())) == 3

    def test_unchanged_destination_is_occupied(self, source_files):
        """Test that unchanged entries cannot be overwritten by another source."""
        a, b, _ = source_files
        moves = [(a, b), (b, b)]

        assert Validator.check_conflicts(moves)
        result = Renamer.perform_rename(moves)

        assert result.errors
        assert not result.moves
        assert a.read_text(encoding='utf-8') == 'content 0'
        assert b.read_text(encoding='utf-8') == 'content 1'

    def test_missing_source_blocks_entire_batch(self, source_files, tmp_path):
        """Test that missing sources are reported before existing sources move."""
        a, _, _ = source_files
        missing = tmp_path / 'missing.txt'

        result = Renamer.perform_rename([
            (a, tmp_path / 'renamed.txt'), (missing, tmp_path / 'other.txt')
        ])

        assert result.missing == [str(missing)]
        assert not result.moves
        assert a.read_text(encoding='utf-8') == 'content 0'
        assert len(list(tmp_path.iterdir())) == 3

    def test_missing_undo_source_blocks_entire_batch(self, source_files, tmp_path):
        """Test that undo leaves other files untouched when a source is missing."""
        a, b, _ = source_files
        moves = [(a, tmp_path / 'first.txt'), (b, tmp_path / 'second.txt')]
        assert not Renamer.perform_rename(moves).errors
        moves[1][1].unlink()

        result = Renamer.undo_moves(moves)

        assert result.missing == [str(moves[1][1])]
        assert not result.moves
        assert moves[0][1].read_text(encoding='utf-8') == 'content 0'
        assert not a.exists()

    def test_unchanged_paths_create_no_temporary_files(self, source_files, tmp_path):
        """Test that unchanged files do not appear as executed moves."""
        result = Renamer.perform_rename([(p, p) for p in source_files])

        assert not result.errors
        assert not result.missing
        assert not result.moves
        assert not list(tmp_path.glob('.bulkrename-*'))

    def test_directory_source_is_rejected(self, tmp_path):
        """Test that the file executor cannot move directories containing sources."""
        src = tmp_path / 'folder'
        src.mkdir()
        child = src / 'file.txt'
        child.write_text('content', encoding='utf-8')

        result = Renamer.perform_rename([(src, tmp_path / 'renamed')])

        assert result.errors
        assert not result.moves
        assert child.read_text(encoding='utf-8') == 'content'

    @pytest.mark.parametrize('duplicate', ['source', 'destination'])
    def test_directory_alias_does_not_hide_conflicts(
            self, source_files, tmp_path, duplicate):
        """Test duplicate detection through symlink aliases of the same directory."""
        a, b, _ = source_files
        alias = tmp_path / 'alias'
        try:
            alias.symlink_to(tmp_path, target_is_directory=True)
        except OSError:
            pytest.skip('Directory symlink creation is unavailable')
        if duplicate == 'source':
            moves = [(a, tmp_path / 'first.txt'), (alias / a.name, tmp_path / 'second.txt')]
        else:
            moves = [(a, tmp_path / 'first.txt'), (b, alias / 'first.txt')]

        result = Renamer.perform_rename(moves)

        assert result.errors
        assert not result.moves
        assert a.read_text(encoding='utf-8') == 'content 0'
        assert b.read_text(encoding='utf-8') == 'content 1'
        assert not list(tmp_path.glob('.bulkrename-*'))


class TestRollback:
    """Test failures during staging, destination assignment, and rollback."""

    @pytest.mark.parametrize('failure_step', range(1, 7))
    def test_cycle_is_restored_after_execution_failure(
            self, source_files, tmp_path, monkeypatch, failure_step):
        """Test rollback after each possible failing step in a three-file cycle."""
        a, b, c = source_files
        moves = [(a, b), (b, c), (c, a)]
        rename = MoveExecutor._rename_no_replace
        calls = 0

        def failing_rename(src, dst):
            nonlocal calls
            calls += 1
            if calls == failure_step:
                raise PermissionError('simulated rename failure')
            rename(src, dst)

        monkeypatch.setattr(MoveExecutor, '_rename_no_replace', failing_rename)

        result = Renamer.perform_rename(moves)

        assert result.errors
        assert not result.moves
        for index, src in enumerate(source_files):
            assert src.read_text(encoding='utf-8') == f'content {index}'
        assert len(list(tmp_path.iterdir())) == 3

    def test_destination_created_during_execution_is_preserved(
            self, source_files, tmp_path, monkeypatch):
        """Test atomic destination protection after preflight has already passed."""
        a, _, _ = source_files
        dst = tmp_path / 'new.txt'
        rename = MoveExecutor._rename_no_replace

        def racing_rename(src, target):
            if target == dst:
                dst.write_text('external content', encoding='utf-8')
            rename(src, target)

        monkeypatch.setattr(MoveExecutor, '_rename_no_replace', racing_rename)

        result = Renamer.perform_rename([(a, dst)])

        assert result.errors
        assert not result.moves
        assert dst.read_text(encoding='utf-8') == 'external content'
        assert a.read_text(encoding='utf-8') == 'content 0'
        assert not list(tmp_path.glob('.bulkrename-*'))

    def test_blocked_rollback_reports_recoverable_file(
            self, source_files, tmp_path, monkeypatch):
        """Test that a blocked restoration preserves and reports the staged file."""
        a, b, _ = source_files
        first = tmp_path / 'first.txt'
        second = tmp_path / 'second.txt'
        rename = MoveExecutor._rename_no_replace

        def failing_rename(src, dst):
            if dst == second:
                a.write_text('external content', encoding='utf-8')
                raise PermissionError('simulated destination failure')
            rename(src, dst)

        monkeypatch.setattr(MoveExecutor, '_rename_no_replace', failing_rename)

        result = Renamer.perform_rename([(a, first), (b, second)])

        assert result.errors
        assert len(result.moves) == 1
        original, current = result.moves[0]
        assert original == a
        assert current.name.startswith('.bulkrename-')
        assert current.read_text(encoding='utf-8') == 'content 0'
        assert a.read_text(encoding='utf-8') == 'external content'
        assert b.read_text(encoding='utf-8') == 'content 1'
        assert str(current) in '\n'.join(result.errors)

        # Remove the conflict and retry undo using the actual remaining location
        a.unlink()
        monkeypatch.setattr(MoveExecutor, '_rename_no_replace', rename)
        undone = Renamer.undo_moves(result.moves)

        assert not undone.errors
        assert not undone.missing
        assert a.read_text(encoding='utf-8') == 'content 0'
        assert not list(tmp_path.glob('.bulkrename-*'))

    def test_failed_rollback_staging_reports_final_location(
            self, source_files, tmp_path, monkeypatch):
        """Test recovery when a completed destination cannot be moved back."""
        a, b, _ = source_files
        first = tmp_path / 'first.txt'
        second = tmp_path / 'second.txt'
        rename = MoveExecutor._rename_no_replace

        def failing_rename(src, dst):
            if dst == second or src == first:
                raise PermissionError('simulated persistent move failure')
            rename(src, dst)

        monkeypatch.setattr(MoveExecutor, '_rename_no_replace', failing_rename)

        result = Renamer.perform_rename([(a, first), (b, second)])

        assert result.errors
        assert result.moves == [(a, first)]
        assert first.read_text(encoding='utf-8') == 'content 0'
        assert b.read_text(encoding='utf-8') == 'content 1'
        assert not a.exists()
        assert not list(tmp_path.glob('.bulkrename-*'))

        monkeypatch.setattr(MoveExecutor, '_rename_no_replace', rename)
        undone = Renamer.undo_moves(result.moves)

        assert not undone.errors
        assert not undone.missing
        assert a.read_text(encoding='utf-8') == 'content 0'

    def test_undo_destination_created_during_execution_is_preserved(
            self, source_files, tmp_path, monkeypatch):
        """Test atomic destination protection while undo is already running."""
        a, _, _ = source_files
        dst = tmp_path / 'renamed.txt'
        assert not Renamer.perform_rename([(a, dst)]).errors
        rename = MoveExecutor._rename_no_replace

        def racing_rename(src, target):
            if target == a:
                a.write_text('external content', encoding='utf-8')
            rename(src, target)

        monkeypatch.setattr(MoveExecutor, '_rename_no_replace', racing_rename)

        result = Renamer.undo_moves([(a, dst)])

        assert result.errors
        assert not result.moves
        assert a.read_text(encoding='utf-8') == 'external content'
        assert dst.read_text(encoding='utf-8') == 'content 0'
        assert not list(tmp_path.glob('.bulkrename-*'))


class TestSymlinks:
    """Test that symlink entries are preserved independently of their targets."""

    def test_broken_symlink_destination_is_occupied(self, source_files, tmp_path):
        """Test that a dangling symlink cannot be overwritten by a rename."""
        a, _, _ = source_files
        dst = tmp_path / 'link.txt'
        try:
            dst.symlink_to(tmp_path / 'missing.txt')
        except OSError:
            pytest.skip('Symlink creation is unavailable')

        result = Renamer.perform_rename([(a, dst)])

        assert result.errors
        assert not result.moves
        assert dst.is_symlink()
        assert a.read_text(encoding='utf-8') == 'content 0'

    def test_broken_symlink_source_can_be_renamed_and_undone(self, tmp_path):
        """Test renaming a dangling symlink without following its target."""
        src = tmp_path / 'link.txt'
        dst = tmp_path / 'renamed.txt'
        target = tmp_path / 'missing.txt'
        try:
            src.symlink_to(target)
        except OSError:
            pytest.skip('Symlink creation is unavailable')

        result = Renamer.perform_rename([(src, dst)])

        assert not result.errors
        assert not result.missing
        assert dst.is_symlink()
        assert dst.readlink() == target
        assert not os.path.lexists(src)

        undone = Renamer.undo_moves(result.moves)

        assert not undone.errors
        assert not undone.missing
        assert src.is_symlink()
        assert src.readlink() == target
        assert not os.path.lexists(dst)
