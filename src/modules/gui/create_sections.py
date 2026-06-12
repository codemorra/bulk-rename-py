# -*- coding: utf-8 -*-

# Bulk Rename Py
# © 2026–present Codemorra (Christopher Kranz)
# Licensed under the MIT License (see LICENSE file)

"""Create sections module for Bulk Rename Py.

Handles creation of UI sections including rename, extension, replace,
counter, and advanced options sections for the bulk file renaming application.
"""

from __future__ import annotations
import os
import re
import sys
import tempfile
import webbrowser
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QUrl, QEvent
from PySide6.QtGui import (
    QAction, QActionGroup, QKeySequence,
    QDesktopServices, QBrush, QColor, QFontDatabase, QFont
    )
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QPushButton, QCheckBox, QLineEdit, QSpinBox, QComboBox, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QGridLayout, QLayout, QMessageBox,
    QFileDialog, QMenu, QSizePolicy, QPlainTextEdit, QSpacerItem,
    QDialog, QDialogButtonBox, QStyle, QTableWidget
)

# Constants
MIN_WINDOW_WIDTH = 1
DEFAULT_WINDOW_SIZE = (1280, 800)


# style for the GUI sections
GROUPBOX_STYLE = """
QGroupBox {
    font-weight: 600;
    border: 1px solid palette(mid);
    border-radius: 6px;
    margin-top: 8px;
    padding: 6px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}
"""


