"""Tests for local logging, rotation, fallback, and application exception hooks."""

import logging
import os
import platform
import subprocess
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

from modules import app_logging


@pytest.fixture
def logging_path(tmp_path, monkeypatch):
    """Isolate log output and restore global logging state and exception hooks."""
    root = logging.getLogger()
    previous_level = root.level
    path = tmp_path / 'logs' / 'bulk-rename-py.log'
    monkeypatch.setattr(app_logging, '_handler', None)
    monkeypatch.setattr(app_logging, 'get_log_path', lambda: path)
    monkeypatch.setattr(app_logging, '_previous_excepthook', sys.excepthook)
    monkeypatch.setattr(app_logging, '_previous_thread_excepthook', threading.excepthook)
    monkeypatch.setattr(sys, 'excepthook', sys.excepthook)
    monkeypatch.setattr(threading, 'excepthook', threading.excepthook)
    try:
        yield path
    finally:
        handler = app_logging._handler
        if handler is not None:
            root.removeHandler(handler)
            handler.close()
        root.setLevel(previous_level)


@pytest.mark.parametrize(('system', 'variable', 'value', 'relative_base'), [
    ('win32', 'LOCALAPPDATA', 'custom', 'custom'),
    ('win32', 'LOCALAPPDATA', None, 'AppData/Local'),
    ('win32', 'LOCALAPPDATA', '', 'AppData/Local'),
    ('linux', 'XDG_STATE_HOME', 'custom', 'custom'),
    ('linux', 'XDG_STATE_HOME', None, '.local/state'),
    ('linux', 'XDG_STATE_HOME', '', '.local/state'),
    ('linux', 'XDG_STATE_HOME', 'relative', '.local/state'),
])
def test_platform_log_path(tmp_path, monkeypatch, system, variable, value, relative_base):
    """Test platform environment selection and home-based fallback paths."""
    monkeypatch.setattr(sys, 'platform', system)
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    if value is None:
        monkeypatch.delenv(variable, raising=False)
    else:
        monkeypatch.setenv(variable, str(tmp_path / value) if value == 'custom' else value)
    other_variable = 'XDG_STATE_HOME' if system == 'win32' else 'LOCALAPPDATA'
    monkeypatch.setenv(other_variable, str(tmp_path / 'wrong-platform'))

    assert app_logging.get_log_path() == (
        tmp_path / relative_base / 'BulkRenamePy' / 'logs' / 'bulk-rename-py.log'
    )


def test_configuration_writes_utf8_and_preserves_existing_handlers(logging_path):
    """Test handler settings and formatted UTF-8 output alongside existing handlers."""
    root = logging.getLogger()
    existing_handlers = list(root.handlers)

    app_logging.configure_logging()
    handler = app_logging._handler
    logging.getLogger('modules.example').info('Überprüfung erfolgreich')

    assert isinstance(handler, RotatingFileHandler)
    assert handler.maxBytes == 1024 * 1024
    assert handler.backupCount == 3
    assert handler.encoding == 'utf-8'
    assert handler.level == root.level == logging.INFO
    assert root.handlers == existing_handlers + [handler]
    content = logging_path.read_text(encoding='utf-8')
    assert 'INFO modules.example: Überprüfung erfolgreich' in content
    assert content.startswith(handler.formatter.formatTime(logging.makeLogRecord({}))[:10])


def test_repeated_configuration_does_not_duplicate_handlers_or_hooks(logging_path):
    """Test that reinitialization preserves delegation and writes each record once."""
    app_logging.configure_logging()
    handler = app_logging._handler
    previous_hooks = (app_logging._previous_excepthook, app_logging._previous_thread_excepthook)

    app_logging.configure_logging()
    logging.getLogger('modules.example').info('Single entry')

    assert app_logging._handler is handler
    assert logging.getLogger().handlers.count(handler) == 1
    assert previous_hooks == (
        app_logging._previous_excepthook, app_logging._previous_thread_excepthook
    )
    assert logging_path.read_text(encoding='utf-8').count('Single entry') == 1


