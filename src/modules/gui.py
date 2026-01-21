# -*- coding: utf-8 -*-

# Bulk Rename Py
# © 2026–present Codemorra
# Licensed under the MIT License (see LICENSE file)

"""
GUI module for Bulk Rename Py.

Provides the main window with all GUI functions.
"""

from __future__ import annotations
import os
import re
import sys
import tempfile
import webbrowser
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QUrl, QTimer, QEvent
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
from .i18n import Translator
from .importer import ImportOptions, collect
from .renamer import (
    RenameCfg, DateTimeCfg, CounterCfg, ReplaceCfg, CaseCfg, MaskCfg,
    preview_names, validate_windows_length, validate_linux_bytes, plan_moves,
    check_conflicts, perform_rename, undo_moves
)
from .settings import (
    get_config, get_language_from_config, set_language_in_config,
    set_cfg, ensure_config_file, reset_config, CONFIG_FILE
    )
from .update_checker import UpdateChecker
from .metadata import APP_INFO


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


# --- Main window ---
class MainWindow(QMainWindow):
    """
    Main window of the application.

    Contains:
    - Menu bar with import function, language settings, About dialog, and an option to reset settings.
    - Various sections for customizing file names.
    - A table comparing the old file names with the new ones in real time.
    - Functions for renaming and undoing.
    """
    MIN_WIDTH = 1

    def __init__(self) -> None:
        """
        Initializes the main window.

        Loads saved configurations and language, creates the basic layout,
        initializes timers and the table view, and ensures that all GUI
        interactions are connected correctly.

        **Returns:**
            `None`
        """
        super().__init__()

        # -- preparations --
        # load config + language
        ensure_config_file()
        self.cfg = get_config()
        self.translator = Translator(get_language_from_config())

        # always enforce Windows-compatible names in Windows
        if self._is_windows():
            if (not self.cfg.has_section('advanced')) or (not self.cfg.getboolean('advanced', 'windows_names', fallback=False)):
                if not self.cfg.has_section('advanced'):
                    self.cfg.add_section('advanced')
                self.cfg.set('advanced', 'windows_names', 'True')
                with CONFIG_FILE.open('w', encoding='utf-8') as f:
                    self.cfg.write(f)

        # timer for delayed preview of new file names
        self._update_timer = QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.timeout.connect(self._update_preview_now)

        # variable for multi-level in-memory undo
        self._undo_stack: list[list[tuple[Path, Path]]] = []

        # window setup
        self.setWindowTitle(self._tr('app'))
        self.resize(1280, 800)

        # --- menu bar ---
        menubar = self.menuBar()
        menu_file = menubar.addMenu(self._tr('menu.file'))
        menu_file.setToolTipsVisible(True)

        # import single/multiple files
        self.act_add_files = QAction(self._tr('menu.add_files'), self)
        self.act_add_files.setShortcut('Ctrl+O')
        self.act_add_files.triggered.connect(self._action_open_files)
        menu_file.addAction(self.act_add_files)

        # import entire directories
        self.act_add_folder = QAction(self._tr('menu.add_folder'), self)
        self.act_add_folder.setShortcut('Ctrl+Shift+O')
        self.act_add_folder.triggered.connect(self._action_open_folder)
        menu_file.addAction(self.act_add_folder)

        menu_file.addSeparator()

        # include hidden files checkbox
        self.act_hidden = QAction(self._tr('menu.show_hidden'), self, checkable=True)
        self.act_hidden.setChecked(self.cfg.getboolean('general', 'hidden_files', fallback=False))
        self.act_hidden.toggled.connect(lambda v: set_cfg('general', 'hidden_files', v))
        menu_file.addAction(self.act_hidden)

        # language selection
        menu_lang = menu_file.addMenu(self._tr('menu.language'))
        lang_group = QActionGroup(self)
        lang_group.setExclusive(True)
        act_lang_en = QAction(self._tr('menu.lang_list.english'), self, checkable=True)
        act_lang_de = QAction(self._tr('menu.lang_list.german'),  self, checkable=True)
        lang_group.addAction(act_lang_en)
        lang_group.addAction(act_lang_de)
        current_lang = self.cfg.get('general', 'language', fallback='en')
        act_lang_en.setChecked(current_lang == 'en')
        act_lang_de.setChecked(current_lang == 'de')
        act_lang_en.triggered.connect(lambda: self._set_language('en'))
        act_lang_de.triggered.connect(lambda: self._set_language('de'))
        menu_lang.addAction(act_lang_en)
        menu_lang.addAction(act_lang_de)

        menu_file.addSeparator()

        # reset settings option
        self.act_reset = QAction(self._tr('menu.reset_settings'), self)
        self.act_reset.triggered.connect(self._reset_all_settings)
        menu_file.addAction(self.act_reset)

        menu_file.addSeparator()

        # about
        self.act_about = QAction(self._tr('menu.about'), self)
        self.act_about.triggered.connect(self._show_about_dialog)
        menu_file.addAction(self.act_about)

        menu_file.addSeparator()

        # exit option
        self.act_exit = QAction(self._tr('menu.exit'), self)
        self.act_exit.setShortcut('Ctrl+Q')
        self.act_exit.triggered.connect(self.close)
        menu_file.addAction(self.act_exit)

        # --- creates the main layout ---
        # central widget with vertical main layout
        central = QWidget(self)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        grid = QGridLayout()
        root.addLayout(grid)

        # create sections
        rename_box = self._make_section_rename()
        ext_box = self._make_section_extension()
        search_box = self._make_section_replace()
        counter_box = self._make_section_counter()
        advanced_opts = self._make_section_advanced_options()

        # create a table (two columns: current name, new name)
        self.table = QTableWidget(0, 2, self)
        self.table.setHorizontalHeaderLabels([
            self._tr('table.current_name'),
            self._tr('table.new_name')
        ])

        # drag & drop
        self.table.setAcceptDrops(True)
        self.table.viewport().setAcceptDrops(True)
        self.table.setDragDropMode(QAbstractItemView.DropOnly)
        self.table.setDropIndicatorShown(True)
        self.table.installEventFilter(self)
        self.table.viewport().installEventFilter(self)

        # lower buttons row
        button_row = QHBoxLayout()

        # clear list
        self.btn_clear = QPushButton(self._tr('actions.clear_list'))
        self.btn_clear.clicked.connect(self._clear_table)
        button_row.addWidget(self.btn_clear, alignment=Qt.AlignLeft)

        button_row.addStretch(1)

        # rename
        self.btn_rename = QPushButton(self._tr('actions.rename'))
        self.btn_rename.clicked.connect(self._perform_rename)
        button_row.addWidget(self.btn_rename)

        # undo
        self.btn_undo = QPushButton(self._tr('actions.undo'))
        self.btn_undo.clicked.connect(self._perform_undo)
        button_row.addWidget(self.btn_undo)

        # --- table configuration ---
        hdr = self.table.horizontalHeader()

        # both columns interactive
        for i in (0, 1):
            hdr.setSectionResizeMode(i, QHeaderView.Interactive)
        hdr.setStretchLastSection(False)

        # define minimum widths
        self._min_left = 160
        self._min_right = 160
        hdr.setMinimumSectionSize(min(self._min_left, self._min_right))

        # connect events
        hdr.sectionResized.connect(self._on_header_resized)

        # balancing columns during viewport resize
        self.table.viewport().installEventFilter(self)

        # set initial 50/50
        QTimer.singleShot(0, self._init_equal_columns)

        # selection and editing behavior
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)  # entire lines can be selected
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)  # multiple selections allowed
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)  # no direct processing
        self.table.setFocusPolicy(Qt.StrongFocus)

        # presentation and layout
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)  # scrollbar always visible
        self.table.verticalHeader().setVisible(False)  # hide line numbers
        self.table.setSortingEnabled(False)  # no sortable columns
        self.table.setAlternatingRowColors(True)  # alternating background colors for better readability
        self.table.setWordWrap(False)  # disable line break
        self.table.setTextElideMode(Qt.ElideMiddle)   # shorten long names in the middle (...)
        vh = self.table.verticalHeader()
        vh.setDefaultSectionSize(22)  # set standard line height to 22 pixels
        vh.setMinimumSectionSize(18)  # minimum line height (to prevent excessive compression)

        # context menu and keyboard shortcut
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._table_context_menu)

        # remove using the delete key
        act_del = QAction(self)
        act_del.setShortcut(QKeySequence.Delete)
        act_del.triggered.connect(self._remove_selected_rows)
        self.table.addAction(act_del)

        # --- layout, size, and behavior of GUI elements ---
        # behavior of the upper sections
        rename_box.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        ext_box.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        search_box.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        counter_box.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)

        # table should grow in both directions
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  # (x, y)

        # grid arrangement
        grid.addWidget(rename_box,    0, 0, 2, 1)
        grid.addWidget(ext_box,       0, 1, 1, 1)
        grid.addWidget(search_box,    0, 2, 1, 1)
        grid.addWidget(counter_box,   0, 3, 1, 1)
        grid.addWidget(advanced_opts, 1, 1, 1, 3)

        stretch_right = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)
        grid.addItem(stretch_right, 0, 4, 2, 1)
        grid.setColumnStretch(4, 1)

        grid.addWidget(self.table,   2, 0, 1, 5)
        grid.addLayout(button_row,   3, 0, 1, 5)

        # columns stretch
        grid.setColumnStretch(0, 0)  # rename_box
        grid.setColumnStretch(1, 0)  # ext_box
        grid.setColumnStretch(2, 0)  # search_box
        grid.setColumnStretch(3, 0)  # counter_box

        # rows strech
        grid.setRowStretch(0, 0)  # upper sections
        grid.setRowStretch(1, 0)  # special options
        grid.setRowStretch(2, 1)  # table
        grid.setRowStretch(3, 0)  # bottom button row

        grid.setVerticalSpacing(5)
        grid.setHorizontalSpacing(5)

        # window size must not be smaller than the minimum layout
        root.setSizeConstraint(QLayout.SetMinimumSize)

        # save calculated minimum window width
        self.MIN_WIDTH = self.minimumSizeHint().width()

        # trigger initial (empty) preview
        self._update_preview_later()

        # disable undo if no undo log is present
        self._update_undo_state()

        # applies tooltips
        self._apply_tooltips()

        self.resize(self.MIN_WIDTH, self.height())

    def _make_section_rename(self) -> QGroupBox:
        """
        Creates the section for customizing the actual file name.

        Contains:
        - The input field for the file name
        - Placeholder buttons:
            - `{name}` = current file name
            - `{name1-3}` = part of the current file name (e.g., `{name5-*}` results in `filename` = `name`
            - `{counter}` = defined counter
            - `{date}` = the current or creation date
            - `{time}` = the current or creation time
        - Options for setting the date and time information

        **Returns:**
            `QGroupBox`: Widget with all controls of the renaming area
        """
        box = QGroupBox(self._tr('sections.rename.title'))
        layout = QVBoxLayout(box)
        layout.setAlignment(Qt.AlignTop)

        # input field for the file name
        self.edit_mask = QLineEdit()
        self.edit_mask.setText('{name}')
        layout.addWidget(self.edit_mask)

        # button row for renaming options
        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignLeft)

        self.btn_name = QPushButton('{name}')
        self.btn_name_slice = QPushButton('{name1-3}')
        self.btn_counter = QPushButton('{counter}')
        self.btn_date = QPushButton('{date}')
        self.btn_time = QPushButton('{time}')

        for b in (self.btn_name, self.btn_name_slice, self.btn_counter, self.btn_date, self.btn_time):
            btn_row.addWidget(b)
            b.setFixedSize(80, 28)
            b.setFocusPolicy(Qt.NoFocus)

        layout.addLayout(btn_row)

        # click handler
        self.btn_name.clicked.connect(lambda: self._insert_token(self.edit_mask, '{name}'))
        self.btn_name_slice.clicked.connect(lambda: self._insert_token(self.edit_mask, '{name1-3}'))
        self.btn_counter.clicked.connect(lambda: self._insert_token(self.edit_mask, '{counter}'))
        self.btn_date.clicked.connect(lambda: self._insert_token(self.edit_mask, '{date}'))
        self.btn_time.clicked.connect(lambda: self._insert_token(self.edit_mask, '{time}'))

        # date row
        date_row = QHBoxLayout()
        date_row.setAlignment(Qt.AlignLeft)

        # date format label
        lbl_date = QLabel(self._tr('sections.rename.lbl_datefmt'))

        # date format combobox
        self.cmb_date = QComboBox()
        self.cmb_date.addItems(['YYYYMMDD', 'DDMMYYYY', 'MMDDYYYY'])
        self.cmb_date.setMaximumWidth(120)

        # date seperator label
        lbl_date_sep = QLabel(self._tr('sections.rename.lbl_sep'))

        # date seperator combobox
        self.cmb_date_sep = QComboBox()
        self.cmb_date_sep.addItem('-', '-')
        self.cmb_date_sep.addItem('_', '_')
        self.cmb_date_sep.addItem('.', '.')
        if not self._is_windows():  # add colon only on non-Windows systems
            self.cmb_date_sep.addItem(':', ':')
        self.cmb_date_sep.addItem(';', ';')
        self.cmb_date_sep.addItem(self._tr('sections.rename.sep_none'), 'none')
        self.cmb_date_sep.addItem(self._tr('sections.rename.sep_space'), 'space')

        for i in (lbl_date, self.cmb_date, lbl_date_sep, self.cmb_date_sep):
            date_row.addWidget(i)

        layout.addLayout(date_row)

        # time row
        time_row = QHBoxLayout()
        time_row.setAlignment(Qt.AlignLeft)

        # time format label
        lbl_time = QLabel(self._tr('sections.rename.lbl_timefmt'))

        # time format combobxo
        self.cmb_time = QComboBox()
        self.cmb_time.addItems(['HHMMSS', 'HHMM', 'HH'])
        self.cmb_time.setMaximumWidth(120)

        # time seperator label
        lbl_time_sep = QLabel(self._tr('sections.rename.lbl_sep'))

        # time seperator combobox
        self.cmb_time_sep = QComboBox()
        self.cmb_time_sep.addItem('-', '-')
        self.cmb_time_sep.addItem('_', '_')
        self.cmb_time_sep.addItem('.', '.')
        if not self._is_windows():  # add colon only on non-Windows systems
            self.cmb_time_sep.addItem(':', ':')
        self.cmb_time_sep.addItem(';', ';')
        self.cmb_time_sep.addItem(self._tr('sections.rename.sep_none'), 'none')
        self.cmb_time_sep.addItem(self._tr('sections.rename.sep_space'), 'space')

        for i in (lbl_time, self.cmb_time, lbl_time_sep, self.cmb_time_sep):
            time_row.addWidget(i)

        layout.addLayout(time_row)

        # datetype row
        datetype_row = QHBoxLayout()
        datetype_row.setAlignment(Qt.AlignLeft)

        # datetype label
        lbl_datetype = QLabel(self._tr('sections.rename.date_type'))

        # datetype combobox
        self.cmb_datetype = QComboBox()
        self.cmb_datetype.addItem(self._tr('sections.rename.date_current'), 'current')
        self.cmb_datetype.addItem(self._tr('sections.rename.date_change'), 'change')

        for i in (lbl_datetype, self.cmb_datetype):
            datetype_row.addWidget(i)

        layout.addLayout(datetype_row)

        # loads values from the config
        self.cmb_date.setCurrentText(self.cfg.get('rename', 'date_format', fallback='YYYYMMDD'))
        self.cmb_time.setCurrentText(self.cfg.get('rename', 'time_format', fallback='HHMM'))
        self._set_combo_by_data(self.cmb_date_sep, self.cfg.get('rename', 'date_seperator', fallback='-'))
        self._set_combo_by_data(self.cmb_time_sep, self.cfg.get('rename', 'time_seperator', fallback='-'))
        self._set_combo_by_data(self.cmb_datetype, self.cfg.get('rename', 'date_type', fallback='current'))

        # saves values in the config
        self.cmb_date.currentTextChanged.connect(
            lambda _: self._handle_config_change('rename', 'date_format', self.cmb_date.currentText()))
        self.cmb_time.currentTextChanged.connect(
            lambda _: self._handle_config_change('rename', 'time_format', self.cmb_time.currentText()))
        self.cmb_date_sep.currentIndexChanged.connect(
            lambda _: self._handle_config_change('rename', 'date_seperator', self.cmb_date_sep.currentData()))
        self.cmb_time_sep.currentIndexChanged.connect(
            lambda _: self._handle_config_change('rename', 'time_seperator', self.cmb_time_sep.currentData()))
        self.cmb_datetype.currentIndexChanged.connect(
            lambda _: self._handle_config_change('rename', 'date_type', self.cmb_datetype.currentData()))

        # refresh preview when the input field is updated
        self.edit_mask.textChanged.connect(self._update_preview_later)

        # style settings
        layout.addStretch(1)
        box.setStyleSheet(GROUPBOX_STYLE)

        return box

    def _make_section_extension(self) -> QGroupBox:
        """
        Creates the section for customizing the file extension.

        Contains:
        - The input field for the file extension
        - Placeholder buttons:
            - `{ext}` = current file extension
            - `{name1-3}` = part of the current file extension
            - `{counter}` = defined counter

        **Returns:**
            `QGroupBox`: Widget with all controls for the extension area
        """
        box = QGroupBox(self._tr('sections.extension.title'))
        layout = QVBoxLayout(box)
        layout.setAlignment(Qt.AlignTop)

        # input field for the file extension
        self.edit_ext = QLineEdit()
        self.edit_ext.setText('{ext}')
        layout.addWidget(self.edit_ext)

        # button row for {ext} and {ext1-3}
        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignLeft)

        self.btn_ext = QPushButton('{ext}')
        self.btn_ext_slice = QPushButton('{ext1-3}')

        for b in (self.btn_ext, self.btn_ext_slice):
            b.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)  # (x, y)
            b.setFocusPolicy(Qt.NoFocus)
            btn_row.addWidget(b)
            b.setFixedSize(75, 28)

        layout.addLayout(btn_row)

        # {counter} button below
        self.btn_ext_counter = QPushButton('{counter}')

        layout.addWidget(self.btn_ext_counter)

        # click handler
        self.btn_ext.clicked.connect(lambda: self._insert_token(self.edit_ext, '{ext}'))
        self.btn_ext_slice.clicked.connect(lambda: self._insert_token(self.edit_ext, '{ext1-3}'))
        self.btn_ext_counter.clicked.connect(lambda: self._insert_token(self.edit_ext, '{counter}'))

        # refresh preview when the input field is updated
        self.edit_ext.textChanged.connect(self._update_preview_later)

        # style settings
        box.setStyleSheet(GROUPBOX_STYLE)

        return box

    def _make_section_replace(self) -> QGroupBox:
        """
        Creates the section for searching and replacing sub-strings.

        Contains:
        - The input field for the search
        - The input field for the substring to be replaced
        - Checkboxes for:
            - RegEx
            - Process only the first match
            - Process only exact matches
            - Case sensitive
            - Exclude file extension

        **Returns:**
            `QGroupBox`: Widget with all controls for the search and replace area
        """
        box = QGroupBox(self._tr('sections.replace.title'))
        layout = QVBoxLayout(box)
        layout.setAlignment(Qt.AlignTop)

        # search & replace grid
        grid = QGridLayout()

        lbl_search = QLabel(self._tr('sections.replace.lbl_search'))
        self.edit_search = QLineEdit()
        self.edit_search.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        lbl_replace = QLabel(self._tr('sections.replace.lbl_replace'))
        self.edit_replace = QLineEdit()
        self.edit_replace.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        grid.addWidget(lbl_search, 0, 0)
        grid.addWidget(self.edit_search, 0, 1)
        grid.addWidget(lbl_replace, 1, 0)
        grid.addWidget(self.edit_replace, 1, 1)

        grid.setColumnStretch(0, 0)  # labels
        grid.setColumnStretch(1, 1)  # input fields

        layout.addLayout(grid)

        # upper checkbox row
        upper_opt_row = QHBoxLayout()
        upper_opt_row.setAlignment(Qt.AlignLeft)

        self.cb_regex = QCheckBox(self._tr('sections.replace.cb_regex'))
        self.cb_first_match = QCheckBox(self._tr('sections.replace.cb_first_match'))
        self.cb_exact_match = QCheckBox(self._tr('sections.replace.cb_exact_matches'))

        for c in (self.cb_regex, self.cb_first_match, self.cb_exact_match):
            upper_opt_row.addWidget(c)

        layout.addLayout(upper_opt_row)

        # lower checkbox row
        lower_opt_row = QHBoxLayout()
        lower_opt_row.setAlignment(Qt.AlignLeft)

        self.cb_case_sens = QCheckBox(self._tr('sections.replace.cb_case_sens'))
        self.cb_ignore_ext = QCheckBox(self._tr('sections.replace.cb_ignore_ext'))

        for c in (self.cb_case_sens, self.cb_ignore_ext):
            lower_opt_row.addWidget(c)

        layout.addLayout(lower_opt_row)

        # loads values from the config
        self.cb_regex.setChecked(self.cfg.getboolean('replace', 'regex', fallback=False))
        self.cb_first_match.setChecked(self.cfg.getboolean('replace', 'only_first_match', fallback=False))
        self.cb_exact_match.setChecked(self.cfg.getboolean('replace', 'exact_match', fallback=False))
        self.cb_case_sens.setChecked(self.cfg.getboolean('replace', 'case_sensitive', fallback=False))
        self.cb_ignore_ext.setChecked(self.cfg.getboolean('replace', 'exclude_extension', fallback=True))

        # saves values in the config
        self.cb_regex.toggled.connect(
            lambda v: self._handle_config_change('replace', 'regex', v))
        self.cb_first_match.toggled.connect(
            lambda v: self._handle_config_change('replace', 'only_first_match', v))
        self.cb_exact_match.toggled.connect(
            lambda v: self._handle_config_change('replace', 'exact_match', v))
        self.cb_case_sens.toggled.connect(
            lambda v: self._handle_config_change('replace', 'case_sensitive', v))
        self.cb_ignore_ext.toggled.connect(
            lambda v: self._handle_config_change('replace', 'exclude_extension', v))

        # refresh preview when the input field is updated
        self.edit_search.textChanged.connect(self._update_preview_later)
        self.edit_replace.textChanged.connect(self._update_preview_later)

        # style settings
        layout.addStretch(1)
        box.setStyleSheet(GROUPBOX_STYLE)

        return box

    def _make_section_counter(self) -> QGroupBox:
        """
        Creates the section for configuring the counter.

        Contains:
        - Spin boxes for:
            - Start index
            - Increments by which the index is increased each time
            - Minimum number of digits
        - A checkbox to apply the counter only in case of name conflicts (duplicates)

        **Returns:**
            `QGroupBox`: Widget with all controls for the counter area
        """
        box = QGroupBox(self._tr('sections.counter.title'))
        layout = QVBoxLayout(box)

        # help function for creating spin boxes
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

        # calls the help function for creating the individual spin boxes
        self.spin_start = add_counter_row(
            self._tr('sections.counter.lbl_start'), 'counter', 'start', 0, 999999)
        self.spin_step = add_counter_row(
            self._tr('sections.counter.lbl_step'), 'counter', 'step', 1, 9999)
        self.spin_digits = add_counter_row(
            self._tr('sections.counter.lbl_digits'), 'counter', 'digits', 1, 10, 45)

        # checkbox for inversion
        self.cb_dupes = QCheckBox(self._tr('sections.counter.dupes'))
        self.cb_dupes.setChecked(self.cfg.getboolean('counter', 'dupes_only', fallback=False))
        layout.addWidget(self.cb_dupes)

        # saves the current values in the config
        self.spin_start.valueChanged.connect(
            lambda v: self._handle_config_change('counter', 'start', v))
        self.spin_step.valueChanged.connect(
            lambda v: self._handle_config_change('counter', 'step', v))
        self.spin_digits.valueChanged.connect(
            lambda v: self._handle_config_change('counter', 'digits', v))
        self.cb_dupes.toggled.connect(
            lambda v: self._handle_config_change('counter', 'dupes_only', v))

        # style settings
        layout.addStretch(1)
        box.setStyleSheet(GROUPBOX_STYLE)

        return box

    def _make_section_advanced_options(self) -> QGroupBox:
        """
        Creates the section for advanced options.

        Contains:
        - Dropdown menu for case sensitivity
        - A checkbox for Windows-compatible file names (always active in Windows)
        - The option to open the current target names in the system editor for manual editing

        **Returns:**
            `QGroupBox`: Widget with all advanced options controls
        """
        box = QGroupBox(self._tr('sections.advanced_opts.title'))
        layout = QVBoxLayout(box)
        layout.setAlignment(Qt.AlignTop)
        layout.setContentsMargins(8, 0, 8, 0)  # smaller gap at the top and bottom

        # row for the options
        row = QHBoxLayout()
        row.setAlignment(Qt.AlignLeft)

        # upper/lower case
        lbl_case = QLabel(self._tr('sections.advanced_opts.lbl_case'))
        self.cmb_case = QComboBox()
        self.cmb_case.addItem(self._tr('sections.advanced_opts.case_values.unchanged'), 'unchanged')
        self.cmb_case.addItem(self._tr('sections.advanced_opts.case_values.lowercase'), 'lowercase')
        self.cmb_case.addItem(self._tr('sections.advanced_opts.case_values.uppercase'), 'uppercase')
        self.cmb_case.addItem(self._tr('sections.advanced_opts.case_values.heading'), 'heading')
        self.cmb_case.addItem(self._tr('sections.advanced_opts.case_values.mocking'), 'mocking')

        # windows-compatible names
        self.cb_windows = QCheckBox(self._tr('sections.advanced_opts.cb_windows'))
        self.cb_windows.setChecked(True if self._is_windows() else self.cfg.getboolean('advanced', 'windows_names', fallback=False))

        # on windows: gray out the checkbox and force it to be active
        if self._is_windows():
            self.cb_windows.setEnabled(False)

        # open in editor
        self.btn_editor = QPushButton(self._tr('sections.advanced_opts.btn_editor'))

        row.addWidget(lbl_case)
        row.addWidget(self.cmb_case)
        row.addStretch(1)
        row.addWidget(self.cb_windows)
        row.addStretch(1)
        row.addWidget(self.btn_editor, alignment=Qt.AlignRight)

        layout.addLayout(row)

        # loads values from the config
        self._set_combo_by_data(self.cmb_case, self.cfg.get('advanced', 'case', fallback='unchanged'))
        self.cb_windows.setChecked(self.cfg.getboolean('advanced', 'windows_names', fallback=False))

        # saves values in the config
        self.cmb_case.currentIndexChanged.connect(
            lambda _: self._handle_config_change('advanced', 'case', self.cmb_case.currentData()))
        self.cb_windows.toggled.connect(
            lambda v: self._handle_config_change('advanced', 'windows_names', v))

        # click handler
        self.btn_editor.clicked.connect(self._open_in_editor)

        # style settings
        box.setStyleSheet(GROUPBOX_STYLE)

        return box

    def _show_about_dialog(self) -> None:
        """
        Displays the application's “About” dialog.

        It shows information about the application, including the
        version number, licensing, and author. Depending on the installation
        source, information about updates is also provided here.

        **Returns:**
            `None`
        """

        def compose_html(status_html: str = '') -> str:
            license_value = APP_INFO.get('license')
            license_link = f'<a href="app://license">{license_value}</a>'
            return (
                f'<b>{APP_INFO["name"]}</b> {APP_INFO["version"]}{status_html}<br>'
                f'{self._tr("about.description")}<br><br>'
                f'<b>{self._tr("about.license")}</b> {license_link}<br>'
                f'<b>{self._tr("about.developer")}</b> {APP_INFO["developer"]}<br>'
                f'<a href="{APP_INFO["url"]}">{APP_INFO["url"]}</a><br><br>'
                f'<small>{APP_INFO["copyright"]}</small>'
            )

        dlg = QDialog(self)
        dlg.setWindowTitle(self._tr('about.title'))
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
        def _on_link_activated(url: str) -> None:
            if url == "app://license":
                self._show_license_dialog(parent=dlg)
            else:
                webbrowser.open(url)

        text_lbl.linkActivated.connect(_on_link_activated)

        # ok button
        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(dlg.accept)
        root.addWidget(buttons, 0, Qt.AlignRight)

        # define initial size based on content
        dlg.adjustSize()
        dlg.setFixedSize(dlg.sizeHint())

        # update check
        def on_checked(status: str, release_url: str) -> None:
            if status == 'available':
                label = self._tr('about.update_available')
                status_html = f' &nbsp;—&nbsp; <a href="{release_url}">{label}</a>'
            elif status == 'none':
                status_html = f' &nbsp;—&nbsp; {self._tr("about.no_update")}'
            elif status == 'failed':
                status_html = f' &nbsp;—&nbsp; {self._tr("about.update_failed")}'
            else:
                status_html = ''

            text_lbl.setText(compose_html(status_html))
            dlg.adjustSize()
            dlg.setFixedSize(dlg.sizeHint())

        dlg._checker = UpdateChecker(APP_INFO['update_repo'], APP_INFO['version'])
        dlg._checker.finished.connect(on_checked)
        dlg._checker.start()

        dlg.exec()

    def _show_license_dialog(self, parent=None) -> None:
        """
        Opens a simple modal dialog displaying the LICENSE file from the application root.

        **Returns:**
            `None`
        """
        license_text = APP_INFO.get("license_text")

        dlg = QDialog(parent or self)
        dlg.setWindowTitle(self._tr("about.license_window_title"))
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

        dlg.resize(750, 600)
        dlg.exec()



