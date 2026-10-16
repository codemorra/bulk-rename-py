"""Integration tests for table and undo state after rename failures."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
)

from modules.core.file_operations import MoveExecutor
from modules.gui.rename_manager import RenameManager


@pytest.fixture(scope='module')
def qt_application():
    """Create a Qt application without opening windows or using real settings."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv('QT_QPA_PLATFORM', 'offscreen')
        application = QApplication.instance() or QApplication([])
        yield application


@pytest.fixture
def manager_factory(qt_application, monkeypatch):
    """Create managers with real table cells and intercepted confirmation dialogs."""
    messages = []
    monkeypatch.setattr(QMessageBox, 'critical', lambda *args: messages.append(args[2]))
    monkeypatch.setattr(QMessageBox, 'information', lambda *args: messages.append(args[2]))

    def create(moves):
        window = SimpleNamespace(
            table=QTableWidget(len(moves), 2), btn_undo=QPushButton(), _undo_stack=[]
        )
        for row, (src, dst) in enumerate(moves):
            item = QTableWidgetItem(src.name)
            item.setData(Qt.UserRole, str(src))
            window.table.setItem(row, 0, item)
            window.table.setItem(row, 1, QTableWidgetItem(dst.name))

        manager = RenameManager(window)
        manager.helpers = SimpleNamespace(
            tr=lambda key: key, question_box=lambda *args: True,
            reset_text_fields=lambda: None
        )
        manager.table_manager.update_preview_later = lambda: None
        # Isolate execution state from the filename validation covered separately
        manager.precheck_rename_block_on_overlength = lambda: True
        manager.show_conflicts = lambda conflicts: messages.extend(conflicts)
        manager.update_undo_state()
        return manager, messages

    return create


def table_paths(manager):
    """Read current source paths as displayed by the manager."""
    table = manager.main_window.table
    return [Path(table.item(row, 0).data(Qt.UserRole)) for row in range(table.rowCount())]


