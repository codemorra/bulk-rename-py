# -*- coding: utf-8 -*-

# Bulk Rename Py
# © 2026–present Codemorra (Christopher Kranz)
# Licensed under the MIT License (see LICENSE file)

"""Update checker module for Bulk Rename Py.

Provides functionality to check for new releases on GitHub.
Runs asynchronously to avoid blocking the GUI.
"""

from __future__ import annotations
import os
import threading
import platform
import requests
import certifi
from PySide6.QtCore import QObject, Signal


def _version_tuple(v: str) -> tuple[int, ...]:
    """Convert version string to comparable tuple.

    Removes leading 'v'/'V' and converts each component to a number
    to allow lexicographical version comparison.

    **Parameters:**
        `v` (str): Version string (e.g., 'v1.2.3' or '1.2.3')

    **Returns:**
        `tuple[int, ...]`: Numeric version tuple

    **Example:**
        'v1.2.3' → (1, 2, 3)
    """
    # Remove leading 'v' or 'V' and surrounding whitespace
    v = v.strip().lstrip('vV')
    parts = []

    # Split by dots and extract numeric components only
    for p in v.split('.'):
        d = ''.join(ch for ch in p if ch.isdigit())
        parts.append(int(d or '0'))

    # Return tuple for lexicographical version comparison
    return tuple(parts) if parts else (0,)


class UpdateChecker(QObject):
    """Asynchronous update checker.

    Checks GitHub API for newer releases in a separate thread.
    Emits finished signal when complete.

    Signals:
        finished(str, str): Emitted when check completes
            - str: 'available', 'none', or 'failed'
            - str: Release URL
    """
    finished = Signal(str, str)  # (status, release_url)

    def __init__(self, repo: str, current_version: str) -> None:
        """Initialize update checker.

        **Parameters:**
            `repo` (str): GitHub repository (user/repo)
            `current_version` (str): Current application version
        """
        super().__init__()
        self.repo = repo
        self.current_version = current_version

    def start(self) -> None:
        """Start update check in background thread.

        Runs asynchronously to avoid blocking the GUI.
        """
        # Run check in background thread
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        """Perform actual update check.

        Queries GitHub API, compares versions, and emits result.
        """
        # Build API and release URLs
        api = f'https://api.github.com/repos/{self.repo}/releases/latest'
        releases_url = f'https://github.com/{self.repo}/releases'

        # Construct detailed User-Agent string
        ua = f'BulkRenamePy/{self.current_version} ({platform.system()}; {platform.machine()})'

        try:
            # Request latest release information
            r = requests.get(
                api,
                headers={'User-Agent': ua, 'Accept': 'application/vnd.github+json'},
                timeout=7.0,
                verify=certifi.where(),
            )
            r.raise_for_status()
            data = r.json()

            # Extract latest tag and release URL
            tag = (data.get('tag_name') or '').strip()
            url = data.get('html_url') or releases_url

            # Compare version numbers
            if _version_tuple(tag) > _version_tuple(self.current_version):
                status = 'available'
            else:
                status = 'none'

            # Emit success result
            self.finished.emit(status, url)

        except Exception:
            # Emit failure result on any error
            self.finished.emit('failed', releases_url)
