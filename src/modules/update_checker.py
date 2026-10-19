"""Update checker module for Bulk Rename Py.

Provides functionality to check for new releases on GitHub.
Runs asynchronously to avoid blocking the GUI.
"""

from __future__ import annotations

import logging
import platform
import re
import threading

import certifi
import requests
from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


def _version_tuple(v: str) -> tuple[int, ...]:
    """Convert version string to comparable tuple.

    Removes leading 'v'/'V' and converts each component to a number
    to allow lexicographical version comparison.

    **Parameters:**
        `v` (str): Version string (e.g., 'v1.2.3' or '1.2.3')

    **Returns:**
        `tuple[int, ...]`: Numeric version tuple

    **Raises:**
        `ValueError`: If the release tag is not a numeric version

    **Example:**
        'v1.2.3' → (1, 2, 3)
    """
    value = v.strip()
    if not re.fullmatch(r'[vV]?[0-9]+(?:\.[0-9]+){0,2}', value):
        raise ValueError(f"Unsupported release version: {v!r}")
    parts = tuple(int(part) for part in value.lstrip('vV').split('.'))
    return parts + (0,) * (3 - len(parts))


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
            with requests.get(
                api,
                headers={'User-Agent': ua, 'Accept': 'application/vnd.github+json'},
                timeout=7.0,
                verify=certifi.where(),
            ) as response:
                response.raise_for_status()
                data = response.json()

            # Extract latest tag and release URL
            if not isinstance(data, dict) or not isinstance(data.get('tag_name'), str):
                raise TypeError('Release response must contain a version tag')
            tag = data['tag_name']
            url = data.get('html_url')
            if not isinstance(url, str) or not url:
                url = releases_url

            # Compare version numbers
            if _version_tuple(tag) > _version_tuple(self.current_version):
                status = 'available'
            else:
                status = 'none'

            # Emit success result
            logger.info('Update check completed: %s; latest version %s', status, tag)
            self.finished.emit(status, url)

        except (requests.RequestException, ValueError, TypeError):
            logger.exception('Update check failed')
            # Emit failure for network errors and malformed release data
            self.finished.emit('failed', releases_url)