class CreateSections:
    """Create sections class for Bulk Rename Py.

    Handles creation of UI sections including rename, extension, replace,
    counter, and advanced options sections for the bulk file renaming application.
    """
    def __init__(self, parent):
        """Initialize create sections with parent reference.

        **Parameters:**
            `parent`: Reference to parent object

        **Returns:**
            `None`
        """
        self.parent = parent
        self.cfg = parent.cfg
        self.helpers = parent.helpers
        self.rename_manager = parent.rename_manager
        self.table_manager = parent.table_manager

    def rename_section(self) -> QGroupBox:
        """Create rename section with file name input and date/time options.

        **Returns:**
            `QGroupBox`: Configured rename section
        """
        box = QGroupBox(self.helpers.tr('sections.rename.title'))
        layout = QVBoxLayout(box)
        layout.setAlignment(Qt.AlignTop)

        # Input field for the file name
        self.parent.edit_mask = QLineEdit()
        self.parent.edit_mask.setText('{name}')
        layout.addWidget(self.parent.edit_mask)

        # Button row for renaming options
        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignLeft)

        self.parent.btn_name = QPushButton('{name}')
        self.parent.btn_name_slice = QPushButton('{name1-3}')
        self.parent.btn_counter = QPushButton('{counter}')
        self.parent.btn_date = QPushButton('{date}')
        self.parent.btn_time = QPushButton('{time}')

        for b in (self.parent.btn_name, self.parent.btn_name_slice, self.parent.btn_counter, self.parent.btn_date, self.parent.btn_time):
            btn_row.addWidget(b)
            b.setFixedSize(80, 28)
            b.setFocusPolicy(Qt.NoFocus)

        layout.addLayout(btn_row)

        # Date row
        date_row = QHBoxLayout()
        date_row.setAlignment(Qt.AlignLeft)

        # Date format label
        lbl_date = QLabel(self.helpers.tr('sections.rename.lbl_datefmt'))

        # Date format combobox
        self.parent.cmb_date = QComboBox()
        self.parent.cmb_date.addItems(['YYYYMMDD', 'DDMMYYYY', 'MMDDYYYY', 'YYYYMM', 'MMYYYY', 'YYYY'])
        self.parent.cmb_date.setMaximumWidth(120)

        # Date separator label
        lbl_date_sep = QLabel(self.helpers.tr('sections.rename.lbl_sep'))

        # Date separator combobox
        self.parent.cmb_date_sep = QComboBox()
        self.parent.cmb_date_sep.addItem('-', '-')
        self.parent.cmb_date_sep.addItem('_', '_')
        self.parent.cmb_date_sep.addItem('.', '.')
        if not self.helpers.is_windows():  # Add colon only on non-Windows systems
            self.parent.cmb_date_sep.addItem(':', ':')
        self.parent.cmb_date_sep.addItem(';', ';')
        self.parent.cmb_date_sep.addItem(self.helpers.tr('sections.rename.sep_none'), 'none')
        self.parent.cmb_date_sep.addItem(self.helpers.tr('sections.rename.sep_space'), 'space')

        for i in (lbl_date, self.parent.cmb_date, lbl_date_sep, self.parent.cmb_date_sep):
            date_row.addWidget(i)

        layout.addLayout(date_row)

        # Time row
        time_row = QHBoxLayout()
        time_row.setAlignment(Qt.AlignLeft)

        # Time format label
        lbl_time = QLabel(self.helpers.tr('sections.rename.lbl_timefmt'))

        # Time format combobox
        self.parent.cmb_time = QComboBox()
        self.parent.cmb_time.addItems(['HHMMSS', 'HHMM', 'HH'])
        self.parent.cmb_time.setMaximumWidth(120)

        # Time separator label
        lbl_time_sep = QLabel(self.helpers.tr('sections.rename.lbl_sep'))

        # Time separator combobox
        self.parent.cmb_time_sep = QComboBox()
        self.parent.cmb_time_sep.addItem('-', '-')
        self.parent.cmb_time_sep.addItem('_', '_')
        self.parent.cmb_time_sep.addItem('.', '.')
        if not self.helpers.is_windows():  # Add colon only on non-Windows systems
            self.parent.cmb_time_sep.addItem(':', ':')
        self.parent.cmb_time_sep.addItem(';', ';')
        self.parent.cmb_time_sep.addItem(self.helpers.tr('sections.rename.sep_none'), 'none')
        self.parent.cmb_time_sep.addItem(self.helpers.tr('sections.rename.sep_space'), 'space')

        for i in (lbl_time, self.parent.cmb_time, lbl_time_sep, self.parent.cmb_time_sep):
            time_row.addWidget(i)

        layout.addLayout(time_row)

        # Datetype row
        datetype_row = QHBoxLayout()
        datetype_row.setAlignment(Qt.AlignLeft)

        # Datetype label
        lbl_datetype = QLabel(self.helpers.tr('sections.rename.date_type'))

        # Datetype combobox
        self.parent.cmb_datetype = QComboBox()
        self.parent.cmb_datetype.addItem(self.helpers.tr('sections.rename.date_current'), 'current')
        self.parent.cmb_datetype.addItem(self.helpers.tr('sections.rename.date_change'), 'change')

        for i in (lbl_datetype, self.parent.cmb_datetype):
            datetype_row.addWidget(i)

        layout.addLayout(datetype_row)

        # Loads values from the config
        self.parent.cmb_date.setCurrentText(self.cfg.get('rename', 'date_format', fallback='YYYYMMDD'))
        self.parent.cmb_time.setCurrentText(self.cfg.get('rename', 'time_format', fallback='HHMM'))
        self.helpers.set_combo_by_data(self.parent.cmb_date_sep, self.cfg.get('rename', 'date_seperator', fallback='-'))
        self.helpers.set_combo_by_data(self.parent.cmb_time_sep, self.cfg.get('rename', 'time_seperator', fallback='-'))
        self.helpers.set_combo_by_data(self.parent.cmb_datetype, self.cfg.get('rename', 'date_type', fallback='current'))

        # Saves values in the config
        self.parent.cmb_date.currentTextChanged.connect(
            lambda _: self.rename_manager.handle_config_change('rename', 'date_format', self.parent.cmb_date.currentText()))
        self.parent.cmb_time.currentTextChanged.connect(
            lambda _: self.rename_manager.handle_config_change('rename', 'time_format', self.parent.cmb_time.currentText()))
        self.parent.cmb_date_sep.currentIndexChanged.connect(
            lambda _: self.rename_manager.handle_config_change('rename', 'date_seperator', self.parent.cmb_date_sep.currentData()))
        self.parent.cmb_time_sep.currentIndexChanged.connect(
            lambda _: self.rename_manager.handle_config_change('rename', 'time_seperator', self.parent.cmb_time_sep.currentData()))
        self.parent.cmb_datetype.currentIndexChanged.connect(
            lambda _: self.rename_manager.handle_config_change('rename', 'date_type', self.parent.cmb_datetype.currentData()))

        # Refresh preview when the input field is updated
        self.parent.edit_mask.textChanged.connect(lambda: self.table_manager.update_preview_later())

        # Style settings
        layout.addStretch(1)
        box.setStyleSheet(GROUPBOX_STYLE)

        return box

    def extension_section(self) -> QGroupBox:
        """Create extension section with extension input and buttons.

        **Returns:**
            `QGroupBox`: Configured extension section
        """
        box = QGroupBox(self.helpers.tr('sections.extension.title'))
        layout = QVBoxLayout(box)
        layout.setAlignment(Qt.AlignTop)

        # Input field for the file extension
        self.parent.edit_ext = QLineEdit()
        self.parent.edit_ext.setText('{ext}')
        layout.addWidget(self.parent.edit_ext)

        # Button row for {ext} and {ext1-3}
        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignLeft)

        self.parent.btn_ext = QPushButton('{ext}')
        self.parent.btn_ext_slice = QPushButton('{ext1-3}')

        for b in (self.parent.btn_ext, self.parent.btn_ext_slice):
            b.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)  # (x, y)
            b.setFocusPolicy(Qt.NoFocus)
            btn_row.addWidget(b)
            b.setFixedSize(75, 28)

        layout.addLayout(btn_row)

        # {counter} button below
        self.parent.btn_ext_counter = QPushButton('{counter}')

        layout.addWidget(self.parent.btn_ext_counter)

        # Click handler - will be connected in __init__ after all UI elements are created

        # Refresh preview when the input field is updated
        self.parent.edit_ext.textChanged.connect(lambda: self.table_manager.update_preview_later())

        # Style settings
        box.setStyleSheet(GROUPBOX_STYLE)

        return box

    def replace_section(self) -> QGroupBox:
        """Create replace section with search/replace functionality.

        **Returns:**
            `QGroupBox`: Configured replace section
        """
        box = QGroupBox(self.helpers.tr('sections.replace.title'))
        layout = QVBoxLayout(box)
        layout.setAlignment(Qt.AlignTop)

        # Search & replace grid
        grid = QGridLayout()

        lbl_search = QLabel(self.helpers.tr('sections.replace.lbl_search'))
        self.parent.edit_search = QLineEdit()
        self.parent.edit_search.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        lbl_replace = QLabel(self.helpers.tr('sections.replace.lbl_replace'))
        self.parent.edit_replace = QLineEdit()
        self.parent.edit_replace.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        grid.addWidget(lbl_search, 0, 0)
        grid.addWidget(self.parent.edit_search, 0, 1)
        grid.addWidget(lbl_replace, 1, 0)
        grid.addWidget(self.parent.edit_replace, 1, 1)

        grid.setColumnStretch(0, 0)  # Labels
        grid.setColumnStretch(1, 1)  # Input fields

        layout.addLayout(grid)

        # Upper checkbox row
        upper_opt_row = QHBoxLayout()
        upper_opt_row.setAlignment(Qt.AlignLeft)

        self.parent.cb_regex = QCheckBox(self.helpers.tr('sections.replace.cb_regex'))
        self.parent.cb_first_match = QCheckBox(self.helpers.tr('sections.replace.cb_first_match'))
        self.parent.cb_exact_match = QCheckBox(self.helpers.tr('sections.replace.cb_exact_matches'))

        for c in (self.parent.cb_regex, self.parent.cb_first_match, self.parent.cb_exact_match):
            upper_opt_row.addWidget(c)

        layout.addLayout(upper_opt_row)

        # Lower checkbox row
        lower_opt_row = QHBoxLayout()
        lower_opt_row.setAlignment(Qt.AlignLeft)

        self.parent.cb_case_sens = QCheckBox(self.helpers.tr('sections.replace.cb_case_sens'))
        self.parent.cb_ignore_ext = QCheckBox(self.helpers.tr('sections.replace.cb_ignore_ext'))

        for c in (self.parent.cb_case_sens, self.parent.cb_ignore_ext):
            lower_opt_row.addWidget(c)

        layout.addLayout(lower_opt_row)

        # Loads values from the config
        self.parent.cb_regex.setChecked(self.cfg.getboolean('replace', 'regex', fallback=False))
        self.parent.cb_first_match.setChecked(self.cfg.getboolean('replace', 'only_first_match', fallback=False))
        self.parent.cb_exact_match.setChecked(self.cfg.getboolean('replace', 'exact_match', fallback=False))
        self.parent.cb_case_sens.setChecked(self.cfg.getboolean('replace', 'case_sensitive', fallback=False))
        self.parent.cb_ignore_ext.setChecked(self.cfg.getboolean('replace', 'exclude_extension', fallback=True))

        # Saves values in the config
        self.parent.cb_regex.toggled.connect(
            lambda v: self.rename_manager.handle_config_change('replace', 'regex', v))
        self.parent.cb_first_match.toggled.connect(
            lambda v: self.rename_manager.handle_config_change('replace', 'only_first_match', v))
        self.parent.cb_exact_match.toggled.connect(
            lambda v: self.rename_manager.handle_config_change('replace', 'exact_match', v))
        self.parent.cb_case_sens.toggled.connect(
            lambda v: self.rename_manager.handle_config_change('replace', 'case_sensitive', v))
        self.parent.cb_ignore_ext.toggled.connect(
            lambda v: self.rename_manager.handle_config_change('replace', 'exclude_extension', v))

        # Refresh preview when the input field is updated
        self.parent.edit_search.textChanged.connect(lambda: self.table_manager.update_preview_later())
        self.parent.edit_replace.textChanged.connect(lambda: self.table_manager.update_preview_later())

        # Style settings
        layout.addStretch(1)
        box.setStyleSheet(GROUPBOX_STYLE)

        return box

    def counter_section(self) -> QGroupBox:
        """Create counter section with counter configuration options.

        **Returns:**
            `QGroupBox`: Configured counter section
        """
        box = QGroupBox(self.helpers.tr('sections.counter.title'))
        layout = QVBoxLayout(box)

        # Help function for creating spin boxes
        def add_counter_row(label_text: str, section: str, key: str,
                            minimum: int, maximum: int, width=70) -> QSpinBox:
            row_layout = QHBoxLayout()

            label = QLabel(label_text)
            label.setAlignment(Qt.AlignLeft)

            spinbox = QSpinBox()
            spinbox.setRange(minimum, maximum)
            spinbox.setValue(self.cfg.getint(section, key))
            spinbox.setFixedWidth(width)
            spinbox.setAlignment(Qt.AlignRight)

            row_layout.addWidget(label)
            row_layout.addStretch(1)
            row_layout.addWidget(spinbox, alignment=Qt.AlignRight)

            layout.addLayout(row_layout)

            return spinbox

        # Calls the help function for creating the individual spin boxes
        self.parent.spin_start = add_counter_row(
            self.helpers.tr('sections.counter.lbl_start'), 'counter', 'start', 0, 999999)
        self.parent.spin_step = add_counter_row(
            self.helpers.tr('sections.counter.lbl_step'), 'counter', 'step', 1, 9999)
        self.parent.spin_digits = add_counter_row(
            self.helpers.tr('sections.counter.lbl_digits'), 'counter', 'digits', 1, 10, 45)

        # Checkbox for inversion
        self.parent.cb_dupes = QCheckBox(self.helpers.tr('sections.counter.dupes'))
        self.parent.cb_dupes.setChecked(self.cfg.getboolean('counter', 'dupes_only', fallback=False))
        layout.addWidget(self.parent.cb_dupes)

        # Saves the current values in the config
        self.parent.spin_start.valueChanged.connect(
            lambda v: self.rename_manager.handle_config_change('counter', 'start', v))
        self.parent.spin_step.valueChanged.connect(
            lambda v: self.rename_manager.handle_config_change('counter', 'step', v))
        self.parent.spin_digits.valueChanged.connect(
            lambda v: self.rename_manager.handle_config_change('counter', 'digits', v))
        self.parent.cb_dupes.toggled.connect(
            lambda v: self.rename_manager.handle_config_change('counter', 'dupes_only', v))

        # Style settings
        layout.addStretch(1)
        box.setStyleSheet(GROUPBOX_STYLE)

        return box

    def advanced_options_section(self) -> QGroupBox:
        """Create advanced options section with case and editor options.

        **Returns:**
            `QGroupBox`: Configured advanced options section
        """
        box = QGroupBox(self.helpers.tr('sections.advanced_opts.title'))
        layout = QVBoxLayout(box)
        layout.setAlignment(Qt.AlignTop)
        layout.setContentsMargins(8, 0, 8, 0)  # Smaller gap at the top and bottom

        # Row for the options
        row = QHBoxLayout()
        row.setAlignment(Qt.AlignLeft)

        # Upper/lower case
        lbl_case = QLabel(self.helpers.tr('sections.advanced_opts.lbl_case'))
        self.parent.cmb_case = QComboBox()
        self.parent.cmb_case.addItem(self.helpers.tr('sections.advanced_opts.case_values.unchanged'), 'unchanged')
        self.parent.cmb_case.addItem(self.helpers.tr('sections.advanced_opts.case_values.lowercase'), 'lowercase')
        self.parent.cmb_case.addItem(self.helpers.tr('sections.advanced_opts.case_values.uppercase'), 'uppercase')
        self.parent.cmb_case.addItem(self.helpers.tr('sections.advanced_opts.case_values.heading'), 'heading')
        self.parent.cmb_case.addItem(self.helpers.tr('sections.advanced_opts.case_values.mocking'), 'mocking')

        # Windows-compatible names
        self.parent.cb_windows = QCheckBox(self.helpers.tr('sections.advanced_opts.cb_windows'))
        self.parent.cb_windows.setChecked(
            True if self.helpers.is_windows() else self.cfg.getboolean('advanced', 'windows_names', fallback=False))

        # On Windows: gray out the checkbox and force it to be active
        if self.helpers.is_windows():
            self.parent.cb_windows.setEnabled(False)

        # Open in editor
        self.parent.btn_editor = QPushButton(self.helpers.tr('sections.advanced_opts.btn_editor'))

        row.addWidget(lbl_case)
        row.addWidget(self.parent.cmb_case)
        row.addStretch(1)
        row.addWidget(self.parent.cb_windows)
        row.addStretch(1)
        row.addWidget(self.parent.btn_editor, alignment=Qt.AlignRight)

        layout.addLayout(row)

        # Loads values from the config
        self.helpers.set_combo_by_data(self.parent.cmb_case, self.cfg.get('advanced', 'case', fallback='unchanged'))
        self.parent.cb_windows.setChecked(self.cfg.getboolean('advanced', 'windows_names', fallback=False))

        # Saves values in the config
        self.parent.cmb_case.currentIndexChanged.connect(
            lambda _: self.rename_manager.handle_config_change('advanced', 'case', self.parent.cmb_case.currentData()))
        self.parent.cb_windows.toggled.connect(
            lambda v: self.rename_manager.handle_config_change('advanced', 'windows_names', v))

        # Click handler
        self.parent.btn_editor.clicked.connect(lambda: self.rename_manager.open_in_editor())

        # Style settings
        box.setStyleSheet(GROUPBOX_STYLE)

        return box
