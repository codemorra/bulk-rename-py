# -*- coding: utf-8 -*-

# Bulk Rename Py
# © 2026–present Codemorra (Christopher Kranz)
# Licensed under the MIT License (see LICENSE file)

"""
GUI module for Bulk Rename Py.

Provides the main window with all GUI functions.
"""

from __future__ import annotations
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPlainTextEdit, QDialogButtonBox, QStyle
from PySide6.QtGui import QFontDatabase, QFont
from PySide6.QtCore import Qt
import webbrowser
from .gui_helpers import GUIHelpers
from ..metadata import APP_INFO
from ..update_checker import UpdateChecker

# Constants
LICENSE_LINK = 'app://license'
DEFAULT_LICENSE_WINDOW_SIZE = (750, 600)


class AboutDialog:
    """
    Displays the application's "About" dialog.

    It shows information about the application, including the
    version number, licensing, and author. Depending on the installation
    source, information about updates is also provided here.
    """

    def __init__(self, main_window):
        """Initializes the AboutDialog with a reference to the main window.

        **Parameters:**
            `main_window`: Reference to the main application window

        **Returns:**
            `None`
        """
        self.main_window = main_window
        self.helpers = GUIHelpers(main_window)

    def show_about_dialog(self) -> None:
        """
        Displays the application's "About" dialog.

        **Returns:**
            `None`
        """
        def compose_html(status_html: str = '') -> str:
            """Composes HTML content for the about dialog.

            **Parameters:**
                `status_html` (str): Optional status HTML for update information

            **Returns:**
                `str`: Formatted HTML string for the dialog content
            """
            license_value = APP_INFO.get('license')
            license_link = f'<a href="app://license">{license_value}</a>'
            return (
                f'<b>{APP_INFO["name"]}</b> {APP_INFO["version"]}{status_html}<br>'
                f'{self.helpers.tr("about.description")}<br><br>'
                f'<b>{self.helpers.tr("about.license")}</b> {license_link}<br>'
                f'<b>{self.helpers.tr("about.developer")}</b> {APP_INFO["developer"]}<br>'
                f'<a href="{APP_INFO["url"]}">{APP_INFO["url"]}</a><br><br>'
                f'<small>{APP_INFO["copyright"]}</small>'
            )

        dlg = QDialog(self.main_window)
        dlg.setWindowTitle(self.helpers.tr('about.title'))
        dlg.setModal(True)
        dlg.setSizeGripEnabled(False)
        dlg.setWindowFlag(Qt.MSWindowsFixedSizeDialogHint, True)

        root = QVBoxLayout(dlg)

        # upper section: icon on the left, text on the right
        top = QHBoxLayout()
        root.addLayout(top)

        # info icon
        icon_size = dlg.style().pixelMetric(QStyle.PM_MessageBoxIconSize)
        info_icon = dlg.style().standardIcon(QStyle.SP_MessageBoxInformation)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(info_icon.pixmap(icon_size, icon_size))
        icon_lbl.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        top.addWidget(icon_lbl, 0, Qt.AlignTop)

        # about text
        text_lbl = QLabel()
        text_lbl.setTextFormat(Qt.RichText)
        text_lbl.setTextInteractionFlags(Qt.TextBrowserInteraction)
        text_lbl.setOpenExternalLinks(False)
        text_lbl.setText(compose_html())
        top.addWidget(text_lbl, 1)

        # handle links
        def safe_open_url(url: str) -> None:
            """Safely opens a URL in the default web browser.

            **Parameters:**
                `url` (str): URL to open

            **Returns:**
                `None`
            """
            try:
                if url == LICENSE_LINK:
                    self._show_license_dialog(parent=dlg)
                else:
                    webbrowser.open(url)
            except Exception as e:
                QMessageBox.warning(
                    dlg,
                    self.helpers.tr('messages.warning'),
                    self.helpers.tr('messages.errors.url_open_failed').format(str(e))
                )

        text_lbl.linkActivated.connect(safe_open_url)

        # ok button
        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(dlg.accept)
        root.addWidget(buttons, 0, Qt.AlignRight)

        # define initial size based on content
        dlg.adjustSize()
        dlg.setFixedSize(dlg.sizeHint())

        # update check
        dlg._checker = UpdateChecker(APP_INFO['update_repo'], APP_INFO['version'])
        dlg._checker.finished.connect(
            lambda status, release_url: (
                text_lbl.setText(compose_html(
                    f' &nbsp;—&nbsp; <a href="{release_url}">{self.helpers.tr("about.update_available")}</a>'
                    if status == 'available' else
                    f' &nbsp;—&nbsp; {self.helpers.tr("about.no_update")}'
                    if status == 'none' else
                    f' &nbsp;—&nbsp; {self.helpers.tr("about.update_failed")}'
                    if status == 'failed' else
                    ''
                )),
                dlg.adjustSize(),
                dlg.setFixedSize(dlg.sizeHint())
            )
        )
        dlg._checker.start()

        dlg.exec()

    def _show_license_dialog(self, parent=None) -> None:
        """
        Opens a simple modal dialog displaying the LICENSE file from the application root.

        **Returns:**
            `None`
        """
        license_text = APP_INFO.get("license_text")

        dlg = QDialog(parent or self.main_window)
        dlg.setWindowTitle(self.helpers.tr("about.license_window_title"))
        dlg.setModal(True)
        dlg.setSizeGripEnabled(True)

        layout = QVBoxLayout(dlg)

        # text area
        text_area = QPlainTextEdit()
        text_area.setPlainText(license_text)
        text_area.setReadOnly(True)

        # font
        mono = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        mono.setStyleHint(QFont.Monospace)
        text_area.setFont(mono)

        layout.addWidget(text_area, 1)

        # ok button
        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(dlg.accept)
        layout.addWidget(buttons, 0, Qt.AlignRight)

        dlg.resize(*DEFAULT_LICENSE_WINDOW_SIZE)
        dlg.exec()