##################
# Helper Methods #
##################

# --------------------------
# --- UI and translation ---
# --------------------------
    def resizeEvent(self, e) -> None:
        """
        Enforces a minimum width for the main window and calls
        the standard resize event of QMainWindow.
        (QT-Event handler)

        **Parameters:**
            `e` (QResizeEvent): Resize event object

        **Returns:**
            `None`
        """
        if self.width() < self.MIN_WIDTH:
            self.resize(self.MIN_WIDTH, max(self.height(), self.minimumSizeHint().height()))

        super().resizeEvent(e)

    def _tr(self, key: str) -> str:
        """
        Short form for translations using the Translator object.

        **Parameters:**
            `key` (str): Key for the language string (e.g., “menu.file”)

        **Returns:**
            `str`: Translated text string
        """
        return self.translator.t(key)

    def _set_language(self, code: str) -> None:
        """
        Saves the selected language in the configuration and
        restarts the window with the new language.

        **Parameters:**
            `code` (str): Language code (e.g., “en” or “de”)

        **Returns:**
            `None`
        """
        set_language_in_config(code)
        self.translator.switch_language(code)
        self._restart_window()

    def _restart_window(self) -> None:
        """
        Opens a new main window and closes the current one.

        Used, among other things, after language or configuration changes.

        **Returns:**
            `None`
        """
        self._next_window = MainWindow()
        self._next_window.show()
        self.close()

    def _insert_token(self, edit: QLineEdit, token: str) -> None:
        """
        Inserts a placeholder token (e.g., “{name}”, “{counter}”, “{date}”)
        at the current cursor position in a QLineEdit.

        **Parameters:**
            `edit` (QLineEdit): Target input field
            `token` (str): Placeholder string to be inserted

        **Returns:**
            `None`
        """
        edit.setFocus()
        edit.insert(token)



