# -*- coding: utf-8 -*-

# Bulk Rename Py
# © 2026–present Codemorra (Christopher Kranz)
# Licensed under the MIT License (see LICENSE file)

"""Table manager module for Bulk Rename Py.

Handles table operations including drag-and-drop, resizing, preview updates,
and table cell management for the file renaming interface.
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
    """Table manager class for Bulk Rename Py.

    Handles table operations including drag-and-drop, resizing, preview updates,
    and table cell management for the file renaming interface.
    """

    def __init__(self, main_window):
        """Initialize table manager with main window reference.

        **Parameters:**
            `main_window`: Reference to main application window

        **Returns:**
            `None`
        """
        self.main_window = main_window
        self.helpers = GUIHelpers(main_window)

    def format_overlen_tooltip(self, messages: list[str]) -> str:
        """Format tooltip text from list of messages.

        **Parameters:**
            `messages` (list[str]): List of message strings

        **Returns:**
            `str`: Formatted tooltip text
        """
        # Join non-empty messages with separator
        msgs = ' / '.join(m for m in messages if m)

        return f'{msgs} ' if msgs else ''

    def style_preview_cell(self, item, invalid: bool, tooltip_text: str, fallback_name: str) -> None:
        """Style preview table cell based on validation status.

        **Parameters:**
            `item`: Table item to style
            `invalid` (bool): Whether item is invalid
            `tooltip_text` (str): Tooltip text for invalid items
            `fallback_name` (str): Fallback tooltip text

        **Returns:**
            `None`
        """
        # Set italic font for invalid items
        f = item.font()
        f.setItalic(bool(invalid))
        item.setFont(f)

        if invalid:
            # Style invalid items with red text and error tooltip
            item.setForeground(QBrush(INVALID_COLOR))
            item.setToolTip(tooltip_text or fallback_name)
        else:
            # Style valid items with default text and normal tooltip
            item.setForeground(QBrush())
            item.setToolTip(fallback_name)

    def update_preview_later(self) -> None:
        """Schedule preview update with delay.

        **Returns:**
            `None`
        """
        # Start timer for delayed preview update
        self.main_window._update_timer.start(PREVIEW_DELAY_MS)

    def eventFilter(self, obj, ev):
        """Event filter for table events.

        **Parameters:**
            `obj`: Object receiving the event
            `ev`: Event object

        **Returns:**
            `bool`: True if event was handled, False otherwise
        """
        # Handle resize events
        if obj is self.main_window.table.viewport() and ev.type() == QEvent.Resize:
            return self._handle_resize_event(ev)

        # Skip events for non-table objects
        if obj not in (self.main_window.table, self.main_window.table.viewport()):
            return super(type(self.main_window), self.main_window).eventFilter(obj, ev)

        # Handle drag enter/move events
        if ev.type() in (QEvent.DragEnter, QEvent.DragMove):
            return self._handle_drag_enter_event(ev)

        # Handle drop events
        if ev.type() == QEvent.Drop:
            return self._handle_drop_event(ev)

        # Pass unhandled events to parent
        return super(type(self.main_window), self.main_window).eventFilter(obj, ev)

    def _handle_resize_event(self, ev) -> bool:
        """Handle table resize events.

        **Parameters:**
            `ev`: Resize event

        **Returns:**
            `bool`: False to allow event propagation
        """
        # Rebalance columns on resize
        self.rebalance_on_view_resize()
        return False

    def _handle_drag_enter_event(self, ev) -> bool:
        """Handle drag enter events for table.

        **Parameters:**
            `ev`: Drag enter event

        **Returns:**
            `bool`: True if drag is accepted, False otherwise
        """
        # Accept drag if it contains URLs
        mime_data = ev.mimeData()
        if mime_data and mime_data.hasUrls():
            ev.acceptProposedAction()
            return True
        return False

    def _handle_drop_event(self, ev) -> bool:
        """Handle drop events for table.

        **Parameters:**
            `ev`: Drop event

        **Returns:**
            `bool`: True if drop was handled, False otherwise
        """
        # Extract local file paths from drop data
        mime_data = ev.mimeData()
        urls = mime_data.urls() if mime_data else []
        paths = [u.toLocalFile() for u in urls if u.isLocalFile()]

        # Process dropped paths if any
        if paths:
            return self._process_dropped_paths(paths, ev)
        return False

    def _process_dropped_paths(self, paths: list[str], ev) -> bool:
        """Process dropped file paths.

        **Parameters:**
            `paths` (list[str]): List of dropped file paths
            `ev`: Drop event

        **Returns:**
            `bool`: True if processing was successful
        """
        # Check for multiple directories
        dir_count = sum(1 for p in paths if Path(p).is_dir())
        if dir_count > 1:
            # Show warning for multiple directories
            QMessageBox.warning(
                self.main_window,
                self.main_window._tr('messages.info'),
                self.main_window._tr('messages.information.multiple_directories')
                )
            ev.ignore()
            return True

        # Accept the drop action
        ev.setDropAction(Qt.CopyAction)
        ev.accept()
        from .rename_manager import RenameManager
        # Import paths using rename manager
        rename_manager = RenameManager(self.main_window)
        rename_manager.import_from_paths(paths)
        return True

    def init_equal_columns(self) -> None:
        """Initialize table columns with equal widths.

        **Returns:**
            `None`
        """
        # Get viewport width and calculate initial column widths
        viewport_width = self.main_window.table.viewport().width()
        left_width = max(self.main_window._min_left, viewport_width // 2)
        right_width = max(self.main_window._min_right, viewport_width - left_width)

        # Adjust widths if they exceed viewport
        if left_width + right_width > viewport_width:
            left_width = max(self.main_window._min_left, min(left_width, viewport_width - self.main_window._min_right))
            right_width = viewport_width - left_width

        # Apply calculated widths
        self.set_columns(left_width, right_width)

    def set_columns(self, left_width: int, right_width: int) -> None:
        """Set table column widths.

        **Parameters:**
            `left_width` (int): Width for left column
            `right_width` (int): Width for right column

        **Returns:**
            `None`
        """
        # Temporarily block signals to prevent unnecessary updates
        self.main_window.table.blockSignals(True)
        self.main_window.table.setColumnWidth(0, left_width)
        self.main_window.table.setColumnWidth(1, right_width)
        self.main_window.table.blockSignals(False)

    def on_header_resized(self, logical_index: int, _old: int, new_width: int) -> None:
        """Handle column header resize events.

        **Parameters:**
            `logical_index` (int): Index of resized column
            `_old` (int): Old width (unused)
            `new_width` (int): New width

        **Returns:**
            `None`
        """
        # Only handle left and right columns
        if logical_index not in (0, 1):
            return

        # Get current viewport width
        viewport_width = self.main_window.table.viewport().width()

        # Calculate new column widths based on which column was resized
        if logical_index == 0:
            left_width, right_width = self._calculate_column_widths(new_width, viewport_width, is_left_column=True)
        else:
            left_width, right_width = self._calculate_column_widths(new_width, viewport_width, is_left_column=False)

        # Apply new widths
        self.set_columns(left_width, right_width)

    def _calculate_column_widths(self, changed_width: int, viewport_width: int, is_left_column: bool) -> tuple[
        int, int]:
        """Calculate new column widths after resize.

        **Parameters:**
            `changed_width` (int): Width of changed column
            `viewport_width` (int): Total viewport width
            `is_left_column` (bool): True if left column was resized

        **Returns:**
            `tuple[int, int]`: Tuple of (left_width, right_width)
        """
        # Get minimum column widths
        min_left = self.main_window._min_left
        min_right = self.main_window._min_right

        # Calculate widths based on which column was resized
        if is_left_column:
            left_width = max(min_left, min(changed_width, viewport_width - min_right))
            right_width = max(min_right, viewport_width - left_width)
        else:
            right_width = max(min_right, min(changed_width, viewport_width - min_left))
            left_width = max(min_left, viewport_width - right_width)

        return left_width, right_width

    def rebalance_on_view_resize(self) -> None:
        """Rebalance column widths when viewport is resized.

        **Returns:**
            `None`
        """
        # Get current viewport width
        viewport_width = self.main_window.table.viewport().width()
        if viewport_width <= 0:
            return

        # Get current column widths
        left_width = self.main_window.table.columnWidth(0)
        right_width = self.main_window.table.columnWidth(1)
        total_width = left_width + right_width if (left_width + right_width) > 0 else viewport_width

        # Calculate new widths maintaining ratio
        left_ratio = left_width / total_width
        new_left_width = int(round(viewport_width * left_ratio))
        new_left_width = max(self.main_window._min_left,
                             min(new_left_width, viewport_width - self.main_window._min_right))
        new_right_width = viewport_width - new_left_width

        # Ensure minimum widths are respected
        if new_right_width < self.main_window._min_right:
            new_right_width = self.main_window._min_right
            new_left_width = viewport_width - new_right_width
            new_left_width = max(self.main_window._min_left, new_left_width)

        # Apply new widths
        self.set_columns(new_left_width, new_right_width)

    def table_add_entry(self, p: Path) -> None:
        """Add file entry to table.

        **Parameters:**
            `p` (Path): Path to file to add

        **Returns:**
            `None`
        """
        try:
            # Add new row to table
            row = self.main_window.table.rowCount()
            self.main_window.table.insertRow(row)
        except Exception as e:
            # Show warning if table addition fails
            QMessageBox.warning(
                self.main_window,
                self.helpers.tr('messages.warning'),
                self.helpers.tr('messages.errors.table_add_failed').format(str(p), str(e))
            )
            return

        # Create and configure current name item
        current_name = QTableWidgetItem(p.name)
        current_name.setToolTip(str(p))
        current_name.setData(Qt.UserRole, str(p))

        # Create empty new name item
        new_name = QTableWidgetItem('')

        # Add items to table
        self.main_window.table.setItem(row, 0, current_name)
        self.main_window.table.setItem(row, 1, new_name)

    def clear_table(self) -> None:
        """Clear all entries from table.

        **Returns:**
            `None`
        """
        # Check if undo stack needs to be cleared
        if self.main_window.table.rowCount() > 0:
            if self.main_window._undo_stack:
                if not self.helpers.question_box('messages.confirm', 'messages.questions.invalidate_undo'):
                    return
                self.main_window._undo_stack.clear()

        # Clear table and reset UI
        self.main_window.table.setRowCount(0)
        self.main_window.table.clearSelection()
        self.helpers.reset_text_fields()

    def table_context_menu(self, pos) -> None:
        """Show context menu for table.

        **Parameters:**
            `pos`: Position where context menu was requested

        **Returns:**
            `None`
        """
        # Get index at click position
        index = self.main_window.table.indexAt(pos)

        if not index.isValid():
            return

        # Select row if not already selected
        if not self.main_window.table.selectionModel().isSelected(index):
            self.main_window.table.clearSelection()
            self.main_window.table.selectRow(index.row())

        # Create and show context menu
        menu = QMenu(self.main_window)
        act_remove = menu.addAction(self.main_window._tr('context_menu.remove'))

        chosen = menu.exec(self.main_window.table.viewport().mapToGlobal(pos))
        if chosen == act_remove:
            # Remove selected rows if remove action was chosen
            self._remove_selected_rows()

    def remove_selected_rows(self) -> None:
        """Remove selected rows from table.

        **Returns:**
            `None`
        """
        # Get selected rows
        sel_row = self.main_window.table.selectionModel().selectedRows()
        if not sel_row:
            return

        # Check if undo stack needs to be cleared
        if self.main_window._undo_stack:
            if not self.helpers.question_box('messages.confirm', 'messages.questions.invalidate_undo'):
                return
            self.main_window._undo_stack.clear()

        # Remove rows in reverse order to maintain correct indices
        for idx in sorted(sel_row, key=lambda i: i.row(), reverse=True):
            self.main_window.table.removeRow(idx.row())

        if self.main_window.table.rowCount() == 0:
            self.helpers.reset_text_fields()

        self.update_preview_later()