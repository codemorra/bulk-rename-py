"""Tests for file collection without duplicate paths or unused metadata reads."""

import os
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

from modules import importer
from modules.importer import Importer, ImportOptions


def test_imports_absolute_paths_and_scans_only_selected_directory(tmp_path, monkeypatch):
    """Test absolute paths, duplicate filtering, and non-recursive folder collection."""
    file = tmp_path / 'file.txt'
    file.write_text('content', encoding='utf-8')
    nested = tmp_path / 'nested'
    nested.mkdir()
    (nested / 'child.txt').write_text('content', encoding='utf-8')
    monkeypatch.chdir(tmp_path)

    result = Importer.collect(['file.txt', '.', file], ImportOptions(True, True, True))

    assert result == [file]
    assert all(isinstance(path, Path) and path.is_absolute() for path in result)


@pytest.mark.parametrize('files, directories, expected', [(False, True, False), (True, False, False),
                                                         (True, True, True)])
def test_import_options_control_folder_scanning(tmp_path, files, directories, expected):
    """Test that disabled file or directory collection does not import folder contents."""
    path = tmp_path / 'file.txt'
    path.write_text('content', encoding='utf-8')

    assert Importer.collect([tmp_path], ImportOptions(files, directories, True)) == (
        [path] if expected else []
    )


@pytest.mark.skipif(os.name == 'nt', reason='Unix hidden files use the leading-dot convention')
def test_hidden_file_options_apply_to_files_and_folders(tmp_path):
    """Test the same visibility filter for explicit files and scanned folder contents."""
    hidden = tmp_path / '.hidden'
    hidden.write_text('content', encoding='utf-8')
    visible = tmp_path / 'visible'
    visible.write_text('content', encoding='utf-8')

    assert Importer.collect([hidden, tmp_path], ImportOptions(True, True, False)) == [visible]
    assert set(Importer.collect([tmp_path], ImportOptions(True, True, True))) == {hidden, visible}


def test_directory_aliases_do_not_duplicate_entries(tmp_path):
    """Test duplicate filtering through aliases without following final file symlinks."""
    file = tmp_path / 'file.txt'
    file.write_text('content', encoding='utf-8')
    directory_alias = tmp_path / 'alias'
    file_alias = tmp_path / 'file-link.txt'
    try:
        directory_alias.symlink_to(tmp_path, target_is_directory=True)
        file_alias.symlink_to(file)
    except OSError:
        pytest.skip('Symlink creation is unavailable')

    assert Importer.collect([file, directory_alias / file.name, file_alias],
                            ImportOptions(True, True, True)) == [file, file_alias]


@pytest.mark.parametrize('attributes, expected', [(0, False), (stat.FILE_ATTRIBUTE_HIDDEN, True),
                                                  (stat.FILE_ATTRIBUTE_SYSTEM, True)])
def test_windows_hidden_attributes_use_native_stat(tmp_path, monkeypatch, attributes, expected):
    """Test Windows visibility flags without accessing the Win32 API through ctypes."""
    file = tmp_path / 'file.txt'
    monkeypatch.setattr(importer, 'os', SimpleNamespace(name='nt'))
    monkeypatch.setattr(Path, 'stat', lambda *args, **kwargs: SimpleNamespace(st_file_attributes=attributes))

    assert Importer._is_hidden(file) is expected
