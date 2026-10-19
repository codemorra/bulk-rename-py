"""Tests for independent core imports and lazy resource loading."""

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def test_core_imports_without_site_packages_or_application_resources(tmp_path):
    """Test core and package imports with Qt and requests unavailable."""
    source = Path(__file__).resolve().parents[1] / 'src'
    script = '''
import sys
sys.path.insert(0, sys.argv[1])
import modules.core
import modules.gui
assert modules.core.Renamer.plan_moves([], []) == []
assert not any(name.startswith(('PySide6', 'requests', 'modules.metadata', 'modules.settings'))
               for name in sys.modules)
'''
    result = subprocess.run([sys.executable, '-S', '-c', script, str(source)],
                            cwd=tmp_path, capture_output=True, text=True, timeout=10, check=False)

    assert result.returncode == 0, result.stderr


def test_metadata_import_does_not_read_license_files(tmp_path):
    """Test that missing license resources are reported only when explicitly requested."""
    source = Path(__file__).resolve().parents[1] / 'src' / 'modules' / 'metadata.py'
    copied = tmp_path / 'application' / 'modules' / 'metadata.py'
    copied.parent.mkdir(parents=True)
    copied.write_text(source.read_text(encoding='utf-8'), encoding='utf-8')
    spec = importlib.util.spec_from_file_location('isolated_metadata', copied)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.APP_INFO['name'] == 'Bulk Rename Py'
    with pytest.raises(RuntimeError, match='Could not find LICENSE'):
        module.get_license_text()


def test_relocated_icon_resources_render_svg(qt_application):
    """Test resource registration and SVG rendering with PySide6 Essentials."""
    import main

    icon = main.QIcon(':/icons/app.svg')

    assert not icon.pixmap(32, 32).isNull()


@pytest.mark.parametrize('layout', ['source', 'onedir', 'onefile'])
def test_relocated_application_resources(tmp_path, monkeypatch, layout):
    """Load both licenses and switch languages in source and frozen layouts."""
    project = Path(__file__).resolve().parents[1]
    if layout == 'source':
        resource_root = tmp_path / 'checkout'
        module_root = resource_root / 'src'
    else:
        resource_root = tmp_path / ('_internal' if layout == 'onedir' else '_MEI123456')
        module_root = resource_root
    modules_dir = module_root / 'modules'
    modules_dir.mkdir(parents=True)
    shutil.copytree(project / 'src' / 'locale', module_root / 'locale')
    for filename in ('LICENSE', 'THIRD_PARTY_LICENSES.txt'):
        shutil.copy2(project / filename, resource_root / filename)
    monkeypatch.setattr(sys, 'frozen', layout != 'source', raising=False)
    if layout != 'source':
        monkeypatch.setattr(sys, '_MEIPASS', str(resource_root), raising=False)
    monkeypatch.chdir(tmp_path)
    loaded = {}
    for name in ('metadata', 'i18n'):
        path = modules_dir / f'{name}.py'
        shutil.copy2(project / 'src' / 'modules' / path.name, path)
        spec = importlib.util.spec_from_file_location(f'relocated_{name}', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        loaded[name] = module

    text = loaded['metadata'].get_license_text()
    for filename in ('LICENSE', 'THIRD_PARTY_LICENSES.txt'):
        assert (project / filename).read_text(encoding='utf-8') in text
    translator = loaded['i18n'].Translator('en')
    assert translator.t('menu.file') == 'File'
    translator.switch_language('de')
    assert translator.t('menu.file') == 'Datei'
    translator.switch_language('en')
    assert translator.t('menu.file') == 'File'
