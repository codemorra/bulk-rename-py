# -*- coding: utf-8 -*-

# Bulk Rename Py
# © 2026–present Codemorra (Christopher Kranz)
# Licensed under the MIT License (see LICENSE file)

"""About dialog module for Bulk Rename Py.

Handles display of application information, version details, license text,
and update checking functionality for the about dialog.
"""

from __future__ import annotations
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPlainTextEdit, QDialogButtonBox, QStyle, QMessageBox
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
    """About dialog for the application.

    Displays application information including version, license, developer details,
    and checks for available updates. Provides access to full license text.
    """

    def __init__(self, main_window):
        """Initialize about dialog with reference to main window.

        **Parameters:**
            `main_window`: Reference to main application window

        **Returns:**
            `None`
        """
        self.main_window = main_window
        self.helpers = GUIHelpers(main_window)

    def show_about_dialog(self) -> None:
        """Display the About dialog with application information.

        Shows version, license, developer info, and checks for updates.

        **Returns:**
            `None`
        """
        def compose_html(status_html: str = '') -> str:
            """Compose HTML content for about dialog.

            Builds formatted HTML string with application metadata and status.

            **Parameters:**
                `status_html` (str): Optional update status HTML

            **Returns:**
                `str`: Formatted HTML for dialog display
            """
            # Build HTML with application info and optional update status
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

        # Create dialog window
        dlg = QDialog(self.main_window)
        dlg.setWindowTitle(self.helpers.tr('about.title'))
        dlg.setModal(True)
        dlg.setSizeGripEnabled(False)
        dlg.setWindowFlag(Qt.MSWindowsFixedSizeDialogHint, True)

        root = QVBoxLayout(dlg)

        # Upper section: icon on left, text on right
        top = QHBoxLayout()
        root.addLayout(top)

        # Info icon
        icon_size = dlg.style().pixelMetric(QStyle.PM_MessageBoxIconSize)
        info_icon = dlg.style().standardIcon(QStyle.SP_MessageBoxInformation)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(info_icon.pixmap(icon_size, icon_size))
        icon_lbl.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        top.addWidget(icon_lbl, 0, Qt.AlignTop)

        # About text with HTML formatting
        text_lbl = QLabel()
        text_lbl.setTextFormat(Qt.RichText)
        text_lbl.setTextInteractionFlags(Qt.TextBrowserInteraction)
        text_lbl.setOpenExternalLinks(False)
        text_lbl.setText(compose_html())
        top.addWidget(text_lbl, 1)

        # Handle link clicks (license or external URLs)
        def safe_open_url(url: str) -> None:
            """Safely open URL in browser or show license dialog.

            **Parameters:**
                `url` (str): URL to open or special license link

            **Returns:**
                `None`
            """
            try:
                if url == LICENSE_LINK:
                    # Show license dialog for special app://license links
                    self._show_license_dialog(parent=dlg)
                else:
                    # Open external URLs in default browser
                    webbrowser.open(url)
            except Exception as e:
                # Show warning on error
                QMessageBox.warning(
                    dlg,
                    self.helpers.tr('messages.warning'),
                    self.helpers.tr('messages.errors.url_open_failed').format(str(e))
                )

        text_lbl.linkActivated.connect(safe_open_url)

        # OK button
        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(dlg.accept)
        root.addWidget(buttons, 0, Qt.AlignRight)

        # Set dialog size based on content
        dlg.adjustSize()
        dlg.setFixedSize(dlg.sizeHint())

        # Start update check in background
        dlg._checker = UpdateChecker(APP_INFO['update_repo'], APP_INFO['version'])
        dlg._checker.finished.connect(
            lambda status, release_url: (
                # Update text with check result
                text_lbl.setText(compose_html(
                    f' &nbsp;—&nbsp; <a href="{release_url}">{self.helpers.tr("about.update_available")}</a>'
                    if status == 'available' else
                    f' &nbsp;—&nbsp; {self.helpers.tr("about.no_update")}'
                    if status == 'none' else
                    f' &nbsp;—&nbsp; {self.helpers.tr("about.update_failed")}'
                    if status == 'failed' else
                    ''
                )),
                # Adjust dialog size to fit new content
                dlg.adjustSize(),
                dlg.setFixedSize(dlg.sizeHint())
            )
        )
        dlg._checker.start()

        dlg.exec()

    def _show_license_dialog(self, parent=None) -> None:
        """Show license dialog with full license text.

        Displays combined LICENSE and THIRD_PARTY_LICENSES in monospace font.

        **Parameters:**
            `parent` (QWidget | None): Parent widget for dialog

        **Returns:**
            `None`
        """
        # Get combined license text from metadata
        license_text = APP_INFO.get("license_text")

        # Create license dialog
        dlg = QDialog(parent or self.main_window)
        dlg.setWindowTitle(self.helpers.tr("about.license_window_title"))
        dlg.setModal(True)
        dlg.setSizeGripEnabled(True)

        layout = QVBoxLayout(dlg)

        # Text area with license content
        text_area = QPlainTextEdit()
        text_area.setPlainText(license_text)
        text_area.setReadOnly(True)

        # Use monospace font for license text
        mono = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        mono.setStyleHint(QFont.Monospace)
        text_area.setFont(mono)

        layout.addWidget(text_area, 1)

        # OK button
        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(dlg.accept)
        layout.addWidget(buttons, 0, Qt.AlignRight)

        dlg.resize(*DEFAULT_LICENSE_WINDOW_SIZE)
        dlg.exec()
