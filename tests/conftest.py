"""Pytest configuration and fixtures for Bulk Rename Py tests."""


import pytest


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
    from modules.core.types import (
        CaseCfg,
        CounterCfg,
        DateTimeCfg,
        MaskCfg,
        RenameCfg,
        ReplaceCfg,
    )
    
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
    from modules.core.types import (
        CaseCfg,
        CounterCfg,
        DateTimeCfg,
        MaskCfg,
        RenameCfg,
    )
    
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


@pytest.fixture(scope='session')
def qt_application():
    """Create a Qt application without opening windows or using real settings."""
    from PySide6.QtWidgets import QApplication

    with pytest.MonkeyPatch.context() as patch:
        patch.setenv('QT_QPA_PLATFORM', 'offscreen')
        application = QApplication.instance() or QApplication([])
        yield application


@pytest.fixture
def manager_factory(qt_application, monkeypatch, basic_rename_config):
    """Create managers with real table cells and intercepted confirmation dialogs."""
    from types import SimpleNamespace

    from PySide6.QtCore import QEvent, Qt, QTimer
    from PySide6.QtWidgets import (
        QMessageBox,
        QPushButton,
        QTableWidget,
        QTableWidgetItem,
        QWidget,
    )

    from modules.gui.rename_manager import RenameManager
    from modules.gui.table_manager import TableManager

    messages = []
    windows = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: messages.append(args[2]))
    monkeypatch.setattr(QMessageBox, 'critical', lambda *args: messages.append(args[2]))
    monkeypatch.setattr(QMessageBox, 'information', lambda *args: messages.append(args[2]))

    def create(moves):
        window = QWidget()
        window.table = QTableWidget(len(moves), 2, window)
        window.btn_undo = QPushButton(window)
        window._undo_stack = []
        windows.append(window)
        window._update_timer = QTimer(window.table)
        window._update_timer.setSingleShot(True)
        window.act_hidden = SimpleNamespace(isChecked=lambda: True)
        for row, (src, dst) in enumerate(moves):
            item = QTableWidgetItem(src.name)
            item.setData(Qt.UserRole, str(src))
            window.table.setItem(row, 0, item)
            window.table.setItem(row, 1, QTableWidgetItem(dst.name))

        window.helpers = SimpleNamespace(
            tr=lambda key: key, question_box=lambda *args: True,
            reset_text_fields=lambda: None, is_windows=lambda: False
        )
        window.table_manager = TableManager(window)
        manager = RenameManager(window)
        window.rename_manager = manager
        window._update_timer.timeout.connect(manager.update_preview_now)
        manager.collect_cfg = lambda: basic_rename_config
        manager.table_manager.update_preview_later = lambda: None
        # Isolate execution state from the filename validation covered separately
        manager.precheck_rename_block_on_overlength = lambda: True
        manager.show_conflicts = lambda conflicts: messages.extend(conflicts)
        manager.update_undo_state()
        return manager, messages

    yield create
    for window in windows:
        window._update_timer.stop()
        window.deleteLater()
    qt_application.sendPostedEvents(None, QEvent.DeferredDelete)
