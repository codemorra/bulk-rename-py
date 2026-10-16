"""Tests for configuration validation, atomic persistence, and shared GUI settings."""

import configparser

import pytest
from PySide6.QtCore import QEvent

from modules import settings
from modules.gui import main_window


@pytest.fixture
def isolated_settings(tmp_path, monkeypatch):
    """Redirect all settings operations to a temporary directory."""
    directory = tmp_path / 'config'
    monkeypatch.setattr(settings, 'CONFIG_DIR', directory)
    monkeypatch.setattr(settings, 'CONFIG_FILE', directory / 'config.ini')
    monkeypatch.setattr(settings, '_detect_system_language', lambda: 'en')
    return settings.get_config()


class TestConfiguration:
    """Test validation on both reads and writes without modifying user settings."""

    @pytest.mark.parametrize('section, key, value, expected', [
        ('counter', 'start', 999999, '999999'),
        ('counter', 'step', 9999, '9999'),
        ('counter', 'step', 0, '1'),
        ('counter', 'digits', 100, '10'),
        ('counter', 'start', 'invalid', '1'),
        ('general', 'language', 'invalid', 'en'),
        ('rename', 'date_format', '100%', 'YYYYMMDD'),
        ('replace', 'regex', 'yes', 'True'),
    ])
    def test_updates_are_validated_and_persisted(self, isolated_settings, section, key, value, expected):
        """Test that returned settings match the sanitized values stored on disk."""
        result = settings.set_cfg(section, key, value)

        assert result.get(section, key) == expected
        assert settings.get_config().get(section, key) == expected
        assert not list(settings.CONFIG_DIR.glob('.config-*.tmp'))

    def test_windows_names_are_enforced_on_read_and_reset(self, isolated_settings, monkeypatch):
        """Test that Windows rules belong to configuration rather than duplicate GUI writes."""
        isolated_settings.set('advanced', 'windows_names', 'False')
        settings._save_config(isolated_settings)
        monkeypatch.setattr(settings, 'IS_WINDOWS', True)

        assert settings.get_config().getboolean('advanced', 'windows_names')
        settings.reset_config(autodetect_language=False)
        assert settings.get_config().getboolean('advanced', 'windows_names')

    @pytest.mark.parametrize('contents', [b'not an ini file', b'[general]\nlanguage=\xff',
                                          b'[general]\n[general]\n'])
    def test_unreadable_configuration_is_not_overwritten(self, isolated_settings, contents):
        """Test that malformed data produces a clear error and remains available for recovery."""
        settings.CONFIG_FILE.write_bytes(contents)

        with pytest.raises(RuntimeError, match='Failed to read configuration'):
            settings.get_config()
        assert settings.CONFIG_FILE.read_bytes() == contents

    @pytest.mark.parametrize('stage', ['write', 'flush', 'replace'])
    def test_failed_write_preserves_previous_file(self, isolated_settings, monkeypatch, stage):
        """Test preservation of the old configuration at each failing persistence step."""
        before = settings.CONFIG_FILE.read_bytes()

        def fail(*args, **kwargs):
            raise OSError('simulated settings failure')

        if stage == 'write':
            monkeypatch.setattr(configparser.ConfigParser, 'write', fail)
        elif stage == 'flush':
            monkeypatch.setattr(settings.os, 'fsync', fail)
        else:
            monkeypatch.setattr(settings.os, 'replace', fail)

        with pytest.raises(RuntimeError, match='Failed to save configuration'):
            settings.set_cfg('counter', 'start', 42)

        assert settings.CONFIG_FILE.read_bytes() == before
        assert not list(settings.CONFIG_DIR.glob('.config-*.tmp'))


def test_window_shares_managers_and_counter_limits(qt_application, isolated_settings, monkeypatch):
    """Test shared dependencies and a single configuration read during window creation."""
    calls = []
    load = main_window.get_config

    def counted_load():
        calls.append(None)
        return load()

    monkeypatch.setattr(main_window, 'get_config', counted_load)
    window = main_window.MainWindow()
    try:
        qt_application.processEvents()
        assert len(calls) == 1
        assert window.rename_manager.helpers is window.helpers
        assert window.table_manager.helpers is window.helpers
        assert window.about_dialog.helpers is window.helpers
        assert window.rename_manager.table_manager is window.table_manager
        for key, widget in [('start', window.spin_start), ('step', window.spin_step),
                            ('digits', window.spin_digits)]:
            assert (widget.minimum(), widget.maximum()) == settings.RANGES[('counter', key)]

        window.spin_start.setValue(999999)
        assert window.cfg.getint('counter', 'start') == 999999
        assert settings.get_config().getint('counter', 'start') == 999999
    finally:
        window._update_timer.stop()
        window.close()
        window.deleteLater()
        qt_application.sendPostedEvents(None, QEvent.DeferredDelete)


def test_settings_failure_is_reported_and_preview_is_scheduled(manager_factory, monkeypatch):
    """Test that a failed preference write is reported without interrupting preview updates."""
    from modules.gui import rename_manager

    manager, messages = manager_factory([])
    scheduled = []

    def fail(*args):
        raise RuntimeError('simulated settings failure')

    monkeypatch.setattr(rename_manager, 'set_cfg', fail)
    monkeypatch.setattr(manager.table_manager, 'update_preview_later', lambda: scheduled.append(True))

    manager.handle_config_change('counter', 'start', 42)

    assert scheduled == [True]
    assert any('simulated settings failure' in message for message in messages)
