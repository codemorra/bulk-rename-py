# Bulk Rename Py - Tests

## Test Overview

- File renaming operations
- Token replacement and slicing
- Case transformations
- Path validation
- Conflict detection
- Regex replacements
- Edge cases handled

## Requirements

```bash
python -m pip install -r requirements.txt -r tests/requirements.txt
```

## Run Tests

### All tests
Run from the repository root. The root-level `pytest.ini` configures test discovery
and the source import path.

```bash
python -m pytest
```

### Specific test
```bash
python -m pytest tests/test_renamer.py::TestRenamer::test_preview_names_basic -v
```

## Known Regression Tests

`test_regressions.py` records confirmed issues in file preservation, duplicate
numbering, regex options, filename validation, and Windows preflight validation.
These tests temporarily use strict `xfail` markers with a reason and an expected
exception type. They execute normally and report the known failures explicitly.
An unexpected pass fails the suite so the marker must be removed when the issue
is fixed. Overwrite regressions are marked as expected failures only on Unix-like
systems, where the current rename operation replaces existing files.

Show the reasons for expected failures with:

```bash
python -m pytest -rx
```

File operation tests use temporary directories and verify file contents. The
Windows preflight test simulates the platform check without opening GUI dialogs;
it does not replace testing the application on Windows.
