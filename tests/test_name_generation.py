"""Tests for final-name duplicate grouping, replacement options, and timestamps."""

import os
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from modules.core import renamer, tokens
from modules.core.renamer import Renamer
from modules.core.tokens import TokenProcessor
from modules.core.types import ReplaceCfg
from modules.core.validation import Validator


class TestDuplicateGrouping:
    """Test counters against complete transformed names in each directory."""

    @pytest.mark.parametrize('names, extension, expected', [
        (['a.txt', 'b.jpg'], '{ext}', ['doc.txt', 'doc.jpg']),
        (['a.txt', 'b.jpg'], 'dat', ['doc001.dat', 'doc002.dat']),
    ])
    def test_extension_affects_duplicate_group(
            self, tmp_path, basic_rename_config, names, extension, expected):
        """Test that both the original and configured extensions affect grouping."""
        cfg = basic_rename_config
        cfg.counter.dupes_only = True
        cfg.mask.name_mask = 'doc{counter}'
        cfg.mask.ext_mask = extension

        assert Renamer.preview_names([tmp_path / name for name in names], cfg) == expected

    def test_identical_names_in_different_directories(self, tmp_path, basic_rename_config):
        """Test that files in independent directories do not share a counter."""
        cfg = basic_rename_config
        cfg.counter.dupes_only = True
        cfg.mask.name_mask = 'doc{counter}'
        paths = [tmp_path / folder / 'a.txt' for folder in ('first', 'second')]

        assert Renamer.preview_names(paths, cfg) == ['doc.txt', 'doc.txt']

    def test_replacement_affects_duplicate_group(self, tmp_path, basic_rename_config):
        """Test duplicates created by search and replacement."""
        cfg = basic_rename_config
        cfg.counter.dupes_only = True
        cfg.mask.name_mask = '{name}{counter}'
        cfg.repl = ReplaceCfg('[ab]', 'doc', True, False, True, True, False)

        assert Renamer.preview_names([tmp_path / 'a.txt', tmp_path / 'b.txt'], cfg) == [
            'doc001.txt', 'doc002.txt'
        ]

    def test_windows_sanitization_affects_duplicate_group(self, tmp_path, basic_rename_config):
        """Test duplicates created by replacing illegal Windows characters."""
        cfg = basic_rename_config
        cfg.counter.dupes_only = True
        cfg.case.windows_names = True
        cfg.mask.name_mask = '{name}{counter}'

        assert Renamer.preview_names([tmp_path / 'x<.txt', tmp_path / 'x>.txt'], cfg) == [
            'x_001.txt', 'x_002.txt'
        ]

    def test_counter_in_extension(self, tmp_path, basic_rename_config):
        """Test duplicate numbering when the counter appears only in the extension."""
        cfg = basic_rename_config
        cfg.counter.dupes_only = True
        cfg.mask.name_mask = 'same'
        cfg.mask.ext_mask = '{counter}{ext}'

        assert Renamer.preview_names([tmp_path / 'a.txt', tmp_path / 'b.txt'], cfg) == [
            'same.001txt', 'same.002txt'
        ]

    def test_counter_start_and_step(self, tmp_path, basic_rename_config):
        """Test that duplicate groups use the configured start, step, and width."""
        cfg = basic_rename_config
        cfg.counter.dupes_only = True
        cfg.counter.start, cfg.counter.step, cfg.counter.digits = 5, 3, 2
        cfg.mask.name_mask = 'doc{counter}'

        assert Renamer.preview_names([tmp_path / 'a.txt', tmp_path / 'b.txt'], cfg) == [
            'doc05.txt', 'doc08.txt'
        ]

    def test_missing_counter_token_does_not_hide_conflicts(self, tmp_path, basic_rename_config):
        """Test that duplicate mode does not invent a missing counter placeholder."""
        cfg = basic_rename_config
        cfg.counter.dupes_only = True
        cfg.mask.name_mask = 'doc'
        paths = [tmp_path / 'a.txt', tmp_path / 'b.txt']

        names = Renamer.preview_names(paths, cfg)

        assert names == ['doc.txt', 'doc.txt']
        assert Validator.check_conflicts(Renamer.plan_moves(paths, names))

    @pytest.mark.skipif(os.name == 'nt', reason='Unix slash replacement only applies on Unix-like systems')
    def test_linux_sanitization_affects_duplicate_group(self, tmp_path, basic_rename_config):
        """Test duplicates created by replacing slashes in generated Unix names."""
        cfg = basic_rename_config
        cfg.counter.dupes_only = True
        cfg.mask.name_mask = '{name}{counter}'
        cfg.repl = ReplaceCfg('x', '/', False, False, True, True, False)

        assert Renamer.preview_names([tmp_path / 'x.txt', tmp_path / '⁄.txt'], cfg) == [
            '⁄001.txt', '⁄002.txt'
        ]


