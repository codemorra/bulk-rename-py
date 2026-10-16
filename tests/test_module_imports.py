"""Tests for independent core imports and lazy resource loading."""

import importlib.util
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
