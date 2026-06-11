# -*- coding: utf-8 -*-

# Bulk Rename Py
# © 2026–present Codemorra (Christopher Kranz)
# Licensed under the MIT License (see LICENSE file)

"""Main window module for Bulk Rename Py.

Handles the main application window setup, UI layout, menu bar configuration,
table management, and signal handling for the bulk file renaming application.
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
from ..settings import (
    get_config, get_language_from_config, ensure_config_file, CONFIG_FILE
    )
from .rename_manager import RenameManager
from .table_manager import TableManager
from .gui_helpers import GUIHelpers, DEFAULT_TOKEN_NAME, DEFAULT_TOKEN_EXT, DEFAULT_TOKEN_COUNTER, DEFAULT_TOKEN_DATE, DEFAULT_TOKEN_TIME, DEFAULT_TOKEN_NAME_SLICE, DEFAULT_TOKEN_EXT_SLICE
from .about_dialog import AboutDialog
from .create_sections import CreateSections

# Constants
MIN_WINDOW_WIDTH = 1
DEFAULT_WINDOW_SIZE = (1280, 800)


class MainWindow(QMainWindow):
    """Main application window for Bulk Rename Py.
    
    Central component that manages the complete GUI including menu bar, file table,
    renaming sections, and user interactions. Coordinates between all GUI components
    and handles the application's main workflow.
    """
    MIN_WIDTH = MIN_WINDOW_WIDTH

    def __init__(self):
        """Initialize main window.

        **Returns:**
            `None`
        """
        super().__init__()
        self._setup_main_window()

    def _setup_main_window(self) -> None:
        """Set up main window components.

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
        """Initialize configuration and settings.

        **Returns:**
            `None`
        """
        # Load config + language
        ensure_config_file()
        self.cfg = get_config()
        self.translator = Translator(get_language_from_config())

        # Initialize helper attributes
        self._next_window = None
        self.helpers = GUIHelpers(self)

        # Always enforce Windows-compatible names in Windows
        if self.helpers.is_windows():
            if (not self.cfg.has_section('advanced')) or (not self.cfg.getboolean('advanced', 'windows_names', fallback=False)):
                if not self.cfg.has_section('advanced'):
                    self.cfg.add_section('advanced')
                self.cfg.set('advanced', 'windows_names', 'True')
                with CONFIG_FILE.open('w', encoding='utf-8') as f:
                    self.cfg.write(f)

        # Timer for delayed preview of new file names
        self._update_timer = QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.timeout.connect(lambda: self.rename_manager.update_preview_now())

        # Variable for multi-level in-memory undo
        self._undo_stack: list[list[tuple[Path, Path]]] = []
        self.rename_manager = RenameManager(self)
        self.table_manager = TableManager(self)
        self.about_dialog = AboutDialog(self)
        self.create_sections = CreateSections(self)

        # Window setup
        self.setWindowTitle(self.helpers.tr('app'))
        self.resize(*DEFAULT_WINDOW_SIZE)

    def _init_menu_bar(self) -> None:
        """Initialize menu bar with file operations and settings.

        **Returns:**
            `None`
        """
        menubar = self.menuBar()
        menu_file = menubar.addMenu(self.helpers.tr('menu.file'))
        menu_file.setToolTipsVisible(True)

        # Import single/multiple files
        self.act_add_files = QAction(self.helpers.tr('menu.add_files'), self)
        self.act_add_files.setShortcut('Ctrl+O')
        self.act_add_files.triggered.connect(lambda: self.rename_manager.action_open_files())
        menu_file.addAction(self.act_add_files)

        # Import entire directories
        self.act_add_folder = QAction(self.helpers.tr('menu.add_folder'), self)
        self.act_add_folder.setShortcut('Ctrl+Shift+O')
        self.act_add_folder.triggered.connect(lambda: self.rename_manager.action_open_folder())
        menu_file.addAction(self.act_add_folder)

        menu_file.addSeparator()

        # Include hidden files checkbox
        self.act_hidden = QAction(self.helpers.tr('menu.show_hidden'), self, checkable=True)
        self.act_hidden.setChecked(self.cfg.getboolean('general', 'hidden_files', fallback=False))
        self.act_hidden.toggled.connect(lambda v: self.rename_manager.handle_config_change('general', 'hidden_files', v))
        menu_file.addAction(self.act_hidden)

        # Language selection
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

        # Reset settings option
        self.act_reset = QAction(self.helpers.tr('menu.reset_settings'), self)
        self.act_reset.triggered.connect(lambda: self.rename_manager.reset_all_settings())
        menu_file.addAction(self.act_reset)

        menu_file.addSeparator()

        # About
        self.act_about = QAction(self.helpers.tr('menu.about'), self)
        self.act_about.triggered.connect(lambda: self.about_dialog.show_about_dialog())
        menu_file.addAction(self.act_about)

        menu_file.addSeparator()

        # Exit option
        self.act_exit = QAction(self.helpers.tr('menu.exit'), self)
        self.act_exit.setShortcut('Ctrl+Q')
        self.act_exit.triggered.connect(self.close)
        menu_file.addAction(self.act_exit)

    def _init_main_layout(self) -> None:
        """Initialize main layout structure.

        **Returns:**
            `None`
        """
        # Central widget with vertical main layout
        central = QWidget(self)
        self.setCentralWidget(central)
        self.root_layout = QVBoxLayout(central)
        self.grid_layout = QGridLayout()
        self.root_layout.addLayout(self.grid_layout)

        # Create sections
        self.rename_box = self.create_sections.rename_section()
        self.ext_box = self.create_sections.extension_section()
        self.search_box = self.create_sections.replace_section()
        self.counter_box = self.create_sections.counter_section()
        self.advanced_opts = self.create_sections.advanced_options_section()

    def _init_table(self) -> None:
        """Initialize table widget for file display.

        **Returns:**
            `None`
        """
        # Create a table (two columns: current name, new name)
        self.table = QTableWidget(0, 2, self)
        self.table.setHorizontalHeaderLabels([
            self.helpers.tr('table.current_name'),
            self.helpers.tr('table.new_name')
        ])

        # Drag & drop
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
        """Initialize button row for actions.

        **Returns:**
            `None`
        """
        # Lower buttons row
        self.button_row = QHBoxLayout()

        # Clear list
        self.btn_clear = QPushButton(self.helpers.tr('actions.clear_list'))
        self.btn_clear.clicked.connect(lambda: self.table_manager.clear_table())
        self.button_row.addWidget(self.btn_clear, alignment=Qt.AlignLeft)

        self.button_row.addStretch(1)

        # Rename
        self.btn_rename = QPushButton(self.helpers.tr('actions.rename'))
        self.btn_rename.clicked.connect(lambda: self.rename_manager.perform_rename())
        self.button_row.addWidget(self.btn_rename)

        # Undo
        self.btn_undo = QPushButton(self.helpers.tr('actions.undo'))
        self.btn_undo.clicked.connect(lambda: self.rename_manager.perform_undo())
        self.button_row.addWidget(self.btn_undo)

    def _init_layout_constraints(self) -> None:
        """Initialize layout constraints and grid arrangement.

        **Returns:**
            `None`
        """
        # Behavior of the upper sections
        self.rename_box.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        self.ext_box.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        self.search_box.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        self.counter_box.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)

        # Table should grow in both directions
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Grid arrangement
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

        # Columns stretch
        self.grid_layout.setColumnStretch(0, 0)
        self.grid_layout.setColumnStretch(1, 0)
        self.grid_layout.setColumnStretch(2, 0)
        self.grid_layout.setColumnStretch(3, 0)

        # Rows stretch
        self.grid_layout.setRowStretch(0, 0)
        self.grid_layout.setRowStretch(1, 0)
        self.grid_layout.setRowStretch(2, 1)
        self.grid_layout.setRowStretch(3, 0)

        self.grid_layout.setVerticalSpacing(5)
        self.grid_layout.setHorizontalSpacing(5)

        # Window size must not be smaller than the minimum layout
        self.root_layout.setSizeConstraint(QLayout.SetMinimumSize)

    def _init_signal_handlers(self) -> None:
        """Initialize signal handlers for UI elements.

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
        """Finalize window setup and apply initial state.

        **Returns:**
            `None`
        """
        self.MIN_WIDTH = self.minimumSizeHint().width()

        self.table_manager.update_preview_later()

        self.rename_manager.update_undo_state()

        self.helpers.apply_tooltips()

        self.resize(self.MIN_WIDTH, self.height())

    def eventFilter(self, obj, ev):
        """Event filter for table events.

        **Parameters:**
            `obj`: Object receiving the event
            `ev`: Event object

        **Returns:**
            `bool`: Result from table manager's event filter
        """
        return self.table_manager.eventFilter(obj, ev)
