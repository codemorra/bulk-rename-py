"""File import module for Bulk Rename Py.

Provides functionality for collecting files from specified paths
with configurable import options and duplicate handling.
"""

import logging
import os
import stat
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from .core.validation import Validator

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ImportOptions:
    """Import configuration options.

    Attributes:
        allow_files: Whether regular files may be imported
        allow_dirs: Whether selected directories may be scanned for files
        include_hidden: Whether hidden files/folders are included
    """
    allow_files: bool
    allow_dirs: bool
    include_hidden: bool


class Importer:
    """File import operations.

    Provides functionality for collecting files from paths with various options.
    All methods are static as no instance state is required.
    """

    @staticmethod
    def collect(paths: list[str | Path], opts: ImportOptions) -> list[Path]:
        """Collect files from specified paths.

        Searches the specified paths (either individual files or all files
        within a chosen directory) and filters out duplicates and hidden
        objects if include_hidden=False is set.

        **Parameters:**
            `paths` (list[str | Path]): List of start paths to import
            `opts` (ImportOptions): Import settings

        **Returns:**
            `list[Path]`: Absolute file paths without duplicate directory entries
        """
        items = []
        seen = set()
        if not opts.allow_files:
            return items

        for raw in paths:
            path = Path(raw).absolute()
            if path.is_file():
                candidates = [path]
            elif opts.allow_dirs and path.is_dir():
                candidates = Importer._iter_files(path)
            else:
                continue
            for candidate in candidates:
                if not opts.include_hidden and Importer._is_hidden(candidate):
                    continue
                key = Validator.path_key(candidate)
                if key not in seen:
                    seen.add(key)
                    items.append(candidate)
        return items

    @staticmethod
    def _iter_files(root: Path) -> Iterator[Path]:
        """Iterate over files in directory.

        **Parameters:**
            `root` (Path): Starting directory

        **Returns:**
            `Iterator[Path]`: Iterator over found files
        """
        for entry in root.iterdir():
            if entry.is_file():
                yield entry

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
                attrs = p.stat(follow_symlinks=False).st_file_attributes
                return bool(attrs & (stat.FILE_ATTRIBUTE_HIDDEN | stat.FILE_ATTRIBUTE_SYSTEM))
            except OSError:
                logger.warning('Could not read hidden attributes for %s', p, exc_info=True)
                return False
        else:
            # Unix-like: leading dot means hidden
            return p.name.startswith('.')