def test_rotation_retains_three_backups(logging_path):
    """Test rotation at the configured size and removal of the oldest backup."""
    app_logging.configure_logging()
    handler = app_logging._handler
    logger = logging.getLogger('modules.example')

    for index in range(5):
        logger.info('Batch %s %s', index, 'x' * (handler.maxBytes // 2))

    assert sorted(path.name for path in logging_path.parent.iterdir()) == [
        'bulk-rename-py.log', 'bulk-rename-py.log.1',
        'bulk-rename-py.log.2', 'bulk-rename-py.log.3',
    ]
    assert 'Batch 4' in logging_path.read_text(encoding='utf-8')
    assert 'Batch 0' not in logging_path.with_suffix('.log.3').read_text(encoding='utf-8')
    assert all(path.stat().st_size <= handler.maxBytes for path in logging_path.parent.iterdir())


@pytest.mark.parametrize('failure', ['directory', 'file', 'home'])
def test_unavailable_log_path_falls_back_to_stderr(logging_path, monkeypatch, capsys, failure):
    """Test usable fallback logging after directory, file, or home lookup failures."""
    if failure == 'directory':
        logging_path.parent.write_text('Not a directory', encoding='utf-8')
    elif failure == 'file':
        logging_path.mkdir(parents=True)
    else:
        def unavailable_home():
            raise RuntimeError('Home directory unavailable')

        monkeypatch.setattr(app_logging, 'get_log_path', unavailable_home)

    app_logging.configure_logging()
    handler = app_logging._handler
    app_logging.configure_logging()
    logging.getLogger('modules.example').info('Application continues')

    assert type(handler) is logging.StreamHandler
    assert app_logging._handler is handler
    output = capsys.readouterr().err
    assert output.count('File logging unavailable') == 1
    assert 'Traceback' in output
    assert output.count('Application continues') == 1


@pytest.mark.parametrize('exception_type', [ValueError, KeyboardInterrupt, SystemExit])
def test_main_exception_hook_logs_traceback_and_delegates(logging_path, monkeypatch, exception_type):
    """Test traceback logging and delegation without treating normal exits as failures."""
    forwarded = []
    monkeypatch.setattr(sys, 'excepthook', lambda *args: forwarded.append(args))
    app_logging.configure_logging()
    try:
        raise exception_type('Main failure')
    except (ValueError, KeyboardInterrupt, SystemExit):
        exception = sys.exc_info()
    sys.excepthook(*exception)

    assert forwarded == [exception]
    content = logging_path.read_text(encoding='utf-8')
    if exception_type is ValueError:
        assert 'CRITICAL modules.app_logging: Uncaught exception' in content
        assert 'Traceback' in content
        assert 'ValueError: Main failure' in content
    else:
        assert content == ''


@pytest.mark.parametrize('exception_type', [ValueError, SystemExit])
def test_thread_exception_hook_logs_traceback_and_delegates(logging_path, monkeypatch, exception_type):
    """Test real worker failures and normal exits through the installed thread hook."""
    forwarded = []
    monkeypatch.setattr(threading, 'excepthook', forwarded.append)
    app_logging.configure_logging()

    def fail():
        raise exception_type('Worker failure')

    worker = threading.Thread(target=fail, name='test-worker')
    worker.start()
    worker.join(timeout=5)

    assert not worker.is_alive()
    assert len(forwarded) == 1
    assert forwarded[0].exc_type is exception_type
    content = logging_path.read_text(encoding='utf-8')
    if exception_type is ValueError:
        assert 'Uncaught exception in thread test-worker' in content
        assert 'Traceback' in content
        assert 'ValueError: Worker failure' in content
    else:
        assert content == ''


@pytest.mark.parametrize('startup_failure', [False, True])
def test_main_lifecycle_logging(tmp_path, startup_failure):
    """Test startup, normal exit, and uncaught startup failure in isolated Qt processes."""
    from modules.metadata import APP_INFO

    source = Path(__file__).resolve().parents[1] / 'src'
    log_path = tmp_path / 'logs' / 'bulk-rename-py.log'
    script = '''
import sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, sys.argv[1])
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
import main
from modules import app_logging
app_logging.get_log_path = lambda: Path(sys.argv[2])
def create_window():
    if sys.argv[3] == 'True':
        raise RuntimeError('Window initialization failed')
    return SimpleNamespace(show=lambda: QTimer.singleShot(0, QApplication.instance().quit))
main.MainWindow = create_window
raise SystemExit(main.main())
'''
    result = subprocess.run(
        [sys.executable, '-c', script, str(source), str(log_path), str(startup_failure)],
        cwd=tmp_path, env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'},
        capture_output=True, text=True, timeout=15, check=False,
    )

    content = log_path.read_text(encoding='utf-8')
    assert f'Application started: Bulk Rename Py {APP_INFO["version"]}' in content
    assert f'Python {platform.python_version()}' in content
    assert f'platform {platform.system()}' in content
    if startup_failure:
        assert result.returncode != 0
        assert 'Uncaught exception' in content
        assert 'Traceback' in content
        assert 'RuntimeError: Window initialization failed' in content
        assert 'RuntimeError: Window initialization failed' in result.stderr
        assert 'Application stopped' not in content
    else:
        assert result.returncode == 0, result.stderr
        assert 'Application stopped: exit code 0' in content
