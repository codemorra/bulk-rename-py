"""
Main entry point for Bulk Rename Py application.

This module serves as the primary entry point when running the application.
It configures application logging, initializes the Qt application environment,
applies platform-specific settings, and launches the main window. The application
uses PySide6 for its GUI.
"""

from __future__ import annotations

import logging
import os
import platform
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication

from modules.app_logging import configure_logging
from modules.gui.main_window import MainWindow
from modules.metadata import APP_INFO
from resources import icons_rc  # noqa: F401 -- Register compiled Qt resources on import.

logger = logging.getLogger(__name__)


def _apply_windows_theme(app: QApplication) -> None:
    """Apply Windows-specific theme adjustments.

    Configures the Fusion style and sets up automatic light/dark mode switching
    based on system preferences. This function is only called on Windows systems.

    Args:
        app: The QApplication instance to configure

    Returns:
        None
    """
    app.setStyle("Fusion")

    # Refresh the Fusion palette when the system color scheme changes
    def _apply_scheme(_scheme: Qt.ColorScheme) -> None:
        app.setPalette(app.style().standardPalette())

    hints = QGuiApplication.styleHints()
    _apply_scheme(hints.colorScheme())
    hints.colorSchemeChanged.connect(_apply_scheme)


def main() -> int:
    """Application entry point and main execution function.

    Performs the following steps:
    1. Configures logging and records application version, Python, and platform
    2. Configures high-DPI scaling for proper display on all screens
    3. Creates the QApplication instance
    4. Applies platform-specific theme settings
    5. Initializes and displays the main window
    6. Starts the Qt event loop and logs its normal return with the exit code

    This function is called when the script is executed directly and serves
    as the entry point for both direct execution and packaged distributions.

    Returns:
        int: The application exit code from QApplication.exec()

    Raises:
        SystemExit: When called from __main__ (wraps the exit code)
    """
    configure_logging()
    logger.info(
        'Application started: Bulk Rename Py %s; Python %s; platform %s',
        APP_INFO['version'], platform.python_version(), platform.system(),
    )

    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    QGuiApplication.setDesktopFileName("bulk-rename-py")

    app = QApplication(sys.argv)

    if os.name == 'nt':
        _apply_windows_theme(app)
    else:
        QApplication.setStyle('Fusion')

    app.setWindowIcon(QIcon(':/icons/app.svg'))

    window = MainWindow()
    window.show()

    exit_code = app.exec()
    logger.info('Application stopped: exit code %s', exit_code)
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
