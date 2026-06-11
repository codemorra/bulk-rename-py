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
import subprocess
import re
import tempfile
from pathlib import Path
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox, QPlainTextEdit, QFileDialog, QTableWidgetItem
from ..core.types import (
    RenameCfg, DateTimeCfg, CounterCfg, ReplaceCfg, CaseCfg, MaskCfg
)
from ..core.renamer import Renamer
from ..core.validation import Validator
from ..settings import set_cfg, reset_config
from ..importer import ImportOptions, collect
from .table_manager import TableManager
from .gui_helpers import GUIHelpers

# Constants
DEFAULT_EDITOR = 'notepad'
TEMP_FILE_SUFFIX = '.txt'
ENCODING = 'utf-8'
COMMENT_CHAR = '#'
UNCHANGED_CASE = 'unchanged'


class RenameManager:
    """
    Manages the renaming preview and operations.
    """

    def __init__(self, main_window):
        """Initializes the RenameManager with a reference to the main window.

        **Parameters:**
            `main_window`: Reference to the main application window

        **Returns:**
            `None`
        """
        self.main_window = main_window
        self.helpers = GUIHelpers(main_window)
        self.table_manager = TableManager(main_window)

    def collect_cfg(self) -> RenameCfg:
        """
        Reads the current GUI and configuration values
        and uses them to create a RenameCfg object for the renaming logic.

        **Returns:**
            `RenameCfg`: Fully populated RenameCfg instance
        """
        return RenameCfg(
            dt=self._collect_datetime_cfg(),
            counter=self._collect_counter_cfg(),
            repl=self._collect_replace_cfg(),
            case=self._collect_case_cfg(),
            mask=self._collect_mask_cfg()
        )

    def _collect_datetime_cfg(self) -> DateTimeCfg:
        """
        Collects datetime configuration from GUI elements.

        **Returns:**
            `DateTimeCfg`: Configured DateTimeCfg instance
        """
        return DateTimeCfg(
            date_format=self.main_window.cmb_date.currentText(),
            date_sep=self.main_window.cmb_date_sep.currentData(),
            time_format=self.main_window.cmb_time.currentText(),
            time_sep=self.main_window.cmb_time_sep.currentData(),
            date_type=self.main_window.cmb_datetype.currentData(),
        )

    def _collect_counter_cfg(self) -> CounterCfg:
        """
        Collects counter configuration from GUI elements.

        **Returns:**
            `CounterCfg`: Configured CounterCfg instance
        """
        return CounterCfg(
            start=self.main_window.spin_start.value(),
            step=self.main_window.spin_step.value(),
            digits=self.main_window.spin_digits.value(),
            dupes_only=self.main_window.cb_dupes.isChecked(),
        )

    def _collect_replace_cfg(self) -> ReplaceCfg | None:
        """
        Collects replace configuration from GUI elements.

        **Returns:**
            `ReplaceCfg | None`: Configured ReplaceCfg instance or None if no search text
        """
        if not self.main_window.edit_search.text():
            return None

        return ReplaceCfg(
            pattern=self.main_window.edit_search.text(),
            replace=self.main_window.edit_replace.text(),
            regex=self.main_window.cb_regex.isChecked(),
            first_only=self.main_window.cb_first_match.isChecked(),
            exact=self.main_window.cb_exact_match.isChecked(),
            case_sensitive=self.main_window.cb_case_sens.isChecked(),
            exclude_extension=self.main_window.cb_ignore_ext.isChecked(),
        )

    def _collect_case_cfg(self) -> CaseCfg:
        """
        Collects case configuration from GUI elements.

        **Returns:**
            `CaseCfg`: Configured CaseCfg instance
        """
        return CaseCfg(
            mode=self.main_window.cmb_case.currentData() or UNCHANGED_CASE,
            windows_names=self.main_window.cb_windows.isChecked(),
        )

    def _collect_mask_cfg(self) -> MaskCfg:
        """
        Collects mask configuration from GUI elements.

        **Returns:**
            `MaskCfg`: Configured MaskCfg instance
        """
        return MaskCfg(
            name_mask=self.main_window.edit_mask.text(),
            ext_mask=self.main_window.edit_ext.text(),
        )

    def update_preview_now(self) -> None:
        """
        Creates preview names, checks their length/size depending on the platform,
        and visually marks invalid entries.

        Platform-dependent logic:
            - Windows -> Character length (validate_path_length with platform='windows')
            - Linux -> Byte size (validate_path_length with platform='linux')

        Display:
            - Invalid -> Text in red + italics
            - Tooltip -> "<translated message> -> <name>"

        **Returns:**
            `None`
        """
        # get total number of rows in the preview table
        rowcount = self.main_window.table.rowCount()
        if rowcount == 0:
            return

        # collect current rename configuration
        cfg = self.collect_cfg()
        paths = [Path(self.main_window.table.item(r, 0).data(Qt.UserRole)) for r in range(rowcount)]
        new_names = Renamer.preview_names(paths, cfg)
        
        # Apply Linux-specific sanitization if needed
        if not self.helpers.is_windows():
            new_names = [Validator.sanitize_filename(name, linux_safe=True) for name in new_names]

        for r, new_name in enumerate(new_names):
            # Check if original file item exists
            src_item = self.main_window.table.item(r, 0)
            if src_item is None:
                continue  # Skip this row if original item is missing
            
            # Create or get preview item
            item = self.main_window.table.item(r, 1)
            if item is None:
                # Create missing preview item
                item = QTableWidgetItem('')
                self.main_window.table.setItem(r, 1, item)
            item.setText(new_name)

            # get base directory for current file
            src_full = Path(src_item.data(Qt.UserRole))
            base_dir = src_full.parent

            # initialize validation state and message list
            invalid = False
            messages = []

            # validate filename according to OS rules
            platform = 'windows' if self.helpers.is_windows() else 'linux'
            
            # Validate filename content only if Windows-safe mode is enabled
            # (otherwise illegal characters are allowed and will be handled by the OS)
            if platform == 'windows' and cfg.case.windows_names:
                if not Validator.validate_filename(new_name, windows_safe=True):
                    invalid = True
                    messages.append(self.helpers.tr('tooltips.table.filename_invalid_chars'))
            
            # Validate path length according to OS limits
            if not Validator.validate_path_length(base_dir, new_name, platform=platform):
                invalid = True
                if platform == 'windows':
                    messages.append(self.helpers.tr('tooltips.table.filename_too_long_windows'))
                else:
                    messages.append(self.helpers.tr('tooltips.table.filename_too_long_linux'))

            # format tooltip and apply preview cell styling
            tooltip = self.table_manager.format_overlen_tooltip(messages)
            self.table_manager.style_preview_cell(item, invalid, tooltip, new_name)

    def open_in_editor(self) -> None:
        """
        Exports the current preview of the target names to a temporary text file,
        opens it in the system editor, and allows manual editing.

        After saving the text file, the list can be imported again.

        **Returns:**
            `None`
        """
        # Collect preview names and check if there are any files
        names = self._collect_preview_names()
        if not names:
            return

        # Create temporary file and write preview names
        tmpfile = self._create_temp_file(names)
        if not tmpfile:
            return

        # Open file in system editor
        self._open_file_in_editor(tmpfile)

        # Process the edited file
        self._process_edited_file(tmpfile, names)

    def _collect_preview_names(self) -> list[str]:
        """
        Collects the preview names from the table.

        **Returns:**
            `list[str]`: List of preview names, or empty list if no files.
        """
        names = [self.main_window.table.item(r, 1).text() for r in range(self.main_window.table.rowCount())]
        if not names:
            QMessageBox.information(self.main_window, self.helpers.tr('messages.info'),
                                    self.helpers.tr('messages.information.no_files'))
        return names

    def _create_temp_file(self, names: list[str]) -> Path | None:
        """
        Creates a temporary file and writes the preview names to it.

        **Parameters:**
            `names` (list[str]): List of preview names to write.

        **Returns:**
            `Path | None`: Path to the temporary file, or None if creation failed.
        """
        try:
            # Determine the directory for the temp file
            if self.helpers.is_windows():
                # default temp directory (e.g., C:\Users\<Name>\AppData\Local\Temp)
                tmpdir = Path(tempfile.gettempdir())
            else:
                # directly in the user cache (~/.cache)
                tmpdir = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))

            tmpfile = tmpdir / f"bulkrename_preview_{os.getpid()}.txt"

            # Create parent directory if it doesn't exist
            tmpfile.parent.mkdir(parents=True, exist_ok=True)

            # Write names to file
            with tmpfile.open("w", encoding=ENCODING, newline="\n") as f:
                for n in names:
                    f.write(n + "\n")

            return tmpfile
        except Exception as e:
            QMessageBox.critical(self.main_window, self.helpers.tr('messages.error'),
                                self.helpers.tr('messages.errors.temp_file_failed'))
            return None

    def _open_file_in_editor(self, tmpfile: Path) -> None:
        """
        Opens the temporary file in the system editor.

        **Parameters:**
            `tmpfile` (Path): Path to the temporary file to open.

        **Returns:**
            `None`
        """
        try:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(tmpfile)))
        except Exception:
            QMessageBox.critical(self.main_window, self.helpers.tr('messages.error'),
                                self.helpers.tr('messages.errors.open_editor_failed'))

    def _process_edited_file(self, tmpfile: Path, original_names: list[str]) -> None:
        """
        Processes the edited file after the user has saved it.

        **Parameters:**
            `tmpfile` (Path): Path to the temporary file.
            `original_names` (list[str]): Original list of preview names.

        **Returns:**
            `None`
        """
        while True:
            if not self.helpers.question_box('messages.confirm', 'messages.questions.load_from_editor'):
                self._cleanup_temp_file(tmpfile)
                return

            # Read processed lines
            lines = self._read_edited_lines(tmpfile)
            if lines is None:
                return

            # Check number of lines
            if not self._validate_line_count(lines, original_names, tmpfile):
                # If validation fails, continue the loop to ask again
                continue

            # Success -> apply and cleanup
            self._apply_edited_names(lines)
            self._cleanup_temp_file(tmpfile)
            return

    def _read_edited_lines(self, tmpfile: Path) -> list[str] | None:
        """
        Reads the edited lines from the temporary file.

        **Parameters:**
            `tmpfile` (Path): Path to the temporary file.

        **Returns:**
            `list[str] | None`: List of edited lines, or None if reading failed.
        """
        try:
            with tmpfile.open('r', encoding=ENCODING) as f:
                lines = f.readlines()
            return self._process_file_lines(lines)
        except Exception:
            QMessageBox.critical(self.main_window, self.helpers.tr('messages.error'),
                                self.helpers.tr('messages.errors.read_failed'))
            return None

    def _process_file_lines(self, lines: list[str]) -> list[str]:
        """
        Processes raw file lines by stripping line endings.

        **Parameters:**
            `lines` (list[str]): Raw lines from file.

        **Returns:**
            `list[str]`: Processed lines with stripped endings.
        """
        return [ln.rstrip('\r\n') for ln in lines]

    def _validate_line_count(self, lines: list[str], original_names: list[str], tmpfile: Path) -> bool:
        """
        Validates that the number of lines in the edited file matches the original.

        **Parameters:**
            `lines` (list[str]): List of edited lines.
            `original_names` (list[str]): Original list of preview names.
            `tmpfile` (Path): Path to the temporary file.

        **Returns:**
            `bool`: True if validation passed, False otherwise.
        """
        if len(lines) != len(original_names):
            mbox = QMessageBox(self.main_window)
            mbox.setIcon(QMessageBox.Warning)
            mbox.setWindowTitle(self.helpers.tr('messages.error'))
            mbox.setText(self.helpers.tr('messages.errors.editor_count_mismatch'))
            reopen = mbox.addButton(self.helpers.tr('dialogs.buttons.open_again'), QMessageBox.ActionRole)
            cancel = mbox.addButton(self.helpers.tr('dialogs.buttons.cancel'), QMessageBox.RejectRole)
            mbox.exec()

            if mbox.clickedButton() == reopen:
                # Reopen file and continue the loop to ask again
                self._open_file_in_editor(tmpfile)
                return False
            else:
                self._cleanup_temp_file(tmpfile)
                return False

        return True

    def _apply_edited_names(self, lines: list[str]) -> None:
        """
        Applies the edited names to the table.

        **Parameters:**
            `lines` (list[str]): List of edited names.

        **Returns:**
            `None`
        """
        for r, val in enumerate(lines):
            self.main_window.table.item(r, 1).setText(val)

    def _cleanup_temp_file(self, tmpfile: Path) -> None:
        """
        Cleans up the temporary file.

        **Parameters:**
            `tmpfile` (Path): Path to the temporary file.

        **Returns:**
            `None`
        """
        try:
            tmpfile.unlink(missing_ok=True)
        except Exception:
            pass

    def perform_rename(self) -> None:
        """
        Performs the renaming process based on the current preview.

        - Reads all source and target names from the table.
        - Validates user confirmation, missing sources, and naming conflicts.
        - Executes the renames via `perform_rename()` (renamer.py).
        - Stores all successful rename pairs in the in-memory undo stack
        to allow multi-level undo within the current session.
        - Updates the table entries, resets input fields, and refreshes the preview.

        **Returns:**
            `None`
        """
        rows = self.main_window.table.rowCount()

        # abort if any filename exceeds the allowed length (validation failed)
        if not self.precheck_rename_block_on_overlength():
            return

        # abort and show info message if there are no files in the table
        if rows == 0:
            QMessageBox.information(
                self.main_window, self.helpers.tr('messages.info'),
                self.helpers.tr('messages.information.no_files_for_rename')
            )
            return

        # confirm rename operation
        if not self.helpers.question_box('messages.confirm', 'messages.questions.confirm_rename'):
            return

        # build planned rename operations from table entries
        paths = [Path(self.main_window.table.item(r, 0).data(Qt.UserRole)) for r in range(rows)]
        new_names = [self.main_window.table.item(r, 1).text() for r in range(rows)]
        plan = Renamer.plan_moves(paths, new_names)

        # check if any actual rename would happen
        effective = [(src, dst) for src, dst in plan if src.name != dst.name]
        if not effective:
            QMessageBox.information(
                self.main_window,
                self.helpers.tr('messages.info'),
                self.helpers.tr('messages.information.no_effective_rename')
            )
            return

        # conflicts
        conflicts = Validator.check_conflicts(effective)
        if conflicts:
            self.show_conflicts(conflicts)
            return

        # source not found
        missing = [str(src) for src, _ in effective if not src.exists()]
        if missing:
            QMessageBox.critical(
                self.main_window,
                self.helpers.tr('messages.error'),
                self.helpers.tr('messages.errors.missing_sources') + '\n\n' + '\n'.join(missing)
            )
            return

        # perform the actual renaming operation and collect any errors
        errors = Renamer.perform_rename(effective)

        # if errors occurred during renaming, show an error dialog and abort
        if errors:
            QMessageBox.critical(
                self.main_window, self.helpers.tr('messages.error'),
                self.helpers.tr('messages.errors.rename_failed') + '\n\n' + '\n\n'.join(errors)
            )
            return

        # remembering moves for undo
        self.main_window._undo_stack.append(effective)
        self.update_undo_state()

        # confirmation dialog
        # QMessageBox.information(
        #     self.main_window, self.helpers.tr('messages.info'),
        #     self.helpers.tr('messages.confirmation.rename_done')
        # )

        # update table
        for r in range(self.main_window.table.rowCount()):
            old_item = self.main_window.table.item(r, 0)
            full = Path(old_item.data(Qt.UserRole))
            new_name = self.main_window.table.item(r, 1).text()
            new_full = full.with_name(new_name)
            old_item.setText(new_full.name)
            old_item.setToolTip(str(new_full))
            old_item.setData(Qt.UserRole, str(new_full))

        # refresh preview after table changes
        self.helpers.reset_text_fields()
        self.table_manager.update_preview_later()

    def show_conflicts(self, conflicts: list[str]) -> None:
        """
        Displays a scrollable error message with all name conflicts found.

        **Parameters:**
            `list[str]`: List of conflicting file names.

        **Returns:**
            `None`
        """
        box = QMessageBox(self.main_window)
        box.setIcon(QMessageBox.Critical)
        box.setWindowTitle(self.helpers.tr('messages.error'))
        box.setText(self.helpers.tr('messages.errors.conflicts_found'))

        # scrollable text area
        text_area = QPlainTextEdit()
        text_area.setReadOnly(True)
        text_area.setPlainText('\n\n'.join(conflicts))
        text_area.setMinimumSize(500, 250)
        text_area.setStyleSheet('QPlainTextEdit { background: palette(base); }')

        # embed widget in message box
        layout = box.layout()
        layout.addWidget(text_area, 1, 0, 1, layout.columnCount())

        box.addButton(self.helpers.tr('dialogs.buttons.ok'), QMessageBox.AcceptRole)

        box.exec()

    def precheck_rename_block_on_overlength(self) -> bool:
        """
        Checks whether at least one new name in the preview exceeds the permitted
        length/byte limits (platform-dependent).

        Platform logic:
            - Windows: validate_path_length with platform='windows' (character/path limits)
            - Linux:   validate_path_length with platform='linux'   (byte limits NAME_MAX/PATH_MAX)

        If at least one entry is too long, a warning dialog is displayed
        and renaming is prevented.

        **Returns:**
            `bool`:
            - True = all names are valid -> renaming allowed.
            - False = at least one name too long -> renaming blocked.
        """
        if not self._has_table_rows():
            return True

        for r in range(self.main_window.table.rowCount()):
            if not self._validate_table_row(r):
                return False

        return True

    def _has_table_rows(self) -> bool:
        """
        Checks if the table has any rows.

        **Returns:**
            `bool`: True if table has rows, False otherwise.
        """
        return self.main_window.table.rowCount() > 0

    def _validate_table_row(self, row: int) -> bool:
        """
        Validates a single table row for name length constraints.

        **Parameters:**
            `row` (int): Row index to validate.

        **Returns:**
            `bool`: True if row is valid, False otherwise.
        """
        item_src = self.main_window.table.item(row, 0)
        item_new = self.main_window.table.item(row, 1)
        
        if not item_src or not item_new:
            return True

        base_dir = Path(item_src.data(Qt.UserRole)).parent
        new_name = item_new.text()
        
        return self._validate_name_length(base_dir, new_name)

    def _validate_name_length(self, base_dir: Path, new_name: str) -> bool:
        """
        Validates a name against platform-specific length constraints.

        **Parameters:**
            `base_dir` (Path): Base directory path.
            `new_name` (str): New filename to validate.

        **Returns:**
            `bool`: True if name is valid, False otherwise.
        """
        platform = 'windows' if self.helpers.is_windows() else 'linux'
        
        # Validate filename content only if Windows-safe mode is enabled
        # (otherwise illegal characters are allowed and will be handled by the OS)
        if platform == 'windows' and cfg.case.windows_names:
            if not Validator.validate_filename(new_name, windows_safe=True):
                self._show_invalid_chars_warning()
                return False
        
        # Validate path length according to OS limits
        if not Validator.validate_path_length(base_dir, new_name, platform=platform):
            self._show_name_too_long_warning()
            return False
        return True

    def _show_name_too_long_warning(self) -> None:
        """
        Shows a warning dialog for names that are too long.

        **Returns:**
            `None`
        """
        QMessageBox.warning(
            self.main_window,
            self.helpers.tr('messages.warning'),
            self.helpers.tr('messages.warnings.name_too_long'),
        )

    def _show_invalid_chars_warning(self) -> None:
        """
        Shows a warning dialog for invalid characters in filenames.

        **Returns:**
            `None`
        """
        QMessageBox.warning(
            self.main_window,
            self.helpers.tr('messages.warning'),
            self.helpers.tr('messages.warnings.invalid_chars'),
        )

    def perform_undo(self) -> None:
        """
        Reverts the most recent rename operation stored in the undo stack.

        - Retrieves the latest rename list from the in-memory stack.
        - Checks for missing targets and potential naming conflicts.
        - Calls `undo_moves()` (renamer.py) to restore original names.
        - Removes the reverted step from the undo stack upon success.
        - Updates the table, preview, and Undo button state.

        **Note:**
        Undo steps are stored only in memory and are lost when the program exits!

        **Returns:**
            `None`
        """
        # if there are no undo steps available
        if not self.main_window._undo_stack:
            QMessageBox.information(
                self.main_window, self.helpers.tr('messages.info'),
                self.helpers.tr('messages.information.no_undo')
            )
            return

        if not self.helpers.question_box('messages.confirm', 'messages.questions.confirm_undo'):
            return

        # get the last rename operation from the undo stack
        moves = self.main_window._undo_stack[-1]

        # try to revert all previously renamed files
        missing, errors = Renamer.undo_moves(moves)

        # show error if some original source files are missing
        if missing:
            QMessageBox.critical(
                self.main_window, self.helpers.tr('messages.error'),
                self.helpers.tr('messages.errors.missing_sources_undo') + '\n\n' + '\n'.join(missing)
            )
            return

        # show error if undo operation failed for any file
        if errors:
            QMessageBox.critical(
                self.main_window, self.helpers.tr('messages.error'),
                self.helpers.tr('messages.errors.undo_failed') + '\n\n' + '\n'.join(errors)
            )
            return

        # successful -> actually remove step from stack
        self.main_window._undo_stack.pop()

        QMessageBox.information(
            self.main_window, self.helpers.tr('messages.info'),
            self.helpers.tr('messages.confirmation.undo_done')
        )

        # reset table based on moves (new -> old)
        mapping = {str(dst): str(src) for (src, dst) in moves}
        for row in range(self.main_window.table.rowCount()):
            item = self.main_window.table.item(row, 0)
            cur_path = str(Path(item.data(Qt.UserRole)))
            if cur_path in mapping:
                old_full = Path(mapping[cur_path])
                item.setData(Qt.UserRole, str(old_full))
                item.setText(old_full.name)
                item.setToolTip(str(old_full))
            else:
                p = Path(item.data(Qt.UserRole))
                item.setText(p.name)
                item.setToolTip(str(p))

        self.helpers.reset_text_fields()
        self.update_undo_state()
        self.table_manager.update_preview_later()

    def invalidate_undo_with_prompt(self) -> bool:
        """
        If there are undo steps, the user is asked whether they should be
        discarded when removing/emptying. If agreed, empties the undo stack
        and updates the button state.

        **Returns:**
            bool: True = continue execution; False = cancel operation.
        """
        if self.main_window._undo_stack:
            if not self.helpers.question_box('messages.confirm', 'messages.questions.invalidate_undo'):
                return False

            self.main_window._undo_stack.clear()
            self._update_undo_state()
        return True

    def update_undo_state(self) -> None:
        """
        Updates the enabled state of the Undo button.

        Enables the Undo button only if the in-memory undo stack
        contains at least one reversible rename step.

        **Returns:**
            `None`
        """
        self.main_window.btn_undo.setEnabled(bool(self.main_window._undo_stack))

    def handle_config_change(self, section: str, key: str, value) -> None:
        """
        Writes a changed setting to the configuration
        and then triggers a delayed preview update.

        **Parameters:**
            `section` (str): Configuration section name
            `key` (str): Option key within the section
            `value` (Any): New value to write

        **Returns:**
            `None`
        """
        set_cfg(section, key, value)
        self.table_manager.update_preview_later()

    def reset_all_settings(self) -> None:
        """
        Resets all settings to factory defaults and restarts the main window.

        Displays a confirmation prompt beforehand and writes the
        default values from DEFAULTS (`settings.py`) to the configuration file.

        **Returns:**
            `None`
        """
        if not self.helpers.question_box('messages.confirm', 'messages.questions.reset_settings'):
            return

        reset_config(autodetect_language=True)

        QMessageBox.information(
            self.main_window, self.helpers.tr('messages.info'), self.helpers.tr('messages.confirmation.settings_reset'))
        self.helpers.restart_window()

    def action_open_files(self) -> None:
        """
        Opens a file dialog for selecting one or more files
        and then imports them into the table.

        **Returns:**
            `None`
        """
        files, _ = QFileDialog.getOpenFileNames(
            self.main_window, self.helpers.tr('dialogs.open_files'), str(Path.home()), self.helpers.tr('dialogs.file_types')
        )

        if files:
            self.import_from_paths(files)

    def action_open_folder(self) -> None:
        """
        Opens a dialog for selecting a directory
        and imports all files contained therein into the table.

        **Returns:**
            `None`
        """
        folder = QFileDialog.getExistingDirectory(
            self.main_window, self.helpers.tr('dialogs.open_folder'), str(Path.home()),
            options=QFileDialog.ShowDirsOnly
        )

        if folder:
            self.import_from_paths([folder])

    def import_from_paths(self, paths: list[str]) -> None:
        """
        Imports files from the specified paths or directories.

        Depending on the settings, filters hidden files,
        sorts the list naturally (e.g., A2 before A10), and fills the table
        with the files found.

        **Parameters:**
            `paths` (list[str]): List of file or directory paths

        **Returns:**
            `None`
        """
        self.table_manager.clear_table()

        # Collect all valid files from the given paths (respecting hidden-file settings)
        opts = ImportOptions(
            allow_files=True,
            allow_dirs=True,
            include_hidden=self.main_window.act_hidden.isChecked()
        )

        items = collect(paths, opts)
        files = [it.path for it in items if not it.is_dir]

        # natural sorting by file name
        files.sort(key=lambda p: [int(t) if t.isdigit() else t.lower()
                                    for t in re.split(r'(\d+)', p.name)])

        # fill in the table
        self.main_window.table.setUpdatesEnabled(False)
        for f in files:
            self.table_manager.table_add_entry(f)
        self.main_window.table.setUpdatesEnabled(True)

        # refresh preview
        self.table_manager.update_preview_later()