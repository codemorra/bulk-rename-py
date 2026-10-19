"""Build local Windows or Linux x86-64 bundles with the active Python environment.

Install requirements-build.txt before running this script. Both build modes keep
their output under dist/ and their generated specs and work files under build/.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import platform
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_NAME = 'bulk-rename-py'
BUILD_MODES = ('onedir', 'onefile')


def build_command(mode: str) -> list[str]:
    """Construct the native build command for a supported platform and mode.

    **Parameters:**
        `mode` (str): Either "onedir" or "onefile"

    **Returns:**
        `list[str]`: PyInstaller command using the current Python interpreter

    **Raises:**
        `ValueError`: If the build mode, operating system, or architecture is unsupported
    """
    if mode not in BUILD_MODES:
        raise ValueError(f'Unsupported build mode: {mode}')
    if sys.platform not in ('win32', 'linux'):
        raise ValueError('Local builds support Windows and Linux only.')
    if platform.machine().lower() not in ('x86_64', 'amd64') or sys.maxsize <= 2**32:
        raise ValueError('Local builds require an x86-64 system and a 64-bit Python interpreter.')

    work_dir = PROJECT_ROOT / 'build' / mode
    command = [
        sys.executable, '-m', 'PyInstaller',
        f'--{mode}',
        '--name', APP_NAME,
        '--noconfirm', '--clean', '--noupx',
        '--distpath', str(PROJECT_ROOT / 'dist' / mode),
        '--workpath', str(work_dir / 'work'),
        '--specpath', str(work_dir),
        '--paths', str(PROJECT_ROOT / 'src'),
        '--add-data', f'{PROJECT_ROOT / "src" / "locale"}:locale',
        '--add-data', f'{PROJECT_ROOT / "LICENSE"}:.',
        '--add-data', f'{PROJECT_ROOT / "THIRD_PARTY_LICENSES.txt"}:.',
    ]
    if sys.platform == 'win32':
        command.extend([
            '--windowed', '--icon', str(PROJECT_ROOT / 'assets' / 'icons' / f'{APP_NAME}.ico'),
        ])
    command.append(str(PROJECT_ROOT / 'src' / 'main.py'))
    return command


def main(argv: list[str] | None = None) -> int:
    """Parse the build mode, check prerequisites, and return the build exit code.

    Dependencies must already be installed. No installation or publishing is
    performed; subprocess output is left visible for build diagnostics.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=BUILD_MODES, help='PyInstaller bundle format')
    args = parser.parse_args(argv)
    try:
        command = build_command(args.mode)
    except ValueError as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1

    if importlib.util.find_spec('PyInstaller') is None:
        print('Error: PyInstaller is missing. Install requirements-build.txt first.', file=sys.stderr)
        return 1

    # Keep PyInstaller's shared cache inside the project's ignored build directory.
    environment = {**os.environ, 'PYINSTALLER_CONFIG_DIR': str(PROJECT_ROOT / 'build' / 'cache')}
    try:
        result = subprocess.run(command, cwd=PROJECT_ROOT, env=environment, check=False)
    except OSError as error:
        print(f'Error: Could not start PyInstaller: {error}', file=sys.stderr)
        return 1

    if result.returncode:
        print(f'Error: PyInstaller failed with exit code {result.returncode}.', file=sys.stderr)
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
