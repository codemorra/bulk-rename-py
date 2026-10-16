"""Tests for table actions, cancelled imports, and external editor workflows."""

import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMenu, QMessageBox

from modules.gui import rename_manager, table_manager
from modules.gui.gui_helpers import GUIHelpers
from modules.importer import Importer


def source_paths(manager):
    """Read source paths from the current table."""
    table = manager.main_window.table
    return [Path(table.item(row, 0).data(Qt.UserRole)) for row in range(table.rowCount())]


@pytest.fixture
def existing_list(tmp_path, manager_factory):
    """Create a loaded file with undo history and a pending preview update."""
    src = tmp_path / 'existing.txt'
    src.write_text('existing content', encoding='utf-8')
    manager, messages = manager_factory([(src, src)])
    window = manager.main_window
    window._undo_stack.append([(tmp_path / 'original.txt', src)])
    manager.update_undo_state()
    window._update_timer.start(60)
    return manager, messages, src


class TestTableActions:
    """Test that table mutations respect cancellation and update undo state."""

    def test_cancelled_import_preserves_list_history_and_preview(self, existing_list, tmp_path):
        """Test that declining undo invalidation cancels the entire import."""
        manager, _, src = existing_list
        manager.helpers.question_box = lambda *args: False
        new_file = tmp_path / 'new.txt'
        new_file.write_text('new content', encoding='utf-8')
        history = list(manager.main_window._undo_stack)

        assert not manager.import_from_paths([str(new_file)])

        assert source_paths(manager) == [src]
        assert manager.main_window.table.item(0, 1).text() == src.name
        assert manager.main_window._undo_stack == history
        assert manager.main_window.btn_undo.isEnabled()
        assert manager.main_window._update_timer.isActive()

    def test_collection_failure_keeps_current_state(self, existing_list, tmp_path, monkeypatch):
        """Test that an unreadable directory cannot clear the previous list."""
        manager, messages, src = existing_list
        history = list(manager.main_window._undo_stack)

        def fail_collection(*args):
            raise PermissionError('simulated unreadable folder')

        monkeypatch.setattr(Importer, 'collect', fail_collection)

        assert not manager.import_from_paths([str(tmp_path)])
        assert source_paths(manager) == [src]
        assert manager.main_window._undo_stack == history
        assert manager.main_window.btn_undo.isEnabled()
        assert any('simulated unreadable folder' in message for message in messages)

    def test_empty_import_keeps_current_state(self, existing_list, tmp_path):
        """Test that importing an empty folder preserves the list and its undo history."""
        manager, messages, src = existing_list
        folder = tmp_path / 'empty'
        folder.mkdir()

        assert not manager.import_from_paths([str(folder)])
        assert source_paths(manager) == [src]
        assert manager.main_window._undo_stack
        assert manager.main_window.btn_undo.isEnabled()
        assert messages == ['messages.information.no_importable_files']

    def test_successful_import_replaces_list_and_clears_undo(self, existing_list, tmp_path):
        """Test replacement, natural ordering, and superscript filename handling."""
        manager, _, _ = existing_list
        paths = [tmp_path / name for name in ('file10.txt', 'file2.txt', '².txt')]
        for path in paths:
            path.write_text('new content', encoding='utf-8')

        assert manager.import_from_paths([str(path) for path in paths])
        assert [p.name for p in source_paths(manager)] == ['file2.txt', 'file10.txt', '².txt']
        assert not manager.main_window._undo_stack
        assert not manager.main_window.btn_undo.isEnabled()
        assert manager.main_window.table.updatesEnabled()

    @pytest.mark.parametrize('confirm', [False, True])
    def test_clear_list_respects_confirmation(self, existing_list, confirm):
        """Test that clear either preserves the entire state or resets it together."""
        manager, _, src = existing_list
        manager.helpers.question_box = lambda *args: confirm

        assert manager.table_manager.clear_table() is confirm
        assert source_paths(manager) == ([] if confirm else [src])
        assert bool(manager.main_window._undo_stack) is not confirm
        assert manager.main_window.btn_undo.isEnabled() is not confirm
        assert manager.main_window._update_timer.isActive() is not confirm

    @pytest.mark.parametrize('confirm', [False, True])
    def test_context_menu_removal_respects_confirmation(self, existing_list, monkeypatch, confirm):
        """Test the real context menu action and its undo confirmation path."""
        manager, _, src = existing_list
        manager.helpers.question_box = lambda *args: confirm
        table = manager.main_window.table
        labels = []

        class TestMenu(QMenu):
            def exec(self, pos):
                labels.extend(action.text() for action in self.actions())
                return self.actions()[0]

        monkeypatch.setattr(table_manager, 'QMenu', TestMenu)
        manager.table_manager.table_context_menu(table.visualItemRect(table.item(0, 0)).center())

        assert labels == ['context_menu.remove']
        assert source_paths(manager) == ([] if confirm else [src])
        assert bool(manager.main_window._undo_stack) is not confirm
        assert manager.main_window.btn_undo.isEnabled() is not confirm

    def test_repaint_state_is_restored_after_row_failure(self, existing_list, tmp_path, monkeypatch):
        """Test that an unexpected row failure cannot leave the table unable to repaint."""
        manager, _, _ = existing_list
        new_file = tmp_path / 'new.txt'
        new_file.write_text('content', encoding='utf-8')

        def fail_row(path):
            raise RuntimeError('simulated row failure')

        monkeypatch.setattr(manager.table_manager, 'table_add_entry', fail_row)

        with pytest.raises(RuntimeError, match='simulated row failure'):
            manager.import_from_paths([str(new_file)])
        assert manager.main_window.table.updatesEnabled()

    def test_unhandled_events_are_not_consumed(self, existing_list):
        """Test that unrelated Qt events pass through the delegated event filter."""
        manager, _, _ = existing_list

        assert not manager.table_manager.eventFilter(manager.main_window, QEvent(QEvent.User))


