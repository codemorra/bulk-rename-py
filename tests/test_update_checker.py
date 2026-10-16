"""Tests for numeric release versions and update response validation."""

import pytest
import requests

from modules import update_checker
from modules.update_checker import UpdateChecker, _version_tuple


@pytest.mark.parametrize('version, expected', [
    ('v1.2.3', (1, 2, 3)), (' V1.2.3 ', (1, 2, 3)),
    ('1.2', (1, 2, 0)), ('1', (1, 0, 0)), ('1.10.0', (1, 10, 0)),
])
def test_numeric_release_versions(version, expected):
    """Test normalized numeric comparison without collecting digits from suffixes."""
    assert _version_tuple(version) == expected


@pytest.mark.parametrize('version', ['', 'unknown', '1.2rc1', '1..2', '1.2.3.4', '1.2.0-beta.1'])
def test_invalid_release_versions_are_rejected(version):
    """Test rejection of tags that cannot be compared as stable numeric versions."""
    with pytest.raises(ValueError, match='Unsupported release version'):
        _version_tuple(version)


@pytest.mark.parametrize('data, expected', [
    ({'tag_name': 'v1.2.0', 'html_url': 'https://example.com/release'},
     ('available', 'https://example.com/release')),
    ({'tag_name': '1.1'}, ('none', 'https://github.com/example/project/releases')),
    ({'tag_name': '1.0.0'}, ('none', 'https://github.com/example/project/releases')),
    ({'tag_name': 'v1.2.0-beta.1'}, ('failed', 'https://github.com/example/project/releases')),
    ({'tag_name': 42}, ('failed', 'https://github.com/example/project/releases')),
    ([], ('failed', 'https://github.com/example/project/releases')),
])
def test_update_response_validation_and_cleanup(monkeypatch, data, expected):
    """Test release data handling and response closure without network requests."""
    closed = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            closed.append(True)

        def raise_for_status(self):
            return None

        def json(self):
            return data

    monkeypatch.setattr(update_checker.requests, 'get', lambda *args, **kwargs: Response())
    checker = UpdateChecker('example/project', '1.1.0')
    results = []
    checker.finished.connect(lambda status, url: results.append((status, url)))

    checker._run()

    assert results == [expected]
    assert closed == [True]


def test_network_error_emits_failed_status(monkeypatch):
    """Test that connection failures produce the normal update failure signal."""
    def fail(*args, **kwargs):
        raise requests.Timeout('simulated timeout')

    monkeypatch.setattr(update_checker.requests, 'get', fail)
    checker = UpdateChecker('example/project', '1.1.0')
    results = []
    checker.finished.connect(lambda status, url: results.append((status, url)))

    checker._run()

    assert results == [('failed', 'https://github.com/example/project/releases')]
