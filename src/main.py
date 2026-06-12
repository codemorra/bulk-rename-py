#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Bulk Rename Py - Main Entry Point
# © 2026–present Codemorra (Christopher Kranz)
# Licensed under the MIT License (see LICENSE file)

"""
Main entry point for Bulk Rename Py application.

This module serves as the primary entry point when running the application.
It initializes the Qt application environment, configures platform-specific
settings, and launches the main window. The application uses PySide6 for its GUI.
"""

from __future__ import annotations
import os
import sys
import PySide6.QtSvg
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon, QGuiApplication
from modules import icons_rc
from modules.gui import main_window
from modules.gui.main_window import MainWindow


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

    # Automatic switching between light and dark mode
    def _apply_scheme(scheme: Qt.ColorScheme) -> None:
        if scheme == Qt.ColorScheme.Dark:
            app.setPalette(app.style().standardPalette())
        else:
            app.setPalette(app.style().standardPalette())

    try:
        # Get current system color scheme
        scheme = QGuiApplication.styleHints().colorScheme()
        _apply_scheme(scheme)
        # Connect signal for future scheme changes
        QGuiApplication.styleHints().colorSchemeChanged.connect(_apply_scheme)
    except AttributeError:
        # Fallback if color scheme detection fails
        pass


def main() -> int:
    """Application entry point and main execution function.

    Performs the following setup steps:
    1. Configures high-DPI scaling for proper display on all screens
    2. Creates the QApplication instance
    3. Applies platform-specific theme settings
    4. Initializes and displays the main window
    5. Starts the Qt event loop

    This function is called when the script is executed directly and serves
    as the entry point for both direct execution and packaged distributions.

    Returns:
        int: The application exit code from QApplication.exec()

    Raises:
        SystemExit: When called from __main__ (wraps the exit code)
    """
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

    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