# --------------------------
# ----- Config changes -----
# --------------------------
    def _handle_config_change(self, section: str, key: str, value) -> None:
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
        self._update_preview_later()

    def _reset_all_settings(self) -> None:
        """
        Resets all settings to factory defaults and restarts the main window.

        Displays a confirmation prompt beforehand and writes the
        default values from DEFAULTS (`settings.py`) to the configuration file.

        **Returns:**
            `None`
        """
        if not self._question_box('messages.confirm', 'messages.questions.reset_settings'):
            return

        reset_config(autodetect_language=True)

        QMessageBox.information(
            self, self._tr('messages.info'), self._tr('messages.confirmation.settings_reset'))
        self._restart_window()



# -------------------
# --- File import ---
# -------------------
    def _action_open_files(self) -> None:
        """
        Opens a file dialog for selecting one or more files
        and then imports them into the table.

        **Returns:**
            `None`
        """
        files, _ = QFileDialog.getOpenFileNames(
            self, self._tr('dialogs.open_files'), str(Path.home()), self._tr('dialogs.file_types')
        )

        if files:
            self._import_from_paths(files)

    def _action_open_folder(self) -> None:
        """
        Opens a dialog for selecting a directory
        and imports all files contained therein into the table.

        **Returns:**
            `None`
        """
        folder = QFileDialog.getExistingDirectory(
            self, self._tr('dialogs.open_folder'), str(Path.home()),
            options=QFileDialog.ShowDirsOnly
        )

        if folder:
            self._import_from_paths([folder])

    def _import_from_paths(self, paths: list[str]) -> None:
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
        self._clear_table()

        # Collect all valid files from the given paths (respecting hidden-file settings)
        opts = ImportOptions(
            allow_files=True,
            allow_dirs=True,
            include_hidden=self.act_hidden.isChecked()
        )

        items = collect(paths, opts)
        files = [it.path for it in items if not it.is_dir]

        # natural sorting by file name
        files.sort(key=lambda p: [int(t) if t.isdigit() else t.lower()
                                  for t in re.split(r'(\d+)', p.name)])

        # fill in the table
        self.table.setUpdatesEnabled(False)
        for f in files:
            self._table_add_entry(f)
        self.table.setUpdatesEnabled(True)

        # refresh preview
        self._update_preview_later()