class TestDropActions:
    """Test that accepted and cancelled drops use the existing rename manager."""

    @pytest.mark.parametrize('confirm', [False, True])
    def test_drop_result_matches_import_result(self, existing_list, tmp_path, confirm):
        """Test that the drop is accepted only after a successful import."""
        manager, _, src = existing_list
        manager.helpers.question_box = lambda *args: confirm
        new_file = tmp_path / 'new.txt'
        new_file.write_text('content', encoding='utf-8')
        actions = []
        event = SimpleNamespace(
            setDropAction=lambda action: actions.append(action),
            accept=lambda: actions.append('accept'), ignore=lambda: actions.append('ignore')
        )

        assert manager.table_manager._process_dropped_paths([str(new_file)], event)
        assert source_paths(manager) == ([new_file] if confirm else [src])
        assert actions == ([Qt.CopyAction, 'accept'] if confirm else ['ignore'])

    def test_multiple_directory_drop_keeps_list(self, existing_list, tmp_path):
        """Test the translated warning for an unsupported multi-directory drop."""
        manager, messages, src = existing_list
        folders = [tmp_path / name for name in ('first', 'second')]
        for folder in folders:
            folder.mkdir()
        ignored = []
        event = SimpleNamespace(ignore=lambda: ignored.append(True))

        assert manager.table_manager._process_dropped_paths([str(p) for p in folders], event)
        assert source_paths(manager) == [src]
        assert ignored == [True]
        assert messages == ['messages.information.multiple_directories']


class TestPendingPreviews:
    """Test that delayed generated previews do not replace explicit editor changes."""

    def test_rename_flushes_pending_preview(self, tmp_path, manager_factory):
        """Test renaming immediately after changing a naming mask."""
        src = tmp_path / 'source.txt'
        src.write_text('content', encoding='utf-8')
        manager, _ = manager_factory([(src, tmp_path / 'stale.txt')])
        manager.collect_cfg().mask.name_mask = 'fresh'
        manager.main_window._update_timer.start(60)

        manager.perform_rename()

        assert (tmp_path / 'fresh.txt').read_text(encoding='utf-8') == 'content'
        assert not (tmp_path / 'stale.txt').exists()
        assert source_paths(manager) == [tmp_path / 'fresh.txt']

    def test_editor_exports_pending_preview(self, tmp_path, manager_factory, monkeypatch):
        """Test that the exported list uses current settings rather than stale cells."""
        src = tmp_path / 'source.txt'
        manager, _ = manager_factory([(src, tmp_path / 'stale.txt')])
        manager.collect_cfg().mask.name_mask = 'fresh'
        manager.main_window._update_timer.start(60)
        exported = []

        def reject_launch(url):
            path = Path(url.toLocalFile())
            exported.append((path, path.read_text(encoding='utf-8-sig')))
            return False

        monkeypatch.setattr(QDesktopServices, 'openUrl', reject_launch)
        manager.open_in_editor()

        assert exported[0][1] == 'fresh.txt\n'
        assert not exported[0][0].exists()

    def test_manual_names_stop_pending_preview(self, tmp_path, manager_factory):
        """Test that applying editor names preserves them until another settings change."""
        src = tmp_path / 'source.txt'
        src.write_text('content', encoding='utf-8')
        manager, _ = manager_factory([(src, tmp_path / 'stale.txt')])
        manager.main_window._update_timer.start(60)

        manager._apply_edited_names(['manual.txt'])

        assert not manager.main_window._update_timer.isActive()
        manager.perform_rename()
        assert (tmp_path / 'manual.txt').read_text(encoding='utf-8') == 'content'