class TestRenameManagerState:
    """Test synchronization of file locations, displayed paths, and undo history."""

    def test_swap_updates_rows_and_supports_undo(self, tmp_path, manager_factory):
        """Test that table updates preserve row identities through a name swap."""
        a, b = tmp_path / 'a.txt', tmp_path / 'b.txt'
        a.write_text('A', encoding='utf-8')
        b.write_text('B', encoding='utf-8')
        moves = [(a, b), (b, a)]
        manager, _ = manager_factory(moves)

        manager.perform_rename()

        assert table_paths(manager) == [b, a]
        assert manager.main_window._undo_stack == [moves]
        assert manager.main_window.btn_undo.isEnabled()
        assert [p.read_text(encoding='utf-8') for p in table_paths(manager)] == ['A', 'B']

        manager.perform_undo()

        assert table_paths(manager) == [a, b]
        assert not manager.main_window._undo_stack
        assert not manager.main_window.btn_undo.isEnabled()
        assert [p.read_text(encoding='utf-8') for p in table_paths(manager)] == ['A', 'B']

    def test_complete_rollback_keeps_table_and_history(
            self, tmp_path, manager_factory, monkeypatch):
        """Test that a restored batch creates no misleading undo entry."""
        a, b = tmp_path / 'a.txt', tmp_path / 'b.txt'
        first, second = tmp_path / 'first.txt', tmp_path / 'second.txt'
        a.write_text('A', encoding='utf-8')
        b.write_text('B', encoding='utf-8')
        manager, messages = manager_factory([(a, first), (b, second)])
        rename = MoveExecutor._rename_no_replace

        def failing_rename(src, dst):
            if dst == second:
                raise PermissionError('simulated rename failure')
            rename(src, dst)

        monkeypatch.setattr(MoveExecutor, '_rename_no_replace', failing_rename)
        manager.perform_rename()

        assert table_paths(manager) == [a, b]
        assert not manager.main_window._undo_stack
        assert not manager.main_window.btn_undo.isEnabled()
        assert [p.read_text(encoding='utf-8') for p in table_paths(manager)] == ['A', 'B']
        assert any('simulated rename failure' in message for message in messages)
        assert not list(tmp_path.glob('.bulkrename-*'))

    def test_incomplete_rollback_records_actual_location(
            self, tmp_path, manager_factory, monkeypatch):
        """Test that staged files remain visible and can be recovered with undo."""
        a, b = tmp_path / 'a.txt', tmp_path / 'b.txt'
        first, second = tmp_path / 'first.txt', tmp_path / 'second.txt'
        a.write_text('A', encoding='utf-8')
        b.write_text('B', encoding='utf-8')
        manager, messages = manager_factory([(a, first), (b, second)])
        rename = MoveExecutor._rename_no_replace

        def failing_rename(src, dst):
            if dst == second:
                a.write_text('external content', encoding='utf-8')
                raise PermissionError('simulated rename failure')
            rename(src, dst)

        monkeypatch.setattr(MoveExecutor, '_rename_no_replace', failing_rename)
        manager.perform_rename()

        staged, unchanged = table_paths(manager)
        assert staged.name.startswith('.bulkrename-')
        assert unchanged == b
        assert manager.main_window._undo_stack == [[(a, staged)]]
        assert manager.main_window.btn_undo.isEnabled()
        assert staged.read_text(encoding='utf-8') == 'A'
        assert a.read_text(encoding='utf-8') == 'external content'
        assert any(str(staged) in message for message in messages)

        a.unlink()
        monkeypatch.setattr(MoveExecutor, '_rename_no_replace', rename)
        manager.perform_undo()

        assert table_paths(manager) == [a, b]
        assert not manager.main_window._undo_stack
        assert not manager.main_window.btn_undo.isEnabled()
        assert a.read_text(encoding='utf-8') == 'A'
        assert b.read_text(encoding='utf-8') == 'B'
        assert not list(tmp_path.glob('.bulkrename-*'))

    def test_incomplete_undo_updates_history_for_retry(
            self, tmp_path, manager_factory, monkeypatch):
        """Test retrying undo after its own rollback cannot restore every file."""
        a, b = tmp_path / 'a.txt', tmp_path / 'b.txt'
        first, second = tmp_path / 'first.txt', tmp_path / 'second.txt'
        a.write_text('A', encoding='utf-8')
        b.write_text('B', encoding='utf-8')
        manager, _ = manager_factory([(a, first), (b, second)])
        manager.perform_rename()
        rename = MoveExecutor._rename_no_replace

        def failing_rename(src, dst):
            if dst == a:
                second.write_text('external content', encoding='utf-8')
                raise PermissionError('simulated undo failure')
            rename(src, dst)

        monkeypatch.setattr(MoveExecutor, '_rename_no_replace', failing_rename)
        manager.perform_undo()

        current_first, current_second = table_paths(manager)
        assert current_first == first
        assert current_second.name.startswith('.bulkrename-')
        assert manager.main_window._undo_stack == [[(a, first), (b, current_second)]]
        assert current_first.read_text(encoding='utf-8') == 'A'
        assert current_second.read_text(encoding='utf-8') == 'B'
        assert second.read_text(encoding='utf-8') == 'external content'

        second.unlink()
        monkeypatch.setattr(MoveExecutor, '_rename_no_replace', rename)
        manager.perform_undo()

        assert table_paths(manager) == [a, b]
        assert not manager.main_window._undo_stack
        assert not manager.main_window.btn_undo.isEnabled()
        assert a.read_text(encoding='utf-8') == 'A'
        assert b.read_text(encoding='utf-8') == 'B'
        assert not list(tmp_path.glob('.bulkrename-*'))

    @pytest.mark.parametrize('obstacle', ['occupied', 'missing'])
    def test_undo_preflight_failure_retains_history(
            self, tmp_path, manager_factory, obstacle):
        """Test that blocked undo keeps its history and displayed file locations."""
        src, dst = tmp_path / 'source.txt', tmp_path / 'destination.txt'
        src.write_text('original', encoding='utf-8')
        manager, messages = manager_factory([(src, dst)])
        manager.perform_rename()
        if obstacle == 'occupied':
            src.write_text('external', encoding='utf-8')
        else:
            dst.unlink()

        manager.perform_undo()

        assert table_paths(manager) == [dst]
        assert manager.main_window._undo_stack == [[(src, dst)]]
        assert manager.main_window.btn_undo.isEnabled()
        assert messages
        if obstacle == 'occupied':
            assert src.read_text(encoding='utf-8') == 'external'
            assert dst.read_text(encoding='utf-8') == 'original'

    def test_unchanged_row_blocks_conflicting_rename(self, tmp_path, manager_factory):
        """Test conflict checking against rows excluded from effective renames."""
        a, b = tmp_path / 'a.txt', tmp_path / 'b.txt'
        a.write_text('A', encoding='utf-8')
        b.write_text('B', encoding='utf-8')
        manager, messages = manager_factory([(a, b), (b, b)])

        manager.perform_rename()

        assert table_paths(manager) == [a, b]
        assert not manager.main_window._undo_stack
        assert messages
        assert a.read_text(encoding='utf-8') == 'A'
        assert b.read_text(encoding='utf-8') == 'B'


class TestEditorFailures:
    """Test editor errors without launching an external application."""

    def test_failed_editor_launch_stops_loading(
            self, tmp_path, manager_factory, monkeypatch):
        """Test that a rejected launch cleans up and never loads edited names."""
        src = tmp_path / 'source.txt'
        manager, messages = manager_factory([(src, tmp_path / 'destination.txt')])
        preview = tmp_path / 'preview.txt'
        preview.write_text('destination.txt\n', encoding='utf-8')
        processed = []
        monkeypatch.setattr(manager, '_create_temp_file', lambda names: preview)
        monkeypatch.setattr(manager, '_process_edited_file', lambda *args: processed.append(args))
        monkeypatch.setattr(QDesktopServices, 'openUrl', lambda url: False)

        manager.open_in_editor()

        assert not processed
        assert not preview.exists()
        assert messages == ['messages.errors.open_editor_failed']

    def test_invalid_editor_encoding_reports_read_error(self, tmp_path, manager_factory):
        """Test that invalid UTF-8 data is reported without applying edited names."""
        src = tmp_path / 'source.txt'
        manager, messages = manager_factory([(src, tmp_path / 'destination.txt')])
        preview = tmp_path / 'preview.txt'
        preview.write_bytes(b'\xff\xfe')

        assert manager._read_edited_lines(preview) is None
        assert messages == ['messages.errors.read_failed']
        assert manager.main_window.table.item(0, 1).text() == 'destination.txt'