# ----------------------
# --- table behavior ---
# ----------------------
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
        if obj is self.table.viewport() and ev.type() == QEvent.Resize:
            self._rebalance_on_view_resize()
            return False

        # drag & drop handling
        if obj not in (self.table, self.table.viewport()):
            return super().eventFilter(obj, ev)

        t = ev.type()

        # accept only local URLs
        if t in (QEvent.DragEnter, QEvent.DragMove):
            md = ev.mimeData()
            if md and md.hasUrls():
                ev.acceptProposedAction()
                return True
            return False

        # extract and import paths
        if t == QEvent.Drop:
            md = ev.mimeData()
            urls = md.urls() if md else []
            paths = [u.toLocalFile() for u in urls if u.isLocalFile()]

            if paths:
                # prevent multiple directories
                dir_count = sum(1 for p in paths if Path(p).is_dir())
                if dir_count > 1:
                    QMessageBox.warning(
                        self,
                        self._tr('messages.info'),
                        self._tr('messages.information.multiple_directories')
                        )
                    ev.ignore()
                    return True

                ev.setDropAction(Qt.CopyAction)
                ev.accept()
                self._import_from_paths(paths)
                return True
            return False

        # forward all other events as normal
        return super().eventFilter(obj, ev)

    def _init_equal_columns(self) -> None:
        """
        Initializes the table with a width ratio of 50/50.

        Takes into account the minimum assigned width when changing the column width.

        **Returns:**
            `None`
        """
        vw = self.table.viewport().width()
        w0 = max(self._min_left, vw // 2)
        w1 = max(self._min_right, vw - w0)

        # if the sum is greater than vw due to minima -> clamp
        if w0 + w1 > vw:
            # preferably leave the left column at minimum width
            w0 = max(self._min_left, min(w0, vw - self._min_right))
            w1 = vw - w0

        self._set_columns(w0, w1)

    def _set_columns(self, w0: int, w1: int) -> None:
        """
        Sets the widths of both columns in a signal-friendly manner.

        Temporarily blocks all signals to prevent infinite loops when manually
        or programmatically adjusting column widths.

        **Parameters:**
            `w0` (int): New width of the left column
            `w1` (int): New width of the right column

        **Returns:**
            `None`
        """
        self.table.blockSignals(True)
        self.table.setColumnWidth(0, w0)
        self.table.setColumnWidth(1, w1)
        self.table.blockSignals(False)

    def _on_header_resized(self, logicalIndex: int, _old: int, new: int) -> None:
        """
        Responds to user resizing of a column and dynamically adjusts the other column.

        Ensures that:
        - the total width of the columns matches the viewport width
        - the other column fills the remaining space
        - minimum widths are maintained
        - no horizontal scroll bar appears

        **Parameters:**
            `logicalIndex` (int): Index of the changed column (0 = left, 1 = right)
            `_old` (int): Old width (not used)
            `new` (int): New width of the changed column

        **Returns:**
            `None`
        """
        if logicalIndex not in (0, 1):
            return

        vw = self.table.viewport().width()

        if logicalIndex == 0:
            # clamp new left width, right fills remainder (>= min)
            w0 = max(self._min_left, min(new, vw - self._min_right))
            w1 = max(self._min_right, vw - w0)
            self._set_columns(w0, w1)
        else:
            # clamp new right width, left fills remainder (>= min)
            w1 = max(self._min_right, min(new, vw - self._min_left))
            w0 = max(self._min_left, vw - w1)
            self._set_columns(w0, w1)

    def _rebalance_on_view_resize(self) -> None:
        """
        Maintains the current ratio of column widths when resizing a window or table.

        If one column reaches its minimum width, only the other column is adjusted.
        The ratio is calculated from the current widths and transferred proportionally
        to the new viewport width.

        **Returns:**
            `None`
        """
        vw = self.table.viewport().width()
        if vw <= 0:
            return

        w0 = self.table.columnWidth(0)
        w1 = self.table.columnWidth(1)
        total = w0 + w1 if (w0 + w1) > 0 else vw

        # current ratio (e.g., 50/50 initially, otherwise user status)
        ratio0 = w0 / total
        # new target widths
        w0_new = int(round(vw * ratio0))
        # clamp left: not smaller than min & not so large that right < min
        w0_new = max(self._min_left, min(w0_new, vw - self._min_right))
        w1_new = vw - w0_new

        # if rounding would result in a value less than min, adjust again.
        if w1_new < self._min_right:
            w1_new = self._min_right
            w0_new = vw - w1_new
            w0_new = max(self._min_left, w0_new)

        self._set_columns(w0_new, w1_new)

    def _table_add_entry(self, p: Path) -> None:
        """
        Adds a new row to the table for the specified file.

        Creates cells for the current and new names and saves the full
        path as tooltip and UserRole data.

        **Parameters:**
            `p` (Path): Full path to the file

        **Returns:**
            `None`
        """
        # determine the next available row index
        row = self.table.rowCount()
        self.table.insertRow(row)

        # create table item for the current filename
        current_name = QTableWidgetItem(p.name)
        current_name.setToolTip(str(p))
        current_name.setData(Qt.UserRole, str(p))

        # create empty cell for the new (renamed) filename
        new_name = QTableWidgetItem('')

        # insert both items into the table
        self.table.setItem(row, 0, current_name)
        self.table.setItem(row, 1, new_name)

    def _clear_table(self) -> None:
        """
        Deletes all rows from the file table and removes markings.

        If an undo is available, a warning is displayed beforehand and, if confirmed,
        the undo stack is emptied (the undo button is deactivated).

        **Returns:**
            `None`
        """
        # only ask if there is anything to delete
        if self.table.rowCount() > 0:
            # warn/ask only if undo is available
            if not self._invalidate_undo_with_prompt():
                return

        self.table.setRowCount(0)
        self.table.clearSelection()
        self._reset_text_fields()

    def _table_context_menu(self, pos) -> None:
        """
        Opens a context menu at the specified position in the table.

        Allows selected rows to be removed by right-clicking.

        **Parameters:**
            `pos` (QPoint): Position of the mouse click relative to the table

        **Returns:**
            `None`
        """
        index = self.table.indexAt(pos)

        # do nothing if the click was outside any valid row
        if not index.isValid():
            return

        # select the clicked row if it was not already selected
        if not self.table.selectionModel().isSelected(index):
            self.table.clearSelection()
            self.table.selectRow(index.row())

        # create context menu with 'Remove' action
        menu = QMenu(self)
        act_remove = menu.addAction(self._tr('context_menu.remove'))

        # execute the menu and handle selected action
        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen == act_remove:
            self._remove_selected_rows()

    def _remove_selected_rows(self) -> None:
        """
        Removes the selected lines and updates the preview.

        If an undo is available, a warning is displayed beforehand and, if confirmed,
        the undo stack is cleared (the undo button is deactivated).

        **Returns:**
            `None`
        """
        sel_row = self.table.selectionModel().selectedRows()
        if not sel_row:
            return

        # warn/ask only if undo is available
        if not self._invalidate_undo_with_prompt():
            return

        for idx in sorted(sel_row, key=lambda i: i.row(), reverse=True):
            self.table.removeRow(idx.row())

        # if there are no more entries -> reset input fields
        if self.table.rowCount() == 0:
            self._reset_text_fields()

        self._update_preview_later()



# ------------------------
# --- Renaming preview ---
# ------------------------
    def _collect_cfg(self) -> RenameCfg:
        """
        Reads the current GUI and configuration values
        and uses them to create a RenameCfg object for the renaming logic.

        **Returns:**
            `RenameCfg`: Fully populated RenameCfg instance
        """
        datetime = DateTimeCfg(
            date_format=self.cmb_date.currentText(),
            date_sep=self.cmb_date_sep.currentData(),
            time_format=self.cmb_time.currentText(),
            time_sep=self.cmb_time_sep.currentData(),
            date_type=self.cmb_datetype.currentData(),
        )

        counter = CounterCfg(
            start=self.spin_start.value(),
            step=self.spin_step.value(),
            digits=self.spin_digits.value(),
            dupes_only=self.cb_dupes.isChecked(),
        )

        repl = None

        if self.edit_search.text():
            repl = None
            if self.edit_search.text():
                repl = ReplaceCfg(
                    pattern=self.edit_search.text(),
                    replace=self.edit_replace.text(),
                    regex=self.cb_regex.isChecked(),
                    first_only=self.cb_first_match.isChecked(),
                    exact=self.cb_exact_match.isChecked(),
                    case_sensitive=self.cb_case_sens.isChecked(),
                    exclude_extension=self.cb_ignore_ext.isChecked(),
                )

        case = CaseCfg(
            mode=self.cmb_case.currentData() or 'unchanged',
            windows_names=self.cb_windows.isChecked(),
        )

        mask = MaskCfg(
            name_mask=self.edit_mask.text(),
            ext_mask=self.edit_ext.text(),
        )

        return RenameCfg(dt=datetime, counter=counter, repl=repl, case=case, mask=mask)

    def _update_preview_now(self) -> None:
        """
        Creates preview names, checks their length/size depending on the platform,
        and visually marks invalid entries.

        Platform-dependent logic:
            - Windows -> Character length (validate_windows_length)
            - Linux -> Byte size (validate_linux_bytes)

        Display:
            - Invalid -> Text in red + italics
            - Tooltip -> “<translated message> -> <name>”

        **Returns:**
            `None`
        """
        # get total number of rows in the preview table
        rowcount = self.table.rowCount()
        if rowcount == 0:
            return

        # collect current rename configuration
        cfg = self._collect_cfg()
        paths = [Path(self.table.item(r, 0).data(Qt.UserRole)) for r in range(rowcount)]
        new_names = preview_names(paths, cfg)

        for r, new_name in enumerate(new_names):
            item = self.table.item(r, 1)
            item.setText(new_name)

            # get base directory for current file
            src_full = Path(self.table.item(r, 0).data(Qt.UserRole))
            base_dir = src_full.parent

            # initialize validation state and message list
            invalid = False
            messages = []

            # validate filename length according to OS limits
            if self._is_windows():
                if not validate_windows_length(base_dir, new_name):
                    invalid = True
                    messages.append(self._tr('tooltips.table.filename_too_long_windows'))
            else:
                if not validate_linux_bytes(base_dir, new_name):
                    invalid = True
                    messages.append(self._tr('tooltips.table.filename_too_long_linux'))

            # format tooltip and apply preview cell styling
            tooltip = self._format_overlen_tooltip(messages)
            self._style_preview_cell(item, invalid, tooltip, new_name)



# -----------------------
# --- Editor-Workflow ---
# -----------------------
    def _open_in_editor(self) -> None:
        """
        Exports the current preview of the target names to a temporary text file,
        opens it in the system editor, and allows manual editing.

        After saving the text file, the list can be imported again.

        **Returns:**
            `None`
        """
        # collect preview lines
        names = [self.table.item(r, 1).text() for r in range(self.table.rowCount())]
        if not names:
            QMessageBox.information(self, self._tr('messages.info'),
                                    self._tr('messages.information.no_files'))
            return

        # determine the directory for the temp file
        if self._is_windows():
            # default temp directory (e.g., C:\Users\<Name>\AppData\Local\Temp)
            tmpdir = Path(tempfile.gettempdir())
        else:
            # directly in the user cache (~/.cache)
            tmpdir = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))

        tmpfile = tmpdir / f"bulkrename_preview_{os.getpid()}.txt"

        with tmpfile.open("w", encoding="utf-8", newline="\n") as f:
            for n in names:
                f.write(n + "\n")

        # open file in system editor
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(tmpfile)))

        while True:
            if not self._question_box('messages.confirm', 'messages.questions.load_from_editor'):
                try:
                    tmpfile.unlink(missing_ok=True)
                except Exception:
                    pass
                return

            # read processed lines
            try:
                with tmpfile.open('r', encoding='utf-8') as f:
                    lines = [ln.rstrip('\r\n') for ln in f.readlines()]
            except Exception:
                QMessageBox.critical(self, self._tr('messages.error'),
                                    self._tr('messages.errors.read_failed'))
                return

            # check number of lines
            if len(lines) != len(names):
                mbox = QMessageBox(self)
                mbox.setIcon(QMessageBox.Warning)
                mbox.setWindowTitle(self._tr('messages.error'))
                mbox.setText(self._tr('messages.errors.editor_count_mismatch'))
                reopen = mbox.addButton(self._tr('dialogs.buttons.open_again'), QMessageBox.ActionRole)
                cancel = mbox.addButton(self._tr('dialogs.buttons.cancel'), QMessageBox.RejectRole)
                mbox.exec()

                if mbox.clickedButton() == reopen:
                    # reopen file and ask again
                    QDesktopServices.openUrl(url) or subprocess.Popen(["gio", "open", str(tmpfile)])
                    continue
                else:
                    try:
                        tmpfile.unlink(missing_ok=True)
                    except Exception:
                        pass
                    return

            # success -> apply and cleanup
            for r, val in enumerate(lines):
                self.table.item(r, 1).setText(val)

            try:
                tmpfile.unlink(missing_ok=True)
            except Exception:
                pass

            return



