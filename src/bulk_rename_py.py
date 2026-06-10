#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Bulk Rename Py
# © 2026–present Codemorra (Christopher Kranz)
# Licensed under the MIT License (see LICENSE file)

"""
Starting point of Bulk Rename Py.

Starts the Qt application (PySide6), loads the GUI (MainWindow),
and transfers control to the Qt event loop.
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
    """
    Special style adjustments in Windows.

    **Returns:**
        `None`
    """
    app.setStyle("Fusion")

    # automatic switching between light and dark
    def _apply_scheme(scheme: Qt.ColorScheme) -> None:
        if scheme == Qt.ColorScheme.Dark:
            app.setPalette(app.style().standardPalette())
        else:
            app.setPalette(app.style().standardPalette())

    try:
        scheme = QGuiApplication.styleHints().colorScheme()
        _apply_scheme(scheme)
        QGuiApplication.styleHints().colorSchemeChanged.connect(_apply_scheme)
    except AttributeError:
        pass


def main() -> int:
    """
    Entry point of the application.

    Configures high-DPI scaling, creates the `QApplication`, sets the style to
    `Fusion`, initializes `MainWindow`, and starts the Qt event loop.

    **Returns:**
        `int`: Exit code of `QApplication.exec()`
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