class TestReplacementOptions:
    """Test consistent options and error reporting for regex and wildcard search."""

    @pytest.mark.parametrize('regex', [False, True])
    @pytest.mark.parametrize('case_sensitive, exact, first_only, expected', [
        (False, True, False, 'X X abcd X.txt'),
        (False, False, False, 'X X Xd X.txt'),
        (True, True, False, 'ABC X abcd X.txt'),
        (True, True, True, 'ABC X abcd abc.txt'),
    ])
    def test_search_options(self, basic_rename_config, regex, case_sensitive, exact, first_only, expected):
        """Test that both search modes honor case, whole-word, and first-match options."""
        cfg = basic_rename_config
        cfg.mask.name_mask = '{name}'
        cfg.repl = ReplaceCfg('abc', 'X', regex, exact, case_sensitive, True, first_only)

        assert Renamer.preview_names([Path('ABC abc abcd abc.txt')], cfg) == [expected]

    @pytest.mark.parametrize('pattern, replacement', [
        ('[', 'x'), ('(x)', r'\2'), ('(?P<name>x)', r'\g<missing>'), ('x', r'\q'),
    ])
    def test_invalid_regex_is_reported(self, basic_rename_config, pattern, replacement):
        """Test invalid patterns and replacement references before generating names."""
        cfg = basic_rename_config
        cfg.repl = ReplaceCfg(pattern, replacement, True, False, True, True, False)

        with pytest.raises(ValueError, match='Invalid search or replacement pattern'):
            Renamer.preview_names([Path('x.txt')], cfg)

    @pytest.mark.parametrize('replacement', [r'\1', r'\g<missing>', r'\q'])
    def test_wildcard_replacement_is_literal(self, replacement):
        """Test that replacement text is not interpreted as regex syntax in wildcard mode."""
        cfg = ReplaceCfg('abc', replacement, False, False, True, True, False)

        assert Renamer._apply_replace('abc', cfg) == replacement

    def test_regex_backreferences(self, basic_rename_config):
        """Test that valid regex replacement references remain supported."""
        cfg = basic_rename_config
        cfg.mask.name_mask = '{name}'
        cfg.repl = ReplaceCfg(r'(img)(\d+)', r'\2_\1', True, False, True, True, False)

        assert Renamer.preview_names([Path('img12.txt')], cfg) == ['12_img.txt']

    @pytest.mark.parametrize('pattern, expected', [('a*e', 'X_middle_a2e.txt'), ('a**e', 'X.txt')])
    def test_wildcard_greediness(self, basic_rename_config, pattern, expected):
        """Test the documented difference between single and double asterisks."""
        cfg = basic_rename_config
        cfg.mask.name_mask = '{name}'
        cfg.repl = ReplaceCfg(pattern, 'X', False, False, True, True, True)

        assert Renamer.preview_names([Path('a1e_middle_a2e.txt')], cfg) == [expected]

    def test_pattern_is_prepared_once(self, basic_rename_config, tmp_path, monkeypatch):
        """Test that duplicate generation reuses the prepared search pattern."""
        cfg = basic_rename_config
        cfg.counter.dupes_only = True
        cfg.mask.name_mask = 'doc{counter}'
        cfg.repl = ReplaceCfg('doc', 'file', False, False, True, True, False)
        prepare = Renamer._compile_search_replace_pattern
        calls = []

        def counted_prepare(*args):
            calls.append(args)
            return prepare(*args)

        monkeypatch.setattr(Renamer, '_compile_search_replace_pattern', counted_prepare)

        assert Renamer.preview_names([tmp_path / f'{i}.txt' for i in range(10)], cfg) == [
            f'file{i:03d}.txt' for i in range(1, 11)
        ]
        assert len(calls) == 1