# -----------------------
# --- Rename and Undo ---
# -----------------------
    def _perform_rename(self) -> None:
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
        rows = self.table.rowCount()

        # abort if any filename exceeds the allowed length (validation failed)
        if not self._precheck_rename_block_on_overlength():
            return

        # abort and show info message if there are no files in the table
        if rows == 0:
            QMessageBox.information(
                self, self._tr('messages.info'),
                self._tr('messages.information.no_files_for_rename')
            )
            return

        # confirm rename operation
        if not self._question_box('messages.confirm', 'messages.questions.confirm_rename'):
            return

        # build planned rename operations from table entries
        paths = [Path(self.table.item(r, 0).data(Qt.UserRole)) for r in range(rows)]
        new_names = [self.table.item(r, 1).text() for r in range(rows)]
        plan = plan_moves(paths, new_names)

        # check if any actual rename would happen
        effective = [(src, dst) for src, dst in plan if src.name != dst.name]
        if not effective:
            QMessageBox.information(
                self,
                self._tr('messages.info'),
                self._tr('messages.information.no_effective_rename')
            )
            return

        # conflicts
        conflicts = check_conflicts(effective)
        if conflicts:
            self._show_conflicts(conflicts)
            return

        # source not found
        missing = [str(src) for src, _ in effective if not src.exists()]
        if missing:
            QMessageBox.critical(
                self,
                self._tr('messages.error'),
                self._tr('messages.errors.missing_sources') + '\n\n' + '\n'.join(missing)
            )
            return

        # perform the actual renaming operation and collect any errors
        errors = perform_rename(effective)

        # if errors occurred during renaming, show an error dialog and abort
        if errors:
            QMessageBox.critical(
                self, self._tr('messages.error'),
                self._tr('messages.errors.rename_failed') + '\n\n' + '\n\n'.join(errors)
            )
            return

        # remembering moves for undo
        self._undo_stack.append(effective)
        self._update_undo_state()

        # confirmation dialog
        # QMessageBox.information(
        #     self, self._tr('messages.info'),
        #     self._tr('messages.confirmation.rename_done')
        # )

        # update table
        for r in range(self.table.rowCount()):
            old_item = self.table.item(r, 0)
            full = Path(old_item.data(Qt.UserRole))
            new_name = self.table.item(r, 1).text()
            new_full = full.with_name(new_name)
            old_item.setText(new_full.name)
            old_item.setToolTip(str(new_full))
            old_item.setData(Qt.UserRole, str(new_full))

        # refresh preview after table changes
        self._reset_text_fields()
        self._update_preview_later()

    def _show_conflicts(self, conflicts: list[str]) -> None:
        """
        Displays a scrollable error message with all name conflicts found.

        **Parameters:**
            `list[str]`: List of conflicting file names.

        **Returns:**
            `None`
        """
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Critical)
        box.setWindowTitle(self._tr('messages.error'))
        box.setText(self._tr('messages.errors.conflicts_found'))

        # scrollable text area
        text_area = QPlainTextEdit()
        text_area.setReadOnly(True)
        text_area.setPlainText('\n\n'.join(conflicts))
        text_area.setMinimumSize(500, 250)
        text_area.setStyleSheet('QPlainTextEdit { background: palette(base); }')

        # embed widget in message box
        layout = box.layout()
        layout.addWidget(text_area, 1, 0, 1, layout.columnCount())

        box.addButton(self._tr('dialogs.buttons.ok'), QMessageBox.AcceptRole)

        box.exec()

    def _precheck_rename_block_on_overlength(self) -> bool:
        """
        Checks whether at least one new name in the preview exceeds the permitted
        length/byte limits (platform-dependent).

        Platform logic:
            - Windows: validate_windows_length (character/path limits)
            - Linux:   validate_linux_bytes    (byte limits NAME_MAX/PATH_MAX)

        If at least one entry is too long, a warning dialog is displayed
        and renaming is prevented.

        **Returns:**
            `bool`:
            - True = all names are valid -> renaming allowed.
            - False = at least one name too long -> renaming blocked.
        """
        # get total number of rows in the table
        rows = self.table.rowCount()
        if rows == 0:
            return True

        # iterate over all table rows
        for r in range(rows):
            item_src = self.table.item(r, 0)
            item_new = self.table.item(r, 1)
            if not item_src or not item_new:
                continue

            # get base directory and proposed new filename
            base_dir = Path(item_src.data(Qt.UserRole)).parent
            new_name = item_new.text()

            # check Windows filename length limit
            if self._is_windows():
                if not validate_windows_length(base_dir, new_name):
                    QMessageBox.warning(
                        self,
                        self._tr('messages.warning'),
                        self._tr('messages.warnings.name_too_long'),
                    )
                    return False
            # check Linux filename byte-length limit
            else:
                if not validate_linux_bytes(base_dir, new_name):
                    QMessageBox.warning(
                        self,
                        self._tr('messages.warning'),
                        self._tr('messages.warnings.name_too_long'),
                    )
                    return False

        # all names are within valid limits
        return True

    def _perform_undo(self) -> None:
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
        if not self._undo_stack:
            QMessageBox.information(
                self, self._tr('messages.info'),
                self._tr('messages.information.no_undo')
            )
            return

        if not self._question_box('messages.confirm', 'messages.questions.confirm_undo'):
            return

        # get the last rename operation from the undo stack
        moves = self._undo_stack[-1]

        # try to revert all previously renamed files
        missing, errors = undo_moves(moves)

        # show error if some original source files are missing
        if missing:
            QMessageBox.critical(
                self, self._tr('messages.error'),
                self._tr('messages.errors.missing_sources_undo') + '\n\n' + '\n'.join(missing)
            )
            return

        # show error if undo operation failed for any file
        if errors:
            QMessageBox.critical(
                self, self._tr('messages.error'),
                self._tr('messages.errors.undo_failed') + '\n\n' + '\n'.join(errors)
            )
            return

        # successful -> actually remove step from stack
        self._undo_stack.pop()

        QMessageBox.information(
            self, self._tr('messages.info'),
            self._tr('messages.confirmation.undo_done')
        )

        # reset table based on moves (new -> old)
        mapping = {str(dst): str(src) for (src, dst) in moves}
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
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

        self._reset_text_fields()
        self._update_undo_state()
        self._update_preview_later()

    def _invalidate_undo_with_prompt(self) -> bool:
        """
        If there are undo steps, the user is asked whether they should be
        discarded when removing/emptying. If agreed, empties the undo stack
        and updates the button state.

        **Returns:**
            bool: True = continue execution; False = cancel operation.
        """
        if self._undo_stack:
            if not self._question_box('messages.confirm', 'messages.questions.invalidate_undo'):
                return False

            self._undo_stack.clear()
            self._update_undo_state()
        return True

    def _update_undo_state(self) -> None:
        """
        Updates the enabled state of the Undo button.

        Enables the Undo button only if the in-memory undo stack
        contains at least one reversible rename step.

        **Returns:**
            `None`
        """
        self.btn_undo.setEnabled(bool(self._undo_stack))



