"""Safe execution and rollback of planned file renames.

Stages sources at temporary paths on the same filesystem, prevents
destination replacement, and reports actual file locations after failures.
"""

import ctypes
import errno
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from .types import RenameResult
from .validation import Validator

# Constants
AT_FDCWD = -100
RENAME_NOREPLACE = 1
logger = logging.getLogger(__name__)


@dataclass
class _MoveState:
    """Track the original, intended, temporary, and current paths of one file."""
    source: Path
    destination: Path
    temporary: Path
    current: Path


class MoveExecutor:
    """Execute file renames without replacing existing directory entries."""

    @staticmethod
    def execute(moves: list[tuple[Path, Path]]) -> RenameResult:
        """Execute a batch with staging and best-effort rollback on failure.

        **Parameters:**
            `moves` (list[tuple[Path, Path]]): Planned source-destination pairs

        **Returns:**
            `RenameResult`: Actual path changes, missing sources, and errors
        """
        result = RenameResult()
        # Use absolute paths without resolving final symlinks
        moves = [(src.absolute(), dst.absolute()) for src, dst in moves]
        states = []

        try:
            result.errors.extend(Validator.check_conflicts(moves))
            result.missing = [str(src) for src, _ in moves if not os.path.lexists(src)]
            for src, _ in moves:
                if src.is_dir() and not src.is_symlink():
                    result.errors.append(f"Cannot rename a directory as a file: {src}")
            if result.errors or result.missing:
                logger.warning(
                    'File move batch rejected: %d missing sources, %d errors',
                    len(result.missing), len(result.errors),
                )
                return result

            # Stage every source before assigning any final destination
            for src, dst in moves:
                if str(src) == str(dst):
                    continue
                temporary = src.with_name(f'.bulkrename-{uuid4().hex}')
                states.append(_MoveState(src, dst, temporary, src))

            for state in states:
                MoveExecutor._rename_no_replace(state.current, state.temporary)
                state.current = state.temporary

            for state in states:
                MoveExecutor._rename_no_replace(state.current, state.destination)
                state.current = state.destination

        except (OSError, ValueError) as e:
            logger.exception('File move batch failed')
            result.errors.append(f"Rename failed: {e}")
            MoveExecutor._rollback(states, result)
        result.moves = [(state.source, state.current) for state in states
                        if str(state.source) != str(state.current)]
        return result

    @staticmethod
    def _rollback(states: list[_MoveState], result: RenameResult) -> None:
        """Restore original paths without overwriting newly occupied paths.

        **Parameters:**
            `states` (list[_MoveState]): Tracked file locations
            `result` (RenameResult): Result to receive rollback errors

        **Returns:**
            `None`
        """
        logger.info('Rollback started: %d tracked files', len(states))
        # Vacate completed destinations before restoring sources in a cycle
        for state in states:
            if str(state.current) in (str(state.source), str(state.temporary)):
                continue
            try:
                MoveExecutor._rename_no_replace(state.current, state.temporary)
                state.current = state.temporary
            except OSError as e:
                logger.exception('Could not stage %s for rollback', state.current)
                result.errors.append(f"Could not stage {state.current} for rollback: {e}")

        for state in states:
            if str(state.current) == str(state.source):
                continue
            try:
                MoveExecutor._rename_no_replace(state.current, state.source)
                state.current = state.source
            except OSError as e:
                logger.exception(
                    'Could not restore %s; file remains at %s', state.source, state.current
                )
                result.errors.append(
                    f"Could not restore {state.source}; file remains at {state.current}: {e}"
                )

        remaining = sum(str(state.current) != str(state.source) for state in states)
        if remaining:
            logger.error('Rollback incomplete: %d files remain at changed paths', remaining)
        else:
            logger.info('Rollback completed: all tracked files restored')

    @staticmethod
    def _rename_no_replace(src: Path, dst: Path) -> None:
        """Atomically rename one directory entry without replacing a destination.

        **Parameters:**
            `src` (Path): Current file path
            `dst` (Path): Required unoccupied destination path

        **Returns:**
            `None`

        **Raises:**
            `OSError`: If the rename fails or safe renaming is unsupported
        """
        if os.name == 'nt':
            # Windows rename rejects existing destinations atomically
            os.rename(src, dst)
            return

        if sys.platform != 'linux':
            raise OSError(errno.ENOTSUP, 'Safe renaming requires Linux or Windows')

        # Linux renameat2 with RENAME_NOREPLACE also protects against target races
        libc = ctypes.CDLL(None, use_errno=True)
        try:
            renameat2 = libc.renameat2
        except AttributeError as e:
            raise OSError(errno.ENOTSUP, 'renameat2 is unavailable') from e
        renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p,
                             ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        renameat2.restype = ctypes.c_int
        if renameat2(AT_FDCWD, os.fsencode(src), AT_FDCWD,
                     os.fsencode(dst), RENAME_NOREPLACE) != 0:
            error = ctypes.get_errno()
            raise OSError(error, os.strerror(error), str(src), None, str(dst))
