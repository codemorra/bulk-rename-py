# -*- coding: utf-8 -*-

# Bulk Rename Py
# © 2026–present Codemorra (Christopher Kranz)
# Licensed under the MIT License (see LICENSE file)

"""
GUI module for Bulk Rename Py.

Provides the main window with all GUI functions.
"""

from __future__ import annotations
import os
import webbrowser
from pathlib import Path
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFontDatabase, QFont
from PySide6.QtWidgets import (
    QMessageBox, QStyle
)
from ..settings import set_language_in_config


# Constants
MIN_WINDOW_WIDTH = 1
DEFAULT_TOKEN_NAME = '{name}'
DEFAULT_TOKEN_EXT = '{ext}'
DEFAULT_TOKEN_COUNTER = '{counter}'
DEFAULT_TOKEN_DATE = '{date}'
DEFAULT_TOKEN_TIME = '{time}'
DEFAULT_TOKEN_NAME_SLICE = '{name1-3}'
DEFAULT_TOKEN_EXT_SLICE = '{ext1-3}'


class GUIHelpers:
    """
    Helper methods for the GUI module.
    """

    def __init__(self, main_window):
        """Initializes the GUIHelpers with a reference to the main window.

        **Parameters:**
            `main_window`: Reference to the main application window

        **Returns:**
            `None`
        """
        self.main_window = main_window

    def resizeEvent(self, e) -> None:
        """Enforces a minimum width for the main window and calls the standard resize event.

        Acts as a Qt event handler for window resize events.

        **Parameters:**
            `e` (QResizeEvent): Resize event object

        **Returns:**
            `None`
        """
        if self.main_window.width() < self.main_window.MIN_WIDTH:
            self.main_window.resize(self.main_window.MIN_WIDTH, max(self.main_window.height(), self.main_window.minimumSizeHint().height()))

        super(MainWindow, self.main_window).resizeEvent(e)

    def tr(self, key: str) -> str:
        """
        Short form for translations using the Translator object.

        **Parameters:**
            `key` (str): Key for the language string (e.g., "menu.file")

        **Returns:**
            `str`: Translated text string
        """
        return self.main_window.translator.t(key)

    def set_language(self, code: str) -> None:
        """
        Saves the selected language in the configuration and
        restarts the window with the new language.

        **Parameters:**
            `code` (str): Language code (e.g., "en" or "de")

        **Returns:**
            `None`
        """
        set_language_in_config(code)
        self.main_window.translator.switch_language(code)
        self.restart_window()

    def restart_window(self) -> None:
        """
        Opens a new main window and closes the current one.

        Used, among other things, after language or configuration changes.

        **Returns:**
            `None`
        """
        try:
            # Import MainWindow dynamically to avoid circular import
            from .main_window import MainWindow
            self.main_window._next_window = MainWindow()
            self.main_window._next_window.show()
            self.main_window.close()
        except Exception as e:
            QMessageBox.critical(
                self.main_window,
                self.helpers.tr('messages.error'),
                self.helpers.tr('messages.errors.window_restart_failed').format(str(e))
            )

    def insert_token(self, edit, token: str) -> None:
        """
        Inserts a placeholder token (e.g., "{name}", "{counter}", "{date}")
        at the current cursor position in a QLineEdit.

        **Parameters:**
            `edit` (QLineEdit): Target input field
            `token` (str): Placeholder string to be inserted

        **Returns:**
            `None`
        """
        if edit is None:
            return
        edit.setFocus()
        edit.insert(token)

    def is_windows(self) -> bool:
        """
        Checks whether the program is running under Windows.

        **Returns:**
            `bool`: True if the operating system is Windows, otherwise False
        """
        return os.name == 'nt'

    def set_combo_by_data(self, combo, value: str) -> None:
        """
        Selects the entry in the passed QComboBox widget
        whose stored itemData corresponds to the specified value.

        **Parameters:**
            `combo` (QComboBox): Target combo box
            `value` (str): Comparison value from itemData()

        **Returns:**
            `None`
        """
        try:
            for i in range(combo.count()):
                if combo.itemData(i) == value:
                    combo.setCurrentIndex(i)
                    return
        except Exception as e:
            QMessageBox.warning(
                self.main_window,
                self.helpers.tr('messages.warning'),
                self.helpers.tr('messages.errors.combo_operation_failed').format(str(e))
            )

    def question_box(self, title_key: str, text_key: str) -> bool:
        """
        Displays a localized security prompt with "Yes"/"No" options.

        **Parameters:**
            `title_key` (str): Translation key for the window title
            `text_key` (str): Translation key for the prompt text

        **Returns:**
            `bool`: True if the user selects "Yes", otherwise False
        """
        title = self.tr(title_key)
        text = self.tr(text_key)

        box = QMessageBox(self.main_window)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle(title)
        box.setText(text)

        yes_btn = box.addButton(self.tr('dialogs.buttons.yes'), QMessageBox.YesRole)
        no_btn = box.addButton(self.tr('dialogs.buttons.no'), QMessageBox.NoRole)

        box.setDefaultButton(yes_btn)
        box.exec()

        return box.clickedButton() == yes_btn

    def reset_text_fields(self) -> None:
        """
        Resets all editable text fields (name mask, extension, search, replace)
        to their default values.

        **Returns:**
            `None`
        """
        self.main_window.edit_mask.setText('{name}')
        self.main_window.edit_ext.setText('{ext}')
        self.main_window.edit_search.setText('')
        self.main_window.edit_replace.setText('')

    def apply_tooltips(self) -> None:
        """
        Assigns tooltips to all GUI elements based on the current language.

        **Returns:**
            `None`
        """
        tooltip_mapping = {
            # menu bar
            'act_add_files': 'tooltips.menu.act_add_files',
            'act_add_folder': 'tooltips.menu.act_add_folder',
            'act_hidden': 'tooltips.menu.act_hidden',
            'act_reset': 'tooltips.menu.act_reset',
            'act_about': 'tooltips.menu.act_about',
            'act_exit': 'tooltips.menu.act_exit',

            # lower buttons
            'btn_clear': 'tooltips.actions.btn_clear',
            'btn_rename': 'tooltips.actions.btn_rename',
            'btn_undo': 'tooltips.actions.btn_undo',

            # rename section
            'edit_mask': 'tooltips.rename.edit_mask',
            'btn_name': 'tooltips.rename.btn_name',
            'btn_name_slice': 'tooltips.rename.btn_name_slice',
            'btn_counter': 'tooltips.rename.btn_counter',
            'btn_date': 'tooltips.rename.btn_date',
            'btn_time': 'tooltips.rename.btn_time',
            'cmb_date': 'tooltips.rename.cmb_date',
            'cmb_date_sep': 'tooltips.rename.cmb_date_sep',
            'cmb_time': 'tooltips.rename.cmb_time',
            'cmb_time_sep': 'tooltips.rename.cmb_time_sep',
            'cmb_datetype': 'tooltips.rename.cmb_datetype',

            # extension section
            'edit_ext': 'tooltips.extension.edit_ext',
            'btn_ext': 'tooltips.extension.btn_ext',
            'btn_ext_slice': 'tooltips.extension.btn_ext_slice',
            'btn_ext_counter': 'tooltips.extension.btn_counter',

            # replace section
            'edit_search': 'tooltips.replace.edit_search',
            'edit_replace': 'tooltips.replace.edit_replace',
            'cb_regex': 'tooltips.replace.cb_regex',
            'cb_first_match': 'tooltips.replace.cb_first_match',
            'cb_exact_match': 'tooltips.replace.cb_exact_matches',
            'cb_case_sens': 'tooltips.replace.cb_case_sens',
            'cb_ignore_ext': 'tooltips.replace.cb_ignore_ext',

            # counter section
            'spin_start': 'tooltips.counter.spin_start',
            'spin_step': 'tooltips.counter.spin_step',
            'spin_digits': 'tooltips.counter.spin_digits',
            'cb_dupes': 'tooltips.counter.cb_dupes',

            # advanced options section
            'cmb_case': 'tooltips.advanced_opts.cmb_case',
            'cb_windows': 'tooltips.advanced_opts.cb_windows_forced' if self.is_windows() else 'tooltips.advanced_opts.cb_windows',
            'btn_editor': 'tooltips.advanced_opts.btn_editor'
        }

        for attr, tooltip_key in tooltip_mapping.items():
            getattr(self.main_window, attr).setToolTip(self.tr(tooltip_key))

    def format_overlen_tooltip(self, messages: list[str]) -> str:
        """
        Adjusts the tooltip for files whose names are too long.

        **Parameters:**
            `messages` (list[str]): List of translated messages

        **Returns:**
            `str`: Combined tooltip text
        """
        msgs = ' / '.join(m for m in messages if m)

        return f'{msgs} ' if msgs else ''

    def style_preview_cell(self, item, invalid: bool, tooltip_text: str, fallback_name: str) -> None:
        """
        Formats a preview cell in the table widget.

        Behavior:
        - If length/size is invalid: Text in red + italics
        - Tooltip shows "<message>"
        - If valid: Standard color + tooltip = file name

        **Parameters:**
            `item` (QTableWidgetItem): Cell in the preview table.
            `invalid` (bool): True = invalid, False = valid.
            `tooltip_text` (str): Tooltip text in case of error.
            `fallback_name` (str): Tooltip text in case of valid name.

        **Returns:**
            `None`
        """
        # set italic font if invalid, normal otherwise
        cell_font = item.font()
        cell_font.setItalic(bool(invalid))
        item.setFont(cell_font)

        # apply red text color and error tooltip if invalid
        if invalid:
            item.setForeground(QBrush(QColor(Qt.red)))
            item.setToolTip(tooltip_text or fallback_name)
        else:
            # reset to default color and show normal tooltip
            item.setForeground(QBrush())
            item.setToolTip(fallback_name)