# --------------
# --- Helper ---
# --------------
    def _is_windows(self) -> bool:
        """
        Checks whether the program is running under Windows.

        **Returns:**
            `bool`: True if the operating system is Windows, otherwise False
        """
        return os.name == 'nt'

    def _set_combo_by_data(self, combo: QComboBox, value: str) -> None:
        """
        Selects the entry in the passed QComboBox widget
        whose stored itemData corresponds to the specified value.

        **Parameters:**
            `combo` (QComboBox): Target combo box
            `value` (str): Comparison value from itemData()

        **Returns:**
            `None`
        """
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                return

    def _update_preview_later(self) -> None:
        """
        Starts a short timer to delay the preview update.

        **Returns:**
            `None`
        """
        self._update_timer.start(60)

    def _question_box(self, title_key: str, text_key: str) -> bool:
        """
        Displays a localized security prompt with “Yes”/“No” options.

        **Parameters:**
            `title_key` (str): Translation key for the window title
            `text_key` (str): Translation key for the prompt text

        **Returns:**
            `bool`: True if the user selects “Yes”, otherwise False
        """
        title = self._tr(title_key)
        text = self._tr(text_key)

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle(title)
        box.setText(text)

        yes_btn = box.addButton(self._tr('dialogs.buttons.yes'), QMessageBox.YesRole)
        no_btn = box.addButton(self._tr('dialogs.buttons.no'), QMessageBox.NoRole)

        box.setDefaultButton(yes_btn)
        box.exec()

        return box.clickedButton() == yes_btn

    def _reset_text_fields(self) -> None:
        """
        Resets all editable text fields (name mask, extension, search, replace)
        to their default values.

        **Returns:**
            `None`
        """
        self.edit_mask.setText('{name}')
        self.edit_ext.setText('{ext}')
        self.edit_search.setText('')
        self.edit_replace.setText('')

    def _apply_tooltips(self) -> None:
        """
        Assigns tooltips to all GUI elements based on the current language.

        **Returns:**
            `None`
        """
        # menu bar
        self.act_add_files.setToolTip(self._tr('tooltips.menu.act_add_files'))
        self.act_add_folder.setToolTip(self._tr('tooltips.menu.act_add_folder'))
        self.act_hidden.setToolTip(self._tr('tooltips.menu.act_hidden'))
        self.act_reset.setToolTip(self._tr('tooltips.menu.act_reset'))
        self.act_about.setToolTip(self._tr('tooltips.menu.act_about'))
        self.act_exit.setToolTip(self._tr('tooltips.menu.act_exit'))

        # lower buttons
        self.btn_clear.setToolTip(self._tr('tooltips.actions.btn_clear'))
        self.btn_rename.setToolTip(self._tr('tooltips.actions.btn_rename'))
        self.btn_undo.setToolTip(self._tr('tooltips.actions.btn_undo'))

        # rename section
        self.edit_mask.setToolTip(self._tr('tooltips.rename.edit_mask'))
        self.btn_name.setToolTip(self._tr('tooltips.rename.btn_name'))
        self.btn_name_slice.setToolTip(self._tr('tooltips.rename.btn_name_slice'))
        self.btn_counter.setToolTip(self._tr('tooltips.rename.btn_counter'))
        self.btn_date.setToolTip(self._tr('tooltips.rename.btn_date'))
        self.btn_time.setToolTip(self._tr('tooltips.rename.btn_time'))
        self.cmb_date.setToolTip(self._tr('tooltips.rename.cmb_date'))
        self.cmb_date_sep.setToolTip(self._tr('tooltips.rename.cmb_date_sep'))
        self.cmb_time.setToolTip(self._tr('tooltips.rename.cmb_time'))
        self.cmb_time_sep.setToolTip(self._tr('tooltips.rename.cmb_time_sep'))
        self.cmb_datetype.setToolTip(self._tr('tooltips.rename.cmb_datetype'))

        # extension section
        self.edit_ext.setToolTip(self._tr('tooltips.extension.edit_ext'))
        self.btn_ext.setToolTip(self._tr('tooltips.extension.btn_ext'))
        self.btn_ext_slice.setToolTip(self._tr('tooltips.extension.btn_ext_slice'))
        self.btn_ext_counter.setToolTip(self._tr('tooltips.extension.btn_counter'))

        # replace section
        self.edit_search.setToolTip(self._tr('tooltips.replace.edit_search'))
        self.edit_replace.setToolTip(self._tr('tooltips.replace.edit_replace'))
        self.cb_regex.setToolTip(self._tr('tooltips.replace.cb_regex'))
        self.cb_first_match.setToolTip(self._tr('tooltips.replace.cb_first_match'))
        self.cb_exact_match.setToolTip(self._tr('tooltips.replace.cb_exact_matches'))
        self.cb_case_sens.setToolTip(self._tr('tooltips.replace.cb_case_sens'))
        self.cb_ignore_ext.setToolTip(self._tr('tooltips.replace.cb_ignore_ext'))

        # counter section
        self.spin_start.setToolTip(self._tr('tooltips.counter.spin_start'))
        self.spin_step.setToolTip(self._tr('tooltips.counter.spin_step'))
        self.spin_digits.setToolTip(self._tr('tooltips.counter.spin_digits'))
        self.cb_dupes.setToolTip(self._tr('tooltips.counter.cb_dupes'))

        # advanced options section
        self.cmb_case.setToolTip(self._tr('tooltips.advanced_opts.cmb_case'))
        if self._is_windows():
            self.cb_windows.setToolTip(self._tr('tooltips.advanced_opts.cb_windows_forced'))
        else:
            self.cb_windows.setToolTip(self._tr('tooltips.advanced_opts.cb_windows'))
        self.btn_editor.setToolTip(self._tr('tooltips.advanced_opts.btn_editor'))

    def _format_overlen_tooltip(self, messages: list[str]) -> str:
        """
        Adjusts the tooltip for files whose names are too long.

        **Parameters:**
            `messages` (list[str]): List of translated messages

        **Returns:**
            `str`: Combined tooltip text
        """
        msgs = ' / '.join(m for m in messages if m)

        return f'{msgs} ' if msgs else ''

    def _style_preview_cell(self, item, invalid: bool, tooltip_text: str, fallback_name: str) -> None:
        """
        Formats a preview cell in the table widget.

        Behavior:
        - If length/size is invalid: Text in red + italics
        - Tooltip shows “<message>”
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
            item.setForeground(QBrush(QColor(Qt.red)))
            item.setToolTip(tooltip_text or fallback_name)
        else:
            # reset to default color and show normal tooltip
            item.setForeground(QBrush())
            item.setToolTip(fallback_name)