class TestEditorWorkflow:
    """Test cancellation, retries, read errors, and temporary file cleanup."""

    @pytest.mark.parametrize('decision', ['cancel', 'reopen', 'launch_failure'])
    def test_line_count_mismatch_has_explicit_exit_paths(
            self, tmp_path, manager_factory, monkeypatch, decision):
        """Test that retry succeeds or cancellation returns without another load prompt."""
        src = tmp_path / 'source.txt'
        manager, messages = manager_factory([(src, tmp_path / 'original.txt')])
        launches = []
        questions = []

        def launch(url):
            path = Path(url.toLocalFile())
            launches.append(path)
            if len(launches) == 1:
                path.write_text('extra.txt\nextra2.txt\n', encoding='utf-8')
                return True
            path.write_text('manual.txt\n', encoding='utf-8')
            return decision != 'launch_failure'

        def confirm(title, text):
            questions.append(text)
            return True

        manager.helpers.question_box = confirm
        monkeypatch.setattr(QDesktopServices, 'openUrl', launch)
        class TestDialog(QMessageBox):
            def exec(self):
                return 0

            def clickedButton(self):
                if decision == 'cancel':
                    return None
                return next(button for button in self.buttons()
                            if self.buttonRole(button) == QMessageBox.ActionRole)

        monkeypatch.setattr(rename_manager, 'QMessageBox', TestDialog)

        manager.open_in_editor()

        assert len(launches) == (1 if decision == 'cancel' else 2)
        assert len(questions) == (2 if decision == 'reopen' else 1)
        assert manager.main_window.table.item(0, 1).text() == (
            'manual.txt' if decision == 'reopen' else 'original.txt'
        )
        assert not launches[0].exists()
        if decision == 'launch_failure':
            assert messages == ['messages.errors.open_editor_failed']

    @pytest.mark.parametrize('corrupt', [False, True])
    def test_read_failure_cleans_up_preview_file(self, tmp_path, manager_factory, monkeypatch, corrupt):
        """Test cleanup after invalid UTF-8 data or deletion by the external editor."""
        manager, messages = manager_factory([(tmp_path / 'source.txt', tmp_path / 'original.txt')])
        paths = []

        def launch(url):
            path = Path(url.toLocalFile())
            paths.append(path)
            if corrupt:
                path.write_bytes(b'\xff\xff')
            else:
                path.unlink()
            return True

        monkeypatch.setattr(QDesktopServices, 'openUrl', launch)
        manager.open_in_editor()

        assert not paths[0].exists()
        assert manager.main_window.table.item(0, 1).text() == 'original.txt'
        assert messages == ['messages.errors.read_failed']

    def test_cancelled_load_cleans_up_preview_file(self, tmp_path, manager_factory, monkeypatch):
        """Test cleanup when the user declines loading the edited file."""
        manager, _ = manager_factory([(tmp_path / 'source.txt', tmp_path / 'original.txt')])
        manager.helpers.question_box = lambda *args: False
        paths = []

        def launch(url):
            paths.append(Path(url.toLocalFile()))
            return True

        monkeypatch.setattr(QDesktopServices, 'openUrl', launch)
        manager.open_in_editor()

        assert not paths[0].exists()
        assert manager.main_window.table.item(0, 1).text() == 'original.txt'

    def test_preview_files_are_unique_and_closed(self, tmp_path, manager_factory, monkeypatch):
        """Test independent files that can be reopened immediately on Windows as well."""
        manager, _ = manager_factory([])
        monkeypatch.setattr(tempfile, 'tempdir', str(tmp_path))
        first = manager._create_temp_file(['first.txt'])
        second = manager._create_temp_file(['second.txt'])

        assert first != second
        assert first.read_text(encoding='utf-8-sig') == 'first.txt\n'
        assert second.read_text(encoding='utf-8-sig') == 'second.txt\n'
        manager._cleanup_temp_file(first)
        manager._cleanup_temp_file(second)

    @pytest.mark.parametrize('name', ['a\nb.txt', 'a\rb.txt', 'bad\ud800'])
    def test_unrepresentable_names_do_not_leave_temp_files(
            self, tmp_path, manager_factory, monkeypatch, name):
        """Test line-break rejection and cleanup after UTF-8 encoding failure."""
        manager, messages = manager_factory([])
        monkeypatch.setattr(tempfile, 'tempdir', str(tmp_path))

        assert manager._create_temp_file([name]) is None
        assert not list(tmp_path.glob('bulkrename_preview_*'))
        assert messages

    def test_bom_and_windows_line_endings(self, tmp_path, manager_factory):
        """Test UTF-8 files saved with a byte-order mark and Windows line endings."""
        manager, _ = manager_factory([])
        path = tmp_path / 'preview.txt'
        path.write_bytes(b'\xef\xbb\xbffirst.txt\r\nsecond.txt\r\n')

        assert manager._read_edited_lines(path) == ['first.txt', 'second.txt']

    def test_filename_starting_with_bom_survives_round_trip(self, tmp_path, manager_factory, monkeypatch):
        """Test that a byte-order mark in a filename is distinct from the file encoding mark."""
        manager, _ = manager_factory([])
        monkeypatch.setattr(tempfile, 'tempdir', str(tmp_path))
        name = '\ufeffname.txt'
        preview = manager._create_temp_file([name])

        assert manager._read_edited_lines(preview) == [name]
        manager._cleanup_temp_file(preview)


