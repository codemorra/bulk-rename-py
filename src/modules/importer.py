# -*- coding: utf-8 -*-

# Bulk Rename Py
# © 2026–present Codemorra
# Licensed under the MIT License (see LICENSE file)

"""
Import module for Bulk Rename Py.

Collect the files to be imported.
Used by the GUI to read and filter user paths.
"""

import ctypes
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


# --- Dataclasses ---
@dataclass(frozen=True)
class ImportOptions:
    """
    Import settings: determines which object types are permitted.

    **Attributes:**
        `allow_files` (bool): Whether regular files may be imported
        `allow_dirs` (bool): Whether directories may be imported
        `include_hidden` (bool): Whether hidden files/folders are included
    """
    allow_files: bool
    allow_dirs: bool
    include_hidden: bool

@dataclass(frozen=True)
class ImportItem:
    """
    Represents an imported object (file or directory).

    **Attributes:**
        `path` (Path): Full path to the object.
        `is_dir` (bool): True if it is a directory.
        `mtime` (float | None): Modification time in seconds since epoch, None on error.
    """
    path: Path
    is_dir: bool
    mtime: float | None


# --- Protected Functions ---
def _iter_files(root: Path, include_hidden: bool) -> Iterator[Path]:
    """
    Returns files in the specified root directory.

    **Parameters:**
        `root` (Path): Starting directory
        `include_hidden` (bool): Whether hidden files are included

    **Returns:**
        `Iterator[Path]`: Iterator over found files
    """
    for entry in root.iterdir():
        if entry.is_file() and (include_hidden or not _is_hidden(entry)):
            yield entry


def _mtime(p: Path) -> float | None:
    """
    Determines the modification time of an object (file or folder).

    **Parameters:**
        `p` (Path): Path to the object

    **Returns:**
        `float | None`: Modification time in seconds since epoch, or None if an error occurs
    """
    try:
        return p.stat().st_mtime
    except Exception:
        return None


def _is_hidden(p: Path) -> bool:
    """
    Checks whether a path is considered “hidden” (platform-dependent).

    **Parameters:**
        `p` (Path): Path to be checked

    **Returns:**
        `bool`: True if the object is hidden; otherwise False
    """
    if os.name == 'nt':
        # Windows: check file attributes (ignore dot prefix)
        try:
            attrs = ctypes.windll.kernel32.GetFileAttributesW(str(p))
            return attrs != -1 and bool(attrs & (0x2 | 0x4))  # HIDDEN | SYSTEM
        except Exception:
            return False
    else:
        # Unix-like: leading dot means hidden
        return p.name.startswith('.')


# --- Public Function ---
def collect(paths: list[str | Path], opts: ImportOptions) -> list[ImportItem]:
    """
    Collects all permitted files according to the import options.

    Searches the specified paths (either individual files or all files
    within a chosen directory) and filters out duplicates and hidden
    objects if `include_hidden=False` is set.

    **Parameters:**
        `paths` (list[str | Path]): List of start paths to import (files or directories)
        `opts` (ImportOptions): Import settings defining file permissions and hidden-file behavior

    **Returns:**
        `list[ImportItem]`: List of imported file items in the determined order
    """
    items: list[ImportItem] = []
    seen: set[str] = set()

    for raw in paths:
        p = Path(raw)
        if not p.exists():
            continue

        # Single file import
        if p.is_file():
            if opts.allow_files and (opts.include_hidden or not _is_hidden(p)):
                if (sp := str(p)) not in seen:
                    seen.add(sp)
                    items.append(ImportItem(p, False, _mtime(p)))

        # Directory import -> only files inside the directory
        elif p.is_dir() and opts.allow_files:
            for f in _iter_files(p, opts.include_hidden):
                sp = str(f)
                if sp not in seen:
                    seen.add(sp)
                    items.append(ImportItem(f, False, _mtime(f)))

    return items
