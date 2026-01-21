# -*- coding: utf-8 -*-

# Bulk Rename Py
# © 2026–present Codemorra
# Licensed under the MIT License (see LICENSE file)

"""
UpdateChecker service for Bulk Rename Py.

Asynchronously checks whether a newer version is available on GitHub.
To do this, the API of the specified repository is queried and the
current release tag is compared with the current program version.
"""

from __future__ import annotations
import os
import threading
import platform
import requests
import certifi
from PySide6.QtCore import QObject, Signal


# --- Protected Helper Function ---
def _version_tuple(v: str) -> tuple[int, ...]:
    """
    Converts a version string into a comparison tuple.

    Removes leading “v”/“V” and converts each component to a number
    to allow version numbers to be compared lexicographically.

    **Parameters:**
        `v` (str): Version string.

    **Returns:**
        `tuple[int, ...]`: Numeric parts of the version as a tuple.
    """
    # remove leading 'v' or 'V' and surrounding whitespace
    v = v.strip().lstrip('vV')
    parts = []

    # split by dots and extract numeric components only
    for p in v.split('.'):
        d = ''.join(ch for ch in p if ch.isdigit())
        parts.append(int(d or '0'))

    # return tuple for lexicographical version comparison
    return tuple(parts) if parts else (0,)


class UpdateChecker(QObject):
    """
    Asynchronously checks whether a new release is available on GitHub.

    Starts a thread that queries the GitHub API, reads the latest
    release tag, and compares it with the current program version.
    Once complete, the `finished` signal is triggered.

    **Signals:**
    - `finished(bool, str)`: Triggered after the check.
    - `str`: Status of the update check:
        - `"available"` -> a newer version is available
        - `"none"` -> no newer version is available
        - `"failed"` -> the update check failed
    - `str`: URL to the project's release page.
    """
    finished = Signal(str, str)  # (available, release_url)

    def __init__(self, repo: str, current_version: str) -> None:
        """
        Initializes the UpdateChecker with repository and current version.

        **Parameters:**
            `repo` (str): GitHub repository in the format “user/repo”.
            `current_version` (str): Local program version (e.g., `“1.2.0”` or `“v1.2.0”`).

        **Returns:**
            `None`
        """
        super().__init__()
        self.repo = repo
        self.current_version = current_version

    def start(self) -> None:
        """
        Starts the check in a separate thread.

        Executes the `_run()` method asynchronously so as not to block the GUI.

        **Returns:**
            `None`
        """
        # run the update check asynchronously to avoid blocking the GUI
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        """
        Performs the actual update check.

        Queries the GitHub API for the latest release tag,
        compares it with the current program version,
        and sends the result via the `finished` signal.

        On errors, emits: finished(False, <releases-url>)

        **Returns:**
            `None`
        """
        # build API and repository URLs
        api = f'https://api.github.com/repos/{self.repo}/releases/latest'
        releases_url = f'https://github.com/{self.repo}/releases'

        # construct a detailed User-Agent string for the request
        ua = f'BulkRenamePy/{self.current_version} ({platform.system()}; {platform.machine()})'

        try:
            # request the latest release information from GitHub
            r = requests.get(
                api,
                headers={'User-Agent': ua, 'Accept': 'application/vnd.github+json'},
                timeout=7.0,
                verify=certifi.where(),
            )
            # raise exception for HTTP errors
            r.raise_for_status()
            data = r.json()

            # extract latest tag and release URL
            tag = (data.get('tag_name') or '').strip()
            url = data.get('html_url') or releases_url

            # compare version numbers to detect newer releases
            if _version_tuple(tag) > _version_tuple(self.current_version):
                status = 'available'
            else:
                status = 'none'

            # emit result via signal (update available?, release URL)
            self.finished.emit(status, url)

        except Exception:
            # on error -> emit failure state and fallback release URL
            self.finished.emit('failed', releases_url)
