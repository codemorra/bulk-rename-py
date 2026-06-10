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
from ..i18n import Translator
from ..importer import ImportOptions, collect
from ..renamer import (
    RenameCfg, DateTimeCfg, CounterCfg, ReplaceCfg, CaseCfg, MaskCfg,
    preview_names, validate_windows_length, validate_linux_bytes, plan_moves,
    check_conflicts, perform_rename, undo_moves
)
from ..settings import (
    get_config, get_language_from_config, set_language_in_config,
    set_cfg, ensure_config_file, reset_config, CONFIG_FILE
    )
from ..update_checker import UpdateChecker
from ..metadata import APP_INFO
from .rename_manager import RenameManager
from .table_manager import TableManager
from .gui_helpers import GUIHelpers, DEFAULT_TOKEN_NAME, DEFAULT_TOKEN_EXT, DEFAULT_TOKEN_COUNTER, DEFAULT_TOKEN_DATE, DEFAULT_TOKEN_TIME, DEFAULT_TOKEN_NAME_SLICE, DEFAULT_TOKEN_EXT_SLICE
from .about_dialog import AboutDialog

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
    MIN_WIDTH = MIN_WINDOW_WIDTH

    def __init__(self) -> None:
        """Initializes the main window.

        Loads saved configurations and language, creates the basic layout,
        initializes timers and the table view, and ensures that all GUI
        interactions are connected correctly.

        **Returns:**
            `None`
        """
        super().__init__()
        self._setup_main_window()

    def _setup_main_window(self) -> None:
        """
        Sets up the main window with all GUI elements and configurations.

        **Returns:**
            `None`
        """
        self._init_config_and_settings()
        self._init_menu_bar()
        self._init_main_layout()
        self._init_table()
        self._init_button_row()
        self._init_layout_constraints()
        self._init_signal_handlers()
        self._finalize_setup()

    def _init_config_and_settings(self) -> None:
        """
        Initializes configuration, language, and helper objects.

        **Returns:**
            `None`
        """
        # load config + language
        ensure_config_file()
        self.cfg = get_config()
        self.translator = Translator(get_language_from_config())

        # Initialize helper attributes
        self._next_window = None
        self.helpers = GUIHelpers(self)

        # always enforce Windows-compatible names in Windows
        if self.helpers.is_windows():
            if (not self.cfg.has_section('advanced')) or (not self.cfg.getboolean('advanced', 'windows_names', fallback=False)):
                if not self.cfg.has_section('advanced'):
                    self.cfg.add_section('advanced')
                self.cfg.set('advanced', 'windows_names', 'True')
                with CONFIG_FILE.open('w', encoding='utf-8') as f:
                    self.cfg.write(f)

        # timer for delayed preview of new file names
        self._update_timer = QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.timeout.connect(lambda: self.rename_manager.update_preview_now())

        # variable for multi-level in-memory undo
        self._undo_stack: list[list[tuple[Path, Path]]] = []
        self.rename_manager = RenameManager(self)
        self.table_manager = TableManager(self)
        self.about_dialog = AboutDialog(self)

        # window setup
        self.setWindowTitle(self.helpers.tr('app'))
        self.resize(*DEFAULT_WINDOW_SIZE)

    def _init_menu_bar(self) -> None:
        """
        Initializes the menu bar with all actions.

        **Returns:**
            `None`
        """
        menubar = self.menuBar()
        menu_file = menubar.addMenu(self.helpers.tr('menu.file'))
        menu_file.setToolTipsVisible(True)

        # import single/multiple files
        self.act_add_files = QAction(self.helpers.tr('menu.add_files'), self)
        self.act_add_files.setShortcut('Ctrl+O')
        self.act_add_files.triggered.connect(lambda: self.rename_manager.action_open_files())
        menu_file.addAction(self.act_add_files)

        # import entire directories
        self.act_add_folder = QAction(self.helpers.tr('menu.add_folder'), self)
        self.act_add_folder.setShortcut('Ctrl+Shift+O')
        self.act_add_folder.triggered.connect(lambda: self.rename_manager.action_open_folder())
        menu_file.addAction(self.act_add_folder)

        menu_file.addSeparator()

        # include hidden files checkbox
        self.act_hidden = QAction(self.helpers.tr('menu.show_hidden'), self, checkable=True)
        self.act_hidden.setChecked(self.cfg.getboolean('general', 'hidden_files', fallback=False))
        self.act_hidden.toggled.connect(lambda v: self.rename_manager.handle_config_change('general', 'hidden_files', v))
        menu_file.addAction(self.act_hidden)

        # language selection
        menu_lang = menu_file.addMenu(self.helpers.tr('menu.language'))
        lang_group = QActionGroup(self)
        lang_group.setExclusive(True)
        act_lang_en = QAction(self.helpers.tr('menu.lang_list.english'), self, checkable=True)
        act_lang_de = QAction(self.helpers.tr('menu.lang_list.german'),  self, checkable=True)
        lang_group.addAction(act_lang_en)
        lang_group.addAction(act_lang_de)
        current_lang = self.cfg.get('general', 'language', fallback='en')
        act_lang_en.setChecked(current_lang == 'en')
        act_lang_de.setChecked(current_lang == 'de')
        act_lang_en.triggered.connect(lambda: self.helpers.set_language('en'))
        act_lang_de.triggered.connect(lambda: self.helpers.set_language('de'))
        menu_lang.addAction(act_lang_en)
        menu_lang.addAction(act_lang_de)

        menu_file.addSeparator()

        # reset settings option
        self.act_reset = QAction(self.helpers.tr('menu.reset_settings'), self)
        self.act_reset.triggered.connect(lambda: self.rename_manager.reset_all_settings())
        menu_file.addAction(self.act_reset)

        menu_file.addSeparator()

        # about
        self.act_about = QAction(self.helpers.tr('menu.about'), self)
        self.act_about.triggered.connect(lambda: self.about_dialog.show_about_dialog())
        menu_file.addAction(self.act_about)

        menu_file.addSeparator()

        # exit option
        self.act_exit = QAction(self.helpers.tr('menu.exit'), self)
        self.act_exit.setShortcut('Ctrl+Q')
        self.act_exit.triggered.connect(self.close)
        menu_file.addAction(self.act_exit)

    def _init_main_layout(self) -> None:
        """
        Initializes the main layout and creates the sections.

        **Returns:**
            `None`
        """
        # central widget with vertical main layout
        central = QWidget(self)
        self.setCentralWidget(central)
        self.root_layout = QVBoxLayout(central)
        self.grid_layout = QGridLayout()
        self.root_layout.addLayout(self.grid_layout)

        # create sections
        self.rename_box = self._create_section_rename()
        self.ext_box = self._create_section_extension()
        self.search_box = self._create_section_replace()
        self.counter_box = self._create_section_counter()
        self.advanced_opts = self._create_section_advanced_options()

    def _init_table(self) -> None:
        """
        Initializes the table widget with headers and configuration.

        **Returns:**
            `None`
        """
        # create a table (two columns: current name, new name)
        self.table = QTableWidget(0, 2, self)
        self.table.setHorizontalHeaderLabels([
            self.helpers.tr('table.current_name'),
            self.helpers.tr('table.new_name')
        ])

        # drag & drop
        self.table.setAcceptDrops(True)
        self.table.viewport().setAcceptDrops(True)
        self.table.setDragDropMode(QAbstractItemView.DropOnly)
        self.table.setDropIndicatorShown(True)
        self.table.installEventFilter(self)
        self.table.viewport().installEventFilter(self)

        # table configuration
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
        hdr.sectionResized.connect(lambda idx, old, new: self.table_manager.on_header_resized(idx, old, new))

        # balancing columns during viewport resize
        self.table.viewport().installEventFilter(self)

        # set initial 50/50
        QTimer.singleShot(0, lambda: self.table_manager.init_equal_columns())

        # selection and editing behavior
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setFocusPolicy(Qt.StrongFocus)

        # presentation and layout
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(False)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.ElideMiddle)
        vh = self.table.verticalHeader()
        vh.setDefaultSectionSize(22)
        vh.setMinimumSectionSize(18)

        # context menu and keyboard shortcut
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(lambda pos: self.table_manager.table_context_menu(pos))

        # remove using the delete key
        act_del = QAction(self)
        act_del.setShortcut(QKeySequence.Delete)
        act_del.triggered.connect(lambda: self.table_manager.remove_selected_rows())
        self.table.addAction(act_del)

    def _init_button_row(self) -> None:
        """
        Initializes the button row at the bottom of the window.

        **Returns:**
            `None`
        """
        # lower buttons row
        self.button_row = QHBoxLayout()

        # clear list
        self.btn_clear = QPushButton(self.helpers.tr('actions.clear_list'))
        self.btn_clear.clicked.connect(lambda: self.table_manager.clear_table())
        self.button_row.addWidget(self.btn_clear, alignment=Qt.AlignLeft)

        self.button_row.addStretch(1)

        # rename
        self.btn_rename = QPushButton(self.helpers.tr('actions.rename'))
        self.btn_rename.clicked.connect(lambda: self.rename_manager.perform_rename())
        self.button_row.addWidget(self.btn_rename)

        # undo
        self.btn_undo = QPushButton(self.helpers.tr('actions.undo'))
        self.btn_undo.clicked.connect(lambda: self.rename_manager.perform_undo())
        self.button_row.addWidget(self.btn_undo)

    def _init_layout_constraints(self) -> None:
        """
        Sets up the layout constraints and arrangements.

        **Returns:**
            `None`
        """
        # behavior of the upper sections
        self.rename_box.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        self.ext_box.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        self.search_box.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        self.counter_box.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)

        # table should grow in both directions
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # grid arrangement
        self.grid_layout.addWidget(self.rename_box,    0, 0, 2, 1)
        self.grid_layout.addWidget(self.ext_box,       0, 1, 1, 1)
        self.grid_layout.addWidget(self.search_box,    0, 2, 1, 1)
        self.grid_layout.addWidget(self.counter_box,   0, 3, 1, 1)
        self.grid_layout.addWidget(self.advanced_opts, 1, 1, 1, 3)

        stretch_right = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.grid_layout.addItem(stretch_right, 0, 4, 2, 1)
        self.grid_layout.setColumnStretch(4, 1)

        self.grid_layout.addWidget(self.table,   2, 0, 1, 5)
        self.grid_layout.addLayout(self.button_row,   3, 0, 1, 5)

        # columns stretch
        self.grid_layout.setColumnStretch(0, 0)
        self.grid_layout.setColumnStretch(1, 0)
        self.grid_layout.setColumnStretch(2, 0)
        self.grid_layout.setColumnStretch(3, 0)

        # rows stretch
        self.grid_layout.setRowStretch(0, 0)
        self.grid_layout.setRowStretch(1, 0)
        self.grid_layout.setRowStretch(2, 1)
        self.grid_layout.setRowStretch(3, 0)

        self.grid_layout.setVerticalSpacing(5)
        self.grid_layout.setHorizontalSpacing(5)

        # window size must not be smaller than the minimum layout
        self.root_layout.setSizeConstraint(QLayout.SetMinimumSize)

    def _init_signal_handlers(self) -> None:
        """
        Connects all signal handlers for UI elements.

        **Returns:**
            `None`
        """
        # Connect signal handlers after all UI elements are created
        if hasattr(self, 'btn_name') and self.btn_name is not None and hasattr(self, 'edit_mask') and self.edit_mask is not None:
            self.btn_name.clicked.connect(lambda: self.helpers.insert_token(self.edit_mask, DEFAULT_TOKEN_NAME))
            self.btn_name_slice.clicked.connect(lambda: self.helpers.insert_token(self.edit_mask, DEFAULT_TOKEN_NAME_SLICE))
            self.btn_counter.clicked.connect(lambda: self.helpers.insert_token(self.edit_mask, DEFAULT_TOKEN_COUNTER))
            self.btn_date.clicked.connect(lambda: self.helpers.insert_token(self.edit_mask, DEFAULT_TOKEN_DATE))
            self.btn_time.clicked.connect(lambda: self.helpers.insert_token(self.edit_mask, DEFAULT_TOKEN_TIME))
        
        # Connect signal handlers for extension section
        if hasattr(self, 'btn_ext') and self.btn_ext is not None and hasattr(self, 'edit_ext') and self.edit_ext is not None:
            self.btn_ext.clicked.connect(lambda: self.helpers.insert_token(self.edit_ext, DEFAULT_TOKEN_EXT))
            self.btn_ext_slice.clicked.connect(lambda: self.helpers.insert_token(self.edit_ext, DEFAULT_TOKEN_EXT_SLICE))
            self.btn_ext_counter.clicked.connect(lambda: self.helpers.insert_token(self.edit_ext, DEFAULT_TOKEN_COUNTER))

    def _finalize_setup(self) -> None:
        """
        Finalizes the setup with tooltips and window sizing.

        **Returns:**
            `None`
        """
        # save calculated minimum window width
        self.MIN_WIDTH = self.minimumSizeHint().width()

        # trigger initial (empty) preview
        self.table_manager.update_preview_later()

        # disable undo if no undo log is present
        self.rename_manager.update_undo_state()

        # applies tooltips
        self.helpers.apply_tooltips()

        self.resize(self.MIN_WIDTH, self.height())

    def _create_section_rename(self) -> QGroupBox:
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
        box = QGroupBox(self.helpers.tr('sections.rename.title'))
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

        # click handler - will be connected in __init__ after all UI elements are created

        # date row
        date_row = QHBoxLayout()
        date_row.setAlignment(Qt.AlignLeft)

        # date format label
        lbl_date = QLabel(self.helpers.tr('sections.rename.lbl_datefmt'))

        # date format combobox
        self.cmb_date = QComboBox()
        self.cmb_date.addItems(['YYYYMMDD', 'DDMMYYYY', 'MMDDYYYY'])
        self.cmb_date.setMaximumWidth(120)

        # date seperator label
        lbl_date_sep = QLabel(self.helpers.tr('sections.rename.lbl_sep'))

        # date seperator combobox
        self.cmb_date_sep = QComboBox()
        self.cmb_date_sep.addItem('-', '-')
        self.cmb_date_sep.addItem('_', '_')
        self.cmb_date_sep.addItem('.', '.')
        if not self.helpers.is_windows():  # add colon only on non-Windows systems
            self.cmb_date_sep.addItem(':', ':')
        self.cmb_date_sep.addItem(';', ';')
        self.cmb_date_sep.addItem(self.helpers.tr('sections.rename.sep_none'), 'none')
        self.cmb_date_sep.addItem(self.helpers.tr('sections.rename.sep_space'), 'space')

        for i in (lbl_date, self.cmb_date, lbl_date_sep, self.cmb_date_sep):
            date_row.addWidget(i)

        layout.addLayout(date_row)

        # time row
        time_row = QHBoxLayout()
        time_row.setAlignment(Qt.AlignLeft)

        # time format label
        lbl_time = QLabel(self.helpers.tr('sections.rename.lbl_timefmt'))

        # time format combobxo
        self.cmb_time = QComboBox()
        self.cmb_time.addItems(['HHMMSS', 'HHMM', 'HH'])
        self.cmb_time.setMaximumWidth(120)

        # time seperator label
        lbl_time_sep = QLabel(self.helpers.tr('sections.rename.lbl_sep'))

        # time seperator combobox
        self.cmb_time_sep = QComboBox()
        self.cmb_time_sep.addItem('-', '-')
        self.cmb_time_sep.addItem('_', '_')
        self.cmb_time_sep.addItem('.', '.')
        if not self.helpers.is_windows():  # add colon only on non-Windows systems
            self.cmb_time_sep.addItem(':', ':')
        self.cmb_time_sep.addItem(';', ';')
        self.cmb_time_sep.addItem(self.helpers.tr('sections.rename.sep_none'), 'none')
        self.cmb_time_sep.addItem(self.helpers.tr('sections.rename.sep_space'), 'space')

        for i in (lbl_time, self.cmb_time, lbl_time_sep, self.cmb_time_sep):
            time_row.addWidget(i)

        layout.addLayout(time_row)

        # datetype row
        datetype_row = QHBoxLayout()
        datetype_row.setAlignment(Qt.AlignLeft)

        # datetype label
        lbl_datetype = QLabel(self.helpers.tr('sections.rename.date_type'))

        # datetype combobox
        self.cmb_datetype = QComboBox()
        self.cmb_datetype.addItem(self.helpers.tr('sections.rename.date_current'), 'current')
        self.cmb_datetype.addItem(self.helpers.tr('sections.rename.date_change'), 'change')

        for i in (lbl_datetype, self.cmb_datetype):
            datetype_row.addWidget(i)

        layout.addLayout(datetype_row)

        # loads values from the config
        self.cmb_date.setCurrentText(self.cfg.get('rename', 'date_format', fallback='YYYYMMDD'))
        self.cmb_time.setCurrentText(self.cfg.get('rename', 'time_format', fallback='HHMM'))
        self.helpers.set_combo_by_data(self.cmb_date_sep, self.cfg.get('rename', 'date_seperator', fallback='-'))
        self.helpers.set_combo_by_data(self.cmb_time_sep, self.cfg.get('rename', 'time_seperator', fallback='-'))
        self.helpers.set_combo_by_data(self.cmb_datetype, self.cfg.get('rename', 'date_type', fallback='current'))

        # saves values in the config
        self.cmb_date.currentTextChanged.connect(
            lambda _: self.rename_manager.handle_config_change('rename', 'date_format', self.cmb_date.currentText()))
        self.cmb_time.currentTextChanged.connect(
            lambda _: self.rename_manager.handle_config_change('rename', 'time_format', self.cmb_time.currentText()))
        self.cmb_date_sep.currentIndexChanged.connect(
            lambda _: self.rename_manager.handle_config_change('rename', 'date_seperator', self.cmb_date_sep.currentData()))
        self.cmb_time_sep.currentIndexChanged.connect(
            lambda _: self.rename_manager.handle_config_change('rename', 'time_seperator', self.cmb_time_sep.currentData()))
        self.cmb_datetype.currentIndexChanged.connect(
            lambda _: self.rename_manager.handle_config_change('rename', 'date_type', self.cmb_datetype.currentData()))

        # refresh preview when the input field is updated
        self.edit_mask.textChanged.connect(lambda: self.table_manager.update_preview_later())

        # style settings
        layout.addStretch(1)
        box.setStyleSheet(GROUPBOX_STYLE)

        return box

    def _create_section_extension(self) -> QGroupBox:
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
        box = QGroupBox(self.helpers.tr('sections.extension.title'))
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

        # click handler - will be connected in __init__ after all UI elements are created

        # refresh preview when the input field is updated
        self.edit_ext.textChanged.connect(lambda: self.table_manager.update_preview_later())

        # style settings
        box.setStyleSheet(GROUPBOX_STYLE)

        return box

    def _create_section_replace(self) -> QGroupBox:
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
        box = QGroupBox(self.helpers.tr('sections.replace.title'))
        layout = QVBoxLayout(box)
        layout.setAlignment(Qt.AlignTop)

        # search & replace grid
        grid = QGridLayout()

        lbl_search = QLabel(self.helpers.tr('sections.replace.lbl_search'))
        self.edit_search = QLineEdit()
        self.edit_search.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        lbl_replace = QLabel(self.helpers.tr('sections.replace.lbl_replace'))
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

        self.cb_regex = QCheckBox(self.helpers.tr('sections.replace.cb_regex'))
        self.cb_first_match = QCheckBox(self.helpers.tr('sections.replace.cb_first_match'))
        self.cb_exact_match = QCheckBox(self.helpers.tr('sections.replace.cb_exact_matches'))

        for c in (self.cb_regex, self.cb_first_match, self.cb_exact_match):
            upper_opt_row.addWidget(c)

        layout.addLayout(upper_opt_row)

        # lower checkbox row
        lower_opt_row = QHBoxLayout()
        lower_opt_row.setAlignment(Qt.AlignLeft)

        self.cb_case_sens = QCheckBox(self.helpers.tr('sections.replace.cb_case_sens'))
        self.cb_ignore_ext = QCheckBox(self.helpers.tr('sections.replace.cb_ignore_ext'))

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
            lambda v: self.rename_manager.handle_config_change('replace', 'regex', v))
        self.cb_first_match.toggled.connect(
            lambda v: self.rename_manager.handle_config_change('replace', 'only_first_match', v))
        self.cb_exact_match.toggled.connect(
            lambda v: self.rename_manager.handle_config_change('replace', 'exact_match', v))
        self.cb_case_sens.toggled.connect(
            lambda v: self.rename_manager.handle_config_change('replace', 'case_sensitive', v))
        self.cb_ignore_ext.toggled.connect(
            lambda v: self.rename_manager.handle_config_change('replace', 'exclude_extension', v))

        # refresh preview when the input field is updated
        self.edit_search.textChanged.connect(lambda: self.table_manager.update_preview_later())
        self.edit_replace.textChanged.connect(lambda: self.table_manager.update_preview_later())

        # style settings
        layout.addStretch(1)
        box.setStyleSheet(GROUPBOX_STYLE)

        return box

    def _create_section_counter(self) -> QGroupBox:
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
        box = QGroupBox(self.helpers.tr('sections.counter.title'))
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
            self.helpers.tr('sections.counter.lbl_start'), 'counter', 'start', 0, 999999)
        self.spin_step = add_counter_row(
            self.helpers.tr('sections.counter.lbl_step'), 'counter', 'step', 1, 9999)
        self.spin_digits = add_counter_row(
            self.helpers.tr('sections.counter.lbl_digits'), 'counter', 'digits', 1, 10, 45)

        # checkbox for inversion
        self.cb_dupes = QCheckBox(self.helpers.tr('sections.counter.dupes'))
        self.cb_dupes.setChecked(self.cfg.getboolean('counter', 'dupes_only', fallback=False))
        layout.addWidget(self.cb_dupes)

        # saves the current values in the config
        self.spin_start.valueChanged.connect(
            lambda v: self.rename_manager.handle_config_change('counter', 'start', v))
        self.spin_step.valueChanged.connect(
            lambda v: self.rename_manager.handle_config_change('counter', 'step', v))
        self.spin_digits.valueChanged.connect(
            lambda v: self.rename_manager.handle_config_change('counter', 'digits', v))
        self.cb_dupes.toggled.connect(
            lambda v: self.rename_manager.handle_config_change('counter', 'dupes_only', v))

        # style settings
        layout.addStretch(1)
        box.setStyleSheet(GROUPBOX_STYLE)

        return box

    def _create_section_advanced_options(self) -> QGroupBox:
        """
        Creates the section for advanced options.

        Contains:
        - Dropdown menu for case sensitivity
        - A checkbox for Windows-compatible file names (always active in Windows)
        - The option to open the current target names in the system editor for manual editing

        **Returns:**
            `QGroupBox`: Widget with all advanced options controls
        """
        box = QGroupBox(self.helpers.tr('sections.advanced_opts.title'))
        layout = QVBoxLayout(box)
        layout.setAlignment(Qt.AlignTop)
        layout.setContentsMargins(8, 0, 8, 0)  # smaller gap at the top and bottom

        # row for the options
        row = QHBoxLayout()
        row.setAlignment(Qt.AlignLeft)

        # upper/lower case
        lbl_case = QLabel(self.helpers.tr('sections.advanced_opts.lbl_case'))
        self.cmb_case = QComboBox()
        self.cmb_case.addItem(self.helpers.tr('sections.advanced_opts.case_values.unchanged'), 'unchanged')
        self.cmb_case.addItem(self.helpers.tr('sections.advanced_opts.case_values.lowercase'), 'lowercase')
        self.cmb_case.addItem(self.helpers.tr('sections.advanced_opts.case_values.uppercase'), 'uppercase')
        self.cmb_case.addItem(self.helpers.tr('sections.advanced_opts.case_values.heading'), 'heading')
        self.cmb_case.addItem(self.helpers.tr('sections.advanced_opts.case_values.mocking'), 'mocking')

        # windows-compatible names
        self.cb_windows = QCheckBox(self.helpers.tr('sections.advanced_opts.cb_windows'))
        self.cb_windows.setChecked(True if self.helpers.is_windows() else self.cfg.getboolean('advanced', 'windows_names', fallback=False))

        # on windows: gray out the checkbox and force it to be active
        if self.helpers.is_windows():
            self.cb_windows.setEnabled(False)

        # open in editor
        self.btn_editor = QPushButton(self.helpers.tr('sections.advanced_opts.btn_editor'))

        row.addWidget(lbl_case)
        row.addWidget(self.cmb_case)
        row.addStretch(1)
        row.addWidget(self.cb_windows)
        row.addStretch(1)
        row.addWidget(self.btn_editor, alignment=Qt.AlignRight)

        layout.addLayout(row)

        # loads values from the config
        self.helpers.set_combo_by_data(self.cmb_case, self.cfg.get('advanced', 'case', fallback='unchanged'))
        self.cb_windows.setChecked(self.cfg.getboolean('advanced', 'windows_names', fallback=False))

        # saves values in the config
        self.cmb_case.currentIndexChanged.connect(
            lambda _: self.rename_manager.handle_config_change('advanced', 'case', self.cmb_case.currentData()))
        self.cb_windows.toggled.connect(
            lambda v: self.rename_manager.handle_config_change('advanced', 'windows_names', v))

        # click handler
        self.btn_editor.clicked.connect(lambda: self.rename_manager.open_in_editor())

        # style settings
        box.setStyleSheet(GROUPBOX_STYLE)

        return box

    def eventFilter(self, obj, ev):
        """
        Intercepts resize and drag & drop events for the table.
        (Qt event handler)
        """
        return self.table_manager.eventFilter(obj, ev)