class TestTimestampConsistency:
    """Test shared timestamps across built-in and custom date and time tokens."""

    def test_current_time_is_shared_across_preview(self, basic_rename_config, monkeypatch):
        """Test a preview spanning midnight without mixing dates or times."""
        cfg = basic_rename_config
        cfg.mask.name_mask = '{name}_{date}_{time}_{yyyy-mm-dd}_{hh-mm-ss}'
        cfg.mask.ext_mask = '{ext}_{yyyy_mm}_{hhmm}'
        calls = []

        class MovingDatetime(datetime):
            @classmethod
            def now(cls):
                calls.append(None)
                if len(calls) == 1:
                    return cls(2026, 12, 31, 23, 59, 59)
                return cls(2027, 1, 1)

        monkeypatch.setattr(renamer, 'datetime', MovingDatetime)
        monkeypatch.setattr(tokens, 'datetime', MovingDatetime)

        assert Renamer.preview_names([Path('a.txt'), Path('b.txt')], cfg) == [
            f'{name}_20261231_235959_2026-12-31_23-59-59.txt_2026_12_2359'
            for name in ('a', 'b')
        ]
        assert len(calls) == 1

    def test_modification_time_is_read_once(self, tmp_path, basic_rename_config, monkeypatch):
        """Test reuse of file metadata in both duplicate passes and custom tokens."""
        cfg = basic_rename_config
        cfg.dt.date_type = 'change'
        cfg.counter.dupes_only = True
        cfg.mask.name_mask = '{date}_{time}_{yyyy-mm-dd}_{hh-mm-ss}_{counter}'
        cfg.mask.ext_mask = '{ext}_{yyyy_mm}_{hhmm}'
        paths = [tmp_path / 'a.txt', tmp_path / 'b.txt']
        timestamp = datetime(2020, 2, 3, 4, 5, 6).timestamp()
        stat = Path.stat
        calls = []

        def counted_stat(path, *args, **kwargs):
            if path in paths:
                calls.append(path)
                return SimpleNamespace(st_mtime=timestamp)
            return stat(path, *args, **kwargs)

        monkeypatch.setattr(Path, 'stat', counted_stat)

        assert Renamer.preview_names(paths, cfg) == [
            f'20200203_040506_2020-02-03_04-05-06_{i:03d}.txt_2020_02_0405'
            for i in (1, 2)
        ]
        assert calls == paths

    def test_unreadable_timestamp_uses_shared_fallback(self, tmp_path):
        """Test deterministic fallback when a file has disappeared before the preview."""
        now = datetime(2026, 10, 16, 12, 34, 56)

        assert TokenProcessor.get_datetime(tmp_path / 'missing.txt', 'change', now) == now

    def test_custom_extension_slicing(self, basic_rename_config):
        """Test extension slicing without counting the separating dot as a character."""
        cfg = basic_rename_config
        cfg.mask.name_mask = '{ext1-2}'
        cfg.mask.ext_mask = '{ext2-3}'

        assert Renamer.preview_names([Path('photo.jpeg')], cfg) == ['jp.pe']


class TestUnchangedNames:
    """Test that default masks preserve existing filename components."""

    @pytest.mark.parametrize('name', ['plain', 'file.txt', '.hidden', 'archive.tar.gz', "O'Brien.txt"])
    def test_default_masks_preserve_names(self, basic_rename_config, name):
        """Test unchanged extensions, dotfiles, and filenames without extensions."""
        cfg = basic_rename_config
        cfg.mask.name_mask = '{name}'

        assert Renamer.preview_names([Path(name)], cfg) == [name]

    @pytest.mark.skipif(os.name == 'nt', reason='Windows does not support trailing dots in filenames')
    def test_default_masks_preserve_unix_trailing_dot(self, basic_rename_config):
        """Test the lone-dot suffix recognized by pathlib starting with Python 3.14."""
        cfg = basic_rename_config
        cfg.mask.name_mask = '{name}'

        assert Renamer.preview_names([Path('file.')], cfg) == ['file.']
