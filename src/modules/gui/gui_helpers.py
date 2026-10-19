"""GUI helpers module for Bulk Rename Py.

Provides utility functions and helper methods for GUI operations,
including translation, window management, UI element manipulation,
and common dialog operations.
"""

from __future__ import annotations

import logging
import os

from PySide6.QtWidgets import QMessageBox

from ..settings import set_language_in_config

logger = logging.getLogger(__name__)

# Constants
DEFAULT_TOKEN_NAME = '{name}'
DEFAULT_TOKEN_EXT = '{ext}'
DEFAULT_TOKEN_COUNTER = '{counter}'
DEFAULT_TOKEN_DATE = '{date}'
DEFAULT_TOKEN_TIME = '{time}'
DEFAULT_TOKEN_NAME_SLICE = '{name1-3}'
DEFAULT_TOKEN_EXT_SLICE = '{ext1-3}'


class GUIHelpers:
    """GUI helper class for Bulk Rename Py.

    Provides utility methods for GUI operations including translation,
    window management, UI element manipulation, and common dialog operations.
    """

    def __init__(self, main_window):
        """Initialize GUI helpers with reference to main window.

        **Parameters:**
            `main_window`: Reference to main application window

        **Returns:**
            `None`
        """
        self.main_window = main_window

    def tr(self, key: str) -> str:
        """Translate text using application translator.

        **Parameters:**
            `key` (str): Translation key

        **Returns:**
            `str`: Translated text
        """
        return self.main_window.translator.t(key)

    def set_language(self, code: str) -> None:
        """Set application language and restart window.

        **Parameters:**
            `code` (str): Language code to set

        **Returns:**
            `None`
        """
        set_language_in_config(code)
        self.main_window.translator.switch_language(code)
        self.restart_window()

    def restart_window(self) -> None:
        """Restart the main application window.

        Creates new window instance and closes current one.

        **Returns:**
            `None`
        """
        try:
            # Import MainWindow dynamically to avoid circular import
            from .main_window import MainWindow
            self.main_window._next_window = MainWindow()
            self.main_window._next_window.show()
            self.main_window.close()
        except (OSError, RuntimeError, ValueError) as e:
            logger.exception('Could not restart the main window')
            # Show error message if restart fails
            QMessageBox.critical(
                self.main_window,
                self.tr('messages.error'),
                self.tr('messages.errors.window_restart_failed').format(str(e))
            )

    def insert_token(self, edit, token: str) -> None:
        """Insert token text into editor widget.

        **Parameters:**
            `edit`: Editor widget to insert into
            `token` (str): Token text to insert

        **Returns:**
            `None`
        """
        if edit is None:
            # Skip if editor is None
            return
        edit.setFocus()
        edit.insert(token)

    def is_windows(self) -> bool:
        """Check if running on Windows operating system.

        **Returns:**
            `bool`: True if running on Windows, False otherwise
        """
        return os.name == 'nt'

    def set_combo_by_data(self, combo, value: str) -> None:
        """Set combo box current item by data value.

        **Parameters:**
            `combo`: Combo box widget
            `value` (str): Data value to search for

        **Returns:**
            `None`
        """
        # Search for matching data value in combo box
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                return

    def question_box(self, title_key: str, text_key: str) -> bool:
        """Show yes/no question dialog.

        **Parameters:**
            `title_key` (str): Translation key for dialog title
            `text_key` (str): Translation key for dialog text

        **Returns:**
            `bool`: True if user clicked Yes, False if No
        """
        title = self.tr(title_key)
        text = self.tr(text_key)

        # Create and configure question dialog
        box = QMessageBox(self.main_window)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle(title)
        box.setText(text)

        yes_btn = box.addButton(self.tr('dialogs.buttons.yes'), QMessageBox.YesRole)
        box.addButton(self.tr('dialogs.buttons.no'), QMessageBox.NoRole)

        box.setDefaultButton(yes_btn)
        box.exec()

        return box.clickedButton() == yes_btn

    def reset_text_fields(self) -> None:
        """Reset all text input fields to default values.

        **Returns:**
            `None`
        """
        # Reset rename mask field
        self.main_window.edit_mask.setText('{name}')
        # Reset extension field
        self.main_window.edit_ext.setText('{ext}')
        # Clear search field
        self.main_window.edit_search.setText('')
        # Clear replace field
        self.main_window.edit_replace.setText('')

    def apply_tooltips(self) -> None:
        """Apply tooltips to all UI elements based on translation keys.

        **Returns:**
            `None`
        """
        tooltip_mapping = {
            # Menu bar
            'act_add_files': 'tooltips.menu.act_add_files',
            'act_add_folder': 'tooltips.menu.act_add_folder',
            'act_hidden': 'tooltips.menu.act_hidden',
            'act_reset': 'tooltips.menu.act_reset',
            'act_about': 'tooltips.menu.act_about',
            'act_exit': 'tooltips.menu.act_exit',

            # Lower buttons
            'btn_clear': 'tooltips.actions.btn_clear',
            'btn_rename': 'tooltips.actions.btn_rename',
            'btn_undo': 'tooltips.actions.btn_undo',

            # Rename section
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

            # Extension section
            'edit_ext': 'tooltips.extension.edit_ext',
            'btn_ext': 'tooltips.extension.btn_ext',
            'btn_ext_slice': 'tooltips.extension.btn_ext_slice',
            'btn_ext_counter': 'tooltips.extension.btn_counter',

            # Replace section
            'edit_search': 'tooltips.replace.edit_search',
            'edit_replace': 'tooltips.replace.edit_replace',
            'cb_regex': 'tooltips.replace.cb_regex',
            'cb_first_match': 'tooltips.replace.cb_first_match',
            'cb_exact_match': 'tooltips.replace.cb_exact_matches',
            'cb_case_sens': 'tooltips.replace.cb_case_sens',
            'cb_ignore_ext': 'tooltips.replace.cb_ignore_ext',

            # Counter section
            'spin_start': 'tooltips.counter.spin_start',
            'spin_step': 'tooltips.counter.spin_step',
            'spin_digits': 'tooltips.counter.spin_digits',
            'cb_dupes': 'tooltips.counter.cb_dupes',

            # Advanced options section
            'cmb_case': 'tooltips.advanced_opts.cmb_case',
            'cb_windows': 'tooltips.advanced_opts.cb_windows_forced' if self.is_windows() else 'tooltips.advanced_opts.cb_windows',
            'btn_editor': 'tooltips.advanced_opts.btn_editor'
        }

        # Apply tooltips to all mapped UI elements
        for attr, tooltip_key in tooltip_mapping.items():
            getattr(self.main_window, attr).setToolTip(self.tr(tooltip_key))
