# -*- mode: python ; coding: utf-8 -*-

# Bulk Rename Py
# © 2026–present Codemorra
# Licensed under the MIT License (see LICENSE file)

from pathlib import Path
from PyInstaller.building.datastruct import Tree


ROOT = Path(SPECPATH).resolve().parents[1]
SRC  = ROOT / "src"

block_cipher = None

a = Analysis(
    [str(SRC / "bulk_rename_py.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=[],
    hiddenimports=["PySide6.QtSvg"],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebEngine",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtMultimedia",
        "PySide6.QtNetwork",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtDesigner",
        "PySide6.QtTest",
    ],
    noarchive=False,
)

a.datas += Tree(str(SRC / "locale"), prefix="locale")
a.datas += Tree(str(SRC / "licenses"), prefix="licenses")

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

version_file = str(ROOT / "packaging" / "windows" / "file_version.txt")

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='BulkRenamePy',
    console=False,
    icon=str(ROOT / "assets" / "icons" / "bulk-rename-py.ico"),
    version=version_file,
    contents_directory='app',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name='BulkRenamePy',
)
