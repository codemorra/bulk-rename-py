"""Tests for native build selection, isolated outputs, and build failure reporting."""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def build_script(monkeypatch):
    """Load the build script without requiring PyInstaller or starting a build."""
    source = Path(__file__).resolve().parents[1] / 'scripts' / 'build.py'
    spec = importlib.util.spec_from_file_location('build_script', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(sys, 'platform', 'linux')
    monkeypatch.setattr(sys, 'maxsize', 2**63 - 1)
    monkeypatch.setattr(module.platform, 'machine', lambda: 'x86_64')
    return module


@pytest.mark.parametrize('system', ['linux', 'win32'])
@pytest.mark.parametrize('mode', ['onedir', 'onefile'])
def test_native_build_layout(build_script, monkeypatch, tmp_path, system, mode):
    """Test mode separation, bundled resource placement, and Windows GUI settings."""
    monkeypatch.setattr(sys, 'platform', system)
    monkeypatch.setattr(build_script.platform, 'machine', lambda: 'AMD64' if system == 'win32' else 'x86_64')
    root = tmp_path / 'project with spaces'
    monkeypatch.setattr(build_script, 'PROJECT_ROOT', root)

    command = build_script.build_command(mode)

    assert command[:3] == [sys.executable, '-m', 'PyInstaller']
    assert f'--{mode}' in command
    assert f'--{"onefile" if mode == "onedir" else "onedir"}' not in command
    assert command[command.index('--distpath') + 1] == str(root / 'dist' / mode)
    assert command[command.index('--workpath') + 1] == str(root / 'build' / mode / 'work')
    assert command[command.index('--specpath') + 1] == str(root / 'build' / mode)
    resources = [command[index + 1] for index, value in enumerate(command) if value == '--add-data']
    assert resources == [
        f'{root / "src" / "locale"}:locale',
        f'{root / "LICENSE"}:.',
        f'{root / "THIRD_PARTY_LICENSES.txt"}:.',
    ]
    assert ('--windowed' in command) == (system == 'win32')
    if system == 'win32':
        assert command[command.index('--icon') + 1] == str(root / 'assets' / 'icons' / 'bulk-rename-py.ico')
    else:
        assert '--icon' not in command
    assert command[-1] == str(root / 'src' / 'main.py')


@pytest.mark.parametrize(('system', 'machine', 'maxsize'), [
    ('darwin', 'x86_64', 2**63 - 1),
    ('linux', 'aarch64', 2**63 - 1),
    ('win32', 'ARM64', 2**63 - 1),
    ('linux', 'x86_64', 2**31 - 1),
])
def test_unsupported_build_hosts_are_rejected(build_script, monkeypatch, system, machine, maxsize):
    """Reject unsupported operating systems, CPU architectures, and 32-bit Python."""
    monkeypatch.setattr(sys, 'platform', system)
    monkeypatch.setattr(sys, 'maxsize', maxsize)
    monkeypatch.setattr(build_script.platform, 'machine', lambda: machine)

    with pytest.raises(ValueError, match='Windows and Linux|x86-64'):
        build_script.build_command('onedir')


def test_invalid_mode_stops_before_build(build_script):
    """Reject invalid modes through both the command builder and CLI."""
    with pytest.raises(ValueError, match='Unsupported build mode'):
        build_script.build_command('invalid')
    with pytest.raises(SystemExit) as error:
        build_script.main(['invalid'])
    assert error.value.code == 2


def test_missing_pyinstaller_reports_prerequisite(build_script, monkeypatch, capsys):
    """Report a missing build dependency without attempting installation or a build."""
    monkeypatch.setattr(build_script.importlib.util, 'find_spec', lambda name: None)

    assert build_script.main(['onedir']) == 1
    assert 'Install requirements-build.txt first' in capsys.readouterr().err


@pytest.mark.parametrize('exit_code', [0, 7])
def test_build_uses_project_paths_and_forwards_exit_code(
        build_script, monkeypatch, tmp_path, capsys, exit_code):
    """Run from another directory while keeping work and cache inside the project."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(build_script.importlib.util, 'find_spec', lambda name: object())
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=exit_code)

    monkeypatch.setattr(build_script.subprocess, 'run', run)

    assert build_script.main(['onefile']) == exit_code
    assert len(calls) == 1
    command, kwargs = calls[0]
    assert command == build_script.build_command('onefile')
    assert kwargs['cwd'] == build_script.PROJECT_ROOT
    assert kwargs['env']['PYINSTALLER_CONFIG_DIR'] == str(build_script.PROJECT_ROOT / 'build' / 'cache')
    if exit_code:
        assert f'failed with exit code {exit_code}' in capsys.readouterr().err


def test_subprocess_start_failure_is_reported(build_script, monkeypatch, capsys):
    """Report process launch errors as a normal failed build."""
    monkeypatch.setattr(build_script.importlib.util, 'find_spec', lambda name: object())

    def fail(*args, **kwargs):
        raise OSError('Process launch failed')

    monkeypatch.setattr(build_script.subprocess, 'run', fail)

    assert build_script.main(['onedir']) == 1
    assert 'Could not start PyInstaller: Process launch failed' in capsys.readouterr().err
