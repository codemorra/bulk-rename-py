# Bulk Rename Py - Tests

## Test Overview

- File renaming operations, name swaps, and rename chains
- Rollback after staging and destination failures
- Table and undo history after incomplete rollback
- Destination conflicts, including files created during execution
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
Unresolved regression tests temporarily use strict `xfail` markers with a reason
and an expected exception type. They execute normally and report the known failures explicitly.
An unexpected pass fails the suite so the marker must be removed when the issue
is fixed. File preservation, name swaps, occupied undo destinations, and Windows
preflight validation now pass without expected-failure markers.

Show the reasons for expected failures with:

```bash
python -m pytest -rx
```

File operation tests use temporary directories and verify file contents. The
Windows preflight test simulates the platform check without opening GUI dialogs;
it does not replace testing the application on Windows.

`test_file_operations.py` injects failures during execution and rollback and
checks the reported recovery paths. `test_rename_manager.py` uses real Qt table
cells with the offscreen platform plugin and intercepts confirmation dialogs;
it does not open the main window or read user settings.

## Lint Checks

Ruff is included in `tests/requirements.txt`. Run it for the Python files being
changed, for example:

```bash
python -m ruff check src/modules/core/file_operations.py tests
```
