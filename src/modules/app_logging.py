"""Application logging configuration for Bulk Rename Py.

Provides local rotating log files with a stderr fallback and records uncaught
Python exceptions while preserving the previously installed exception hooks.
"""

import logging
import os
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

_handler: logging.Handler | None = None
_previous_excepthook = sys.excepthook
_previous_thread_excepthook = threading.excepthook
logger = logging.getLogger(__name__)


def get_log_path() -> Path:
    """Select the local log file path without creating directories.

    Uses LOCALAPPDATA on Windows and XDG_STATE_HOME on Linux, with home-based
    defaults when unset. Relative XDG paths are ignored to keep logs outside
    the current working directory.

    **Returns:**
        `Path`: Application log file in the platform's local state directory
    """
    if sys.platform == 'win32':
        local_app_data = os.environ.get('LOCALAPPDATA')
        base = Path(local_app_data) if local_app_data else Path.home() / 'AppData' / 'Local'
    else:
        state_home = os.environ.get('XDG_STATE_HOME')
        base = Path(state_home) if state_home else Path.home() / '.local' / 'state'
        if not base.is_absolute():
            base = Path.home() / '.local' / 'state'
    return base / 'BulkRenamePy' / 'logs' / 'bulk-rename-py.log'


def configure_logging() -> None:
    """Configure INFO logging and exception hooks at application startup.

    Installs a UTF-8 rotating file handler, falling back to stderr if the log
    path is unavailable. Repeated calls reuse the installed handler and hooks;
    existing handlers remain installed.

    **Returns:**
        `None`
    """
    global _handler, _previous_excepthook, _previous_thread_excepthook

    root = logging.getLogger()
    if _handler is None or _handler not in root.handlers:
        failure = None
        try:
            path = get_log_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            _handler = RotatingFileHandler(
                path, maxBytes=1024 * 1024, backupCount=3, encoding='utf-8'
            )
        except (OSError, ValueError, RuntimeError):
            failure = sys.exc_info()
            _handler = logging.StreamHandler()

        _handler.setLevel(logging.INFO)
        _handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s %(name)s: %(message)s'
        ))
        root.setLevel(logging.INFO)
        root.addHandler(_handler)
        if failure is not None:
            logger.warning('File logging unavailable; using stderr', exc_info=failure)

    if sys.excepthook is not _log_uncaught_exception:
        _previous_excepthook = sys.excepthook
        sys.excepthook = _log_uncaught_exception
    if threading.excepthook is not _log_thread_exception:
        _previous_thread_excepthook = threading.excepthook
        threading.excepthook = _log_thread_exception


def _log_uncaught_exception(exc_type, exc_value, traceback) -> None:
    """Record unexpected exceptions and delegate to the previous Python hook.

    KeyboardInterrupt and SystemExit retain their existing handling without
    being logged as application failures.
    """
    if not issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
        logger.critical('Uncaught exception', exc_info=(exc_type, exc_value, traceback))
    _previous_excepthook(exc_type, exc_value, traceback)


def _log_thread_exception(args) -> None:
    """Record unexpected worker failures and delegate to the previous thread hook."""
    if not issubclass(args.exc_type, (KeyboardInterrupt, SystemExit)):
        logger.critical(
            'Uncaught exception in thread %s',
            args.thread.name if args.thread is not None else 'unknown',
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )
    _previous_thread_excepthook(args)
