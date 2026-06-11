# -*- coding: utf-8 -*-

# Bulk Rename Py
# © 2026–present Codemorra (Christopher Kranz)
# Licensed under the MIT License (see LICENSE file)

"""File import module for Bulk Rename Py.

Provides functionality for collecting files from specified paths
with configurable import options and duplicate handling.
"""

import ctypes
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True)
class ImportOptions:
    """Import configuration options.

    Attributes:
        allow_files: Whether regular files may be imported
        allow_dirs: Whether directories may be imported
        include_hidden: Whether hidden files/folders are included
    """
    allow_files: bool
    allow_dirs: bool
    include_hidden: bool


@dataclass(frozen=True)
class ImportItem:
    """Represents an imported file or directory.

    Attributes:
        path: Full path to the object
        is_dir: True if it is a directory
        mtime: Modification time in seconds since epoch, None on error
    """
    path: Path
    is_dir: bool
    mtime: float | None


class Importer:
    """File import operations.

    Provides functionality for collecting files from paths with various options.
    All methods are static as no instance state is required.
    """

    @staticmethod
    def collect(paths: list[str | Path], opts: ImportOptions) -> list[ImportItem]:
        """Collect files from specified paths.

        Searches the specified paths (either individual files or all files
        within a chosen directory) and filters out duplicates and hidden
        objects if include_hidden=False is set.

        **Parameters:**
            `paths` (list[str | Path]): List of start paths to import
            `opts` (ImportOptions): Import settings

        **Returns:**
            `list[ImportItem]`: List of imported file items
        """
        items: list[ImportItem] = []
        seen: set[str] = set()

        for raw in paths:
            p = Path(raw)
            if not p.exists():
                continue

            # Import single file
            if p.is_file():
                if opts.allow_files and (opts.include_hidden or not Importer._is_hidden(p)):
                    if (sp := str(p)) not in seen:
                        seen.add(sp)
                        items.append(ImportItem(p, False, Importer._mtime(p)))

            # Import directory contents
            elif p.is_dir() and opts.allow_files:
                for f in Importer._iter_files(p, opts.include_hidden):
                    sp = str(f)
                    if sp not in seen:
                        seen.add(sp)
                        items.append(ImportItem(f, False, Importer._mtime(f)))

        return items

    @staticmethod
    def _iter_files(root: Path, include_hidden: bool) -> Iterator[Path]:
        """Iterate over files in directory.

        **Parameters:**
            `root` (Path): Starting directory
            `include_hidden` (bool): Whether hidden files are included

        **Returns:**
            `Iterator[Path]`: Iterator over found files
        """
        for entry in root.iterdir():
            if entry.is_file() and (include_hidden or not Importer._is_hidden(entry)):
                yield entry

    @staticmethod
    def _mtime(p: Path) -> float | None:
        """Get file modification time.

        **Parameters:**
            `p` (Path): Path to the object

        **Returns:**
            `float | None`: Modification time in seconds since epoch
        """
        try:
            return p.stat().st_mtime
        except Exception:
            return None

    @staticmethod
    def _is_hidden(p: Path) -> bool:
        """Check if path is hidden (platform-dependent).

        **Parameters:**
            `p` (Path): Path to be checked

        **Returns:**
            `bool`: True if the object is hidden
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
