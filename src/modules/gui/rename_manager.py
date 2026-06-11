# -*- coding: utf-8 -*-

# Bulk Rename Py
# © 2026–present Codemorra (Christopher Kranz)
# Licensed under the MIT License (see LICENSE file)

"""Rename manager module for Bulk Rename Py.

Handles file renaming operations, configuration collection, validation,
and preview generation for the bulk rename functionality.
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
from ..importer import ImportOptions, Importer
from .table_manager import TableManager
from .gui_helpers import GUIHelpers

# Constants
DEFAULT_EDITOR = 'notepad'
TEMP_FILE_SUFFIX = '.txt'
ENCODING = 'utf-8'
COMMENT_CHAR = '#'
UNCHANGED_CASE = 'unchanged'


class RenameManager:
    """Rename manager class for Bulk Rename Py.

    Handles file renaming operations, configuration collection, validation,
    and preview generation for the bulk rename functionality.
    """

    def __init__(self, main_window):
        """Initialize rename manager with main window reference.

        **Parameters:**
            `main_window`: Reference to main application window

        **Returns:**
            `None`
        """
        self.main_window = main_window
        self.helpers = GUIHelpers(main_window)
        self.table_manager = TableManager(main_window)

    def collect_cfg(self) -> RenameCfg:
        """Collect rename configuration from UI controls.

        **Returns:**
            `RenameCfg`: Configuration object with all rename settings
        """
        return RenameCfg(
            dt=self._collect_datetime_cfg(),
            counter=self._collect_counter_cfg(),
            repl=self._collect_replace_cfg(),
            case=self._collect_case_cfg(),
            mask=self._collect_mask_cfg()
        )

    def _collect_datetime_cfg(self) -> DateTimeCfg:
        """Collect datetime configuration from UI controls.

        **Returns:**
            `DateTimeCfg`: Datetime configuration object
        """
        return DateTimeCfg(
            date_format=self.main_window.cmb_date.currentText(),
            date_sep=self.main_window.cmb_date_sep.currentData(),
            time_format=self.main_window.cmb_time.currentText(),
            time_sep=self.main_window.cmb_time_sep.currentData(),
            date_type=self.main_window.cmb_datetype.currentData(),
        )

    def _collect_counter_cfg(self) -> CounterCfg:
        """Collect counter configuration from UI controls.

        **Returns:**
            `CounterCfg`: Counter configuration object
        """
        return CounterCfg(
            start=self.main_window.spin_start.value(),
            step=self.main_window.spin_step.value(),
            digits=self.main_window.spin_digits.value(),
            dupes_only=self.main_window.cb_dupes.isChecked(),
        )

    def _collect_replace_cfg(self) -> ReplaceCfg | None:
        """Collect replace configuration from UI controls.

        **Returns:**
            `ReplaceCfg | None`: Replace configuration object or None if no search text
        """
        if not self.main_window.edit_search.text():
            # Return None if no search pattern is provided
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
        """Collect case configuration from UI controls.

        **Returns:**
            `CaseCfg`: Case configuration object
        """
        return CaseCfg(
            mode=self.main_window.cmb_case.currentData() or UNCHANGED_CASE,
            windows_names=self.main_window.cb_windows.isChecked(),
        )

    def _collect_mask_cfg(self) -> MaskCfg:
        """Collect mask configuration from UI controls.

        **Returns:**
            `MaskCfg`: Mask configuration object
        """
        return MaskCfg(
            name_mask=self.main_window.edit_mask.text(),
            ext_mask=self.main_window.edit_ext.text(),
        )

    def update_preview_now(self) -> None:
        """Update preview table with renamed filenames.

        **Returns:**
            `None`
        """
        rowcount = self.main_window.table.rowCount()
        if rowcount == 0:
            # Skip if no files in table
            return

        # Collect configuration and generate preview names
        cfg = self.collect_cfg()
        paths = [Path(self.main_window.table.item(r, 0).data(Qt.UserRole)) for r in range(rowcount)]
        new_names = Renamer.preview_names(paths, cfg)
        
        # Sanitize filenames for Linux
        if not self.helpers.is_windows():
            new_names = [Validator.sanitize_filename(name, linux_safe=True) for name in new_names]

        # Update table with preview names and validation
        for r, new_name in enumerate(new_names):
            src_item = self.main_window.table.item(r, 0)
            if src_item is None:
                continue
            
            item = self.main_window.table.item(r, 1)
            if item is None:
                item = QTableWidgetItem('')
                self.main_window.table.setItem(r, 1, item)
            item.setText(new_name)

            src_full = Path(src_item.data(Qt.UserRole))
            base_dir = src_full.parent

            invalid = False
            messages = []

            platform = 'windows' if self.helpers.is_windows() else 'linux'
            
            # Validate filename for Windows
            if platform == 'windows' and cfg.case.windows_names:
                if not Validator.validate_filename(new_name, windows_safe=True):
                    invalid = True
                    messages.append(self.helpers.tr('tooltips.table.filename_invalid_chars'))
            
            # Validate path length
            if not Validator.validate_path_length(base_dir, new_name, platform=platform):
                invalid = True
                if platform == 'windows':
                    messages.append(self.helpers.tr('tooltips.table.filename_too_long_windows'))
                else:
                    messages.append(self.helpers.tr('tooltips.table.filename_too_long_linux'))

            tooltip = self.table_manager.format_overlen_tooltip(messages)
            self.table_manager.style_preview_cell(item, invalid, tooltip, new_name)

    def open_in_editor(self) -> None:
        """Open preview names in external editor for manual editing.

        **Returns:**
            `None`
        """
        names = self._collect_preview_names()
        if not names:
            # Skip if no names collected
            return

        tmpfile = self._create_temp_file(names)
        if not tmpfile:
            # Skip if temp file creation failed
            return

        self._open_file_in_editor(tmpfile)

        self._process_edited_file(tmpfile, names)

    def _collect_preview_names(self) -> list[str]:
        """Collect preview names from table.

        **Returns:**
            `list[str]`: List of preview names
        """
        names = [self.main_window.table.item(r, 1).text() for r in range(self.main_window.table.rowCount())]
        if not names:
            # Show info message if no files
            QMessageBox.information(self.main_window, self.helpers.tr('messages.info'),
                                    self.helpers.tr('messages.information.no_files'))
        return names

    def _create_temp_file(self, names: list[str]) -> Path | None:
        """Create temporary file with preview names.

        **Parameters:**
            `names` (list[str]): List of names to write to temp file

        **Returns:**
            `Path | None`: Path to created temp file or None if failed
        """
        try:
            # Determine temp directory based on platform
            if self.helpers.is_windows():
                tmpdir = Path(tempfile.gettempdir())
            else:
                tmpdir = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))

            tmpfile = tmpdir / f"bulkrename_preview_{os.getpid()}.txt"

            # Create parent directories if needed
            tmpfile.parent.mkdir(parents=True, exist_ok=True)

            # Write names to temp file
            with tmpfile.open("w", encoding=ENCODING, newline="\n") as f:
                for n in names:
                    f.write(n + "\n")

            return tmpfile
        except Exception as e:
            # Show error if temp file creation fails
            QMessageBox.critical(self.main_window, self.helpers.tr('messages.error'),
                                self.helpers.tr('messages.errors.temp_file_failed'))
            return None

    def _open_file_in_editor(self, tmpfile: Path) -> None:
        """Open temporary file in external editor.

        **Parameters:**
            `tmpfile` (Path): Path to temporary file to open

        **Returns:**
            `None`
        """
        try:
            # Open file with default system editor
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(tmpfile)))
        except Exception:
            # Show error if opening editor fails
            QMessageBox.critical(self.main_window, self.helpers.tr('messages.error'),
                                self.helpers.tr('messages.errors.open_editor_failed'))

    def _process_edited_file(self, tmpfile: Path, original_names: list[str]) -> None:
        """Process edited file and apply changes.

        **Parameters:**
            `tmpfile` (Path): Path to temporary file
            `original_names` (list[str]): List of original names

        **Returns:**
            `None`
        """
        while True:
            # Ask user if they want to load edited names
            if not self.helpers.question_box('messages.confirm', 'messages.questions.load_from_editor'):
                self._cleanup_temp_file(tmpfile)
                return

            lines = self._read_edited_lines(tmpfile)
            if lines is None:
                # Skip if reading failed
                return

            if not self._validate_line_count(lines, original_names, tmpfile):
                # Retry if line count validation fails
                continue

            self._apply_edited_names(lines)
            self._cleanup_temp_file(tmpfile)
            return

    def _read_edited_lines(self, tmpfile: Path) -> list[str] | None:
        """Read edited lines from temporary file.

        **Parameters:**
            `tmpfile` (Path): Path to temporary file

        **Returns:**
            `list[str] | None`: List of lines or None if failed
        """
        try:
            # Read all lines from temp file
            with tmpfile.open('r', encoding=ENCODING) as f:
                lines = f.readlines()
            return self._process_file_lines(lines)
        except Exception:
            # Show error if reading fails
            QMessageBox.critical(self.main_window, self.helpers.tr('messages.error'),
                                self.helpers.tr('messages.errors.read_failed'))
            return None

    def _process_file_lines(self, lines: list[str]) -> list[str]:
        """Process file lines by stripping line endings.

        **Parameters:**
            `lines` (list[str]): List of raw lines from file

        **Returns:**
            `list[str]`: List of processed lines
        """
        # Strip line endings from each line
        return [ln.rstrip('\r\n') for ln in lines]

    def _validate_line_count(self, lines: list[str], original_names: list[str], tmpfile: Path) -> bool:
        """Validate that line count matches original names.

        **Parameters:**
            `lines` (list[str]): List of edited lines
            `original_names` (list[str]): List of original names
            `tmpfile` (Path): Path to temporary file

        **Returns:**
            `bool`: True if validation passes, False otherwise
        """
        if len(lines) != len(original_names):
            # Show warning if line count mismatch
            mbox = QMessageBox(self.main_window)
            mbox.setIcon(QMessageBox.Warning)
            mbox.setWindowTitle(self.helpers.tr('messages.error'))
            mbox.setText(self.helpers.tr('messages.errors.editor_count_mismatch'))
            reopen = mbox.addButton(self.helpers.tr('dialogs.buttons.open_again'), QMessageBox.ActionRole)
            cancel = mbox.addButton(self.helpers.tr('dialogs.buttons.cancel'), QMessageBox.RejectRole)
            mbox.exec()

            if mbox.clickedButton() == reopen:
                # Reopen editor if user wants to fix
                self._open_file_in_editor(tmpfile)
                return False
            else:
                # Clean up and cancel if user cancels
                self._cleanup_temp_file(tmpfile)
                return False

        return True

    def _apply_edited_names(self, lines: list[str]) -> None:
        """Apply edited names to preview table.

        **Parameters:**
            `lines` (list[str]): List of edited names

        **Returns:**
            `None`
        """
        # Update each row in table with edited name
        for r, val in enumerate(lines):
            self.main_window.table.item(r, 1).setText(val)

    def _cleanup_temp_file(self, tmpfile: Path) -> None:
        """Clean up temporary file.

        **Parameters:**
            `tmpfile` (Path): Path to temporary file to clean up

        **Returns:**
            `None`
        """
        try:
            # Delete temp file if it exists
            tmpfile.unlink(missing_ok=True)
        except Exception:
            # Ignore cleanup errors
            pass

    def perform_rename(self) -> None:
        """Perform the actual file renaming operation.

        **Returns:**
            `None`
        """
        rows = self.main_window.table.rowCount()

        # Check for potential issues before renaming
        if not self.precheck_rename_block_on_overlength():
            return

        if rows == 0:
            # Show info if no files to rename
            QMessageBox.information(
                self.main_window, self.helpers.tr('messages.info'),
                self.helpers.tr('messages.information.no_files_for_rename')
            )
            return

        # Confirm rename operation with user
        if not self.helpers.question_box('messages.confirm', 'messages.questions.confirm_rename'):
            return

        # Collect current paths and new names
        paths = [Path(self.main_window.table.item(r, 0).data(Qt.UserRole)) for r in range(rows)]
        new_names = [self.main_window.table.item(r, 1).text() for r in range(rows)]
        plan = Renamer.plan_moves(paths, new_names)

        # Filter out no-op renames
        effective = [(src, dst) for src, dst in plan if src.name != dst.name]
        if not effective:
            # Show info if no actual renames needed
            QMessageBox.information(
                self.main_window,
                self.helpers.tr('messages.info'),
                self.helpers.tr('messages.information.no_effective_rename')
            )
            return

        # Check for conflicts
        conflicts = Validator.check_conflicts(effective)
        if conflicts:
            self.show_conflicts(conflicts)
            return

        # Check for missing source files
        missing = [str(src) for src, _ in effective if not src.exists()]
        if missing:
            QMessageBox.critical(
                self.main_window,
                self.helpers.tr('messages.error'),
                self.helpers.tr('messages.errors.missing_sources') + '\n\n' + '\n'.join(missing)
            )
            return

        # Perform the actual rename operation
        errors = Renamer.perform_rename(effective)

        if errors:
            # Show errors if rename failed
            QMessageBox.critical(
                self.main_window, self.helpers.tr('messages.error'),
                self.helpers.tr('messages.errors.rename_failed') + '\n\n' + '\n\n'.join(errors)
            )
            return

        # Update undo stack and UI state
        self.main_window._undo_stack.append(effective)
        self.update_undo_state()

        # Update table with new filenames
        for r in range(self.main_window.table.rowCount()):
            old_item = self.main_window.table.item(r, 0)
            full = Path(old_item.data(Qt.UserRole))
            new_name = self.main_window.table.item(r, 1).text()
            new_full = full.with_name(new_name)
            old_item.setText(new_full.name)
            old_item.setToolTip(str(new_full))
            old_item.setData(Qt.UserRole, str(new_full))

        # Reset UI and update preview
        self.helpers.reset_text_fields()
        self.table_manager.update_preview_later()

    def show_conflicts(self, conflicts: list[str]) -> None:
        """Show conflicts dialog with detailed conflict information.

        **Parameters:**
            `conflicts` (list[str]): List of conflict descriptions

        **Returns:**
            `None`
        """
        # Create and configure conflict dialog
        box = QMessageBox(self.main_window)
        box.setIcon(QMessageBox.Critical)
        box.setWindowTitle(self.helpers.tr('messages.error'))
        box.setText(self.helpers.tr('messages.errors.conflicts_found'))

        # Create text area for conflict details
        text_area = QPlainTextEdit()
        text_area.setReadOnly(True)
        text_area.setPlainText('\n\n'.join(conflicts))
        text_area.setMinimumSize(500, 250)
        text_area.setStyleSheet('QPlainTextEdit { background: palette(base); }')

        # Add text area to dialog layout
        layout = box.layout()
        layout.addWidget(text_area, 1, 0, 1, layout.columnCount())

        # Add OK button
        box.addButton(self.helpers.tr('dialogs.buttons.ok'), QMessageBox.AcceptRole)

        box.exec()

    def precheck_rename_block_on_overlength(self) -> bool:
        """Pre-check rename operation for potential issues.

        **Returns:**
            `bool`: True if pre-check passes, False if issues found
        """
        if not self._has_table_rows():
            # Skip validation if no rows
            return True

        # Validate each row in table
        for r in range(self.main_window.table.rowCount()):
            if not self._validate_table_row(r):
                return False

        return True

    def _has_table_rows(self) -> bool:
        """Check if table has any rows.

        **Returns:**
            `bool`: True if table has rows, False otherwise
        """
        return self.main_window.table.rowCount() > 0

    def _validate_table_row(self, row: int) -> bool:
        """Validate a specific table row.

        **Parameters:**
            `row` (int): Row index to validate

        **Returns:**
            `bool`: True if row is valid, False otherwise
        """
        item_src = self.main_window.table.item(row, 0)
        item_new = self.main_window.table.item(row, 1)
        
        if not item_src or not item_new:
            # Skip validation if items are missing
            return True

        # Get base directory and new name for validation
        base_dir = Path(item_src.data(Qt.UserRole)).parent
        new_name = item_new.text()
        
        return self._validate_name_length(base_dir, new_name)

    def _validate_name_length(self, base_dir: Path, new_name: str) -> bool:
        """Validate filename length and characters.

        **Parameters:**
            `base_dir` (Path): Base directory path
            `new_name` (str): New filename to validate

        **Returns:**
            `bool`: True if validation passes, False otherwise
        """
        platform = 'windows' if self.helpers.is_windows() else 'linux'
        
        # Validate filename characters for Windows
        if platform == 'windows' and cfg.case.windows_names:
            if not Validator.validate_filename(new_name, windows_safe=True):
                self._show_invalid_chars_warning()
                return False
        
        # Validate path length
        if not Validator.validate_path_length(base_dir, new_name, platform=platform):
            self._show_name_too_long_warning()
            return False
        return True

    def _show_name_too_long_warning(self) -> None:
        """Show warning for filename too long.

        **Returns:**
            `None`
        """
        QMessageBox.warning(
            self.main_window,
            self.helpers.tr('messages.warning'),
            self.helpers.tr('messages.warnings.name_too_long'),
        )

    def _show_invalid_chars_warning(self) -> None:
        """Show warning for invalid characters in filename.

        **Returns:**
            `None`
        """
        QMessageBox.warning(
            self.main_window,
            self.helpers.tr('messages.warning'),
            self.helpers.tr('messages.warnings.invalid_chars'),
        )

    def perform_undo(self) -> None:
        """Perform undo operation to revert file renames.

        **Returns:**
            `None`
        """
        if not self.main_window._undo_stack:
            # Show info if no undo available
            QMessageBox.information(
                self.main_window, self.helpers.tr('messages.info'),
                self.helpers.tr('messages.information.no_undo')
            )
            return

        # Confirm undo operation with user
        if not self.helpers.question_box('messages.confirm', 'messages.questions.confirm_undo'):
            return

        # Get last rename operation from stack
        moves = self.main_window._undo_stack[-1]

        # Attempt to undo the rename operation
        missing, errors = Renamer.undo_moves(moves)

        if missing:
            # Show error if source files are missing
            QMessageBox.critical(
                self.main_window, self.helpers.tr('messages.error'),
                self.helpers.tr('messages.errors.missing_sources_undo') + '\n\n' + '\n'.join(missing)
            )
            return

        if errors:
            # Show error if undo failed
            QMessageBox.critical(
                self.main_window, self.helpers.tr('messages.error'),
                self.helpers.tr('messages.errors.undo_failed') + '\n\n' + '\n'.join(errors)
            )
            return

        # Remove completed undo from stack
        self.main_window._undo_stack.pop()

        # Show success message
        QMessageBox.information(
            self.main_window, self.helpers.tr('messages.info'),
            self.helpers.tr('messages.confirmation.undo_done')
        )

        # Update table with reverted filenames
        mapping = {str(dst): str(src) for (src, dst) in moves}
        for row in range(self.main_window.table.rowCount()):
            item = self.main_window.table.item(row, 0)
            cur_path = str(Path(item.data(Qt.UserRole)))
            if cur_path in mapping:
                # Revert to original filename
                old_full = Path(mapping[cur_path])
                item.setData(Qt.UserRole, str(old_full))
                item.setText(old_full.name)
                item.setToolTip(str(old_full))
            else:
                # Keep current filename if not in mapping
                p = Path(item.data(Qt.UserRole))
                item.setText(p.name)
                item.setToolTip(str(p))

        # Reset UI and update state
        self.helpers.reset_text_fields()
        self.update_undo_state()
        self.table_manager.update_preview_later()

    def invalidate_undo_with_prompt(self) -> bool:
        """Invalidate undo stack with user confirmation.

        **Returns:**
            `bool`: True if undo stack was invalidated or empty, False if user cancelled
        """
        if self.main_window._undo_stack:
            # Ask user to confirm undo stack invalidation
            if not self.helpers.question_box('messages.confirm', 'messages.questions.invalidate_undo'):
                return False

            # Clear undo stack and update UI
            self.main_window._undo_stack.clear()
            self._update_undo_state()
        return True

    def update_undo_state(self) -> None:
        """Update undo button state based on undo stack.

        **Returns:**
            `None`
        """
        # Enable undo button if stack has items
        self.main_window.btn_undo.setEnabled(bool(self.main_window._undo_stack))

    def handle_config_change(self, section: str, key: str, value) -> None:
        """Handle configuration changes.

        **Parameters:**
            `section` (str): Configuration section
            `key` (str): Configuration key
            `value`: Configuration value

        **Returns:**
            `None`
        """
        # Save configuration and update preview
        set_cfg(section, key, value)
        self.table_manager.update_preview_later()

    def reset_all_settings(self) -> None:
        """Reset all application settings to defaults.

        **Returns:**
            `None`
        """
        # Confirm reset with user
        if not self.helpers.question_box('messages.confirm', 'messages.questions.reset_settings'):
            return

        # Reset configuration
        reset_config(autodetect_language=True)

        # Show confirmation and restart
        QMessageBox.information(
            self.main_window, self.helpers.tr('messages.info'), self.helpers.tr('messages.confirmation.settings_reset'))
        self.helpers.restart_window()

    def action_open_files(self) -> None:
        """Open file dialog to select files for renaming.

        **Returns:**
            `None`
        """
        # Show file open dialog
        files, _ = QFileDialog.getOpenFileNames(
            self.main_window, self.helpers.tr('dialogs.open_files'), str(Path.home()), self.helpers.tr('dialogs.file_types')
        )

        # Import selected files
        if files:
            self.import_from_paths(files)

    def action_open_folder(self) -> None:
        """Open folder dialog to select folder for renaming.

        **Returns:**
            `None`
        """
        # Show folder open dialog
        folder = QFileDialog.getExistingDirectory(
            self.main_window, self.helpers.tr('dialogs.open_folder'), str(Path.home()),
            options=QFileDialog.ShowDirsOnly
        )

        # Import selected folder
        if folder:
            self.import_from_paths([folder])

    def import_from_paths(self, paths: list[str]) -> None:
        """Import files from given paths.

        **Parameters:**
            `paths` (list[str]): List of file/folder paths to import

        **Returns:**
            `None`
        """
        # Clear existing table
        self.table_manager.clear_table()

        # Configure import options
        opts = ImportOptions(
            allow_files=True,
            allow_dirs=True,
            include_hidden=self.main_window.act_hidden.isChecked()
        )

        # Collect and filter files
        items = Importer.collect(paths, opts)
        files = [it.path for it in items if not it.is_dir]

        # Sort files naturally (with number support)
        files.sort(key=lambda p: [int(t) if t.isdigit() else t.lower()
                                    for t in re.split(r'(\d+)', p.name)])

        # Add files to table efficiently
        self.main_window.table.setUpdatesEnabled(False)
        for f in files:
            self.table_manager.table_add_entry(f)
        self.main_window.table.setUpdatesEnabled(True)

        # Update preview after import
        self.table_manager.update_preview_later()