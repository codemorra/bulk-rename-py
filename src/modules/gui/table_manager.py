# -*- coding: utf-8 -*-

# Bulk Rename Py
# © 2026–present Codemorra (Christopher Kranz)
# Licensed under the MIT License (see LICENSE file)

"""
GUI module for Bulk Rename Py.

Provides the main window with all GUI functions.
"""

from __future__ import annotations
from pathlib import Path
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QMessageBox, QTableWidgetItem

# Import functions from helpers
from .gui_helpers import GUIHelpers

# Constants
PREVIEW_DELAY_MS = 60
MIN_COLUMN_WIDTH = 160
COLUMN_RATIO_THRESHOLD = 0.3
INVALID_COLOR = QColor(Qt.red)


class TableManager:
    """
    Manages the table behavior and operations.
    """

    def __init__(self, main_window):
        """Initializes the TableManager with a reference to the main window.

        **Parameters:**
            `main_window`: Reference to the main application window

        **Returns:**
            `None`
        """
        self.main_window = main_window
        self.helpers = GUIHelpers(main_window)

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
        f = item.font()
        f.setItalic(bool(invalid))
        item.setFont(f)

        # apply red text color and error tooltip if invalid
        if invalid:
            item.setForeground(QBrush(INVALID_COLOR))
            item.setToolTip(tooltip_text or fallback_name)
        else:
            # reset to default color and show normal tooltip
            item.setForeground(QBrush())
            item.setToolTip(fallback_name)

    def update_preview_later(self) -> None:
        """
        Starts a short timer to delay the preview update.

        **Returns:**
            `None`
        """
        self.main_window._update_timer.start(PREVIEW_DELAY_MS)

    def eventFilter(self, obj, ev):
        """
        Intercepts resize and drag & drop events for the table.
        (Qt event handler)

        - **Resize (Viewport)**: keeps column ratios stable.
        - **DragEnter/DragMove (Table/Viewport)**: allows local files/folders to be dropped.
        - **Drop (Table/Viewport)**: extracts local paths and calls the import logic.
        - Other events are passed to the default handler.

        **Parameters:**
            `obj`: Observed object (e.g., table viewport)
            `ev`: Triggered event

        **Returns:**
            `bool`: True if the event has been fully handled; otherwise False, so that further processing is possible.
        """
        # viewport resize
        if obj is self.main_window.table.viewport() and ev.type() == QEvent.Resize:
            return self._handle_resize_event(ev)

        # drag & drop handling
        if obj not in (self.main_window.table, self.main_window.table.viewport()):
            return super(type(self.main_window), self.main_window).eventFilter(obj, ev)

        # handle drag & drop events
        if ev.type() in (QEvent.DragEnter, QEvent.DragMove):
            return self._handle_drag_enter_event(ev)

        if ev.type() == QEvent.Drop:
            return self._handle_drop_event(ev)

        # forward all other events as normal
        return super(type(self.main_window), self.main_window).eventFilter(obj, ev)

    def _handle_resize_event(self, ev) -> bool:
        """
        Handles viewport resize events.

        **Parameters:**
            `ev`: Resize event

        **Returns:**
            `bool`: False to allow further processing
        """
        self.rebalance_on_view_resize()
        return False

    def _handle_drag_enter_event(self, ev) -> bool:
        """
        Handles drag enter/move events.

        **Parameters:**
            `ev`: Drag event

        **Returns:**
            `bool`: True if event was handled, False otherwise
        """
        mime_data = ev.mimeData()
        if mime_data and mime_data.hasUrls():
            ev.acceptProposedAction()
            return True
        return False

    def _handle_drop_event(self, ev) -> bool:
        """
        Handles drop events.

        **Parameters:**
            `ev`: Drop event

        **Returns:**
            `bool`: True if event was handled, False otherwise
        """
        mime_data = ev.mimeData()
        urls = mime_data.urls() if mime_data else []
        paths = [u.toLocalFile() for u in urls if u.isLocalFile()]

        if paths:
            return self._process_dropped_paths(paths, ev)
        return False

    def _process_dropped_paths(self, paths: list[str], ev) -> bool:
        """
        Processes dropped paths and imports them.

        **Parameters:**
            `paths`: List of dropped file paths
            `ev`: Drop event

        **Returns:**
            `bool`: True if import was successful, False otherwise
        """
        # prevent multiple directories
        dir_count = sum(1 for p in paths if Path(p).is_dir())
        if dir_count > 1:
            QMessageBox.warning(
                self.main_window,
                self.main_window._tr('messages.info'),
                self.main_window._tr('messages.information.multiple_directories')
                )
            ev.ignore()
            return True

        ev.setDropAction(Qt.CopyAction)
        ev.accept()
        # Import locally to avoid circular import
        from .rename_manager import RenameManager
        rename_manager = RenameManager(self.main_window)
        rename_manager.import_from_paths(paths)
        return True

    def init_equal_columns(self) -> None:
        """
        Initializes the table with a width ratio of 50/50.

        Takes into account the minimum assigned width when changing the column width.

        **Returns:**
            `None`
        """
        viewport_width = self.main_window.table.viewport().width()
        left_width = max(self.main_window._min_left, viewport_width // 2)
        right_width = max(self.main_window._min_right, viewport_width - left_width)

        # if the sum is greater than viewport_width due to minima -> clamp
        if left_width + right_width > viewport_width:
            # preferably leave the left column at minimum width
            left_width = max(self.main_window._min_left, min(left_width, viewport_width - self.main_window._min_right))
            right_width = viewport_width - left_width

        self.set_columns(left_width, right_width)

    def set_columns(self, left_width: int, right_width: int) -> None:
        """
        Sets the widths of both columns in a signal-friendly manner.

        Temporarily blocks all signals to prevent infinite loops when manually
        or programmatically adjusting column widths.

        **Parameters:**
            `left_width` (int): New width of the left column
            `right_width` (int): New width of the right column

        **Returns:**
            `None`
        """
        self.main_window.table.blockSignals(True)
        self.main_window.table.setColumnWidth(0, left_width)
        self.main_window.table.setColumnWidth(1, right_width)
        self.main_window.table.blockSignals(False)

    def on_header_resized(self, logical_index: int, _old: int, new_width: int) -> None:
        """
        Responds to user resizing of a column and dynamically adjusts the other column.

        Ensures that:
        - the total width of the columns matches the viewport width
        - the other column fills the remaining space
        - minimum widths are maintained
        - no horizontal scroll bar appears

        **Parameters:**
            `logical_index` (int): Index of the changed column (0 = left, 1 = right)
            `_old` (int): Old width (not used)
            `new_width` (int): New width of the changed column

        **Returns:**
            `None`
        """
        if logical_index not in (0, 1):
            return

        viewport_width = self.main_window.table.viewport().width()

        if logical_index == 0:
            left_width, right_width = self._calculate_column_widths(new_width, viewport_width, is_left_column=True)
        else:
            left_width, right_width = self._calculate_column_widths(new_width, viewport_width, is_left_column=False)

        self.set_columns(left_width, right_width)

    def _calculate_column_widths(self, changed_width: int, viewport_width: int, is_left_column: bool) -> tuple[
        int, int]:
        """
        Calculates new column widths while respecting minimum width constraints.

        **Parameters:**
            `changed_width` (int): New width of the changed column
            `viewport_width` (int): Total available width
            `is_left_column` (bool): True if left column was changed, False for right

        **Returns:**
            `tuple[int, int]`: (left_column_width, right_column_width)
        """
        min_left = self.main_window._min_left
        min_right = self.main_window._min_right

        if is_left_column:
            # clamp new left width, right fills remainder (>= min)
            left_width = max(min_left, min(changed_width, viewport_width - min_right))
            right_width = max(min_right, viewport_width - left_width)
        else:
            # clamp new right width, left fills remainder (>= min)
            right_width = max(min_right, min(changed_width, viewport_width - min_left))
            left_width = max(min_left, viewport_width - right_width)

        return left_width, right_width

    def rebalance_on_view_resize(self) -> None:
        """
        Maintains the current ratio of column widths when resizing a window or table.

        If one column reaches its minimum width, only the other column is adjusted.
        The ratio is calculated from the current widths and transferred proportionally
        to the new viewport width.

        **Returns:**
            `None`
        """
        viewport_width = self.main_window.table.viewport().width()
        if viewport_width <= 0:
            return

        left_width = self.main_window.table.columnWidth(0)
        right_width = self.main_window.table.columnWidth(1)
        total_width = left_width + right_width if (left_width + right_width) > 0 else viewport_width

        # current ratio (e.g., 50/50 initially, otherwise user status)
        left_ratio = left_width / total_width
        # new target widths
        new_left_width = int(round(viewport_width * left_ratio))
        # clamp left: not smaller than min & not so large that right < min
        new_left_width = max(self.main_window._min_left,
                             min(new_left_width, viewport_width - self.main_window._min_right))
        new_right_width = viewport_width - new_left_width

        # if rounding would result in a value less than min, adjust again.
        if new_right_width < self.main_window._min_right:
            new_right_width = self.main_window._min_right
            new_left_width = viewport_width - new_right_width
            new_left_width = max(self.main_window._min_left, new_left_width)

        self.set_columns(new_left_width, new_right_width)

    def table_add_entry(self, p: Path) -> None:
        """
        Adds a new row to the table for the specified file.

        Creates cells for the current and new names and saves the full
        path as tooltip and UserRole data.

        **Parameters:**
            `p` (Path): Full path to the file

        **Returns:**
            `None`
        """
        try:
            # determine the next available row index
            row = self.main_window.table.rowCount()
            self.main_window.table.insertRow(row)
        except Exception as e:
            QMessageBox.warning(
                self.main_window,
                self.helpers.tr('messages.warning'),
                self.helpers.tr('messages.errors.table_add_failed').format(str(p), str(e))
            )
            return

        # create table item for the current filename
        current_name = QTableWidgetItem(p.name)
        current_name.setToolTip(str(p))
        current_name.setData(Qt.UserRole, str(p))

        # create empty cell for the new (renamed) filename
        new_name = QTableWidgetItem('')

        # insert both items into the table
        self.main_window.table.setItem(row, 0, current_name)
        self.main_window.table.setItem(row, 1, new_name)

    def clear_table(self) -> None:
        """
        Deletes all rows from the file table and removes markings.

        If an undo is available, a warning is displayed beforehand and, if confirmed,
        the undo stack is emptied (the undo button is deactivated).

        **Returns:**
            `None`
        """
        # only ask if there is anything to delete
        if self.main_window.table.rowCount() > 0:
            # warn/ask only if undo is available
            if self.main_window._undo_stack:
                if not self.helpers.question_box('messages.confirm', 'messages.questions.invalidate_undo'):
                    return
                self.main_window._undo_stack.clear()

        self.main_window.table.setRowCount(0)
        self.main_window.table.clearSelection()
        self.helpers.reset_text_fields()

    def table_context_menu(self, pos) -> None:
        """
        Opens a context menu at the specified position in the table.

        Allows selected rows to be removed by right-clicking.

        **Parameters:**
            `pos` (QPoint): Position of the mouse click relative to the table

        **Returns:**
            `None`
        """
        index = self.main_window.table.indexAt(pos)

        # do nothing if the click was outside any valid row
        if not index.isValid():
            return

        # select the clicked row if it was not already selected
        if not self.main_window.table.selectionModel().isSelected(index):
            self.main_window.table.clearSelection()
            self.main_window.table.selectRow(index.row())

        # create context menu with 'Remove' action
        menu = QMenu(self.main_window)
        act_remove = menu.addAction(self.main_window._tr('context_menu.remove'))

        # execute the menu and handle selected action
        chosen = menu.exec(self.main_window.table.viewport().mapToGlobal(pos))
        if chosen == act_remove:
            self._remove_selected_rows()

    def remove_selected_rows(self) -> None:
        """
        Removes the selected lines and updates the preview.

        If an undo is available, a warning is displayed beforehand and, if confirmed,
        the undo stack is cleared (the undo button is deactivated).

        **Returns:**
            `None`
        """
        sel_row = self.main_window.table.selectionModel().selectedRows()
        if not sel_row:
            return

        # warn/ask only if undo is available
        if self.main_window._undo_stack:
            if not self.helpers.question_box('messages.confirm', 'messages.questions.invalidate_undo'):
                return
            self.main_window._undo_stack.clear()

        for idx in sorted(sel_row, key=lambda i: i.row(), reverse=True):
            self.main_window.table.removeRow(idx.row())

        # if there are no more entries -> reset input fields
        if self.main_window.table.rowCount() == 0:
            self.helpers.reset_text_fields()

        self.update_preview_later()