def test_main_window_rename_undo_and_clear(qt_application, tmp_path, monkeypatch):
    """Test the complete window with isolated settings and intercepted confirmations."""
    from modules import settings
    from modules.gui import main_window

    config_dir = tmp_path / 'config'
    monkeypatch.setattr(settings, 'CONFIG_DIR', config_dir)
    monkeypatch.setattr(settings, 'CONFIG_FILE', config_dir / 'config.ini')
    monkeypatch.setattr(main_window, 'CONFIG_FILE', config_dir / 'config.ini')
    monkeypatch.setattr(QMessageBox, 'information', lambda *args: None)

    def unexpected_error(*args):
        pytest.fail(str(args[2]))

    monkeypatch.setattr(QMessageBox, 'critical', unexpected_error)
    monkeypatch.setattr(QMessageBox, 'warning', unexpected_error)
    window = main_window.MainWindow()
    try:
        qt_application.processEvents()
        window.rename_manager.helpers.question_box = lambda *args: True
        src = tmp_path / 'source.txt'
        src.write_text('content', encoding='utf-8')

        assert window.rename_manager.import_from_paths([str(src)])
        window.edit_mask.setText('renamed')
        window.rename_manager.perform_rename()

        dst = tmp_path / 'renamed.txt'
        assert dst.read_text(encoding='utf-8') == 'content'
        assert window.btn_undo.isEnabled()
        assert window.table.item(0, 0).data(Qt.UserRole) == str(dst)

        window.rename_manager.perform_undo()

        assert src.read_text(encoding='utf-8') == 'content'
        assert not window.btn_undo.isEnabled()
        assert window.table.item(0, 0).data(Qt.UserRole) == str(src)

        window.table.selectRow(0)
        window.table_manager.remove_selected_rows()
        assert window.table.rowCount() == 0
        assert not window._update_timer.isActive()

        assert window.rename_manager.import_from_paths([str(src)])
        assert window.table_manager.clear_table()
        assert window.table.rowCount() == 0
        assert not window._update_timer.isActive()
    finally:
        window._update_timer.stop()
        window.close()
        window.deleteLater()
        qt_application.sendPostedEvents(None, QEvent.DeferredDelete)


def test_restart_failure_uses_existing_translator(manager_factory, monkeypatch):
    """Test that a failed window restart reports its original error without another exception."""
    from modules.gui import main_window

    manager, messages = manager_factory([])
    manager.main_window.translator = SimpleNamespace(t=lambda key: key + ' {0}')

    def fail_restart():
        raise RuntimeError('simulated restart failure')

    monkeypatch.setattr(main_window, 'MainWindow', fail_restart)
    GUIHelpers(manager.main_window).restart_window()

    assert messages == ['messages.errors.window_restart_failed simulated restart failure']
